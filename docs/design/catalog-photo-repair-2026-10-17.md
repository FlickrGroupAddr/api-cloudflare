# Catalog photo identity repair

Date: 2026-10-17. Implementation evidence for #0104. Dormant source; Lightroom
Classic 15.6 / SDK 15.3 host qualification remains pending.

`clients/lightroom/publisher/PhotoCatalogRepair.lua` implements the documented
post-callback choice from the [#0084 lifecycle investigation](../research/photo-catalog-repair-lifecycle-2026-10-16.md).
The accepted [ADR0011](../../../architecture-design/docs/decisions/0011-catalog-remote-id-and-hosted-proof.md),
[ADR0012](../../../architecture-design/docs/decisions/0012-photographer-reconciliation-after-ambiguous-upload.md)
and [upload recovery store contract](../../../architecture-design/docs/proposals/upload-attempt-recovery-store-2026-10-16.md)
control ordering, identity and retention. This note describes the adapter and
does not define another persistence or hosted wire schema.

## Interface and ownership

Construct with `PhotoCatalogRepair.new(options)`. Options are the captured
`catalog`, `pluginId`, `activationToken`, `activeCatalog`, `currentActivation`,
`isOwner`, SDK-aware `pcall`, actual upload-attempt `store`, and
`readServiceIdentity(service)`. The last callback reads the exact current saved
hosted service ID locally and synchronously; it cannot provision a service or
call hosted verification. The caller must run inside an `LrTasks` asynchronous
task, as the documented SDK enumeration methods require.

`repair(scope, attemptNumber, now)` accepts the actual store's four-field scope.
It inspects and validates the retained attempt before touching remote identity.
The store's read-only `validateCatalogRepair` rechecks its full revision fence
inside the adapter's catalog gate without opening a nested access gate. Missing
or malformed state, a stale fence or changed scope grants no setter call.

The adapter resolves all SDK objects afresh before, inside and after the gate:

- The captured catalog must remain the active catalog, with the same activation
  and dispatcher ownership.
- Exactly one provider-filtered service must match the local service ID, plug-in
  ID and saved hosted service identity.
- `getPublishedCollectionByLocalIdentifier` must resolve the same ordinary
  collection, owned by that exact service; a collection set or smart collection
  cannot pass the checks.
- `findPhotoByUuid` must return the exact current photo object, and the original
  collection must contain it exactly once.
- Exactly one publication-data record must refer to that photo. A duplicate,
  missing record or a different object sharing its UUID stops repair.

No rendition object enters this interface or survives through it. The adapter
never creates an association, changes the collection remote ID, publishes an
edited flag or changes a publish count.

## Ordering and confirmation

Normal returned-ID attempts require the durable `returned_id` record before
catalog repair. Photographer reconciliation additionally requires the durable
acknowledged photo-proof checkpoint. The accepted store's transition rules
continue to enforce catalog-before-proof for normal upload and
proof-before-catalog for photographer reconciliation.

The only SDK setter is documented `LrPublishedPhoto:setRemoteId`. SDK15.3's local
`LrPublishedPhoto.html` reference at its `publishedPhoto:setRemoteId` anchor
explicitly requires a catalog write gate. The adapter uses documented ordinary
`withWriteAccessDo`, timeout five seconds, synchronous mode. A callback expires
when the gate call returns, so a late queued callback cannot write. It performs
no network, UI, task launch, file I/O, sleep or explicit yield.

An existing different nonempty photo remote ID is a conflict. An absent or
empty ID may be set to the exact retained string. A successful executed gate
must be followed by current-scope photo-record readback with that exact ID.
Only then does the adapter ask the store to acknowledge catalog publication
with its fresh fence. Failed or uncertain store acknowledgement remains safely
retryable; a later invocation observes and acknowledges the existing exact ID.

Journal gate acquisition can yield after a successful SDK observation. The
adapter supplies `acknowledgeCatalog` with an exact SDK relationship predicate,
which the store invokes synchronously inside its private gate before changing
the checkpoint and after committed readback. The adapter also resolves the
current relationship after acknowledgement. A stale scalar remote-ID reader
cannot substitute for that exact scoped publication relationship.

`observe(scope, attemptNumber, photoId)` provides a pure current SDK observation,
without a journal gate or mutation. The recovery controller invokes it after
its final potentially yielding journal/link operation before each normal proof
request and before returning a verified result. It returns
`catalog_identity_observed` only for the exact current relationship and ID.
Its SDK readers and local identity callback must be synchronous; a predicate
inside a catalog gate may not yield. These checks prove current observation at
the stated boundary, without freezing later user edits or SDK state.

An already acknowledged local checkpoint still requires fresh catalog
observation. This permits repair after Undo or resumption while retaining the
original ID and proof. The ordinary gate's Undo entry and a readback observation
are not native abrupt-stop durability evidence.

Results use sanitized `state` values. `catalog_acknowledged` is the successful
checkpoint result. `catalog_repair_pending`, SDK scope/publication-data failures,
`remote_id_conflict`, or a store refusal grant no downstream operation. A caller
persists applicable attention through the existing store; the adapter neither
discards the retained authorization/ID nor retries any upload, proof, Album or
group operation. A committed reconciled proof survives every local failure;
retry performs the local write/observation only.

## Verification and remaining qualification

Dedicated SDK-fake tests exercise the actual adapter and actual store, including
both ordering paths, restart, stale scope and fences, absent/duplicate
publication data, conflicts, gate exceptions/queued returns and local retry.
SDK15.3's Windows compiler checks Lua syntax. The parent integration receipt
records focused results and independent review.

The source is dormant and does not register a provider. No actual Lightroom
catalog, rendering, upload, provider, credential or network operation was used.
The #0084 New-photo publication-data availability and native Published/Modified
classification gaps remain explicit. Missing records stay pending until that
separately authorized host branch is qualified; the documented alternative
`addPhotoByRemoteId` is not selected here. Native persistence, abrupt-stop,
restored-catalog and release gates remain separately owned.
