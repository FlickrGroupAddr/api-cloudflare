# Finite synthetic POST characterization packet

Date: 2026-10-16. Ticket #0058. Status: offline prepared; native/cloud measurements
remain unperformed. This packet is evidence preparation, not production transport,
owner approval, deployment authority or Lightroom qualification. #0059 owns action
approval; #0060 owns the approved run and verified teardown. Target: Lightroom
Classic 15.6 Release / Adobe SDK 15.3, as pinned by the
[adapter map](../design/group-workflow-adapter-map-2026-10-16.md).

Authority remains architecture `AGENTS.md`, `docs/README.md`, accepted
ADRs0045/0062/0063, `plugin-service-contract.md`, and
`existing-public-photo-intake.md`. This fixture creates no production endpoint or
release registration. The [GET-only result](../evidence/existing-photo-native-network-run-2026-10-16.md)
is historical evidence for its eight GET cases and two receiver reports only.
POST method/body/header forwarding, response handling and stop behavior below
are all still unmeasured in Lightroom. No GET-to-POST inference is permitted.

## Exact artifact and effective configuration

`probes/group-post-characterization/worker.mjs` is the directly uploaded ES module;
there is no install, bundler or TypeScript compiler step. `schema.sql` is its
disposable D1 schema. `scripts/group_post_characterization.py` contains a bounded
provider adapter and lifecycle. Its CLI only prints an offline artifact manifest:

```powershell
uv tool run --from uv==0.12.5 uv run --frozen python -m scripts.group_post_characterization
```

The manifest records SHA2-256 digests of the server, schema, lifecycle, native
fixture and exact existing Lua clients/codec. Generate it from the final reviewed
commit again at #0059; any changed digest invalidates approval for the old packet.
`probes/lightroom/FGA-GroupPost-v1.lrplugin/` is separate from the GET fixture and
the release plugin. Its version is 0.0.1.1, toolkit identifier ends
`grouppost.v1.lrc15`. It imports the recorded existing proof/batch encoder and
dkjson files directly. Changes to those shared files require manifest review.

Worker upload metadata: main module `worker.mjs`, compatibility date `2026-10-16`,
observability disabled, logpush false. Exactly two `workers.dev` endpoints are
enabled with previews disabled. Names are `fga-post-src-<24hex>` and
`fga-post-recv-<same24hex>`; one D1 database is `fga-post-db-<same24hex>`.
Bindings: DB, ROLE (`source`/`receiver`), RUN_ID, SUBDOMAIN, EXPIRES, ACCESS and
CANARY. ACCESS/CANARY are synthetic secret-text bindings; they are never a real
installation credential or Flickr token. There are no routes, custom domains,
cron triggers, queues, service bindings, production stores or outbound fetches.
The fixed source/receiver origins derive only from the validated run and account
subdomain; neither native target nor request can supply an arbitrary URL.

## Closed request and response matrix

Each POST uses `LrHttp.post(source .. '/v1/cases/' .. id, bytes, headers,
'POST', 15)` inside `LrFunctionContext.postAsyncTaskWithContext`, protected with
yield-safe `LrTasks.pcall`. Headers are exactly Authorization (`Bearer SYNTHETIC-`
plus 32 lowercase hex), Content-Type (`application/json`) and X-FGA-Post-Access
(64 lowercase hex). They contain synthetic markers only. The existing batch
client is exercised with a known all-zero synthetic canonical-format value to
capture its complete validated request; its header value is replaced with the
explicit canary before network dispatch. No stored credentials are read.

Proof body, from `ExistingPhotoClient.encodeProof`, is exactly:

```json
{"schemaVersion":1,"flickrPhotoId":"SYNTHETIC-PHOTO","expectedLinkedFlickrRevision":1}
```

Batch body, from `GroupSubmissionClient.submit`, is one complete set:

```json
{"schemaVersion":2,"photoBinding":{"fgaPhotoBindingId":"SYNTHETIC-BINDING","expectedVerificationRevision":1},"flickrGroupIds":["SYNTHETIC-GROUP-01"]}
```

`batch-sixty` contains ordered synthetic group IDs 01 through 60 in that same
single body; no subset or retry is sent. dkjson key order is explicitly fixed in
the fixture runtime. The server compares the exact encoded bytes and media type.
These diagnostic case paths stand in for the production proof and batch paths;
the existing client's path and encoding are checked before capture. They do not
send traffic to `flickrgroupaddr.com` or Flickr.

| Case IDs | Server behavior | Measurement still required |
| --- | --- | --- |
| proof; batch-one; batch-sixty | 200; 202; 202 synthetic JSON | Actual POST bytes/method/header receipt, complete 60-set single call |
| status-400/401/409/429/503 | Exact status, JSON/no-store; 401 Bearer challenge; 429 Retry-After 2 | SDK status and selected header retention, error body handling |
| same-301/302/303/307/308 | Fixed same-origin `/v1/receive/<case>` | Follow/refuse, resulting GET/POST, preserved/dropped exact body, Authorization and media type |
| cross-301/302/303/307/308 | Fixed receiver-origin `/v1/receive/<case>` | Same observations independently at receiver; no real credential forwarding inference |
| oversize-success; oversize-error | 202/503 with exactly 2,097,153 ASCII bytes | Returned/partial byte counts relative to existing 2 MiB response limit |
| timeout | Durable synthetic receipt before 16-second delayed response, SDK timeout 15 | Actual timeout/error category, returned/partial data and observed wall duration |
| lost-response | Same receipt-before-delay shape under separate case ID; no retry | Server arrival remains observable even when SDK gets no response; never infer unsent |
| cancel (last) | Receipt-before-16-second-delay; cancelable progress scope | Wait for visible `Case cancel` caption, then cancel during that request; next dependent call must be suppressed |

Every server response has JSON content type, no-store and fixture marker
`X-FGA-Post-Probe: fga-group-post-v1`. Oversize payloads intentionally need not be
valid JSON. Redirect receivers accept only fixed diagnostic GET/POST paths,
retain sanitized method/body-byte/exact-match/header-presence booleans, and echo
no request bytes or header values. Refused redirects are measured outcomes, not
fixture failures or evidence that another host will safely handle credentials.

## Finite bounds and stops

There are 23 native POST calls, at most ten controlled redirect arrivals and one
final diagnostic GET; no automatic retry. A shared atomic D1 update caps **64
accepted requests per role**, including report reads, before body allocation.
Request bodies are streamed through a 16,384-byte cap even without Content-Length;
oversized requests are refused without storing their body. At most 46 bounded
case observation rows can exist. Source/receiver endpoints reject query strings,
arbitrary paths, extra receive path segments and unsupported methods. Fixture DB
errors produce a sanitized 503, never raw exception text.

Per response allocation is at most 2,097,153 fixture bytes; delay is exactly 16
seconds for three cases. The cap is a finite server promise. Lightroom may
allocate a returned response before Lua examines it; this does not qualify a
production pre-allocation byte cap, elapsed-time deadline or active cancellation.
LrDate measurements are observed wall time and may be invalidated by clock
adjustment. No monotonic or in-flight abort guarantee is claimed.

Resources expire from serving at 1,200 seconds, including a check after delay.
Preparation has a 240-second local deadline; each provider request uses a
20-second socket timeout and 64 KiB response cap, no redirect or retry, and a
total 120-call budget. A socket timeout does not guarantee a hard wall deadline.
The native fixture requires 600â€“1,200 seconds remaining at start and refuses new
work at expiry minus **240 seconds**, reserving ten 20-second observation/cleanup calls for
two Workers and one DB. The lifecycle owner must remain in the same job, call
`hold_and_cleanup` immediately after publishing the private native target, and
clean up on terminal receipt, stop, failure or the cutoff. No later heartbeat or
manual wakeup is part of the lifetime plan.

Native input and output are fixed under `C:\Temp\FGA-group-post-v1`. Target JSON
has only schemaVersion, planVersion, runId, subdomain, access, canary and
expiresAtUnix. `target.json` is moved to `target.used.json` before invocation,
so replay is refused. Progress cancellation/context cleanup is sticky: check
before/after each network operation; after stop, do not fetch a diagnostic report,
retry, reopen dialogs or invoke through another automation route. Preserve Escape
stops. The cloud owner may collect already-written sanitized DB observations
while cleaning up; a stop never permits another native POST. The partial native
receipt survives a protected-call failure without copying exception text.

## Identity-matched cleanup and receipts

The lifecycle persists creation intent before provider calls and exact returned
identities before the next operation. Worker names must first be absent. Cleanup
visits only the acknowledged exact resources in the same owner journal. Before
deletion it reads each exact Worker settings path and requires the matching
RUN_ID, ROLE and EXPIRES bindings; DB deletion requires matching UUID and name.
It verifies 404 afterward. Unacknowledged creates, lost acknowledgements, foreign
identities, failed reads, exhausted time/budget or unsuccessful verification
leave `cleanup_unconfirmed`; they never license a guessed delete or a claim that
expiry removed the resources. A new run may not overwrite the existing journal.

The private journal/target retains exact IDs and synthetic access markers only
in the runtime directory, never tracked public evidence. Native `status.json`
publishes through a temporary sibling; receipt values are statuses, byte counts,
closed error categories, selected-header booleans and wall durations. No body,
partial data, header text, account identifier, photo metadata or credentials are
copied into it. Cloud `cleanup.json` contains only resource kinds, acknowledged/
deleted flags, stage, provider call count and qualification false. The native
fixture always records remote cleanup as unconfirmed; only verified lifecycle
teardown can change the separate cloud receipt. Characterized means an attempt
finished; individual failed measurements remain failed and cannot unlock #0061.

The packet includes the concrete disabled `run_once` action runner in the lifecycle
module. Its CLI continues to describe only. An owner-approved caller supplies the
provider adapter, synthetic markers, current numeric same-job owner, one bounded
native dispatch callback and a stop reader. The callback must dispatch once and
return promptly; it must never wait indefinitely, install anything implicitly or
retry an ambiguous invocation. No callback or adapter was supplied to real tools
in this turn.

`run_once` verifies the complete approved manifest against current source,
configuration, target runtimes and fixed action paths before any provider call.
It exclusively creates the run output directory, refuses all preexisting native
target/used/status/stop/temporary paths, persists owner/account/attempt identity,
prepares resources, atomically publishes the private target and records the
single native invocation attempt before dispatch. It never invokes twice,
including after a lost invocation acknowledgement or failure.

The bounded watch validates terminal schema, plan/run identity, outcome, closed
reason category and request counts before accepting a receipt. A wrong-run or
malformed terminal causes failure and teardown. Cancellation, deadline or a
backward clock sets a sticky stop file; the actual native `Run.lua` checks it
before/after I/O. The watch allows up to 20 seconds for an already-running native
request to return, then exports bounded observations and executes identity-matched
cleanup in `finally`. A failure to publish a local receipt cannot skip remote
teardown. The private failure journal and exact target/status artifacts remain
for review; a later attempt cannot overwrite them. A closed `action.json` records
native outcome, stop preservation, invocation count, observation confirmation and
cleanup facts. Failed/stopped/unmeasured outcomes cannot become characterization
success merely because cloud teardown succeeded.

Fixed native paths are under `C:\Temp\FGA-group-post-v1`; cloud journal/evidence
is `.coordination-runs/group-post-characterization/<runId>/`, and the approved
manifest is `probes/group-post-characterization/manifest.json`. The manifest pins
Python3.14 / uv0.12.5, Node24.22.0 offline verification, Lightroom15.6 / SDK15.3,
and exact action paths. #0059 approves this complete packet and the exact trusted
caller/dispatch mechanism, account and digest; it does not implement a missing
runner. No GitHub Actions workflow or live provider CLI is added or triggered.

## Action-time approval summary for #0059

Approve only an exact reviewed commit/digest, one fresh 24-hex run, one explicit
Cloudflare account/subdomain, two fixed disposable Worker names and one DB name,
the effective configuration above, synthetic ACCESS/CANARY delivery and deletion,
one isolated native fixture installation/load, and one 23-case SDK invocation.
Name the cleanup owner/job and local artifact/target/status paths, the final
native cancel gesture and Escape preservation, request/byte/time/resource caps,
and the ten-call observation/cleanup margin. Include settings/DB identity checks and terminal
404 receipts, with unknown acknowledgements recorded as unresolved. Remove the
fixture installation and local target markers only after collecting sanitized
receipts and verifying the exact installed artifact identity. No release plugin
registration, credential access, real Flickr calls, catalog write or production
qualification belongs to this action. A materially changed artifact requires
review of its concrete action scope again.

## Offline verification

Node 24.22.0 executes `worker.test.mjs`; pinned uv 0.12.5 executes
`tests.test_group_post_characterization` with actual Lua 5.1 and existing clients.
These checks exercise the code without loading Lightroom or calling a provider.
Record final focused results and required independent Sol / High review in the
parent handoff. No deployment, installation, native invocation, credential read,
real account action or owner decision occurred in #0058.


Final offline review: the concrete one-attempt runner, pre-dispatch stop checks,
fixed per-case cancellation cue and complete Run.lua SDK/file-stub behavior
passed independent Sol / High re-review. All **16 focused Python/Lua tests**,
**four Worker suites**, Ruff/format and Pyright passed; the final checked-in
manifest equals the current packet. Parent integration passed **492 full
Python/Lua tests** and **295 backend/native-emulator tests**. These are offline
results; no deployment, fixture load or native network experiment occurred.
