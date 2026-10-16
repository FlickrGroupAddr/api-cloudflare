# Photo catalog remote-ID repair after the rendition callback

Date: 2026-10-16. Ticket: #0084. Status: documented API choice and isolated
offline source proof; **Lightroom Classic host qualification NOT RUN**.

## Engineering decision

Use a freshly resolved, provider-scoped `LrPublishedPhoto:setRemoteId` inside a
catalog write gate to repair an existing publication-data record after its
rendition callback has ended. This is a documented photo API independent of
the rendition object. Do not retain a rendition or call its
`recordPublishedPhotoId` from a later recovery task. A collection's remote ID
identifies the album and supplies no evidence that this photo was repaired.

This API choice does not change ADR 0011 or ADR 0012's identity, provenance,
ordering, or recovery semantics and requires no new product-contract exception.
ADR 0012 names the rendition method when describing the catalog boundary;
this documented alternate lifecycle implements that same boundary after the
callback, without claiming that a stale rendition remains callable.

The isolated source proof deliberately repairs identity only. It does not clear
an edited flag, change a publish count, create a collection or photo association,
or claim the native **Published photos** transition. `setRemoteId` has no
documented promise to perform that transition. Missing publication-data records
remain pending in this proof rather than being silently manufactured.

There is also a documented engineering option for that missing-record case:
`LrPublishedCollection:addPhotoByRemoteId(photo, id, url, published)`. Its contract
adds a photo to a normal collection and explicitly replaces the ID and URL if
the photo already exists. It can mark the photo published or needing publish.
Use only the existing FGA target collection and original photo, after checking
membership and current identity; never turn repair into arbitrary association
creation. Qualify it in the disposable fixture below before selecting it for
the New-photo case. Its published Boolean must not erase edits made after the
original attempt. This is an SDK lifecycle test gap, not an owner decision to
weaken upload or reconciliation policy.

## SDK evidence inspected locally

The current reference is Adobe SDK **15.3 (April 2026)**, confirmed by Terry's
2026-10-15 Developer Console check recorded in
`docs/research/lrc15-outbox-persistence-boundary.md`. Target host remains
Lightroom Classic **15.6**, not a later major. Licensed reference root:
`C:/Projects/FGA/architecture-design/vendor/LrC SDK/15.3/API Reference/modules/`.
No Adobe documentation or implementation is copied into this repository.

| Local reference and anchor | Relevant documented contract |
| --- | --- |
| `LrExportRendition.html:369`, `exportRendition:recordPublishedPhotoId` | Publishing-only rendition method; marks successful publication, subject to intervening user edits. No documented post-callback lifetime. |
| `LrPublishedPhoto.html:479`, `publishedPhoto:setRemoteId` | Sets the associated photo's remote ID in a catalog write gate, explicitly including the private gate. No rendition parameter or publishing-callback restriction. |
| `LrPublishedPhoto.html:420`, `publishedPhoto:getRemoteId` | Reads this photo's recorded remote ID. |
| `LrPublishedCollection.html:579`, `pubCollection:getPublishedPhotos` | Returns collection publication-data records; requires an `LrTasks` asynchronous task. Does not expressly specify New-photo record availability. |
| `LrPublishedCollection.html:414`, `pubCollection:addPhotoByRemoteId` | Adds or replaces a photo's remote ID/URL and published flag inside a write gate. Smart-collection constraints are explicit. |
| `LrPublishedCollection.html`, `pubCollection:getService` | Resolves the collection's owning service. |
| `LrPublishService.html`, `publishService:getPluginId`, `publishService.localIdentifier` | Provider identity and catalog-local service identity. |
| `LrCatalog.html:1396`, `catalog:getPublishServices` | Optional provider ID filter when resolving persisted service/collection identity afresh. |
| `LrCatalog.html:1801`, `catalog:withWriteAccessDo` | Serializes catalog writes; callback exceptions roll back; successful changes apply after callback completion. Return values distinguish executed, queued, aborted. |

The ordinary write gate is used in this standalone proof because it explicitly
documents rollback and the committed-callback boundary. It introduces an Undo
entry; production recovery must revalidate actual catalog state after Undo and
on resumption rather than trusting a previous local completion hint. The
documented private-gate permission for `setRemoteId` is not itself a new host
persistence qualification. This proof does not replace the separate qualified
outbox persistence boundary.

## Required ordering and failure behavior

Normal: durably record the complete successful upload result and exact Flickr
ID; repair the catalog identity; observe the exact record after an executed
write gate; then request ADR 0011 hosted proof. Retain authorization and ID in
the outbox across every failure. Never move hosted proof ahead of the catalog
boundary simply because repair runs in a later task.

Reconciled: durable photographer-selected tuple; idempotent hosted ambiguity
resolution; durably record the committed acknowledgement; then repair catalog
identity. A failed write remains `reconciled_catalog_write_pending`, with the
same tuple and acknowledgement. Only after observed catalog repair may the
state become `hosted_photo_verified` and normal album/group obligations proceed.

Both paths resolve the persisted catalog, FGA provider, service, collection and
photo UUID afresh. Recheck scope and current remote ID inside the serialized
gate. A different nonempty remote ID is a conflict, never an overwrite. Missing
or duplicate records, moved/deleted photos, gate timeout, exception, queued
return or mismatched readback leave repair pending. Retry only catalog repair;
no image upload, album operation or group admission is permitted by this helper.
Observe the recorded photo ID, never the collection ID, as repair evidence.
Readback proves observation at that time, not process/power-loss durability.

## Isolated offline proof

`proofs/photo_catalog_repair_lifecycle.lua` is not in a plug-in bundle and has no
manifest, registration, menu, network or imports. Its caller supplies the
documented SDK objects and `LrTasks.pcall`. The record flags are synthetic
projections of already-validated durable state, not a production serialization
or trust boundary. Integrating real outbox validation, restart scope resolution,
UI concurrency and completion transitions belongs to #0104/#0103.

`tests/test_photo_catalog_repair_lifecycle.py` runs that actual Lua source under
Lua 5.1 via pinned Lupa. It checks normal and reconciled ordering prerequisites,
exact provider/service/collection/photo scope, conflicting ID refusal, missing
record refusal, synchronous gate results, failure retry and status preservation.
Fakes cannot establish Adobe runtime behavior, disk persistence or native grid
classification. No host, catalog, Flickr, hosted API or desktop action occurred.

Run through the repository's pinned uv 0.12.5 tool runner:

```console
uv tool run --from uv==0.12.5 uv run --frozen python -m unittest discover -s tests -p test_photo_catalog_repair_lifecycle.py
```

## Exact future qualification packet

This checklist is reviewable preparation, not live-test authorization. Terry's
Escape stop remains active. Do not register or load a probe, resume desktop
automation or mutate even a disposable catalog until that stop is cleared and
the exact fixture/build procedure is authorized.

1. Prepare a standalone development provider with a unique toolkit ID and
   incremented build; no networking, credentials, real-account dependencies,
   upload/delete/album/group implementation or production registration. Record
   artifact hash and SDK 15.3 references. Use a new disposable catalog and one
   deterministic local synthetic photo, explicitly identified before writes.
2. Create only this provider's service/normal collection. Put the photo in the
   collection as New, capture service/collection/UUID identifiers and enumerate
   `getPublishedPhotos`. Record whether a publication-data object exists with
   an empty remote ID. No old association spike or Adobe Flickr record is used.
3. Simulate a rendition callback that durably records a synthetic successful
   normal result, then returns without `recordPublishedPhotoId`. A separate
   `LrTasks.startAsyncTask` must resolve the same record afresh and execute this
   repair. No rendition reference may escape the callback.
4. If step 2 exposes a record, measure exact ID, URL, edited flag, publish count,
   New/Published/Modified UI section, target membership, unrelated collection
   state and whether any publish/deletion callback ran before/after setRemoteId.
   No claim that setRemoteId marks Published is a pass criterion.
5. If no New publication-data record exists, retain that failed precondition.
   In the same bounded fixture, separately exercise documented
   `addPhotoByRemoteId` on the already-present photo. Measure duplicates,
   membership, edited status and native classification for published=false and
   a separate unchanged-fixture published=true case. Do not auto-select this
   branch merely to convert a failed measurement into a pass.
6. Repeat with a synthetic reconciled record: no write without the durable
   acknowledgement; the exact acknowledged tuple repairs successfully after
   callback return. A different existing remote ID must remain unchanged.
7. Force an unavailable gate and a synthetic callback exception. Pending state
   must survive; the next task repairs the same tuple, without any network call.
   Make an intervening harmless edit and confirm repair never loses the edit or
   enables a later duplicate upload. Exercise Undo and revalidation.
8. Perform one normal host restart, freshly resolve objects, and observe the
   exact ID and scope. Record this as normal-restart evidence only. Any later
   power-loss claim requires its own scoped evidence.
9. Review sanitized results against every check. Missing records, incorrect UI
   semantics or persistence failures remain explicit failures; no live path is
   enabled until its actual host-dependent branch is qualified. Only fixture
   catalog records may be cleaned up through documented local operations.

## Scope of reused evidence and remaining gap

The completed existing-photo association investigation establishes only that
its own provider-scoped association survived its tested lifecycle. It does not
prove this New-photo repair, a post-rendition write, publication-data availability
or current-host behavior. Collection `setRemoteId` evidence concerns albums.
Neither is repeated or claimed as this ticket's host proof.

The documented alternate photo API is resolved. Offline source proof and the
future fixture procedure are deliverable now; **no post-callback host pass is
claimed**. The remaining dependency for production integration is the exact
New-photo/catalog-state branch qualification under the preserved desktop stop,
plus the separately owned durable recovery implementation. No new exception to
ADR 0011/0012 is proposed.
