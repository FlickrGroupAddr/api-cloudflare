# PMB-1 main Worker entry admission and settlement bridge

Date: 2026-10-19. Ticket #0198. Status: source/synthetic implementation;
actual runtime, all-store qualification and action readiness remain **false**.

The accepted [PMB-1 source contract](prospective-maintenance-contract-decision-2026-10-18.md)
controls this bridge. The [source census](pmb1-closure-census-2026-10-19.md)
owns the included entry/family inventory. Neither this source nor its synthetic
ports claim that an actual production writer census, admission barrier, durable
journal or pending-state reader has been qualified.

## Actual handler composition

[`createMaintenanceWorker`](../../src/worker.ts) requires a
[`MainEntryMaintenance`](../../src/main_entry_maintenance.ts) instance and calls
the same complete `workerHandlers` implementation used by ordinary
`createWorker`. There is no toy route, synthetic authentication result, new HTTP
maintenance endpoint or `FGA_READ_ENABLED` shortcut. The existing default export
continues to construct the ordinary artifact. A prospective retained assembly
must explicitly select the maintenance constructor and supply independently
qualified ports; the ordinary default is **not** a maintenance-capable assembly.
The constructor rejects an absent bridge. Object shape alone does not qualify a
port: the later exact assembly/qualification must refuse missing or unqualified
durable and independent adapters rather than substituting the test fixtures.

Admission precedes all fetch routing, including login/Google/OAuth paths that
precede the registry, static administration paths, unknown paths and errors.
The entire scheduled callback is admitted before status cleanup, Google-key
refresh, authentication/plugin-code cleanup, native credential maintenance,
group refresh, dispatch capability checks, due-partition reads and wake hints.
Flags retain their ordinary feature semantics and provide no closure evidence.

The capability projection covers the main graph's D1 prepared operations and
original atomic batches, all configured Flickr/application/native/temporary/
authentication secret reads, budgeted and thumbnail provider fetches, response
body consumption and independently retained cancellation, asset fetch, native wake calls, and the injected
album create-repair reader factory/methods. It preserves native receiver branding
and unwraps statements only inside the original D1 batch boundary. Unreviewed
D1 execution methods, raw handles and provider-body clone/tee/pipe APIs refuse;
adding such a source call requires expanding this reviewed projection.

The fixed main graph awaits its domain operations. Provider-body holds cover
headers that arrive before parsing ends. Each body/reader cancellation has a
separate retained effect: reader EOF cannot settle an underlying cancellation
promise. Native cancellation itself remains synchronous under the existing
admitted transport authority, preserving current read/EOF/releaseLock ordering;
the secondary durable observation cannot authorize another provider operation.
An unreturned invocation and its existing body record remain owned if that
observation latch is pending, lost or interrupted by restart. Cancellation
rejection marks the drain unresolved even when an existing helper catches it.
No independent standalone album worker
is imported by this change. `PartitionWorker`, its deferred consumption and its
native alarm remain the separate #0197/#0194 closure obligations. An acknowledged
wake does not drain the receiving object. An effective asset binding or another
capability with additional included writers also needs actual census/disposition;
the source cannot infer that external configuration is read-only.

## Required durable and independent ports

Both ports are trusted composition capabilities, never request data. There is
no default backend, schema installation, credential reader, provider client or
invented global Cloudflare drain API in this implementation.

- `MainEntryJournal.admit` atomically latches a unique invocation only while
  admission is open, bound to exact candidate digest, lifecycle and canonical
  positive signed-int64 generation TEXT. It must retain unknown admissions.
- `effect` durably latches each D1/provider/body/secret/wake/asset/repair effect
  before it runs and checks the invocation's original generation and authority.
  `settled` records the observed local fulfillment/rejection; rejection does not
  prove that a remote mutation failed. `returned` retains the handler outcome.
  Caught failures never erase the underlying records or establish qualification.
- `stop` irreversibly stops new admission across every effective instance,
  caller and old version covered by that actual adapter. It does not close D1,
  an object, secrets or any other store. It cannot revoke a still-required fixed
  domain result transaction merely because new admission is stopped.
- `MainEntryObserver.assess` independently establishes complete supported
  admitted-handler, pending external-result, required domain-result, old-callback
  and restarted-invocation disposition for every enumerated main family. The
  fixed deadline is passed to both stop and assessment. Their transports must
  honor it without internal mutation replay or a new window.

The independent boundary must inspect the complete actual pending state and
durable invocation/effect records across restarts, including unknown or failed
records. In the current source that includes native lifecycle operations and
connection/native-credential ownership, every OAuth temporary-slot phase and
pending replacement/retirement, Google refresh ownership, group refresh work,
and all admitted domain/authentication/status/rate/error/recovery transactions.
The synthetic observer independently reads native/OAuth/Google/group state on
the fixture's unwrapped SQLite handle; it does **not** implement the actual complete reader.
No `LIMIT 5`, first-row shortcut, empty local set, elapsed quiet time, zero count,
same-writer acknowledgement or receipt boolean proves complete actual coverage.
Unknown phases/schema, missing state, unavailable readers or unsupported old
execution disposition must refuse. A receipt's digest identifies evidence; it
does not authenticate independence, completeness or custody by itself.

The generation must be enforced atomically by the durable effect adapter.
Checking it once before an await, using only process memory, replacing a lost
journal, or reconstructing an empty tracker after restart does not meet this
port contract. There is no reinitialization, expiry unlock or reopen method.
In particular, a new instance and a later open storage generation cannot restore
an old invocation's effect authority. Supported actual disposition remains a
separate qualification obligation; source interfaces cannot manufacture it.

## Drain and failure semantics

Each instance admits at most 256 simultaneously active main handlers. One
explicit `stop(1..300000 milliseconds)` attempt irreversibly stops local
admission before awaiting its durable stop, all local admitted handlers and the
independent assessment. Monotonic checks surround those boundaries; late,
nonfinite and backwards readings refuse even if timer delivery is delayed.
The result is only a main-admission disposition. It supplies no storage-close,
common-interval, custody, capture, equality or reopen permission.

Already admitted fixed handlers may continue their original safety work while
draining. A pending native PATCH cannot be canceled to declare success. Its
actual lifecycle reconciliation and audit transactions must finish first. A
failed result write, lost journal receipt, thrown handler, unreadable independent
state, pending settlement or deadline exhaustion refuses the drain permanently
for this bridge. A late successful callback cannot turn that refusal into success.
The source leaves storage open for required settlement; it performs no control
transition. The later operator must not close stores after this refusal.

If an existing handler races its network/reader operation and returns while an
effect/body is outstanding, the drain refuses and retains the original admitted
authority for its required safety callbacks. It does not mark the invocation
returned, discard a pending result, abort a fixed transaction or declare that
work disposed. Independent recovery must account for that retained obligation.
An ordinarily returned invocation loses local capability authority, and durable
generation checks also reject orphan callbacks after generation advancement.

PMB-1's D1 mutation guards remain mandatory at the storage boundary; this bridge
is not their substitute. Required safety results settle **before** the separate
fixed operator closes any included store. Closure order, all object/alarm state,
managed-secret/configuration custody, old versions, runtime clock behavior and
qualified complete pending-state evidence remain #0187/#0182 obligations. The
exact future assembly and ordinary authenticated restoration check remain
#0199 work. Source-change pins must be refreshed there; the earlier frozen
source census does not silently cover these new bytes/exports.

## Synthetic verification

Using pinned Node 24.22.0 and native TypeScript 7.0.2 from the API root:

```text
node --test tests/main_entry_maintenance.test.mjs
node --test tests/installations.test.mjs tests/admin_core.test.mjs tests/flickr_oauth.test.mjs tests/album_create_repair.test.mjs tests/photo_thumbnails.test.mjs
node node_modules/typescript/bin/tsc --noEmit
```

Twenty-three focused tests cover every registered route's stopped entry, pre-registry
admin and whole schedule closure, actual current-installation auth/lookup and
security headers, admission/stop races and restart, delayed lookup/network/body,
actual native PATCH/mandatory lifecycle/audit settlement, result-write failure,
timeout with later required settlement, actual OAuth callback replacement and
scheduled temporary-slot retirement, actual album admin repair dependency,
throwing/pending journals, independent missing/mismatched coverage, stale
callbacks after generation advancement, late/backwards clocks, actual-thumbnail
reader EOF with pending/rejected cancellation, invalid-response body cancellation,
and successful synchronous disposal without an introduced releaseLock race. The existing
domain and authentication regression suites retain their own fixed semantics.
These are source/SQLite synthetic checks, not managed D1/native/hosted evidence.

No private records or credentials, runtime configuration, provider account,
DNS/native application, schema installation, registration, deployment, capture,
cleanup or reopening is accessed or authorized by this source work.
