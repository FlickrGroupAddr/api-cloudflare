# Fixed-origin edge measurement feasibility

Date: 2026-10-16. Ticket #0037.
Status: Research complete; current method unqualified; return to design now. No live request,
deployment, native experiment, credential change or replacement implementation.

## Authority and result

Accepted architecture [ADR 0061](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/decisions/0061-develop-bounded-hosted-thumbnails.md)
permits candidate development. Its [hosted-thumbnail candidate](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/hosted-thumbnail-candidate.md)
remains Proposed and requires an exact-build, actual-endpoint/edge transport
matrix, credential protection and a documented bounded supported client path.
The [documentation hierarchy](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/README.md)
controls; this note neither accepts that candidate nor weakens its gates.

The current inputs identify an endpoint baseline, not a qualified bounded path.
Two concrete gaps prevent a positive feasibility verdict: the deployed baseline
is not the checkout thumbnail candidate, and the captured runtime does not
explicitly enable the provider's incoming-request cancellation signal. More
fundamentally, no documented response-size guarantee for provider-generated
valid-request errors was established. Application response limits alone do not
bound every response the native HTTP stack can receive. The integrated decision is
[return to design now](../operations/fixed-origin-feasibility-verdict-2026-10-16.md).
Aggregate characterization remains possible, but it does not qualify the desired
allocation, credential-redirect or effective-edge guarantees. Native cancellation/
publication/cleanup and backend abort remain separate evidence obligations; no
caller-controlled in-flight native GET abort handle is added as a requirement.

## Current inventory boundary

Use [the #0036 inventory](../operations/existing-photo-inventory-2026-10-16.md)
and [its sanitized receipt](../evidence/existing-photo-inventory-local-2026-10-16.json).
The retained final capture has one active version/module, a validated exact
version response and stable deployment metadata across capture. Account and zone
ruleset catalogues contain zero configured root/zone entrypoints. Worker route
and Page Rule lists are empty; the expected enabled custom-domain attachment is
observed. Empty route lists do not imply absence of the custom-domain path.
These are capture-time facts, without an atomic edge/configuration fence.

Private inspection of the exact captured module finds the current-installation
route, but no existing-public-photos route string, thumbnail path substring,
thumbnail feature-gate name or incoming request.signal use. This is a bounded
static-presence screen, not a semantic decompilation proof. It establishes no
right to substitute the checkout candidate for the captured runtime. Later
candidate deployment and exact artifact/configuration rebinding belong to the
reviewed execution packet; this task performs neither.

Only sanitized findings appear here. Raw settings, identifiers, bindings, module
bytes and configuration values remain in the private #0036 capture. Its receipt
records the relevant SHA2-256 digests; no token file was read.

## Obligations and supported observation

| Boundary | Measurement/enforcement method for a later reviewed packet | Present conclusion |
| --- | --- | --- |
| Exact endpoint and routing | Pin the actual fixed-origin custom-domain attachment, active weighted version/module hashes, settings and all configured edge entrypoints. Re-read around the finite matrix; refuse drift or unknown reads. Exercise the three intended GET resources independently: installations/current, existing-public-photos and existing-public-photos/{syntheticPhotoId}/thumbnail below /api/v001/. | Input baseline available; discovery/thumbnail candidate not established in captured module. |
| Ordinary success and application errors | At the final response boundary, account for every status/body constructor and exception path. Count encoded bytes, declared versus actual length, compression/decoding behavior and media type on the actual native path. Include disabled route, authentication, query, no-match, database/secret/upstream failure, oversize and late-authority-change cases. Preserve JSON/no-store and matching Bearer codes where required. | Checkout thumbnail helper limits validated image bytes to 256 KiB and observed operation time to 15 seconds; discovery upstream read is 2 MiB/15 seconds. These are separate backend limits, not a final JSON response cap, native allocation measurement, deployed fact or provider-error cap. |
| Redirect and Authorization protection | Review each redirect-producing layer and every credential-bearing outbound construction; use manual upstream mode and refuse every 3xx before a follow. The later native matrix must observe whether its supported HTTP stack follows and forwards Authorization, using only synthetic disposable markers and an authorized controlled receiver. A post-return status/URL check cannot retract an already forwarded credential. | Checkout discovery signs a fixed Flickr REST request with manual redirects; thumbnail fetch builds fresh Accept-only headers for an allowlisted CDN URL. It does not forward the installation Authorization header. This does not prove native-to-edge redirect protection or provider behavior. |
| Provider errors, challenges and redirects on valid paths | The required bound needs a supported mechanism covering all applicable layers, including failures before/without Worker execution. No such complete mechanism is established here. Finite samples cannot waive the unknown provider bound; record it as a design gap and do not turn unknown HTML into an accepted envelope. | Zero configured entrypoints removes those configured rule executions at capture time, not platform-generated failure pages or future drift. No documented complete valid-request provider body bound or no-redirect assurance was established. Blocked. |
| Early HTTP parser rejection | Keep malformed-target and duplicate-Authorization inputs separate from ordinary errors. Collect bounded status/body/header metadata privately; publish only classifications/counts/hashes. Verify rejection occurred before the application and contains no redirect, shell, application/session data, credentials or application/session cookie. | Narrow accepted exceptions only; historical fingerprints are scoped fixture discriminators, not blanket HTML permission or current-path qualification. |
| Native cancel and native timeout | Observe the supported host call outcome, observed SDK wall-time difference and its clock-adjustment limits, UI cancellation, suppression of late publication and file cleanup. Correlate separately with backend observation if available. | Parent native-method research owns SDK limits. Native return/cancel does not itself prove socket closure, backend abort, upstream cancellation or allocation bound. |
| Backend timer and incoming disconnect | Distinguish timer-fired local AbortController, observed incoming signal, outbound fetch/body cancellation request, operation-settled result and final publication fence. Use finite synthetic correlation labels and booleans, never credentials/URLs/photo data. Confirm each observable claim separately; record absent observations as unknown. | Checkout thumbnail wrapper propagates its own timer/optional incoming signal into fetch/body cancellation and checks final authority. Incoming disconnect support is not enabled in the captured runtime; no hosted cancellation observation exists. |

The checkout locations are src/worker.ts, src/installations.ts,
src/existing_photo_discovery.ts and src/photo_thumbnails.ts. Their inspection
supports candidate code claims only. An abort request or canceled reader is not
proof that a provider or database operation stopped remotely; logical fences
must prevent a late result from being published even when remote work continues.
The accepted #0031 backend timing amendment does not generalize to the FGA LrC
plug-in or thumbnail candidate. Native timing uses the documented SDK wall
clock and its limitations; no native monotonic timer is established here.
The candidate expressly offers observed elapsed-time rejection, not a hard
wall-clock stall guarantee. Counting already returned bytes cannot measure
allocations performed before the native call returns.

## Incoming request signal applicability

Current primary Cloudflare [compatibility documentation](https://developers.cloudflare.com/workers/configuration/compatibility-flags/#enable-requestsignal-for-incoming-requests)
still lists enable_request_signal as an explicit opt-in without a default date.
The [introduction notice](https://developers.cloudflare.com/changelog/post/2025-05-22-handle-request-cancellation/)
also requires it. Private comparison of captured Worker settings, active version
runtime metadata and exact module-version metadata agrees: the enable flag is
absent. A recent compatibility date, the existence of request.signal in source,
or a local synthetic AbortSignal does not establish incoming disconnect support.
The separate request_signal_passthrough option concerns forwarding an incoming
signal to subrequests; it is not a substitute for enabling incoming cancellation.

Enabling the required flag is a candidate runtime/configuration change requiring
its own reviewed artifact and affected checks. It is not authorized or performed
by this research. Even after enablement, a later actual-path test must correlate
client disconnect with backend signal and publication behavior; documentation
alone does not prove how the supported Lightroom Classic host closes a request.

## Provider boundary and the early-400 exception

Cloudflare documents [production error pages](https://developers.cloudflare.com/workers/observability/errors/)
when a Worker cannot return a response, including uncaught exceptions, exhausted
CPU and routing failures. Those responses can originate outside application
serialization. This source identifies error classes; it does not supply the
complete response-byte bound needed here. A Worker catch handler cannot be
assumed to rewrite an error generated before or instead of that invocation.

The accepted architecture [HTTP route contract](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/operations/http-route-conformance.md)
and [ADR 0054](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/decisions/0054-accept-early-duplicate-authorization-rejection.md)
allow only the provider's early HTTP 400 for malformed request targets or duplicate
Authorization fields to omit the application JSON/no-store presentation (and,
for the duplicate-header case, the Bearer challenge). The no-data/no-shell/
no-redirect restrictions remain. These exceptions do not cover a valid-request
outage, ordinary 404/405, other authentication failure or arbitrary HTML page.
They are presentation exceptions, not a waiver of the candidate transport bound.

Cloudflare's [Request reference](https://developers.cloudflare.com/workers/runtime-apis/request/)
warns that follow mode forwards sensitive headers across hostnames. Its manual
mode returns a redirect to the Worker. This supports the checkout upstream
policy; it says nothing about the Lightroom Classic native client's redirect
behavior, which needs its own independent evidence.

## Return-to-design handoff now

The present method does not qualify the candidate. Return it to architecture
with the [integrated verdict](../operations/fixed-origin-feasibility-verdict-2026-10-16.md)
now; dependent live qualification/promotion remains blocked. Do not defer that
verdict until a later finite matrix or treat unobserved provider behavior as a
passing bound.

The next conventional decision is an offline review of the exact candidate
artifact/configuration against the unresolved supported receive-allocation,
provider-response and credential-redirect method. Keep native cancellation/
publication/cleanup evidence distinct from backend abort/disconnect behavior.
Identify a documented
supported mechanism for each required claim before selecting a live packet.
Review incoming-signal enablement separately; it supplies neither a native GET
abort handle nor a complete provider-response cap. If the mechanisms remain
unavailable, architecture must resolve the candidate design under its existing
authority process. This research proposes no replacement and accepts no waiver.

Ticket #0040 may draft a finite fault-case specification documenting these gaps.
Execution, #0044 packet approval and #0047 qualification cannot inherit a pass
from aggregate characterization or this research. Exact artifact binding is a
necessary future execution input, not production code qualification. No live-test,
deployment or capability-activation authority results from this note.
