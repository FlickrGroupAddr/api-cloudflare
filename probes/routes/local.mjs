// Miniflare requires Node; lifecycle, HTTP probes and evidence stay in Python.
import { readFile } from "node:fs/promises";
import { Miniflare } from "miniflare";
import { createServer, request as upstreamRequest } from "node:http";
import { safePath } from "./worker.ts";
const config = JSON.parse(await readFile(process.argv[2], "utf8"));
let outboundCalls = 0;
const mf = new Miniflare({ modules: true, scriptPath: config.main,
  compatibilityDate: config.compatibility_date, compatibilityFlags: config.compatibility_flags,
  host: "127.0.0.1", port: 0,
  cf: false, logRequests: false, telemetry: { enabled: false }, bindings: config.vars,
  assets: { directory: config.assets.directory, binding: config.assets.binding,
    routerConfig: { has_user_worker: true, invoke_user_worker_ahead_of_assets: config.assets.run_worker_first },
    assetConfig: { html_handling: config.assets.html_handling, not_found_handling: config.assets.not_found_handling } },
  outboundService() { outboundCalls++; throw new Error("external_network_forbidden"); },
});
// Node exposes the unparsed request target. Reject it before Miniflare's URL parser
// can erase backslashes. The proxy forwards every accepted target unchanged.
const upstream = await mf.ready;
const server = createServer((req, res) => {
  if (!req.url?.startsWith("/") || safePath("http://local.invalid" + req.url) === null) {
    res.writeHead(400, { "Content-Type": "application/json", "Cache-Control": "no-store",
      "X-FGA-Routing-Component": "raw-target-guard", "X-FGA-Routing-Build": config.vars.PROOF_BUILD_ID });
    res.end('{"error":"invalid_request_target"}');
    return;
  }
  const forward = upstreamRequest({ hostname: upstream.hostname, port: upstream.port,
    path: req.url, method: req.method, headers: req.headers }, reply => {
    res.writeHead(reply.statusCode, reply.headers);
    reply.pipe(res);
  });
  forward.on("error", () => { res.writeHead(502); res.end(); });
  req.pipe(forward);
});
try {
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  console.log(JSON.stringify({ url: `http://127.0.0.1:${server.address().port}` }));
  process.stdin.resume();
  await new Promise(resolve => process.stdin.once("end", resolve));
  console.log(JSON.stringify({ outboundCalls }));
} finally {
  await new Promise(resolve => server.close(resolve));
  await mf.dispose();
}
