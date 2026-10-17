# Hosted local-removal archival

Date: 2026-10-17. Maintainer handoff for #0115 under the accepted
[title and local-removal wire](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/proposals/album-title-local-removal-wire-2026-10-17.md)
(#0094) and accepted #0092 create-repair boundary. The contracts control over
this implementation summary.

## Scope and activation

This is non-destructive hosted archival. Removing a local photo relationship or
collection preserves Flickr photos, photosets and memberships. No lifecycle
route makes a Flickr call. There is no DELETE, remove-membership, image-replace,
unarchive, title-based adoption, replacement-create or photoset-ID reuse path.
The source remains dormant/default-off under `FGA_ALBUM_LOCAL_REMOVAL_ENABLED=0`; this work does not authorize deployment,
feature activation, live Flickr work or native/Lightroom execution.

## Wire and archive

The two authenticated PUT routes are `/album-bindings/{bindingId}/local-removal`
and `/album-bindings/{bindingId}/photo-associations/{photoBindingId}/local-removal`,
relative to `/api/v001`. They require the current installation credential,
closed schema-version-1 JSON, canonical paths and no query parameters. Requests
are bounded to 4 KiB and success responses to 32 KiB. A first receipt is 201
with its exact replay Location; replay is 200. JSON uses private no-store,
nosniff and no-referrer. Existing lifecycle GET and #0092 administrative routes
retain their respective ownership; no new administrative route is introduced.

- Photo removal archives an existing binding/photo pair, advances the binding
  and obligation revisions once, and retains its immutable pair receipt. A
  missing pair is 404; removal never creates an obligation.
- Album removal atomically closes the binding as
  `local_collection_removed_remote_preserved`, archives all accepted local
  pairs and establishes their receipts. It advances the binding revision once
  for the transaction and each changed obligation revision once.
- Exact authenticated receipt recovery precedes stale-revision checks. Pair
  replay is one-way; album replay requires the original acknowledged attempt
  value, including null. A different value conflicts. Replay changes no
  revision, event or work fact, and old admission receipts do not resurrect a
  relationship.
- New removal checks binding revision before obligation revision and validates
  the exact current unresolved create acknowledgement. A revision/ambiguity
  change requires refreshed confirmation; never copy a newly found attempt
  into an old confirmation. Current ownership remains mandatory, while a
  paused/revoked remote grant alone does not prevent safe archive/replay.

## Retained worker obligations

Undispatched title intent is canceled without erasing historical title revision.
A marked title attempt retains evidence for read-only reconciliation; even an
observation of its pre-dispatch title cannot authorize another editMeta POST.
Archive serializes with dispatch and admission, so a losing worker cannot create
another title marker and no new photo obligation is admitted after closure.

Already accepted membership obligations continue to verified fulfillment or
truthful repair, including undispatched obligations. Archive before first-create
marking can still permit original materialization using the immutable first
photo and last committed title/revision frozen by archive. Original claims,
link/grant/pause fences and fresh proofs remain mandatory. A marked ambiguous
create is never replayed; the accepted proven-zero-request-bytes exception is
unchanged. Bound missing photosets retain identity and are never recreated.
After an archived pair's first verified fulfillment, later external membership
removal does not trigger automatic repair.

## Tombstones and administrative repair

The future client callback must persist its exact pending request in durable
publish-service settings before network handoff, obtain the hosted receipt and
persist that receipt before collection destruction can be acknowledged. Photo
removal uses a binding/photo-pair tombstone; album removal uses binding identity.
A truly unbound local object needs no hosted tombstone. This hosted change does
not implement or qualify that Lightroom callback durability boundary.

A timeout/malformed response preserves the tombstone and resumes the same
request. A lifecycle GET showing archive does not replace its exact matching
receipt and acknowledgement. Hosted success followed by catalog/bookkeeping
failure leaves a closed hosted binding and visible local repair; retry local
bookkeeping, never unarchive or create a new binding to hide partial completion.

Album confirmation acknowledges **Album creation repairs** for original pending
or in-flight materialization, even before ambiguity exists. The immutable
removal receipt retains its original request/acknowledgement facts. Later
`create_outcome_unknown` retains the original marker/context/first photo and,
in one fenced semantic transaction, sets `admin_only`, advances binding revision
once and exposes the original attempt with the retained removal acknowledgement
time. The earlier null-attempt receipt is not rewritten.

Repair remains discoverable without a catalog through
`GET /admin/album-create-repairs` and exact
`GET /admin/album-bindings/{bindingId}/status`. The owning administrative session,
explicit exact-ID owner choice and fresh proofs remain required; an installation
credential or UUID is not an administrative session. Resolution preserves
archive, canceled title intent and immutable identity. Existing accepted
attachments may continue; changed authority or missing proof remains attention,
without override or replacement create.

## Verification and remaining gates

Independent protocol/integration review passed fourteen checks, including the
canonical encoded opaque-photo-ID correction and exact generated projections.
Independent storage/concurrency review passed 228 checks, including actual local
D1 race/rollback/SQL authority tests and the reviewed legacy-fixture adaptations.
No open material findings remain. Detailed private receipts are retained in
workspace `work-batch-2026-10-17-archive`.

Parent verification: 757 Python/Lua tests, pinned native TypeScript 7.0.2,
exact generated API consistency, Ruff and Pyright passed. Full backend result:
857 tests passed. Publication privacy/whitespace verification accompanies the
handoff commit. No upstream operation or native UI action occurred.

New guards correctly refuse old tests' direct archive updates. Current-schema
fixtures now use the real archive operation with current revisions and exact
acknowledgements; historical predecessor-schema mutation and migration
preservation tests remain explicit. No production guard was weakened. The first
aggregate was stopped after exposing these setup failures and an obsolete race
proxy; the final run uses bounded process concurrency and the corrected harness.
The runtime maximum-counter state was not manufactured by disabling SQL guards;
that extreme remains an unexecuted limitation distinct from the tested safe-range
refusals, authority, revisions and rollback.
Hosted D1, exact-artifact qualification, administrative UI and Lightroom Classic
15.6 / SDK 15.3 callback destruction/recovery remain separate release gates.

The aggregate also exposed the separately tracked #0154 Request-owner lifetime
regression. Its bounded shared-reader/admission correction and independent GC
proof are recorded in [the cancellation note](album-request-cancellation-2026-10-17.md).
The final 857-test result includes that correction. Initial delegation used
sixteen direct subagents: eight Sol Medium, four Sol High and four Luna Light;
completed author slots were reused for independent review and narrow regression
corrections. No children, tool upgrades, shared localswim edits or live actions
were used. The parent owns integration, publication and handoff.
