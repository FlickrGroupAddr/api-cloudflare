# Production matrix handoff — 2026-09-14

**Current status:** The owner approved the synthetic restore and continuation.
The old hold is resolved. See [complete suite qualification](2026-09-14-complete-suite-qualification.md)
for current results, the complete command and CI acceptance. Sections below record earlier checkpoints.

## Earlier handoff (resolved)

Cards **#0018 Complete the production fail-polite conformance gate** and **#0002
Prove the Cloudflare-native hosted foundation** are handed off to **Needs Terry**.
The rollup has no other unfinished foundation child. Registrar-transfer #0019
remains separately Blocked; this work does not change its October 13 date.

The specific owner action is permission to **copy generated synthetic snapshots
between newly created, empty D1 test databases in the FGA Cloudflare account**.
Automatic approval review rejected FP-BLOCK-003 three times, first as a potentially
destructive hosted restore, then as sensitive snapshot egress/remote mutation.
The last rejection said the transcript did not establish specific authorization.
The runner now checks run ownership, fresh server-side name/UUID identity, target
emptiness, and synthetic source identities. No production restore or production
snapshot is involved. No rejected operation was run indirectly through CI or a
different tool. The existing CI credential is valid; no new token is requested.

This is an execution permission handoff, not an architecture waiver or full release
acceptance. The engineering listed below still remains after permission is granted.

## Implemented and verified

- The new matrix builds the optimized production artifact and uses its real
  authentication/admission, OAuth transport, D1 allocator, retry, status and native
  lifecycle paths. The external driver supplies controlled faults, time, HTTPS
  peer responses and fixture setup. It introduces no live application route.
- All 30 membership/preflight/result IDs passed locally and against real hosted
  D1. All six queue IDs passed through actual admission and coordinator paths.
- All ten crash IDs passed on hint and sweep recovery after independently killing
  the owned Node/workerd process tree, waiting for the production lease expiry,
  and restarting the same artifact/storage. These are local Worker process
  proofs, not claims to terminate a Cloudflare host.
- Nine permanent-block IDs passed across code 6, code 7, unknown-result and
  unresolved-dispatch seeds. FP-BLOCK-005 additionally passed with real hosted D1
  and native Secrets Store slots through disconnect, relink and Plugin Code
  rotation. The private service bridge and six fixture slots were cleaned up.
- API and lifecycle Flickr calls now share the same key-wide D1 rate window as
  dispatch reservations. A proven pre-fetch abort remains safely retryable and
  refunds only the proven-unused add slot. A synchronous or asynchronous fetch
  failure remains uncertain; an upstream error cannot forge the zero-handoff proof.
- Restore target guards reject an unowned, renamed or nonempty database before
  import. Local regression tests cover those rejection boundaries.
- Validation: 120 Python tests, 112 Node tests, native TypeScript, Ruff, Pyright,
  generated API consistency, and all six existing bounded mutation controls.
  Every bounded mutant failed its intended behavioral assertion; working sources
  remained unchanged. These six are not the required full 28-class mutation suite.

The [sanitized component receipt](../evidence/production-matrix-progress-2026-09-14.json)
records report hashes, case inventory, artifact identity and cleanup. **55/56
observed IDs across component runs is not one qualified release run.** The receipt
has `fullConformancePassed: false` and cannot satisfy the release verifier.
Local Miniflare runs use compatibility date 2026-07-30; the live configured date
is 2026-09-11. Reports do not claim parity with the newer hosted runtime.

## Exact continuation

1. Obtain the specific synthetic hosted restore permission above. Keep the
   existing execution hold on remote snapshot imports, including CI, until then.
2. Run the integrated restore case with the existing dedicated CI credential:

   ```powershell
   uv run --frozen python -m scripts.production_matrix --environment hosted-db --native --token-file C:\Temp\fgaci.txt --section blocks --block-ids FP-BLOCK-003
   ```

   It must reject the snapshot predating a permanent block and session revocation,
   restore the current protection snapshot into a separate empty target, preserve
   native-generation behavior, and reject the revoked session after restoration.
   The code has not yet passed this integrated hosted case; address implementation
   failures without weakening the current-snapshot barrier.
3. Complete the full 28-class production mutation runner against the accepted
   inventory in `scripts.fail_polite_release.MUTATIONS`. Reuse the now-working
   local provider fixtures for deterministic negative controls, and count only
   intended behavioral/database assertion failures. Compilation/infrastructure
   failures are not successful mutant detections. The older six-case runner is
   a regression check, not a substitute.
4. Run the complete positive matrix on one committed candidate and required
   hosted/native adapters. Collect fresh ADR0058 provenance within that run;
   preserve configuration, migration, artifact and adapter hashes, recovery and
   seed witnesses. Fill the complete schema-version-2 evidence, not a collection
   of partial reports relabeled as full conformance.
5. Wire that generated evidence/artifact/configuration into the manual CI verifier,
   run CI, and move #0018 and #0002 to Ready for Review only when all requirements
   pass. Keep failure/omission/skip handling closed.

Reproduction for the unblocked local sections is in
[`probes/release/README.md`](../../probes/release/README.md). Raw run directories
remain ignored and private. Do not publish raw tokens, secret bindings, archived
rows, OAuth headers or private operator logs.

## Deployment boundary

No production Worker deployment or real Flickr call was performed during this
matrix work. The last verified live flags remain ADMIN=1 and READ=INTAKE=DISPATCH=0,
with both write gates paused. This checkpoint does not enable Flickr group adds,
insert a release receipt, or change the accepted native-first direction.
