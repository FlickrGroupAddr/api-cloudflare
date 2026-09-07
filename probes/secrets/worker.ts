import { SyntheticSecretsClient, ProbeError, type Generation, type Scope } from "./client.ts";
import { signedTransport, type Credentials } from "./transport.ts";

interface Env {
  PROOF_TOKEN: string;
  AWS_SESSION: string;
  PROOF_CONFIG: string;
}
interface Config {
  scope: Scope;
  generations: Generation[];
  build: string;
  expires: number;
}

function response(status: number, result: unknown): Response {
  return Response.json(result, { status, headers: { "Cache-Control": "no-store" } });
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    if (!env.PROOF_TOKEN || request.headers.get("Authorization") !== `Bearer ${env.PROOF_TOKEN}`) {
      return response(401, { error: "unauthorized" });
    }
    let stage = "config";
    try {
      const config = JSON.parse(env.PROOF_CONFIG) as Config;
      if (Date.now() > config.expires) return response(410, { error: "proof_expired" });
      const url = new URL(request.url);
      if (url.search || (url.pathname !== "/ready" && url.pathname !== "/probe")) {
        return response(404, { error: "not_found" });
      }
      if (url.pathname === "/ready" && request.method === "GET") {
        return response(200, { build: config.build });
      }
      if (url.pathname !== "/probe" || request.method !== "POST") {
        return response(405, { error: "method" });
      }
      const text = await request.text();
      if (text.length > 512) return response(400, { error: "body" });
      const body = JSON.parse(text);
      if (!body || Object.keys(body).sort().join() !== "action,index" ||
        !Number.isInteger(body.index) || body.index < 0 || body.index >= config.generations.length) {
        return response(400, { error: "body" });
      }
      if (body.action === "preflight") {
        return response(200, { build: config.build, result: true });
      }
      stage = "credentials";
      const credentials = JSON.parse(env.AWS_SESSION) as Credentials;
      stage = "client";
      const transport = signedTransport(credentials, config.scope.region, fetch);
      const client = new SyntheticSecretsClient(config.scope, transport);
      const generation = config.generations[body.index];
      const started = Date.now();
      let result: unknown;
      stage = "operation";
      if (body.action === "create") {
        result = await client.create(generation);
      } else if (body.action === "recover") {
        result = await client.recover(generation);
      } else if (["read", "delete", "wrong-version", "put-denied", "bad-token"].includes(body.action)) {
        const ref = await client.recover(generation);
        if (!ref) return response(409, { error: "not_visible", build: config.build });
        if (body.action === "read") {
          await client.read(ref);
          result = true;
        } else if (body.action === "delete") {
          await client.requestDeletion(ref);
          result = { requested: true };
        } else {
          const wrongVersion = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
          const put = body.action === "put-denied";
          const awsBody = put
            ? { SecretId: ref.arn, ClientRequestToken: wrongVersion, SecretString: "fga-synthetic-denial-test" }
            : { SecretId: ref.arn, VersionId: body.action === "wrong-version" ? wrongVersion : ref.version };
          const sender = body.action === "bad-token"
            ? signedTransport({ ...credentials, SessionToken: "invalid-synthetic-session" }, config.scope.region, fetch)
            : transport;
          const reply = await sender(new Request(client.endpoint, {
            method: "POST", redirect: "manual", signal: AbortSignal.timeout(10_000),
            headers: { "Content-Type": "application/x-amz-json-1.1",
              "X-Amz-Target": `secretsmanager.${put ? "PutSecretValue" : "GetSecretValue"}` },
            body: JSON.stringify(awsBody),
          }));
          const data = await reply.json() as Record<string, unknown>;
          const code = typeof data.__type === "string" ? data.__type.split("#").at(-1) : "";
          const expected = body.action === "wrong-version" ? ["ResourceNotFoundException"] :
            put ? ["AccessDeniedException"] : ["UnrecognizedClientException", "InvalidClientTokenId", "InvalidSignatureException"];
          result = { passed: reply.status === 400 && expected.includes(code ?? ""),
            status: reply.status, code: expected.includes(code ?? "") ? code : "unexpected" };
        }
      } else {
        return response(400, { error: "action" });
      }
      return response(200, { build: config.build, result, milliseconds: Date.now() - started });
    } catch (error) {
      const kind = error instanceof SyntaxError ? "syntax" :
        error instanceof TypeError ? "type" : "other";
      return response(502, { error: error instanceof ProbeError ? error.message : `probe_${stage}_${kind}` });
    }
  },
};
