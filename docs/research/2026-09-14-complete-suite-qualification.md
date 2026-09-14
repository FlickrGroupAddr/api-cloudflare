# Complete suite qualification â€” 2026-09-14

Terry approved all recommendations following the explicit synthetic hosted restore
request. That execution hold is resolved. #0018 and #0002 are In Progress for final
qualification; no additional credential or architecture decision is needed.

The integrated hosted FP-BLOCK-003 restore passed all four protection seeds. All
56 stable IDs now have observed component passes. The full 28-class mutation
runner passed its unmodified controls and detected every deliberate production
source mutation through its intended behavioral/database assertion. Compile and
infrastructure failures never count as detected mutations.

The exact optimized module also passed on Cloudflare compatibility date 2026-09-11:
normal prepared handoff, protection after redeployment, and zero handoff after
native I/O refreshes the clock beyond the freshness boundary. The stable local
independent-process adapter is separately identified as Miniflare 2026-07-30.
The verifier now requires the matching hosted module digest/date and successful
hosted observations. No prerelease runtime was substituted.

The restore harness needed more than the engine-provenance reader's default
64-KiB response budget as the synthetic archive grew. The final import keeps one
query transaction and a bounded 4-MiB response allowance for owned test D1 queries.
The bulk-file experiment failed foreign-key constraints and was discarded.
Default provenance reads remain limited to 64 KiB. Regression tests cover both
budgets, oversized responses and invalid limits. Owned test resources were removed.

## Complete command and CI

```powershell
uv run --frozen python -m scripts.production_release_suite --token-file C:\Temp\fgaci.txt
uv run --frozen python -m scripts.fail_polite_release --evidence .coordination-runs/production-release/evidence.json --artifact .coordination-runs/production-release/worker.js --config .coordination-runs/production-release/configuration.json
```

The complete command requires committed inputs, runs every stable case against
hosted D1/native secret fixtures, verifies the hosted module, cleans up, runs all
28 mutations, obtains fresh ADR0058 provenance and emits exact-candidate evidence.
It refuses missing/failed cases, omissions, changed inputs, mismatched artifacts,
missing infrastructure or incomplete cleanup. Ordinary component reports remain
partial and cannot satisfy the full gate.

Manual CI retains all prior regression, independent-stop and hosted-restore checks,
then invokes this complete suite and the final verifier with explicit file paths.
An initial broad workflow rewrite was rejected by automatic review. The narrower
additive change preserving all existing protections was approved. A proposed
module/configuration artifact upload was also rejected; the accepted safer version
retains **only the sanitized JSON receipt** as `fail-polite-production-evidence`.
Raw provider logs, source snapshots, tokens, module and configuration stay inside
the job. The module and configuration are used for verification before job exit.

**Observed component success is not yet final qualification.** The acceptance
record is the complete command plus the manual GitHub Release validation run and
its sanitized artifact. The board records the tested commit/run and any failure.
Move #0018/#0002 to Ready for Review only after those gates pass. Registrar-transfer
#0019 remains separately Blocked.

The audit guard case now also checks an actual audit entry created through the
registered Plugin Code detail route and verifies controlled index migration,
rollback of a failed migration, and restoration of the original schema. All four
seeds passed locally. This does not dismantle a production guard.

No live application deployment, production restore or real Flickr request occurs
in this suite. Live dispatch stays disabled; the synthetic hosted endpoint uses
an expiring bearer guard and is removed after each run.

## Native adapter follow-up

The first complete CI attempt stopped at the safe-retry/order case. The private
native-secret bridge now uses standard service-binding fetch calls instead of
custom RPC getters. Public routes stay disabled and each named entry point still
reads one fixed native binding. A fresh hosted reproduction passed with zero
native-read failures: two reads and no add in the rejected attempt, followed by
fresh reads and one synthetic add on retry. Both cleanup checks passed.
Failure receipts now retain sanitized case witnesses for diagnosis.

The canonical test contract now records the executable repository/command,
engine disclosure policy and CI artifact name required by its implementation
section. No stable case, mutation or safety requirement changed. Its reviewed
fingerprint, public mirror and runtime constant were synchronized together.
Negative mutation controls run locally with production migrations and the same
unmodified control module; the positive storage matrix uses managed D1. Those
runtime scopes are explicit in the final receipt.
