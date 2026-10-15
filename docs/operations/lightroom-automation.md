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
