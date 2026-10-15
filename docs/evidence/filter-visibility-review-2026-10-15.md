# Build 9 independent filter and layout review

2026-10-15. Fixture-only #0027 candidate in `batch9/ui`; canonical model
from `C:/Projects/FGA/api-cloudflare`. No repository/board changes or native UI
qualification performed by this review.

No remaining blocking source/event-model finding. The initial candidate had a
deferred-event race: highlight A, type a nonmatching query without delivering its
observer, Clear, then Add. Because Clear restored the old snapshot query, the
idempotent query handler skipped refreshing and retained A's highlight. Clear
now unconditionally refreshes the lists after assigning the empty query, so the
stale highlight is discarded before Add. The independent harness exercises this
sequence with synchronous and deferred observers.

The adjacent bold status uses supported `font = "<system/bold>"`, with explicit
FILTERED text and exact match counts. Any nonempty query, including a single
space, activates the status and Clear. Matching is case-insensitive literal
substring matching, including punctuation; no trimming or Lua-pattern semantics
are introduced. The visible field holds the query, with its full quoted text
repeated in the status tooltip. FILTERED plus a zero numerator identifies the
filter state; Clear restores rows without changing selected IDs or confirmation
title. Per the primary's clarified copy decision, the denominator is explicitly
labelled eligible groups and includes selected additions; the available numerator
excludes selected additions. The separate selected counter is unchanged.

The final candidate suppresses numeric completeness claims for invalid
projections: unfiltered status says Loading group data or Group data unavailable;
active status prefixes FILTERED and the tooltip says counts are unknown. Clear
preserves that availability state. The 18-scenario rerun now checks each invalid
projection with a space query and Clear in both event modes.

The status has documented `height_in_lines = -1` wrapping with a 36-pixel minimum
height. Positive two-line height alone does not enable documented wrapping.
These properties provide a stable reserved region in the candidate but cannot
prove clipping behavior at a host's actual font scale; that remains a native gate.

Header, query row, status and list now share one side column. Clear filter
shares the query field's immediate row, placing the action beside its field;
the single query field fills the row space remaining beside the fixed button.
Both side columns use fill .5, both lists fill their side column, and neither
side/list has a numeric width. Shared header heights align the list origins and
center-column spacer. A fixed 220-pixel list region contains the vertically
centered move controls, within a fixed 90-pixel center column. Root/row fill
propagation is present. The bound-only read-only scroller is a sibling and does
not constrain the list row.

SDK 15.3 primary references under architecture-design's
`vendor/LrC SDK/15.3/API Reference/modules/`:

- `LrView control view properties.html:360`: canonical bold font.
- `LrView.html:499`: shared sizing uses the greatest shared value.
- `LrView node layout properties.html:316`: fill/minimum sizing and numeric
  explicit-width exclusion from resizing; `:370` fill; `:410` placement.
- `LrView.html:933`: simple-list native 450-pixel default, item/value arrays,
  and exclusion of the font property from simple lists.
- `LrView view properties.html:358`: whole-view tooltip.
- `LrView text properties.html:350`: wrapped text sizing.

`test_filter_review.py` passed 18 synchronous/deferred fixture scenarios using
the canonical provisioned Python/Lupa runtime. Coverage includes whitespace,
literal punctuation, Clear restoration and stale-Add rejection, truthful
filtered/unfiltered counts and labels, hidden selected rows, protected IDs,
new/bound/existing zero semantics, 1/59/60/61 bounds, dynamic confirmation titles,
cancel, incomplete/contradictory data, long-name detail and highlight-only no-op.
Structural assertions check same-side ancestors, equal fill, shared header
heights, fixed center controls, supported bold text, exactly one query field and
the Clear button sharing that field's immediate row. All 18 scenarios passed
again after this final placement refinement.

This verifies source structure and simulated documented events. It does not
establish native pixel widths, clipping, resize behavior, focus, keyboard access,
or whether Lightroom's rendered modal consumes the right-side gap observed in
build 8. Those require a build 9 native host observation before acceptance.

Reviewed Preview.lua SHA256:
`F084A6DC6F4D1FE13935C710E5C375DFCD0EDF85EF9D70538A2EE9B91244E969`.

Reproduce from the workspace with:

```powershell
& C:/Projects/FGA/api-cloudflare/.venv/Scripts/python.exe batch9/review/test_filter_review.py batch9/ui/clients/lightroom/prototypes/FGA-LrC15-SelectionPreview.lrplugin C:/Projects/FGA/api-cloudflare/clients/lightroom/prototypes/FGA-LrC15-SelectionPreview.lrplugin/SelectionModel.lua
```

Primary owns canonical adaptation and required repository verification.
