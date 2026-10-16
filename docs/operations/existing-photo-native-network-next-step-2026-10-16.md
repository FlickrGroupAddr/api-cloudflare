# Existing-photo native network qualification: next step

Date: 2026-10-16. Status: finite native characterization completed separately;
fixed-origin qualification remains open. See [the observed result](../evidence/existing-photo-native-network-run-2026-10-16.md)
and [the next proposed engineering plan](existing-photo-fixed-origin-plan-2026-10-16.md).
The experiment descriptions below retain their original scope and limits.

The finite actual `LrHttp.get` experiment is now recorded in the linked result;
the unresolved boundary is the fixed FGA endpoint and its deployed HTTPS edge.
The completed
[native synthetic receipt](../evidence/existing-photo-native-synthetic-2026-10-16.json)
qualifies its ten UI/client/cache scenarios for fixture 0.0.1.5 and release
0.2.0.6 on the recorded Lightroom Classic 15.6 build. It does not exercise HTTP,
credential forwarding, allocation, network cancellation or the deployed edge.
Do not repeat that synthetic matrix merely to start network work.

## Controlling authority and remaining scope

Architecture-design `docs/README.md` controls document precedence. Accepted
ADR 0061 authorizes developing and qualifying bounded hosted thumbnails, but
explicitly leaves `docs/hosted-thumbnail-candidate.md` Proposed and production
disabled. The candidate requires an oversize/error/timeout/redirect matrix
against the actual hosted endpoint/edge and supported native host, including
allocation and Authorization forwarding observations. It permits trusting the
private backend/edge to enforce its bounds; it does not require protection
against an arbitrary malicious replacement server. Neither local tests nor a
successful disposable endpoint run accepts that production contract or enables
a capability. See [the hosted handoff](hosted-thumbnail-handoff-2026-10-15.md).

The existing disposable hosted probe exercises actual production handlers with
synthetic D1/upstream fixtures. Its evidence and lifecycle are documented in
[hosted qualification preparation](../evidence/existing-photo-hosted-qualification-2026-10-16.md).
Its workers.dev origin, probe gate, injected upstreams and disposable bindings
are distinct from `https://flickrgroupaddr.com`, its production edge rules and
the release client's fixed-origin authenticated adapter. Its automatic teardown
also prevents assuming a prior CI endpoint is still available for native use.
Use the latest retained hosted receipt to assess that work; do not relabel it
as production-origin or native evidence.

## What SDK 15.3 documents

The installed primary reference is
`C:/Projects/FGA/architecture-design/vendor/LrC SDK/15.3/API Reference/modules/LrHttp.html`,
particularly `LrHttp.get` and the namespace error description; `LrTasks.html`
documents async tasks and yielding protection.

`LrHttp.get(url, headers, timeout)` returns a complete body string and header
table. Its timeout is the wait during each connection phase, not a documented
end-to-end deadline. Network failure returns nil and an information table that
can contain an error code and partial_data. The documented GET signature
provides no redirect policy, streaming callback, response-byte cap or request
handle for active cancellation. Upload callbacks on other APIs do not establish
GET streaming controls. Do not invent a fourth argument, cancellation primitive,
get-to-file control, debug facility or hidden networking API.

Thus a documented native probe can measure status/returned lengths, bounded
error categories, elapsed observations and controlled redirect behavior. It
cannot impose a preallocation cap with a check after `get` returns, promise a
hard total 15-second limit, or prove that a UI cancellation flag aborts a native
in-flight request. The accepted direction remains feasible only if the trusted
endpoint/edge plus measured host behavior satisfy the scoped transport boundary.
That is unresolved, not a pass and not proof that the design is impossible.
If it cannot be established, return to design rather than weaken the gate.

## Smallest concrete experiment

Prepare a separate development-only native network probe using documented
`LrHttp.get` in an SDK async task. Use an explicit fixed test origin for each
run and direct synthetic requests; do not alter the release adapter to accept
arbitrary origins or use its stored credential. Keep the completed fixture,
release artifacts and qualification flags unchanged. Give any new loadable
probe its own version and record exact source/configuration/host provenance.

The first experiment can use a freshly provisioned disposable workers.dev
endpoint and a separately controlled disposable redirect receiver. Reuse the
existing hosted harness design where applicable, but prepare an explicit
bounded native execution window before exact-resource cleanup. Do not reuse
unknown or already deleted resources, and do not extend a running CI resource's
lifetime without reviewing its lifecycle. Use only synthetic noncredential
Authorization markers; never copy a real Plugin Code to workers.dev or a
redirect receiver. Receiver results contain only marker-present/matches booleans
and counts, with request/header/body logging disabled. Do not retain the marker.

| Experiment | Required bounded observation |
| --- | --- |
| Valid JPEG/PNG and no-store errors | Returned status, media/length validation and actual decodability for valid images; bounded JSON errors publish no image/cache. Marker-only JPEG bytes from a handler test do not prove decoding. |
| Declared and undeclared length | Valid small body, exactly 256 KiB and 256 KiB plus one; a separately declared, finite larger body if needed for allocation characterization. Review its explicit byte limit first; no unbounded body experiment. |
| Invalid/truncated body | Mismatched declared length, truncated connection, invalid signature, wrong media type and error statuses; record only lengths/categories, never partial_data bytes. |
| Slow headers/body and interrupted caller | Controlled bounded delays around the 15-second argument; measure per-phase behavior and server abort/disconnect separately. A post-fetch cancelled flag is not an HTTP abort. |
| Redirects | Controlled same-origin and cross-origin redirects, covering the response codes selected in the concrete plan; measure whether requests arrive and whether the synthetic Authorization marker is forwarded. Never use a live installation bearer. |
| Authority changes | Production handlers with synthetic installation/link/grant changes before final publication; a disposable database only. Separate handler fence evidence from the native client's response-discard behavior. |

Do not derive peak native memory allocation from returned byte length alone.
If allocation behavior is a claimed result, specify an independent supported
process-memory observation method and its precision/limits before the run;
otherwise report only returned lengths and the unmeasured allocation gap.
Record SDK timeout observations and backend abort observations separately.
The native probe should retain complete sanitized current-run terminal receipts
only: host/build, artifact/configuration digests, scenario, numeric status/byte
counts, closed error/header booleans, timings with clock limitations, redirect
marker booleans and cleanup results. No URLs, credentials, response/image bytes
or real photography metadata belong in evidence.

## Fixed-origin promotion boundary and approval

The disposable experiment is useful host characterization. It cannot complete
the candidate's actual fixed-endpoint/edge gate. A subsequent concrete plan must
identify how controlled cases reach the trusted `flickrgroupaddr.com` resource
and demonstrate that its exact effective routing, authentication, redirect,
error-body and response-size policies match the qualified build. A different
path on the same hostname is not automatically equivalent: rule matching can
vary by path. An isolated synthetic resource or controlled fault-injection
configuration may be a proposed method, but neither is currently authorized by
this note, and provider routing feasibility must be checked before choosing it.
Do not redirect real authenticated production requests through the disposable
probe or introduce a public arbitrary-URL/fault endpoint.

No extra owner permission is required merely to read local SDK documentation,
prepare a probe, run offline tests or commit verified in-scope preparation.
Existing authorization for a disposable hosted ceremony should be reused within
its actual scope; this note does not require asking Terry to approve it again.
ADR 0061 itself expressly says the candidate and synthetic tests do not authorize
deployment. Before a new live experiment, the primary must establish whether
prior authorization covers its concrete resources, deployment, receiver and
native requests. If it does, proceed within that authorization. If it does not,
finish the reviewable test artifact/configuration first and obtain approval for
that specific deployment/test, with exact resource scope, finite limits,
credential-free synthetic data, duration and cleanup. Do not ask for blanket
network permission or production capability activation to run a disposable test.

Any change to the production custom-domain route or edge, or production
fault-injection configuration, needs authorization covering that concrete change;
the existing disposable workers.dev scope does not implicitly grant it. Review
and approve the required `enable_request_signal` compatibility setting in the
configuration being tested before attributing disconnect behavior to it. A
narrow real-account public-photo read, if needed after synthetic gates, remains
a separately scoped owner authorization; an exact group-add pair and write
activation are not prerequisites for credential-free network characterization.
The accepted production contract and explicit read-capability activation remain
later gates. Intake, dispatch and Flickr write gates stay paused throughout.

The actionable handoff is therefore: build and review the small synthetic native
network probe and its finite disposable response/receiver plan; resolve existing
live-run authorization against that concrete plan; execute and clean up exact
resources; retain only the measured host claims; then close the fixed-origin
edge/configuration gap with a separately reviewed deployment plan. No live call,
new deployment, desktop action or runtime source change was performed while
writing this note.
