# Native administration and batch integration

This supersedes the implementation status in the earlier 2026-09-12 checkpoint. Terry accepted ADRs 0048 and 0057 and selected the sixbucks Cloudflare account. The implementation is ready for review; production hostname activation still requires the DNS-zone move. This is not the separate #0018 production release/conformance pass.

## Implemented

The real Worker now routes Google GIS login, opaque browser sessions, recent reauthentication, logout, session inventory/revocation, Flickr connection reads, JSON OAuth start, callback, disconnection and separate verified gate resumes. Hono routes the requests; React Router supplies session storage mechanics with an application D1 adapter; Google Auth Library validates Google signatures and claims; JOSE parses bounded protected headers; csrf-sync supplies synchronizer-token mechanics with an additional constant-time comparison. The cookie remains the accepted opaque 256-bit identifier, whose SHA-256 digest selects a D1 row. React Router's unsigned-cookie warning is expected for this accepted server-side opaque design; cookie claims are never authorization.

Login consumption, session creation/rotation, principal revision and mandatory success audit share a D1 batch. Current owner policy is checked on protected requests. Exact Origin, CSRF and recent-authentication checks protect sensitive mutations. Logout commits before cookie expiration and converges for absent, malformed, expired and revoked cookies; failures preserve the cookie. Session inventory is scoped, paginated and guarded against revision/count races.

The shared D1 limiter normalizes IPv6 to /64 and stores HMAC source keys only. Source/global budgets include potentially invalid in-flight work. Login starts have a separate bounded start budget so creating a nonce does not spend a Google-login POST token. Google key refresh uses shared ownership, published freshness, bounded/coalesced refresh and failure cooldown.

Native lifecycle ownership is durable in D1. Replacement pauses authority before the one guarded provider mutation. Callback candidates must pass a real signed Flickr owner/permission check. Activation and audit commit together only for the matching generation and current operation. Unknown writes are not repeated. Definitive current-grant rejection stops authority and schedules correlated retirement; stale rejection cannot disable a successor. Successful replacement never resumes either write gate.

Five fixed temporary native slots hold OAuth request-token pairs outside SQL. Their canonical D1 transactions count toward the five-live cap before request-token work. Startup observes the exact schema, generation, transaction ID, token and secret before returning the authorization target. Native propagation required a bounded read-only wait; the provider write and token exchange remain single-attempt operations. Callback exchange is single use, and temporary-slot retirement stays owned until its matching marker is observed.

The authenticated photo-binding and schemaVersion 2 batch API use the actual installation-credential boundary, closed generated contracts, stable photo identity, bounded fresh verification, one atomic selection and zero-or-one post-commit native hint. The Lua 5.1 adapter submits the complete ordered selection in one HTTP call without slicing. No admission request performs a Flickr group write.

The real UI assets are under `assets/admin/`. They provide connection state, explicit owner confirmation, separate gate resumes, reauthentication, truthful logout handling and session management. A separately labeled local review server uses only simulated API data. Browser review verified the page layout, session inventory and typed-owner disconnect transition, including disabled write controls after retirement.

## Validation

- All **31 combined hosted checks passed**, including all **18 CBA IDs**, the actual Lua client against the hosted API, native binding reads, the limited runtime writer, real D1/DO behavior, maintained-library verification of synthetic signed Google assertions, native OAuth staging/activation/retirement and logout.
- The complete Node regression run passed **60 tests**, including compiled local workerd/D1 tests and strict credential, session, rollback and stale-result cases.
- The Python regression suite passed **85 tests**, including actual Lua 5.1 execution.
- Native TypeScript, Ruff, Pyright and executable-registry/generated-contract checks passed. A clean `npm ci` succeeded; the four previously known development-toolchain advisories remain.
- The CBA mutation runner uses isolated source copies and checks all nine required fault classes. All nine mutations were detected, the baseline passed, and the working sources were unchanged. See [mutation evidence](../evidence/cba-mutations-2026-09-12.json).
- Every disposable Worker, D1 database, Durable Object namespace, native secret and run-owned store was removed and absence confirmed. The persistent user-supplied writer token was not revoked.

[Hosted evidence](../evidence/native-admin-intake-2026-09-12.json) includes the failed attempts and their cleanup. The failures were not relabeled as passes: they exposed the initial test user-agent rejection, a wrong synthetic peer in the proof sweep, and real native propagation delay. The final implementation retains exact credential binding throughout.

## Deployment and remaining work

The production template is `wrangler.example.jsonc`. Its feature flags remain disabled. It describes the nine native bindings, D1 migrations, private custom hostname and maintenance schedule. The actual COORD namespace must come from the partition-worker deployment; no fixture class belongs in production. Full dispatcher, current-schema restore and release evidence remain under #0018. The historical coordination archive covers its older scoped tables and must not be presented as a complete backup of the new authentication/lifecycle schema.

The `fga-sixbucks` Wrangler profile is bound only to this implementation repo; the default login is preserved. Google owner configuration and supplied credential-file locations are in ignored local configuration. Actual credentials, Google subject, provider resource IDs and local credential contents are excluded from this document and the published evidence.

Production is blocked on moving the `flickrgroupaddr.com` DNS zone from the old Cloudflare account to the selected business account. Its registrar is Amazon Registrar. Current Wrangler zone permissions can identify the zone but cannot export DNS records (HTTP 403), so source records and DNSSEC settings still require owner access. No old DNS record, nameserver or zone was changed. See the [domain handoff](../operations/fga-domain-account-move.md). After the move, provision the persistent deployment and complete a real browser Google/Flickr consent smoke check before enabling the relevant feature flags. A live Flickr group-write smoke test is not implied by this integration.

## Reproduction

Run `npm ci`, `npm run check`, `node --test tests/*.test.mjs probes/foundation/*.test.mjs`, `npm run api:check-generated`, `uv run --frozen python -m unittest discover -s tests`, `uv run --frozen ruff check .`, and `uv run --frozen pyright`.

Run `npm run cba:mutations` for isolated mutation checks. `uv run --frozen python scripts/intake_hosted.py run` creates and removes a guarded disposable hosted fixture using the approved account inputs; `--admin-only` isolates the administrative path. The fixture is bounded by a random outer credential, expiry and request budget and has no real Flickr transport. Preserve its private run directory on failure for cleanup/evidence.

Run `node scripts/serve_admin_review.mjs` for the simulated UI; its loopback URL is written to `.coordination-runs/admin-ui-review.json`. The Google owner setup and Cloudflare login bridge are operator helpers, not production authentication endpoints. The bridge preserves official Wrangler state/PKCE verification, rejects stale callbacks without stopping the current listener, and starts Wrangler's two-minute timeout only on an explicit browser click.
