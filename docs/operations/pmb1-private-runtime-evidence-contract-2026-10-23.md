# Private runtime maintenance evidence contract

Date: 2026-10-23. Ticket #0251.
Status: **Accepted scoped source contract; implementation and qualification pending.**

Terry directly answered in the implementation chat:

> I’ll accept your recommendation for 0251

In context, the first clause accepts the independently reviewed #0251 recommendation
for bounded source implementation, independent review and qualification preparation.
It includes the explicit ADR0051 private trusted-code containment limitation.
This is genuine owner acceptance, not inferred from a card move or a review verdict.

This acceptance grants no actual evidence, unseen-fact approval, positive qualification,
private/provider access, schema installation, resource creation, deployment, capture,
migration, cleanup, reopening, run/call budget, renewal or replay.

Reviewed source bindings:

- Proposal SHA2-256: `e09d1e2e899e774ce58b46831e5939fb97c18cb15a7f95f5a6080928ef8280c7`.
- Decision sheet SHA2-256: `800699e1ef0ab6fd3fc3844cb503ae0d7caafdb3c7a30dd71971a8b57a248dcc`.
- Independent review SHA2-256: `2d352d1f0903c54c0ca6ac5530ad7dae78f019c202ebf5d0a6c221ed1a71e444`.

The reviewed clauses below are adopted without semantic edits. Only their historical
proposal title/status header is omitted; proposal-tense wording remains provenance.
The accepted status above controls this document. Original proposal and review files
remain unchanged in the private task evidence.

## Accepted reviewed clauses

1. Problem, authority and recommendation

The FGA API backend's prospective retained Worker needs NativeSourceInput and
ReviewedCoverage with genuinely fresh actual census, all-writer, custody and
native-retirement facts. The current constructors check typed reconciliation;
they deliberately do not authenticate those facts. Compiling facts into a private
module is source support, but recompilation changes retained bytes and a fixed
custody interval expires. Parent #0199 therefore remains incomplete.

Recommend reusing the separately owned external main-entry D1 journal as the
private authoritative transport and durable use ledger for already reviewed
evidence. This adds a narrowly scoped evidence authority beside, not inside,
ordinary invocation/effect accounting. It assumes no actual database exists or
qualifies. Reuse requires the later actual inventory to establish the exact
external resource and every binding/management holder. Failure retains NO-GO.

PMB-1, ADR0051, ADR0065 and ADR0066 remain controlling. No compared-store contents,
supported-state boundary, complete discovery, exact typed value, custody,
callback disposition, restoration or qualification requirement is weakened.
This proposal deliberately changes one input-delivery rule; it is not an
implementation or a claim that the current database schema supplies the path.

2. Exact current clause -> proposed replacement

Current coverage.ts constructor comment, lines 39-46:
"Construct only after authenticating the complete separately retained actual
census, source/fence meaning, native terminal records and resource custody."
"There is intentionally no JSON, environment, HTTP, packet-owned loader, default,
PASS callback or self-review."

Current static-artifact/entry.ts lines 53-55:
"ReviewedCoverage is an independent trusted input with NO environment/JSON
loader. Source packaging cannot authenticate factual custody or inventory."

Replace only the absolute no-loader exclusion for a newly selected prospective
source revision with the following proposed normative clause:

"After genuine Root and fresh independent semantic authentication, the trusted
private operator may publish the exact reviewed finite evidence envelope to the
separately owned, specifically bound external main-journal D1 through its fixed
reviewed publisher. The FGA API backend's native maintenance code may decode that
protected envelope into existing typed trusted inputs only after verifying the
qualified private provenance path, complete holder/writer inventory, publication
and review binding, exact target identities, finite current custody, durable
attempt state and complete bounded readback specified in this contract.

This is the sole serialized input-delivery exception. A JSON object, row,
authenticationRecord/reviewer string, digest, count, provider receipt or native
binding alone proves neither review nor factual meaning. Untrusted request,
environment, packet-owned or arbitrary database truth loaders remain forbidden.
No default positive result, self-review, automatic renewal, mutation replay or
fallback success is introduced. Missing, unqualified or uncertain provenance
refuses before positive maintenance authority."

The native-source.ts expected/observed population and packet validators remain
mandatory after delivery. Hash equality is identification, not semantic authority.
Existing frozen sources/defaults/history are unchanged. If accepted, record this
amendment in a new accepted scoped authority and update the named current-source
comments only in its separately reviewed implementation revision.

3. Who authenticates facts, and how that reaches the Worker

- Root gathers actual observations and independently retained source/management
  records under a separately authorized finite packet. Each claim identifies its
  actual source, acquisition method, complete population, observation interval,
  applicable version and limits. Native terminal records distinguish a stopped
  execution from a null alarm, empty tracker or acknowledged local receipt.
- A fresh non-author reviewer inspects the actual protected source evidence and
  its semantic reconciliation. Root must not review its own assembly. The review
  covers completeness, all old/current writers and creators, effective resource
  holders, source/fence meaning, custody and each native pending-operation result.
  A model-authored approval sentence without that work supplies no authentication.
- Root retains the exact approved envelope bytes, review result and detailed
  evidence privately. The review record binds the full envelope digest, target
  identities, evidence-source records and finite interval. A later content change
  needs fresh review; copying approval labels is insufficient.
- A fixed private operator publisher verifies those exact retained artifacts and
  the genuine review handoff, then writes only their exact content using the
  already authorized operator management path. No Worker/ordinary code path may
  publish, approve, amend or renew semantic evidence. No management token is put
  in the Worker; existing credential grants/expiry/delivery are checked separately.
- Before enabling this authority, independently qualify the publisher source,
  credential custody, actual binding-holder inventory and deployed code of every
  holder. Ordinary journal code may write only its existing fixed bookkeeping;
  maintenance code may append fixed use/terminal events. Neither has an evidence
  publication method. An unexpected holder or arbitrary-SQL path refuses use.

This protected provenance is procedural plus the existing private trusted runtime
and operator capability boundary. It is not a database-enforced Root/reviewer role:
the existing native D1 binding is broad. Under ADR0051, trusted code must not issue
unauthorized SQL or disable guards. A compromised runtime or operator credential
can defeat this containment. Owner acceptance must expressly include that limit;
do not disguise it with a publisher-name field, a second row or a shared secret.

4. Exact binding and the digest/immutable-version timing problem

Each envelope binds all of the following literally, with canonical exact strings:

- Contract/profile/boundary/schema revisions and the evidence-channel D1 UUID.
- Main-entry candidate source-context digest, lifecycle and journal generation.
- Full final retained module digest, final configuration digest, complete resource
  inventory digest and provider immutable version ID for each target component.
- Native owner/control reader source pins, namespace/object identities, exact
  control reference and packet pins; separately reconciled actual population.
- All writer versions/source pins/authorities and actual native retirement plus
  terminal-operation records; per-store generations remain separately named.
- Root publication/review record references, unique envelope and attempt IDs,
  exact allowed operation, fixed call/byte/row/time allocation and custody interval.

Source-context identity is not the full module identity. Preserve the existing
check candidate==the compiled generated source-context digest. Preserve the
independently retained full RetainedTarget module/configuration/resource/version
checks too; one digest cannot substitute for the other.

Publish runtime evidence only after the actual final identities and corresponding
management observations exist. They reside outside retained module bytes, so no
artifact embeds its own digest or an as-yet-unissued version ID. Runtime code must
not rewrite old authenticated bindings to current constants. Actual executing
version/binding attribution must itself be independently qualified and covered by
the closed custody/retirement inventory. If the platform cannot establish that
attribution for a required current/old instance, refuse; do not infer it from
whichever envelope was most recently selected. A later exact implementation must
prove this gate before the proposal can satisfy parent #0199.

5. Minimal durable representation and finite footprint

Propose three new guarded relations in the exact external journal only:

- Immutable envelope header: exact bindings, expected chunk count/total bytes,
  content digest, review/provenance references, interval and allocation.
- Immutable payload chunks keyed by envelope and ordinal. At most 16 chunks,
  each at most 262144 bytes; combined payload at most 4194304 bytes. Header and
  complete serialized payload bounds include the NativeSourceInput source bytes,
  packets and complete semantic evidence. Exceeding the cap refuses, never
  truncates, substitutes source hashes or omits population members.
- Append-only ordered events: publish, retire, use-reserved and terminal
  complete/refused/unknown. Unique keys prevent a second reservation of the same
  envelope/attempt/operation. Events reference immutable exact envelope bindings.
  No mutable current-evidence pointer, replace, expiry deletion or reset exists.

Evidence events have their own durable exact ordering; they do not modify the
stopped main-journal control revision or invocation/effect relations. Conversely,
ordinary admission/settlement activity supplies no evidence-approval authority.

Exact SQL/schema/guard definitions are later implementation, not supplied here.
Headers/chunks/events have strict type/size/identity constraints and ordinary
INSERT/UPDATE/DELETE/UPSERT/REPLACE/cascade hostile tests. Publication is one fixed
atomic D1 batch with at most 18 statements (header + 16 chunks + publish event), then
independent primary bounded readback. No other service participates atomically.

Before materializing payload, the reader uses a primary aggregate/header check
to reserve total row/serialized-byte ceilings. A second primary transaction reads
the complete exact ordered chunks plus event state; an unchanged final event
revision reread is mandatory. Missing, duplicate, excess, unordered or changed
chunks/events refuse. The publisher and consumer never use current observation
to manufacture expected chunk/content/source identities.

The envelope must supply the source-qualified native owner packets and finite
capture allocation as well as coverage. Leaving PMB1_READ_PACKETS or a fixed
PMB1_CAPTURE_CONTROL_PLAN as the effective source would leave the same expiry
problem unresolved. Select a NEW native-source/owner revision whose protected
control reference names the external D1 UUID, envelope ID and exact capture
attempt, rather than treating new data as the old namespace/object control.

For that new revision, this D1 event ledger is the SOLE authority for its raw
capture reservation/consumption/completion. The existing namespace capability
still addresses the exact already included storage-owning object; its fixed
owner method reads and validates the published packet and atomically consumes
the exact D1 reservation before acquiring native facts. Request arguments carry
identifiers only and cannot supply packet truth, SQL, review facts or a grant.
The source consumer reserves once; the owner consumes once; completion records
the original attempt. No callback, storage handle or arbitrary SQL crosses RPC.

This is a prospective native-control source successor, not a reinterpretation
of NativeCaptureControl's immutable singleton plan. Preserve every legacy
controller row, spent attempt and source. Do not renew its time window, reset it,
change its packet binding or reuse an unknown capture. The outer independently
retained operator ledger must reconcile legacy and new attempt allocations
before a new successor attempt is authorized. No old control migration or
additional control resource is selected by this proposal.

One consumption attempt permits at most 8 D1 requests and 32 statements total:
preflight, exact read, reservation transaction/readback, bounded status rereads
and terminal event. Each response is bounded before acquisition by schema and
query predicates; escaped serialization and retained copies are charged. The
finite implementation must prove those ceilings and compatibility with the
later selected account/runtime limits. Schema inspection/initial provisioning
and publication are separately allocated operations, not hidden in consumption.
The 4 MiB payload cap is an outer ceiling, not extra caller allocation: parsing,
decoding source bytes, retained copies, owner/control reads and acquired facts
must all fit their explicit separate and aggregate pre-acquisition budgets.

No new resource, service or authentication secret is selected. The database
already used by the prospective main journal gains at most one 4 MiB envelope
plus bounded header/event overhead per explicitly allocated publication. There
is no automatic publication loop, indefinite retention purge or garbage collector.
Finite lifetime storage allocations and existing journal load remain separately
reviewed. If later qualified database limits cannot fit a complete envelope or
the fixed batches, remain NO-GO and return the concrete unmet requirement.

6. Freshness, retirement, restart and uncertain outcomes

- Preserve the existing common custody limit: throughMs-fromMs<=600000ms. All
  current facts must cover the exact common interval and every required operation;
  clocks and executing source must be qualified. Check time and event revision
  before and after awaits. Expired/future/overlapping-conflicting evidence refuses.
  No timestamp update or newly copied approval renews old facts.
- Select exactly one published, unretired envelope for the exact target/lifecycle
  and explicitly allocated attempt. Do not select a convenient latest row or
  search another candidate after failure. Append-only retirement permanently
  removes future consumption authority; it cannot fabricate past callback death.
- Atomically latch use-reserved before any positive maintenance/native attempt.
  The fixed claim checks exact bindings, no retirement and no earlier claim in
  that transaction. A restart reads the same durable claim. It may perform only
  the allocated read-only reconciliation; it may not claim again or retry work.
- For new successor attempts, D1 use-reserved and native-acquisition-consumed
  events have unique exact attempt/operation keys. The owning native adapter
  consumes before its first storage acquisition; completion cannot create a
  first reservation or erase an unknown attempt. Existing NativeCaptureControl
  remains authoritative only for its unchanged legacy attempts. Lost reservation
  or consumption acknowledgement spends authority conservatively; no transaction
  spans D1 and object storage. An unused reservation loses availability safely.
- Publication, retirement, claim or terminal-write timeout/lost/malformed ACK is
  UNKNOWN. Never repeat a mutation to discover its outcome. Only a previously
  allocated bounded primary readback may reconcile the exact operation. Unknown
  provenance, claim, retirement or effective writer state prevents positive use.
- Retirement racing an in-flight read causes final revalidation to refuse the
  positive result. It neither cancels native operations nor authorizes replay.
  Custody cannot be shortened retroactively; Root must safely disposition any
  in-flight operation before releasing its promised exclusive interval.
- A fresh envelope may allocate a genuinely new observation only after fresh
  factual review and independently preserved budgets. It cannot revive an old
  unknown/spent capture or convert failed mutation acknowledgement to success.
- Database restore/reset/rollback, missing durable history, uncertain binding
  ownership or journal replacement invalidates the channel. There is no claimed
  rollback-proof hardware counter. Qualify native durability and preserve the
  external operator attempt ledger/custody. Do not use rollback to recover an
  unspent-looking attempt; recovery requires a separately reviewed lifecycle.

7. Ordinary route and retained restoration independence

The exact existing GET /api/v001/installations/current remains the ordinary
registry/authentication/lookup path through the fixed read-only D1 projection.
It must not construct, load, reserve or renew positive maintenance evidence before
that lookup. Missing/expired/retired/unknown channel records, unavailable external
journal or an expired source module must not change the existing ordinary GET's
authentication, lookup, response, feature gate or read-only behavior.

Successful GET proves only the accepted authenticated restoration observation.
It creates no custody, disposition, publication, reopening or qualification PASS.
All mutation/scheduled/partition paths retain their existing maintenance gates.
Tests must restore exact retained bytes after evidence expiry and prove the
ordinary GET still succeeds without any evidence-channel write/read or other
included-store mutation. Full independent typed snapshots remain mandatory.

8. Alternative and decisive implementation/qualification gates

Supported private service bindings let a Worker call another Worker without a
public URL. A native control-object method similarly requires its configured
namespace capability. Neither transport authenticates semantic review by itself.
The current control has no protected operator intake or reviewed facts ledger;
adding RPC still needs publication custody, durable claims and version binding.
A separate service also adds a deployable authority and binding inventory.
Prefer D1 reuse unless concrete evidence shows it cannot meet this contract.

Implementation must independently prove protected publisher call graph, complete
holder census, hostile ordinary writes, full exact-source binding, bounded
materialization, genuine reviewer record handling, substitutions, retirement
races, stale/future clocks, cold-start/restart claims, unknown/lost ACK, no replay,
partial publication, database-history loss, exact retained restoration and closed
GET independence. Synthetic records remain explicitly synthetic; local emulator
fit is separate from selected configured-date and actual managed qualification.

Owner acceptance permits source implementation/review and qualification packet
preparation only. It supplies no actual inventory/reviewed fact, new credential,
private/provider/native access, schema installation, resource creation,
migration, deployment, capture, cleanup, live execution, reopening or run/call
budget. Parent #0199 and every actual qualification gate remain unpassed.

9. Supporting sources (official API findings, not execution evidence)

Cloudflare documents D1 batched statements as transactions with rollback on a
statement failure, and first-primary sessions as starting from current primary
state. This supports the proposed local SQL transaction shape, not review
authentication, bounded client acquisition or actual engine qualification.
https://developers.cloudflare.com/d1/worker-api/d1-database/

Cloudflare lists a 2,000,000-byte string/BLOB/row cap, 100 bound parameters, 100 KB
SQL statement cap and 50/1000 queries per invocation by plan. Proposed chunking
and fixed ceilings stay below individual documented maxima; the later exact
allocation must still account for all existing invocation work and overhead.
https://developers.cloudflare.com/d1/platform/limits/

Cloudflare documents private Worker-to-Worker service bindings and RPC access
through explicit configured bindings. Transport isolation is an alternative
capability boundary, not evidence of actual Root/reviewer semantic approval.
https://developers.cloudflare.com/workers/runtime-apis/bindings/service-bindings/
https://developers.cloudflare.com/workers/runtime-apis/rpc/visibility/

Cloudflare also documents runtime version metadata including a version ID; its
navigation labels the feature Beta. This is a potential attribution source to
evaluate, not a selected dependency or proof of module/configuration identity.
The pinned local Workers types and Wrangler schema expose the binding. Neither
availability in types nor this proposal grants actual configuration or accepts
a Beta dependency. Required attribution must qualify or remain NO-GO.
https://developers.cloudflare.com/workers/runtime-apis/bindings/version-metadata/

Canonical/local source references and exact read pins: SOURCE-REFERENCES.json.
