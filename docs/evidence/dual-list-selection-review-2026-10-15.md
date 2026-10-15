# Selection-search independent review, 2026-10-15

Scope: #0027 staged prototype in `batch5/search`; source and event-model review
only. No native Lightroom Classic host qualification was performed by this agent.

The licensed Lightroom Classic SDK 15.3 reference supports bound `simple_list`
items and array-of-exact-ID values (`API Reference/modules/LrView.html`, lines
924–933), per-edit validation (`LrView edit view properties.html`, 430–432), and
property observers with the changed value (`LrObservableTable.html`, 345–360).
`visible=false` explicitly retains layout (`LrView view properties.html`,
368–370), so hiding hundreds of checkboxes is not a compact filtered list.

Two native lists with the available list filtered on each edit and all selected
additions retained on the right use documented controls without a custom list
framework. Exact IDs, rather than row positions or duplicate display labels,
own identity. Explicit Add/Remove buttons prevent highlights caused by keyboard
navigation or possible native item replacement from silently moving rows.
An injected adjacent-highlight event demonstrated the ambiguity of automatic
movement; this was a hypothetical event-model probe, not evidence that the
Lightroom Classic host actually produces that behavior.

Independent checks are in `test_dual_list_review.py`. They cover synchronous
and deferred notification delivery, rapid query replacement, duplicate-name
exact identities, both move directions, persistent right-side selections under
no-match search, highlight-only no-op behavior, repeated highlight changes,
new-photo None/zero and groups/zero behavior, bound/existing 0/1 behavior,
59/60/61 bounds, protected rows, and unavailable/contradictory projections.

Review found a stale Add race: if a query property changes before its observer
runs, the prior available-items array can still contain the highlighted ID.
Add must reject a pending query refresh (or validate against the latest query).
The regression is at `test_dual_list_review.py:131`.

The corrected candidate also reconciles a pending None/radio change before a
button action, clearing old selections and returning without moving a row.
This prevents a pending None from retaining older selected additions.

Final verification: all 14 synchronous/deferred scenario runs passed against
staged `Preview.lua`, SHA2-256
`5C8E39361C0D42DEBF70A0D11C5693F8F53743AC3E9A07603D3801A5A4BF855E`.
Run through the implementation repository's `uv run --frozen python` environment,
passing the staged bundle directory and canonical `SelectionModel.lua` path.
Native follow-up still needs list layout, focus/keyboard behavior, immediate
edit binding, redraw, arrow actions, and long-ID/name visibility checks.
