# Build 8 independent selection-width review

2026-10-15; fixture-only #0027 candidate in `batch8/ui`. No native host
qualification, repository/board mutation, or production admission performed.

No blocking source or event-model issue found. Eligible row titles put the full
name before the bracketed exact group NSID; `row.value` remains the exact ID.
Duplicate labels keep distinct values and detail strings. The new highlight
observers update display detail only. A wrapped detail and bound whole-list
tooltip expose the full long title/NSID without relying on undocumented per-row
hover or horizontal scrolling. Explicit buttons still own movement.

Both list nodes omit explicit width and have equal `fill_horizontal=.5`, equal
height and a shared full-width row. The root and ancestor row omit width and
fill horizontally. Header sides have equal text minima/fill, and the left search
fills its parent. The center column/buttons remain 90 pixels wide, with
`place_vertical=.5` on the column against the list-only row. The separate
740-pixel read-only scroller is a sibling, not an ancestor constraining the lists.

Local licensed SDK 15.3 primary references, under architecture-design's
`vendor/LrC SDK/15.3/API Reference/modules/`:

- `LrView node layout properties.html:316`: proportional fill and explicit
  minimum-width exclusion from automatic resizing; `:370` horizontal fill and
  `:410` vertical placement.
- `LrView.html:933`: native simple-list default width 450, item title/value,
  array-valued highlight selection.
- `LrView text properties.html:350`: wrapping with `height_in_lines=-1` and
  a text-width hint; `:360` character-based minimum.
- `LrView view properties.html:358`: whole-view tooltip.

The documented simple-list default width and real SDK layout arithmetic are not
emulated. Native host acceptance must observe initial equal list widths, growth
on modal resize, left-search alignment, centered fixed controls, wrapping/focus
and long-name/NSID access before making a native-layout success claim.

`test_width_review.py` adapts the preceding independent selected-set review and
adds structural ancestor/fill checks, full names/IDs, duplicate discrimination,
long-title detail and highlight-only no-op checks. All 14 synchronous/deferred
scenarios passed against staged Preview.lua and SelectionModel.lua using the
canonical repository's already provisioned `.venv/Scripts/python.exe` and Lupa.
The required `uv run --frozen` launcher encountered sandbox cache-write retries;
the primary owns required full verification. Scenarios also retain zero-save,
bound/existing zero rejection, 1/59/60/61 bounds, both move directions, stale
search race rejection, hidden selected rows, cancellation, protected rows and
incomplete/contradictory projection checks.

Reviewed candidate SHA2-256: Preview.lua
`B381379C21D5F48F40E8188DAD4C2BD3D464C333EF45E8ECE864B2B5168BABEB`;
SelectionModel.lua
`100587138918B4C882930B214A6216A7335EF8BB469FC350E86CC49653296F41`.
The model differs only in the long synthetic label and its explanatory comment;
selection/protection/result logic is unchanged.
