# Lightroom automation launch and recovery

Ticket #0033 restores the supported native-control entry point for FGA host
tests. Use `scripts/lightroom_automation.mjs` through the computer-use skill's
Node REPL and documented `@oai/sky` API. Read that skill before UI work; this
runbook does not replace its interaction, consent, or stop rules.

## Launch or reuse

Initialize `sky` exactly as the installed computer-use skill documents. Inspect
`await sky.list_apps()` and select Lightroom Classic's returned app ID. Then,
inside the same Node REPL session:

```javascript
globalThis.launcher = await import(
  'file:///C:/Projects/FGA/api-cloudflare/scripts/lightroom_automation.mjs'
);
globalThis.lrWindow = await launcher.ensureLightroomWindow(sky, {
  appId: lrAppId, // Exact ID from the inspected inventory, not a guessed path.
  timeoutMs: 60000,
});
globalThis.lrState = await sky.get_window_state({
  window: lrWindow, include_screenshot: true, include_text: true,
});
```

Inspect the refreshed state before interacting. The helper returns a current
window identity; it does not establish that a workflow is ready or that every
test has passed. Keep window objects, screenshots, and accessibility content
inside the private UI session. Do not serialize the entire state to logs: it
includes screenshot payloads and may include catalog names and photo metadata.
An optional `log` callback receives only fixed launcher stage names.

The launcher reuses one existing window or launches the selected installed app
once. It polls for a returned window and rehydrates that identity. The installed
app ID can be a shell GUID while the returned window's `app` is a process ID;
use the returned ownership value rather than replacing it with the shell ID.
Multiple matching apps or windows fail explicitly instead of choosing one.

## Known startup false negative

On 2026-10-15, `launch_app` reported `launched app did not expose a targetable
window` even though Lightroom started. A fresh app inventory exposed its usable
window. The helper recognizes only that exact error for the selected app and
continues bounded enumeration; it never retries the launch itself. Other errors
propagate unchanged. It does not patch the bundled computer-use runtime.

A deadline bounds this caller, not an already dispatched native operation.
After a timeout or unknown outcome, re-enumerate before deciding what to do.
Never blindly repeat a launch or UI action. After a dialog closes, a refresh
may report `window is not a usable app window`; re-enumerate and rehydrate,
then observe whether the action already completed before sending another input.

## Native menus and dialogs

Follow observe, inspect, one action, refresh. In the verified 15.6 host, `Alt_L+h`
opened Help. Popup accessibility elements were sometimes reported in the tree
but unavailable to indexed clicks. The supported fallback was the popup's own
current screenshot ID with coordinates inspected in that bounded screenshot.
The same approach opened and closed About Lightroom. Main-window coordinates
did not reliably account for the popup's frame/fullscreen offset. Do not copy
coordinates, element indexes, screenshot IDs, or window IDs from this runbook
or a previous observation; inspect each new state.

Terry normally uses full-screen mode. In the 2026-10-15 native run, `Control_L+Alt_L+f` exposed the menu bar but repeating it did not restore the previous mode. `Shift_L+f` cycled the native screen modes; observe after each press and stop at the intended mode. Do not infer a toggle from the shortcut's name or a completed input call.

## Stop and test boundaries

An intentional Escape stop is terminal for computer use in that turn. Preserve
the original cancellation; do not reset the session, disable Escape, relaunch,
or use another automation route to defeat it. A previous latched stop cleared
in a later user-authorized turn with a fresh supported session. If the stop
persists, hand off that concrete runtime problem rather than loop.

Use only the documented computer-use API. Do not invoke internal helpers,
invent helper protocols, spawn Lightroom through a shell, or use alternate
Windows automation. The launcher sends no UI input and performs no catalog,
credential, Flickr, or network mutation itself. Subsequent tests still need
their own fixtures, permissions, and acceptance evidence. In particular, use
the outbox probe's guarded empty catalog, preserve production write gates, and
keep plugin installation and other consent-sensitive actions within the
computer-use skill's authorization rules.

## Hand back desktop control

Terry clarified on 2026-10-18 that a visible blue Computer Use boundary tells
him the primary operator is still busy. Complete or safely stop the native work
and any in-flight owner cleanup, then explicitly end the supported Computer Use
session before announcing handback. A prose message alone is insufficient.

The installed Sky API exposes no documented session-shutdown method. In the
current supported tool surface, `mcp__node_repl.js_reset` resets the owned
JavaScript kernel and clears its controller context. Use that supported reset
for handback after all native work is terminal. Report the reset accurately;
it is not an observed guarantee that the app has removed its blue boundary.
Do not issue guessed Sky methods, kill helper processes, or restart the session
for source-only work. Never use a reset to defeat a user Escape stop or unknown
native operation. Later native work requires fresh applicable authority and a
new observed window selection.

## Verification and handoff

`node --test tests/lightroom_automation.test.mjs` covers reuse, cold start,
delayed-window recovery, identity handling, ambiguity, deadlines, cancellation,
and fixed-stage logging (18 tests). Native evidence is recorded separately in
`docs/evidence/lightroom-automation-2026-10-15.json`.

The live run verified Lightroom Classic 15.6 / Camera Raw 18.7, opened and
closed About, reused the running application without launching again, and
performed a normal close followed by a cold start with exactly one launch.
The installed FGA-LrC15 release displayed version 0.2.0.1 in Plugin Manager;
its existing stored-credential read-only check returned **Connected** through
native interaction. Plugin Manager was closed afterward. No new plugin was
installed and no credential was entered.
This recovers the automation prerequisite for #0022, #0027, and #0029; their
workflow-specific and owner review gates remain separate.

## Reviewed command manifests

Use `scripts/run_reviewed_manifest.py` for literal command-manifest ingress.
Default invocation is disabled and exits without reading a manifest or launching
a child. `--check` validates without dispatch. `--execute` launches one child and
returns its exit status; a failure does not trigger a retry.

Both active modes require `--manifest <absolute-json-path>` and
`--sha2-256 <exact-lowercase-reviewed-digest>`. The JSON document has exactly:

```json
{
  "executable": "<absolute-native-executable>",
  "cwd": "<absolute-working-directory>",
  "environmentOverrides": {"NAME": "literal value"},
  "argv": ["literal", "argument", "strings"]
}
```

- `argv` excludes the executable. Do not stringify parsed non-string values,
  rebuild command text, invoke a shell, or parse the packet with a date-coercing
  JSON reader. Python JSON retains ISO UTC strings unchanged.
- The checked bytes are bounded to 1 MiB, read from a stable regular file without
  symbolic-link/reparse-point path components or hardlink aliases, and matched
  to the exact digest.
  Duplicate keys, unknown fields, non-string arguments/environment values, NULs,
  invalid paths/encodings, and oversized inputs refuse before child launch.
- Limits: 512 argv members; 32,767 characters per literal string; 4,096 per path;
  128 environment overrides. Native Windows command/environment limits count
  UTF-16 code units. Windows batch executables refuse because they require a shell.
- The actual child receives `[executable, *argv]` with `shell=False`, the manifest
  working directory, and inherited environment with the literal overrides applied.
  Manifest values are not printed. Child output remains the child's responsibility.

Before dispatch, the operator must still bind the stage-specific expected script,
argv prefix/width, source and packet identities, and reviewed environment. The
manifest hash and `--execute` flag establish neither approval nor a current valid
run. Existing authorization, credentials, finite limits, deadlines, claims,
cleanup, terminal-state, and no-replay checks remain owned by the underlying
protocol. The launcher supplies no fresh deadline, automatic retry, provider
logic, forced termination, positive qualification, or revival of a spent run.

The regression suite launches only a benign native Python receiver with synthetic
28/50/62-argument vectors and proves exact strings, UTC parsing, cwd and environment
at that boundary. Separate full rehearsal must exercise the real entrypoint and
the relevant pure stage validators before any newly authorized live attempt.

### Before issuing a qualification token

Complete local preparation before selecting live execution clocks:

1. Independently review the exact launcher and run its native argument regression
   tests. Rehearse the full local operator sequence through that same entry point,
   with provider and GUI test doubles identified explicitly.
2. Check prospective stage manifests with `--check`; independently bind each
   stage's executable, argument prefix and width, source pins, cwd and environment.
   Keep UTC values as literal strings throughout.
3. Recompute the declared source/role inventory and validate record fields and
   finite timing relationships. Resolve changed declarations before issuance;
   never skip a role to satisfy an old count or retime an old observation.
4. Prepare the ordered handoffs: observed issuer exit, immutable terminal ledger
   snapshot, independent issuer-result review, collector packet/result review,
   current native/history evidence, independent final-packet judgment, finalize,
   and a separate explicit operator release.
5. Establish applicable owner authority before starting the new attempt's fixed
   clocks. Preserve spent claims and stopped runs. Unknown outcomes stop without
   automatic replay; successful local checks supply no current credential,
   provider, native or catalog facts.

Local rehearsal success is a prerequisite to proposing another live attempt,
not a POST qualification result. Native observations, actual provider receipts,
cleanup, exact-child retirement and the existing release gates remain separate.