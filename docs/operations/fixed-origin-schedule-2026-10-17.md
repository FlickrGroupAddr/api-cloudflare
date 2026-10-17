# Fixed-origin finite schedule accounting

Date: 2026-10-17. Ticket #0148. Status: offline accounting and rejection witness;
**NO-GO for execution**. This document does not accept a changed target schema,
waive an observation, authorize native input or pass qualification.

The [execution packet](fixed-origin-execution-packet-2026-10-17.md) owns the
reviewed limits and unresolved artifact gates. The source examined here is
`Config.lua`, `Qualification.lua` and `Run.lua` under
`probes/lightroom/FGA-FixedOrigin-v1.lrplugin`, the unchanged
`ExistingPhotoClient.authenticatedRequest`, and the lifecycle quota/receiver.
The 20 canonical handler cases and 10 edge cases remain required. `ok` and
`invalid-auth` are aliases; they add no separate observations.

## Current source cannot fit

Each fault invocation first discovers its PNG preflight page: credential
verification plus discovery. Its selected thumbnail then performs credential
verification plus thumbnail. Thus every canonical fault costs four admitted
FGA requests even though only one selects the fault. Thirty faults alone cost
120, exceeding the exact 96 budget. A target selects one case/mode, and moving
it to the run's used-target path prevents another invocation for that run.
Thirty-three required fault/browser/cancel/stale invocations therefore cannot
consume the single reviewed target. No reset, second run or retry is allowed.

| Known work | FGA admission upper budget | Receiver/report admissions | Native invocations |
| --- | ---: | ---: | ---: |
| 30 canonical fault invocations | 120 | 0 | 30 |
| Browser pages 1, 2, 1 (Next, Previous, then finish) | 16 | 0 | 1 |
| Cancel during first thumbnail GET | 4 | 0 | 1 |
| Stale first thumbnail result | 4 | 0 | 1 |
| Five same-origin redirect arrivals | 5 | 5 | 0 |
| One independently reserved aggregate report | 1 | 1 | 0 |
| Known subtotal | **150** | **6** | **33** |

A first browser page costs six requests (discovery pair plus two thumbnail
pairs), second page four, returned first page six. The current loop permits six
presentations and could cost 30; the 16 bound above requires the exact three-
presentation action order. Unexpected navigation must abort, never consume an
unbudgeted loop. Cancellation/stale reserve all four requests even if a stop
occurs earlier. Unused admission cannot be reassigned. Redirect arrivals reserve
all five even when the SDK does not follow; missing arrivals remain an
observation, not permission to retry. The report reserves both admissions
separately from cancellation; inability to report remains inconclusive.

These totals are **incomplete known-work budgets**, not an execution-ready
estimate. Additional required live work is not assigned zero:

- Actual PNG/JPEG/boundary image rendering and explicit human confirmation;
  the fault path only receives bytes and never creates a picture control.
- Backend abort/disconnect observation, distinct from cooperative cancellation;
  the SDK GET has no demonstrated abort handle.
- Exact temporary and rollback public HTTPS route-conformance phases,
  including the actual effective edge and artifact binding.
- Fresh provider capture/readback, synthetic provider restoration cases A/B,
  ordinary authenticated safe reads, production-state continuity and both
  paused durable gates, disable/restore/delete and independent readbacks.

Public routing probes and provider management/readback are different traffic
classes from admitted qualification requests. They still require a finite
inventory and their own authorization/budgets; they are not free operations
outside this ledger. Provider restoration A/B needs separate proposed resource
scope. No account request was made to determine their counts here.

## Offline versus live evidence

Offline source-matrix tests, synthetic Lua transport tests, compiled inventory,
configuration projection and development HTTP conformance can be prepared
without live admissions. Their pass never replaces public HTTPS conformance,
actual native rendering, host cancellation, backend disconnect or restoration.
Artifact digest calculation is offline; binding the digests to a hosted
receipt needs the actual same-artifact hosted phase. All five route phases
remain mandatory for both temporary and rollback configurations.

The ten-minute inner limit starts from one common start. The outer twenty
minutes includes that interval and a ten-minute cleanup reserve; it is not
another ten minutes of qualification. Admission/publication must recheck
expiry across awaits. Native 30/15-second connection timeouts and the one
16000-ms upstream stall do not prove a hard total deadline. Human observation
has no demonstrated bounded duration. A deadline crossing stops further work
and records incomplete evidence; expiry does not prove cleanup. No plan may
restart the clock, use cleanup reserve for cases or assume cleanup completes
within it.

## Executable rejection and proposed amendment

`scripts/fixed_origin_schedule.py` is a pure offline, closed accounting witness.
It imports no network, provider, native, credential or lifecycle adapter. Run:

```console
uv run --frozen python scripts/fixed_origin_schedule.py
uv run --frozen python scripts/fixed_origin_schedule.py --profile proposed-shared-discovery
```

Both intentionally exit 2 and emit sanitized `no-go`. Validation rejects a
missing/unknown case, changed cost/classification/limit, extra target/run,
retry/reset, forged source support or authority and altered report/deadline
reservation. Known current totals are 150/6; a proposed shared-discovery
program yields 96/6: existing success fault bodies supply three mandatory decoder observations without another GET, and four admissions are earmarked for an independent backend disconnect driver. Remaining provider/ordinary live obligations are explicitly unbudgeted.
Neither profile can produce execution authorization or a qualification pass.
Tests are owned in `tests/test_fixed_origin_schedule.py`.

The exact reviewable alternative is canonical
`architecture-design/docs/proposals/fixed-origin-schedule-amendment-2026-10-17.md`.
It preserves 96/16 and both clocks; its single-target batch requires new source,
source-hash/schema review and resolution of all unbudgeted observations before
an execution-ready schedule exists. The current packet/source remains the
NO-GO baseline. #0044 NO-GO, #0037 unqualified, #0043 negative restoration and
#0045's bounded disposition remain unchanged.
