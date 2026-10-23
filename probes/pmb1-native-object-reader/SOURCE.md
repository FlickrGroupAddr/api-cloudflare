# Prospective native binding composition

Status: SOURCE implementation, pending independent review. Actual complete
native acquisition and managed qualification remain NO-GO. No deployment,
credential, provider call or actual resource is supplied by these sources.

`createNativeSource` in `native-source.ts` is the concrete `SupportedSource`
factory for the explicitly selected ADR0066 boundary. It consumes a separately
retained expected account/namespace/object inventory, provenance digest, exact
census digest and per-object source/manifest/query packets. It reconciles all
account namespace metadata and every selected object, including
`hasStoredData=false`, before resolving any owning object. Source/manifest,
population and packet mismatches refuse before native acquisition. The expected
inventory is never made from observed output. A provenance digest identifies an
input; it does not establish independence or completeness.

The management census is a separate controller phase. REST pagination supplies
observations, not a consistent snapshot, remote storage handles or creator
closure. Account identity is retained explicitly. The external control namespace
is included in account metadata but must be outside every compared namespace.

`native-owner.ts` exports a real `DurableObject` subclass with one read-only typed
RPC operation. Future composition must export it under the **existing storage-
owning class identity** and bind the existing namespace. A new reader namespace
would read different storage and is invalid. Its constructor performs no storage
operation. There is no HTTP handler, bootstrap or arbitrary SQL RPC. Missing state
refuses; an absent object is never fabricated as empty. Legacy classes and frozen
readers are unchanged. Binding/deployment and actual custody remain future gates.

The owner receives only a packet digest and an external reservation. Its exact
source-bound packet comes from reviewed configuration. It consumes the external
reservation before acquisition, then runs the selected reader and
`readLocalSupportedBoundary` against its own storage in one native transaction.
The finite reviewed SELECT set, source/manifest, full observable metadata,
application SQL/KV/alarm/fences and exact typed checks remain enforced. Only
acquired values cross RPC; storage handles, callbacks and a live `ReadSession`
never cross that boundary.

The carrier retains ordered read events. The factory gives the outer unchanged
successor a closed local session over these already acquired facts. Query/index,
KV cursor, alarm/fence order, truncation, object/packet substitution and use after
closure refuse. This local interpretation performs no second native read or
storage replay. Unknown acquisition and caught invalid-session operations poison
the source. Terminal pages, finite events and final artifact bounds remain exact.

`native-control.ts` implements a small external capture journal in a separate
private namespace. Explicit `initialize()` installs only its own fixed SQL schema
and reviewed plan. There is no automatic initialization. Fixed reserve/consume/
complete transitions bind the plan, namespace, object and owner packet. Reserve
increments a persisted finite call counter; a unique object key rejects a new
source instance. Consume persists before native acquisition, so recreating an
owner cannot use that reservation again. Unknown outcomes remain spent. Cleanup,
deletion and replacement of external control state are not provided. The owner's
additional isolate guard is not the restart guarantee.

`transport.py` supplies the separately named `FiniteHttpsGet`. The original
`population.HttpsGet` remains disabled. Import/construction perform no network or
credential load. Explicit later journal preparation and activation require an
exact retained packet, source graph, evidence references, expected inventory,
numeric address, finite window and credential digest. Evidence references are
inputs, not self-certified qualification. The collector reuses the reviewed
project's concrete `_pinned_https`, `Request` and external `SQLiteJournal`; there
is no second HTTP parser/client or ambient project-module import. The reused D1
library's complete closed graph and bound exports are verified. One fixed sibling
census module is loaded from retained bytes and its executable exports checked.

TLS uses the exact Cloudflare hostname with a separately pinned public numeric
address, no DNS/proxy/redirect/retry, one absolute deadline and a decrypted HTTP
wire ceiling covering headers, framing, cookies and body. Validated Set-Cookie
fields are discarded and still budgeted. Only the selected account's namespace/
object GET routes and bounded pagination parameters are admitted. Durable ordinal
and response allowances precede sockets. Repeated paths and reconstructed
attempts refuse; unknown outcomes retain the allowance. Existing limits remain.

Native serialized-fact accounting, SQL preflight, KV acquisition reservation and
carrier framing reserve precede acquisition; no bound was raised. Native SQL is
still synchronous and cannot be interrupted by a JS timer. Complete engine/JS
heap, RPC wire allocation and an interruptible absolute native deadline remain
**UNKNOWN**. No `complete` flag or factory supplies these facts.

Closure observations come from the separately retained closure packet, not a live
independent census of writers/callbacks. Actual executing-source and automatic-
table provenance, binding ownership, inventory independence/completeness,
creator/all-writer retirement, common closed custody, callback disposition,
clocks, external journal durability, grants/delivery, bounds, retained artifact
and restoration/reopen still require independent actual qualification. A null
alarm proves no callback completion. ADR0066 excludes only the exact hidden
representation in `BOUNDARY.md`; included metadata/application/KV facts stay exact.

Synthetic tests retain independent literal metadata/signed64/binary expectations.
Local workerd tests prove genuine RPC class support, no bootstrap and external
reservation persistence across abort/recreation. Outbound network is disabled
and emulators disposed. They do not qualify complete managed capture or native
heap/deadline bounds. Python transport tests use scripted sockets and temporary
journals only.

Official primary references checked 2026-10-23:
[namespace API](https://developers.cloudflare.com/durable-objects/api/namespace/),
[Workers RPC](https://developers.cloudflare.com/workers/runtime-apis/rpc/),
[RPC security](https://developers.cloudflare.com/workers/runtime-apis/rpc/visibility/),
[RPC lifetime](https://developers.cloudflare.com/workers/runtime-apis/rpc/lifecycle/),
[SQLite storage](https://developers.cloudflare.com/durable-objects/api/sqlite-storage-api/).
The application-defined acquisition RPC is implemented here; it is not a claimed
provider snapshot or global in-flight enumeration API.
