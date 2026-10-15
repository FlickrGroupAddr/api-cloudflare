# Group selection and submission readiness

Date: 2026-10-15. Status: implementation planning and source audit, not a new
architecture contract or production conformance result. No UI implementation,
production activation, hosted mutation, or live Flickr request is included.

Current owner-reported host target (2026-10-15 screenshot): Lightroom Classic
15.6 Release, Camera Raw 18.7, build `202609251514-f839cde9`. New host acceptance
must use that installed target. Earlier 15.5.1 host evidence is historical and
must not be carried forward as 15.6 qualification.
Terry also rechecked Adobe Developer Console on 2026-10-15 and supplied screenshot
confirmation that its latest available SDK remains 15.3 (April 2026).

## Authority and review prerequisite

Read the implementation and architecture `AGENTS.md` and architecture
`docs/README.md`. Accepted authority is architecture
`docs/plugin-service-contract.md` (local selection, Phase 6, idempotency, status),
`docs/decisions/0045-use-a-library-modal-and-photo-metadata-for-group-selection.md`,
`docs/existing-public-photo-intake.md`, `docs/queue-status-api.md`, and
`docs/moderator-safety-ui-conformance.md`. Paths below are repository relative;
architecture references are explicitly identified.

Implementation of the selection/submission UI remains contingent on completion
of the separate native mockup review. Existing-photo integration also requires
the existing-photo workflow. This document makes later implementation bounded
and testable without treating readiness work as satisfaction of those gates.

## Verified source inventory

| Evidence | Verified fact and implication |
| --- | --- |
| `clients/lightroom/GroupSubmissionClient.lua:20` | `submit` validates binding, safe integer revision, dense unique selection, and canonical credential before encoding. |
| Same file, lines 25–40 | One through 60 exact IDs; duplicates, holes, extra keys, and over-limit sets fail the complete selection. Existing tests cover these cases. |
| Same file, lines 44–57 | One schema-version-2 body and one injected POST; no proof, persistence, response decoder, retry, or status implementation. A raw 202 response is returned unchanged. This is the adapter's bounded scope, not evidence of complete workflow conformance. |
| `clients/lightroom/FGA-LrC15.lrplugin/Info.lua:1` | Current release registers connection settings only; no selection metadata or menu registration. The batch adapter resides outside this bundle. |
| `src/admission.ts:3` and `:4` | Backend bounds are 60 groups and 15 seconds of existing-photo proof age. |
| `src/admission.ts:36` through `:51` | Binding authority checks owner, credential, link and verification revisions; new existing-photo pairs require current proof; fully existing pairs can pass after proof expiry. Permanent block consistency is guarded. |
| `src/admission.ts:64` through `:90` | One guarded D1 batch inserts only absent pairs, returns retained pairs in request order, and emits at most one best-effort hint after commit. Lost hints rely on durable due rows. Source inspection is not fresh hosted transaction proof. |
| `src/intake_api.ts:37` through `:48` | 202 batch response includes per-pair IDs/state/created/block; admission failures are returned whole, including stale proof classification. |
| `src/submission_status.ts:99` through `:128` | Projection validates state, permanent block, outcome, queue consistency and closed operator actions. No client-side projection counterpart exists in the inspected bundle. |
| Architecture `docs/plugin-service-contract.md:1740` and ADR0045 `:175` | Exact durable outbox mechanism is still an explicit implementation gap. Editable photo metadata is already decided; it must not silently become the recovery authority. |

## Bounded implementation scopes after review

1. **Editable choice and durable recovery contract.** Implement ADR0045's strict
   metadata schema and synchronous private catalog write for one exact
   service/collection/photo scope. Specify the separate durable outbox mechanism
   before claiming restart safety: catalog/installation scope, atomic replacement,
   concurrent callback exclusion, crash detection, corruption handling, version
   migration, and record retention. Keep the mechanism conventional and prove its
   documented SDK behavior. Store only non-secret correlation, original group
   set/revision, binding/proof revisions, handoff phase, and validated returned
   intent identities; do not store credentials or photo metadata in recovery.
   Existing-photo selections without a catalog photo must have an explicit
   outbox correlation rule rather than inventing a catalog authority.
2. **Complete eligibility assembly.** Join the complete writable-group snapshot,
   fresh binding-scoped membership observation and complete binding-filtered
   history. Follow every page and reject changed/incomplete inputs. Apply the
   accepted block-first total presentation rule and reviewed semantic copy.
   Current members and every retained intent remain read-only. Confirmation
   accepts only newly eligible exact pairs; deselection has no removal meaning.
3. **Proof and batch handoff.** Persist the immutable selection snapshot before
   the first handoff. For existing public photos, repeat safe hosted proof
   immediately before a handoff that could add an intent, then use its returned
   revision. Invoke the existing adapter with the complete bounded set once.
   Validate the full 202 body against binding, photo, requested pairs, exact
   unique intent IDs, closed states and authoritative block shape before
   recording confirmed handoff and consuming a matching editable revision.
   Response delivery failure retains an unresolved outbox record. A safe repeat
   of the identical idempotent batch is permitted by the accepted contract;
   it must never become upload replay, direct Flickr mutation, or a new pair set.
4. **Retained per-pair status.** Persist validated identities and assemble each
   complete status traversal before publishing a fresh display. Preserve the
   last good display as stale on failure; use server revisions and observed
   times. Poll only while visible, honor recommended intervals/Retry-After,
   coalesce collection reads, back off on transport/503, restart traversal from
   page one and stop on null recommendation or dialog close. No status action
   schedules work or offers resubmission of a retained pair.
5. **Bundle and host qualification.** Include the adapter and reviewed modules
   in FGA-LrC15; verify only the qualified major. Exercise a synthetic server
   boundary and isolated host fixtures before any separately scoped live intake
   or dispatch gate change. Preserve independent outcomes for multiple photos.

These scopes can become separate implementation cards. Scopes 1–4 need review
acceptance and a settled outbox durability contract; source-level fixtures can
be prepared independently, but do not satisfy host or release qualification.

## Objective acceptance cases

| Case | Fixture/trigger | Observable acceptance |
| --- | --- | --- |
| SEL-01 | Same photo in two albums/services; replace one entry | Exact UUID/service/collection scope changes, other entry preserved, revision increments, IDs bytewise sorted. |
| SEL-02 | Unknown schema, duplicate scope/ID, wrong UUID, 61 IDs, write timeout | No overwrite as empty; no handoff/render; prior record survives; other photos continue. |
| SEL-03 | Explicit none, absent choice, empty existing-photo additions | No batch; unpublished absent choice uses reviewed no-additions report; zero-group publish retains its separate publication/album obligations. |
| OUT-01 | Crash before/after outbox commit, before/after dispatch, after server commit but before response, during confirmation persistence | Restart retains immutable snapshot or known prior record; no silently lost choice, fabricated intent ID, upload replay, or false success. Prove on selected SDK/storage mechanism. |
| OUT-02 | User changes choice while older response returns | Consume only equal selectionRevision; later edit remains. Concurrent callbacks cannot clear or replace each other's unresolved work. |
| PROOF-01 | Initial proof succeeds, delay crosses 15 seconds, mixed existing/new pairs | Whole batch gets stale-proof refusal with no new pair; retain original set, repeat safe proof when required and use new verification revision. |
| PROOF-02 | Link changes, foreign binding, ownership/public visibility loss | Whole selection refused, no intents; retain diagnostic-safe unresolved choice and require correction. Local photo ID never establishes authority. |
| CBA-01 | 1 and 60 eligible groups; 61, duplicate, sparse sets | Exactly one complete POST for valid sets; zero POST/encode for invalid sets. Never slice or pace. |
| CBA-02 | Commit succeeds, response lost, same batch explicitly reconciled | Same intent IDs/current states with created:false; no second intent/attempt, reset, reorder, or new worker hint from duplicate admission. |
| CBA-03 | HTTP 202 malformed body, missing/extra pair, duplicate intent, wrong binding, unknown state/block, contradictory block | Do not consume selection or label confirmed handoff; preserve unresolved record. HTTP 202 alone never means Flickr addition. |
| SAFE-01 | Moderation block or delivery-uncertain block plus current membership absent, moderation disabled, relink/restart | No checkbox, retry, override, clear, or force-send action; retained protected pair remains protected. |
| SAFE-02 | Status/projection page fails, changes generation or is incomplete | Entire handoff disabled; unavailable is distinct from empty. A successful earlier partial page cannot enable additions. |
| STATUS-01 | Every durable state and pause/head/ahead/due tuple | Reviewed copy distinguishes queued/working, added, moderation recorded with unknown decision, attention, cancelled, and permanently blocked uncertain delivery; no percentage, cross-group rank or ETA. |
| STATUS-02 | Multi-page history, transitions between pages, 429/503/transport failure, dialog close | Publish only complete traversal, preserve stale prior display, respect read cadence and Retry-After, no per-intent poll burst and no Flickr call/work scheduling. |
| REPLAY-01 | Timeout/exception after non-idempotent upload or uncertain Flickr add | Never automatically replay upload/add; safe idempotent backend batch reconciliation is separately identified. Status refresh and restart cannot clear permanent suppression. |
| PRIV-01 | Malicious error body/header, credential in thrown text, stale group title, hostile response ID | Logs/copy use allowlisted classifications; no bearer, raw body, photo metadata, or arbitrary upstream text reaches recovery/logs/UI. |

## Security and SDK qualification gaps

Verified: the current adapter accepts an injected relative-path POST and encoder
(`GroupSubmissionClient.lua:53`) and does not fix HTTPS origin, redirect policy,
timeout, response-size bound or yield-safe exception handling itself. The existing
connection code supplies a fixed HTTPS URL/30-second timeout
(`FGA-LrC15.lrplugin/ConnectionCore.lua:10`–`:11`, `:145`) and uses `LrTasks.pcall`
in the owning task (`ConnectionController.lua:134`); raw Lua 5.1 `pcall` cannot
wrap a yielding SDK network call (`ConnectionCore.lua:143`). The batch controller
must meet the same credential boundary through documented SDK calls. Existing
connection success does not qualify POST redirect behavior or error semantics.
The adapter validates credential syntax, not installation identity or authority.

Not yet verified here: current Adobe SDK POST redirect suppression, cancellation,
body limits, response-header/status behavior, durable write/replace guarantees,
catalog concurrent-callback semantics, or crash recovery on supported Windows
and LrC15 builds. Review the newest published Adobe SDK reference and the actual
qualified host before choosing APIs. Do not infer secure entropy from local IDs
or an undocumented UUID module. Existing architecture SDK15.3 references document
the accepted modal and metadata APIs; they do not prove the still-unselected
outbox persistence mechanism. The source audit made no live SDK/provider query.

## Evidence produced in this readiness pass

`tests/test_batch_client_recovery_boundary.py` executes the actual current adapter
in Lua 5.1 with injected synthetic functions: a lost response returns after one
call; post exception propagates after one call; encoder failure sends nothing;
malformed raw 202 body passes through. The last case is deliberately a passing
characterization of a missing integration validator, not a conformance pass.
Future controller tests must assert that such a response cannot consume recovery
state. No existing source file is changed.

Validation on 2026-10-15: all four new characterization tests and all six
existing `tests/test_batch_client.py` cases passed using the repository's frozen
environment (`uv run --frozen --no-sync`). Ruff check with `--no-cache` passed
for the new test. Use `FGA_SOURCE_ROOT` when running the staged test outside the
implementation repository; an isolated writable `UV_CACHE_DIR` avoids the
sandbox's default cache permissions. These results cover injected boundaries,
not actual SDK transport, durable outbox behavior or hosted conformance.
