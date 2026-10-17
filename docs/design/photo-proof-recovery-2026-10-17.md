# Same-tuple photo-proof recovery

Date: 2026-10-17. Ticket #0104. Dormant implementation evidence; no native or
network qualification, provider activation, upload, or real catalog operation.

`clients/lightroom/publisher/PhotoProofRecovery.lua` composes the accepted
[#0083 store](../../../architecture-design/docs/proposals/upload-attempt-recovery-store-2026-10-16.md),
[ADR0011 normal proof](../../../architecture-design/docs/decisions/0011-catalog-remote-id-and-hosted-proof.md),
[ADR0012 reconciliation](../../../architecture-design/docs/decisions/0012-photographer-reconciliation-after-ambiguous-upload.md),
and [plug-in/service wire sections 5.5–5.6](../../../architecture-design/docs/plugin-service-contract.md).
Those sources own ordering, identity and HTTP semantics. The existing
[#0084 lifecycle evidence](../research/photo-catalog-repair-lifecycle-2026-10-16.md)
and [catalog repair adapter](catalog-photo-repair-2026-10-17.md) own post-callback
local repair. This controller introduces no recovery endpoint or storage field.

## Controller boundary

Construct `PhotoProofRecovery.new` with these injected values:

- `store`: the actual `UploadAttemptStore` instance, configured for the captured
  catalog, activation, exact current photo object and elected scope owner.
- `catalogRepair`: the `PhotoCatalogRepair` instance for the same store/catalog;
  its `repair(scope, attemptNumber, now)` resolves publication data anew.
  Its `observe(scope, attemptNumber, photoId)` performs a pure current SDK
  relationship observation without entering a store/catalog gate or yielding.
- `pcall`: SDK-aware protected execution, returning ordinary Lua protected-call
  results, including every returned transport value.
- `proofTransport`: absent by default. An explicitly supplied adapter has
  `capabilities.uploadPhotoProof == true` and
  `request(method, path, encodedBody, maxResponseBytes) -> rawBody, sdkHeaders`.
- `linkedFlickrRevision()`: the positive exact current linked-account revision;
  it is checked before the request and again after every yielding boundary.
- `proofAttempts`: an integer from one through three, default one. For more
  than one attempt, `backoff(seconds)` is mandatory and returns true only after
  completing the requested delay; delays are one second, then two seconds.

`resume(scope, photo, attemptNumber, now, retryAttention)` is the sole operation.
All scope fields are captured by value. Attempt number chooses an existing
record; there is no admission, upload-result invention, photographer-selection,
new-copy, rendering or image-upload method. The explicit selected tuple must
already be durably committed by `selectKnownPhoto`. Missing original
authorization correlation remains attention; a catalog ID alone cannot supply it.

The transport accepts only the generated accepted PUT path and the closed
`schemaVersion`/`flickrPhotoId` request. It owns installation authentication,
fixed-origin enforcement, redirect refusal, cancellation, duration and bounded
body consumption. This module does not read credentials or duplicate #0101's
signing client. The response-size argument is a required adapter limit, while
the controller also checks the returned bytes. A capability flag is an
injection contract, not evidence that a real adapter has passed qualification.
The synthetic-only `SharedReadTransport.offline` constructor is not used.
No native transport is selected or made available by this module.

## Ordering and restart

Normal returned-ID recovery freshly repairs/observes the local remote ID and
confirms `catalogPublication` before PUT `photo-binding`. A failed local write
leaves `catalog_write_pending` without making the proof request. An earlier
catalog acknowledgement is never substituted for a fresh observation: Undo,
deletion, membership changes and foreign IDs remain the adapter's guarded
local repair/refusal cases.

Photographer reconciliation PUTs `ambiguity-resolution` for the persisted
authorization/photo tuple first. Only a fully validated response followed by
confirmed `acknowledgeProof` permits catalog repair. An unconfirmed local proof
acknowledgement grants no catalog write; it may have committed, so reopening
rereads the original record. A lost HTTP acknowledgement safely repeats the
same tuple. Neither path requests a fresh authorization or replays image bytes.

An acknowledged proof always skips HTTP and resumes only local catalog repair.
If that repair fails, `reconciled_catalog_write_pending` retains the durable
hosted acknowledgement and exact photo ID. Once both checkpoints are confirmed,
`hosted_photo_verified` means only photo proof and local remote-ID repair.
Album and group obligations remain independent pending work; this controller
does not retire the full record, consume group choice, or claim complete publish.
It retains no rendition or callback-only object.

## Strict response and callback fences

Success requires HTTP200 or201, a bounded SDK header array, one JSON content
type, `Cache-Control: no-store`, no duplicated controlling header, matching
optional content length, and exact resource `Location` for201. Any supplied
Location must equal the original request path. Header count is at most64,
individual field/value lengths at most256 bytes, and combined bytes at most4096.

The raw body is at most4096 bytes and uses the existing strict
`UploadAttemptCodec`: invalid UTF-8, duplicate/escaped-duplicate keys, unknown
fields, malformed JSON and numeric lexemes that round into integer revisions
are refused before decoded values are trusted. The closed seven-field accepted
binding must match the exact photo and captured linked revision, use bounded
binding identity, positive safe verification revision, accepted source kind
and a valid bounded UTC timestamp. All three accepted source kinds are allowed:
the hosted common identity may predate this authorization or resolution.
Only the four-field store acknowledgement projection is passed to the store;
raw response bytes and headers stay transient.

Every request, backoff and linked-revision callback is followed by a fresh store
inspection with the original exact store/gate/attempt/record/photo-metadata
fence. Changes, including unrelated shared-store writes, stop this invocation
without acknowledgement or automatic rebasing. A later invocation may reread
and repeat only the immutable tuple. The store and catalog adapter additionally
fence catalog object, activation, ownership and exact photo/relationship identity
at their gates/readbacks. Reentrant use of one controller returns
`recovery_busy`; another instance receives no extra ownership authority.

Journal gates and link callbacks can yield after the catalog adapter returns.
Immediately before every normal proof invocation, including retries, the
controller therefore invokes the adapter's pure `observe` after its last
yielding operation. Every `hosted_photo_verified` result likewise follows a
final pure observation after the last private-store inspection. A disappeared
relationship, emptied/changed remote ID or foreign/current scope prevents that
normal PUT or terminal result and retains the local catalog-pending outcome.
Reconciliation still performs its hosted commit before any catalog write;
after acknowledgement, the same final observation guards its local-only resume.

## Budget exhaustion and truthful attention

HTTP400/401/403/404/409/422 stop immediately. Retryable transport/dependency or
invalid-success responses use only the configured finite attempt budget with
injected bounded backoff. Cancellation/failed backoff stops the budget too.
No default sleep, network retry framework or hidden scheduling is supplied.

Exhaustion/refusal uses existing `checkpointNeedsAttention(photoProof)` and
preserves every correlation, catalog remote ID and acknowledged checkpoint.
The outcome is `uploaded_proof_needs_attention` or
`reconciliation_needs_attention`, with a fixed sanitized detail category and
`attentionPersisted`. If the attention write is unconfirmed, `storageState`
reports that limitation; no persistence claim is made. This caller must retain
that visible failure rather than treating it as success. The current controller
also latches the stopped budget in memory even if that attention write fails.
After a process restart only successfully persisted state is recoverable;
unavailable storage cannot provide an invented durable exhaustion guarantee.

After confirmed attention, automatic restart does not reset the budget. Only
an explicit later `retryAttention == true` runs another bounded verification
budget for that same persisted tuple. This uses no new schema fields and
implements ADR0011's deliberate verification retry. An unavailable transport
returns `proof_transport_unavailable` without claiming hosted proof. Scope,
storage and revision refusals remain visible and grant no dependent operation.

## Verification boundary

The dedicated `tests/test_photo_repair_recovery.py` and
`tests/photo_repair_recovery_fixture.lua` synthetic fixture
execute these actual new modules with the #0095 store, covering normal versus
reconciliation ordering, lost acknowledgement/restart, local-only repair after
hosted commit, strict malformed responses, bounded failure and explicit retry,
missing correlation, link changes and stale catalog/revision callbacks. The
batch evidence receipt records focused results and fresh independent review.

SDK15.3 parsing is a source check. Actual LrC15.6 gate semantics, publication-data
availability, Undo behavior, native transport bounds, abrupt stop and restored
catalog qualification remain separate gates. This implementation does not
qualify the native Published transition or authorize real Flickr/catalog writes.
