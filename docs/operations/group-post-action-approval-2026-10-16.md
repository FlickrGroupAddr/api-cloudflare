# Synthetic POST action approval packet

Date: 2026-10-16. Ticket #0059. Status: concrete offline packet reviewed; ready for an
action-time owner decision and the future dedicated operator credential input. No action authority or
production qualification is claimed. #0060 owns an approved execution and teardown.

This supplements [the finite #0058 packet](group-post-characterization-2026-10-16.md).
Canonical authority remains architecture `AGENTS.md` / `docs/README.md`, the
accepted contracts identified there and later explicit owner directives. Prior
GET evidence and standing code/commit approval do not authorize this POST action.

## Exact reviewed source

Source: `FlickrGroupAddr/api-cloudflare` commit
`b599ca828d2a645b686aca0354d6c8ee2c2a0250`. The checked-in
`probes/group-post-characterization/manifest.json` has SHA2-256
`87e52649df09518ed372e5482ca3c61be7c3ac4f7e8c6bd07c7cdc09206805ed`.
All nine manifest artifact digests were independently compared with local bytes
while preparing this packet and matched. This is a file-integrity check, not a
new runtime test. The manifest pins the direct Worker module/schema, lifecycle,
three native Lua files and existing proof/batch clients plus dkjson. Changed
artifact, effective configuration, caller or delivery scope needs renewed review.

The native fixture is exactly
`C:\Projects\FGA\api-cloudflare\probes\lightroom\FGA-GroupPost-v1.lrplugin`,
version **0.0.1.1**, toolkit ID
`com.sixbuckssolutions.fga.grouppost.v1.lrc15`. Its Library command is
**Characterize synthetic POST v1**. Register/load this separate directory in
Plugin Manager and invoke that command once through the supported native API;
it imports the manifest-pinned clients from their existing repository locations.
There is no package install, bundle build or release plug-in registration in
this scope. The fixture uses synthetic data and no catalog API; it requires no
selected photo, catalog fixture, catalog creation or catalog write. Host metadata
and screenshots remain private.

Pinned targets: Python **3.14**, uv **0.12.5**, Node **24.22.0** for offline
verification, Lightroom Classic **15.6** and SDK **15.3**. The prior GET run
observed Camera Raw 18.7 / host build `202609251514-f839cde9`; the future operator
must observe the current host rather than assume that historical identity.

## Proposed single attempt

The planned fresh run ID is `c01ba6d2c2754597aa311c9f`, selected offline here.
Only these names belong to the proposal:

| Kind | Name |
| --- | --- |
| Source Worker | `fga-post-src-c01ba6d2c2754597aa311c9f` |
| Receiver Worker | `fga-post-recv-c01ba6d2c2754597aa311c9f` |
| Disposable D1 | `fga-post-db-c01ba6d2c2754597aa311c9f` |

Both Worker names must be absent before creation. Returned resource IDs remain
in the private owner journal. Origins will be those Worker names plus the
privately retained account's workers.dev subdomain. The account identity is
already retained by #0036; the prior GET ready artifact retains its subdomain.
The reviewed private bridge configuration binds those identities to this attempt;
neither is a missing owner-supplied input. No arbitrary native/request URL is accepted.

Upload `worker.mjs` directly with compatibility date `2026-10-16`, workers.dev
enabled, previews disabled, observability disabled and logpush false. Bind only
DB, RUN_ID, ROLE, SUBDOMAIN, EXPIRES, ACCESS and CANARY. No production binding,
route, custom domain, cron, queue, service binding or outbound fetch is included.

ACCESS is 64 lowercase hex; CANARY is `SYNTHETIC-` plus 32 lowercase hex. Generate
fresh synthetic values only. Deliver them as synthetic secret-text bindings and
the private native target. They are neither real installation nor Flickr
credentials. Provider authentication is separate and must never enter the
target, native fixture, sanitized receipts or public evidence.

The native invocation contains **23 POST cases**, at most ten controlled redirect
arrivals and one final diagnostic GET, with no automatic retry: proof, batch-one,
batch-sixty; status 400/401/409/429/503; same-origin and receiver-origin
301/302/303/307/308; oversize-success/error; timeout; lost-response; cancel last.
The existing batch client sends the complete 60-group set in one body.

## Fixed paths, stops and teardown

| Artifact | Fixed path |
| --- | --- |
| Approved manifest | `C:\Projects\FGA\api-cloudflare\probes\group-post-characterization\manifest.json` |
| Private owner output | `C:\Projects\FGA\api-cloudflare\.coordination-runs\group-post-characterization\c01ba6d2c2754597aa311c9f\` |
| Native target | `C:\Temp\FGA-group-post-v1\target.json` |
| Consumed target | `C:\Temp\FGA-group-post-v1\target.used.json` |
| Native terminal receipt | `C:\Temp\FGA-group-post-v1\status.json` |
| Sticky stop | `C:\Temp\FGA-group-post-v1\stop.json` |

Refuse an existing output directory or any native target/used/status/stop or
temporary sibling. Never overwrite an earlier attempt. The native fixture moves
target to used before dispatch. Private owner output contains the exact creation
journal, bounded observations and separate cloud `cleanup.json` / `action.json`.

For the last case, wait for the visible **Case cancel** caption, then click the
native progress Cancel control during that request. Cancellation is sticky and
must suppress the next dependent call. Intentional Escape is a terminal stop
for native input in that turn: no reset, relaunch, retry, dialog reopening or
alternate automation route. The cloud owner may collect already-written bounded
observations and clean up. No additional native POST is allowed after stop.

The proposed cleanup owner is the #0060 primary operator's **same live job**,
using `run_once` in `scripts/group_post_characterization.py`; its numeric owner
identity is `str(os.getpid())`, resolved by that process at execution. Terry does
not need to supply a PID. The concrete dispatch/stop caller is the independently reviewed #0145 bridge.
It must remain running immediately after target publication through stop,
terminal receipt, failure or cutoff and execute teardown in `finally`. The
callback must dispatch once and return promptly; an ambiguous acknowledgement
never permits another invocation. No heartbeat or later wakeup owns cleanup.

Delete only journal-acknowledged identities after exact Worker settings checks
for RUN_ID/ROLE/EXPIRES and exact D1 UUID/name checks. Verify terminal 404s for
both Workers and D1. Lost acknowledgements, foreign identities, failed reads or
unverified deletion remain `cleanup_unconfirmed`; expiry is not deletion proof.
After collecting sanitized receipts, remove only this exact fixture's Plugin
Manager registration and local target markers after verifying installed identity
and obtaining any applicable action-time confirmation. After intentional Escape,
UI cleanup waits for explicitly permitted input; remote teardown may continue.
Preserve unresolved journal/evidence for recovery. Native cleanup and remote
cleanup are separate verdicts.

## Bounds and evidence limits

- Two disposable Workers and one D1 only; serving expires after **1,200 seconds**.
- Preparation deadline 240 seconds. Start native work only with 600–1,200 seconds
  remaining; stop new work at expiry minus 240 seconds for ten cleanup/observation
  calls. Stop watch allows up to 20 seconds for existing native I/O to return.
- At most 120 provider calls; each has a 20-second socket timeout, 64 KiB response
  cap, no redirects and no retries. Socket timeout is not a hard wall deadline.
- At most 64 accepted requests per role including report reads; at most 46 case
  rows; request cap 16,384 bytes before body storage.
- Response allocation at most 2,097,153 fixture bytes; three delays exactly
  16 seconds; native SDK timeout argument 15 seconds.

Record only closed outcomes, statuses, byte counts, header-presence/exact-match
booleans and observed wall times. Do not persist request/response bodies, partial
data, header values, account IDs, host/catalog/photo metadata or credentials in
public evidence. Wall timing, post-return byte checks and observed cancellation
do not prove a monotonic deadline, pre-allocation response cap or active abort.
Failed/stopped/unmeasured outcomes remain so even after successful teardown.
The run cannot by itself qualify production transport, credentials, group
additions or a later Lightroom major, or unlock #0061 with missing measurements.

## Reviewed bridge and exact local inputs

#0145 closes the earlier concrete-caller engineering gap. The
[bridge procedure](group-post-execution-bridge-2026-10-16.md) and
`scripts/group_post_execution_bridge.py` supply the same local Python owner,
fixed invoke/ack/stop handshake, exact Node REPL / @oai/sky operator procedure,
one-attempt semantics and unconditional remote observation/cleanup composition.
Its independent S_H review passed 16 offline composition tests and adversarial
stop/receipt/approval-snapshot checks. The unchanged #0058 source manifest remains
the base; this is an additional explicit component, not a relabeling of it.

Companion manifest: `probes/group-post-characterization/execution-bridge-manifest.json`.
Its SHA2-256 is `bd8a2797d8fb1e23209f6c78f997d54d52ed1b8c18bc366cf65b5f16ba966392`. It pins the bridge code, operator document,
base manifest and closed offline description. Private configuration is prepared
at `.coordination-runs/group-post-execution-bridge/private/config.json`; the exact
account comes from #0036's `20261016T214740Z/private/restoration-inputs.json`,
and the subdomain from the retained GET ready artifact. Neither needs to be
supplied again. The same process resolves `str(os.getpid())` at execution.

The future authentication route is exactly `C:/Temp/fga-post-operator-token.txt`.
It is currently absent and has not been read or created in preparation. After
the owner chooses the run, provide an appropriately scoped temporary provider
token through that file; restrict it to the local operator and SYSTEM before
apply. It is read boundedly into memory only after exact approval/configuration/
artifact verification. Do not reuse the read-only inventory token, export a CI
secret, put a token in argv or publish it in any receipt. Its absence is a future
execution input, not an unspecified engineering delivery mechanism.

The future approved-packet.json is an integrity record, not owner consent.
The installed [Computer Use skill](C:/Users/TDO-XPS15-2024/.codex/plugins/cache/openai-bundled/computer-use/26.1013.31256/skills/computer-use/SKILL.md)
and its confirmations.md require “Blocking confirmation required immediately
before the action” for installing/running newly acquired software through Windows
UI. #0059 therefore needs the exact action-time decision immediately before this
new fixture registration/load/invocation; prior GET/code/contract approvals do
not authorize it. The supported Node REPL / @oai/sky route remains uninitialized
and untested in this preparation. If unavailable at execution, stop rather than
using another helper. Removing registration through UI has its own applicable
confirmation/stop boundary; after Escape, defer it until input is permitted again.

No provider request, credential read, native API initialization, fixture action,
resource creation/deletion, deployment or owner execution decision occurred.
#0059 is now a genuine owner handoff; #0060 remains the execution owner. The
independent unresolved #0037 gates are not passed by this finite characterization.
