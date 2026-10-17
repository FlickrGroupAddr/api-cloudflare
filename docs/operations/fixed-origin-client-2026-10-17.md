# Fixed-origin native client source

Date: 2026-10-17. Ticket #0041. Status: prepared source; native execution unqualified.

`probes/lightroom/FGA-FixedOrigin-v1.lrplugin` is a separately versioned,
major-15-only qualification bundle. Its original code composes the unchanged
release `ExistingPhotoClient`, `ConnectionCore`, `SharedReadTransport` policy
and bundled JSON implementation. It never imports the SDK secure store, touches
a catalog, creates a binding proof, or activates release capabilities. The
synthetic installation credential exists only in memory. The release
`SharedReadTransport.offline` constructor remains synthetic-only.

This source implements a finite future observation instrument. It does not
authorize loading, invocation, fixture provisioning, registration, deployment,
Flickr requests, credential access or a real-account run. Existing ten-scenario
receipts remain closed. [#0037's negative verdict](fixed-origin-feasibility-verdict-2026-10-16.md)
and later production gates remain unchanged. SDK15.3 `LrHttp.get` returns a
complete body; post-return checks cannot establish a receive-allocation bound,
hard total deadline, native GET abort or credential redirect protection.

The governing preservation boundary remains architecture
`docs/non-destructive-existing-photo-boundary.md` (Accepted). The detailed
`docs/hosted-thumbnail-candidate.md` remains Proposed under accepted ADR0061;
these files implement preparation and synthetic evidence, not its acceptance.

## Configuration and request boundary

The sole future input is `C:\Temp\FGA-fixed-origin-v1\target.json`, at most
16 KiB. No target or capability is committed. `Config.lua` owns the closed
schema, case set, source-file set and exact path/timeout table. The input binds
its run, ephemeral outer capability, finite case/mode, at-most-ten-minute UTC
window, exact source SHA256 values, Worker SHA256 and runtime-configuration
SHA256. Time comes from documented `LrDate.currentTime` converted from the SDK
epoch; this is not a monotonic-clock claim. Unknown keys, missing bindings,
wrong host, expired input and reused run input fail before a native call.

All four probe sources and four release dependencies are hashed in place before
execution. Lightroom must report major15/minor6. Receipt host metadata records
its numeric revision, SHA256 of build string and OS-version string, plus the
declared SDK15.3 target. This binds observations to the local host without
recording machine names or paths. The source does not infer a runtime SDK
version API that Adobe does not document. Hashes supplied for the hosted Worker
and configuration are declared execution-packet bindings; independent deployment
and receiver evidence must establish that those hashes describe the endpoint.

After validation, the exact target is moved to a run-specific used filename.
The isolated module loader uses the unchanged release files without modifying
`package.path` or `package.loaded`. `Qualification.dependencies` requires the
separate `SharedReadTransport.qualification` policy constructor; a missing seam
fails closed. The constructor's capability flags remain false.

The release client's normal synthetic bearer request reaches only the finite
translator. Immediately before native GET, the translator rechecks time,
cancellation, exact FGA origin/path, expected timeout and the single synthetic
Authorization header. It replaces that header with the ephemeral outer
`FGA-Qualification` capability and the run/case headers required by the isolated
wrapper. No arbitrary URL, destination, body or caller-supplied header crosses
this boundary. The capability never enters release client state or the synthetic
secure-store dependency. After a yielding GET it rechecks cancellation/expiry
before returning bytes. Ordinary verification reads are also translated.

Fault-mode authentication and discovery explicitly select the compliant `png`
preflight namespace and expect `qualification-png-install`. Only the exact
original single-photo thumbnail request selects the configured handler/edge
stimulus. Thus the release client's two verification reads and discovery cannot
be rejected or mutated by a stimulus intended for the image response. The
thumbnail then executes in the existing isolated selected-case namespace;
`invalid-auth` aliases bad-auth and edge cases use the isolated PNG handler plus
their edge replacement. This deliberate qualification-only selector translation
does not assert that the two synthetic namespaces are one production identity.
It resets no case, quota, authority fence or configuration. The closed path/mode
gate refuses browser paths in fault mode and single-photo paths in browser mode.
Browser, cancellation and stale modes use `ok` with the
finite two-page observation agreed with the isolated provider: page1 has two
rows and page2 has one, total3, linked revision1. The path table is authoritative;
the release client's default page size is unchanged.

## Future native observations

The later authorized packet must collect native observations from actual network
responses and correlate them with isolated handler/receiver receipts. Offline
Lua checks prove source behavior only. The following observations are distinct:

- **Complete page:** discover and validate the entire finite page; fetch and
  validate every corresponding image before creating any picture control.
  Inspect each image in Lightroom and explicitly select “All images rendered”.
  `pictureControls` counts controls; `observerConfirmedPages` records explicit
  human confirmation. Neither is an automatic decoder-success claim.
- **Navigation:** separately exercise Next, Previous and Cancel. Each modal view
  finishes before page cache removal; the next page is not rendered until all
  its images stage successfully. The run permits at most six page presentations.
- **Cancellation:** use the cancelable progress scope during a finite delayed
  response, or create the fixed `STOP` file. Check cancellation upon GET return
  and before staging/rendering. Record late-result rejection and owned-cache
  cleanup separately from backend abort/disconnect. SDK15.3 supplies no GET abort
  handle; cancellation is cooperative and may wait for the native GET to return.
- **Stale result:** the explicit `stale` mode advances its observation generation
  immediately after the first actual image response, then exercises the same
  generation fence before any cache publication. This is an intentional stale
  stimulus, not a claim of parallel navigation during an outstanding modal GET.
- **Cache lifetime:** one asynchronous function context owns every request,
  modal view and uniquely selected run cache. A single cleanup handler closes
  the adapter, clears response/config/module references and deletes that cache
  after task completion or error. It never deletes another run's cache. Verify
  the owned directory is absent, including cancellation/error paths. Cleanup
  failure is explicit and cannot become a successful native receipt.

`LrFunctionContext.postAsyncTaskWithContext`, `addCleanupHandler`,
`LrTasks.pcall`, `LrProgressScope.setCancelable/isCanceled`, `LrHttp.get`,
`LrDigest.SHA256.digest`, `LrApplication.versionTable` and file/path helpers are
documented in the locally licensed SDK15.3 API Reference. The source uses
yield-safe SDK protection around yielding work. No Adobe sample implementation
was copied. The source does not use an undocumented GET option or abort API.

## Receipts and verification

Terminal `receipt-RUN.json` is emitted from context cleanup, after cache-removal
attempt. It contains only fixed reason/counter/boolean fields, finite run/case/
mode IDs, hashes and bounded host version metadata. It excludes capabilities,
bearers, raw errors, paths, request/response bodies, URLs, photo titles and bytes.
Used target files still contain an ephemeral capability: keep that local runtime
directory private, exclude it from evidence exports, and remove the input under
the later packet's cleanup procedure. Terminal receipts never prove remote
cleanup or bind a measured allocation bound by themselves.

Focused verification uses `tests/test_fixed_origin_native_client.py` with actual
Lua5.1 and real release parsing. It exercises exact translation refusal,
yield/resume cancellation, complete-page navigation, partial-page cancellation,
stale-result suppression, false qualification flags and source parsing. Genuine
decodable PNG bytes are generated from original synthetic pixel data. The
licensed SDK15.3 compiler parses all four new Lua files. These checks make no
native, provider, Flickr, credential-store or catalog call.
