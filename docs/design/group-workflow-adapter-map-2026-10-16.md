# Remaining group workflow adapters

Date: 2026-10-16. Ticket #0055. Status: implementation allocation and current-source
contract map, not architecture acceptance, native qualification or release authority.

This map uses release **0.2.0.7**, not the superseded 2026-10-15 inventory. The
supported qualification target is Lightroom Classic **15.6 Release**, build
`202609251514-f839cde9`, Camera Raw 18.7, Adobe SDK **15.3**, build
`202604090947-8f3672ed`. SDK minimum 15.0 in `Info.lua` is a loading declaration,
not evidence of qualification on every minor or any later major.

Authority: architecture repository `AGENTS.md`, `docs/README.md`, accepted
ADRs0045/0062/0063, `docs/plugin-service-contract.md`,
`docs/existing-public-photo-intake.md`, `docs/queue-status-api.md`, and
`docs/moderator-safety-ui-conformance.md`. The [single-turn decomposition](../planning/remaining-work-single-turn-decomposition-2026-10-16.md)
assigns work; it does not amend those contracts. Proposed module names below
are ordinary implementation choices, not new protocol or persistence authorities.

## Current source and owning tickets

All Lua paths in this table are under `clients/lightroom/FGA-LrC15.lrplugin/`.
New names identify bounded destinations; this document creates none of them.

| Remaining component | Current implementation to reuse | Concrete destination and owner |
| --- | --- | --- |
| SDK task, cancellation, identity and store factory | `ExistingPhotoGroupWorkflow.run(context,deps)` validates all injected functions and capability assertions; stores already enforce synchronous private gates and exact readback | New `GroupWorkflowAdapters.lua`: `new(context, options)` supplies the exact workflow dependency object; #0056 owns implementation and fails closed for unqualified seams |
| Shared authenticated READ and proof protocol | `ConnectionCore.verifyStored`; `ExistingPhotoClient.authenticatedRequest`, `discover`, `prove`, `memberships`; `GroupDiscoveryClient.new(Core).discoverStored`; `SubmissionStatusClient.history` | New `AuthenticatedWorkflowTransport.lua`: guarded GET/proof request adapter preserving existing client signatures; #0057 owns shared protocol and fixed-origin READ, consumed by #0023 and #0024 without either full milestone waiting for the other |
| POST measurement | Existing native network fixture measured GET cases only | New separately versioned probe and finite packet under `probes/` and `docs/operations/`; #0058 prepares, #0059 obtains concrete action scope, #0060 measures and cleans up; no release registration |
| Proof and whole-set batch POST | `ExistingPhotoClient.encodeProof`; bundled `GroupSubmissionClient.submit`; `GroupSelectionController.validate202` and `_commit` | Same transport module, separate proof POST and `batchPost(path,bytes,headers)` entry points; #0061 supplies transport only after #0060, #0056 and #0057; retain one call for the complete 1–60 set |
| Visible retained status | `SubmissionStatusClient.history(d,binding,prior)` supplies complete stabilized traversals, closed projection, stale prior result and pacing; no visible poll owner exists | New `SubmissionStatusController.lua` and `SubmissionStatusDialog.lua`; #0062 owns `new(deps,binding)`/visible session lifecycle and read-only view, reusing status validation/presentation |
| Explicit recovery core | Both stores expose `listPending`, `readHandoff`, `confirm`; workflow returns `reconciliation_required` with original IDs before opening a fresh selector | New `GroupHandoffReconciliation.lua`; #0063 owns `list(scope)` and explicit `reconcile(scope,handoffId)` through injected store/proof/batch/status adapters, as bounded below |
| Library exact scope and unpublished Save | `GroupSelectionStore`, `GroupSelectionController` unbound commit and accepted `GroupSelectionDialog` already implement storage/Save/core UX | New `LibraryGroupSelection.lua` plus private `MetadataDefinition.lua`; #0064 under #0024 owns exact photo/service/ordinary-Album resolution and unregistered metadata declaration; no provider callback ownership |
| Publisher frozen selection interface | `GroupSelectionStore.prepare`, `confirm`, immutable record and revision-consumption rules exist | New `FrozenGroupSelection.lua`; #0065 under #0024 exposes `freeze(scope,expectedRevision,handoffId,binding?)`, `read(scope,handoffId)` and `acknowledge(scope,handoffId,outboxRevision,ack)` as thin store delegation; #0097 under #0026 consumes it in original publish-provider callbacks |
| Native invocation and recovery UI | `ExistingPhotoGroupWorkflow` is unregistered; `RunExistingPhotoBrowser` remains disabled by `ExistingPhotoClient.PRODUCTION_QUALIFIED` | New `RunExistingPhotoGroupWorkflow.lua`, `RunLibraryGroupSelection.lua` and `GroupHandoffReconciliationDialog.lua`; #0066 composes disabled adapters/status/recovery without adding release entries |
| Final release registration | `Info.lua` build 7 registers only writable-group browser and connection settings; no metadata provider, existing-photo workflow or publish provider | #0070 prepares reviewed fail-closed `Info.lua` menu/metadata delta after listed dependencies; #0071/#0072 own exact registered group candidate smoke. #0129/#0130 separately own publisher registration/smoke under #0026 |

The canonical compatibility batch client and build-7 bundled copy are already
byte-equal and tested; do not create another implementation. Existing store,
eligibility, dialog and browser compositions are not unfinished replacements.
The controller/design and store/design remain the detailed owners:
[controller](group-selection-controller.md), [stores](group-selection-store.md).

## Identity, task and storage adapters

`currentIdentity()` must return exactly `{installationId,linkedFlickrRevision}`,
with validated opaque installation ID and positive safe-integer link revision.
It is a simple non-yielding read of a verified invocation session. It cannot
query the network from inside a catalog write callback.

#0056/#0057 initialize that session with `ConnectionCore.verifyStored` against
`GET /api/v001/installations/current`, requiring active/current credentials and
the strict current document. `installationRevision` is not a linked Flickr
revision. `ConnectionController` preferences currently retain only installation
identity/revision; a last-verified label or those preferences cannot supply the
missing link identity. Obtain the link revision from a validated authenticated
`ExistingPhotoClient.discover` response (including a valid empty page), then
require the same revision across discovery, selected binding and membership.
No new identity endpoint is needed for this existing-photo path. A publisher
must obtain its link identity through its accepted hosted binding/authorization
context; it cannot substitute a stored photo field for authenticated authority.

Capture the active catalog object, installation/link identity, canonical current
credential and absence of a candidate credential. Fence before and after every
yielding HTTP/catalog boundary, before exposing pending IDs, before dispatch and
before confirmation. A local candidate, credential replacement, catalog change,
link mismatch, cancellation or stale session prevents further dependent work.
Remote revision checks remain backend authority; local fences cannot detect an
external change before another authenticated response. Preserve the existing
workflow's guarded calls rather than weakening them to capability booleans.

Use `LrFunctionContext.postAsyncTaskWithContext` for the invocation that may use
`LrHttp.post`; pass `LrTasks.pcall` for yield-safe protected calls, `LrTasks.sleep`
for yielding waits, and `LrApplication.activeCatalog` for catalog identity.
One context owns dialogs, property observers, cache cleanup and the visible
status/recovery lifetime. Cleanup marks cancellation before releasing resources.
Use a cancelable `LrProgressScope` and poll `isCanceled`, together with modal
close/context cleanup, before and after I/O and inside sliced sleep intervals.
Cancellation is cooperative. It does not prove cancellation of an in-flight
native HTTP call and cannot erase a prepared handoff or prove that POST was unsent.

The store factory passes the same catalog, `_PLUGIN`, `LrTasks.pcall`, active
catalog reader and verified session reader into the current stores. Keep their
`withPrivateWriteAccessDo(...,{timeout=5,asynchronous=false})` and executed/callback/
exact-readback conditions. Never perform HTTP, dialogs or task launch in the
private write callback. #0056 supplies a non-secret durable unique handoff ID
allocator, using catalog-private compare-and-set state; no timestamp or random
string is an authorization token or cryptographic claim. Store uniqueness
checks remain authoritative for collision refusal.

### Clock source and guarantee

The current controller design describes `now()` as monotonic seconds around
proof, durable snapshot and batch handoff. Its executable checks require finite
samples, refuse backward time and refuse observed age at least 15 seconds.
SDK15.3 `LrDate.currentTime` documents Cocoa wall time, not monotonic time.
The inspected SDK module reference exposes no documented monotonic clock.
`os.clock` measures CPU time and is not a substitute for elapsed yielding I/O.
The native GET fixture explicitly describes its wall-clock measurement as
non-monotonic.

The accepted existing-public intake contract requires immediate fresh proof and
backend enforcement of its 15-second age; it does not separately require a
monotonic client clock. Its monotonic Workers membership/preflight language has
a different component and scope. The implementation design's stronger label
does not create an owner decision gate. #0056 can use documented
`LrDate.currentTime` as an observed-time client guard with the existing
finite/backward/expiry refusal, while keeping the backend's current-revision and
database proof-age checks authoritative. #0056 must align the controller design
wording and tests with that limited guarantee before qualification; this map
changes no code or existing design. Do not claim hard elapsed-time enforcement,
replace backward samples with `max(last,wall)`, or introduce a helper to satisfy
an unaccepted implementation preference. An undetected wall adjustment can
defeat the local age estimate; it cannot bypass the backend admission guard.
This routine adapter choice creates no new architecture exception. #0067 still
owes actual host behavior and failure checks for the chosen adapter.

## Immutable recovery request semantics

#0063 reads the original record under its exact scope and fences the current
catalog/installation/link/credential session. It never calls `saveChoice` to
replace an unresolved handoff, infers no successful dispatch from `prepared`,
and performs no request on open. The photographer explicitly requests a bounded
reconciliation attempt. A history view can explain retained states; it cannot
invent a batch acknowledgement, `created` flags or replacement intent IDs.

For an unchanged valid proof revision, a repeat preserves the original batch
body, authenticated owner, binding and entire original ordered group set.
`src/admission.ts` requires the current binding verification revision even when
every requested pair exists. Its proof-age exemption for an all-existing set
does not exempt the revision equality, owner, link or credential guards.

If safe existing-public proof must be refreshed, use the same original Flickr
photo ID and expected link revision. Validate the returned binding against the
original binding ID, photo ID, source and link; retain provenance even for an
upload-origin binding reused by the existing-public workflow. A different
identity refuses recovery. A fresh `verificationRevision` is attempt-local
authorization for a new reverified admission request over the same immutable
natural keys; it is not a byte-identical retry of the old body. This follows the
specific intake contract's explicit proof-then-batch expiry recovery. The
generic exact-body retry rule still applies to a literal repeat.

Keep original `handoffId`, selection revision, scope, group set and snapshotted
binding, including its old verification revision, unchanged in durable storage.
Check the fresh attempt's observed proof interval through the qualified clock seam.
Submit the whole original group set once, with the fresh expected verification
revision only in the wire request. Validate the entire bounded 202 using the
attempt binding and exact original groups; then call store `confirm` using the
original handoff/outbox revision and original snapshotted binding in the local
acknowledgement. The 202 has binding/photo correlation but no proof revision;
the original local record must not be rewritten to pretend it was newly created.
An old successful attempt may consume only its matching current editable
revision; a newer choice survives. All transport/validation/storage ambiguity
retains the original prepared record. No automatic retry loop, subset, upload,
Flickr add/remove or publication-association repair belongs to this operation.

Controlling detail: architecture `existing-public-photo-intake.md`, sections
"Common group-submission batch" and proof expiry/recovery; generic retry rules
in `plugin-service-contract.md`. Current backend evidence is `admission.ts`
binding/VALID guards and `intake_api.ts` rejection and 202 projection. No backend
change or architecture exception is required by this allocation.

## Status, Library and registration checks still owed

#0062 must publish only complete `SubmissionStatusClient.history` results, keep
last good data explicitly stale on failure, coalesce reads per binding, fence
late responses, restart at page one and honor the returned minimum cadence,
Retry-After/backoff and null recommendation. Poll only while visible; close
stops further reads. Status actions never queue, resubmit or change a gate.

#0064 validates exactly one selected photo, an ordinary FGA Album, owning
service/plugin identity, catalog/photo membership and persistent UUID using the
SDK selection/collection APIs before constructing the store scope. Ambiguous
sources, smart collections and foreign providers fail closed. The private
untitled `groupAdditionSelections` string definition follows ADR0045. Empty
unpublished Save remains valid; bound Queue remains 1–60. #0065 owns frozen
revision exposure/consumption; #0026's #0097/#0119 consume it in per-rendition
provider callbacks without selectors or serial dialogs. Do not register a
provider to make the Library metadata editor available.

Remaining integration evidence is finite: actual SDK task/context and cooperative
cancel behavior; session/rotation/catalog fences; synchronous store wiring and
pending discovery; complete READ/thumbnail effective-edge gates; independently
characterized proof/batch POST redirect/body/header/error behavior; visible
status stale/cadence lifecycle; explicit original-handoff recovery with fresh
proof and late acknowledgement; Library exact scope and frozen revision use;
then reviewed fail-closed registrations and exact artifact native smoke.
#0067–#0072 own the integrated group packet/run/registration gates. The completed
GET eight cases plus two receiver reports do not characterize POST. #0027's
accepted interaction and #0029's exact bounded restart/outbox evidence are reused
within their original scope; neither full owner cycle is repeated. Original
#0023/#0024 remain final evidence audits, not replacement implementation cycles.

## Inspection provenance and validation

Current-source inspection included `Info.lua`, `ConnectionController.lua`,
`ConnectionCore.lua`, `ExistingPhotoGroupWorkflow.lua`, `ExistingPhotoClient.lua`,
`ExistingPhotoBrowser.lua`, both stores, `GroupSelectionController.lua`, bundled
`GroupSubmissionClient.lua`, `SubmissionStatusClient.lua`, `src/installations.ts`,
`src/existing_photo_discovery.ts`, `src/admission.ts` and `src/intake_api.ts`.
The current [development handoff](../operations/lrc15-development-handoff-2026-10-16.md)
and [independent composition review](../evidence/existing-photo-group-workflow-review-2026-10-16.md)
establish the build-7 packaging versus build-6 native evidence distinction.

Local licensed primary references were inspected in architecture repository
`vendor/LrC SDK/15.3/API Reference/modules/`: `LrHttp.html` (GET/POST signatures,
POST-specific context, headers.status and error returns), `LrFunctionContext.html`
(task/context lifetime and cleanup), `LrCatalog.html` (selection/private gate),
`LrProgressScope.html` (cooperative cancellation) and `LrDate.html` (wall time).
Library scope methods are cross-referenced by architecture
`docs/research/lightroom-classic.md` and accepted ADR0045. SDK source/text is not
redistributed. This pass performed source/reference review only; no native,
cloud, live-account, catalog write, release registration or capability enablement
was performed. Independent review and integration verification belong to the
primary's #0055 handoff; this document does not self-certify those gates.
