# #0216 proposed indexed native dispatch

Revision r3; source/synthetic candidate only, 2026-10-20. Not accepted or executed.
actionReady=false; nativeRouteReady=false; productionQualified=false.

This proposal replaces the final coordinate action in a NEW #0161 successor
packet. It does not amend the spent attempt, its frozen runtime cells, the
current API checkout, or any existing credential/approval/manifest.

## Supported boundary and prerequisite

The installed computer-use 26.1013.40934 API documents
`click({window, element_index})`, where the index comes from the latest
`get_window_state()` accessibility tree. Its guidance requires observing,
returning for inspection, then exactly one action and immediate refresh.
There is no documented accessibility cache-generation getter or snapshot token
for indexed clicks. The candidate therefore cannot independently attest an
out-of-band capture or native change. One primary must own all desktop input
and Sky access; no other capture, navigation, focus change, or UI input may
intervene between the controller observation and its action. The protocol
checkpoint performs file work only. Loss of this condition stops the attempt.

Before any new provider lifetime, the primary needs fresh positive native
evidence that the current exact fixture menu item can actually be invoked by
the supported indexed route. Merely seeing an index is insufficient: the
automation runbook records that native popup indexes have sometimes failed.
Source tests cannot supply this evidence. The primary must separately prepare
and review a bounded no-cloud rehearsal with a valid marker lifecycle and
unambiguous fixture-entry evidence. The existing fixture writes a failed,
zero-POST/zero-GET status when invoked without target.json, but a missing-target
rehearsal is only a proposal: absent target/used/stop markers, fresh isolated
evidence, owned local cleanup, no in-flight attempt, and the final action scope
must first be established. Never reuse the spent actual161 markers to do it.
No native action or marker write is authorized by this document.

The parser counts every occurrence of the exact command text across the whole
tree. Each must belong to a supported indexed menu-item row. A single row may
omit its ID annotation or use the exact suffix ` ID: <positive safe integer>`.
Repeated references are supported only when every command-bearing row is
byte-identical, including indentation, index notation, role, full label and the
same required positive ID annotation. Line endings delimit rows; CRLF and LF
are supported. ID-less repetitions, changed IDs, different indices, equivalent
but differently quoted labels, disabled/unknown annotations, unsupported target
contexts and distinct rows reusing the target index refuse, including malformed
bracket/whitespace notation or leading-zero aliases. This broader collision
recognition only refuses rows; it cannot establish a command target. The ID corroborates
the repeated representation; the inspected index remains the click argument.

The controller retains and checks the original whole observation; it never
deduplicates or rewrites its tree. Sky documents formatted tree text without a
universal line grammar. A changed format requires a reviewed source adaptation.
An exact line lacking a disabled annotation is
not independent proof of enabled/actionable state; inspect the real menu and
obtain the positive rehearsal evidence. There is no coordinate fallback,
offset compensation, guessed index, keyboard fallback, or retry after input.

JavaScript remains necessary for this module because the supported Computer Use
Node REPL owns the returned Window/observation objects and indexed input. Moving
this parser to Python would require crossing that live object boundary. Python
continues to own the external request, deadline and cleanup orchestration.

## New packet integration, after independent source review

Bind the complete candidate source/tests, this proposal, final runtime cells,
and final exact packet by SHA2-256. Preserve the Python request/owner/prewarm,
claim/source binding, stop, deadline, cleanup and no-replay policy. Any material
source/contract change remains proposed until the applicable owner acceptance;
neither a source-test pass nor an independent review accepts a new contract.
Use fresh run identity, markers and grants; retain spent attempts as evidence.

The new D cell must import the final reviewed, manifested candidate location.
Do not silently substitute the existing API module or edit frozen161 cells.
The candidate keeps `createNativeDispatchController` and `prewarm`/`stop`;
its action now accepts exactly `observation`, `elementIndex`, `commandLabel`.

After the correlated request becomes visible and validates, replacement F is:

```js
if (!globalThis.requestVisible) throw new Error('request_not_visible');
globalThis.observation = await controller.observe(lrWindow);
globalThis.lrWindow = observation.window;
nodeRepl.write(String(observation.accessibility?.tree || ''));
nodeRepl.write('Inspect the fresh exact menu command, enabled state, index and screenshot. Stop here.');
```

Both screenshot and accessibility text are required for this particular
decision: visual inspection corroborates the intended enabled menu command,
and the exact name/role/index drives the action. Keep the tree private in the
native session; do not persist catalog text or screenshot payloads. The
controller permits one observation only and includes capture time in the same
30-second observation/request bounds. It freezes every identity/action/count/
deadline field of the original invocation before capture, then requires the
same fields after capture, before intent, and after the dispatch checkpoint.
A replacement invocation cannot extend, shorten, or replace that observed
authority. The original deadline applies throughout. No extra refresh, navigation or capture
is allowed after F. Rejection or expiry exits to the existing stop/cleanup
procedure and does not authorize a new observation/controller/attempt.

After inspecting F, replacement G is a distinct cell:

```js
{
  const elementIndex = NaN; // Replace only with the exact index inspected in F.
  globalThis.dispatchResult = await controller.dispatchObserved({
    observation, elementIndex,
    commandLabel: 'Characterize synthetic POST v1',
  });
  globalThis.lrWindow = dispatchResult.state.window;
  nodeRepl.write(JSON.stringify({ outcome: dispatchResult.outcome,
    actualInputCount: dispatchResult.actualInputCount }));
}
```

This cell cannot accept coordinates. The index must match the single element
established by the exact MenuItem row or supported identical references in the
controller's unchanged capture. Durable attempted intent
still precedes the owner dispatch checkpoint and one supported click; immediate
refresh still precedes the acknowledgement. Input/refresh/ack uncertainty
remains terminal, with zero/one/unknown counts recorded honestly and no replay.
An input acknowledgement still does not establish fixture entry, target
consumption, case output, receiver rows, cleanup, or production qualification.

Keep the existing cancellation, owned cleanup, terminal-state checks and final
supported Node-kernel handback. An intentional Escape ends native input for
that turn. Do not initialize native control for source preparation or review.


## Closed dispatch failure diagnostics (#0224, source-only)

After a rejected `dispatchObserved` call, the primary may read
`controller.getFailureDiagnostic()`. It returns `null` when no dispatch failure
has been recorded, or a frozen memory-only object with exactly `stage` and
`failureClass`. The existing generic thrown errors and strict receipt schemas
are unchanged. This accessor performs no input, observation, file access or retry.

| Stage | Failure class |
| --- | --- |
| `request_guard`, `attempted_publication`, `dispatch_checkpoint`, `final_guard` | `local_guard_or_coordination_failure` |
| `click_pending` | `click_call_did_not_return` |
| `post_click_window_check` | `post_click_window_check_failed` |
| `refresh_pending` | `refresh_call_did_not_return` |
| `ack_publication` | `ack_publication_failed` |

Only fixed labels may enter a sanitized evidence handoff. An unavailable label
must remain unavailable (`null`); an unrecognized internal stage is classified
`unclassified`. No error property, message, stack, cause, arbitrary code, UI text,
screenshot, title, path or credential is copied into diagnostics. The stage is
frozen before cleanup; failed stop/ack cleanup and subsequent replay refusals
cannot overwrite an attempted failure. A pre-attempt refusal does not hide a
later attempted failure. Prewarm/observation/readiness errors outside dispatch's
caught region have no diagnostic from this accessor.

These labels identify the boundary that failed to return normally, not the API's
cause or delivered input count. `click_pending` still means unknown delivery and
`actualInputCount=null`; one is recorded only after normal click return. Window,
refresh and acknowledgement failures after that return retain one and unknown
outcome. Use the existing receipts to establish counts, stop state and ownership.
Do not treat a stage or normal click return as fixture-entry proof. No probe,
new route, replay, fallback or old-attempt reuse is authorized by this source work.

Offline verification uses pinned Node 24.22.0:
`node --test tests/group_post_native_dispatch.test.mjs`. Injected click, window,
refresh, ack, checkpoint and cleanup failures cover closed labels, frozen original
stage, hostile secret-shaped thrown values, count uncertainty and no replay.
These synthetic checks establish no native qualification.
