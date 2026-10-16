# Single local POST execution bridge

Date: 2026-10-16. Ticket #0145. Offline engineering preparation only. #0059
owns action-time approval; #0060 owns execution. This does not reopen the
accepted #0058 evidence or qualify production transport.

`scripts/group_post_execution_bridge.py` supplies the concrete `Provider`,
current numeric `str(os.getpid())` owner, synthetic markers, `invoke_native`
and `stop_requested` to the reviewed `group_post_characterization.run_once`.
That same Python job prepares resources, publishes the target, holds through
terminal/stop/deadline and unconditionally exports observations and performs
identity-matched cleanup. No daemon, command server, subprocess, native import
or replacement Computer Use client is involved.

## Exact private inputs

Fixed run: `c01ba6d2c2754597aa311c9f`. The private configuration is
`C:\Projects\FGA\api-cloudflare\.coordination-runs\group-post-execution-bridge\private\config.json`.
Its closed schema contains `runId`, `accountId`, `subdomain`, `tokenFile`,
`accountSource`, `subdomainSource`. The concrete account identity comes from
#0036's retained `restoration-inputs.json`; the workers.dev subdomain comes from
the retained `ready-38945950488/ready.json`. Exact source references and values
are bound in the private configuration; private provenance paths are pinned in
the bridge. Preparation projects only account/subdomain metadata and never
opens any token file. Both identities are already retained inputs, not new owner
questions. The approval binds the complete configuration's SHA2-256. The apply gate reads each approval, configuration and manifest once as bounded bytes, computes its digest from those bytes and parses that same snapshot. File replacement after reading cannot substitute later parsed scope or identities before credential access.

The dedicated future provider credential delivery is exactly
`C:\Temp\fga-post-operator-token.txt`. It is currently absent. After #0059
approval, the owner supplies a narrowly scoped operator token through this
private local file, with access restricted to the local operator. Token
provisioning and permission checks belong to that separately approved execution,
not preparation. Do not reuse #0036 inventory authentication, export a CI secret
or put the token in argv, environment, target, acknowledgements or evidence.
The apply path reads at most 4,097 bytes in memory after approval/config/artifact
verification and accepts only 20–4,096 ASCII letters, digits, `_` and `-`, with
no newline. No provider exception or token contents reach CLI output. Provider
authentication reaches only the existing fixed-account `Provider` header.

The offline command reads no private configuration or credential:

```console
uv tool run --from uv==0.12.5 uv run --frozen python -m scripts.group_post_execution_bridge
```

After final review and #0059 action-time approval, #0060 may create the exact
private `approved-packet.json` beside config. It is the offline description with
`mode` changed to `approved_execution` and one additional `configSha2_256` field.
It binds bridge bytes, approved manifest digest, configuration bytes, run, paths,
native route and one-attempt limit. No approval file is created in preparation.
Record its SHA2-256 separately in the approved action packet. Execute only:

```console
uv tool run --from uv==0.12.5 uv run --frozen python -m scripts.group_post_execution_bridge --apply --approved-sha2-256 <exact-approved-packet-digest>
```

An existing approval file is an integrity binding, not evidence of user consent.
The primary must obtain the separate action-time approval required by the
Computer Use skill. The job remains an attached bounded execution session while
the same primary operates the supported Node REPL route. Never detach it or
leave cleanup for a later turn. Changed artifacts/configuration need renewed
review and approval. Missing credential delivery prevents execution, not offline
engineering readiness.

## Concrete fixed-file operator handoff

The existing native interface remains exactly `C:\Temp\FGA-group-post-v1\`:
`target.json`, `target.used.json`, `status.json`, `stop.json` and their reviewed
temporary siblings. The fixture moves target to used before any POST. Existing
native/output files refuse a fresh attempt. The bridge exclusively creates
the additional `bridge` subdirectory: an existing directory refuses ownership.
Never remove stale files to replay this proposed run.

Only these additional files are used:

| File inside `bridge` | Writer | Meaning |
| --- | --- | --- |
| `owner.json` | Same Python job | Active/closed owner plus deadline |
| `invoke.json` | Same Python job | One request for the exact Library command |
| `ack.json` | Primary Node REPL operator | One input result; no retry authorization |
| `operator-stop.json` | Primary Node REPL operator | Sticky Escape/unknown/operator stop |

Every identity contains `schemaVersion: 1`, `planVersion: fga-group-post-v1`,
the exact `runId`, numeric string `owner`, and fresh 32-hex `generation`. Request
adds only `action: invoke_characterize_synthetic_post_v1_once`, fixed `target`
and `status` path strings and `deadlineUnix`. It contains no account, endpoint,
token or synthetic marker. Acknowledgement is exactly identity plus
`outcome: dispatched`; `unknown` or `stopped` also terminate the attempt. No
other action, command, executable, script body or arbitrary URL is accepted.
Any stop-file presence stops, including stale, malformed or foreign contents.

The future primary performs the following bounded sequence; no watcher or
automatic UI loop runs in Node REPL:

1. Read the installed Computer Use skill and guidance/confirmations. After
   action-time approval, initialize only its supported `@oai/sky` package in
   Node REPL. Use `scripts/lightroom_automation.mjs` and returned window objects
   to select the approved Lightroom Classic 15.6 window. Verify the separate
   manifest-pinned fixture registration/version/Library command through observed
   UI. Never construct handles or use guessed indexes.
2. Once the attached Python job publishes `invoke.json`, use Node's ordinary
   `node:fs/promises` bounded file reads. Require the exact closed request schema,
   expected paths/run/action, active correlated owner, finite unexpired request
   and owner deadlines. Check that the owner PID is still live with
   `process.kill(Number(owner), 0)`; a failure refuses input. Check that neither
   native nor operator stop exists and no matching native terminal receipt exists.
   A stale/foreign receipt refuses input. Recheck owner/deadlines/stops immediately
   before the action. File I/O is coordination, never a custom Sky protocol.
3. Keep a persistent `globalThis.fgaPostAttempt` containing the complete request
   identity, and set `attempted: true` **before** issuing the single observed
   Library command action. If any attempt is already recorded, refuse another
   invocation. UI observations and menu navigation may precede this action;
   each follows the skill's observe/inspect/one-action/refresh rule. Menu indexes
   must come from the immediately preceding observed accessibility tree. This
   concrete requested command is **Characterize synthetic POST v1**; no callback
   supplied by a file is executed.
4. After that one input returns, atomically publish `ack.json` using an exclusive
   `ack.json.tmp` write then rename, with only request identity plus
   `outcome: dispatched`. This acknowledges input dispatch, never POST success.
   Do not wait for the full native run before acknowledging. If input/refresh
   throws or its result is unknown, publish identity plus `outcome: unknown`
   when possible, publish `operator-stop.json` and issue no further native input.
   Lost acknowledgement, expired request or stale generation never permits a
   repeat action; observe files only while Python cleans up.
5. Follow the fixture's progress using supported observations. At **Case cancel**,
   use its observed progress Cancel control once as approved. Intentional Escape
   immediately latches `globalThis.fgaPostAttempt.stopped = true` and publishes
   `operator-stop.json` (identity plus `reason: escape`). Do not reset, relaunch,
   reopen dialogs, retry or use an alternate route. A native terminal receipt is
   terminal even if its outcome is failed/stopped. No UI input follows owner loss,
   deadline, terminal, Escape, uncertain input or any stop file.

The request's acknowledgement deadline is 30 seconds; the Python callback waits
at most 31 finite iterations, checking stop before accepting an acknowledgement.
It validates generation/owner/run/schema/plan and the exact ack shape. Missing,
foreign, malformed or unknown acknowledgement latches stop and raises into the
reviewed lifecycle's `finally` cleanup. Before raising for an unknown dispatch, the bridge publishes native stop and permits at most 20 seconds for existing I/O to return, ending sooner for a validated terminal receipt or the reserved cleanup cutoff. This waiting period does not claim active abort. The request remains immutable and
retained for review. It is never republished. Stop checks also run before
preparation, publication and invocation through the existing lifecycle.

The job's absolute and elapsed owner cutoff is 960 seconds from claim, with
the existing earlier resource-expiry-minus-240 cutoff retained. The native stop
watch permits at most 20 seconds for existing native I/O to return. The existing
120-call provider budget and 20-second socket timeout remain unchanged; these
are finite bounds, not proof of hard wall cancellation. Abrupt OS/process death
cannot guarantee a Python `finally`; the operator must stop input on owner loss
and preserve the identity journal for separately authorized recovery. No second
job assumes this owner's resources or guesses remote deletion identities.

## Receipts and local teardown

The reviewed lifecycle alone exports bounded observations and deletes only
journal-acknowledged resources after exact identity checks. Failed/foreign reads,
lost acknowledgements or uncertain deletion remain `cleanup_unconfirmed`.
Native completion does not imply remote cleanup. Remote cleanup does not imply
successful measurements. Handshake files, native markers and exact journals
remain private; their removal and fixture unregistration require identity checks
in #0060 after receipt review. The bridge samples its sticky stop again after the reviewed lifecycle returns, so a concurrent native terminal and Escape cannot report characterized or clear the stop. It updates the final private action and owner-journal verdict to preserve that stop, then marks its owner closed in `finally`.
Public evidence contains only closed outcomes/counts/booleans and source hashes.

Offline tests compose the actual `run_once`, fake provider and file operator,
covering target consumption, stops around publication, unknown/lost/foreign
acknowledgements, stale paths, deadline/owner loss, cleanup uncertainty and
credential/error-output refusal. They neither load the native fixture nor
initialize `@oai/sky`. Run with the pinned prefix shown above and
`python -m unittest tests.test_group_post_execution_bridge`.


The no-input rule terminates characterization input. Any later Plugin Manager
cleanup is a separate Windows UI action with applicable action-time confirmation.
Intentional Escape has withdrawn control: defer that UI cleanup until the user
permits input again. Same-job remote teardown may continue; do not equate its
success with native registration cleanup. Retain private files when cleanup is
not yet authorized or identity is uncertain. The final companion manifest is
`probes/group-post-characterization/execution-bridge-manifest.json`; it records
the reviewed bridge and operator document alongside the unchanged #0058 manifest.
