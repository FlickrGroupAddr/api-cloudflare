# Dormant first-photo album materialization

Date: 2026-10-17. Ticket: #0111. Offline implementation note; no hosted or
provider qualification is claimed.

`src/album_materialization_worker.ts` exports `consumeAlbumMaterialization`.
The caller must supply a transport factory and explicitly set
`FGA_ALBUM_MATERIALIZATION_ENABLED` to `1`. No Worker route, scheduled entry,
Durable Object registration, credential reader or default network constructor
is installed by this module.

Authority remains the accepted canonical
[album-write reconciliation contract](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/album-write-reconciliation.md),
[album admission wire](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/proposals/album-binding-photo-association-wire-2026-10-16.md)
and [status/create repair supplement](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/proposals/album-status-create-repair-wire-2026-10-17.md).
This note records implementation boundaries; it does not redefine their policy.

- The owning D1 store supplies the immutable first photo and current claim,
  link/grant, gate, title and lifecycle fences. Earlier installation credential
  versions do not authorize background work.
- A fresh strict complete first-photo context read precedes request preparation.
  Preparation fixes the hosted title and photo before the dispatch transaction.
  A racing title revision makes that marker fail instead of sending stale text.
- The marker commits the exact pre-context set before the one-shot prepared
  create handoff. The database retains marked ambiguity across restart/takeover.
- A complete create ID/URL is retained on the attempt before exact owner and
  fresh first-photo membership proof. Failed proof retains candidate evidence
  without committing remote identity. One transaction commits immutable identity and satisfies
  the primary obligation; no primary `addPhoto` operation exists.
- A malformed/unknown response, post-marker exception, failed proof, stale
  result or unconfirmed result commit returns outcome unknown. A documented
  adapter-classified rejection may commit rejection. Both retain history and
  permit no further create in this slice. There is no zero-byte replay path.
- Each invocation has a 45-second monotonic budget, including awaited database
  work and cleanup. Current database authority must retain more than a
  10-second outbound-operation deadline plus 5-second commit margin before
  another call begins. Result recording and final commit require the commit
  margin. The database independently fences its 45-second invocation deadline
  and 60-second lease; expired evidence cannot authorize dispatch or results.
- Local cleanup cannot change a durable result. Unmarked failures release only
  their own fenced claim; they never manufacture remote success or identity.

The transport is an explicitly synthetic dependency seam. Future production
composition must retain the shared Flickr rate budget, accepted fault gates,
bounded reads and current authority checks. The feature flag alone is not
permission to add a real provider, read credentials, register scheduling or
perform a Flickr write. Later-photo attachment, ambiguity repair endpoints,
remote title synchronization and the accepted lifecycle wire remain separate work.

Focused executable evidence is in `tests/album_materialization_worker.test.mjs`
and the companion store/transport suites. Parent integration records aggregate
checks and fresh independent review. Offline SQLite evidence does not establish
hosted D1 behavior or a Flickr/Lightroom qualification pass.
