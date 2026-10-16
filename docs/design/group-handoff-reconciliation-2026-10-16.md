# Explicit immutable group handoff reconciliation

Date: 2026-10-16. Implementation candidate for #0063; disabled and unregistered.
This note projects the accepted existing-public intake contract and the
[adapter map](group-workflow-adapter-map-2026-10-16.md); it grants no native,
hosted, real-account, release or group-addition authority.

`GroupHandoffReconciliation.new(deps)` captures the catalog and verified
installation/link/current-credential session. The composition supplies a
qualified SDK task, `LrTasks.pcall`, cancellation/session readers, the existing
store, canonical `GroupSubmissionClient`, proof, batch, strict JSON and observed
clock adapters. `workflow` is explicitly `existing_public_photo` or
`publisher_bound`; an existing-public workflow retains upload-origin provenance.
Missing dependencies refuse construction. `PRODUCTION_QUALIFIED` remains false;
the module has no release registration or invocation of its own.

`list(scope)` enumerates `listPending` under the exact store scope and reads
each original ID through `readHandoff`. It exposes only original pending IDs
after current-session fences. Construction and listing never call proof or
batch adapters. An empty list, copied catalog, restored store, missing record or
unreadable outbox proves nothing about remote submission history.

Only the photographer's explicit `reconcile(scope,handoffId)` attempts a batch.
The controller reads the original prepared handoff, verifies its workflow,
scope, binding, link and whole ordered 1–60 group set, and copies it before
yielding. Session checks bracket catalog and HTTP operations, with an additional
check inside the final POST boundary. Credential replacement/candidate,
installation/link change, catalog change or cancellation stops dependent work.
One controller rejects overlapping actions as busy. The invocation owner must
reuse one controller for its recovery view and cancel it when that view closes.

For existing-public recovery, including upload-origin bindings reused by that
workflow, the proof adapter rechecks the original Flickr photo and expected
link. The complete proof document must preserve binding ID, photo, source and
link. The returned verification revision is attempt-local authorization; only
the wire request uses it. The original handoff, selection/outbox revision,
binding, old proof revision and pair set remain immutable. The observed clock
guard refuses nonfinite, backward or at-least-15-second intervals, including
at dispatch after encoding. The documented SDK wall clock cannot guarantee
elapsed time across undetected clock changes; backend revision/proof-age checks
remain authoritative. A publisher-bound upload-origin repeat preserves the
original revision and body; backend stale-revision rejection retains the record.

One canonical batch submission sends the entire original set. There is no
automatic retry, replacement handoff, subset, new choice, upload, direct Flickr
add/remove or association repair. Existing remote pairs retain their intent
IDs and permanent suppression; backend reconciliation owns idempotency, owner,
link, visibility and current-revision enforcement. Retained status is a separate
read-only view and cannot invent an acknowledgement or clear a block.

The core bounds and strictly validates the entire HTTP 202 using
`GroupSelectionController.validate202` before calling store `confirm`. The
acknowledgement uses original handoff/outbox/selection revisions and original
snapshotted binding, plus the validated whole response. Existing store logic
consumes only the matching current editable revision. A newer edit survives.
Both stores accept the optional final parameter
`confirm(scope,id,outboxRevision,ack,operationCurrent)`. Recovery supplies its
full current-session predicate as this per-operation fence. It must be a
non-yielding function returning literal `true`. The store checks it before
waiting for the private gate, inside the callback before reading, immediately
before durable writes and at exact readback. A session change while waiting
therefore leaves the prepared record and editable selection untouched. Existing
callers omitting the parameter retain the stores' existing scope fences; no
schema, retention or previously accepted store contract changes are required.
Transport failure, invalid proof/202, cancellation, context change, storage
ambiguity or corrupt/full local state cannot authorize replacement work.
An unavailable confirmation returns unresolved; a durable acknowledgement may
already exist after an ambiguous store return, so future listing rereads storage.

## Focused verification

`tests/test_group_handoff_reconciliation.py` executes the actual Lua5.1 recovery
core, canonical batch client, strict response validator and both durable stores
with synthetic SDK/storage/backend boundaries. The fixture demonstrates a
committed lost response followed by same-ID, `created:false` reconciliation
without another hint/order/attempt; fresh attempt proof versus immutable stored
proof; literal publisher request repeat; malformed whole responses; proof age
and context fences; full/corrupt/absent outboxes; newer edits and permanent
block retention. These tests are local protocol evidence, not a live backend
or Lightroom Classic 15.6 / SDK15.3 qualification. Independent review and
integration/native gates remain with the parent ticket pipeline.
