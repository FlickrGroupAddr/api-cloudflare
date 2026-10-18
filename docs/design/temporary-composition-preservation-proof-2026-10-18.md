# Temporary composition: preservation proof and privacy boundary

Date: 2026-10-18. Ticket #0169. Status: **derived design; B selected for
development on 2026-10-18; no live qualification**. The dated owner direction
below selects private full snapshots for development and qualification preparation.
Alternatives A and C remain Proposed and unselected. No account, capture or run
access, production query, deployment, SQL, credential access or native action is
authorized by that direction. No production values were inspected.

## Result

The current metadata-only collection permission cannot produce the required full
paused-state consistency and writer-barrier proof. No existing reviewed adapter
proves that result while keeping production records and secret values outside
collector custody. Keep `baseline` unavailable and materialization, preservation,
provider-restoration and deployment readiness false. A nonempty
`productionState` object is a shape check, not this proof.

This is an incompatibility between the selected collection scope and the needed
evidence, not evidence that D1 cannot meet the accepted safety requirements.
Terry selected B below for development: full private snapshots processed by bounded
code. That direction does not make production execution ready or supply missing
account/capture/run permission. The complete reader and an actual all-writer
barrier still need the engineering and qualification gates below. C remains an
unselected Proposed alternative; no witness/trust amendment has been accepted.

## Controlling sources

- Canonical [documentation authority](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/README.md)
  controls status and amendments. This derived note cannot alter an accepted
  contract or make a proposed permission accepted.
- Accepted [ADR0007](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/decisions/0007-fail-polite-group-submissions.md),
  [persistence/scheduler contract](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/worker-persistence-scheduler-contract.md)
  and [required conformance contract](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/testing/fail-polite-worker-database-conformance.md)
  preserve permanent suppression, durable history, ordering, fencing and recovery.
  [ADR0051](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/decisions/0051-trust-private-storage-runtime-with-guarded-writes.md)
  trusts the private storage runtime within its stated scope; it does not waive
  preservation, client/provider least privilege or production qualification.
- The local [preservation evidence contract](../operations/fixed-origin-preservation-2026-10-17.md#paused-gates-and-consistent-full-data)
  requires complete typed relational contents/schema/row identities and unchanged
  durable gate revisions. The [restoration protocol](../operations/fixed-origin-restoration-2026-10-17.md#return-to-design-handoff-finite-preservation-protocol)
  requires exact retained-version/configuration/resource continuity, nonforced
  restore and independent receipts. Both remain offline preparation evidence.
- The selected [collection boundary](../operations/temporary-composition-collection-decision-2026-10-18.md)
  excludes production records, secret values and mutations. It explicitly leaves
  `productionState` unavailable when proof/privacy is unresolved. The
  [assembly packet](../operations/temporary-fixed-origin-composition-2026-10-18.md)
  does not authenticate supplied full-state evidence.

Preserving the local full-equality bar is the proposed course. Allowing drift,
ignoring tables/columns, treating only monotonic safety facts as sufficient, or
replacing full comparison with a bare attestation would change that bar. Any such
change needs an explicit proposed amendment at the owning contract, linked to the
canonical authority and accepted by Terry before implementation relies on it.
No such amendment is adopted or recommended here.

## Why the available sources do not close the gap

| Source | Actual capability | Missing proof or privacy incompatibility |
| --- | --- | --- |
| `scripts/fixed_origin_preservation.py:capture_sqlite` | Enumerates schema and all typed rows, including hidden rowids, in one explicit local SQLite read transaction; comparator requires exact equality | Synthetic connections/identities only; no production D1 reader. Returned evidence contains actual cells. Relabeling it as hosted evidence would be false. |
| `scripts/controlled_trial_observations.py:collect` | Reads fixed inventories and pair projections twice, including gate metadata; explicitly relies on an external stopped-writer barrier | Reads/retains production photo and database records if run live; inventories omit other columns/tables and are not full preservation. Equal passes do not establish a multi-request snapshot or exclude an intervening change that is later reversed. |
| `scripts/current_schema_archive.py:capture` | Exact selected migration-schema archive from a declared stopped source, including private authentication/CSRF values | `source_stopped=True` is caller evidence, not a barrier. Full private records would leave the provider. Its older archive scope/normalization is not the newer all-schema/hidden-rowid contract; `_cf_KV` and SQLite bookkeeping treatment require explicit reconciliation, not silent omission. |
| `scripts/temporary_composition_delta.py:validate_baseline` | Requires complete configuration sections and a nonempty `productionState` dictionary | Does not validate full-state contents, establish custody, authenticate the source or prove any writer stopped. |

The public safe metadata projections cannot observe even the two required durable
gate rows. The owner/user identity must be independently resolved privately;
require stored integer `enabled=0` and positive unchanged pinned revisions for
exactly the deployment and intended owner scopes. Capability flags, inventory
counts and request-target echoes supply none of those observations.

Full row comparison necessarily examines every included cell somewhere. Secret
store values are outside this proof and must never be fetched. Database cells
may themselves contain authentication material; the existing archive explicitly
warns about CSRF values. The actual captured schema needs a private sensitive-cell
classification before any broader read. Hashing after HTTP receipt, suppressing
logs or redacting retained output cannot make that prior receipt cease to be a
record/secret read. No assertion is made that production contains only safe cells.

## Required all-writer barrier and consistent observation

A later concrete packet must name one mechanism that meets every item below.
No current source supplies it, and no operational step is authorized by this note.

1. **Census the exact artifacts and writers.** Privately bind the original and
   temporary artifacts, actual schema/resources and every code/operator identity
   capable of writing them. Cover ordinary and authenticated reads with audit,
   session or rate-limit effects; intake; admin/credential operations; scheduled
   maintenance; dispatch/recovery; queue consumers; Durable Object alarms/hints;
   service callers; migration tools and direct provider operators. Current
   `src/worker.ts:scheduled` invokes status/authentication/key/credential
   maintenance before its dispatch-capability check. Current source demonstrates
   why a dispatch flag is insufficient; it is not a census of the captured module.
2. **Close admission and drain before baseline.** Prevent new writes across all
   those entry points and independently acknowledge completion or durable fencing
   of already admitted work, delayed callbacks and pending transactions. Include
   stale invocations and other deployed versions. An absent schedule, silent log,
   elapsed arbitrary delay or disabled Flickr write gate is not an acknowledgment.
   The separate qualification admission gate must not replace either production
   gate. Any pause mutation needs separate explicit authority.
3. **Preserve the barrier through restored verification.** Name its durable owner,
   generation, exact scope, safe crash behavior, expiry and independent readback.
   A stale process must fail at the storage commit boundary, not merely have
   checked a flag before an await. Restart, old-version execution, configuration
   propagation, direct-operator writes and failure to read the barrier cannot
   reopen writes. If the retained original lacks that mechanism, adding it means
   a changed artifact and cannot silently satisfy exact original restoration.
4. **Capture complete actual state consistently.** Discover the actual production
   schema with the same boundary protecting the data reads. Retain the newer
   comparison semantics: all schema objects, typed cells, duplicates, table/column
   identity, hidden rowids or WITHOUT ROWID keys, sequences/bookkeeping and gate
   rows. Refuse unsupported objects/types and exhausted row/byte/time/query
   limits. Prove one coherent snapshot or prove a continuously enforced no-writer
   interval covering every page. Schema discovery followed by unrelated SELECTs
   is not automatically one transaction. Separate D1/DO stores need their own
   observations under the common freeze; never assume a cross-service transaction.
5. **Compare before installation, at fresh preflight and after restoration.** Bind
   each observation to exact run, resource, artifact, barrier generation, time,
   completeness and independently retained provenance. Preserve the existing
   freshness/window bounds or explicitly review a replacement before reliance.
   Compare full state with no drift exclusions and pin the two durable gate
   revisions unchanged. A failed, stale or ambiguous read refuses the attempt;
   it does not imply empty state or authorize a repair write.
6. **Keep ordinary read checks inside the same safety claim.** The exact restored
   artifact must supply any required authenticated check without writes or Flickr
   calls. If its existing authenticated route necessarily writes audit, sessions
   or maintenance rows, that check cannot coexist with this full-equality freeze.
   Record the incompatibility and obtain a scoped contract/design decision; do
   not omit its writes, suppress required audit, or substitute a newer route.

Official D1 [binding documentation](https://developers.cloudflare.com/d1/worker-api/d1-database/)
provides transactional `batch()` calls; the
[replication documentation](https://developers.cloudflare.com/d1/best-practices/read-replication/)
describes session ordering. Neither alone establishes a frozen all-writer
interval across collection requests and Worker restoration. These public
references were checked on 2026-10-18; no account behavior was tested.

A preexisting outside-database operational barrier that preserves the captured
configuration would be the simplest fit, if it can actually satisfy the census,
drain and stale-writer requirements. Its existence is unproved. Installing a new
SQL trigger, barrier table, module wrapper, route or credential restriction during
the attempt is a mutation/configuration change, not evidence that the unchanged
captured deployment already has this property. A barrier that is removed by exact
restoration cannot protect the subsequent data/readback interval without a
separately qualified overlapping mechanism. No automatic expiry may resume writes.

## Owner direction and qualification gates

**Owner direction recorded 2026-10-18.** Terry explicitly selected **B: develop and
qualify private full snapshots**, including authentication/session fields processed
only by bounded code. Raw records must never enter chat, logs or Git. This selects
the development direction; it grants no actual account access, production capture
or run access, and no production SQL or mutation. The exact private destinations,
custody, effective grants, finite action packet and execution permission still need
their separate gates.

#0170 owns development of the bounded typed private D1 reader/codec and isolated
qualification-source preparation. #0163 retains the qualified all-writer barrier,
actual capture, provisioning and materialization gates. B's selection does not
qualify the existing isolated archive for production, authenticate a supplied
snapshot, or satisfy any missing source/consistency proof. Accepted full-state
preservation requirements remain unchanged. C is Proposed and unselected; its
witness/trust amendment below has not been accepted.

**Proposed choice A — retain the current collection boundary.** Continue the
bounded partial metadata preparation and keep production composition NO-GO.
`baseline` stays unavailable. This is the only choice requiring no new production
record/secret-read or mutation authority. It does not resolve #0163's assembly
prerequisite.

**B — selected for development; actual observation remains gated.** Develop a
small reviewed read-only observer/comparator producing full private typed snapshots
with explicit private destinations and retention/deletion custody. Authentication
and session fields are included and processed only by bounded code; raw records
remain outside chat, logs and Git. This direction deliberately permits development
toward private database-record export rather than provider-local witness-only
comparison. It does not grant a current production read/export, supply a stopped
source or qualify the older isolated archive. Secret-store/binding values remain
excluded. No production SQL or request follows from this direction alone.

Before either a private observer or a future provider-local comparator can run:

- Bind actual schema/artifact authority, sensitive-cell handling, finite queries,
  effective grants, credential custody, request/byte/time bounds, independent
  source pins, operator consent and exact record destinations. Do not invent
  unobserved production table lists or choose bounds that silently truncate data.
- Implement and independently review the barrier and complete-reader seams on
  synthetic/local inputs first. Reuse safe typed serialization where valid;
  reconcile archive omissions and D1 result conversion rather than changing
  sealed offline comparators or claiming `source_stopped` implements exclusion.
- Qualify against isolated hosted D1 and the actual production adapter semantics:
  concurrent writer before/after barrier, in-flight callback, stale/restarted
  worker, operator bypass, barrier loss during restoration, schema drift between
  pages, equal-count replacement, mutate-and-revert, hidden-rowid/type/large-value
  drift, pagination/limit failure, timeout and observation cleanup failure.
  Required behavior is refusal or proven fencing, never an unexplained green root.
- Inject private synthetic photo/authentication markers into every supported value
  type and failure path. Verify none reaches public output, logs, trace, exception,
  process arguments, support artifacts or agent messages. Private full-data
  custody remains a deliberate read/export under choice B, even when logs are clean.
- Present the resulting exact action packet for separate access/mutation decisions.
  Retained-version/changed-secret provider cases, ordinary-route conformance,
  resource continuity and cleanup receipts remain independent required gates.

**Proposed choice C — unselected; full comparison inside a separately reviewed
trusted Cloudflare comparator.** This alternative remains for comparison with B;
Terry has not selected it or accepted its witness/trust amendment. A dedicated
observer Worker would read
the exact approved D1 through its binding, canonicalize every actual schema
object/cell/row identity inside Cloudflare, and compute a complete-state SHA2-256
root there. The operator would receive only an authenticated bounded witness
containing equality/refusal, run/source/target provenance and the approved root.
No rows, per-cell values or raw SQL results would be returned to the operator.
This is ordinary trusted backend computation, not zero-knowledge or remotely
attested computation. The D1 binding supplies a plausible compute boundary; no
existing project adapter implements or qualifies this workflow.

A concrete implementation candidate is deliberately small:

1. Deploy the separately reviewed observer Worker outside the serving production
   Worker; bind only the exact production database and a separately owned private
   proof store. Do not alter the captured module, its routes or production schema.
   A production binding grants real read capability and must be separately approved;
   API endpoint allowlists do not make that runtime capability read-only. The
   trusted observer source exposes fixed read operations only, no caller SQL,
   arbitrary table selection, record-return endpoint, write/repair or secret lookup.
2. Under the independently enforced barrier, discover the actual schema and build
   one finite query manifest, including bookkeeping and hidden row identities.
   Obtain complete bounded pages from the primary-consistent read path and compute
   one canonical full-state root. Use unambiguous length-delimited typed encoding,
   exact integer strings, canonical binary64 handling, raw blob bytes, deterministic
   schema/column ordering and duplicate-preserving row ordering. Qualify the D1
   transport representation; JavaScript number rounding must not erase 64-bit
   integer differences. An unknown table/type or unsupported row identity refuses.
   Do not copy the older archive codec's exclusions or normalization silently.
3. Store only the run-bound root, schema/query-manifest digest, phase, completeness,
   barrier generation and finite dispatch/progress journal in the isolated proof
   store. No production row, secret-valued cell or restorable database copy goes
   into that store. Before-installation, fresh-preflight and restored roots must
   match; all their independent gate/configuration/resource/barrier checks must
   also pass. A root alone does not establish those facts. The proof store's writes
   are separate approved mutations and never a transaction with production D1.
4. A restarted observer may resume only an explicitly journaled incomplete phase
   while the same verified barrier still holds and the original bounds remain.
   An uncertain page/phase, missing proof-store acknowledgment, lost baseline root,
   changed barrier, expired window or exhausted budget refuses. Rebuilding a root
   after barrier loss is a fresh observation requiring a newly reviewed baseline,
   not continuation of the prior claim. Bound response sizes before accumulation,
   total bytes/pages/queries and execution time against hosted limits; if the
   proposed full dataset cannot fit, stop and redesign rather than sample it.
5. Return a closed witness over the approved authenticated TLS channel, with an
   independent operator-retained run challenge/request pin and exact observation
   phases. Independently read back the deployed observer version/module/configuration
   and target binding and retain those pins with the witness. A self-reported source
   digest is not proof that those bytes executed. Independent review checks source,
   provider deployment evidence and failure tests; it cannot recompare unseen rows.
   Keep roots and manifests private unless separately reviewed for disclosure;
   hashes are integrity commitments, not anonymization or protection against guessing.

**Proposed witness/trust amendment required for C.** At the owning preservation
contract, explicitly permit a qualified trusted in-provider observer to replace
privately retained raw full-state inputs with its authenticated complete-state
comparison witness. Preserve all-table/all-cell/schema/row-identity equality,
paused gates and unchanged revisions, consistent observation, freshness, writer
barrier and independent restoration/cleanup requirements. Record the accepted
SHA2-256 collision assumption and trust in the deployed observer, D1 read path,
proof-store journal and source/deployment provenance. The external reviewer would
no longer independently compare raw state; that is a real evidence/trust change,
not a format-only adapter update. Parent should place any normative Proposed
amendment at the appropriate canonical authority before acceptance is requested;
this derived note does not adopt it.

C also needs an explicit scope distinction: private rows may be transiently read
by the approved observer inside Cloudflare, while no production records or secret
values leave that boundary. Secret stores/binding payloads remain unread. If
actual database cells contain authentication secrets, complete equality entails
processing those cells inside the trusted observer. If Terry's exclusion means
no additional runtime may read such cells even internally, C is incompatible with
that exclusion too; do not claim hashing avoids the read or drop those columns.
Qualification must inject synthetic secret-valued cells and prove they cannot
escape through witness, exception, diagnostic, logs or proof storage.

The unsolved all-writer barrier is decisive for C as well as B. A separate observer
cannot fence writers merely by reading D1, and exact root equality at three times
cannot prove no intervening mutate-and-revert. No supplied evidence establishes a
barrier surviving exact retained-original restoration without changing that
original. C is therefore a concrete candidate for separately authorized synthetic
implementation/hosted qualification and an owner witness/trust decision, not a
production-feasible claim today. If the exact-artifact barrier fails, stop at that
specific incompatibility or propose an explicit new baseline/artifact decision;
never weaken equality or quietly replace the captured original.

## Handoff

This analysis inspected tracked public source and public provider documentation
only. No SQL, account request, private identity resolution, production capture,
implementation, deployment or qualification test ran. Documentation validation
checks links/format and source references only. A fresh independent High review
must assess this incompatibility and owner-choice wording before handoff. The
primary owns any canonical Proposed amendment and board relationships; this file
adds no second normative schema or acceptance contract.
