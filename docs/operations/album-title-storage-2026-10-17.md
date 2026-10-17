# Revisioned album title storage

Date: 2026-10-17. Source implementation for #0114 under the accepted
[title lifecycle wire](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/proposals/album-title-local-removal-wire-2026-10-17.md).

Migration `0024_album_title_sync.sql` adds title receipts, attempts and sanitized
append-only events without rebuilding admission, materialization or repair
tables. It runs after `0023` and before `0025`. Its only replaced binding guard
preserves the preceding admission/materialization revision conditions and adds
exact title receipt authority. A deliberate same-text rename advances both
binding and title revision once. Receipt acceptance and the binding's ordinary
change event are one owning-D1 transaction.

Exposed title observations, dispatch evidence, completion/attention transitions
and missing-album status advance the physical binding revision once per semantic
transaction. Guarded append-only title semantic events authorize that increment;
the ordinary binding event consumes the authority. Claim allocation, read-budget
charges, lease changes and private result-class bookkeeping do not advance it.
Migration `0025` retains this branch alongside its attachment semantic branch.

`album_title_store.ts` exposes current ownership-authenticated lifecycle reads
and exact revision-addressed intent acceptance. A matching receipt replays its
immutable request/acceptance facts before stale, archive or remote-link checks;
the current snapshot is selected in the same transaction. A different request
at an occupied revision conflicts. New intent checks binding revision first,
then title revision, exhaustion, lifecycle and current remote authority.

The worker APIs reserve each bounded read before external I/O. Claims preserve
the exact owner, photoset, link/grant and write-gate snapshots. Expired claims
resume with a new lease/epoch while retaining their marker, desired and prior
title, read budget and retry time. The dispatch API returns authority only from
the exact conditional `UPDATE RETURNING` row; trigger-inflated D1 metadata is
never used to infer permission for another POST.

An attempt's original binding-revision snapshot is immutable. Each lease records
its own binding revision, and subsequent authority derives only the guarded
semantic events produced by that attempt in that epoch. A foreign binding change
fences the existing lease and late response. Recovery captures the current
binding revision in a new lease after expiration, retaining the original
snapshot and unresolved marker before any further reconciliation read.

Reconciliation classifies against the latest committed desired title first,
then the dispatched title, then its exact prior title. The latest satisfied
revision is persisted explicitly so equal text cannot accidentally satisfy a
later deliberate rename. A third title becomes a conflict. An incomplete read
retains prior timestamped evidence and the unresolved marker. Archive cancels
unmarked work; marked work remains eligible only for reads and cannot dispatch
again. Original create metadata is not represented as an observed remote title.

Each execution's persisted deadline is ten seconds. Retry timing is durable
before the I/O boundary, including crash recovery. Dispatch retries are capped
at three per revision, with at least five then thirty seconds between attempts;
reads are capped at five per attempt. A crash after the fifth reservation becomes
durable attention on expiration. Unresolved marked exhaustion blocks newer
dispatch. A complete prior-title observation after the third dispatch safely
closes that marker in attention, allowing a later deliberate intent. No counter
wraps beyond the JavaScript safe integer boundary.
The fifth pre-dispatch read may prove completion, but cannot authorize an edit
that would have no remaining capacity for its mandatory post-dispatch proof.

Strict missing-album evidence is retained on the attempt and projected through
`album_binding_remote_status`; it never clears the bound photoset or invents a
replacement materialization. Migration `0025` extends that same status view for
attachment evidence.

Verification uses actual modules with synthetic external boundaries and actual
local D1 for migration preservation, atomic failure rollback and guarded title
dispatch/reconciliation. These checks do not qualify hosted D1, Lightroom,
deployment, credentials or live Flickr operations. Consumers remain explicitly
default-off. Local removal routes, tombstones and their repair acknowledgement
receipts belong to #0115; the title storage only preserves their accepted
no-further-title-write boundary.
