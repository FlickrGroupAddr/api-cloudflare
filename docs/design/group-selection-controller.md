# Disabled group-selection controller and native dialog

Status: implementation candidate for ticket 0024; production qualification is
false. Governing authority is architecture ADR0045 as amended by accepted
ADRs0062/0063 and the accepted plugin-service contract. The owner accepted
preview 0.0.1.12's interaction; this integration reuses it without another UX
approval checkpoint. This candidate adds no menu, metadata-provider registration,
publisher, network origin, deployment gate, or automatic startup.

`GroupSelectionController.new(deps,scope,eligibility,binding,context?)` reads the scoped
choice through `store:readChoice(scope)`. Its model copies the ready
`GroupSelectionEligibility` output into name-first rows with exact IDs, local
selected IDs and read-only presentation rows. Saved IDs that are no longer
eligible remain counted and explicitly listed in an unavailable-choice notice.
Confirmation stays disabled until the photographer explicitly clears these
unavailable local choices in memory. Cancel preserves the stored choice.
Protected rows receive no selection/removal controls. Unavailable projections
cannot become an empty successful read.
`GroupSelectionDialog.show(controller,{photoName,albumName})` presents the
documented native modal and calls `controller:commit()` only on OK. Cancel writes
nothing. The dialog preserves multi-highlight Add/Remove, live literal filtering,
FILTERED and Clear, aligned lists, full highlighted names and IDs, dynamic
count-aware action labels, and empty unpublished Save. Only eligible groups can
enter the editable lists. Deselection changes a local choice only.

The controller requires these injected adapters:

| Adapter | Required behavior |
| --- | --- |
| `store` | `readChoice`, `saveChoice(scope,ids,expectedRevision,handoffId?,binding?)`, `confirm(scope,id,outboxRevision,ack)` from `GroupSelectionStore`. Bound save durably snapshots the entire immutable choice and binding atomically. Confirm persists validated intent identities and consumes only the matching editable revision. |
| `client` | Bundled `clients/lightroom/FGA-LrC15.lrplugin/GroupSubmissionClient.lua`, an exact copy of the retained canonical compatibility source `clients/lightroom/GroupSubmissionClient.lua`. |
| `call` | Documented `LrTasks.pcall` from the owning asynchronous task. Raw Lua 5.1 `pcall` cannot protect yielding SDK network calls. |
| `prove(photoId,linkedRevision)` | Safe hosted existing-public-photo proof; returns a validated binding. It cannot render, upload or add to Flickr groups. |
| `now()` | Monotonic seconds. Existing-public proof starts immediately before proof and must remain younger than 15 seconds after the durable snapshot and before POST. Nonnumeric, nonfinite, backward and expired readings refuse the handoff. |
| `newHandoffId()` | Unique non-secret durable correlation ID, independent of request idempotency. The store rejects reuse. No entropy or authorization claim follows from this ID. |
| `credential()` | Supplies the installation credential at request time; never puts it in model, recovery, return value or dialog. |
| `post`, `encode`, `decode`, `jsonNull` | Qualified fixed-origin, redirect-safe, bounded host transport and strict JSON adapters. `post` returns body and `{status=number}`; JSON null must retain an explicit sentinel shared with the store. |

Unpublished commit saves zero through 60 IDs and performs no request. Bound
commit refreshes existing-public proof, atomically saves and snapshots, then
invokes the existing client once for the complete one-through-60 set. It checks
HTTP 202, bounded body, closed schema, exact binding/photo, ordered exact pairs,
unique intent IDs, closed states and consistent permanent blocks before
acknowledgment. Accepted means durable hosted intents, never Flickr addition.
Unknown, malformed, lost or thrown responses retain the prepared record. Neither
this controller nor dialog automatically replays any operation. An explicit
future reconciliation flow must use the immutable prepared identity and the
backend's idempotent batch semantics; upload/add replay is outside this module.
The store's revision comparison prevents a late response clearing a newer edit.

Read-only current membership and retained-state copy come from eligibility/status
adapters. Group refresh, membership observation and status observation times
remain visible, including positive membership alongside protection copy.
Status traversal, visible-only polling, last-good stale display and
cadence belong to `SubmissionStatusClient`, not this modal's input events.
No status refresh or selection event initiates group work.

Outstanding composition/qualification: selected photo/Album scope resolution,
private metadata registration, documented host-task lifetime/cancellation,
fixed-origin POST redirect and body-limit behavior, actual host durable recovery,
integration of safe proof with current linked identity, and native release
qualification. The accepted fixture interaction does not qualify these adapters.
Offline tests exercise actual Lua 5.1 modules and synthetic boundaries; they do
not establish host transport, storage durability or live provider behavior.

Existing-public-photo selection without a catalog photo uses the separate
`ExistingPhotoGroupStore` candidate described in [the store design](group-selection-store.md).
It scopes catalog-private recovery to installation/binding/photo/link/workflow,
without an LrPhoto, fabricated UUID, Album or published-photo record. Actual-core
composition tests and independent review cover this path. Qualified host-task,
identity/transport and recovery-UI composition remain separate work.

The existing-public-photo composition must pass trusted constructor context
`{workflow="existing_public_photo"}`. Final proof follows this workflow even
when the backend preserves `sourceKind="fga_direct_upload"` on a reused
binding. Binding provenance is never rewritten to select a client workflow.
The original publisher-bound path may use `{workflow="publisher_bound"}`; an
upload-origin binding in that path keeps its existing proof behavior. Unknown
workflow context fails closed.

## Existing-public-photo workflow composition candidate

`ExistingPhotoGroupWorkflow.run(context,deps)` composes the actual browser,
protocol clients, eligibility assembler, binding-only catalog outbox, selection
controller and accepted native dialog. It remains unregistered and declares
`PRODUCTION_QUALIFIED=false`. The caller owns one documented asynchronous SDK
task and function context; this module creates no task or menu entry.

Before any module loading, credential read, request, dialog or write, the
caller must explicitly supply every capability assertion: `hostTask`,
`thumbnailTransport`, `readTransport`, `proofTransport`, `batchTransport`,
`catalogOutbox`, `currentIdentity`, and `credentialBoundary`. These assertions
are composition inputs, not evidence of qualification. Missing adapters or
assertions produce `qualification_required` and no work.

Required host adapters are `call` (LrTasks.pcall), secure `retrieve`, qualified
`httpGet` and proof `httpPost`, bounded relative-path `batchPost`, strict
`decode`/`encode` and shared `jsonNull`, cancellable `sleep`, `cancelled`,
monotonic `now`, unique `newHandoffId`, `currentIdentity`, and `activeCatalog`,
plus the exact `catalog`, `plugin`, and existing `batchClient` module. The
existing batch adapter is injected explicitly from the release bundle. A
byte-equality packaging test guards drift from its retained canonical source. `currentIdentity` returns the authenticated installation ID and current
linked Flickr revision; it is not inferred from photo or catalog metadata.

The existing browser returns only `(binding,membershipObservation)` on success;
it does not return the selected photo title. The composition therefore displays
the exact Flickr photo ID as its context. It identifies the Album as absent and
creates no photo UUID, catalog photo, publish record, or Album entity. It
preserves binding provenance, including `fga_direct_upload`, while explicitly
passing `workflow="existing_public_photo"` to force fresh final public-photo
proof before queue handoff.

One invocation captures installation/link/catalog/credential context and checks
it before and after every transport call. It reuses complete browser membership
results, loads a fresh complete writable-group snapshot and complete verified
history, and opens the selector only after eligibility assembly succeeds. It
uses the separately implemented binding-only store's exact scope and private
catalog outbox. Existing pending handoffs stop the invocation with
`reconciliation_required` and their original non-secret IDs. Reopening never
creates a replacement handoff or automatically replays the batch. Failed reads
return `unavailable`; cancelled dialogs leave the outbox unchanged; a lost batch
response retains the original prepared snapshot and returns `unresolved`.

Synthetic tests execute all actual Lua cores, including the existing browser
and native selection dialog through mocked documented SDK controls. They cover
the preserved upload-origin proof edge, durable snapshot before one POST,
missing capability refusal, stale/incomplete reads, identity changes, cancel,
and unresolved handoff identity across reopen. They do not qualify native HTTP,
thumbnail cache, host lifetime, outbox durability, production registration or
live dispatch.

Workflow identity fencing validates exactly `{installationId,linkedFlickrRevision}`
with an opaque installation ID and positive safe-integer link revision before
credential reads or requests and at every later fence. A post-outbox-gate fence
also checks rotation, credential and cancellation before returning pending IDs;
a yielding catalog gate cannot expose them under changed workflow context.

Release build 0.2.0.7 adds the exact canonical batch-client copy to the bundle.
The actual-core workflow integration test now supplies that bundled module;
explicit transport and qualification adapter injection remains required.
The native ten-of-ten synthetic result remains evidence for the recorded module
hashes with release build 6. Build 7 is offline-verified packaging and is not
qualified as a complete native release by that earlier result.
