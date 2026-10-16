# FGA-LrC15 development handoff, 2026-10-16

This is the current resume point. Earlier dated handoffs retain historical
evidence and do not describe today's remaining gates. The Lightroom Classic
15 client stays major-specific: host 15.6, build `202609251514-f839cde9`, Adobe
SDK 15.3; no support claim for a later Lightroom Classic major.

## Completed engineering milestones

- Toolchain and dependency work is pushed and #0035 is Ready for Review.
  CI and the qualified portable runtime use Node 24.22.0/npm 12.2.0; the
  machine-wide Node remains 24.20.0. TypeScript stays stable 7.0.2; 7.1.0 is
  not stable in the recorded 2026-10-16 registry checks. See [the dated toolchain inventory](../research/node-toolchain-inventory-2026-10-16.md). Dependency overrides passed the locked install, runtime tests and
  zero-vulnerability audit; prerelease Miniflare is not introduced.
- #0023's separate native synthetic fixture **0.0.1.5** passed all ten
  UI/client/cache scenarios against release modules **0.2.0.6**. The primary
  observed decoding, long identity, navigation, cancellation, complete-page
  behavior, stale proof/errors and cache cleanup. The [retained native record](../evidence/existing-photo-native-synthetic-2026-10-16.json)
  contains distinct terminal receipts and exact tested source SHA2-256 values.
  Earlier failed initialization receipts are retained separately.
- #0023's [disposable hosted matrix](../evidence/existing-photo-hosted-qualification-2026-10-16.md)
  passed all 22 cases in [CI 38929606706](https://github.com/FlickrGroupAddr/api-cloudflare/actions/runs/38929606706),
  source `1fb7ca8`, compatibility date 2026-10-16, with `nodejs_compat` and
  `enable_request_signal`. Its fresh Worker and D1 were both deleted. No
  real Flickr upstream was contacted. Earlier failed attempts remain failures;
  no cause is invented for the unexplained responses and no checks were relaxed.
- #0024's disabled source composition is pushed in `2b322b2` after independent
  High review. The actual browser/proof/membership, group/history, eligibility,
  accepted dialog/controller and binding-only outbox are composed with the
  existing batch client through explicit adapters. Installation/link/catalog/
  credential/cancellation fences and unresolved handoff reconciliation are
  preserved. See [the workflow review](../evidence/existing-photo-group-workflow-review-2026-10-16.md)
  and [controller design](../design/group-selection-controller.md).
- #0025's owner-selected exact pair is privately retained; do not request it
  again. The [readiness inventory](controlled-trial-readiness-2026-10-16.md)
  enumerates unfilled final-candidate, baseline, queue-census, qualification,
  stop/recovery and activation evidence. Pair selection is not activation.

The final integrated offline suite passed **360 Python/actual Lua tests** on
the qualified Node 24.22.0 path. The combined runtime suite passed **218 tests**
after dependency overrides; pinned native TypeScript 7 and generated API checks
passed. Changed Lua sources compiled with Adobe SDK 15.3; affected Ruff and
Pyright checks passed. Detailed local test output remains ignored; exact
native and cloud evidence is retained in the linked tracked records.

Build **0.2.0.7** subsequently packages the exact canonical batch client inside
the release bundle and uses it in workflow integration tests. One byte-equality
check guards drift. Its 31 targeted tests, Adobe compilation and static checks
passed. It remains unqualified as a complete native bundle; the ten retained
native receipts remain build **0.2.0.6**, not build 7.

## Remaining engineering and permission boundary

The next #0023 work is actual native HTTP characterization, followed by the
fixed trusted FGA endpoint/edge qualification. Read [the next-step scope](existing-photo-native-network-next-step-2026-10-16.md).
The native UI fixture injects responses; the disposable cloud runner uses Python
HTTP. Their passes cannot establish actual LrHttp allocation, redirects or
Authorization forwarding, active network cancellation, production edge policy,
or full JPEG decoding. Finite measurements must not be relabeled as universal
preallocation or total elapsed-time guarantees absent supported controls.

Prepare and independently review the separate finite network probe and its
two-Worker/one-D1 resource/cleanup packet before loading or deploying it. The
primary keeps desktop input exclusive during approved runs and must observe
after each action. A newly installed/loadable fixture needs the computer-use
skill's action-time owner confirmation for its concrete scope. Reuse existing
disposable authorization only where it actually covers the new resources and
requests; production-domain changes are a separate boundary.

#0024 still needs the real host transport/storage adapter qualification,
integrated native batch/status/reconciliation behavior and reviewed release
registration. Source/mock integration is not that native result. #0025 retains
those prerequisites plus final exact-artifact hosted qualification and a later
explicit one-pair live activation decision. Do not mark these full milestones
complete because their source and synthetic portions pass.

Production existing-photo/thumbnail/intake/dispatch capabilities remain disabled;
both durable write gates remain paused. No production deployment, migration,
real photo write or group addition is authorized by these results.

## Resume without repeating settled work

Reuse the healthy loopback [implementation board](http://127.0.0.1:8795/) and
its actor-filtered JSON monitor. Inspect/mutate through localswim-cli; never edit
board JSON. Bot-only writes must not trigger redundant next-turn inspection.
Keep #0027's accepted dual-list/live-filter/multi-select UX and #0029's completed
outbox proof closed. Do not ask Terry to repeat those approvals or tests.
The primary left Lightroom Classic running with no fixture dialog open after
the ten-scenario matrix. Refresh returned app/window state before any new input;
do not launch another instance or reuse stale handles.

## Next concrete action: owner load/run decision

The reviewed finite network packet is pushed in **86fbc7d**. Its separate
native plug-in is **0.0.1.2**, not the already executed synthetic UI fixture.
Read [the finite server/lifecycle plan](../../probes/existing-photo-native-network/README.md),
[the native fixture guide](existing-photo-native-network-fixture-2026-10-16.md)
and [the independent review](../evidence/existing-photo-native-network-review-2026-10-16.md).

The proposed run creates exactly two disposable workers.dev Workers, one fresh
synthetic D1 and two temporary Actions secrets containing only synthetic gate/
canary values. It reuses the existing Cloudflare CI credential unchanged; the
old local CI-token file is absent and no replacement is needed. The resource
expiry is twenty minutes, with at most 32 admitted requests per role, 262145
bytes per response and one 16-second delay. The CI runner has explicit cleanup
margin beyond expiry, exact identity journaling, single-attempt mutations and
sanitized readiness/cleanup artifacts. No resources or temporary secrets have
been created and no workflow has been dispatched for this packet.

Before provisioning/loading/invoking, obtain the concrete Windows action-time
approval. Generate expiry only after approval. The primary owns desktop input,
private target assembly, the native terminal observation, exact remote cleanup
confirmation and removal of only the two newly created temporary secrets. Do
not overwrite existing secret names or infer native completion from CI counters.
No real Plugin Code, Flickr credential, photo, catalog write or production route
is involved. This experiment records finite native HTTP behavior and keeps all
production, native allocation and total-deadline qualification claims false.
Fixed production-origin/edge review and the downstream #0024/#0025 gates remain.

Final handoff verification: the complete frozen Python run passed 381 tests;
a subsequent affected-module run passed all fourteen final native network tests.
The final independent native/lifecycle check passed twenty-one tests; five
server tests and eighty-seven checks across six npm test scripts also passed.
The earlier 218-test production-runtime result remains tied to its unchanged
production sources after the dependency update. No new fixture or CI preparation
result is substituted for actual native execution or production acceptance.
