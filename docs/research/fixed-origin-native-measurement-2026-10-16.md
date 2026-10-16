# Fixed-origin native measurement feasibility

Date: 2026-10-16. Ticket #0037. Status: research and proposed measurement method;
no native measurement, transport qualification, contract acceptance or live authority.

The conventional independent Windows process counters can characterize memory
use during a finite native GET matrix. They cannot measure or enforce an exact
per-response allocation limit. SDK15.3 supplies a complete response string and
per-phase timeout, with no documented GET abort handle or receive-byte cap.
The remaining qualification must combine limited host observations with proved
bounds on the actual trusted endpoint and effective HTTPS edge. This note
does not establish those bounds or permit dependent live promotion.

## Authority and target

Canonical architecture `AGENTS.md` and `docs/README.md` control authority.
Accepted [ADR0061](../../../architecture-design/docs/decisions/0061-develop-bounded-hosted-thumbnails.md)
authorizes development and qualification; its [thumbnail candidate](../../../architecture-design/docs/hosted-thumbnail-candidate.md)
remains Proposed. The candidate requires actual endpoint/edge and supported-host
allocation, timeout and redirect evidence; it trusts the private backend/edge,
rather than requiring protection against an arbitrary replacement server.
The [existing intake contract](../../../architecture-design/docs/existing-public-photo-intake.md)
retains its other accepted boundaries. No source below amends them.

Use the [current adapter map](../design/group-workflow-adapter-map-2026-10-16.md):
release 0.2.0.7, Lightroom Classic15.6 build `202609251514-f839cde9`, SDK15.3
build `202604090947-8f3672ed`. The [fixed-origin plan](../operations/existing-photo-fixed-origin-plan-2026-10-16.md)
owns the exact proposed route/case/lifecycle scope. The [prior native result](../evidence/existing-photo-native-network-run-2026-10-16.md)
is finite disposable-origin GET characterization only; no new experiment ran here.

## Native contract and observable claims

Primary SDK references are the local Adobe SDK15.3 `API Reference/modules/`
files under `architecture-design/vendor/LrC SDK/15.3/`:

| Obligation | Documented interface and permissible conclusion | Remaining limit |
| --- | --- | --- |
| Receive allocation | `LrHttp.html`, namespace and `LrHttp.get`: GET returns a response-body string and header table; network error returns nil plus information that may include partial_data | The string exists before a post-return length check. No documented streaming callback, receive limit or preallocation ceiling; no documented native copy/allocator bound. Count partial_data separately without retaining bytes. |
| Timeout | `get(url, headers, timeout)`: timeout is the wait in each connection phase before canceling | `15` is not a total 15-second deadline. Record observed duration, native error category, returned and partial lengths. No documented phase decomposition or hard real-time maximum. |
| User cancellation | `LrProgressScope.html` cancel/isCanceled: task must poll the signal and stop; `LrTasks.html` tasks cooperate on the host UI thread | Poll before/after I/O and suppress publication after cancellation. No GET handle is exposed to abort an in-flight call. A documented cancelled error code alone supplies no caller-operated cancellation mechanism. |
| Client timing | `LrDate.html` currentTime supplies Cocoa wall seconds | Record observed wall-time differences, finite/backward/expired checks and clock limitation. No SDK guarantee of monotonicity, millisecond accuracy or detection of every clock adjustment. `os.clock` CPU time cannot time yielding I/O. |
| Redirects | No documented GET redirect-policy parameter | Observe only enumerated statuses and targets using synthetic markers at the actual origin. A result for one redirect does not qualify another status, route or edge rule. |
| Backend abort/disconnect | Separate backend instrumentation and effective provider configuration own these observations | Client timeout/closed UI does not prove disconnect delivery, canceled upstream work, or absence of a response already sent. Missing observations remain unknown. |

SDK POST upload callbacks provide outgoing data, not a documented GET response
stream. This GET method does not qualify POST; the separate POST tickets retain
their own scope.

The prior result returned a 262145-byte image and a 262145-byte error and reported
timedOut at 16056 observed ms. This establishes neither peak allocation nor
active cancellation nor a total deadline. Its observed cross-origin marker
absence is restricted to that controlled redirect.

## Independent process-memory observation method

Select conventional Windows Performance Monitor process counters, collected
outside the Lightroom Classic host with a finite `Get-Counter` invocation at
one-second intervals. Microsoft documents the instrumentation, localized counter
names, access restrictions and finite MaxSamples in [Get-Counter](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.diagnostics/get-counter?view=powershell-7.5).
This is a selected research method, not an implemented or locally validated collector.

For the later reviewed packet, identify the exact host PID, process start
identity and counter instance; include ID Process with every sample and refuse
instance/PID changes. Resolve localized names; verify counters and access before
native execution. Scope collection to that process, keep unrelated activity
quiet, and collect a finite baseline, one labeled case at a time, and a recovery
window. Set the exact sample count/duration within the reviewed execution window.
Retain numeric samples, validity/status, nominal and actual sample gaps, case
windows and sanitized host/tool provenance only. Do not collect memory dumps,
process command lines, image data, catalog information or other applications'
counters. Unavailable counters, gaps or interfering host work make the affected
memory result inconclusive; do not substitute returned lengths.

| Metric | Meaning | Precision and attribution limit |
| --- | --- | --- |
| Private Bytes | Whole-process private committed memory | Byte-valued OS accounting; not exact bytes allocated by GET or Lua. |
| Working Set | Current resident process working set | Residency varies independently of logical allocation; shared resident memory is included. |
| Page File Bytes Peak | Lifetime process peak private commit | A previous catalog/render/UI peak can dominate the entire matrix; it cannot be reset per case by subtracting the baseline. |
| Working Set Peak | Lifetime peak resident working set | Same lifetime/attribution limitation; not a receive-buffer high-water mark. |

The mappings come from [Memory Performance Information](https://learn.microsoft.com/en-us/windows/win32/memory/memory-performance-information).
The [PROCESS_MEMORY_COUNTERS_EX](https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-process_memory_counters_ex)
definition supplies private commit, resident working set and lifetime peak
semantics. For a collector that needs direct PID handles,
[GetProcessMemoryInfo](https://learn.microsoft.com/en-us/windows/win32/api/psapi/nf-psapi-getprocessmemoryinfo)
is the documented equivalent; it requires query access and checked failures.
No custom native collector is justified for this first characterization.

Interpretation limits are deductions from these process-level semantics:
one-second samples can miss subsecond allocations; faster sampling would still
not prove every transient allocation. Byte units do not supply byte-accurate
per-response attribution. Heap reuse can hide a buffer allocation in unchanged
commit, and frees/other activity can offset increases. Native networking, TLS,
Lua, decoder, catalog and UI allocations coexist. A 256KiB-scale response may be
indistinguishable from host noise. Report baseline ranges and observed changes
without naming the difference the response allocation. Lifetime peaks add useful
process context but do not solve attribution. No finite counter run proves a
universal upper bound on future host memory.

An external [QPC/Stopwatch interval clock](https://learn.microsoft.com/en-us/windows/win32/sysinfo/acquiring-high-resolution-time-stamps)
can time an observer's own events independently of UTC. It does not add a
monotonic SDK clock or identify exact GET entry/return across processes without
an independently reviewed correlation mechanism. Process-sample timing must not
be reported as subsecond native-request timing. Do not introduce an external
helper, debugger or heap instrumentation merely to imply a stronger guarantee.

## Feasibility verdict and return-to-design boundary

This method supplies independent **process-memory observations**, with explicit
sampling and attribution limits. It supplies no per-response allocation cap,
no client receive enforcement and no active native GET cancellation. None of
those stronger claims follows from SDK signatures or returned lengths.

The candidate's trusted-endpoint approach is not disproved by that limitation:
it deliberately places bounds at the private backend/edge. Qualification still
needs the edge half of #0037 to identify a demonstrably bounded effective
path for success, ordinary errors, provider errors and redirects, plus finite
supported-host observations. The proposed 4096-byte application-error collector
threshold is not evidence of an existing provider-error cap. The accepted
malformed-target/duplicate-Authorization early-400 exception is narrowly scoped,
not an exception for all errors. Do not invent a numerical allowed host-memory
overhead or mark allocationBoundProven from a flat counter graph.

If the effective endpoint/edge cannot enforce the candidate's required bound,
or later host observations cannot substantiate the scoped qualification claim,
stop dependent fixed-origin live promotion and return to design with the exact
unmet obligation, effective path/configuration evidence, finite observations
and their limits. If an exact per-response allocation ceiling or hard total
deadline is required, the documented GET interface and this method do not
establish it; that requirement needs a supported design resolution before a
dependent run can claim qualification. Record a concrete design decision rather
than relabeling aggregate observations as enforcement. This research implements
no replacement and accepts no waiver.

Verification: read-only authority, current source/evidence and primary SDK/
Microsoft documentation inspection. No runtime tests, counters, native launch,
credentials, provider requests or code changes were performed.
