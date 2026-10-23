# Bounded native object source mechanisms and capability finding

Status: SOURCE SUBSET ONLY; complete object capture remains NO-GO.
Recorded 2026-10-23 under accepted PMB-1 / ADR0065. This directory supplies no
deployment, object invocation, credential, provider operation, actual oracle,
all-writer closure, resource or qualification authority.

`population.py` constructs the supported account namespace and per-namespace
object REST paths for an injected synthetic/model GET port. The actual HTTPS
entry is permanently disabled before DNS or connection with
`native_census_transport_unqualified`; there is no enable flag or network
implementation in this directory. Returned model bodies are byte bounded before
JSON decoding; pagination has no SDK auto-pagination or retry. Account namespace metadata and selected namespace
object populations reconcile against a separately supplied, frozen expected
inventory. False `hasStoredData` entries remain included. Opaque provider cursors
are not object identifiers or ordering keys. Unknown fields, missing required
metadata, duplicate IDs/JSON keys, cursor loops, excess pages/objects/bytes and
unknown outcomes refuse. A census instance is spent after any attempt.

The census output always has `completeSnapshot: false` and
`actualQualification: false`. Equality with an inventory is a bounded observation;
it does not establish REST snapshot consistency, expected-inventory custody,
creator disposition or a common all-store closed interval. A new Python instance
does not renew an actual invocation budget. The caller must account for each
actual request separately. The removed r01 HTTP implementation could not bound
header/framing/slow-drip acquisition or an absolute network deadline. No actual
transport is supplied or enabled here. A future implementation needs separately
reviewed concrete bounds and actual permit/custody; passing a model callback does
not qualify or authorize network acquisition.

`native.ts` implements the existing `ReadSession` shape for storage already owned
by the executing Durable Object. `readLocal` opens one supported native storage
transaction. The exact approved SELECT set, custody input and limits freeze before
the callback. A SQL-only count/byte preflight runs inside that transaction before
materializing the exact original result. Signed64 facts must already be decimal
TEXT projections; unsafe Number results refuse. Original queries are never
rewritten to drop metadata. Query/callback/time/byte/row limits are finite;
callback reentry, expired sessions and unknown operations refuse without replay.
Native transaction entry is gated before invoking the consumer even when the
native callback begins after the timeout already returned. The SQL byte/count
preflight itself runs synchronously inside the native engine: a JavaScript timer
cannot interrupt it. It bounds projected result serialization before original
cursor materialization, not engine work or arbitrary engine/JS heap allocation.
An absolute native execution deadline and complete heap bound remain unqualified;
the source timer/post-check is not proof of either.

Native KV list acquires at most one item with supported `startAfter` / `limit`.
It reserves a conservative 2 MiB serialized-source allowance before every list,
including a potentially empty terminal page. After successful acquisition, a
bounded supported-type traversal measures a conservative upper bound for retained
typed facts and releases the unused in-flight reserve. Retained facts plus each
next worst-case acquisition stay within the unchanged 4 MiB ceiling. Small KV
inventories can complete; sufficiently large retained facts refuse the next
acquisition before dispatch. Unsupported values poison the session even if a
consumer catches the error. This is serialized-fact accounting, not a native/JS
heap claim. Raw typed values remain intact for the original reader's exact codec.
Observed fixture size never reduces the pre-read reserve; no budget is raised.

The fence reads the actual maintenance singleton, closed state and exact
generation. Writer epoch, interval and custody come from the caller's separately
established evidence; a local transaction cannot prove them. Native alarm reads
report only scheduled time. They do not establish handler disposition. The
existing native wakeup and partition disposition mechanisms remain in
`../pmb1-native-wakeup/candidate.ts` and `../../src/partition_maintenance.ts`.
No legacy alarm marker, sequence or callback identity is fabricated.

There is deliberately no complete `SupportedSource` factory joining a REST
census to remote storage. The APIs do not yield a remote storage handle; this
directory installs no RPC. The factory's unresolved actual population, transport,
custody and qualification requirements remain separate from the source successor.

## Exact capability finding

Cloudflare documents that the SQLite-backed KV API uses an automatically visible
`__cf_kv` table but denies SQL access to its contents. The existing complete
reader includes every discovered table, requires guard/cell coverage and reads
exact counts/identities/cells. Its synthetic SQL-visible `__cf_kv` fixture is not
proof that those native operations exist. `native_internal_sql_unavailable`
refuses before attempting to read that table. Unknown automatic metadata still
refuses; no object exemption is imported from the distinct D1 profile.

Supported typed KV enumeration exposes key/value facts, including binary and
bigint values, but not the hidden SQL storage representation, hidden row
identities or provider implementation cells. Thus equal typed KV snapshots do
not prove equality of every required raw hidden SQL fact. This is a concrete
contract/API mismatch, not merely absent credentials or a missing test run.

Separately, the supported listing API documents cursor pagination without a
common consistent-snapshot guarantee. A census alone cannot rule out population
changes across pages, omitted not-yet-visible allocations or old writers. This
is an evidence gap in the consulted API contract, not a claim that the provider
has been shown to omit an object. Native `getAlarm()` may return null while an
alarm callback runs; deleting an alarm does not cancel that callback. Existing
writer/callback disposition and independently retained inventory remain required.

## Accepted prospective boundary; implementation remains incomplete

Terry accepted the independently reviewed narrow prospective boundary on
2026-10-23. [Architecture ADR0066](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/decisions/0066-scope-prospective-object-preservation-to-supported-state.md)
and its scoped contract record the explicitly selected
`pmb1-private-object-kv-interface-v1` boundary within the no-REAL profile.

Only inaccessible raw SQL contents and rowids of the exact automatic object
`__cf_kv` table are excluded from equality. Its observable schema/census, all
application SQL/guards/cells/identities, supported typed KV including binary, and
alarms/identities/order remain exact. The hidden provider representation remains
unobserved, unfrozen and unverified and may change undetected. This is distinct
from D1's `main._cf_KV` boundary, with no general metadata or prefix exclusion.

The alternative was to keep every hidden raw fact required and retain NO-GO
pending supported provider evidence/access. The accepted narrow change permits
prospective source implementation and review only; it supplies no native proof.

The separately selected source successor is implemented in
[`object-kv-interface.ts`](object-kv-interface.ts), with exact source/manifest
binding and full observable metadata retained as described in
[`BOUNDARY.md`](BOUNDARY.md). `readLocalSupportedBoundary` admits only its exact
source-bound automatic column-metadata pragma; raw hidden SQL still refuses.
The original complete reader and `readLocal` default are not relabeled or changed
to select that boundary. Complete native SupportedSource acquisition, independent
inventory and all-writer/creator closure, common custody, callback disposition,
memory/time/acquisition bounds and managed qualification remain unproved. Neither
acceptance nor typed KV equality proves raw hidden SQL equality or a REST snapshot.

## Official evidence consulted 2026-10-23

- [Namespace list API](https://developers.cloudflare.com/api/resources/durable_objects/subresources/namespaces/methods/list/)
  and [object list API](https://developers.cloudflare.com/api/resources/durable_objects/subresources/namespaces/subresources/objects/methods/list/):
  supported metadata, pagination and permission surface. No documented global
  in-flight list or common snapshot guarantee is inferred.
- [SQLite storage API](https://developers.cloudflare.com/durable-objects/api/sqlite-storage-api/):
  automatic hidden table restriction; transactional local SQL/KV; cursor metadata;
  list ordering/limits; typed structured-clone values. `transactionSync` requires
  a synchronous callback, so this asynchronous reader uses `transaction`.
- [Native alarm API](https://developers.cloudflare.com/durable-objects/api/alarms/):
  scheduled time differs from callback identity/disposition.
- [Native storage limits](https://developers.cloudflare.com/durable-objects/platform/limits/):
  SQLite-backed combined KV key/value and SQL row/string/BLOB limits are 2 MB.

The implementation is TypeScript because it runs against the native Workers
storage API and implements the TypeScript reader's callback interface. REST
orchestration and validation use Python under the repository's default.

Tests: pinned Node 24.22.0 `--test native.test.mjs`; pinned native TypeScript 7.0.2
`tsc --noEmit -p tsconfig.json`; pinned uv 0.12.5 `run --frozen --no-sync python -m
unittest discover -s probes/pmb1-native-object-reader -p test_population.py`, scoped
Ruff and Pyright. Tests use an in-memory SQLite/model storage and mocked HTTP
connection only; expected inventories and SQL/typed facts are separate literals.
