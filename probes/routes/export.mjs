// Native Node import is the small bridge to the typed, executable registry.
import { ASSET_CONFIG, ASSET_PREFIX, GUARDS, ROUTES, SHELL_PATHS, validateRegistry } from "./registry.ts";
validateRegistry();
const routes = [...ROUTES].sort((a, b) => a.id.localeCompare(b.id, "en"));
const paths = {};
for (const r of routes) {
  const operation = { operationId: r.id, "x-routing-proof-only": true,
    description: "Isolated routing fixture. Authentication and business operations are not implemented.",
    responses: { [r.expectedStatus]: { description: `Safe ${r.probe} routing discriminator` } },
    parameters: [...r.pathPattern.matchAll(/\{([a-z_]+)\}/g)].map(m => ({ name: m[1], in: "path", required: true, schema: { type: "string" } })) };
  (paths[r.pathPattern] ??= {})[r.method.toLowerCase()] = operation;
}
console.log(JSON.stringify({ inventory: { schemaVersion: 1, scope: "isolated-routing-proof",
  routes, guards: GUARDS, shellPaths: SHELL_PATHS, assetPrefix: ASSET_PREFIX },
  assetConfig: ASSET_CONFIG,
  openapi: { openapi: "3.1.0", info: { title: "FGA routing proof (not production API)", version: "0.0.0" }, paths } }));
