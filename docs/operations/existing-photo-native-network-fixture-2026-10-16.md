# Disposable native network characterization fixture

Date: 2026-10-16. Status: prepared and offline verified; not loaded or run.

The separate `probes/FGA-ExistingPhoto-Network.lrplugin` version **0.0.1.2**
characterizes documented SDK 15.3 `LrHttp.get` behavior against two finite,
plan-generated workers.dev resources. It does not use the production client
adapter, Plugin Code, Lightroom catalog, provider credentials or real images.
The completed native UI/cache fixture and release source/hash artifacts are
unchanged. Authority and remaining fixed-origin gates are described in
[the next-step note](existing-photo-native-network-next-step-2026-10-16.md).

This packet is preparation only. The primary will seek action-time approval
for the concrete lifecycle and native plug-in load/run. No cloud resource,
config credential, native UI or network was accessed while preparing it.

## Agreed finite plan

The hosted owner prepares exactly two fresh Workers and one shared synthetic
D1 database. Their generated configuration has no production route, binding,
secret or Flickr access. Maximum lifetime is **20 minutes**, each role permits
at most **32 requests**, each response is at most **262145 bytes**, and the
only artificial delay is **16 seconds**. Quotas and expiry live in shared D1,
not per-isolate memory. Exact resource identities and cleanup remain the hosted
operator's responsibility. The native fixture never calls provider APIs.

Private target path: `C:\Temp\FGA-existing-photo-network\target.json`.
The producer must write a UTF-8 JSON object of at most 8192 bytes with exactly:

| Field | Required value |
| --- | --- |
| `schemaVersion` | Integer 1 |
| `planVersion` | `fga-native-network-v1` |
| `runId` | Fresh 24-character lowercase hexadecimal plan identity |
| `workersDevSubdomain` | The reviewed account's one DNS label, 1-63 lowercase ASCII letters/digits/interior hyphens |
| `accessToken` | Fresh 64-character lowercase hexadecimal disposable gate |
| `canaryToken` | `SYNTHETIC-` followed by fresh 32-character lowercase hexadecimal text |
| `expiresAtUnix` | Integer Unix seconds, later than current time and at most 1200 seconds ahead |

There are no configurable URLs, paths, cases, timeouts or arbitrary headers.
The only accepted origins derive from that plan:
`https://fga-native-network-src-{runId}.{workersDevSubdomain}.workers.dev` and
`https://fga-native-network-recv-{runId}.{workersDevSubdomain}.workers.dev`.
The native fixture does not discover/choose accounts or alternative endpoints.
The hosted producer and primary must verify that this private target corresponds
to their exact created-resource journal before load/run. Structural validation
is not cryptographic attestation of the local config producer. Do not hand-edit
it to point to another endpoint, copy a real credential into either token field,
or publish this private file. Unknown fields and invalid/expired plans fail
before any GET. The fixture's current-time conversion uses the documented
2001 Cocoa epoch plus 978307200 seconds; it does not claim a monotonic clock.

Every source case sends `X-FGA-Network-Access: <disposable gate>` and
`Authorization: Bearer <synthetic canary>`. This deliberately measures forwarding
of a noncredential marker. Both Workers use the agreed
`X-FGA-Network-Probe: fga-native-network-v1` response marker and no-store policy,
including denials. No installation bearer, Flickr OAuth or real secret may be
substituted for the canary. A gate may be forwarded to the controlled receiver;
it is limited to these short-lived disposable resources.

## Fixed invocation order

The native fixture invokes at most ten GET operations: a baseline receiver
report, these eight source cases in order, then a final receiver report.
`LrHttp.get` itself may perform redirect requests, which the hosted role quotas
also count. There are no retries, random cases or parallel requests.

| Source path under `/v1/cases/` | Fixed response |
| --- | --- |
| `png` | 200 image/png, 68 bytes; actual synthetic PNG |
| `jpeg` | 200 image/jpeg, 634 bytes; actual synthetic solid-color 2x2 JPEG |
| `boundary-image` | 200 image/png, 262144 bytes; marker fixture |
| `oversize-image` | 200 image/png, 262145 bytes; marker fixture |
| `oversize-error` | 503 text/plain, 262145 bytes |
| `slow-response` | 200 image/png, 68 bytes after 16 seconds |
| `redirect-same` | 302 to the same origin's `/v1/cases/png` |
| `redirect-cross` | 302 to the derived receiver's `/v1/receive/{runId}` |

The receiver receive route is ungated so a stripped custom header does not
prevent observing redirect arrival. It returns only schemaVersion,
receiverReached, authorizationPresent and canaryMatched. Its D1 observation
records every arrival and only Authorization-present/exact-canary-match
booleans; neither tokens nor request/header payloads enter persisted evidence.

The receiver `/v1/report` requires the disposable gate and returns exactly
`schemaVersion: 1`, `receiverRequests` (0-32), `authorizationObserved` and
`canaryObserved`. Both native report reads send the gate and **no Authorization**,
so reporting cannot manufacture a forwarding observation. Report reads count
toward the role quota but not receiverRequests. The baseline must report zero
arrivals and false flags; otherwise the native fixture stops before source
cases. The final report is correlated with the native `redirect-cross` response,
not treated as attribution on its own. A returned original 302 requires zero
receiver arrivals and false aggregate flags. A receiver 200 must have the marker,
no-store and JSON media type, plus a bounded, exact closed object containing
schemaVersion 1, receiverReached true, and boolean authorizationPresent and
canaryMatched (a match also requires Authorization present). That response
requires exactly one aggregate arrival and exact agreement of both flags.
Any unrelated arrival, malformed receiver payload, flag disagreement or other
native result makes observationConclusive false, leaves redirectFollowObserved
absent, and reports an incomplete observation. More than one arrival is likewise
inconclusive; aggregate count/booleans remain sanitized diagnostics without
attributing them to this native request. Impossible
boolean/count combinations are rejected. No result is inferred from a missing,
expired, malformed or quota-denied report.

## Review and action-time handoff

Before asking Terry for the load/run decision, review the finite hosted plan,
exact new runtime/configuration/source hashes, private target schema, created
resource journal, local validation and cleanup/recovery procedure. Confirm
that target expiry leaves enough time for one native attempt. Do not create
resources or start that clock during preparation.

After action-time approval, the primary owns provisioning, source hash capture,
private target placement, plug-in loading and the single command invocation.
Keep the plug-in at its checkout location because it loads the existing
vendored `dkjson.lua` by a native SDK path relative to the checkout; it does not
modify that library or the release bundle. Use SDK 15.3 targeting on the exact
recorded installed host/build, with all entrypoints versioned 0.0.1.2.

Invoke Library > Plug-in Extras > Existing-photo disposable network
characterization once. A module-level active guard prevents overlapping calls
and is released by function-context cleanup. Observe the current receipt
transition; a stale receipt from an earlier attempt is not evidence. Do not
rerun a consumed/interfered plan to turn a failure into a pass; inspect the
sanitized result and use a newly reviewed plan/resources when another attempt
is authorized. The hosted expiry and exact cleanup remain required even if the
native plug-in never starts or an error interrupts it.

## Receipt, limits and cleanup

Stable status: `C:\Temp\FGA-existing-photo-network\status.json`, published
through a checked temporary sibling and SDK move. Existing status is removed
only after a complete temporary file has been written and closed. Delete,
move and source/destination checks remain hard failures; publication is not a
crash/power-loss durability guarantee. A missing, stale, malformed or
nonterminal receipt, a publication error, or an interrupted run is not completion.
The primary correlates attemptId, planId, runtime version, host/build and source
hashes. Plan/resource origins and token values stay private.

The schema-1 receipt records current-run stage, closed outcome/reason,
GET-call count, fixed case IDs, numeric HTTP status, returned/partial byte counts,
observed milliseconds and timing-valid flags, closed network-error/media
categories, response-marker/no-store/location booleans, finite-plan comparisons,
receiver report validity and final canary booleans/count. It never includes
response/partial_data bytes, URLs, header values, tokens, SDK error strings,
photography metadata or private config. Unknown native error codes become
`other_network_error`. Receipt updates occur between requests; there is no GET
progress callback. Parent evidence stores exact source/configuration digests
separately; the Lua receipt does not calculate them.

`characterized` means the finite response measurements matched this experiment;
`incomplete` preserves unexpected observations, and `failed` preserves a closed
configuration/report/runtime failure. Redirect follow/refusal and canary
forwarding/stripping are measured results, not real-credential safety passes.
The 16-second case may return the image or a timeout: the documented 15-second
argument applies per connection phase. Neither result establishes a hard total
request deadline. Plan expiry is checked between requests, not enforced as a
native in-flight abort.

JPEG decodability is checked offline by the hosted fixture preparation; it is
not checked by this native probe. The native receipt records lengths and media
categories only.

The fixture allocates no image/cache files (`responseFilesCreated: 0`). It
clears its response references between operations; that does not prove when
native memory is reclaimed. The 262145-byte comparisons run **after** GET returns:
they are finite measurements, not a native preallocation cap. Boundary/oversize
image marker fixtures do not prove full image decoding, and this probe does not
display or decode images. It does not measure peak process memory. Receipts
always state `nativeTransportQualified: false`, `productionQualified: false`,
`allocationBoundProven: false` and `totalDeadlineProven: false`.

`remoteCleanupConfirmed` remains false in the native receipt. The hosted primary
must delete only the exact two created Workers and shared synthetic D1 from the
private journal, verify those deletions, retain sanitized cleanup evidence and
remove the private target/gate material. Never delete unrelated resources or
infer remote cleanup from local receipt completion. Keep the sanitized status
only as needed for reviewed evidence; the temporary path is ephemeral.

Fourteen offline actual-Lua5.1 tests cover fixed paths/headers/case counts,
configuration rejection before requests, report freshness, canary outcomes,
timeout/partial-data/error sanitization, privacy exclusions, finite excess
observations, native Windows path construction, checked receipt delete/move failure behavior
and version consistency. Ruff,
Pyright and Adobe SDK15.3 `luac -p` pass. SDK objects are stand-ins in these tests;
no host/network observation or production gate is claimed. The fixed FGA
origin/edge and detailed production contract still require their separate gates.

Build 0.0.1.2 evidence-integrity correction: ready metadata exposes the receiver
path/run identity, so aggregate count 0/1 alone cannot attribute an arrival to
the native redirect. This version correlates the actual response with strict
closed receiver JSON and the final report as specified above. Regressions cover
an unrelated arrival with an unfollowed 302, malformed/extra/wrong-type payloads,
and payload/report flag disagreement. The earlier committed review receipt and
its source hashes remain historical evidence for build 0.0.1.1; they do not
approve these changed runtime bytes. The independent reviewer must record a
separate review/addendum for this build. No endpoints, secret paths or new
authentication framework were added; no UI or live call occurred during this fix.

The receiver/report attribution parser is intentionally narrower than the general
configuration decoder: bounded flat objects with known literal ASCII keys,
canonical nonnegative integer fields and boolean values only. It rejects comments,
duplicate keys, trailing commas, escaped/unknown names, floating-point numeric
forms and trailing data before applying each exact schema. The controlled
Worker emits that canonical subset. This prevents permissive dkjson extensions
from turning malformed attribution data into an apparently valid observation;
config parsing remains separate. Regression cases cover the three permissive
forms for both receiver payloads and final reports.
