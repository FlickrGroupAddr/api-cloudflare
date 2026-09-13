# Plugin Code lifecycle and transfer integration

Date: 2026-09-13

Status: Local implementation and UI checks passed. Full production release
conformance remains in progress; no real Flickr group writes are enabled.

Terry accepted ADR 0049 and directed continuation to the handoff gates. The
canonical acceptance, lifecycle/transfer/allowlist updates, closed wire projection
and structural tests are pushed as architecture-design `fb91f42`. This resolves
the rotation decision in the preceding dispatcher checkpoint.

The actual Worker now exposes the six browser-authenticated Plugin Code
collection/member/candidate operations. Issuance creates exactly 32 random
octets and encodes ADR 0044's canonical 64-character value. Only its complete
SHA2-256 digest is stored. Metadata and replay responses never reveal plaintext.
Creation, completion, cancellation, expiry and revocation use D1 transactions
with current session/recent-authentication checks, strong parent validators,
version/pointer constraints and retained lifecycle/audit evidence. Concurrent
candidate creation has one winner; an exact completion replay is a no-op only
while its recorded resulting revision and state remain current. Revocation
invalidates both current and pending credentials and retains group work/blocks.

The list is bounded and uses an owner/page-size-bound opaque HMAC continuation
with a separate purpose prefix on the existing native limiter key. It creates
no cursor rows. A successful list/detail audit commits before metadata release;
failed attributable requests append sanitized failure evidence when possible.
The maintenance path expires up to 50 candidates using the database clock.

The Plugin Codes panel stays at the accepted `/admin/` URL. It uses the existing
recent-authenticated session, six explicit transfer confirmations, a one-time
copy, a five-minute erasure deadline and manual clipboard cleanup. Explicit
Erase overwrites the clipboard with a fixed non-secret sentence; refusal leaves
manual cleanup instructions and never reads the clipboard. Navigation, hidden
page state and late-response fencing prevent redisplay. Reload exposes metadata
only. The panel refuses creation in a document that already loaded Google
scripts and disables unrelated actions while plaintext is visible. No secret is
stored in browser storage, a URL, a file, logs or HTML source.

Validation: 91 Node tests, 95 Python tests, native TypeScript, Ruff, Pyright and
generated API checks passed. A compiled optimized production Worker test used
real local D1 and native bindings, verified synthetic Google signatures, and
exercised concurrent rotation and invalidation. It made no Flickr request.
File-backed route tests cover expiry without weakening immutable expiry guards,
audit rollback, scoping, stale validators, malformed requests and bound pages.
Browser review used clearly labeled simulated data and confirmed disabled
unrelated actions, one-time display and no redisplay after reload. The agent
did not read or write the user's clipboard; cleanup behavior used an injected
unit-test clipboard. Local runtime fixtures were disposed.

Migration `0010_plugin_code_lifecycle.sql` adds retained credential lifecycle
metadata. The current-schema archive derives 33 tables automatically and its
existing regression checks pass. These results are local evidence, not a hosted
current-schema restore or the complete fail-polite release gate. Remaining
status/bypass, process/deployment restart, hosted restore/reconciliation and
release-pipeline work stays on implementation ticket #0018. The separate
DNS/account handoff on #0016 remains a production prerequisite.

The later [status and deployment handoff](2026-09-13-status-and-handoff-gates.md)
records the current implementation, verification and remaining owner input.
