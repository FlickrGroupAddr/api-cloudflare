# Existing-photo synthetic native qualification fixture

Date: 2026-10-16. Status: all ten synthetic native scenarios passed on Lightroom Classic 15.6; network and production qualification remain pending.

This procedure exercises the actual `ExistingPhotoClient.lua` and
`ExistingPhotoBrowser.lua` in `clients/lightroom/FGA-LrC15.lrplugin` through a
separate SDK 15.3 development plug-in. It supplies synthetic discovery, PNG,
binding-proof and membership responses; it imports no HTTP or catalog API.
The current installed host is Lightroom Classic 15.6. The fixture does not
qualify the native network boundary, turn on a feature, register the release
existing-photo action, or change production qualification flags.

Authority is architecture-design `docs/README.md`, accepted ADRs 0060/0061 and
the accepted existing-public-photo intake contract. The detailed hosted-thumbnail
candidate remains Proposed. See [the hosted handoff](hosted-thumbnail-handoff-2026-10-15.md)
for the independent endpoint and native transport gates. Synthetic stale-proof
and error responses test client handling, not the correctness of deployed
installation/link/grant fencing.

## Fixture and isolation

Load only `probes/FGA-ExistingPhoto-Qualification.lrplugin`, version **0.0.1.5**,
when the primary desktop operator is ready. Keep its location in the checkout:
the runtime resolves the release bundle relative to the fixture directory and
loads those source files directly. The release browser exposes an explicit
`Browser.new(sdk, client)` dependency factory around its existing implementation;
the fixture supplies scoped SDK adapters and the actual release client. The
release `Browser.run` API lazily creates its default instance with ordinary
SDK imports and client require. No browser implementation is copied; no global
`import`, `require`, environment or shared module cache is replaced. The fixture must be reloaded after runtime changes. It targets
SDK 15.3 on the separately recorded host build; SDK targeting is not evidence
of execution in host 15.3.

The fixture injects transport/JSON responses and a narrow cache adapter. The
cache adapter delegates creation, naming, image file I/O and ordinary deletion
to the actual SDK/filesystem, rooted only beneath
`C:/Temp/FGA-existing-photo-qualification/cache`. It tracks its own browser
run directories and checks their absence after context cleanup. It does not
enumerate, delete or inspect the production browser cache. One scenario returns
false for deletion of the current page; final context cleanup still delegates
recursive deletion of the fixture-owned run directory to the SDK. Remaining
files or unconfirmed cleanup fail the result; do not remove a failure before
recording it. Never delete neighboring directories.

All pictures are an original 150-by-150 blue/gold PNG checkerboard. Titles,
IDs, groups and timestamps are synthetic. The fifth photo has a 128-character
opaque ID; some titles are long, and the first title is empty. No real metadata,
credentials, photos or provider URLs are read. A static Flickr-shaped URL in
the synthetic protocol is never requested. All synthetic thumbnail requests
yield through `LrTasks.yield`; cancellation during a thumbnail is a controlled
fixture cancellation flag, not proof of native network interruption.

## Native run order

Before loading, record source SHA2-256 values for Info.lua, Run.lua,
Qualification.lua, synthetic.png, the release Info.lua, ExistingPhotoClient.lua,
ExistingPhotoBrowser.lua and dkjson.lua in the primary's sanitized evidence.
Bind each observation to those artifacts and the receipt host/build. Source
hashes are external provenance; the runtime receipt does not calculate hashes.
Do not use a previous version's receipt as evidence for a changed source file.

Use Library > Plug-in Extras > Existing-photo synthetic qualification. Each
invocation offers a scenario chooser, then runs the actual browser. Cancel in
the chooser starts no scenario and leaves the prior receipt unchanged. Run one
scenario at a time; the runtime ignores concurrent invocations while active.
Observe after each desktop action. Do not repeat the already completed #0027
selection or #0029 outbox tests.

| Order/scenario | Operator actions | Expected result |
| --- | --- | --- |
| 1 `success` | Observe five fully loaded thumbnails; inspect blank/long title, dates, full selectable opaque ID, selection and scrolling. Select any row, Verify Photo, then Close memberships. | Exact selected identity shown with fresh proof and timestamped synthetic membership; one proof and one membership read. |
| 2 `navigation_cancel` | Next, Previous, Cancel. | Page 2 hides its repeated ID and explains that it was already shown; return to five complete rows; no proof or membership read. |
| 3 `empty` | Inspect explicit empty state; Cancel. | No photos observed; no thumbnail/proof/membership request. |
| 4 `cancel_during_thumbnail` | Start scenario. | Controlled cancellation after first yielding thumbnail response; no page or proof. |
| 5 `discovery_error` | Dismiss warning. | Discovery unavailable; no rows or proof. |
| 6 `malformed_page` | Dismiss warning. | Duplicate identity makes the entire page invalid; no thumbnails or rows. |
| 7 `thumbnail_error` | Dismiss warning. | Invalid second image prevents publication of all rows; first staged image removed. |
| 8 `stale_proof` | Select any row, Verify Photo; dismiss warning. | Linked-account-changed message; no membership read or stale selection reused. |
| 9 `membership_error` | Select any row, Verify Photo; dismiss warning. | Membership Unavailable; no prior or partial membership dialog. |
| 10 `cleanup_failure` | Next; dismiss warning. | Injected page-delete refusal prevents navigation/proof; context removes the owned run directory. |

A `passed` fixture receipt checks request counters, full-page staging before
presentation, expected result and cleanup. It cannot judge recognizability,
layout, exact-ID accessibility or subjective usability. Record those operator
observations separately. Wrong actions cause a failed scenario; rerun only the
relevant scenario with the documented sequence. UI Cancel and controlled
in-flight cancellation are deliberately separate cases.

## Receipt and failure handling

Read `C:/Temp/FGA-existing-photo-qualification/status.json`. Every started run
publishes `outcome: running`, `terminal: false`, then replaces it with a complete
terminal result via a temporary sibling and SDK move. Replacement deletes only
the previous stable receipt; there may be a short missing-file interval. File
write, close, delete and move results are checked. A missing or nonterminal
receipt, parse error, wrong schema/run/version or failed result is not a pass.
Startup or receipt-publication failure can leave no new terminal receipt; do
not infer success from an old terminal receipt. The current action's `runId`
and running-to-terminal transition must match. This is an ephemeral status
handoff, not crash/power-loss durability or a retained run history.

Schema 1 identifies `probe: existing_photo_synthetic`, `probeVersion`,
`releaseVersion`, `runId`, validated numeric host major/minor/revision and
bounded host build, scenario, outcome, terminal state, request/dialog/state
counts, `completePages`, `cacheClean` and `reasonCode`. A top-level sanitized
runtime failure can omit counters and reports `cacheClean: false`.
`nativeTransportQualified` and `productionQualified` are always false.
No response bytes, paths, URLs, titles, IDs, credentials, SDK exception strings
or image bytes enter the receipt. Copy only the schema-valid sanitized receipt
into evidence if retention is needed before the next scenario overwrites it.
The browser's existing logger can record only its fixed cleanup-failure category.

If the native fixture cannot load, the picture fails to decode, a dialog fails,
the receipt cannot publish, or owned cache remains, record the sanitized failure
and source/version/host provenance. Stop dependent qualification work and fix
the fixture or release code in a reviewed revision. Do not toggle release gates
or bypass the browser's cleanup fences to make a scenario complete.

## Offline verification and remaining gates

`uv run --frozen python -m unittest discover -s tests -p test_existing_photo_qualification_native.py -v`
passes eight test methods, including all ten scenarios, actual release view-tree
construction, duplicate suppression, no partial page publication, cleanup,
registration/version consistency and PNG CRC/pixel validation. Ruff and Pyright
checks cover the new Python test. The Adobe SDK 15.3 Windows Lua compiler
accepts Info.lua, Run.lua and Qualification.lua with `-p`. Lua executes under actual Lua 5.1 through
Lupa; SDK objects are stand-ins in these tests. These results are fixture
verification only. The primary loaded build 0.0.1.1 successfully, but its command failed before
showing the chooser because the fixture misspelled the documented
`viewFactory:popup_menu` method. Build 0.0.1.2 corrected that defect. The offline
suite now invokes the native chooser with an explicit supported-control
whitelist and verifies that context cleanup releases the active guard after
a chooser construction error and after Cancel. Build 0.0.1.3 has not yet been
reloaded or run natively by this agent.

The primary owns exact installed-host execution and subjective observations.
The separate disposable hosted/native matrix must still exercise actual
`LrHttp.get` against the fixed trusted FGA endpoint/edge: response allocation,
redirects/Authorization handling, bounded bodies/timeouts, disconnect behavior,
and current authority changes. This fixture cannot prove any of those network
properties. Production contract acceptance and explicit activation approval
remain independent gates; Flickr writes, intake, group submission, release
registration and qualification flags remain paused.

SDK-symbol review for build 0.0.1.3 used the installed SDK 15.3 API Reference,
not runtime guesses: LrView factory controls/spacing and bind/osFactory,
LrApplication.versionTable, LrBinding.makePropertyTable, LrDate.currentTime,
LrDialogs.presentModalDialog/message, LrFileUtils createAllDirectories/exists/
chooseUniqueFileName/delete/move, LrFunctionContext.callWithContext and
addCleanupHandler, LrLogger enable/warn, LrPathUtils child/parent and LrTasks
startAsyncTask/pcall/yield. The wrapper resolves all of these documented names;
its chooser uses `popup_menu`. Release-module SDK calls remain subject to their
separate native execution gates.

Build 0.0.1.2 reached the native chooser but failed the checked SDK move of the
running receipt before any scenario executed. A valid temporary envelope was
created; no stable receipt existed. Build 0.0.1.3 uses canonical Windows
`C:\Temp` plus `LrPathUtils.child` for every fixture-owned receipt, cache,
asset and release-source path. A strict Windows-path regression now tests these
joins, real temporary-file publication/replacement and SDK-style destination
requirements, and confirms false delete/move results remain hard failures.
This correction is a candidate fix; native receipt publication still requires
the primary's reload and observation. No failed move is treated as success.

Build 0.0.1.3 published a valid running and terminal receipt on the native host,
then failed before page presentation inside fixture initialization. No scenario
UI or request result passed. Build 0.0.1.4 adds closed phase diagnostics:
`load_json`, `load_client`, `build_adapters`, `load_browser`, `browser_run`,
`cache_cleanup`. `failurePhase` retains the phase at the protected failure,
`errorType` records only Lua's type label, and `standardFunctions` records boolean
callability for loadfile/setfenv/setmetatable plus whether `_G` is a table.
No exception message, source location, path or response data is serialized.
An offline injected missing-setfenv failure verifies that the outer catch retains
`load_browser`, zero requests and sanitized diagnostics. These diagnostics do
not infer a native failure cause; the next native receipt must establish it.

Build 0.0.1.4 localized the native initialization failure to `load_browser`:
`setfenv` is unavailable in this installed host, with zero requests or presented
pages. Build 0.0.1.5 removes the dependency entirely. The explicit release-browser
factory loads without ambient imports/require; production callers retain the
lazy default Browser.run and validImage/constants API. An offline actual-Lua5.1
regression removes setfenv and runs the complete success fixture through that
same factory. All 34 existing client/browser tests and eight fixture tests pass;
SDK15.3 compilation, Ruff and Pyright pass. The primary owns the release build
increment, exact source provenance and native confirmation. No native success is
inferred from this offline correction.

## Primary native result, 2026-10-16

The primary loaded fixture **0.0.1.5** against release modules **0.2.0.6** in
Lightroom Classic **15.6**, build `202609251514-f839cde9`. All ten scenarios
above passed with ten distinct terminal run IDs, complete page staging and
confirmed fixture cache cleanup. The primary observed the supported UI controls,
recognized the checkerboard pictures, inspected the wrapped long title and
full selectable 128-character ID, exercised navigation and cancellation, and
observed the expected stale-proof, discovery, thumbnail and membership warnings.
The cleanup-refusal scenario blocked navigation before the function context
removed the owned run directory. The final result dialog was closed and the
host was left running without an active fixture dialog.

[The retained native record](../evidence/existing-photo-native-synthetic-2026-10-16.json)
contains exact tested source SHA2-256 values, sanitized operator observations
and all ten runtime receipts. Earlier initialization failures are retained in
[the prior-failure record](../evidence/existing-photo-native-prior-failures-2026-10-16.json);
their receipts are not reused as success evidence. No runtime source changed
during the ten passing runs.

This passes the synthetic native UI/client/cache portion only. Injected
responses do not establish actual LrHttp response allocation, redirect or
Authorization handling, network cancellation, provider authority fencing or
production endpoint behavior. Those independent gates remain open; no
registration, write gate, qualification flag or live submission was enabled.
