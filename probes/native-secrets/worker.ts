import { Authority, Refusal, observe, resolve } from "./lifecycle.ts";
interface Env { DB: D1Database; GRANT: SecretsStoreSecret; PROOF_TOKEN: string; PROOF_CONFIG: string; }
interface Config { runId: string; generations: string[]; build: string; expires: number; instance?: string; }
function response(status: number, body: unknown) {
  return Response.json(body, { status, headers: { "Cache-Control": "no-store" } });
}
export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    if (!env.PROOF_TOKEN || request.headers.get("Authorization") !== `Bearer ${env.PROOF_TOKEN}`) {
      return response(401, { error: "unauthorized" });
    }
    let config: Config;
    try { config = JSON.parse(env.PROOF_CONFIG); } catch { return response(503, { error: "config" }); }
    if (!/^rp-[a-f0-9]{24}$/.test(config.runId) || !Number.isFinite(config.expires) ||
      !Array.isArray(config.generations) || config.generations.length !== 3 ||
      !config.generations.every(g => /^[a-f0-9-]{36}$/.test(g))) return response(503, { error: "config" });
    if (Date.now() >= config.expires) return response(410, { error: "expired" });
    const url = new URL(request.url);
    if (url.search || !["/ready", "/probe"].includes(url.pathname)) return response(404, { error: "route" });
    if (url.pathname === "/ready" && request.method === "GET") return response(200, { build: config.build, instance: config.instance });
    if (url.pathname !== "/probe" || request.method !== "POST") return response(405, { error: "method" });
    try {
      const text = await request.text();
      if (text.length > 512) throw new Refusal("body");
      const body = JSON.parse(text);
      if (!body || Object.keys(body).sort().join() !== "action,expected,index,operation" ||
          !Number.isSafeInteger(body.expected) || body.expected < 0 ||
          !Number.isInteger(body.index) || body.index < 0 || body.index > 2 ||
          !config.generations.includes(body.operation)) throw new Refusal("body");
      const authority = new Authority(env.DB, config.runId);
      const generation = config.generations[body.index];
      let result: unknown;
      switch (body.action) {
        case "preflight": result = true; break;
        case "state": result = await authority.state(); break;
        case "audit": result = await env.DB.prepare("SELECT revision,state FROM events ORDER BY revision").all(); break;
        case "attempts": result = await env.DB.prepare("SELECT operation,expected,kind FROM attempts").all(); break;
        case "observe": result = await observe(env.GRANT, config.generations); break;
        case "resolve": result = await resolve(() => authority.state(), env.GRANT, config.generations); break;
        case "binding": {
          // Hosted bindings may return callable RPC stubs for unsupported method names.
          // Invoke only against this run's synthetic name; mere property presence proves nothing.
          const grant = env.GRANT as unknown as { put?: (name: string, value: string) => Promise<unknown> };
          const present = typeof grant.put === "function";
          let writeAttemptRejected = !present;
          if (present) {
            let timer: ReturnType<typeof setTimeout> | undefined;
            try {
              const outcome = await Promise.race([
                grant.put!(`fga-native-${config.runId.slice(3)}`, "synthetic-binding-write-test")
                  .then(() => "accepted", () => "rejected"),
                new Promise<string>(done => { timer = setTimeout(() => done("timeout"), 10_000); }),
              ]);
              writeAttemptRejected = outcome === "rejected";
            } catch { writeAttemptRejected = true; }
            finally { if (timer !== undefined) clearTimeout(timer); }
          }
          result = { read: typeof env.GRANT.get === "function", writeMethodPresent: present,
            writeAttemptRejected,
            managementCredentialPresent: Object.keys(env).some(k => /TOKEN|KEY/.test(k) && k !== "PROOF_TOKEN") };
          break;
        }
        case "begin": result = await authority.begin("replace", body.expected, body.operation, generation); break;
        case "disconnect": result = await authority.begin("delete", body.expected, body.operation, generation); break;
        case "check-write": result = await authority.check("replace", body.expected, body.operation, generation); break;
        case "check-delete": result = await authority.check("delete", body.expected, body.operation, generation); break;
        case "activate": case "activate-fail": {
          await authority.check("replace", body.expected, body.operation, generation);
          const value = await observe(env.GRANT, config.generations);
          if (value.outcome !== "present" || value.generation !== generation) throw new Refusal("candidate_unavailable");
          result = await authority.activate(body.expected, body.operation, generation, body.action === "activate-fail");
          break;
        }
        case "confirm-retirement": {
          await authority.check("delete", body.expected, body.operation, generation);
          const value = await observe(env.GRANT, config.generations);
          if (value.outcome !== "retired" || value.generation !== generation) throw new Refusal("retirement_unconfirmed");
          result = await authority.confirmRetirement(body.expected, body.operation, generation);
          break;
        }
        default: throw new Refusal("action");
      }
      return response(200, { build: config.build, instance: config.instance, result });
    } catch (error) {
      const code = error instanceof Refusal ? error.message : error instanceof SyntaxError ? "body" : "operation_failed";
      return response(code === "body" || code === "action" ? 400 : 409, { build: config.build, instance: config.instance, error: code });
    }
  },
};
