# First-photo album materialization: executable contract map

Date: 2026-10-17

Status: Derived implementation and test map for #0111. This document accepts no
new policy and claims no hosted, Flickr, native Lightroom or deployment pass.
The card was verified In Progress before this work. All runtime entry points
remain dormant. The owning accepted contracts below control over this map.

## Authority and bounded scope

Apply canonical [documentation authority](../../../architecture-design/docs/README.md),
[album publishing](../../../architecture-design/docs/album-scoped-publish-contract.md),
[write reconciliation](../../../architecture-design/docs/album-write-reconciliation.md),
[lifecycle semantics](../../../architecture-design/docs/album-lifecycle-contract.md),
and [worker scheduling](../../../architecture-design/docs/worker-persistence-scheduler-contract.md).
Accepted [#0088 admission](../../../architecture-design/docs/proposals/album-binding-photo-association-wire-2026-10-16.md)
owns transaction authority, immutable identity and revisions. Accepted
[#0092 status/create repair](../../../architecture-design/docs/proposals/album-status-create-repair-wire-2026-10-17.md)
owns the exact materialization/status vocabulary and retained unknown-attempt identity.
These relative canonical links assume the adjacent FGA repositories.

#0111 consumes the committed #0108 binding and #0110 primary obligation. It adds
only first-photo create claim, dispatch, proof and durable recovery. Later-photo
read/add/read belongs to #0112; status/candidate/owner-resolution routes to #0113;
title/lifecycle wire and title dispatch to #0114. Terry accepted #0094; canonical
commit `3fbb6bf` records that decision. This map does not implement those routes.
Accepted non-destructive removal semantics remain controlling.

## Module and test responsibilities

The names below are the author-coordinated module seams, not a second authority
for their eventual exact TypeScript signatures. Storage owns migration
`0022_album_materialization.sql` and `src/album_materialization_store.ts`;
upstream owns `src/album_materialization_transport.ts` with
`createSyntheticAlbumMaterializationTransport`; worker owns
`src/album_materialization_worker.ts` and dormant
`consumeAlbumMaterialization(env, bindingId, transportFactory)`. The transport
requires explicitly injected signing, fetch and current-authority functions;
there is no runtime factory, default network, credential reader, scheduler
registration or HTTP entry point in this slice.

| Accepted invariant | Executable seam and durable fact | Required focused evidence |
| --- | --- | --- |
| Hosted exact first candidate is immutable | Store claim derives owner/photo from existing binding and committed photo proof; no client remote ID/title selects identity | Later candidate, foreign owner, changed link, malformed or absent proof cannot claim/create |
| One active database claim | `claim` obtains a strictly increasing epoch, lease ID and bounded database-clock expiry in the owning D1 transaction | Two claimants yield one owner; expired takeover increments epoch; stale release/update is inert |
| Current worker authority differs from admission credential authority | Store checks current link revision, native grant generation, connection pause/operation/local state, and exact enabled deployment/user gate revisions; installation token rotation alone does not revoke accepted work | Pause/relink/gate change at each await refuses marker/result; accepted work survives ordinary credential rotation |
| Context evidence precedes dispatch | Transport reads complete successful first-photo `getAllContexts`; store retains exact unique photoset ID set and observation time on original attempt | Failed/mixed/duplicate/invalid/over-budget/incomplete body yields no POST; complete empty set is retained evidence but proves no remote identity |
| No unmarked POST | Prepare a fixed signed create request first; `markAlbumCreateDispatch` rechecks current claim/authority, unmaterialized state, absent photoset, original attempt, first photo and exact captured title/revision; commit append-only marker/count before one-shot send | Marker failure, changed title, changed primary, rollback and insufficient remaining lease yield zero POSTs; observer at fetch sees committed marker |
| Title is a request snapshot | Pending rename before marker changes the title that must be prepared; any later title intent cannot mutate an already marked request | Title race between prepare and marker refuses stale body; no refresh of durable marker with different request |
| Whole create success and exact read proof | Validate one opaque returned photoset ID and bounded Flickr navigation URL, then exact-ID `photosets.getInfo` owner and fresh first-photo contexts membership | Malformed success, wrong ID/owner, missing membership, failed read or invalid URL never completes binding or obligation; no `addPhoto` for primary |
| One atomic proof commit | `finish` commits immutable photoset ID/navigation/proof, materialized state and primary `membership_verified` with timestamps and events under current claim/fences | Partial fault rolls back every field/event/revision; duplicate remote identity conflicts; stale result cannot overwrite recovery; revision exhaustion refuses mutation |
| Ambiguity is durable | `unknown` retains original marked attempt and pre-context set; no committed identity is invented | Lost response, transport failure, process crash, failed result commit and marked lease takeover preserve `create_outcome_unknown`; repeated consumer/retry/hint sends zero more creates |
| Rejection is method-specific | `reject` accepts only a documented complete rejection whose semantics establish no album creation; all doubtful/unknown codes follow unknown | One fixture per explicitly supported code; HTTP success alone, arbitrary numeric code or generic group-add classifier is insufficient |
| Safe pre-dispatch failure is distinct | `failBeforeDispatch` never removes historical marker evidence; a fresh attempt is eligible only where no create bytes could have left | Read/prepare failure and marker rejection permit safe pre-dispatch progress; timeout/exception/lease expiry alone never count as zero-byte proof |
| State changes and history are fenced | Every store mutation checks current epoch, expected attempt and exact immutable IDs; semantic transaction advances binding/affected obligation once; lease housekeeping does not | Takeover, wrong attempt, stale authority and reused ID fail atomically; reads/claim renewal do not increment domain revisions |
| Removal preserves accepted work | Retain archived binding, immutable first photo, pending obligations and unknown attempts; no new relationship is admitted | Accepted primary obligation finishes or truthful repair remains after removal; no delete/remove/replacement endpoint; archived relation never triggers later drift restoration |

## Exact state and proof interpretation

#0092 defines `materialization_pending`, `create_rejected`,
`create_outcome_unknown`, `materialized`, `remote_album_missing_needs_attention`
and `album_identity_conflict`; pending/rejected/unknown require a null committed
photoset ID. Unknown requires the original marked attempt. Membership waiting
for an unresolved create remains `waiting_for_album`; completion requires
`membership_verified` plus its stored observation time.

The album publishing narrative says a returned ID supplies binding evidence;
the narrower reconciliation contract requires owner and membership reads before
committing the ID once. The executable seam therefore stages returned ID as
attempt evidence, then atomically commits identity and primary proof. It does
not expose a materialized binding before proof or an unknown binding with a
committed photoset ID. A returned ID whose proof is unavailable remains evidence
for read-only reconciliation, never permission for another create.

Exact owner and exact first-photo membership are the postcondition. The first
photo need not still be the remote album's primary role after an external edit.
Title, one candidate, primary-role match, elapsed time, an empty candidate list
or pre/post set difference cannot automatically establish ambiguous identity.
Owner selection and its provenance remain #0113. The worker must not invent an
automatic candidate-selection branch.

## Reuse, finite work and error boundaries

For eventual runtime binding, use existing `workerGrant`/`sameGrant` authority
concepts, fixed Flickr endpoint
signing, native credential envelope parsing, `NOW_US_SQL`, transaction guards,
and deployment/user Flickr write gates. The album store must enforce its own
album identity/claim predicates; a prior read of worker grant alone is not an
atomic dispatch authorization.

Require `budgetedFlickrFetch` and `DEFAULT_FLICKR_RATE_POLICY` for the same key-wide
rate window as ordinary work. `reserveFlickrAttempt` is tied to group submission
attempts and must not be called with fabricated group identities. Exhaustion or
budget-store failure sends no additional upstream request and cannot bypass the
marker or proof boundary. A rate failure after marker is conservatively unknown.
Do not import the group-add result classifier: its retry/uncertainty rules
describe a different remote operation.

One successful create path has four upstream calls: pre-context GET, one create
POST, info GET and post-context GET. There is no hidden retry, crawl, candidate
discovery or sleep loop. Reuse the ordinary worker's bounded lease/deadline
approach (60-second lease, 45-second invocation, at most 10 seconds per call,
5-second final-commit margin), checking remaining time before starting work.
These are the ordinary scheduler baseline and integration constraints, not a
claim that the synthetic seam establishes an outer invocation deadline or
provider capacity. The synthetic adapter bounds pre-context, prepare, create,
and combined info/post-context proof stages to 10 seconds each; factory work
must also fit the overall budget before any runtime binding is qualified.
Never begin a call if its deadline and commit margin cannot fit the lease.
Retain due work durably and yield when no progress is safe.

Accepted #0092 bounds discovery contexts at 1000 unique IDs and 1 MiB serialized
pre/post input; its 10-second total discovery/resolution deadlines apply to
those operations, not automatically to the four-call create workflow. Using
these finite context limits or stricter existing 256 KiB reader limits is a
conservative refusal boundary. Truncation, partial arrays and silently dropped
invalid entries never establish success. Exact chosen transport and aggregate
byte caps must be declared in code and boundary-tested; tighter caps can reduce
availability but cannot relax completeness.

No new HTTP error schema is introduced by this dormant worker. Existing
admission errors remain unchanged. Transport malformed/unavailable results,
known Flickr rejections, durable authority refusal and database unavailability
must remain distinct internally, with fixed sanitized codes. Logs/events retain
FGA binding/attempt IDs and classifications; no title, Flickr ID, URL, catalog
path, raw response or OAuth material. Missing authority is refusal, not absence.

## Decisions that must not be guessed

- The upstream author checked the official
  [create method documentation](https://www.flickr.com/services/api/flickr.photosets.create.html) and
  selected the conservative no-create allowlist `1,2,3,95,96,97,98,99,100`.
  `111,112,114,115,116` are excluded rather than guessed. An unsupported code
  becomes unknown; code 105/106 or generic
  transient service language is not zero-byte proof and never permits replay.
- This slice intentionally permits at most one lifetime marked create per
  binding. It does not implement re-create after a documented rejection or a
  zero-byte exception. Any later retry policy must preserve accepted dispatch
  history and prove the narrower safe exception explicitly.
- Lease and per-call limits do not authorize an unbounded pre-dispatch retry
  loop. Declare finite invocation work and durable due/backoff behavior. A
  separate product-level total retry count or operator retry action cannot be
  invented here.
- If the implementation wants to commit identity before owner/membership proof,
  automatically select an ambiguous candidate, overwrite a photoset ID, create
  after remote deletion or move controlling authority outside the owning D1,
  stop: those are consequential contract changes, not implementation choices.

## Verification boundary

This map was checked against accepted source sections and the sibling authors'
module interfaces. It requires fresh independent review and actual production
module tests; it is not an executable test receipt. Parent owns final aggregate
verification, integration and handoff. Native/provider qualification and release
remain separate, unpassed gates.
