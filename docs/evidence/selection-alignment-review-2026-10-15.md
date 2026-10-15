# Build 10 independent review

2026-10-15. Scope: fixture-only #0027 candidate in `batch10/ui`, canonical
preview9 `SelectionModel.lua` under `C:/Projects/FGA/api-cloudflare`. No
repository, board, commit, or native UI operations performed.

No blocking source/event-model findings. This is not native pixel acceptance.
Preview9's equal-height header arrangement had not aligned actual rendered
lists. Build10 instead places both simple lists directly in the same list-only
row (Preview.lua:206). Both specify height220 and fill.5; the center column is
90x220 and centers its two90-wide buttons. Header height cannot independently
move one list down in this structure.

Header and footer rows use identical spacing12, center90 and side fill.5. Each
side metadata wrapper includes a zero-height450-wide spacer (Preview.lua:172),
matching the documented default list width. Lists and growing side wrappers
have no numeric width. The match counter remains above the left list per the
primary's clarified placement; the selected counter sits below the right list
(Preview.lua:227). The heading carries FILTERED whenever any query characters
exist, including whitespace. Clear is the query field's immediate row sibling.
Count text is exactly `n matches / t total`; unavailable/loading projections
replace numeric counts with their availability state, while heading FILTERED
and the tooltip's unknown-count explanation remain truthful (Preview.lua:80).

Documented SDK15.3 references, under architecture-design's
`vendor/LrC SDK/15.3/API Reference/modules/`:

- `LrView node layout properties.html:316`: fill respects child minima; numeric
  width/height excludes automatic resizing in that direction. This supports
  fixed spacer minima without fixing growing list/side widths.
- `LrView.html:499`: share selects the greatest shared value. No shared-header
  height is relied on in this candidate.
- `LrView.html:933`: simple_list default width450, minimum height80, array-based
  value/items and no font property.
- `LrView node layout properties.html:410`: placement of remaining space.
- `LrView control view properties.html:360`: documented bold font.

Independent `test_alignment_review.py` passed18 fixture/event combinations:
nine fixtures with synchronous and deferred observers. Assertions cover the
direct sibling layout, equal220 heights, metadata minima/fill/spacing, center
controls, counter placement, heading cue, adjacent Clear, literal whitespace
and punctuation queries, exact IDs and duplicate labels, long-label detail,
highlight-only no-op, stale Add after a deferred query, Clear before deferred
events, hidden selections, protected/unknown IDs, zero/one/60/61 boundaries,
dynamic confirmation and selected counts, cancellation, incomplete data,
fixture reopening isolation, and detached result IDs. SDK import stubs reject
any unexpected host import. Source remains a fixture modal without network,
catalog, credential, or persistence operations.

Run using canonical frozen environment, with an accessible writable uv cache:

```powershell
$env:UV_CACHE_DIR = 'C:/Users/TDO-XPS15-2024/Documents/ChatGPT/FGA/.tmp/uv-review-cache'
uv run --frozen python C:/Users/TDO-XPS15-2024/Documents/ChatGPT/FGA/batch10/review/test_alignment_review.py C:/Users/TDO-XPS15-2024/Documents/ChatGPT/FGA/batch10/ui/clients/lightroom/prototypes/FGA-LrC15-SelectionPreview.lrplugin C:/Projects/FGA/api-cloudflare/clients/lightroom/prototypes/FGA-LrC15-SelectionPreview.lrplugin/SelectionModel.lua
```

Working directory: `C:/Projects/FGA/api-cloudflare`. uv reported inability to
acquire the read-only environment lock but completed using the frozen environment.
The first two cache locations were inaccessible; the workspace cache run passed.

Actual host top/bottom/width measurements, resize behavior, clipping, keyboard
access and focus remain native qualification gates. Identical source minima
and fill do not prove rendered pixel edges. Review hash for Preview.lua:
`989AFC8F23D0A43F45D911BEB69ACF30D31BF74E8AFFE7C4809757E9176F3584`.

Primary owns canonical harness adaptation, integration and required verification.
