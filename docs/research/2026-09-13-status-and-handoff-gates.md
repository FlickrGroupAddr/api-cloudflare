# Status integration and deployment handoff

Date: 2026-09-13

Status: Local integration and bounded regression checks passed. The initial
persistent deployment is running in administration-only mode. Production
conformance and owner browser validation remain incomplete; real Flickr writes
stay disabled.

## Completed continuation

Terry accepted ADR 0049. The canonical acceptance and closed Plugin Code HTTP
projection are pushed as architecture-design `fb91f42`; the implemented
credential lifecycle and one-time transfer UI are in api-cloudflare `3d35317`.
See the [rotation checkpoint](2026-09-13-plugin-code-rotation-integration.md).
No further rotation-route approval is pending.

The FGA API backend now exposes the accepted installation- and browser-session-
authenticated submission-status collection/item routes. A single SQLite read
statement obtains database observation time, scoped counts, gate projections
and bounded page rows. The page joins permanent blocks by exact server-owned
photo/group identity. Unknown outcomes, contradictory states/blocks and invalid
continuations fail the whole response. There is no Flickr/identity-provider
call, worker wake, intent mutation or bypass action on a status read.

The status limiter uses a per-installation or independent per-session bucket,
a 20-request burst with 120-per-ten-minute refill, and the 600-read deployment
sliding window. Its bookkeeping is separate from domain state. Status cleanup
failure cannot starve the durable scheduler. Exact paired keyset continuation
retains microseconds and owner/binding scope. The current implementation uses
nullable advisory group names rather than inventing names from IDs.

The read-only history panel uses protection-first copy, bounded pages and the
server's minimum polling interval. State, FIFO-ahead count, due time and holds
determine queue wording; a polling interval never becomes an ETA. A failed read
keeps prior data labeled stale, while session loss clears protected UI data.
There is no retry, reopen, force, clear-block or cancellation control. Browser
review used explicitly simulated data and confirmed moderation protection copy
and the available read-only controls.

A protocol or unknown-code deployment pause now also requires a different
artifact with retained conformance evidence before a fresh token check and the
usual gate compare-and-set. The runtime and release verifier share the reviewed
contract identity. No HTTP route can insert that evidence. Production receipt
publication still belongs to the unfinished full release pipeline; no production
receipt was inserted here. Existing initial/user gate verification remains
independent of this protocol-repair requirement.

## Validation and scope

The final local suite passed **102 Node tests** and **95 Python tests**. Native
TypeScript, Ruff, Pyright, generated API checks and the canonical architecture
checks passed. Native D1 tests cover concurrent rotation, both status credential
families, real dispatcher outcomes and no extra provider calls. The compiled
bounded crash matrix passed **84 checks**. All six existing crash mutations and
the deferred-preparation mutation were detected with passing controls and
unchanged working sources. Local runtime fixtures were disposed.

Migration `0012_protocol_repair_evidence.sql` is the current head; the exact
archive covers **36 tables**. The identifier guard now safely permits digits
in fingerprint column names, and nonempty receipt rows round-trip with guards.
These checks do not establish hosted D1 restore/reconciliation, independently
killed production processes, every required bypass, or the complete 56-case /
28-mutation release run. The existing `release:verify` command still refuses
missing production evidence. It remains an evidence verifier, not a substitute
for the unfinished full runner and CI promotion wiring. See the
[sanitized evidence](../evidence/status-and-rotation-integration-2026-09-13.json).

## Stop point for the night - 2026-09-13

Terry directed a stop for the night and a later continuation. No further
implementation, credential change, or deployment is running for this handoff.

The DNS move and Cloudflare access work are complete. The destination zone is
active, the native read token is verified, the apex is connected to `fga-api`,
and its TLS certificate is active. The persistent `fga-production` D1 schema
matches migration head `0012_protocol_repair_evidence.sql`. The initial 37-table
archive (36 domain tables plus D1 migration history) round-tripped through a
separate local SQLite database; this is not hosted restore/reconciliation proof.

The Google button styles, embedded-frame origin rejection and injected analytics
are fixed. The public query-free login page uses an origin-only referrer;
protected pages, callbacks and APIs retain no-referrer. Administrative HTML uses
no-store and no-transform. Fresh live-browser loads had no console errors or
warnings, and clicking the framed control reached Google's sign-in page. The
owner's Google Console origin and redirect values were correct throughout.
Latest implementation commit before this stop note: `844857b`; corresponding
canonical clarification: architecture-design `cb311b5`.
See the [verified login repair](2026-09-13-google-login-origin-fix.md).

### First work when resumed

Resolve the Google owner identity, not another DNS or Cloudflare-login issue.
The owner's personal-account callback reached the FGA API backend and returned
`401 unauthorized`. Terry also reported that the business-account attempt did
not work. The deployed `GOOGLE_OWNER_SUB` was confirmed to match the saved setup
configuration, but its mapping to the desired personal account has not been
established. The application distinguishes owner rejection from an invalid
Google assertion; investigate that exact callback/allowlist boundary before
asking for another attempt.

Terry explicitly chose his personal Gmail account as the sole administrator.
The exact requested email is stored privately as `requestedGoogleOwnerEmail`
with `googleOwnerChangePending: true` in
`.coordination-runs/fga-runtime-inputs.json` and on the private work card.
It is independent of the sixbucks Cloudflare account. Do not repeat the earlier
suggestion to use the business Google account. No allowlist value was changed
before the stop.

Compare the original owner setup value with the configured value, obtain the
correct Google-verified subject for the requested personal account if needed,
and update only that sole-owner binding under Terry's explicit direction.
Preserve signed assertion, audience, issuer, nonce and CSRF checks; do not guess
a subject ID or admit additional accounts to bypass the error. Avoid collecting
or printing raw Google assertions. Once the owner can sign in, complete the
Flickr connection/browser checks and continue the remaining release work.

### Deployment left in place

Only administration is enabled: `FGA_ADMIN_ENABLED=1`; read, intake and dispatch
flags are all `0`. No live Flickr group adds are enabled. The current optimized
artifact is `126759eb8d2df2a9af5b58347d5571f0a14b2acfa90124ca4f387025cfeea6c1`.
Private current configuration, artifact and verification are under
`.coordination-runs/production/`; the latest summary is `current-deployment.json`.
Do not run the initial bootstrap again as an ordinary deployment updater.

Full 56-case/28-mutation production conformance, hosted restore/reconciliation,
process-stop and promotion work remain incomplete. The initial deployment and
login rendering checks do not establish those gates. Registrar-transfer work
remains separate. The owner has not requested an overnight automation.
