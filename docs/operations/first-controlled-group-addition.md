# First controlled production group addition

Status: preparation only, 2026-10-15. **Activation is blocked.** This document
does not authorize production intake, gate resume, dispatch, or a Flickr add.
Terry must select the exact real photo/group pair, review the completed evidence
packet and activation/stop procedures, and explicitly authorize live activation.
Keep submission intake and dispatch disabled and both durable write gates paused
through preparation. Preserve the zero-dispatch baseline; preparation itself
makes no production request or provider mutation.

Implementation ticket #0025 depends on #0024, connecting Lightroom group
selection to submission and status. At the 2026-10-15 end-of-day checkpoint,
0025 is Needs Terry and 0024 is Ready for Work. Terry requested that the next
session on 2026-10-16 begin with this owner-input handoff: review this runbook
and select the exact public photo/group pair. That selection does not authorize
live activation or waive 0024 and exact-artifact qualification. This runbook
does not close either ticket.

## Scope and owner inputs

The intended trial admits one already published photo to one owner-selected
group through the qualified FGA client/backend path. It does not publish a new
photo, remove pool membership, or demonstrate every classifier against Flickr.
Synthetic conformance supplies adverse-result coverage; never provoke real
moderation, ambiguous delivery, or duplicate writes as a test.

Complete this private execution worksheet before requesting activation:

| Input | Value to supply |
| --- | --- |
| Exact Flickr photo ID and public photopage | `<TERRY_SELECTS_PHOTO>` |
| Exact Flickr group ID and group page | `<TERRY_SELECTS_GROUP>` |
| Selection and activation approval references | `<TERRY_APPROVAL_REFERENCES>` |
| Intended Flickr owner; FGA user and installation | `<PRIVATE_VERIFIED_IDENTITIES>` |
| Photo binding and verification/link revisions | `<PRIVATE_BINDING_AND_REVISIONS>` |
| Qualified backend commit, bundle SHA2-256, CI run/receipt | `<EXACT_CANDIDATE>` |
| Qualified FGA-LrC15 version, bundle digest, LrC version | `<EXACT_CLIENT>`; target Lightroom Classic 15.6, Camera Raw 18.7, build `202609251514-f839cde9` per Terry's host update |
| Production configuration/version and migration head/digest | `<FRESH_OBSERVED_STATE>` |
| Gate revisions and credential-generation match | `<SANITIZED_PRIVATE_EVIDENCE>` |
| Previous disabled Worker version and configuration | `<VERIFIED_ROLLBACK_TARGET>` |
| Bounded activation, stop/recovery procedure and rehearsal | `<REQUIRED_BEFORE_APPROVAL>` |
| Trial deadline, observer, one-pair scope and stop triggers | `<EXPLICIT_TRIAL_BOUNDS>` |

IDs are placeholders here. Do not search Terry's catalog or choose a pair on his
behalf. Verify any exact photopage used as public evidence as an unauthenticated
guest at time of use. Keep catalog paths, private metadata, credentials, raw
provider logs and configuration in ignored private evidence. Public receipts
contain only necessary sanitized facts, hashes, times and outcome labels.

## Evidence required before the approval checkpoint

1. **Candidate qualification.** Retain a successful exact-artifact release
   receipt covering all 56 stable cases, all 28 detected mutations with passing
   controls, hosted module/date, storage provenance, restored protections,
   secret-generation reconciliation and confirmed fixture cleanup. Match source,
   migration, contract, artifact and configuration digests. A new dispatch-bound
   implementation requires qualification of its own artifact. Historical passes
   establish precedent, not qualification of modified inputs.
2. **Client path.** #0024 must have reviewable evidence for selecting exactly one
   group, handing off exactly one intent, displaying retained status, and
   distinguishing current membership, local selection, pending moderation and
   uncertainty. Record the actual qualified client version. Do not substitute a
   direct Flickr call, ad-hoc SQL insertion or synthetic client fixture for this
   end-to-end trial.
3. **Fresh stopped baseline.** Observe deployed flags, exact Worker version,
   both paused gate revisions, verified expected owner/write grant and matching
   generation without retrieving or logging token values. Record total dispatch
   markers, attempts, blocks, active intents, unresolved markers and leases.
   A dated zero count is not a current-state check.
4. **Queue census.** Inspect every active partition and its FIFO head, including
   future-due/throttled work and abandoned attempts. Check all users/partitions,
   not only the selected binding. Record counts and a bounded private inventory.
   Truncation, pagination gaps or unexplained work fail this gate. Do not delete,
   cancel or reorder unrelated work to obtain an empty census.
5. **Pair eligibility.** Validate the owner-selected photo through the normal
   existing-public binding path once authorized. Verify the exact pair has no
   permanent block, previous terminal intent, unresolved dispatch or current
   membership. A prior moderation/uncertainty block ends this trial for that pair.
   A previous successful add/current membership is a duplicate outcome, not
   evidence of a new live addition.
6. **Recovery readiness.** Retain the disabled Worker/configuration rollback
   target, pretrial D1 recovery point and post-checkpoint protection reconciliation
   plan. Rehearse stop and recovery against disposable fixtures, including a
   marked in-flight attempt, duplicate wake and process loss. Record the exact
   executable procedure and observed bounds before Terry reviews activation.

The 2026-09-18 compatibility-date record identifies CI run 35381025422 and the
group-discovery production receipt as the later historical qualification baseline.
The original read-only promotion and September 14 release receipt are historical;
do not copy their version IDs or digest into the trial worksheet as current facts.

## Source-verified inspection and qualification surfaces

Run commands from the implementation checkout. These local commands do not
activate production or contact Flickr:

```powershell
npm run check
npm run release:inventory
uv run --frozen python -m scripts.current_schema_archive
uv run --frozen python -m scripts.fail_polite_release --evidence '<PRIVATE_EVIDENCE_JSON>' --artifact '<EXACT_WORKER_JS>' --config '<EXACT_CONFIGURATION_JSON>'
```

Replace each quoted placeholder with an existing private file; do not execute a
placeholder. The archive module's CLI prints schema provenance only. Its
`capture(..., source_stopped=True)` and `verify_restored(...)` functions are
library operations; running the module does **not** create a backup or perform a
restore. Full hosted qualification is performed by the existing release workflow
and documented production-suite runner; its provider fixture operations require
their separately approved execution context.

The existing authenticated status surfaces are:

- `GET /api/v001/admin/flickr-connection` for owner/connection and both gate
  states/revisions; no separate gate-list handler was found in `admin_api.ts`.
- `GET /api/v001/admin/group-submission-intents?view=active&page_size=100`
  and `view=attention` / `view=history`; follow the returned continuation exactly.
- `GET /api/v001/admin/group-submission-intents/{submissionIntentId}` for the
  retained trial record. Installation-authenticated equivalents omit `/admin`.

Status reads have durable admission/audit bookkeeping; do not describe them as
zero-row-write SQL observations. Admin status alone is user-scoped and cannot
prove the complete deployment queue census.

The following SQL is a source-verified inspection specification for a reviewed
read-only D1 operator adapter. It is **not** a permission to execute remote SQL.
Keep results private and export only sanitized counts. A missing bounded adapter
is a readiness gap; do not improvise a token-bearing CLI command.

```sql
SELECT scope, enabled, CAST(revision AS TEXT) AS revision
FROM flickr_write_gates ORDER BY scope, scope_id;

SELECT state, COUNT(*) AS intents, SUM(add_dispatch_count) AS dispatched
FROM submission_intents GROUP BY state ORDER BY state;

SELECT COUNT(*) AS attempts FROM submission_attempts;
SELECT COUNT(*) AS dispatch_markers FROM attempt_dispatches;
SELECT COUNT(*) AS blocks FROM submission_blocks;
SELECT COUNT(*) AS unresolved_dispatches
FROM attempt_dispatches d LEFT JOIN attempt_resolutions r USING(attempt_id)
WHERE r.attempt_id IS NULL;

SELECT COUNT(*) AS active_partitions
FROM group_partitions p WHERE EXISTS
 (SELECT 1 FROM submission_intents i
  WHERE i.partition_id=p.partition_id AND i.active_fifo_member=1);
SELECT COUNT(*) AS retained_leases
FROM group_partitions WHERE lease_id IS NOT NULL;

SELECT p.partition_id, p.user_id, p.group_id,
 CAST(p.wake_revision AS TEXT) AS wake_revision,
 CAST(p.next_work_not_before_us AS TEXT) AS due_us,
 p.lease_id, CAST(p.lease_generation AS TEXT) AS lease_generation,
 CAST(p.lease_expires_at_us AS TEXT) AS lease_expires_us,
 i.intent_id, i.photo_id, i.state, CAST(i.enqueue_ordinal AS TEXT) AS ordinal,
 i.add_dispatch_count
FROM group_partitions p JOIN submission_intents i
 ON i.partition_id=p.partition_id AND i.active_fifo_member=1
ORDER BY p.partition_id, i.enqueue_ordinal LIMIT 101;
```

If the last query returns 101 rows, stop and use a reviewed bounded continuation
procedure to obtain a complete inventory. The trial must not activate on an
incomplete result. Exact-pair queries use bound photo/group parameters to inspect
`submission_blocks` and `submission_intents`, then join `submission_attempts`,
`attempt_membership`, `attempt_preflights`, `attempt_dispatches` and
`attempt_resolutions` by retained IDs. Do not interpolate owner input into SQL.

## Activation states and stop rules

| State | Required invariant / transition |
| --- | --- |
| PREPARATION | Intake=0, dispatch=0, both durable gates paused; no admission or real Flickr write. This is the present state. |
| READY_FOR_OWNER | All worksheet/evidence fields complete, queue census accounted for, bounded activation/stop tooling rehearsed; flags remain disabled. Present reviewable packet to Terry. |
| APPROVED_STAGE | Only after Terry's explicit pair-specific live authorization: permit the approved normal binding/admission path while dispatch stays disabled and gates paused. Admit one pair, retain its returned intent ID, then close intake and prove exactly the intended new active record and no unexpected work. |
| APPROVED_EXECUTE | Only within the approved one-pair window, use the reviewed wake/dispatch procedure. Resume gates through the authenticated revision-checked API; never raw SQL. Enable dispatch only after the final fresh census and stop readiness check. |
| STOPPED_RECONCILING | Close intake and disable future dispatch using the rehearsed procedure; pause durable gates through a supported audited mechanism. Already-dispatched bytes cannot be recalled. Reconcile marked attempts under fail-polite rules with dispatch still prevented for new work. |
| CLOSED | Intake=0, dispatch=0, gates paused, final trial state durable, unresolved work accounted for, evidence retained; Terry reviews the result before any broader enablement. |

No time-based gate resume or automatic continuation is authorized by this trial.
Stop on unexpected intent/partition/dispatch, an identity/generation/revision
change, broken evidence/monitoring, deadline expiry, any terminal result, any
moderation/unknown/ambiguous result, or a write-gate trip. Safe read failures,
explicit temporary Flickr results and throttling also end this first execution
window: retain ordinary retry state and stop using the reviewed procedure. A
configuration rollout is not instantaneous and normal classifier-authorized
retries may race the stop; account for every marker/result. This runbook claims a
one-pair trial, not a hard maximum of one HTTP request. Ambiguous/moderation pairs
remain permanently suppressed. Do not repeatedly click Submit or Retry to obtain
success.

### Minimal engineering completion before owner review

The missing public pause endpoint does not require a new public route. ADR0051
permits trusted fixed operator operations. Migration0009's
`write_gate_transition` trigger already appends immutable per-gate pause evidence
when enabled/revision changes. Use a parameterized atomic operator transaction
that (1) asserts the exact deployment and user gate states/revisions through
`transaction_guards`, (2) changes only enabled target gates to paused and advances
their revisions, (3) appends an `audit_events` entry identifying the operator
component, owner target, reason and unique stable correlation, and (4) removes
the guard. Already-paused targets retain their revisions. Never reuse this
operation for resume; resume keeps the existing authenticated grant-check path.

The staged `scripts/controlled_trial_pause.py` implements that fixed operator
batch. The [official D1 query API](https://developers.cloudflare.com/api/resources/d1/subresources/database/methods/query/)
accepts a `batch` array of SQL/parameter objects, so an operator does not need a
new public Worker or remote-development service. This shape was checked on
2026-10-15. Use the reviewed private plan's exact account/database/owner IDs;
the tool accepts no SQL or destination URL, does not follow redirects, caps the
response at 64 KiB, sets a 30-second timeout and performs no automatic retry.
Its default mode validates the plan offline and prints only a digest/count.

The accepted administrative-control-plane contract's **FGA audit trail** section
says: “Every successful FGA database mutation and its successful audit event
commit in the same transaction.” It also states: “An audit-write failure refuses
a mutation.” That section distinguishes `audit_events` from domain history.
The generic gate trigger records no operator/request correlation and therefore
does not alone satisfy the first-class audit requirement for this control
operation. The supported batch avoids relying on that narrower interpretation.

Eight local checks of the actual staged operator statements/adapter passed:
both-scope pause and correlated audit; stale either-scope refusal; atomic audit
failure rollback; mixed/already-paused revisions without churn; lost-response
inspection without replay; refusal to confirm absent audit/later revision;
plan rejection; and fixed, bounded single-request provider encoding/no retry.
These are local SQLite and fake-provider observations, not a hosted REST atomicity
pass. Rehearse the same fixed REST batch against disposable hosted D1 fixtures,
including forced audit failure and stale revisions, before production use.

The `scripts/controlled_trial_pause_hosted.py` script supplies that disposable
drill, including all migrations through `0014_photo_memberships.sql`, exact
created-ID journaling, stale/audit-failure rollback checks, read-only inspection
after a simulated lost response, zero submission/dispatch rows and deletion of
only the newly created database. The
[2026-10-15 hosted receipt](../evidence/controlled-trial-pause-hosted-2026-10-15.json)
records **passed**, with all nine assertions true and cleanup confirmed.
[CI run 38752805316](https://github.com/FlickrGroupAddr/api-cloudflare/actions/runs/38752805316)
tested source commit `5f19773` using the dedicated test credentials.
The earlier [local authentication failure](../evidence/controlled-trial-pause-local-auth-unavailable-2026-10-15.json)
is retained separately: it made no provider request or resource. That local
credential availability issue did not prevent the dedicated CI proof.

The dedicated **Controlled pause proof** workflow uses the repository's existing
`FGA_CLOUDFLARE_CI_TOKEN` secret and `FGA_CLOUDFLARE_ACCOUNT_ID` variable through
`--from-env`. This mode reads neither an ignored local manifest nor a token file
and invokes no Wrangler login. Five mocked configuration/CLI checks passed,
including missing/invalid environment credentials causing zero provider calls or
resource creation. The workflow preserves the existing CI credential preflight,
uses pinned checkout/setup-uv/upload actions and locked Python dependencies,
and uploads only the exact sanitized proof receipt even on failure. Its private
created-ID journal is excluded from artifact upload. The workflow is a scoped
disposable batch/cleanup proof, not full release qualification or live-write
activation. The successful receipt has been reviewed and retained; it proves
the fixed pause batch's hosted atomicity and cleanup for the recorded schema.

Prepare a private JSON plan with exactly these fields: `schemaVersion` (1),
`accountId`, `databaseId`, `fgaUserId`, fresh UUID `operationId`,
`expectedDeploymentRevision`, `expectedDeploymentEnabled`,
`expectedUserRevision`, `expectedUserEnabled`. Enabled values are integer 0/1;
revisions are positive safe integers. Preserve that exact plan after an
unconfirmed response. The review packet records its digest and intended targets.
Do not pass token values in argv or print raw requests.

```powershell
uv run --frozen python -m scripts.controlled_trial_pause --plan-file '<PRIVATE_PAUSE_PLAN_JSON>'
```

Only during the separately authorized execution window, use the operator's
existing least-privilege Cloudflare token file for the mutation below. This token
is provider authority, never the Flickr token or Plugin Code:

```powershell
uv run --frozen python -m scripts.controlled_trial_pause --plan-file '<SAME_PRIVATE_PAUSE_PLAN_JSON>' --token-file '<PRIVATE_CLOUDFLARE_TOKEN_FILE>' --apply
```

If the outcome is unconfirmed, do not repeat `--apply`. Inspect with the identical
plan/operation ID; this executes only a fixed read and never replays the pause:

```powershell
uv run --frozen python -m scripts.controlled_trial_pause --plan-file '<SAME_PRIVATE_PAUSE_PLAN_JSON>' --token-file '<PRIVATE_CLOUDFLARE_TOKEN_FILE>' --inspect
```

Only `confirmed_paused` confirms both target gates, exact expected resulting
revisions, the stable operation audit, and required pause evidence. Later gate
revisions or missing audit retain `unconfirmed_inspect_required`; reconcile them
before further action. A successful pause fences new markers and does not recall
in-flight POST bytes. Disable intake and future dispatch as well, then reconcile
already-marked work with the normal protected recovery path.

For wake delivery, the minimal source change is to gate the existing scheduled
due sweep on `FGA_DISPATCH_ENABLED==="1" && COORD` rather than intake configuration.
This keeps normal D1 queue/gate/lease decisions, rate reservation and prepared
transport intact. The staged `scheduled-sweep.patch` contains the single
conditional change; it adds no public endpoint or service. With it, stage one
pair while stopped, close intake, drain admitted requests, complete the queue
census, resume the two gates through their existing API, then enable dispatch;
the ordinary cron can wake the retained pair with intake still closed.

The staged `tests/controlled_dispatch_sweep.test.mjs` passed four local tests:
normal authenticated one-pair admission followed by closed-intake cron dispatch
through the real consumer/transport and a terminal repeat sweep; no wake/POST
with dispatch disabled; and no POST with either deployment or user gate paused.
The provider peer uses synthetic responses; no external request is possible.
The test's namespace adapter invokes the normal consumer but does not prove
Cloudflare alarm delivery, configuration propagation or hosted runtime timing.
Run the integrated candidate with
`node --test tests/controlled_dispatch_sweep.test.mjs`. The intake and
status-cleanup sweep fixtures explicitly enable dispatch for their recovery
checks.

**Fresh full exact-artifact qualification remains required before production
deployment or execution.** Integration, local regressions and the fixed operator
batch's hosted proof are complete for this candidate. Terry can review this
packet and select the intended pair; live activation remains a separate explicit
decision after all release prerequisites are satisfied.

### Audited current-path limitations

- A complete empty-queue census, exactly one normal admitted pair, intake
  disabled afterward, no remaining admission invocation and a second complete
  census can bound the trial to that pair using existing durable invariants.
  Every partition must be accounted for, including delayed work and in-flight
  attempts. A new pair allowlist/one-shot dispatcher is not inherently required.
  `duePartitions` can select up to 64 partitions; `PartitionWorker` can immediately
  arm a successor after a terminal head. Thus a partial/selected-user census
  cannot establish the one-pair bound.
- **The closed-intake sequence has an unproved wake.** `worker.ts` returns from
  scheduled processing before `duePartitions` when `configured(env)` is false;
  that predicate requires intake enabled. An admission hint sent while dispatch
  is disabled gets 503 from `PartitionWorker.fetch` before binding or arming.
  With dispatch enabled but gates paused, queued heads do not arm in `arm()`.
  Gate resume does not itself publish a wake. Therefore the unmodified sequence
  of staging one pair while
  stopped, closing intake, then resuming gates/enabling dispatch is not a
  source-proven start procedure. Supply a supported bounded wake and rehearse
  this sequence, or review an alternative narrow sweep/intake window and its
  admission concurrency limits. Do not claim the existing cron wakes work with
  intake disabled. The `/wake` surface is internal to the Durable Object binding,
  not a public operator API.
- Admission hints and existing Durable Object alarms can wake work independently
  of cron, so disabling cron or intake alone is not a dispatch stop. The existing
  fail-polite states already protect moderation/ambiguity against replay. Preserve
  those protections and use ordinary qualified dispatch, rather than inventing a
  stricter one-HTTP contract for this trial.
- The registered admin routes provide `POST .../flickr-write-gates/user/resume`
  and `.../deployment/resume`, with body
  `{"schemaVersion":1,"expectedRevision":<OBSERVED_REVISION>}`. They require the
  owner browser session, exact Origin, CSRF and recent authentication; they verify
  the current expected owner/write grant and compare-and-set the revision. These
  calls contact Flickr and change durable authority. No explicit operator pause
  route or bounded pause CLI existed in the audited checkout. The staged fixed
  audited operator tool above supplies the minimal proposed pause implementation.
  A verified configuration rollout/rollback
  with dispatch disabled can stop future dispatch, but does not establish both
  durable gates paused. Supply an audited stop/pause procedure before claiming
  that closing invariant; do not use disconnect as an improvised pause or edit
  gates through unrestricted ad-hoc SQL. Rehearse rollout/in-flight behavior rather than infer it from
  the disabled configuration alone.
- Bootstrap tooling deliberately requires every feature disabled. It is not a
  production promotion/enable command. No supported one-trial activation CLI,
  current-state inventory CLI or current-production stop CLI was identified.
  Capture the actual private production configuration and previous disabled
  version during authorized preflight; do not reuse historical command paths.

These are engineering readiness inputs. They are not additional owner choices
about backup frequency or exceptions to accepted write safety.

## Classify the observed result once

| Observation | Retained meaning and operator action |
| --- | --- |
| Fresh membership already present, or Flickr code 3 | `added` / already present; no further add. Record a duplicate outcome separately from proof of a new add. Stop the window. |
| Complete success after add | `added`; retain marker, fresh reads, result and intent. Stop, then use a documented membership read if verification is needed. Do not replay the add. |
| Existing permanent exact-pair block | No add is eligible. Stop before activation/admission; retain first evidence. Neither new request nor changed moderation state clears it. |
| Flickr code 6 or 7 | Atomic permanent exact-pair block plus terminal `moderation_submitted`; FGA's action is complete, final moderator decision unknown. Stop. Absence is not rejection. No poll/scrape/retry may infer permission to resubmit. |
| Missing/failed/uninterpretable fresh moderation read | No add. Preserve safe retry evidence and stop this window. A cached group-discovery value never authorizes a write. |
| Unresolved `dispatch_started`, response loss, malformed/unknown post-dispatch result | Preserve evidence, terminal `delivery_uncertain` and permanent pair suppression under normal recovery; unknown code also pauses deployment. Never replay to discover what happened. |
| Codes 98/99 | User gate pauses; repair/relink explicitly, retain intent result, stop. Repair does not resume work automatically. |
| Codes 95/96/97/100 or 111/112/114/115 | Deployment gate pauses; stop and repair. Protocol/classifier repair also requires corrected-artifact conformance. No gate bypass. |
| Codes 1/2/4/8/10/11/116 | `needs_attention`, no automatic retry. Stop; any later corrected selection is a separate reviewed action. |
| Codes 5, 105 or 106 | Retain normal throttled/retrying classification, stop this trial window and prevent scheduled continuation pending review. No ad-hoc immediate resend. |

Every actual add attempt requires fresh exact-photo membership, then fresh group
`getInfo` as its immediately preceding Flickr operation, with all three possible
operation slots reserved before the reads. Retain durable preflight, fenced
marker, prepared transport and observed-age result. ADR0056 permits the private
Workers I/O-clock model with observed age strictly below 1,000 ms and its explicit
real-elapsed-time gap; do not describe it as a hard monotonic guarantee.

## Rollback and closure

Application rollback stops future eligibility only after the rehearsed mechanism
is confirmed effective; it cannot undo a Flickr addition or moderation event.
FGA never calls `pools.remove`. Preserve post-trial intents, attempts, markers,
blocks, audit events and gate revisions across any application rollback.

D1 Time Travel supplies the accepted daily coverage with documented 30-day Paid
retention. It overwrites D1 in place and does not restore Worker configuration or
native credentials. A database restore is an incident recovery step, not cleanup
for this trial. Stop all runtime writers first, retain the undo bookmark, verify
current schema/rows/guards/integrity and reconcile all newer blocks, unresolved
dispatches, revocations and live secret generations before any resume. If newer
protection history cannot be recovered, keep writes paused indefinitely rather
than guess. An older snapshot must never make the trial pair eligible again.

Close with a sanitized receipt: approved scope/reference; exact qualified client
and server identities; pre/post flags and gate revisions; complete active-work
census; trial intent/state and classifier reason; attempt/dispatch deltas;
membership/preflight/result evidence; preserved block if required; confirmed
stopped state; unresolved issues and private evidence locations. A successful
trial grants no standing permission for the next pair or continuous dispatch.

## Audited sources

- [Read-only production promotion](read-only-production-promotion.md),
  [current compatibility qualification](compatibility-date-2026-09-18.md),
  [backup/recovery](d1-backup-and-recovery.md) and
  [complete suite qualification](../research/2026-09-14-complete-suite-qualification.md).
- `src/worker.ts`, `src/intake_api.ts`, `src/dispatch_worker.ts`,
  `src/scheduling.ts`, `src/fail_polite.ts`, `src/native_lifecycle.ts`,
  `src/admin_api.ts`, `src/submission_status.ts`, `src/status_registry.ts`;
  migrations 0001, 0003, 0004 and 0009; release/archive/bootstrap scripts.
- Canonical architecture `AGENTS.md`, documentation authority policy, accepted
  ADR0007, ADR0013, ADR0056, the fail-polite conformance contract and accepted
  administrative control-plane contract. Lower-level operations prose cannot
  weaken permanent suppression, fresh preflight or authenticated resume.

This preparation inspected source/card metadata and ran local synthetic proofs.
It did not verify live
production, obtain tokens, select private photography data, execute a provider
request, alter the board, or activate a write.
