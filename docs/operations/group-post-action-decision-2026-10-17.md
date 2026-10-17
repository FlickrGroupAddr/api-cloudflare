# Concrete synthetic POST owner decision

Date: 2026-10-17. Ticket #0059. Status: proposed owner action decision; no consent or execution recorded.

Recommend authorizing one finite synthetic characterization attempt under the exact scope below, once the primary presents the final verified packet at action time. #0058 and #0145 are Completed engineering prerequisites. They do not authorize this action. #0060 owns any approved execution, observations and teardown; #0059 owns Terry's decision.

This decision supplements the [reviewed action packet](group-post-action-approval-2026-10-16.md) and [single-job bridge procedure](group-post-execution-bridge-2026-10-16.md). It changes neither accepted architecture nor production qualification. Architecture `AGENTS.md`, `docs/README.md` and their accepted scoped authorities remain controlling.

## Exact proposed action

Authorize the #0060 primary to create exactly two disposable Workers and one D1 in the account already bound by the retained private configuration, register/load the separate synthetic Lightroom fixture, invoke its Library command once, perform its final controlled Cancel case, and keep the same attached Python owner alive through bounded observations and identity-checked remote teardown.

| Scope | Exact value |
| --- | --- |
| Run | `c01ba6d2c2754597aa311c9f` |
| Source Worker | `fga-post-src-c01ba6d2c2754597aa311c9f` |
| Receiver Worker | `fga-post-recv-c01ba6d2c2754597aa311c9f` |
| Disposable D1 | `fga-post-db-c01ba6d2c2754597aa311c9f` |
| Base source | `b599ca828d2a645b686aca0354d6c8ee2c2a0250` |
| Base manifest | `probes/group-post-characterization/manifest.json` |
| Base manifest SHA2-256 | `87e52649df09518ed372e5482ca3c61be7c3ac4f7e8c6bd07c7cdc09206805ed` |
| Bridge manifest | `probes/group-post-characterization/execution-bridge-manifest.json` |
| Bridge manifest SHA2-256 | `bd8a2797d8fb1e23209f6c78f997d54d52ed1b8c18bc366cf65b5f16ba966392` |
| Bridge module | `scripts/group_post_execution_bridge.py` |
| Bridge module SHA2-256 | `0a66f0d35b90e1b408ab49914f8e33718ee9b27b975afa02dcded6289af7251b` |
| Native fixture | `C:\Projects\FGA\api-cloudflare\probes\lightroom\FGA-GroupPost-v1.lrplugin` |
| Fixture identity | Version `0.0.1.1`; toolkit `com.sixbuckssolutions.fga.grouppost.v1.lrc15` |
| Native command | Library: **Characterize synthetic POST v1**, once |
| Native route | Supported Node REPL / `@oai/sky` and observed Lightroom window |

The manifests bind all base artifact bytes and the additional bridge code/operator procedure. Changed bytes, configuration, target, caller or delivery scope require renewed review before approval. This document is not an executable approval file.

Use the retained private configuration at `C:\Projects\FGA\api-cloudflare\.coordination-runs\group-post-execution-bridge\private\config.json`. Its account is sourced from #0036's retained restoration inputs and its workers.dev subdomain from the retained GET ready artifact. No account identity needs to be requested again. Public evidence must not expose those values. Exact configuration bytes must be included by SHA2-256 in the future approved packet; the primary must record and verify that approved-packet digest before apply. Neither private configuration nor credentials were read for this decision document.

The proposed service configuration remains compatibility date `2026-10-16`, workers.dev on, previews/observability/logpush off, and only `DB`, `RUN_ID`, `ROLE`, `SUBDOMAIN`, `EXPIRES`, `ACCESS`, `CANARY` bindings. Fresh synthetic ACCESS/CANARY values only. No production routes, bindings, photo data, Flickr calls or feature activation are in scope.

## Finite runtime and retained paths

- Exactly 23 POST cases, at most ten controlled redirect arrivals and one diagnostic GET; one native invocation, with no automatic retry. Cases include proof, one/sixty groups, bounded statuses, same/receiver-origin redirects, oversize responses, timeout, lost response and Cancel last.
- Serving lifetime 1,200 seconds; preparation deadline 240 seconds. Start native work only with 600-1,200 seconds remaining. Stop new work at resource expiry minus 240 seconds. The bridge's owner cutoff is 960 seconds from claim, with the earlier resource cutoff retained.
- At most 120 provider calls, 20-second socket timeout each, 64 KiB provider response cap, no redirects/retries. Native request cap 16,384 bytes; 64 accepted requests per role; 46 case rows; fixture response allocation at most 2,097,153 bytes. Three delays are 16 seconds; native SDK timeout argument is 15 seconds.
- A stop allows at most 20 seconds for existing native I/O to return, bounded by the cleanup reserve. This is not proof of active abort or a hard wall timeout.

| Artifact | Exact path |
| --- | --- |
| Owner output | `C:\Projects\FGA\api-cloudflare\.coordination-runs\group-post-characterization\c01ba6d2c2754597aa311c9f\` |
| Native root | `C:\Temp\FGA-group-post-v1\` |
| Native markers | `target.json`, `target.used.json`, `status.json`, `stop.json` beneath that root |
| Bridge handshake | `bridge\owner.json`, `bridge\invoke.json`, `bridge\ack.json`, `bridge\operator-stop.json` beneath that root |
| Future approved packet | `C:\Projects\FGA\api-cloudflare\.coordination-runs\group-post-execution-bridge\private\approved-packet.json` |
| Future operator credential | `C:\Temp\fga-post-operator-token.txt` |

Refuse existing attempt/output/handshake/native marker files and their reviewed temporary siblings; never erase them to replay this run. Account/subdomain inputs are retained; credential provision is still a future execution input. No claim is made here about the credential file's current existence. Its presence, permissions and content were not inspected.

After approval, Terry supplies a narrowly scoped temporary provider token through that exact private file, restricted to the local operator and SYSTEM. The bridge reads it boundedly into memory only after approval/configuration/artifact verification. Never reuse the inventory token, export a CI secret or put a token in arguments, native targets, receipts or public evidence. Before execution, establish the token's effective account/resource grants, expiry and revocation owner; the bridge validates syntax and does not prove those provider permissions or revocation. The 1,200-second service expiry is not credential expiry. Existing teardown does not promise deletion/revocation of the operator token. An approved JSON packet binds integrity; it cannot substitute for Terry's consent.

## Native control and cleanup decision

The approved native target is Lightroom Classic 15.6 / SDK 15.3; observe the actual host before execution. A different host is a renewed review gate. The fixture uses synthetic data without catalog APIs, selected photos, a catalog fixture or catalog writes. Keep host metadata/screenshots private.

The primary verifies the exact observed fixture identity and menu command, the live correlated Python owner, finite deadlines and absence of stops immediately before the one invocation. Set the persistent attempted flag before input. An uncertain or lost input acknowledgement is terminal; never invoke again. At the visible **Case cancel** caption, use the observed progress Cancel control once.

The prior intentional Escape remains a withdrawal of native control. Native input may resume only with Terry's explicit permission at this action boundary. A new Escape immediately latches stop: no reset, relaunch, retry, dialog reopening or alternate route. Owner loss, unknown input, expired deadline, terminal receipt or any stop marker also ends characterization input. The Python owner may complete bounded observation and remote teardown.

The same attached Python process, identified by `str(os.getpid())`, owns remote cleanup through `run_once` and `finally`. Delete only journal-acknowledged identities after exact Worker RUN_ID/ROLE/EXPIRES and D1 UUID/name checks; verify terminal 404s for both Workers and D1. Unknown identities, lost acknowledgements, failed reads or unverified deletion remain `cleanup_unconfirmed`; expiry is not deletion proof. Abrupt process death cannot guarantee finally cleanup: preserve the exact journal for separately authorized recovery rather than start a replacement owner.

Plugin Manager unregistration and local marker cleanup are separate from remote deletion. Review receipts and verify this exact fixture/paths first. A Windows UI deletion needs its own applicable action-time confirmation. After Escape, defer all UI cleanup until Terry permits native input again. Retain unresolved private journal/markers as recovery evidence; never claim native cleanup because remote teardown succeeded.

## Owner choice and evidence limits

The final action-time request must identify this exact run/manifest/bridge/configuration binding, permit resumption after the prior Escape, and explicitly cover fixture registration/load, one invocation, controlled Cancel and same-job remote creation/teardown. Terry may approve that bounded attempt or defer it. No owner decision is recorded by this document.

The installed [Computer Use skill](C:/Users/TDO-XPS15-2024/.codex/plugins/cache/openai-bundled/computer-use/26.1013.40934/skills/computer-use/SKILL.md) directs reading [confirmations.md](C:/Users/TDO-XPS15-2024/.codex/plugins/cache/openai-bundled/computer-use/26.1013.40934/docs/confirmations.md), which says **“Blocking confirmation required immediately before the action”** for Windows install/run of newly acquired software. This is the applicable reason for the final fixture action confirmation. The historical packet's older skill location is provenance, not the current installed policy reference. Remote API cleanup and later Windows UI cleanup have separate authority boundaries.

#0145's completed independent review resolved sticky-stop/terminal races, unknown-dispatch grace and approval/configuration snapshot substitution; its 16 offline tests passed. That is engineering evidence, not native execution proof. Current local artifact verification is recorded separately for this handoff; do not infer a fresh runtime test from hashes.

Keep only closed outcomes, statuses, byte counts, header-presence/exact-match booleans and wall timings in public evidence. Failed/stopped/unmeasured results stay explicit regardless of teardown success. This finite run cannot qualify production transport, credentials, group additions or a later Lightroom major. #0037 remains unqualified; #0044 remains NO-GO and #0043 restoration remains negative in their independent scopes. No new provider request, cloud resource change, native initialization/input, credential read or owner execution consent occurred in this preparation.
