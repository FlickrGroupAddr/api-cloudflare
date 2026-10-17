# Frozen ordinary-Album publish context

Date: 2026-10-17. Implementation note for #0097; dormant source, not native qualification.

`clients/lightroom/publisher/FrozenPublishContext.lua` composes the actual
[#0065 consumption adapter](frozen-choice-consumption-2026-10-17.md) with the
[#0095 upload-attempt store](upload-attempt-store-2026-10-17.md). Those modules
own selection semantics, strict response validation, storage schema and bounded
write gates. The accepted [upload-attempt contract](../../../architecture-design/docs/proposals/upload-attempt-recovery-store-2026-10-16.md)
and [publish flow](../../../architecture-design/docs/zero-state-publish-flow.md)
control. This module adds no wire, storage schema, selector or upload operation.

## Composition contract

`new(deps, exportContext)` captures one catalog, activation and freshly verified
ordinary-Album target. It returns a session or `nil, reason`. Dependencies are:

- `plugin`, SDK-aware `pcall`, `activeCatalog`, `activationToken`,
  `currentActivation`, and the dispatcher's synchronous `isOwner(scope, number)`.
- `readRemoteId(photo)`, a synchronous exact published-photo relationship reader.
- `verifyTarget(exportContext)`, the owning provider's fresh #0090 identity/target
  verification boundary. It returns `ok=true`, `fgaPublishServiceId`,
  `linkedFlickrRevision`, and lossless decimal `localCollectionIdentifier`.
- `identityCurrent(expectedTarget)`, a synchronous local predicate that checks
  the current verified identity against that captured three-field projection.
  It must return exactly true; it cannot perform network I/O or yield. The
  expected object is detached. The dependency owner supplies the verification
  mechanism; this module does not fabricate identity proof or a lease.
- Optional synchronous `cancelled()`.

The local identity predicate, catalog and activation are rechecked through the
existing modules' gate callbacks. `verifyTarget` runs outside private gates.
All callbacks invoked by a private gate must remain synchronous and local.
The dispatcher owns its ownership lifetime; this module does not allocate one.

`session:prepare(photo, handoffId, now)` is the single pre-render entry point.
The caller supplies its already-qualified non-secret handoff allocation and a
store-valid timestamp. The module verifies the exact catalog photo object and
ownership, calls #0065 `freeze` once, and persists precisely that detached choice
through #0095 `inspect`/`prepare`. No saved selection becomes `absent`, explicit
empty Save becomes `none`, and both persist an empty group array. The local
service/Album/photo tuple and hosted service identity are frozen independently
for each photo. Hosted Album identity/revision initially remain JSON null.

Only `state="prepared"` authorizes the caller to proceed to its separate render
boundary. The result contains an opaque `context` handle plus detached `snapshot`,
`record` and `fence` projections. `snapshot.scope` additionally includes the
verified hosted service ID. Mutating returned objects cannot change the private
handle or persisted attempt. The provider must call prepare before requesting
render and must not call a second freeze/prepare in its rendition adapter.

The session attempts at most one freeze per photo. A failed admission may retain
#0065 outbox history or an unconfirmed #0095 write; it returns no context handle
and grants no render, upload or retry authority. No rollback is claimed across
the two catalog writes. Existing recovery/repair contracts own reconciliation;
this module does not clear uncertain history or manufacture a successor.

## Confirmation contract

`inspect(handle, now)` rereads the actual attempt, checks the immutable full scope,
selection kind/revision and group array, and returns a detached record/fence plus
snapshot. Foreign handles, closed recovery gates, removed attempts, stale
catalog/activation/identity or lost ownership refuse progress. Updated mutable
checkpoint revisions are allowed without changing the frozen choice.

The normal execution owner advances the actual upload-attempt store through its
existing APIs. This context adds no dispatch permission or checkpoint writer.
A separately constructed store with the same captured ownership dependencies
can supply those operations; their existing fences remain mandatory.

- `bindGroups(handle, now)` derives the direct-upload binding only from an
  acknowledged persisted photo proof and exact returned photo ID. The proof's
  linked Flickr revision must equal the captured verified service revision.
- `confirmGroups(handle, status, document, now)` requires acknowledged catalog,
  photo-proof and group-handoff checkpoints. It passes the complete response to
  #0065, which validates the entire matching 202 against the locked binding and
  exact frozen group set before consuming the matching selection revision.
- `confirmPublication(handle, now)` requires acknowledged catalog, photo-proof
  and durable hosted Album-obligation checkpoints. It derives the two #0065
  publication flags from those records, rather than accepting caller booleans.
  An Album obligation acknowledgement establishes durable responsibility, not
  verified Flickr membership.

#0065 alone owns matching-revision consumption. Later selection edits survive;
confirmation does not reread them as the frozen choice. Group acceptance is not
Flickr delivery or overall publication completion. The execution owner remains
responsible for retirement/choice disposition and any later required handoff.

Handles are activation-local and cannot be reconstructed after restart. Persisted
frozen choices remain in the upload journal, while #0065 retains the immutable
handoff revision in its own outbox. This module exposes no restart replay or
recovery dispatch operation. No #0094 proposed lifecycle behavior is adopted.

## Evidence boundary

The focused actual-Lua integration tests are
`tests/test_publisher_frozen_context.py`, with transactional synthetic SDK
fixtures. The SDK15.3 Windows compiler checks the source syntax. Results and
review references belong in the batch evidence receipt. Target remains Lightroom
Classic15.6 / SDK15.3, major15 only. Source checks establish no native durability,
render qualification, cloud access, real-account authority or production activation.
`PRODUCTION_QUALIFIED` remains false, and the provider remains unregistered.
