# Screenshot synthetic POST dispatch contract

Status: Accepted scoped route amendment, Terry, 2026-10-21. Source and packet
preparation only; native qualification and action gates remain pending.

This records the accepted #0218 proposal r01 decision for one fresh synthetic-only,
no-cloud rehearsal. The private acceptance record pins proposal r01 SHA2-256
`05237309e4892cc254482ecfd7ea648f88c54503094b2b2bd9a504e250f7cae5`.
It prospectively permits a screenshot-bound click on the exact visible enabled
`Characterize synthetic POST v1` command. It does not reopen prior attempts,
explain their unknown delivery, authorize a fallback, or establish native success.
The indexed controller and its historical contract remain unchanged.

## Source and supported API

`scripts/group_post_screenshot_dispatch.mjs` exports
`createScreenshotDispatchController`; it shares only the reviewed bounded Node
file adapter with `group_post_native_dispatch.mjs`. JavaScript is justified by the
installed Computer Use 26.1016.51333 supported `node_repl` / `@oai/sky` API. The
module neither imports/initializes Sky nor discovers or reconstructs windows.
The primary supplies the supported API and one actual returned target Window.
Tests inject synthetic objects and in-memory files; those are source tests,
never purported native observations or fixture-entry evidence.

The current API documents `click({window, screenshotId, x, y})` with
window-relative coordinates, Screenshot dimensions in logical pixels, origins in
screen coordinates, and z-order. Window exposes app/id/title, without a screen
origin. These fields do **not** document a transform from a popup screenshot to
window-relative coordinates or prove which screenshot is the window frame.

The implementation deliberately accepts only a selected returned screenshot that
the primary can visibly establish as the full target-window frame containing the
exact enabled command, with a point in its window-relative logical coordinates.
`windowFrame` and `screenshot` must be the very same returned object. A detached
popup selection refuses. Extra screenshots require direct visual comparison:
each must be an unambiguous contained duplicate crop already visible within the
selected full-window image. Bind every such exact returned object in array order
in `inspection.duplicateCrops`; no extra unknown, independent or ambiguous frame
is permitted. Each crop must also have strictly smaller logical extent, no larger
width/height, and higher z-order. These metadata guards reject contradictions;
they do not prove the visual relationship. Mixed screen origins/logical dimensions
cannot establish containment or disjointness. No subtraction of origins, scaling, popup offset, z-order guess, or generic
assertion can establish a missing mapping. If the current native API/observation
does not demonstrably provide the accepted full-window case, stop preparation or
execution; a reviewed source adaptation and any material owner decision precede
another run. This restriction is conservative implementation scope under the
accepted amendment, not a claim that native capture will satisfy it.

## Two-cell operation

After the one attached numeric owner/generation/run is established, prewarm checks
all eight native fixed paths absent, proves the exact exclusive Node writer, and
obtains the fresh owner prewarm checkpoint. It retains the original finite request
and owner cutoff. Request lifetime and observation age are at most 30 seconds;
checkpoint lifetime is at most 10 seconds and within owner/request deadlines.
Expired authority is never extended or republished.

1. In the final observation cell call `await controller.observe(targetWindow)`.
   Stop and inspect the automatically displayed screenshot directly. Do not save,
   decode, print or re-emit its payload. This is the only final observation for
   that run, including on capture failure. The returned Window must retain the selected app/id; RPC may return a distinct
   object. The exact final returned Window object is then pinned for input and
   every subsequent identity/field check.
2. In the separate reviewed action cell call `dispatchObserved` with exactly
   `observation`, `screenshot`, `windowFrame`, `commandLabel`, `x`, `y`, and
   `inspection`. Keep the literal command and inspected point in that cell.
   `inspection` contains exactly six true fields: `enabledCommand`,
   `pointInsideCommand`, `windowFrame`, `targetOwnership`, `mapping`, `soleControl`,
   plus `duplicateCrops`, an array of the exact extra Screenshot objects visually
   established as contained duplicate crops (empty for a single-frame state).
   These record the primary's direct inspection, not API semantic attestation.
   Unknown/disabled/adjacent commands, uncertain frame role, mapping or ownership,
   photo/catalog/modal surfaces, or another app stop before input.

No navigation, input, extra capture, focus/layout change, interleaved operator or
loss of sole ownership may intervene. File checkpoints may intervene. The primary
must stop the run if any condition is lost; it cannot create a second observation
under the same request. The controller can detect in-memory mutation, not attest
to external UI stability or prove the primary's visual judgment.

## Guards, intent and terminal behavior

The controller snapshots the original Window fields and identity, WindowState,
screenshot array, each Screenshot object and its id/geometry/url, and accessibility
reference/fields when present. Same objects and unchanged supported fields are
required before intent and immediately before input. Ids must be nonempty and
unique; geometry must be finite, positive where applicable, with finite extents.
The point must be finite and inside half-open logical frame bounds. Exact schema
checks exclude injected callbacks or alternate commands. Original action fields
are copied into a frozen in-memory click object before any await, so caller
mutation cannot redirect an input after capture/intent/checkpoint.

Before input, the session is latched and attempted intent is exclusively persisted
before the owner dispatch checkpoint. Stops, owner, original request, frame and
all deadlines are rechecked. No wait or file operation follows the final guard
before the one supported click. No index, keyboard, manual invocation or route
fallback is available. The closed diagnostics describe the failure boundary,
never a cause or an assertion of delivery.

`actualInputCount` becomes unknown (`null` in the acknowledgement) immediately
before awaiting click, then becomes one only on normal return. The controller
checks retained Window fields and immediately refreshes state, then exclusively
acknowledges. Click, refresh or acknowledgement failure is terminal and cannot
retry input. A failed click remains unknown; a normal click followed by refresh
failure records one returned input, with unknown overall outcome. An acknowledgement
or normal click never proves fixture entry or terminal success. A pre-input failed
final guard can honestly record zero. The global session latch prevents a new
controller instance from replaying an attempted run.

The generic skill recovery advice does not override this contract: a non-target
window error stops this run; no activate-and-retry. Escape withdrawal, expiry,
owner loss, terminal state, attempted intent and unknown delivery forbid retry.
A new run requires a fresh reviewed packet and cannot reuse spent authority.

## Remaining native gates

- Fresh independent source, runtime-cell, packet and actual-result reviews.
- Exact source/cell hashes, fresh run/generation, finite deadlines, one attached
  owner, isolated coordination root, and exact eight-path ownership/freshness and
  reparse checks. Preserve prior receipts and spent markers.
- Current host/build and SDK compatibility, exact loaded synthetic fixture/version,
  exactly one supported returned target Window, visible enabled command, and a
  demonstrably valid full-window frame/coordinate mapping. Source tests prove none.
- Independently reviewed fixture-entry oracle and exact terminal receipt. The
  missing-target candidate must prove the expected failed terminal result, fresh
  sole-writer correlation and zero POST/GET counts. Missing files do not prove
  zero input or success. If correlation is insufficient, stop before native action.
- Resolve intentional Escape withdrawal and every applicable action-time skill
  confirmation. Contract acceptance itself does not satisfy these gates.
- No provider, credential, Cloudflare, Flickr, real-photo or catalog API activity.
  Persist sanitized metadata only. Exact owned terminal disposal remains a
  separate decision; deletion through Windows UI requires action-time confirmation.
- Close or safely stop the exact owner, retain receipts, and release native input
  through supported shutdown/reset only after activity is safe. Never reset to
  bypass Escape. A positive reviewed #0218 result remains insufficient by itself
  for a fresh #0161 cloud packet.
