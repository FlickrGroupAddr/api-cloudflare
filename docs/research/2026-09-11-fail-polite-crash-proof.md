# Native fail-polite crash proof, 2026-09-11

Status: Bounded native crash proof passed; production fail-polite conformance is not passed.

The candidate adapter in `src/fail_polite.ts` keeps dispatch markers, permanent
exact-pair suppression, attempt history and result classification in the same
D1 database as admission and scheduling. The existing claim function now permits
recovery of an abandoned `attempting` head even when a write gate is paused.
Recovery can close the old attempt; new dispatch still requires enabled gates,
matching link/gate revisions and the current lease ID and generation.

The bounded crash proof uses the accepted manual-clock test boundary and a
controlled HTTP/HTTPS peer. It makes no real Flickr call and enables no public
mutation route. The proof fixture and its transport are absent from the public
Worker entry point.

## Tested behavior

One D1 batch starts a retained attempt. Membership and moderation observations
are attempt-specific append-only facts. A fenced marker transaction commits
before the adapter hands POST to the HTTP stack. Terminal classification commits
the block (when required), resolution, intent state, active-FIFO removal, event,
next-head due time and wake revision together. Code 6/7 produces
`moderation_submitted` plus a permanent block; unknown and ambiguous outcomes
produce `delivery_uncertain` plus a permanent block. Unknown codes also pause the
deployment write gate in the same transaction. Explicit 105/106 responses allow
a later fresh attempt, while code 3 is idempotent success.

A successor claims through the same function used by hints and sweeps. An
abandoned attempt without a marker becomes a safe retry requiring new reads.
An unresolved marker becomes permanent `delivery_uncertain`, with no transport
call during recovery. A committed terminal result remains unchanged. Actor
abort/recreation, duplicate admission, duplicate hints and sweeps preserve the
block and original attempt history. An injected rollback during recovery leaves
the marker unresolved until a later successor commits the block atomically.

All ten `FP-CRASH` boundaries run through both hint and sweep paths. The controlled
peer records request order and whether the marker exists when each POST arrives.
For the handoff crash, the controller waits for the peer's durable POST record,
then aborts the actor independently. Before/after D1 witnesses are retained in each ignored local proof report; observed POST counts are checked separately from terminal state.
The result-transaction injector forces a real D1 batch rollback after its block
statement. Actual Durable Object aborts replace the actor rather than catching
an exception and continuing with its memory.

## Evidence

Final source snapshot: `04941748d90eb5a930348ee03818e765db9ea38a`.
The public summaries retain check IDs/results and SHA2-256 hashes of every participating source, migration,
controller and dependency lockfile. The tested `src/fail_polite.ts` differs from
the Git blob only by newline normalization; normalized bytes were compared.
Native TypeScript 7.0.2 validation ran before each provider bundle.
Public summaries omit row witnesses, fixture identifiers, provider resource
identifiers and URLs. The complete synthetic reports remain in ignored
`.coordination-runs/` directories, bound by their published SHA2-256 digests.

- [Hosted proof](../evidence/fail-polite-hosted-2026-09-11.json): **88 checks passed**, including all ten crash boundaries through both entry paths, real HTTPS peer observations, real Cron dispatch, and exact archive/restore of all 19 selected domain/metadata tables.
- [Local proof](../evidence/fail-polite-local-2026-09-11.json): **84 checks passed**, with zero non-fixture outbound calls.
- [Mutation evidence](../evidence/fail-polite-mutations-2026-09-11.json): **six of six intentional defects detected**, each with a passing unmutated control.
- [Admission regression](../evidence/coordination-admission-regression-2026-09-11.json): **31 local checks passed**; [scheduling regression](../evidence/coordination-scheduling-regression-2026-09-11.json): **30 local checks passed** with migration 0004 installed.
- Native TypeScript, Ruff checks/formatting and Pyright passed; **76 Python tests** and **18 Node tests** passed.
- [Cleanup](../evidence/fail-polite-cleanup-2026-09-11.json): the disposable Worker, its Durable Object namespace and both D1 databases were removed and absence verified. No production resources changed.

The hosted compatibility date was 2026-09-11; local workerd used 2026-07-30.
Cloudflare rejected the read-only `sqlite_version()` diagnostic as unauthorized,
so an exact hosted SQLite engine revision is not claimed. The archive comparison
used the actual deployed D1 engine, checked every selected row and schema object,
validated foreign keys, and verified an ordinary history delete was rejected.

Six isolated local mutations each passed an unmodified control and failed the
intended behavior assertion: omitted marker, retryable unknown result, replayable
abandoned dispatch, inclusive freshness boundary, terminal result without its
block, and missing marker-delete guard. The runner restored original source
bytes after every mutation. This is bounded mutation evidence, not the complete
production inventory.

The initial local attempts exposed fixture defects: Node could not consume the
Miniflare Request object directly, and the rollback injector initially tracked
unbound rather than bound D1 statements. Those runs remain failed in private
working evidence; the adapter boundary and injector were corrected before the
final local/hosted runs. No mutating test case was retried into a pass.

## Production limits and next integration work

Implementation ticket #0018 tracks this full release gate, with explicit
dependencies on #0006, #0013, #0015, #0016 and #0017.

The [accepted full suite](https://github.com/FlickrGroupAddr/architecture-design/blob/286b9727ea9c8beffbc57505c9187f04a2dd44d0/docs/testing/fail-polite-worker-database-conformance.md)
still controls release acceptance. This bounded proof does not satisfy its whole
case inventory, production-adapter topology or full mutation gate:

- #0013 still owns deployed Workers monotonic freshness. The 999,999/1,000,000
  microsecond comparisons here use an injected manual clock; they do not prove
  the native clock advances during CPU-only work or suspension.
- Production OAuth signing/transport, the production rate allocator, exhaustive
  malformed-protocol limits, retry/backoff policy and all transport-proof classes
  remain integration work. The fixture uses a disposable bearer, deterministic
  three-slot reservation and synthetic identifiers.
- The public admission/status/admin/lifecycle routes must use the final adapter
  and pass every bypass test. The existing read-only public API remains the only
  implemented production slice.
- The crash mechanism here is Durable Object abort/recreation. A separately
  terminated operating-system process and full deployment-restart coverage are
  not claimed.
- The complete accepted case/mutation inventory and fail-closed CI release gate
  must pass for the exact deployable artifact and migration head before enabling
  real `flickr.groups.pools.add`.

D1 remains the sole durable authority; no transaction across D1 and Durable
Object storage is assumed. These results establish no need for an AWS service.
The private runtime trust boundary remains ADR 0051. Existing development-tool
advisories and the local/hosted runtime-date difference remain documented in the
foundation and scheduling reports; this change did not update the toolchain.

See [reproduction and cleanup](../../probes/coordination/README.md).
