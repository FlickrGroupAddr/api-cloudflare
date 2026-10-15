# Selection preview adversarial review

Date: 2026-10-15. Scope: ticket #0027 fixture interaction only. Result: one
acceptance-fixture coverage defect demonstrated and its proposed fix independently
validated; no additional selection-logic defect demonstrated. Production
selection, persistence, API handoff and host acceptance remain separate gates.

Reviewed implementation sources:

- `clients/lightroom/prototypes/FGA-LrC15-SelectionPreview.lrplugin/Preview.lua`
  — SHA2-256 `C1568AF970B4EF200A550B080E442D42090585CC010F6C2E5B3500EDC9946F2A`.
- `clients/lightroom/prototypes/FGA-LrC15-SelectionPreview.lrplugin/SelectionModel.lua`
  — baseline SHA2-256 `4326F8C43365B264CC2655BA286007A246B91365777BA9879804CFEFF711E7AE`;
  reviewed amendment SHA2-256
  `BAF2909FB2DD1B5A05830C93522473707E96EADDDDB9C930E691561F8B4FABEB`.

Authority read for the review: implementation `AGENTS.md`, architecture
`AGENTS.md` and `docs/README.md`, accepted ADR0045, accepted
`docs/moderator-safety-ui-conformance.md`, and accepted
`docs/plugin-service-contract.md` section 3.5. The reviewer made no native UI
inputs, catalog accesses, credential reads, service requests, board writes or
source changes. The parent owns the actual Lightroom Classic 15.6 acceptance.

## Independent executable evidence

`tests/test_selection_preview_adversarial.py` loads the actual two Lua sources
in explicit `lupa.lua51.LuaRuntime`, asserts Lua version `(5, 1)`, and drives
the real observer callbacks through multiple consecutive modal reconstructions.
SDK views are simulated property tables and control trees. No copied model or
replacement selection algorithm decides the tested outcomes.

The seven new tests exercise sequences beyond the prior single-dialog observer
checks:

| Sequence | Verified result |
| --- | --- |
| Select one group, search a different exact ID, select that row, then clear search | Hidden first choice remains included; both checked rows reappear; fixture summary contains exactly two IDs. |
| Select one group, hide it with search, choose No group additions | Hidden and visible marks clear; unpublished explicit none confirms zero groups. |
| Select 60, search the 61st ID, check it, search an unmatched literal, then restore the full list | 61 disables confirmation even with no visible rows; the hidden count remains 61; unchecking the overflow restores 60; Cancel produces no summary. |
| Select while complete, then mark required projections unavailable before the next modal reconstruction | Every selectable checkbox disappears, confirmation disables, and even a synthetic `ok` return produces no result. |
| Bound fixture with membership plus permanent moderation protection | The full protection meaning, unknown moderator decision, and later-membership information remain visible together; none of the four current/retained/protected IDs has a checkbox. Bound one is valid; returning to zero disables confirmation. |
| Apply literal searches containing `.*`, `%`, `[`, `(` or an unmatched phrase, then cancel | Search does not interpret Lua patterns or throw; no matched rows become a fabricated empty snapshot; Cancel produces no summary. |
| Select two groups with the same display name, then search one exact ID | The amended fixture contains distinct identities and a label longer than 170 rendered characters; both selections remain counted while only one exact-ID match is visible. |

The seventh test fails the original model because it lacks duplicate-looking
names, matching the missing data for the documented native acceptance case.
The original fixture also lacks an intentionally long label. The selection
mockup author amended only synthetic group names: groups 374 and 375 share a
display name and group 376 has a long name. This is a concrete review-coverage
fix, not an unsafe handoff or production parser defect. Independent execution
against the unchanged `Preview.lua` and amended model passes all seven tests.

Every simulated dialog additionally enforces at most 376 rendered checkboxes.
This proves the existing fixture's bound, including reconstruction after search;
it does not establish production 10,000-row performance, host responsiveness or
native viewport layout. Hidden selections remain counted, so filtering cannot
turn an over-limit set into a valid one.

Validation: the first six tests passed the original sources in 0.994 seconds;
the new missing-fixture test failed the original model; all seven passed the
reviewed amendment in 1.020 seconds using the repository's pinned environment.
Ruff and Pyright passed. Adobe SDK 15.3's local Windows `luac.exe -p` also
passed the unchanged preview entrypoint and amended model. Execute
from the implementation repository with `uv run --frozen --no-sync python
tests/test_selection_preview_adversarial.py`. When running this staged file,
set `FGA_SOURCE_ROOT` to the implementation repository and use an explicitly
writable uv cache. For the independent amendment check,
`FGA_SELECTION_MODEL_OVERRIDE` points at the proposed staged `SelectionModel.lua`;
this variable is unnecessary after the parent integrates that model. No
dependency or toolchain change is required.

## Readiness boundary

The fixture source remains suitable for owner/native interaction review; this
result neither accepts that interaction for production nor qualifies a hosted
operation. The parent must record current Lightroom Classic 15.6 build
`202609251514-f839cde9` observations independently for search/reopen usability,
376-row responsiveness, keyboard focus after Apply search, resizing, long labels,
wrapped protection text, Escape/window close, and the visible zero/1/60/61 states.

Before production selection, the accepted architecture still requires complete
writable groups, a fresh complete membership observation and complete retained
history; exact photo/Album scope; reviewed persistent selection and outbox
semantics; fresh existing-photo proof before handoff; and whole-batch/status
validation. The synthetic `ready` flag and three representative retained states
are fixture inputs, not a production projection parser or proof of those gates.
No production activation follows from this review.
