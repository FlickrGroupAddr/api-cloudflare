# Fixed-origin preservation: bounded offline evidence contract

Date: 2026-10-17. Ticket #0152. Status: **offline preparation only**. No current
production observation, provider restore, deletion, native action or deployment
was performed. #0044 remains NO-GO, #0037 unqualified and #0043 negative for
provider restoration. Completed #0045 records a NO-GO disposition; it grants no
live authority.

Source amendment accepted by Terry on 2026-10-19 under architecture
[ADR0064](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/decisions/0064-scope-private-d1-preservation-to-application-state.md):
the [private D1 application-state profile](#accepted-private-d1-application-state-source-profile)
below permits only exact-manifest `_cf_KV` contents outside equality. Its
implementation and hosted qualification remain pending. The original strict
synthetic helper and historical evidence keep their original all-table scope.

`scripts/fixed_origin_preservation.py` implements the exact-comparison and
cleanup-receipt rejection rules below using synthetic evidence. Its CLI always
refuses execution. It has no HTTP, provider, credential, production-path reader,
deployment or deletion adapter. `synthetic_example()` is an explicitly labeled
test sample; none of its values are observed production baselines.

The governing accepted authority remains the architecture
[documentation hierarchy](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/README.md),
[ADR0007](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/decisions/0007-fail-polite-group-submissions.md)
and [required conformance contract](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/testing/fail-polite-worker-database-conformance.md).
The local [#0043 protocol](fixed-origin-restoration-2026-10-17.md) supplies the
preparation requirements; this implementation neither amends accepted state
semantics nor converts that negative result into a provider pass. The
[authorization disposition](fixed-origin-authorization-disposition-2026-10-17.md)
keeps the missing live work explicit.

## Baseline and finite comparison

The offline envelope pins the actual public #0036 capture-index digest
`ea43ba41d7bb5c6ae7fae569f77a8d126cfcfb7a0a550e5f92856c771b9f8202`
and captured module digest
`f1cef97fe6e1e62b5ff2b57f7e11516423974e756011750feb1aebe3abb13e6d`.
They come from `fixed_origin_restore.py`; the new work reads no private capture.
Pinning these known digests does not establish current provider state.

The metadata inventory is closed to the same fifteen named files:

- `account_rulesets_page_0.json`, `active_version_0.json`,
  `active_version_0_modules.json`, `custom_domains.json`.
- `deployments_after.json`, `deployments_before.json`, `page_rules.json`,
  `restoration-inputs.json`, `routes.json`.
- `script_settings.json`, `unversioned_artifact.bin`, `worker_settings.json`,
  `zone_lookup.json`, `zone_rulesets_page_0.json`, `zone_settings.json`.

Each has a SHA2-256 digest. Extra/missing names, failed/unknown observations and
non-digest values refuse comparison. This file census describes the completed
capture's scope; it is not a universal promise that future ruleset descendants
fit the same fifteen files. A changed effective inventory requires a new
explicitly reviewed schema/capture, never truncation to this old census.

The envelope additionally requires exact retained-version identity at weight100,
binding/runtime/effective-edge digests, production D1 identity, Durable Object
class/namespace lifecycle digest, assets digest, secret-reference identity digest,
disabled intake/dispatch/thumbnail assertions and a background-quiescence proof
digest. A digest names a privately retained proof, not proof of its authority.
The synthetic validator cannot authenticate or produce those provider inputs.
No secret value, generation replacement, object lifecycle, production resource,
schema change or historical data restoration belongs to the attempt.

`validate_preservation(baseline, refreshed, restored, cleanup, now_ms=...)`
requires all three synthetic envelopes to agree exactly, except their observation
timestamps. Refreshed preflight must be within 60 seconds of the initial
observation; restored evidence must be within 60 seconds of the validation
clock. Observations and completed cleanup fit the one twenty-minute window.
These are rejection bounds for this offline model, not a new live schedule or
permission to admit further requests. Expired/incomplete receipts remain
unconfirmed; this comparator never controls whether necessary cleanup executes.

## Paused gates and consistent full data

The real migration `0003_submission_coordination.sql` defines
`flickr_write_gates(scope, scope_id, enabled, revision)`. Production evidence must
bind the deployment row `('deployment','*')` and the exact owner/user row
`('user',<privately resolved owner identity>)`, both `enabled=0`, with positive
integer revisions pinned by the reviewed fresh baseline. No production revision
number or owner identity was observed in this batch.

The synthetic closed example uses `synthetic-user`, deployment revision7 and
user revision11. It requires exactly these two scopes and their unchanged
revisions, and checks them against the independently captured table contents.
An enabled/missing/duplicate/foreign row, changed revision or disagreement
between the summarized gates and full snapshot refuses. Boolean `False` does
not substitute for the stored integer `0`. Environment capability flags do not
substitute for these durable rows. Gate revisions are ordering authority;
formatted timestamps cannot replace them.

`capture_sqlite(connection, run=..., database=..., observed_at_ms=...)` receives a
caller-owned **synthetic** SQLite connection. Use a fresh connection exclusively
for this helper: it installs a temporary instruction budget and clears that
handler afterward. It opens no database path and must never be supplied a real
production connection under a synthetic label.

The helper rejects an active caller transaction, then reads `sqlite_schema`
and every enumerated table within one explicit read transaction, finally rolling
it back. It retains all schema objects, column order and every row as typed
null/integer/real/text/blob cells; rows are sorted without losing duplicates.
Nonfinite REAL values are refused at collection rather than producing a
snapshot the comparator could not accept. Claimed REAL cells also must decode
to a finite float and round-trip to the exact canonical `.hex()` string;
overflowing, noncanonical or malformed encodings refuse even when supplied
consistently across every input envelope. It includes migration/SQLite
bookkeeping tables when present. The aggregate is
bounded to 128 tables, 2048 schema objects, 256 columns per table, 10000 rows,
4MiB canonical evidence and ten million SQLite VM instructions. Per-value
SQLite length limits and incremental aggregate byte checks prevent a large
result from being accumulated before checking. Engine `table_list` classification
refuses virtual and shadow tables without relying on SQL whitespace or spelling.
Exceeded bounds, SQLite failures or unsupported values fail closed; they never
produce a partial successful snapshot or a row-count substitute.

Every ordinary rowid table also retains the hidden signed-integer SQLite rowid,
aligned with its canonical typed row; this includes explicit INTEGER PRIMARY KEY
aliases and bookkeeping tables. If a declared column shadows `rowid`, the helper
uses the unshadowed `_rowid_` or `oid` alias. If all three are shadowed it refuses
instead of omitting the hidden identity. WITHOUT ROWID tables record `rowids=null`
and retain their explicit key columns. The current checkout's source/migrations
do not use implicit rowid for durable ordering, but this collector preserves it
anyway: future adapter/schema uncertainty cannot weaken exact identity comparison.
This compares relational contents, schema and SQLite row identities; it does not
compare B-tree page placement, free pages or physical database-file bytes.

Rollback failure is a separate closed refusal:
`synthetic_snapshot_cleanup_failed_discard_connection`. Each remaining client
setting is restored independently, including progress handler, length limit and
row/text factories, even when an authorizer denies ROLLBACK. The connection may
still have an active read transaction and must be discarded by its owner; no
snapshot is returned, no raw SQLite diagnostic escapes and no success is inferred.
The helper does not disable the caller's authorizer or guess how to release its
transaction. A closed/unavailable connection also produces a sanitized refusal.

This is actual local SQLite read-transaction behavior, not D1 consistency
evidence. The comparison detects equal-count row substitutions, schema changes,
gate drift and any added/lost credential, suppression, admission, intent,
dispatch or audit fact represented in a complete source snapshot. A production
reader must enumerate the **actual captured production schema**, rather than
assuming the newer checkout's migrations describe it. Existing source contracts
do not provide that reader here. No arbitrary row/time limit silently omits
safety history: exceeding this bounded design requires a new reviewed method.

Background writers must be quiesced with a separately approved mechanism before
the baseline and remain quiesced through readback, or a separately accepted
consistency/accounting protocol must replace this exact-equality design.
Paused Flickr write gates alone do not prove sessions, read maintenance,
schedulers or other writers are quiescent. This implementation accepts no drift
exception, ignored table, monotonic-only substitute or automatic repair write.

## Accepted private D1 application-state source profile

Status: **accepted source contract amendment on 2026-10-19; implementation,
independent review and hosted qualification pending**. Canonical ADR0064 owns
the consequential boundary decision; this section owns its detailed evidence
semantics. Source profile identifier: `adr0064-private-d1-application-state-v1`.

This profile narrows only the preceding blanket requirement to read every
enumerated table and accept no ignored table. Its one exception is the
inaccessible contents of exact `main._cf_KV`, documented by
[Cloudflare](https://developers.cloudflare.com/d1/best-practices/import-export-data/)
as reserved underlying storage. It is not a general drift allowance. The
existing strict all-table helper, old evidence formats, packets, stopped
attempts and historical NO-GO dispositions remain strict; no retrospective
selection, compatibility default or successful relabeling is permitted.

1. **Complete application state.** Discover the actual captured schema and
   retain every FGA-owned logical fact and every addressable table/cell,
   including authentication/session/CSRF state, credentials, revocations,
   permanent suppression, append-only history, intents, admission, dispatch,
   queue order, leases, fencing, gate values/revisions, migration history,
   SQLite sequences and addressable statistics. Retain exact schema, SQL
   guards, indexes, views, triggers, typed values, duplicates and hidden rowids
   or WITHOUT ROWID keys. No application fact may be lost through this boundary.
2. **Closed exact exclusion.** Bind an explicit exclusion manifest to this
   profile/contract revision, exact main-schema table name `_cf_KV`, object kind,
   official provider documentation and actual observed schema/table-list
   metadata. Review source, migrations and observable schema relationships for
   application dependence. Any application-owned fact or dependency that would
   be omitted refuses the profile. Never infer ownership from a prefix.
3. **Full census remains evidence.** Retain and exactly compare every observable
   schema/table-list entry, including `_cf_KV`. Missing, changed, conflicting,
   duplicate or malformed identity/classification metadata refuses. Do not
   manufacture empty contents, counts, row identities or hashes for excluded
   contents, and do not query inaccessible contents just to manufacture a denial.
4. **No unknown omissions.** Reconcile the full discovered schema/table census
   against the finite reviewed query/classification manifest before data reads.
   Unknown or unmanifested names refuse. A new ordinary table requires a new
   complete reviewed inclusion plan; a new provider-like name or changed
   reserved identity needs new evidence and review and never inherits this
   exclusion. No `_cf_*` or `sqlite_*` filter is allowed. Unsupported objects,
   values or inaccessible application state still refuse the whole capture.
5. **Truthful receipt boundary.** Bind profile, contract revision, exclusion
   manifest and ordered query/source provenance into each new input/output and
   comparison receipt. Declare excluded contents explicitly `unobserved`,
   `unfrozen` and `unverified`. Keep actual excluded identity/reason and retained
   observable metadata in private evidence. Public receipts expose only approved
   bounded metadata/digests. A scoped result must not satisfy or be labeled as
   whole-D1/provider-content equality; missing/mismatched profiles or manifests
   refuse. Exact metadata equality says nothing about reserved content equality.
6. **Preserve application barriers.** The complete application-writer freeze or
   separately accepted consistency/accounting protocol remains mandatory across
   baseline and readback. Authentication/read maintenance, administration,
   schedulers and ordinary checks that write application state remain writers.
   Never classify such writes as excluded provider background activity. The
   barrier makes no claim to freeze inaccessible provider internals. Matching
   sweeps still cannot rule out mutate-and-revert behavior.
7. **Keep independent gates.** All finite bounds, private custody, provenance,
   primary-consistent reading, exact independent equality, no replay, unknown
   retention, equality-before-cleanup, resource/configuration continuity and
   unchanged gate revisions remain. REAL extraction and UTF-8 representation,
   backup/restore, atomicity, authentication, least privilege, protected history,
   guards and production/release qualification remain required independently.

The excluded actual contents may change without observation or prevention;
provider internals can affect service behavior. No harmlessness or provider
preservation guarantee follows. This is Terry's accepted managed-service
visibility boundary for source work. It authorizes source implementation,
independent review and qualification preparation, not production reads,
account/credential access, provider operations, deployment, migration,
live/native action or new provider contact. Every production/hosted verification
flag remains false until its own applicable evidence and acceptance gates pass.

Before relying on an implementation, independently test exact `_cf_KV`
classification with retained census metadata; rejection of unknown/similar names,
application dependence and malformed/mismatched manifests; census drift;
application/history/authentication/sequence/guard/rowid drift; unsupported values;
and profile mismatch. Preserve strict-profile denial and existing finite,
no-replay and cleanup controls. These are required future checks, not executed
test or hosted results. The separate managed REAL capability gate remains open.

### Source implementation interface

The source implementation selects this boundary only with an explicit
`profile_manifest` argument to `private_d1_snapshot_codec.collect_snapshot` and
`fixed_origin_preservation.validate_preservation`. The finite reader requires
both `profile` and `profileManifest` in its plan and matching explicit consent;
the existing plan digest and source/evidence pins still bind that input. An
omitted profile retains the original strict format and table-content reads.

`private_d1_snapshot_profile.py` validates the closed private manifest. It binds
the profile and contract revision, the official provider documentation, complete
observed schema and table-list rows, every included table, the one exact
exclusion, and source/migration/schema dependency-review digests. Those digests
and a negative dependency attestation are reviewed inputs, not an implemented
source-analysis proof or evidence that independent review occurred. Observable
SQL references to excluded contents conservatively refuse, including comments
and literals, rather than adding a permissive SQL parser.

New private snapshots retain the manifest, complete table-list metadata, column
metadata for included tables and exact ordered generated query/source provenance.
The comparator requires the same profile binding in each envelope and the
cleanup evidence. Its distinct version-2 application-state receipt explicitly
sets `wholeProviderContentsEqualityVerified` false and labels excluded contents
`unobserved`, `unfrozen` and `unverified`; public output contains labels and
digests only. It cannot consume strict inputs or pass as a strict receipt.
Source tests use synthetic in-memory SQLite and fake transports. Independent
review, isolated hosted qualification and the separate REAL capability gate
remain pending; this interface enables no new provider dispatch or authority.

## Stop, restore and cleanup receipts

The comparator consumes receipts; it does not issue operations. It requires:

1. Run-bound durable qualification admission disabled, acknowledged and
   independently read back, with the pinned admission revision advanced once.
   This is distinct from the two unchanged production write gates.
2. A later latched, acknowledged, independently read-back restore to the exact
   baseline retained version with `force=false`. A latest-version choice,
   rebuilt upload, changed target, force override or unknown acknowledgment
   refuses. The restored full configuration/data comparison must pass first.
3. Exact run/identity-matched creation acknowledgment, deletion latch,
   deletion acknowledgment and independent absence receipt for the one
   synthetic D1, receiver and each of the two declared temporary Actions secret
   identities. Production D1 cannot appear in the removal set. No deletion
   starts before restored evidence in this contract.
4. Separate matching-run cleanup receipts for the native target, native cache
   and local secret material, after restored verification. A native receipt
   cannot prove remote deletion. Foreign identities, missing receipts, failed
   absence reads, unknown results or out-of-order observations refuse completion.

One-time latching and actual mutation ownership remain the lifecycle operator's
responsibility; booleans in a synthetic receipt do not implement a durable
provider lock. The existing fixed-name Actions secret ownership gap is not
resolved by this validator. An ambiguous mutation must retain the exact private
journal for bounded read-only reconciliation, with no blind replay, forced
restore, resource recreation or guessed deletion. Failure leaves cleanup
unconfirmed and cannot license further admission.

## Required source seams and remaining handoff

The module returns these explicit missing source categories even when its
synthetic comparison passes:

- Fresh complete capture and independent retained-target availability readback.
- Current exact production user scope and paused gate revisions.
- Bounded consistent production schema/full-data reader and privately retained
  integrity/consistency provenance. A completed old capture or row census is
  insufficient.
- Approved background quiescence and artifact-bound safe authenticated ordinary
  reads. The sample checks only the captured refusal statuses401/404/404 on the
  three intended GET paths; it does not exercise an authenticated ordinary
  production route. The pinned ordinary module lacks the existing-photo
  handlers. No newer candidate/source route may silently supply those checks.
- Exact resource/secret-reference and Durable Object lifecycle continuity.
- Independent admission-off, restore and exact remote-absence receipts.
- Matching-run native/local cleanup receipts.

Next engineering ownership is a separately reviewed observation/receipt adapter
for each missing seam, bound to the actual captured artifact and private
identities. A current-account/API/native invocation remains outside this batch.
The restored-version/changed-secret synthetic Case A/B provider proof is separate
from this comparison contract and remains required before any production attempt.

Successful offline output sets `comparisonPassed` and synthetic
`cleanupEvidenceComplete` only. `currentProductionStateVerified`,
`providerRestorationVerified`, `changedSecretSemanticsVerified`,
`authenticatedOrdinaryRoutesVerified` and `deploymentAllowed` always stay false.
Untrusted or fabricated evidence cannot become a production pass through this
module. The public output contains only closed labels, digest and false gates;
the full comparison inputs belong in private synthetic test storage, never in
published production evidence.

Verification uses pinned uv0.12.5/Python3.14.7, with no outbound calls:

```console
uv run --frozen python -m unittest tests.test_fixed_origin_preservation
uv run --frozen ruff check scripts/fixed_origin_preservation.py tests/test_fixed_origin_preservation.py
uv run --frozen pyright scripts/fixed_origin_preservation.py tests/test_fixed_origin_preservation.py
```

Executed verification: all26 offline unit tests passed; Ruff lint/format checks
and Pyright passed for the module and tests. The independent test author covers
exact equality, full-row/schema/migration/SQLite-sequence drift, failed/unknown
gates, freshness/order, foreign identities and cleanup receipt incompleteness.
Regression coverage includes nonfinite REALs, denied rollback on successful and
failed reads, restored connection settings, hidden-rowid drift/alias alignment,
WITHOUT ROWID and inaccessible hidden identities. Claimed-cell regressions reject
overflow, underflow and noncanonical REAL strings at each stage and across all
three envelopes, while canonical signed zero, subnormals and maximum finite
REALs remain valid. Tests use synthetic in-memory
SQLite only. Independent implementation review
remains a separate parent-owned handoff gate.
