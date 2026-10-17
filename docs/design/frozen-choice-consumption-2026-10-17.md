# Frozen group choices for publisher composition

Date: 2026-10-17. Disabled implementation candidate for #0065; no release or
provider registration. This note describes the callable adapter for #0026/#0097,
not an architecture amendment or native qualification.

The controlling accepted architecture is
[ADR0045](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/decisions/0045-use-a-library-modal-and-photo-metadata-for-group-selection.md),
as amended by
[ADR0063](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/decisions/0063-use-empty-selection-for-no-group-additions.md),
and [ADR0010](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/decisions/0010-zero-group-publication.md).
The existing [selection store contract](group-selection-store.md) owns durable
schema, bounds, corruption handling and revision compare-and-set.

## Callable interface

Require `FrozenChoiceConsumptionAdapter` from `FGA-LrC15.lrplugin`.
`Adapter.new(deps, exportContext, rendition.photo)` returns `session`, or
`nil, "scope_invalid"`. Supply the owning SDK task's `LrTasks.pcall` as
`deps.call`, the plug-in identity as `deps.plugin`, `deps.activeCatalog`, and
optional `deps.cancelled`. No HTTP, credential, render or upload adapter is used.

The exact `exportContext.publishService` and `publishedCollection` objects must
identify the FGA LrC plug-in's ordinary non-smart Album, with
`publishedCollectionInfo.isDefaultCollection == false`. The rendition photo must
belong to that Album and the current catalog. The durable scope is exactly the
positive safe-integer service and collection local IDs plus the persistent photo
UUID. Selection UI and names play no role. The module rechecks object identity,
IDs, UUID, membership, catalog and cancellation at storage boundaries.

| Call | Result and responsibility |
| --- | --- |
| `session:freeze(handoffId)` | Before rendering, reads the current choice and uses actual `GroupSelectionStore.prepare` to durably freeze its exact revision/groups. Returns `{state="frozen", snapshot=token, choice=view}` only after confirmed readback. |
| `session:inspect(token)` | Returns a fresh detached `choice` view; it cannot alter the private snapshot. An unknown token fails with `snapshot_invalid`. |
| `session:bindGroups(token, binding)` | For nonempty choices, captures the owning publisher's already validated direct-upload binding once, after publication and before dispatch. The exact five fields are `fgaPhotoBindingId`, `flickrPhotoId`, `verificationRevision`, `linkedFlickrRevision`, `sourceKind="fga_direct_upload"`. Both revisions are positive safe integers. It returns `bound`; a second bind fails. |
| `session:confirmGroups(token, status, document)` | Requires the bound token, HTTP status 202, and the complete decoded response. Actual `GroupSelectionController.validate202` validates the exact binding/photo, whole ordered frozen group set, unique intent IDs, states and permanent blocks. Only then does actual store `confirm` receive the constructed acknowledgement. |
| `session:confirmPublication(token, evidence)` | For absent/explicit-none choices only, requires exactly `{publicationRecorded=true, albumAttachmentDurable=true}`. It records no group submission and cannot accept a fabricated empty batch. |

The view contains `scope`, `selectionState`, `choice`, `selectionRevision`,
`flickrGroupIds`, `handoffId` and the original `outboxRevision`. A missing editable
choice is `selectionState="absent"`, revision 0, `choice="none"`, and zero groups.
An explicit empty Save is `selectionState="none"` with its positive saved
revision. Both can proceed without a selector; the distinction remains visible.
Groups and scope in every view are copies. Caller mutation of views, token
properties, binding inputs or a response after validation cannot change the
private snapshot or the acknowledgement passed across the write gate.

The module allocates no handoff identity: the publisher supplies a valid
non-secret correlation ID through its existing qualified allocation path.
Duplicate IDs, full storage, corrupt selection/outbox, a revision race, stale
scope, timeout or unconfirmed readback return a failure state for this photo.
An old confirmed handoff consumes an editable entry only when its revision and
groups still match; newer edits survive, including an empty Save. Existing
outbox history prevents revision reuse after consumption. Concurrent operations
on one session return `busy`; another photo has its own session and can progress.

Successful confirmation returns `state="confirmed"`, `selectionConsumed` and
`groupAcceptanceRecorded`. The last value is false for zero groups. Group
acceptance records durable intents, which may already be moderated or blocked;
it does not establish Flickr delivery, photo publication, Album attachment or
overall publisher success. For zero groups the caller must independently prove
the publication record and durable Album obligation before passing both flags.
The adapter neither performs nor verifies those external writes itself.

## Integration and evidence limits

Before any render, #0026 can compose this module directly with the completed
Library Save/store modules. Whole-#0024 acceptance is not a source-composition
prerequisite. The owning publisher must correlate the validated new-upload
binding to the exact rendition, own its qualified transport/strict bounded JSON
decoding, and submit exactly the detached frozen group IDs. The response cannot
choose or replace the expected binding. An arbitrary store acknowledgement is
not part of the public adapter interface.

The pre-render outbox snapshot deliberately has no hosted binding. `bindGroups`
locks the newly created publication binding in this invocation only; it does
not mutate that immutable durable snapshot. Tokens cannot be reconstructed from
IDs or moved between sessions. Crash/restart reconciliation needs the separate
publisher publication/binding recovery contract; this adapter grants no replay
authority and provides no recovery dispatch operation. Existing-bound or
existing-public photo workflows retain their own proof/reconciliation adapters.

`PRODUCTION_QUALIFIED` remains false. `Info.lua`, metadata registration and the
existing common modules are unchanged by this work. No callback, native run,
cloud request, credential access or accepted #0027/#0029 evidence is introduced
or reopened. The target remains Lightroom Classic 15.6 build
`202609251514-f839cde9` with SDK15.3 build `202604090947-8f3672ed`.

`tests/test_frozen_choice_consumption.py` executes the actual adapter, store,
controller response validator and dkjson in Lua5.1. Its synthetic SDK boundary
covers missing/none/groups, safe integers, immutable snapshots/bindings/acks,
late acknowledgements, revision reuse fencing, whole-response validation,
retained terminal blocks, independent photo failure, exact UUID/service/Album
scope, corrupt-state preservation, gate/cancellation fences and zero-group
obligations. SDK15.3's actual Windows `luac.exe -p` checks both new Lua files.
Local documented API references were inspected for the export-context fields
and the existing photo/service/collection methods; licensed SDK source is not
copied here. These are bounded source/compiler checks, not host qualification.

Implementation verification on 2026-10-17 passed 19 dedicated Lua5.1 tests,
20 existing selection-store tests, 11 existing selection-controller tests,
Ruff lint/format and Pyright. Python checks used
`uv tool run --from uv==0.12.5 uv run --frozen` without tooling updates.

SHA2-256 provenance for the exported boundary and actual core dependencies:

| File | SHA2-256 |
| --- | --- |
| `FrozenChoiceConsumptionAdapter.lua` | `e2969f8b7b91fb201896b473f7728f29174ee1b8dc1104d0db49a17519a596cb` |
| `GroupSelectionStore.lua` | `E3B06EC949F4A13E641F926515BCD571B88166750F02690484CF2871BF5D146D` |
| `GroupSelectionController.lua` | `79A3E058C3707CFF3C2DA5A1C9EBA2975C21F7C1B1A92E59C3DD72D178B8B7C1` |
| `dkjson.lua` | `197CB50834C642F84B4CF99FE724932C50E6D9C92FAEC7AD89AA25E91DF4D481` |
