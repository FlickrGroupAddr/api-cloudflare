# Bounded upload-attempt catalog store

Date: 2026-10-17. Implementation evidence for #0095; dormant, unregistered source.

The new `UploadAttemptStore.lua` and its private `UploadAttemptCodec.lua` implement
the accepted [#0083 local-storage contract](../../../architecture-design/docs/proposals/upload-attempt-recovery-store-2026-10-16.md).
That accepted contract owns the policy and limits. This note publishes the exact
executable version-1 projection and adapter responsibilities. It grants no
networking, rendering, native host test, abrupt-stop test or production activation.

## Executable local schema

`uploadAttemptRecoveryStore` is one catalog-private JSON string, separate from
`groupAdditionOutboxV1` and `existingPhotoGroupOutboxV1`. Root fields are exactly
`schemaVersion`, `storeRevision`, `nextAttemptNumber`, `recoveryGate`, `attempts`.
The recovery gate has exactly `state`, `gateRevision`, `confirmedAt`. The property
is absent only for first ordinary initialization; its first observed revision is
1, with next attempt 1 and gate revision 1. The first committed admission writes
store revision 2. No allocated counter resets or wraps.

The `recordFields` allowlist in the module is the executable full-record schema:

- Identity: `recordKind`, `attemptNumber`, `recordRevision`,
  `predecessorAttemptNumber`, `publishServiceLocalId`, `fgaPublishServiceId`,
  `publishedCollectionLocalId`, `photoUuid`.
- Frozen choices: `selectionRevision`, `selectionKind`, `flickrGroupIds`.
- Correlation/result: `fgaUploadAuthorizationId`, `uploadPhase`,
  `dispatchMarkedAt`, `flickrPhotoId`, `resultKind`.
- Independent checkpoints: `photoProof`, `catalogPublication`, `albumObligation`,
  `groupHandoff`.
- Display/recovery: `createdAt`, `updatedAt`, `attentionCode`,
  `recoveryDisposition`, `recoveryConfirmedAt`.

Every listed record field is present; inapplicable values are explicit JSON null.
Local service/collection IDs are exact positive safe integers. UUIDs follow the
existing 36-character hexadecimal UUID validator. Opaque IDs retain the existing
selection/binding validator: 1–128 ASCII bytes, first alphanumeric, remaining
alphanumeric or `@._:-`. The accepted 256-byte outer ceiling does not widen those
controlling validators. Group IDs must already be unique and bytewise ordered;
the store refuses unsorted input rather than changing the frozen set silently.

The contract's exact checkpoint fields are implemented as closed objects.
`state` is `pending`, `needs_attention` or `acknowledged`; only acknowledged
checkpoints carry a non-null `acknowledgedAt`. Pending checkpoints carry explicit
nulls for unknown correlations. The local Album target's service/collection/photo
key is frozen at admission. The hosted Album binding ID/revision may both be null
before first upload/proof creates that binding. If already known, the ID remains
immutable while the observed hosted revision may advance under accepted #0088.

The exact `publishedPhotoCorrelations` photo field has `schemaVersion`,
`metadataRevision`, `entries`. A present field requires positive metadata revision;
an absent field supplies revision 0 only as the initial compare-and-set value.
Each entry uses precisely the contract's completed-entry allowlist, implemented
by `entryFields`; no group response bodies or arbitrary payloads are retained.
Ordering is local service ID, collection ID, hosted service ID, then photo UUID.

All JSON is validated for UTF-8, grammar, escaped duplicate keys, paired Unicode
surrogates, version, field allowlists, array shape, counters, ordering and
phase/null combinations before use. Exact mathematical numeric-token validation
precedes dkjson's double conversion, so fractional `1.00000000000000001` cannot
round into an accepted revision. Mathematically integral decimal/exponent forms
remain supported within the exact safe range. Decoder failures never initialize an empty
replacement. Exact integer encoding uses dkjson's documented custom encoder,
matching the existing group catalog store convention.

## Adapter and transition API

Construct the store with the captured catalog object, plug-in object, activation
token, current catalog/activation callbacks, per-scope `isOwner`, SDK-aware
`pcall`, and `readRemoteId(photo)`. `isOwner` is a current in-memory dispatcher
ownership predicate, with no lease expiry. `readRemoteId` reads only the exact
current published-photo relationship. It must not perform network I/O. The
store also requires `catalog:findPhotoByUuid` to return the exact supplied photo
object; a UUID match in another catalog/copy does not suffice.

Every mutating method requires the full fence returned by `inspect`: exact
`storeRevision`, `gateRevision`, `attemptNumber`, `recordRevision`,
`metadataRevision`. Null attempt/revision means no target record. Methods never
retry a conflict internally. Reread and validate the original frozen inputs
before a caller retries a safe local operation.

| API | Confirmed behavior |
| --- | --- |
| `prepare` | Freezes exact scope/choice/local Album target before render; permits null hosted Album correlation and checks existing remote ID/correlation, all retained scope records, counts and completion reservations. |
| `authorize` | Assigns the server correlation once; refuses reuse of a retained authorization ID. |
| `markDispatch` | Persists the never-cleared marker and returns one activation-local permission only after exact readback. |
| `takeDispatchPermission` | Burns that permission before rechecking its exact marker fence; returns `invoke_once` at most once. Neither inspect nor reopening can create a permission. |
| `recordResult` | Stores a caller-validated definitive returned ID, documented no-success rejection, or unknown outcome. The store does not classify Flickr responses. |
| `cancelBeforeInvocation`, `successor` | Preserve nondispatch evidence; a successor atomically retains its predecessor and receives a fresh attempt number. New-copy mode requires explicit per-photo confirmation and retains possible-upload predecessors indefinitely. |
| `selectKnownPhoto` | Stores the exact photographer-selected ID and original tuple before idempotent ADR0012 resolution. The caller must use the accepted endpoint/verification; missing endpoint correlation remains attention. |
| `acknowledgeCatalog`, `acknowledgeProof` | Normal returned-ID flow requires catalog acknowledgement before hosted proof. Photographer reconciliation requires hosted proof acknowledgement before catalog acknowledgement. |
| `acknowledgeAlbum` | After photo proof, matches the frozen service/local-collection key, current link and exact photo binding; establishes an unknown Album binding or preserves its known identity, accepts a nonregressing hosted revision, and stores only a closed validated natural-key acknowledgement. |
| `acknowledgeGroups` | Validates every transient item against the immutable group set and original proof binding/revision before persisting the compact count/boolean acknowledgement. |
| `checkpointNeedsAttention` | Marks an applicable pending checkpoint with a fixed sanitized category; never downgrades an acknowledgement. |
| `retire` | Requires every applicable acknowledgement and caller-confirmed choice disposition; atomically upserts the exact photo correlation and removes only that full record. Both serialized values require exact readback. |
| `retireNonDispatch` | Requires reported failure/cancellation and an explicit caller assertion that no recovery dependency needs the safely terminal record. Possible-photo records are always refused. |
| `enterRecovery`, `recordMissingHistory` | Persist history-untrusted state/attention without inventing lost authorization, dispatch or group choice. A failed recovery write keeps the activation's memory gate closed. |

Each method's `state` is its result. Only a successful confirmed result permits
the explicitly named dependent operation. `storage_unavailable`,
`write_unconfirmed`, `revision_conflict`, malformed-state refusal, and capacity
refusal grant none. An unconfirmed write may already have committed; reread and
classify it. Never equate an unconfirmed dispatch marker with no dispatch.

Album acknowledgement additionally requires transient `fgaPublishServiceId`,
`localCollectionIdentifier` and `linkedFlickrRevision` evidence from the validated
#0088 binding. The local collection identifier is its exact lossless decimal
string. These fields are checked against the frozen local target and current
photo proof and are not added to the persisted checkpoint schema. An existing
non-null photoset identity cannot be replaced. A newer binding revision is valid
because accepted admission/lifecycle/materialization transactions advance it.

The adapter must supply already-validated accepted response projections and
explicit owner recovery decisions. Passing raw HTTP status, an arbitrary body,
or a boolean derived from a timeout is insufficient. `retire`'s choice disposition
is the caller's confirmation that an exact selection revision was consumed,
or a newer revision preserved, or the original selection was absent. This store
does not edit `groupAdditionSelections` or implement a provider.

Ordinary reads and mutations use one synchronous private gate with timeout 5 seconds.
The #0104 `validateCatalogRepair` exception is read-only and requires the caller
to hold the synchronous ordinary catalog write gate. It revalidates the exact
full fence and current publication relationship without nesting a private gate;
it grants no permission for later writes after that caller gate ends.
Late queued callbacks are fenced closed after the gate returns. The callback
does no render, network, UI, file I/O, sleep, task launch or yield. Active catalog,
activation, ownership and exact photo object are checked before entry, inside
the callback and after return. Exact readback covers both properties even when
one was not changed. A catalog switch never redirects a late result.

## Bounds, retention and recovery

The accepted limits are constants in the module: 256 full records, 65,536 bytes
per record, 33,554,432 bytes for the shared property; 256 entries per photo,
16,384 bytes per entry and 8,388,608 bytes for that photo field. Before admission,
the store counts both existing entries and distinct unfinished per-photo scope
reservations. Fixed maximum record/entry reservations plus root overhead fit
the accepted property budgets; growing checkpoints cannot consume another
attempt's reservation. There is no expiry, LRU eviction or clear-history API.
An unresolved predecessor remains a full record while its successor progresses.

Ordinary reopening uses the accepted current-catalog assumption. A surviving
dispatch marker is classified unknown even before a classifier mutation. Known
or suspected copy/restore requires `enterRecovery` before new publication. The
gate persists and has no blanket unpause operation. An observed remote ID without
matching completed or active known-photo correlation also enters recovery and
persists the reason category through the gate/classification. Malformed shared
state closes the in-memory gate without overwriting it; malformed photo metadata
blocks that photo.

An older restored prepared/authorized record cannot grant dispatch or safe
cancellation in recovery. Per-photo selected-known-ID reconciliation preserves
the absence of a lost marker; explicit new-copy recovery retains the original
uncertainty. Missing history gets `history_attention`, unknown selection and no
invented authorization/marker. A history-attention record cannot retire as a
successful upload because its original group choice remains unknown. Unrecognized
history loss remains the accepted operational limitation.

## Accepted initial obligation observations

Terry accepted the [#0092 status wire](../../../architecture-design/docs/proposals/album-status-create-repair-wire-2026-10-17.md)
on 2026-10-17. Its exact `waiting_for_album` and `attachment_pending` states now
join the three accepted reconciliation states in the strict checkpoint and
completed-correlation vocabulary. Waiting retains a null photoset identity;
attachment pending and verified membership require a non-null identity. Existing
reconciliation/attention observations may retain null or committed identity.
Both full-record and compact-metadata validation enforce these combinations.

Acknowledging durable hosted responsibility permits retirement after every other
applicable checkpoint and choice disposition succeeds. It does not assert album
membership: the compact entry retains the exact hosted state and nullable ID.
Admission success alone still supplies no state or membership evidence. The
adapter must validate the closed hosted binding/obligation/status projection and
its exact natural key before passing the scoped acknowledgement. Missing,
malformed, uncertain or foreign evidence leaves the local checkpoint pending
and the full record retained. No network operation or schema field was added.

## Verification and qualification boundary

`tests/test_upload_attempt_store.py` executes the actual modules in Lua5.1 using
Lupa 2.8 and the dedicated transactional synthetic fixture. It covers all store
mutations with callback write failure, abort/queued/timeout, stale/global/photo
revisions, marker readback races, catalog/activation/ownership switches, combined
retirement rollback and both readbacks, malformed/duplicate/UTF-8/version/null
refusal, exact integer bounds, 256/257 admission, photo reservations, maximal
60-group serialization, and known/absent/older copy-restore classification.

The SDK15.3 Windows compiler parses the two modules and Lua fixture. Python
validation uses unchanged pinned uv0.12.5, `uv run --frozen`, Ruff and Pyright.
The parent evidence receipt records final results/hashes and independent review.

These are offline implementation checks. Native capacity, actual combined-gate
rollback/atomicity, abrupt-stop survival and restored-catalog observations remain
the separately authorized #0125/#0127/#0136 gates. The dormant metadata descriptor
is registered only as a source definition; `Info.lua` still does not activate
the provider. No real catalog, credentials, rendering or Flickr operation was used.

## Independent review and handoff

Independent High review reproduced and then verified corrections for premature
hosted Album identity/revision freezing and fractional number lexemes rounding
into accepted integer revisions. The corrected store admits an unbound local
Album without fabricating hosted identity, validates post-proof scoped correlation
and allows legitimate hosted revision advances. Numeric checks precede lossy
JSON decoding. Final verification passed 39 actual Lua tests, independent scope/
retirement probes, 10,005 exact-decimal comparisons and SDK15.3 parsing.

The #0092 acceptance resolved the initial-state vocabulary dependency. The
bounded follow-up adds focused positive acknowledgement/retirement regressions,
exact scope/proof/ID refusal checks and full/compact reopen validation. Fresh
independent High review and the parent's integration receipt own the final
handoff. Native qualification remains separate as described above.
