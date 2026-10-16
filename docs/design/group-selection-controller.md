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
| `client` | Existing `clients/lightroom/GroupSubmissionClient.lua`; copied into a candidate bundle by a separately owned composition step. |
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
