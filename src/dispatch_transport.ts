import { FlickrFailure, DispatchTransportError, ProvenNotDispatched } from "./dispatch_policy.ts";
export { DispatchTransportError, ProvenNotDispatched } from "./dispatch_policy.ts";
import OAuth from "oauth-1.0a";
import type { AttemptContext, PreparedAdd, Transport } from "./fail_polite.ts";
import { applicationEnvelope, hmac, readJson, type Application, type FlickrFetch,
  type Pair, type SecretReads } from "./flickr_reads.ts";

const REST = "https://www.flickr.com/services/rest/";
const ID = /^[A-Za-z0-9][A-Za-z0-9@._:-]{0,127}$/;
type Method = "flickr.photos.getAllContexts" | "flickr.groups.getInfo" | "flickr.groups.pools.add";


function signed(method: Method, context: AttemptContext, pair: Pair, app: Application): Request {
  const post = method === "flickr.groups.pools.add";
  const data: Record<string, string> = { method, format: "json", nojsoncallback: "1" };
  if (method !== "flickr.groups.getInfo") data.photo_id = context.photoId;
  if (method !== "flickr.photos.getAllContexts") data.group_id = context.groupId;
  const url = new URL(REST);
  if (!post) url.search = new URLSearchParams(data).toString();
  const oauth = new OAuth({ consumer: { key: app.consumerKey, secret: app.consumerSecret },
    signature_method: "HMAC-SHA1", hash_function: hmac });
  oauth.getNonce = () => Array.from(crypto.getRandomValues(new Uint8Array(32)),
    b => b.toString(16).padStart(2, "0")).join("");
  const authorization = oauth.toHeader(oauth.authorize(
    { url: String(url), method: post ? "POST" : "GET", ...(post ? { data } : {}) },
    { key: pair.token, secret: pair.tokenSecret }));
  return new Request(url, { method: post ? "POST" : "GET", redirect: "manual",
    headers: { ...authorization, Accept: "application/json",
      ...(post ? { "Content-Type": "application/x-www-form-urlencoded" } : {}) },
    ...(post ? { body: new URLSearchParams(data).toString() } : {}) });
}

export function membershipPresent(value: Record<string, unknown>, groupId: string): boolean {
  if(value.stat==="fail"&&typeof value.code==="number"&&Number.isSafeInteger(value.code))throw new FlickrFailure(value.code);
  if (value.stat !== "ok" || !Array.isArray(value.pool) || value.pool.length > 256)
    throw new DispatchTransportError();
  const ids = new Set<string>();
  for (const entry of value.pool) {
    if (!entry || typeof entry !== "object" || Array.isArray(entry)) throw new DispatchTransportError();
    const pool = entry as Record<string, unknown>;
    if (typeof pool.id !== "string" || !ID.test(pool.id) || ids.has(pool.id) ||
        typeof pool.title !== "string" || pool.title.length > 1024 || /[\x00-\x1f\x7f]/.test(pool.title))
      throw new DispatchTransportError();
    ids.add(pool.id);
  }
  return ids.has(groupId);
}

export function moderationValue(value: Record<string, unknown>, groupId: string): 0 | 1 {
  const group = value.group;
  if(value.stat==="fail"&&typeof value.code==="number"&&Number.isSafeInteger(value.code))throw new FlickrFailure(value.code);
  if (value.stat !== "ok" || !group || typeof group !== "object" || Array.isArray(group))
    throw new DispatchTransportError();
  const record = group as Record<string, unknown>;
  if (record.id !== groupId || ![0, 1, "0", "1"].includes(record.ispoolmoderated as number | string))
    throw new DispatchTransportError();
  return Number(record.ispoolmoderated) as 0 | 1;
}

async function addResult(response: Response): Promise<"ok" | number> {
  if (!response.ok || !/^application\/json(?:;|$)/i.test(response.headers.get("Content-Type") ?? "") || !response.body)
    throw new DispatchTransportError();
  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8", { fatal: true, ignoreBOM: false });
  let count = 0, text = "";
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      count += value.length;
      if (count > 262144) throw new DispatchTransportError();
      text += decoder.decode(value, { stream: true });
    }
    text += decoder.decode();
    const value: unknown = JSON.parse(text);
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new DispatchTransportError();
    const result = value as Record<string, unknown>;
    if (result.stat === "ok") return "ok";
    if (result.stat === "fail" && typeof result.code === "number" && Number.isSafeInteger(result.code)) return result.code;
    throw new DispatchTransportError();
  } catch {
    await reader.cancel().catch(() => {});
    throw new DispatchTransportError();
  } finally { reader.releaseLock(); }
}

/** One attempt, one fixed Flickr endpoint, and one already-prepared POST handoff.
 * assertCurrent must read current D1/native authority; the caller's final marker
 * transaction must still fence the captured link and gate revisions atomically.
 * The transport is a candidate until the complete production gate passes.
 */
export async function createDispatchTransport(
  secrets: SecretReads, generation: string, assertCurrent: () => Promise<void>,
  fetcher: FlickrFetch = request => fetch(request),
): Promise<Transport> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 10000);
  let raw: string, appRaw: string;
  try {
    [raw, appRaw] = await Promise.race([
      Promise.all([secrets.FLICKR_GRANT.get(), secrets.FLICKR_APPLICATION.get()]),
      new Promise<never>((_, reject) => controller.signal.addEventListener("abort", () => reject(new DispatchTransportError()), { once: true })),
    ]);
  } catch { throw new DispatchTransportError(); }
  finally { clearTimeout(timer); }
  if (typeof raw !== "string" || raw.length > 8192) throw new DispatchTransportError();
  let grant: Record<string, unknown>;
  try { grant = JSON.parse(raw); } catch { throw new DispatchTransportError(); }
  const opaque = (value: unknown): value is string => typeof value === "string" && value.length > 0 && value.length <= 2048 && !/[\x00-\x20\x7f]/.test(value);
  if (raw.length > 8192 || !grant || typeof grant !== "object" || Array.isArray(grant) ||
      Object.keys(grant).sort().join() !== "generation,schemaVersion,token,tokenSecret" ||
      grant.schemaVersion !== 1 || grant.generation !== generation || !opaque(grant.token) || !opaque(grant.tokenSecret))
    throw new DispatchTransportError();
  const app = applicationEnvelope(appRaw);
  const pair = { token: grant.token, tokenSecret: grant.tokenSecret };
  await assertCurrent();
  let identity: string | null = null;
  let phase: "new" | "reading" | "absent" | "preflight" | "prepared" = "new";
  const bind = (context: AttemptContext) => {
    if (![context.attemptId, context.photoId, context.groupId].every(value => typeof value === "string" && ID.test(value)))
      throw new DispatchTransportError();
    const key = JSON.stringify([context.attemptId, context.photoId, context.groupId]);
    if (identity !== null && identity !== key) throw new DispatchTransportError();
    identity = key;
  };
  return {
    async membership(context) {
      bind(context);
      if (phase !== "new") throw new DispatchTransportError();
      phase = "reading";
      await assertCurrent();
      const present = membershipPresent(await readJson(signed("flickr.photos.getAllContexts", context, pair, app), fetcher), context.groupId);
      if (!present) phase = "absent";
      return present;
    },
    async preflight(context) {
      bind(context);
      if (phase !== "absent") throw new DispatchTransportError();
      phase = "reading";
      await assertCurrent();
      const moderated = moderationValue(await readJson(signed("flickr.groups.getInfo", context, pair, app), fetcher), context.groupId);
      phase = "preflight";
      return moderated;
    },
    async prepareAdd(context): Promise<PreparedAdd> {
      bind(context);
      if (phase !== "preflight") throw new DispatchTransportError();
      phase = "prepared";
      await assertCurrent();
      const abort = new AbortController();
      const deadline = setTimeout(() => abort.abort(), 10000);
      let request: Request;
      try { request = new Request(signed("flickr.groups.pools.add", context, pair, app), { signal: abort.signal }); }
      catch { clearTimeout(deadline); throw new DispatchTransportError(); }
      let handedOff = false, disposed = false;
      return {
        handoff() {
          if (handedOff) throw new DispatchTransportError();
          if (disposed || abort.signal.aborted) throw new ProvenNotDispatched();
          handedOff = true;
          // No signing, request construction, body serialization or await here.
          let response: Promise<Response>;
          try { response = fetcher(request); } catch { throw new DispatchTransportError(); }
          return response.then(addResult).catch(() => { throw new DispatchTransportError(); });
        },
        dispose() { disposed = true; clearTimeout(deadline); abort.abort(); },
      };
    },
  };
}
