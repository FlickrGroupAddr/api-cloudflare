# FGA-LrC15 new-photo publisher workplan

Date: 2026-10-15

Status: Implementation-readiness assessment and recommended bounded work;
not architecture acceptance, UI approval, deployment qualification, or upload
authorization. Architecture authority remains `C:\Projects\FGA\architecture-design`.

## Current task allocation

The 2026-10-16 [single-turn scheduling map](remaining-work-single-turn-decomposition-2026-10-16.md)
and live board supersede this earlier broad work allocation. Original #0026 is
now a final evidence-only audit. Completed #0028/#0029/#0034 remain reusable only
within their recorded scopes; their integration and new production guarantees
are explicit new tasks. Accepted contracts and owner decisions still control.

## Readiness conclusion

The publisher milestone contains independent engineering work that can be
scoped before the group-selection mockup review. Keep the milestone dependent
on that review and the integrated existing-photo selection/submission/status
workflow. Promote bounded child scopes based on a clear completion boundary,
even when their execution depends on another child. Do not promote the whole
milestone as one implementation task.

Rendering/preflight, upload authorization, and normal uploaded-photo proof do
not depend on the selector's appearance. Their accepted semantics permit
isolated implementation and synthetic tests. Production provider wiring,
selection consumption, recovery UI, and complete publish qualification have
additional dependencies. A subsequent bounded P26-A implementation adds an
unregistered preflight policy/SDK adapter and synthetic Lua 5.1 tests; see
`clients/lightroom/publisher/README.md`. It does not implement the publisher,
authorize an upload, or resolve the recovery/album dependencies below.

## Authority and inspected evidence

Read the architecture repository's `AGENTS.md` and `docs/README.md` first.
Accepted ADRs and scoped contracts control; research, diagnostics, derived
OpenAPI and board scheduling do not grant new behavior. Relevant sources:

- `docs/zero-state-publish-flow.md`, accepted Phases 4–8; apply the narrower
  current binding and album contracts where old step text still describes
  photo proof as a Phase 6 side effect.
- `docs/plugin-service-contract.md` sections 4–6; ADRs 0001, 0005, 0009,
  0010, 0011, 0012, 0022 and 0045.
- `docs/album-scoped-publish-contract.md`,
  `docs/album-write-reconciliation.md`, and
  `docs/album-lifecycle-contract.md`.
- `docs/research/upload-signing-boundary.md`,
  `docs/project-log/2026-08-20-lightroom-diagnostic.md`,
  `docs/research/catalog-only-existing-photo-association-spike.md`,
  `lightroom/FGA Diagnostics.lrdevplugin/DirectUploadProbe.lua`,
  `PngMatrix.lua`, and `CatalogAssociationPublishServiceProvider.lua`.
- `vendor/LrC SDK/README.md`: locally documented SDK 15.3 provenance,
  build `202604090947-8f3672ed`. Terry independently reconfirmed on
  2026-10-15, with an Adobe Developer Console screenshot, that SDK 15.3
  (April 2026) remains the latest available SDK. Terry's installed-host
  screenshot on the same date identifies Lightroom Classic 15.6, Camera Raw
  18.7, build `202609251514-f839cde9`. Qualify against that current host using
  documented SDK 15.3 interfaces; the FGA-LrC15 major-version identity remains
  appropriate. The parent integration updates the SDK provenance README.

Read-only implementation inspection on this date found:

- `clients/lightroom/FGA-LrC15.lrplugin/Info.lua` registers the information
  provider only. The installed source is a read-only connection client,
  not a production publish provider.
- `src/registry.ts` registers existing-public-photo binding and batch handoff,
  but no upload-authorization, upload-origin binding, ambiguity candidate, or
  ambiguity-resolution operation. A binding response enum mentioning upload
  provenance is not evidence that those handlers exist.
- Migrations contain common photo bindings/events but no upload-authorization
  or album-binding/obligation implementation. Reuse common identity carefully;
  do not infer an upload association from an existing-public binding.
- `tests/test_connection_client.py` already runs original Lua code in actual
  Lua 5.1 through `lupa.lua51`; bounded publisher logic can use that existing
  testing convention with injected host/network/storage adapters.

The previous direct-upload probe demonstrated full-resolution PNG rendering
and `LrHttp.postMultipart` with an independently signed envelope. It was a
diagnostic using a loopback signer and explicit test confirmation, not the
production route, outbox, publish callback, or crash-recovery implementation.
Its envelope uses diagnostic field names; production code must follow the
current scoped contract. Its simple response parser/error handling must not
be copied as a complete ambiguity classifier.

The catalog-only spike proved a reversible provider-scoped existing-photo
association and normal-restart persistence in a disposable catalog. Its default
collection and blocked-render provider deliberately differ from the accepted
ordinary-Album publisher. ADR 0038 keeps existing-photo intake queue-only;
this evidence does not authorize adopting Adobe Flickr publish records.

## Recommended child cards

### P26-A — Completed-rendition preflight and per-photo isolation

**Scope:** Original pure policy plus documented SDK adapter for completed
renditions. Receive the configured format/byte limit and an already captured
immutable per-photo context. Check completed-file existence, readability,
nonzero exact byte length and size policy. Default render settings to
full-resolution 8-bit sRGB PNG; retain separately selected supported settings.
Keep production registration outside this card.

**Acceptance:** Synthetic host/file adapters prove failed render, missing,
unreadable, zero-byte and oversized files request no upload authorization and
send no Flickr request. Test `limit - 1`, `limit`, and `limit + 1`; equality
passes. The oversized result includes measured size/limit and states nothing
was uploaded. There is no automatic resize/JPEG fallback. One failed photo
does not stop a healthy photo or silently discard it. Document actual SDK
render/file APIs and run the established Lua checks.

**Readiness/dependencies:** Ready to implement independently of selection
mockup review with injected context and limit. Full provider use requires
P26-C's durable pre-render snapshot. Verify the current supported SDK and
configuration source for the byte limit before host integration; do not
invent a numerical Flickr limit from historical probe sizes.

### P26-B — Hosted direct-upload authorization

**Scope:** Register the accepted authorization operation, closed request and
response schemas, authentication/gates, metadata validation, current credential
generation handling, mature OAuth signing and durable authorization association.
The backend receives metadata only. Store installation/user/issue time and
nullable photo association, without storing the signed envelope or photo metadata.

**Acceptance:** Tests reject unknown/client authority fields and invalid
metadata combinations; paused applicable write gates issue no envelope. Persist
authorization before returning it. Return only the fixed Flickr upload URL and
exact signed metadata; prove signature/metadata agreement with a deterministic
synthetic signer/transport. Apply no-store and sanitized errors/logging; no secret
or bearer envelope reaches durable storage. No real image upload is needed.

**Readiness/dependencies:** Bounded implementation can start before selection
review. Verify the selected runtime's mature OAuth dependency and secret-generation
boundary; the earlier Python signing proof does not prove a Workers library.
Hosted deployment/credential tests are separate qualification. Never promise
single-use enforcement or a shorter Flickr-enforced expiry.

The bounded P26-B candidate is now implemented behind the disabled `FGA_UPLOAD_AUTHORIZATION_ENABLED` flag, with migration0015 and executable registry schemas. See the [implementation handoff](../operations/lrc15-parallel-handoff-2026-10-15.md) and independent upload authorization review for local evidence. It has not been deployed or qualified against hosted secrets, and does not implement the following upload/recovery/provider stages.

### P26-C — Durable local upload attempt and direct-upload recovery boundary

**Scope:** First settle and prove the local recovery-store mechanism, then
implement the per-photo state machine and one direct multipart invocation.
Persist photo UUID, target Album, immutable group snapshot and later server
authorization ID before dispatch. Persist a dispatch boundary so restart after
invocation without a durable result remains unknown. Keep the envelope in
memory only. Persist a definitive returned photo ID before normal catalog write.

**Acceptance:** Fault injection before/after every durable write and multipart
invocation proves no automatic image replay. Pre-invocation failure can use a
fresh authorization. Timeout, disconnect, malformed/incomplete result or crash
after invocation without durable result becomes `upload_outcome_unknown`.
Unknown outcomes produce no catalog remote ID, album work or group handoff.
Resume/restart retains each photo independently. Lost hosted acknowledgement
retries only that hosted operation. Test secrecy with synthetic sentinel values.

**Readiness/dependencies:** A bounded storage/SDK proof can start now; production
storage implementation needs its documented durability, write-failure, concurrent
callback and catalog-copy semantics resolved. The accepted zero-state contract
explicitly leaves the storage mechanism deferred. ADR 0045's private selection
metadata field does not by itself settle a crash-safe upload outbox. Direct
network integration depends on A/B and that proof. Selector-specific snapshot
consumption and recovery UI remain behind the selection review.

**Recovery follow-on:** Implement same-tuple ambiguity resolution from ADR 0012;
show advisory candidates and require per-photo selection confirmation. Preserve
`Leave unresolved`; warn and retain the old terminal record before a deliberate
new-copy attempt with fresh authorization. Candidate pagination/envelope closure
is a separate architecture dependency, not permission to invent field names.

### P26-D — Hosted photo proof, album binding and accountable obligations

**Scope:** Split execution into D1 (upload-origin proof) and D2 (album integration).
D1 implements the accepted idempotent upload-authorization photo-binding PUT
and resolution PUT with installation ownership, exact-photo/current linked-owner
proof and immutable correlation/provenance. D2 records one album binding per
stable local key and one obligation per album/photo binding, then implements
guarded materialization and attachment reconciliation.

**Acceptance:** D1 proves first commit/repeat/conflict outcomes (201/200/409),
fresh complete `photos.getInfo`, owner/revision fencing and transaction rollback.
A zero-group photo obtains the same proof without an empty batch. D2 proves
first database-committed candidate wins, no candidate for an unknown upload,
immutable photoset ID, idempotent obligations, and derived hosted authority
fields. A successful create still requires membership verification. Ambiguous
create is never replayed; attachment uses the accepted fresh read/add/read path.
Catalog-sync failure retries only catalog writes and shows attachment pending
or repair status truthfully.

**Readiness/dependencies:** D1 is independently implementable before selection
review after its upload-authorization persistence dependency. D2 semantics are
accepted but exact hosted binding/status/repair wire is absent from the scoped
album contracts; close that contract before client endpoints or schemas are
invented. Worker/storage tests may be designed from existing accepted state
requirements meanwhile. Keep D2 as explicit child dependencies rather than
hiding a complete album subsystem inside a photo-proof change.

### P26-E — Original publish provider and catalog lifecycle integration

**Scope:** Register the original provider, ordinary Album creation/settings,
documented rendering callback and catalog identity writes. Use the server-issued
publish-service identity and documented local collection ID. Reject any host
default before rendering/upload; expose no smart albums or general remote-album
picker. Integrate A–D and local-only removal/rename lifecycle rules.

**Acceptance:** Disposable-catalog host evidence verifies native publish and
restart behavior, normal upload-result remote ID versus hosted proof pending,
reconciled binding acknowledgement before catalog write, and local-write-only
repair. Test matching/orphaned/conflicting collection remote IDs. Existing
published photos cannot be re-uploaded as a generic handoff recovery action.
Deletion/removal callbacks never become implicit destructive Flickr authority.
Do not copy Adobe sample implementation into public original source.

**Readiness/dependencies:** Provider shell/local Album lifecycle can be bounded
separately, but complete publishing is blocked by A–D, approved unpublished-photo
selection integration, and documented post-callback catalog repair APIs. Do not
assume `recordPublishedPhotoId` remains callable outside its rendition callback;
prove the documented alternate lifecycle or close the repair design explicitly.

### P26-F — Group handoff, truthful status and complete qualification

**Scope:** Reuse the reviewed selector and integrated group/status client.
Consume an immutable snapshot for each new photo; after hosted photo proof
and applicable catalog prerequisites, submit nonempty groups through the sole
batch operation. Track upload, proof, catalog sync, album obligation and group
handoff as distinct accountable outcomes. A pending album operation is not an
invented global ordering barrier; follow the accepted individual prerequisites.

**Acceptance:** Zero groups create no batch/intents. Nonempty retry uses the
same photo binding and selection without rendering/uploading again. Test mixed
success/unknown/failure across multiple photos and restart while hosted binding,
album or batch acknowledgement is missing. UI distinguishes verified photo,
album attachment pending/repair, accepted intents, actual group results and
permanent blocks. Neither native published state nor upload HTTP success claims
complete publication. Qualify actual current Lightroom Classic host behavior
and retain sanitized exact-artifact evidence.

**Readiness/dependencies:** Well-scoped dependent card; execution/integration
requires selection mockup review and existing-photo submission/status workflow,
plus A–E. Controlled production upload is a separate explicit consent gate.
The first controlled existing-photo group addition is a related activation
milestone, not a substitute for new-photo upload authorization.

## Contract gaps and implementation cautions

1. Architecture `openapi/openapi.json` explicitly marks ambiguity-candidate
   pagination/envelope `not_closed`; normal upload authorization and binding
   operations are projected as closed. Close only the missing candidate wire;
   do not label all upload wire as unspecified.
2. Album contracts settle behavior but provide no concrete hosted album routes
   or closed request/response schemas. They remain a client integration blocker.
3. The local immutable outbox's storage/commit/restart/concurrency behavior is
   deferred. Selection JSON is not automatically a recovery journal. Persisted
   pre-dispatch uncertainty must cover the crash after upload acceptance but
   before the photo ID is stored.
4. Normal upload and reconciled upload deliberately order catalog/proof writes
   differently under ADRs 0011/0012. Preserve both paths. Research summaries
   and older Phase 8 text must not reverse the accepted scoped contract.
5. Architecture OpenAPI's UploadAuthorization response description says
   "one-use" although ADR 0005 and signing evidence explicitly disprove enforced
   single use. Treat that as derived wording drift to correct, not a security
   property an implementation can promise.
6. No documented SDK secure-random/general UUID generator exists in the reviewed
   evidence. Never add `LrUUID`, Lua random, clocks or machine/catalog IDs as
   authentication entropy. Hosted components generate security-sensitive values;
   catalog UUID/local IDs are non-secret correlation only.

## Gates retained throughout the split

Selection-review approval remains required for the production unpublished-photo
selector and its consumption. Independent backend/pure policy work does not
accept a new interaction. No Adobe Flickr provider interception or unsupported
Publish Services panel/context-menu injection is allowed.

Use synthetic adapters and disposable catalogs first. No production catalog
mutation, Flickr upload, album write, group addition, deployment or credential
operation occurred for this assessment. A controlled production upload requires
its own explicit authorization for the exact bounded operation. Test fixtures
remain private wherever possible; a public-only test requires immediate explicit
approval after explaining follower/feed exposure, interval and cleanup. Never
commit private images/catalog metadata or OAuth envelopes. The prior successful
diagnostics do not waive these gates.
