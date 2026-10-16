# Group-selection integration review

Date: 2026-10-16. Status: independent source and synthetic Lua 5.1 review of the
disabled candidate. No production composition, native host acceptance, live
catalog operation, provider request, deployment or capability activation was
performed. This review owns only this evidence note; module owners made fixes.

## Authority and conclusion

Architecture `AGENTS.md`, `docs/README.md`, accepted ADR0045/0062/0063,
`docs/plugin-service-contract.md`, `docs/queue-status-api.md` and
`docs/moderator-safety-ui-conformance.md` control. Editable metadata, immutable
recovery, hosted binding/proof and permanent pair protection are distinct
authorities. The accepted two-list interaction and bounded outbox fixture proof
are not reopened by this review.

After the corrections below, no unresolved material source defect was found
within the injected catalog-photo and binding-only existing-public candidate
cores. This conclusion does not claim that a production composition exists.
The binding-only correlation gap found in the first pass is now resolved by
the separately reviewed private outbox described below.

## Reviewed source boundaries

- `GroupSelectionStore.lua:288`, `:306`, `:381` and `:453`: strict whole-document
  validation, exact safe-integer encoding, synchronous private-gate mutation,
  pre-write bounds, exact readback, in-gate revision checks, frozen scope/binding,
  immutable snapshots and equal-revision selection consumption. Retained outbox
  revisions prevent selection-revision reuse after consumption. Storage refusal
  never evicts unresolved work. Confirmed group records retain validated complete
  intent/block projections; a raw HTTP 202 cannot directly consume a selection.
- `GroupSelectionEligibility.lua:29` and `:98`: complete required aggregates,
  exact binding/photo correlation, exhaustive status validation and block-first
  merge. Current membership and all retained intents remain read-only; absence
  does not weaken permanent protection. Failed loading retains diagnostic stale
  prior data without enabling confirmation.
- `SubmissionStatusClient.lua:148`, `:254` and `:335`: closed state/outcome/queue/
  attention/block validation; bounded ordered history traversals; cancellation;
  no partial publication; stabilization from page one; pacing and recommendation
  handling; prior observation, gate revision and intent revision/protection
  regression refusal. The host composition still owns coalescing reads across
  dialogs and fencing concurrently returning operations against its latest model.
- `GroupSelectionController.lua:41` and `:136`: the complete one-through-60 set
  is snapshotted before one backend batch call; existing-public proof is refreshed
  immediately before handoff, with finite observed-age checks. Binding/photo,
  requested order, unique intent identities, states, created flags and matching
  permanent blocks are validated before durable confirmation. Delivery ambiguity
  leaves the immutable handoff unresolved. These injected adapters are not a
  claim of qualified production transport, codec or credential composition.
- `GroupSelectionDialog.lua:13`: the two lists edit only local eligible choices.
  Save/Queue labels reflect the selected count; empty Save is unpublished-only.
  Protected rows remain read-only, positive later membership remains visible,
  observation times are shown and stale saved choices require an explicit local
  correction. Cancel performs no durable write.

All module paths above are under `clients/lightroom/FGA-LrC15.lrplugin/`.

## Findings resolved during review

1. Default Lua 5.1/dkjson number formatting could round otherwise safe integer
   catalog IDs/revisions while exact-string readback still matched the rounded
   representation. The store now uses dkjson's documented custom encoder with
   exact integer formatting; high-value round-trip/exhaustion regression passes.
2. Immediate double history traversal could exceed the real status reader's
   burst-20/refill-one-per-five-seconds allowance. Reads are now paced with
   cancellable injected SDK sleeps; the second initial traversal respects the
   first traversal's 15/60-second recommendation. The 1,201-intent/26-read token
   simulation passes. This is offline scheduling evidence, not native timing.
3. An older complete status result could replace a newer prior display when
   intent revisions were unchanged. Prior observed-time and per-scope gate
   revision/state regressions now fail closed, preserving the stale prior model.
4. Saved IDs that became ineligible were hidden in the selected set and could
   disable confirmation without a way to remove them. The dialog now identifies
   those exact saved choices and offers an explicit local clearing action. It
   changes no membership, intent or permanent block and Cancel still writes nothing.
5. The dialog omitted observation labels and the positive membership fact on a
   protected pair. It now displays refresh/membership/status times and an added
   read-only membership statement alongside the permanent-protection copy.
6. Non-finite local proof-clock values could pass comparison checks. The controller
   now rejects non-finite, backward and expired observations before a batch call.

## Binding-only integration follow-up

The first pass identified that `GroupSelectionStore` requires an actual
`LrPhoto`, service/collection IDs and UUID, while an eligible existing public
photo may have none. `ExistingPhotoGroupStore.lua` now supplies a separate
catalog-private `existingPhotoGroupOutboxV1` property without accessing an
`LrPhoto`, publication record, editable selection metadata, Album or publish
service. This is private recovery bookkeeping, compatible with the accepted
queue-only boundary; it does not fabricate a catalog photo association or amend
ADR0045's editable metadata schema.

Its exact scope (`ExistingPhotoGroupStore.lua:199`) is the installation ID,
server binding ID, exact Flickr photo ID, linked revision and preserved binding
source kind. Frozen scope/binding inputs, current installation/link and active
catalog checks before/inside/after the private gate (`:302`), guarded local
revision replacement (`:352`), immutable records, full acknowledgement validation
and exact readback (`:399`) retain the same failure boundaries as the photo store.
The property has finite record/byte bounds and never evicts unresolved work.
These local identity checks are correlation fencing, not hosted authentication.

Two follow-up defects were resolved:

- Existing-public intake may reuse an upload-origin binding whose preserved
  `sourceKind` remains `fga_direct_upload`. Provenance alone could therefore
  bypass the controller's final proof branch. The trusted constructor now accepts
  explicit `{workflow="existing_public_photo"}` context (`GroupSelectionController.lua:94`),
  and that workflow always refreshes exact-photo proof before handoff (`:148`)
  without rewriting provenance. Unknown context fails closed. The actual
  existing-public composition must supply this context; the original publisher
  bound path retains its distinct behavior.
- A newer acknowledged record can coexist with an older unresolved record.
  Looking only at the latest editable choice hid the older recovery work after
  restart. Both stores now expose bounded exact-scope read-only `listPending`
  (`ExistingPhotoGroupStore.lua:386`, `GroupSelectionStore.lua:440`). Reconstructed
  store tests discover the older prepared record even after the newer record was
  acknowledged. Enumeration performs no submission or automatic replay; recovery
  still requires explicit reconciliation of the immutable original handoff.

## Qualification limits

Production registration/metadata declaration, ordinary Album scope resolution,
fixed-origin credential/strict-codec transport adapters, task lifetime and
latest-request publication fencing remain composition responsibilities. The
source candidate does not qualify SDK POST redirects, allocation, actual private
catalog transaction/crash behavior, restore/copy recovery or upload replay.
The separately accepted #0029 bounded fixture proof remains valid within its
recorded scope; no repeat of it is requested here. Retained records have finite
bounds and no eviction/compaction policy; explicit full-storage refusal remains
the truthful behavior until a reviewed retention rule exists.

## Verification and exact reviewed source

Independent frozen-environment commands passed with actual Lua 5.1:

- `uv run --frozen python -m unittest discover -s tests -p test_group_selection_*.py`:
  43 passed, zero failed after the binding-only/proof follow-up.
- `uv run --frozen python -m unittest discover -s tests -p test_existing_photo_group_store.py`:
  16 passed, zero failed, including actual controller/batch-client composition
  with no `LrPhoto`, preserved upload-origin provenance and pending enumeration.
- `uv run --frozen python -m unittest discover -s tests -p test_submission_status_client.py`:
  13 passed, zero failed.

These tests use synthetic catalog/HTTP/SDK adapters. They do not prove the live
host or hosted provider. The primary agent owns additional cross-module
composition verification and final build provenance.

SHA2-256 digests of the reviewed module files:

| File | Digest |
| --- | --- |
| `GroupSelectionStore.lua` | `a6a287d26fc36658ac6cdadfe74901cd1c958aedfb584d3d0c9f83f3436cc0e9` |
| `ExistingPhotoGroupStore.lua` | `09961a17406d1d3c7aa69bbe84af1713490e897b5d9e91409674ee0fc00b0dcf` |
| `GroupSelectionEligibility.lua` | `60d572e6b0668899b215f9b93e9f01fb5d0c0a7a57084b2b524d351be305134d` |
| `SubmissionStatusClient.lua` | `ba79c2446e0bd6ade03d70993fb2ad961529b57809ab4e7fa9b6af1330f568f3` |
| `GroupSelectionController.lua` | `79a3e058c3707cff3c2da5a1c9eba2975c21f7c1b1a92e59c3dd72d178b8b7c1` |
| `GroupSelectionDialog.lua` | `54bcd089e4254ebc22407e5ff81d3c7de4edc1a1f1f2f04695d58dcd0e7e3b2a` |
