# Finite native D1 operator binding — partial source delivery

This Python operator source supplies a concrete, finite D1 REST read transport,
complete no-REAL reader, external durable operator journal and read-only retained
confirmation custodian. The exact mutation receipt remains unsupported by the
documented unchanged protocol. `Provider.dispatch()` refuses before networking.
This is not a complete production control binding or a qualification PASS.

The distinct `SyntheticSuccessorBinding` and `successor_control.Qualification`
now execute the accepted two-statement candidate end to end under a trusted
synthetic exchange. They compose immutable retained campaign intents, complete
independent PRIMARY reads, the external journal, atomic request/SQL-statement/
request-byte/response-byte allocation and a separate SQLite returned-invocation
custodian. This is executable qualification-source delivery, with distinct
synthetic result/receipt wrappers. It has no production sender or credential
loader: `activate()` refuses and `activate_synthetic()` uses a constant
noncredential. Constructor/default CLI remain inert. The original Provider and
single_fixed_update behavior remain unchanged.

The Python operator is separate from the Worker `MainEntryJournal` backend.
Do not import it into a Worker or present it as a native Worker adapter.
The external SQLite journal lives in the trusted operator's qualified private
filesystem, outside every compared D1 database and object store. It adds no D1
resource. All eventual API requests, retained files and response ceilings still
need inclusion in the reviewed campaign allocation; this source grants none.

## Delivered mechanisms

- `Binding` uses the existing `_pinned_https` primitive: one numeric public
  address, verified `api.cloudflare.com` TLS hostname, no DNS/proxy/redirect,
  one explicit framed response, wire accounting, no internal retries. Every read
  requires the API's `served_by_primary: true`; absent or false refuses.
- A separately retained packet pins exact account/database, address, source,
  credential digest, query sequence, fixed limits, clock domain and independent
  evidence files. Its pin is a trusted integration input. Evidence hashes do not
  establish their truth, qualification, review, source independence or custody.
  The later operator must establish those factual gates before activation.
- Default construction and CLI perform no operational I/O, credential delivery
  or networking. Normal module loading reads fixed local source only. The fixed
  20-module project dependency graph, including journal, adapter, source verifier,
  HTTP dependencies and lazy codec imports, is compiled from frozen bytes into
  private namespaces. Project imports route only within that explicit graph.
  Ambient cached namesakes are neither used nor replaced; Python and its standard
  library remain trusted. Private module registration supports dataclass type
  resolution; it never reuses an existing module. Repeated checks bind executed
  graph bytes, module/export identity and binding aliases to all pinned files.
  Explicit `activate()` validates the retained packet, current source
  and existing journal before invoking a supplied credential loader. It never
  discovers environment credentials, cached accounts or isolated-run permits.
- SQLite `BEGIN IMMEDIATE`, zero busy timeout and FULL synchronization serialize
  permanent singleton reservation, atomic successor CAS, one dispatch claim,
  shared root read/reconciliation counters and durable request ordinals. A
  missed/late acknowledgment cannot release a reservation or reset a counter.
  Worst-case response allowance is charged before dispatch; unknown responses
  retain it. Only a validated timely received response refunds its unused bytes.
- `Observer` issues its own fixed complete PRIMARY read requests. `CompleteReader`
  calls the existing full typed codec and profile/guard verifier using only the
  exact finite reviewed query sequence. It preserves full 65-table source fit,
  signed-int64 decimal transport, observable metadata, guards and row identity.
  Only the accepted `_cf_KV` contents exclusion applies. A future pagination or
  truncation signal refuses; it never fabricates exhaustion or adds queries.
- `native_source_descriptor()` uses the accepted candidate for local source
  provenance and requires a separately retained expected native profile. It
  compares all application schema rows to the fixed candidate and keeps complete
  native metadata equality. It never creates an oracle from its own readback or
  silently reuses the candidate's synthetic metadata as a native oracle.
- `FileConfirmations` has no writer or `retain_returned` operation. It reads only
  an independently retained pinned index for an expected independent producer,
  exact immutable intent/result and the producer's retained commit/readback/final
  journal acknowledgment/returned-invocation evidence. JSON labels alone have no
  attestation authority. Establishing the producer's independence and actual
  timely result provenance remains an external custody qualification requirement.

## Exact mutation receipt capability finding

The [D1 REST query contract](https://developers.cloudflare.com/api/resources/d1/subresources/database/methods/query/)
documents `meta.changes` as an approximate indication from connection-total
changes, and documents optional PRIMARY metadata. It does not promise the exact
single-statement direct-row count required by the existing `Provider` contract.
Returning success, matching state or a numeric `changes == 1` cannot supply the
missing promise. This source never normalizes that approximate value to an exact
commit receipt. The existing adapter also prohibits deriving a count from returned
rows and permits only the original single fixed UPDATE. Production writes refuse
before dispatch, even if a packet contains an apparently positive evidence file.

Terry accepted the bounded source successor on 2026-10-23; the
[accepted scoped note](../../docs/operations/pmb1-exact-change-receipt-successor-2026-10-23.md)
owns that choice. `binding.exact_receipt_successor` provides an inert builder,
request/statement manifest, strict ordered body decoder and byte-bound decoded
receipt manifest for the distinct
`fixed_update_with_exact_count_v1` protocol. It contains exactly the unchanged
fixed UPDATE from one immutable intent, followed by
`SELECT CAST(changes() AS TEXT) AS exact_change_count`. A third statement is
excluded. Preserve separately issued complete PRIMARY readback and all existing
durable intent/unknown/no-retry rules. The
[SQLite changes contract](https://sqlite.org/c3ref/changes.html) and
[SQL function contract](https://sqlite.org/lang_corefunc.html) define direct
changes for the preceding mutation, excluding trigger work. The
[D1 Worker batch contract](https://developers.cloudflare.com/d1/worker-api/d1-database/)
describes ordered transaction execution with rollback on failure; the REST query
contract accepts batches but does not itself establish every required
same-connection/commit/ordered-result fact. Independently review and qualify those
facts for the exact selected supported REST/native interface before native
dispatch. A later standalone `SELECT changes()` on another connection cannot
serve this purpose. The decoder returns typed decoded evidence only, with exact
decimal TEXT zero/one handling; it does not attest commit or normalize that
evidence into the historical Provider receipt. Zero cannot become idempotent
success. Missing/order/extra-result/numeric/PRIMARY/completion anomalies refuse.
The original named UPDATE parameter bytes are preserved; the selected REST
parameter binding itself remains a qualification obligation. No builder or
decoder loads credentials, provisions a resource, spends an intent or dispatches.
Production dispatch remains unimplemented and disabled for all protocol identifiers.

The concrete synthetic REST candidate builds exactly the fixed batch body and a
fully framed request for the retained account/database/address. Before handing
it to the supplied synthetic exchange, one SQLite transaction reserves the
request ordinal, both SQL statements and the complete request wire/maximum
response allocation, and permanently consumes that intent's batch-dispatch slot.
Read requests each consume one request and one SQL statement. A normal transition
requires five requests and six SQL statements (two complete preflight reads,
one two-statement mutation request, two complete postflight reads). Additional
transitions and reconciliation share the original root limits and exact retained
query sequence; no implicit query, budget or replay is added.

Whole-campaign generation headroom is reserved once for the immutable root,
before activation/latch. The pure batch codec validates one increment only;
durable successor advancement validates the root ordinal, adjacency and remaining
slots. The immutable original transition limit is never charged again as though
each successor began a new campaign. MAX-3 with limit three and MAX-2 with limit
two may therefore finish exactly at signed-int64 MAX; root overflow and a fourth
transition still refuse. Legacy journals without the new allocation tables are
not upgraded or reset by a successor request.

`ReturnedInvocations.invoke()` calls the model producer itself; no API accepts a
caller-created Result for retention. After an actual timely returned model
confirmation and final journal acknowledgement/checks, it retains the exact
intent/result and request/response evidence in a separate exclusively created
append-only SQLite custodian. Unknown/lost/late/refused outcomes cannot produce
a receipt. Public synthetic receipts have a different type from the historical
ConfirmedReceipt; the private synthetic lifecycle bridge alone consumes them.
This models custody integration, not qualified native independent attestation.

The [prepared-statement contract](https://developers.cloudflare.com/d1/worker-api/prepared-statements/)
currently documents ordered and anonymous parameters and explicitly leaves named
parameters to future support. The unchanged UPDATE uses the named
`:expected_generation` twice. The tests explicitly bind it by name in their
SQLite model; they never treat this as REST array-binding evidence. Worker batch
ordering/transaction documentation cannot establish this unchanged named native
path or qualify REST. Terry separately accepted the
[prospective positional variant](../../docs/operations/pmb1-positional-generation-successor-2026-10-23.md)
in #0250. `positional_receipt_successor` derives exactly two token replacements,
both `:expected_generation` to the same `?1`, with every other historical byte
unchanged. It binds one canonical positive signed-int64 decimal TEXT parameter
and retains the same exact-count SELECT. Its identifier is
`fixed_update_with_exact_count_positional_v1`, with distinct batch/count types,
request/receipt manifests and source pins. The original named codec rejects its
batch type and remains unchanged in SQL/protocol/default behavior.

Select the new source explicitly with `SyntheticPositionalSuccessorBinding`;
the ordinary synthetic binding continues to select the named protocol. A packet
for the other class refuses before exchange. Both model selections preserve the
same durable control, root headroom, independent PRIMARY reads, returned model
custody and request/statement/wire-byte budgets. Neither class has native sender
activation or an actual credential loader. Positional source acceptance supplies
no REST connection/transaction/commit evidence or native qualification.

## Remaining factual and source limits

- No exact native receipt, independently produced native source oracle, actual
  target/configuration/metadata, writer closure, global census, grant, custody,
  immutable artifact, common interval, restoration or positive run is supplied.
- The source-bound packet does not replace the full later reviewed qualification
  packet. Matching synthetic SQLite state never supplies native completeness.
- The operator must qualify stable monotonic clock continuity across restarts,
  filesystem power-loss durability, ACLs, protection against path replacement,
  hard links and rollback, and retention of the one journal path. No source-only
  path or hash check proves those properties. Missing state refuses and is never
  auto-provisioned. `provision()` is an explicit later private preparation step;
  failed preparation keeps its tombstone, with no automatic cleanup/retry.
- Native REST full results and the exact selected query/response bounds require
  later qualification. Multi-query capture requires the common all-writer closed
  interval; it is not a native multi-query snapshot transaction.
- The read-only confirmation parser cannot independently produce or certify the
  required producer attestation. No caller-created `Result` or journal phase can
  be elevated to a retained confirmation by this module.

Tests are entirely synthetic. They patch the concrete HTTPS boundary, exercise
real temporary SQLite durability/serialization and the complete candidate schema,
and explicitly label their expected metadata and evidence as fixtures. They never
load actual credentials or contact Cloudflare. Independent standard-library
socket acquisition and DNS blockers surround every test; teardown requires zero
calls even when an exception would otherwise have been caught by the operator.

Run with the pinned existing environment, without dependency synchronization:

```text
uv run --frozen --no-sync python -m unittest discover -s probes/pmb1-native-d1-binding -p test_binding.py
uv run --frozen --no-sync ruff check probes/pmb1-native-d1-binding
uv run --frozen --no-sync ruff format --check probes/pmb1-native-d1-binding
uv run --frozen --no-sync pyright --project probes/pmb1-native-d1-binding/pyrightconfig.json
```
