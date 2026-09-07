# Isolated Worker routing proof

This fixture exercises the Cloudflare Worker and Static Assets routing boundary.
It is not the production FGA API backend. Authentication, database lookup, login
transactions, Flickr calls, and business mutations are deliberately unimplemented.
The fixture routing gate passes after the accepted early-provider-rejection
clarification; see the [current evidence](../../docs/research/2026-09-07-worker-routing-clarification.md).

## Structure

- `registry.ts` registers every fixture handler and owns namespace guards, the
  shell allowlist, and asset-routing configuration. `worker.ts` dispatches those
  registrations before assets, independent of HTTP method. All incoming paths
  invoke the Worker; only explicit `GET`/`HEAD` shell or asset paths reach ASSETS.
- `export.mjs` imports the same typed registry using Node's TypeScript support.
  It deterministically emits the versioned inventory and OpenAPI under
  `generated/`. Neither artifact lists a production origin or secrets. The
  OpenAPI describes only the fixture's safe response surface, with no invented
  successful database/authentication schemas.
  Generated JSON uses explicit LF line endings on both Windows and Linux so
  tracked snapshots and runtime artifact hashes agree.
- `scripts/route_conformance.py` runs the native TypeScript validation gate,
  generates artifacts and hashed static assets, bundles once, starts local HTTP,
  deploys the same bundle to a unique disposable Worker, repeats the matrix,
  binds observations to artifact digests and deployment identity, and deletes
  the Worker without force. It reuses the tested Wrangler/authentication/cleanup
  boundary from the runtime-permissions harness. No D1 database is created.
- `local.mjs` is the development topology: a loopback Node HTTP adapter validates
  the raw target using the Worker's shared validator, then forwards accepted
  requests unchanged to Miniflare's actual Worker/Static Assets router. This
  prevents the emulator's URL parser from erasing a backslash before validation.
  Node is required for Miniflare and this raw Node HTTP integration; orchestration
  and the black-box collector remain Python. Outbound Worker fetches are rejected
  and counted locally; the fixture has no hosted outbound-fetch call or secret.

Worker responses and raw local rejections carry isolated-fixture component/build
headers derived from the source digest. Ordinary responses must match the current
build. These diagnostics are confined to this probe and are not a production
health response design. Early provider rejection is accepted only for a malformed
target returning HTTP 400, without fixture markers, with the exact previously
observed provider body fingerprint, and without a cookie or redirect. An unknown
HTML body, application-generated HTML error, or provider error on a valid path
still fails. The accepted exception does not weaken application JSON/no-store.

The shell is a small fixture at `/admin/`, with a restrictive CSP, no-referrer,
nosniff, and no-store. No additional client-side navigation is currently
allowlisted. Exact files deliberately collide with registered handler paths;
the tests must still reach the Worker. Missing assets cannot become shell HTML.
The fixture returns fixed `401` responses for protected routes, `400` for invalid
login/callback probes, and `503 not_implemented` for login start. Its fixed
health responses prove routing only, not production startup/database readiness.

## Run from a Windows terminal in this checkout

```console
npm ci
npm run check
npm run routes:test
uv run --frozen python -m unittest discover -s tests -v
npm run route-conformance
```

The equivalent gate command is:

```console
uv run --frozen python scripts/route_conformance.py run
```

The gate requires an existing Wrangler login resolving exactly one account. It
uses a generated, checked-unused `fga-rp-<random>` name on workers.dev; it never
changes a production domain, zone rule, existing Worker, or database. It waits
for five consecutive successful health/API/shell readiness samples and at least 30
seconds of settling before two complete matrix sweeps, retains all readiness
samples and both sweeps, and verifies the deployment did not change during
collection. There is no skip-hosted or permissive promotion mode.
A mismatching phase keeps the command nonzero even when other tests pass.

Private run manifests, logs, generated local/deployment configurations, fixture
assets, readiness samples, and complete reports are beneath ignored
`.route-runs/rp-<random>/`. The source inventory and OpenAPI are tracked. Keep
private logs out of public evidence: Wrangler identity/deployment output can
contain account and author information. Collector results retain only case IDs,
status, media type, response digest, bounded error classifications, and numeric
provider error codes; no response bodies, cookies, credentials, or query values.
Wrangler disk logging and telemetry are disabled at the command boundary.

Cleanup runs even after mismatches. If cleanup fails, preserve the run directory
and retry its exact generated identity:

```console
uv run --frozen python scripts/route_conformance.py cleanup --run-directory .route-runs/rp-<random>
```

The hosted configuration requests compatibility date `2026-09-07`. The existing
stable Miniflare/workerd pins support `2026-08-06`; that local limitation is
explicit in the evidence. No local result claims the newer hosted runtime.

## Contract and proof limits

Accepted architecture ADRs 0016, 0031, 0037, 0043, and 0050 and
`architecture-design/docs/operations/http-route-conformance.md` control the
routing obligations. The fixed boundary probes complement registry-generated
handler probes so deleting a registration cannot silently erase every test of
an accepted boundary. Collector regression tests reject HTML masquerading as a
backend error and identifying/cookie-bearing health responses.

This bounded proof cannot approve a production release even after its routing
matrix passes. Replace fixtures with actual handlers, generate their complete
wire schemas, configure the real preview/production edge, implement required
startup invariants, and rerun the accepted predeployment gate for those artifacts.

The architecture's documented FGA LrC plug-in call uses `LrHttp.get` with an
explicit `Authorization` field. This collector uses a truthful
`FlickrGroupAddr-RouteConformance/0.0.0` User-Agent and synthetic inputs. It does
not impersonate the Lightroom Classic host or prove its default User-Agent,
Windows TLS behavior, or actual LrHttp execution. A real host check remains a
client-compatibility prerequisite for the installation-read slice; no browser
cookie authentication or invented SDK networking contract is inferred here.
