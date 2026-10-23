# Native invocation and protected-delivery source

This module implements the native controller/custodian software boundary. Its
tests use temporary synthetic state and patched native interfaces. They establish
no actual native, managed-store, credential, filesystem or clock qualification.

`NativeController` accepts the exact `NativePositionalSender` class. It preserves
the adapter's immutable intent, original root/headroom/window, one-dispatch
marker, unknown outcome and successor CAS lifecycle. It selects only
`fixed_update_with_exact_count_positional_v1`; historical single-statement and
named-source controllers remain separate.

For each transition, the controller issues full independent PRIMARY control and
schema reads before mutation and after the exact returned one-row batch receipt.
It retains the returned rows and request/response evidence. Only a timely actual
return from the final journal `settle(..., confirmed)` call followed by current
source/clock/sender checks can produce a confirmed result. A journal phase,
current target readback, supplied `Result`, synthetic wrapper or JSON proof flag
cannot produce a confirmation through this interface.

`ReturnedInvocations.invoke` calls that concrete native controller itself. Before
calling it, the custodian commits a unique reference and intent claim to its
separate external SQLite file. Claims and returned receipts are append-only;
missing state never provisions automatically. A lost claim ACK, crash, missing
native result, lost final journal ACK or failed check cannot replay that claim
or reconstruct a receipt. Only the actual timely returned confirmed result and
its complete evidence are retained. Reopening the same retained file preserves
claims, receipts and a persisted clock watermark. `read` verifies the exact
intent/result, fixed batch manifest, source schema, full four-read evidence and
packet/target binding before supplying an adapter `ConfirmedReceipt`.

`ProtectedCredential` is inert at construction. Its trusted inputs are the exact
independently authenticated delivery-review path and SHA2-256 pin, packet pin,
target, source graph, clock and finite deadline. The reviewed record binds the
exact credential file and fingerprint plus the grant and custody artifacts.
The sender cross-checks those references against its independently retained
native admission before activation. The loader checks non-secret evidence
before reading the exact token bytes; it does not search, trim, discover,
refresh or retry. A nonblocking lock atomically consumes the delivery before any
evidence or protected read. Competing callers refuse immediately, and failed
loads remain spent. No secret
bytes enter custody receipts or error messages.

Actual trusted-review provenance, current effective grants/target, source oracle,
same-connection transaction/rollback/commit/no-interleaving behavior, independent
complete PRIMARY semantics, accepted finite bounds, all-writer closure, stable
cross-process clock domain, protected-path/ACL/rollback/power-loss custody and
release gates remain external positive requirements. File hashes authenticate
identity under those trusted inputs; they do not establish those facts. An
operator must not construct native admission from these tests or source-only
records. No new service or privilege is required by this implementation.
