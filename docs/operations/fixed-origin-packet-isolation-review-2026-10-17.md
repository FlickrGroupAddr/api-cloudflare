# Fixed-origin packet: independent isolation review

Date: 2026-10-17. Ticket #0044. Status: independent source/offline review;
**no-go for deployment or native execution**. No production qualification.

## Reviewed authority and exact artifacts

The card was In Progress before this review. The source baseline was clean
API commit `dc7234ac59eda9acc74972268296abbc251efae8`; canonical authority was
the accepted repository policy, ADR0061 and the accepted non-destructive
existing-photo boundary. The detailed hosted-thumbnail candidate remains Proposed.
These authorities permit development and qualification preparation; source
completion and independent review do not accept the production contract.

The exact captured ordinary dispatcher is SHA256
`f1cef97fe6e1e62b5ff2b57f7e11516423974e756011750feb1aebe3abb13e6d`.
The actual candidate executed by the offline tests remains the separately approved
`b599ca828d2a645b686aca0354d6c8ee2c2a0250` bundle, SHA256
`c1edd7e5e721119030085c9c0705de5d2f3a32b9cffc6bbed56f363df3432e36`.
Thus dc7234a identifies the reviewed wrapper/composition/native-source baseline;
it does not identify a freshly bundled candidate or deployed Worker.

The private fixture was `private-evidence/0038/parent-final-20261016` under the
FGA workspace. Tests hash the two modules and every recorded candidate source
input before execution. Raw capture, configuration and synthetic fixture outputs
remain outside Git. No token or real secret was read.

## Isolation and authentication result

No material source isolation defect was found in the reviewed boundary:

- [wrapper.mjs](../../probes/fixed-origin-isolation/wrapper.mjs) delegates an
  ordinary request and its original environment directly to the exact captured
  dispatcher. Qualification controls select a separate closed branch. The
  capability uses its own exact scheme, run and case; unsupported controls,
  lifetime, method, body/framing and complete observable URL fail closed.
- [handler_cases.mjs](../../probes/fixed-origin-lifecycle/handler_cases.mjs)
  strips client headers before the actual candidate receives a newly constructed
  synthetic Bearer request. The explicit frozen synthetic environment contains
  no production environment lookup, spreading, secret reader or real fetch.
  Its fixed in-memory responder checks exact discovery operation/parameters,
  synthetic owner and credential-free image destinations. Twenty independent
  namespaces retain final installation/link/grant mutations across reconstruction.
- [composition.mjs](../../probes/fixed-origin-lifecycle/composition.mjs)
  keeps ordinary dispatch outside quota/receiver work. Selected calls use durable
  admission and expiry/abort/publication fences. Receiver paths are separately
  reserved and require exact URLs; a production Bearer is refused before
  forwarding. Only Authorization and the explicit synthetic canary observation
  cross its constructor-injected receiver service binding.
- [SharedReadTransport.lua](../../clients/lightroom/FGA-LrC15.lrplugin/SharedReadTransport.lua)
  lines 297-389 pins the qualifier to its sole canonical synthetic current
  credential. A pending candidate, changed current credential, inactive context,
  cancellation or closed adapter permanently refuses further work. Its eight
  exact fixture paths, expected timeouts and single Authorization header prevent
  arbitrary URL, photo, query, revision and header input. Production constructors
  refuse and every capability/qualification flag stays false.
- [Qualification.lua](../../probes/lightroom/FGA-FixedOrigin-v1.lrplugin/Qualification.lua)
  translates only those finite synthetic requests into the outer ephemeral
  capability, rechecking cancellation and expiry around GET. Fault authentication
  and discovery use the compliant PNG namespace; only the thumbnail selects the
  fault namespace. This deliberate synthetic split is not a production identity
  equivalence claim.
- [Run.lua](../../probes/lightroom/FGA-FixedOrigin-v1.lrplugin/Run.lua)
  hashes the fixed local source set, requires Lightroom15.6, consumes a bounded
  exact target once and owns its cache in one asynchronous function context.
  Cleanup and the closed receipt omit credentials, URLs, payloads and raw errors.
  SDK/file I/O belongs to this prepared native entrypoint; no native execution
  occurred during review. Worker/configuration hashes are declared bindings,
  requiring independent endpoint evidence before they can describe a deployment.

The VM adapter is instrumentation for trusted pinned source, not a security
sandbox for hostile executable code. Exact observable URL equality cannot recover
wire syntax normalized before Request creation. Ordinary-route sample tests are
bounded refusal-path evidence; the direct unchanged-dispatch source seam is the
basis for the delegation conclusion.

## Concrete packet blockers and measurement limits

**The full current native fault matrix does not fit the one-attempt FGA quota.**
Each fault-mode stimulus uses four FGA admissions: installation verification,
discovery, another installation verification, then thumbnail. The actual source
is [ExistingPhotoClient.lua](../../clients/lightroom/FGA-LrC15.lrplugin/ExistingPhotoClient.lua)
lines 290-315; `test_every_fault_reaches_only_its_thumbnail_after_png_preflight`
asserts three PNG preflights plus one selected stimulus. Twenty handler cases
plus ten edge cases therefore require 120 admissions before browser navigation,
receiver arrivals/reports or other checks. The durable limit is 96 in
[quota_receiver.mjs](../../probes/fixed-origin-lifecycle/quota_receiver.mjs).
Separate fresh offline test stores do not establish a single executable
one-attempt native schedule. An exact reviewed schedule that fits the existing
bounds, or an explicitly reviewed scope/budget change, remains missing.
Reconstruction, retry or quota reset cannot silently repair that mismatch.
The once-only used-target filename also prevents a second native invocation for
that same run. The current entrypoint executes one case/mode, so quota arithmetic
alone cannot make a multi-case run executable.

Additional exact admission costs are:

| Observation | FGA admissions | Receiver admissions |
| --- | --- | --- |
| Browser page1, two images | 6 | 0 |
| Browser page2, one image | 4 | 0 |
| Page1, Next to page2, Previous to page1 | 16 | 0 |
| Maximum six alternating page presentations | 30 | 0 |
| Stale mode through first image rejection | 4 | 0 |
| Each followed same-origin redirect arrival | 1 extra | 1 |
| Each same-origin aggregate report | 1 | 1 |

Cancellation needs a chosen action point and a worst-case reserved prefix; it is
not free merely because the final receipt says cancelled. A future bounded
preparation card can reconcile which observations must be native and which full
handler matrix remains offline, then prepare one immutable multi-step target and
source binding within 96/16 and the existing windows. Such an orchestrator would
be a reviewed source change, not reuse of the current consumed target. For
arithmetic illustration only, ten edge faults (40), three successful formats/
bounds (12), navigation (16), stale (4), a cancellation prefix capped at four,
and five receiver arrivals plus one report (6) total 82 FGA and six receiver
admissions. This is not a chosen sufficient subset, implemented schedule or
authorization; required coverage, sequencing, latencies and one-target design
remain to be established. No quota increase, Completed-card reopening or
additional provider/native run is inferred.

Returned-response validation checks byte count, strict JSON/media/no-store,
duplicate/Location headers, redirects and image bounds after GET returns.
These are application publication guards. They do not establish a native receive
allocation limit, a hard total deadline, native GET abort or protection of the
capability before an SDK redirect is followed. Image signature validation remains
with the actual thumbnail client. The UTC clock is not asserted monotonic.

The native source's complete-page rendering, navigation, cooperative cancellation,
stale-result discard and owned-cache cleanup need supported-host observations.
Offline coroutine and filesystem models do not supply those observations.
Likewise receiver reports are bounded observations and cannot prove that every
edge/provider response has a supported bound.

[#0037's unqualified verdict](fixed-origin-feasibility-verdict-2026-10-16.md)
therefore remains controlling. Supported effective-path allocation and credential
redirect protection, provider-generated valid-path error bounds, backend
abort/disconnect and native cancellation/publication/cleanup evidence are still
missing. [#0043](fixed-origin-restoration-2026-10-17.md) additionally leaves
retained-version restoration, changed-secret semantics, current production state
and both current paused production durable gates unverified. No live packet is
ready for authorization on the strength of this review.

## Focused verification

On 2026-10-17, the pinned Node24.22.0 VM/SQLite run passed **89 tests**
across `isolation.test.mjs` and `composition.test.mjs`. The pinned frozen
Python/Lupa Lua5.1 run passed **14 tests** across
`tests.test_shared_read_qualification` and
`tests.test_fixed_origin_native_client`.

These exercised exact module/source hashes, actual captured/candidate handlers,
closed selectors, original Request/environment delegation, isolated synthetic
authority changes, durable exhaustion/reconstruction, expiry/abort fences,
receiver forwarding and qualifier credential/path gates. Instrumented selected
branches observed zero production environment/database access, global fetch,
host I/O and dynamic imports. No provider request, native plug-in loading,
fixture invocation, secure-store read, catalog operation or real photo occurred.

## Packet document cross-check

The independent review read
[the packet inventory](fixed-origin-execution-packet-2026-10-17.md) and verified
all sixteen listed source SHA256 values against the reviewed source. Its
isolation/native/source-binding wording preserves the distinction between
preparation baseline, archived candidate and exact captured ordinary dispatcher.
Its explicit no-go, 96 hard cap, once-only-target gap and separate #0037/#0043
limitations agree with this review. No material correction to those claims was
required. This cross-check does not supply any missing route-conformance phase
or provider/host evidence.

A late finite-fixture wording finding was corrected and rechecked: only actual-
handler oversize fixtures are 262145 bytes; its upstream-error is HTTP502 with
a fixed 22-byte marker, and its HTTP302 redirect uses that marker too. The
16000 ms stall is distinct. This correction changes no source or qualification
verdict. The packet's fixed global Actions secret absent/create race is also
explicitly retained as a missing future ownership/adapter prerequisite.
