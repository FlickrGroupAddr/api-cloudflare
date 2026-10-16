# Bounded editable selections and local group handoffs

Date: 2026-10-16. Status: bounded source implementation with synthetic Lua 5.1
tests; no production registration, provider enablement or live catalog write.

The authority is the architecture repository's `AGENTS.md`, documentation
authority policy, accepted ADR0045 and ADR0063, and accepted local selection and
recovery clauses in `docs/plugin-service-contract.md`. Research does not amend
those sources. The implementation uses the current locally inspected SDK15.3
documented photo/catalog plug-in property methods and synchronous private write
gate. Terry confirmed that SDK version on 2026-10-15.

`clients/lightroom/FGA-LrC15.lrplugin/GroupSelectionStore.lua` implements a small
injected store. No `Info.lua` or metadata declaration is added here. A future
registered production integration must declare ADR0045's private untitled photo
string field before using it with a live photo.

## Persistent documents and limits

The per-photo `groupAdditionSelections` string follows ADR0045's exact schema:
`schemaVersion: 1`, with `entries` ordered by numeric service and collection
local IDs. An entry contains only `publishServiceLocalId`,
`publishedCollectionLocalId`, `photoUuid`, `selectionRevision`, `choice` and
`flickrGroupIds`. Every entry must name the owning photo UUID. The store permits
at most 64 service/collection entries and 512 KiB of encoded selection JSON per
photo. A choice is `none` with an empty array, or `groups` with one through 60
unique exact IDs sorted bytewise. Missing state is distinct from explicit none.

The separate catalog-wide `groupAdditionOutboxV1` string is
`{schemaVersion: 1, records: [...]}`. Records are ordered bytewise by `handoffId`.
The outbox permits at most 128 retained records and 1 MiB of encoded JSON. It
never evicts an unresolved or acknowledged record. There is no automatic
compaction, deletion or repair API; a separately reviewed retention policy is
needed before these finite bounds can be reclaimed.

Each record copies all six selection fields and adds `handoffId`,
`outboxRevision` and `state`. A snapshot of an absent choice explicitly uses
revision 0, `none` and an empty array; real editable revisions start at 1. The
initial record has revision 1 and state `prepared`. An acknowledged record has
revision 2 and state `acknowledged`; its original correlation and selection
remain immutable. A bound-photo record also copies an exact `binding` object:
`fgaPhotoBindingId`, `flickrPhotoId`, `verificationRevision`, `linkRevision`,
`sourceKind`. The source kind must be `existing_public_flickr_photo` or
`fga_direct_upload`. A bound photo cannot snapshot an empty group queue.

For an acknowledged group batch, `submissions` retains the exact bounded
validated intent projection: `fgaSubmissionIntentId`, `flickrGroupId`, `state`,
`created` and `permanentSubmissionBlock`. Rows match the snapshotted sorted
group IDs one for one; intent IDs are unique. Unknown states, non-boolean
created values, missing/extra groups, contradictory permanent blocks and
invalid timestamps are rejected. Protected moderation/delivery states require
their matching immutable block and `created: false`. This projection is the
batch response, not a fabricated full status response.

Strict grammar checking precedes the existing dkjson decoder. The store rejects
comments, malformed/trailing JSON, duplicate decoded keys, object/array
confusion, extra fields, unknown versions, invalid identities, duplicate scopes,
invalid sort order, oversized documents and invalid revisions. It preserves the
original bytes on refusal. Only absent (`nil`) properties initialize empty
documents. An empty string or JSON null is corruption, not an empty choice.
dkjson's documented custom encoders format validated integers with `%.0f`;
Lua5.1's default `tostring` would round some otherwise safe integer IDs and
revisions. No credential, OAuth envelope, authorization header, display name,
photo title, filename or other raw photo metadata belongs in either document.

## Adapter API

Construct `Store.new{catalog, photo, plugin, pcall, activeCatalog}`. Production
callers must inject `LrTasks.pcall` and `LrApplication.activeCatalog`, and invoke
the store from an SDK task where the documented gate may yield while acquiring
access. The implementation imports no networking, filesystem, password, dialog
or task-launch API. Unit tests inject Lua `pcall` only to exercise control flow.

All methods use colon calls. Every scope is exactly
`{publishServiceLocalId, publishedCollectionLocalId, photoUuid}`. Positive local
IDs/revisions are exact integers no greater than 9007199254740991. The caller
must first resolve and validate the ordinary FGA Album/service/photo membership;
this storage adapter verifies the active catalog object and photo UUID again
before, inside and after its gate. Names never establish scope.
The store copies scope and optional binding before waiting for the gate, so a
caller mutating its own table cannot retarget a waiting save.

| Method | Successful result and boundary |
| --- | --- |
| `readChoice(scope)` | `{state="ready", selection=entry-or-nil}` |
| `saveChoice(scope, groups, expectedRevision, handoffId?, binding?)` | `{state="saved", selection=entry, handoff=record-or-nil}`; optional handoff is created atomically with the new editable selection |
| `prepare(scope, expectedRevision, handoffId, binding?)` | `{state="prepared", handoff=record}`; copies the already-saved revision without consuming it |
| `readHandoff(scope, handoffId)` | `{state="ready", handoff=record}`; refuses a different scope |
| `listPending(scope)` | `{state="ready", handoffs=[records]}`; returns every prepared record in the exact scope, bounded by the validated outbox |
| `confirm(scope, handoffId, expectedOutboxRevision, ack)` | `{state="confirmed", selectionConsumed=boolean, handoff=record}`; updates durable acknowledgement and consumes only the equal editable revision |

Expected selection revision 0 means absence. `saveChoice` accepts zero through
60 IDs, normalizes order and refuses duplicates. It increments the maximum of
the current editable revision and retained outbox revisions for the same scope.
Retaining that high-water mark prevents revision reuse after consumption: an
old receipt cannot match revision 1 of a newly created choice. Exhausting the
safe integer range refuses the save. A reused handoff ID refuses the operation;
recovery reads the immutable existing record rather than making another one.
Even an equal revision cannot consume a current entry whose choice or group set
contradicts its immutable snapshot; that state is preserved as invalid.

A group acknowledgement has exact fields `kind="groups_accepted"`,
`selectionRevision`, `flickrGroupIds`, `submissions` and the original `binding`
when one was snapshotted. The caller supplies it only after validating the
complete durable backend result, including binding/photo correlation. Raw HTTP
202 is not acknowledgement. A zero-group publication acknowledgement instead
has `kind="publication_recorded"`, the exact revision and empty group array,
`publicationRecorded=true` and `albumAttachmentDurable=true`. It cannot stand
for an empty group batch. The store validates correlation and shape; it cannot
independently prove a remote write or turn caller assertions into hosted truth.

Fixed failure states include `scope_invalid`, `choice_invalid`,
`stored_invalid`, `storage_full`, `revision_conflict`, `revision_exhausted`,
`handoff_invalid`, `handoff_exists`, `handoff_not_found`, `ack_invalid`,
`storage_unavailable` and `write_unconfirmed`. Results contain no raw exception
or stored value. A caller retains its dialog choice and unresolved handoff on
failure and performs no dependent external action.

## Transaction and recovery limits

Each operation reads and validates both whole documents inside one synchronous
`withPrivateWriteAccessDo(callback, {timeout=5, asynchronous=false})`. It checks
expected revisions inside the gate, validates/encodes both proposed values and
checks both byte bounds before either setter. Atomic save plus snapshot and
acknowledgement plus equal-revision consumption use that same callback. The
callback performs no network, UI, render, yield or task launch. The injected
active-catalog adapter must be a simple SDK read.

Success requires the documented `executed` return, completed callback and exact
post-gate readback of both properties. Queued, aborted, unknown, thrown and
mismatched readback outcomes are unconfirmed. A callback unexpectedly invoked
after the gate returned is fenced before it can write. A failed readback can
follow a committed local write, so failure never authorizes inventing a new
handoff or ignoring the existing durable record. Read it and reconcile.

The accepted #0029 schema-2 build-0.0.2.6 evidence at
`docs/evidence/lrc15-outbox-host-2026-10-15.json` records same-session private
catalog write/readback, callback rollback and independently observed normal
restart for its exact isolated fixture. This implementation does not request
repeating that proof or enlarge its conclusion. Synthetic tests model rollback;
they cannot establish host disk flush, arbitrary process crash, power loss,
storage failure or restored-catalog correctness.

This module is the editable selection and group handoff storage core. It is not
a complete upload recovery record, upload dispatch marker, restore detector,
external replay policy or production-qualified outbox. `prepared` identifies
an unresolved local handoff, never proof that a provider operation did not
occur. Restored/copied/absent historical local state cannot establish no image
dispatch. Production upload integration still requires the explicit restore/
copy recovery gate and hosted reconciliation described in the outbox research,
plus complete upload authorization/result ordering and separate crash-point
evidence. Catalog switching fails a current operation closed; catalog copies
do not acquire new cross-device authority.

`tests/test_group_selection_store.py` executes the actual module under Lua5.1
with synthetic catalog/photo objects. It covers strict schemas and bounds,
revision conflicts inside the gate, stale acknowledgements and revision reuse,
immutable snapshots across reconstructed store instances, zero-group ordering,
partial/contradictory responses, exact high integer serialization, full-storage
refusal, transactional rollback, delayed callbacks, read failures, readback
mismatch and catalog switches. It accesses no real catalog or provider.

## Existing-public photos without an LrPhoto

`ExistingPhotoGroupStore.lua` closes the separate existing-public-photo path.
Accepted ADR0022, ADR0038 and `existing-public-photo-intake.md` explicitly allow
group queueing without a Lightroom photo, publish service or Album. They forbid
creating/mutating a published-photo association for this path. Private plug-in
recovery bookkeeping is separate from that publication record boundary; it
does not attach or import the Flickr photo. The accepted existing-public-photo
contract supplies the binding/proof and common batch semantics, while the
plug-in/service contract leaves the exact local recovery mechanism open. The
catalog-wide property implementation follows the same documented SDK15.3
private property gate already exercised in the isolated #0029 proof.

This module never accesses `LrPhoto`, the ADR0045 selection field, publication
metadata or catalog publication APIs. It uses one different catalog property,
`existingPhotoGroupOutboxV1`, with its own strict `{schemaVersion:1,records:[...]}`
document. Bounds are 128 retained records, 1 MiB encoded JSON and one through
60 unique byte-sorted IDs per group batch. Unknown/corrupt/full state fails
closed without eviction, automatic repair or replay. A read cannot silently
replace the property with an empty document.

The exact durable scope is
`{installationId,fgaPhotoBindingId,flickrPhotoId,linkedFlickrRevision,sourceKind}`.
The first three IDs are opaque bounded strings, the linked revision is a
positive safe integer, and source kind is the binding's exact
`existing_public_flickr_photo` or `fga_direct_upload` provenance. The latter is
needed because existing-public intake can reuse a binding first created by a
direct upload. No fabricated UUID, local photo ID, service or Album is used.
The current-installation contract does not expose an FGA user ID: the FGA API
backend derives the user from the authenticated installation and binding, so
this local schema does not invent a user field or claim client-side authority.

Each immutable record adds `selectionRevision`, `choice:"groups"`,
`flickrGroupIds`, `handoffId`, `outboxRevision`, `state`, and the same exact
five-field `binding` used by the photo store. Its binding/photo/source/link
fields must equal its scope. `verificationRevision` belongs to the refreshed
proof frozen in that record, rather than the scope used while the modal was
open. A different binding, Flickr photo, installation, source or link cannot
reuse another record. A duplicate selection revision for one exact scope is
corrupt, even under a different handoff ID. Integer encoding and validated
acknowledged `submissions` follow the photo-store rules above.

Construct `ExistingPhotoGroupStore.new{catalog,plugin,pcall,activeCatalog,
currentIdentity}`. The new adapter uses the same colon `readChoice`,
`saveChoice`, `readHandoff` and `confirm` signatures and success/failure states
as the group controller. There is no `prepare` method: a nonempty existing-photo
queue always performs one atomic `saveChoice(scope,groups,expectedRevision,
handoffId,binding)`. A handoff ID and the matching binding are mandatory. It
cannot turn an empty selection into a batch or persist a synthetic no-group
publication. Pending changes stay in the controller's memory until that atomic
snapshot; closing or canceling the modal makes no durable change.

The injected `currentIdentity` is a simple non-yielding read of the calling
session's verified identity and returns exactly
`{installationId,linkedFlickrRevision}`. The store checks it and the active
catalog before, inside and after the synchronous private gate. Missing or
changed identity fails closed. This check is correlation fencing, not remote
authentication: callers still require current installation credentials,
complete membership/history, fresh owner/public proof and full backend response
validation. The store imports no credential API and stores no bearer value.

`readChoice` returns the highest retained revision for the exact scope only
when that latest record is still prepared. An acknowledged latest record means
there is no pending choice. Earlier unresolved records remain retained and can
be inspected by handoff ID; they never reappear as an old editable choice after
a newer choice was acknowledged. `saveChoice` checks the currently pending
revision inside the gate (or expected 0 for absence), then allocates one more
than the highest retained revision. It never resets that high-water mark after
acknowledgement. `confirm` changes only the matching record to acknowledged and
returns `selectionConsumed:true` only when it was the latest pending revision;
an older response preserves the newer pending choice. No record is deleted.

Each operation strictly validates the whole outbox, freezes caller scope and
binding before waiting for the gate, applies compare-and-set under that gate,
requires synchronous executed status and checks exact readback. It provides no
automatic replay or recovery dispatch function. Restoring or copying a catalog
does not refresh an installation/link/binding proof or make a prepared record
safe to send. Production integration and independent host/crash/restore gates
remain disabled and unqualified as described above.

`tests/test_existing_photo_group_store.py` executes the actual new store under
Lua5.1 with synthetic catalog-only SDK mocks. It covers full correlation,
unknown/corrupt/oversize/full records, strict grammar, duplicate scoped
revisions, exact high integers, immutable snapshots, stale/newer revisions,
validated intent retention, rollback, delayed callback fencing and catalog/
identity changes. A composition test runs the actual `GroupSelectionController`
and existing batch client through fresh proof, durable whole-set snapshot, one
batch POST and validated acknowledgement with no `LrPhoto` object or API.

Both stores expose `listPending(scope)` after reconstruction. It returns all
prepared records for that exact scope in stored handoff-ID order, including an
older unresolved handoff when a newer handoff has been acknowledged and the
editable/current choice is absent. Returned records are independent copies;
the caller does not need to remember a handoff ID outside the outbox to discover
this unresolved work. This read-only operation shares strict validation,
identity/catalog checks and record/byte bounds with other reads. It sends
nothing and grants no replay permission. The user-facing recovery workflow
and hosted reconciliation remain separate integration work.

Binding-only records additionally carry the exact fixed
`workflow:"existing_public_photo"` independently of their immutable
`sourceKind`. The optional constructor `workflow` setting must equal that value
when supplied. An existing-public-photo selection can reuse
`sourceKind:"fga_direct_upload"`; neither the store nor controller rewrites that
provenance. Its explicit existing-public workflow still requires the final
fresh hosted proof. The controller receives this workflow as a separate trusted
constructor context, rather than inferring it from binding provenance. The
composition regression exercises that reused-upload binding through one proof,
durable snapshot and one batch handoff.
