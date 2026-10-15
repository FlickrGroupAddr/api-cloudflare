# FGA-LrC15 Selection Preview

Copyright 2026 Terry Ott. MIT License; see the repository LICENSE.

Ticket #0027 review artifact. Fixture-only native SDK modal; no production
implementation or qualification claim. The preview imports only documented
SDK UI/task/path modules. It never reads credentials, contacts a service,
reads/writes the catalog, registers a publish provider, or submits groups.

In Lightroom Classic 15.6, use **File > Plug-in Manager > Add** and select this
exact `FGA-LrC15-SelectionPreview.lrplugin` folder. Then use **Library > Plug-in
Extras > FGA: Preview group selection (fixtures only)…**. A selected catalog
photo is unnecessary because every photo/Album context is synthetic. The
production command must validate exactly one selected photo in one ordinary
FGA Album before opening; the preview does not bypass production validation.

Keep this bundle separate from `FGA-LrC15.lrplugin`. Its toolkit identifier ends
in `.selectionpreview`. Do not overwrite or silently install it into the
production bundle path. No automatic installer is provided. Remove/disable
this entry through Plug-in Manager after review.

Choose a fixture, try the controls, and cancel to discard. Build **0.0.1.9**
shows available groups on the left and selected additions on the right.
Search above the left list filters literal name/ID text on every edit,
including deletion, without reopening the modal. The right list always shows
every selected addition. Highlight one row and use the center **Add →** or
**← Remove** button to move its exact ID. Highlighting alone makes no change;
this avoids treating native highlight changes during list updates as new
addition requests. Both lists stay sorted by display name. Rows show the name
first and the exact Flickr group NSID in brackets at the end.

Build 0.0.1.9 keeps a bold **FILTERED** message and the available-match/eligible count
directly below the query whenever it contains any characters, including spaces.
The query field shows the active literal query; the status tooltip repeats its
full text. **Clear filter**, directly beside the query field, restores all
available rows immediately in the same
dialog. With an empty query, the status says **All available** and Clear filter
is disabled. Counts explicitly distinguish available matches from all eligible
groups, including selected additions in the eligible total.
Loading or unavailable projections instead show their data state and mark counts
unknown in the tooltip; a missing projection never appears as a complete empty
list. The status reserves a 36-pixel wrapped area for two regular native text
lines. Font scaling and actual clipping still require host review.
Filtering and clearing preserve the selected set and confirmation title.

Each side now owns its heading and list in one column, so their edges follow
the same container instead of independently sized rows. Both columns have the
native list's 450-pixel minimum and equal `fill_horizontal` growth; the filter
row, including Clear filter, fills the left side, and the selected heading is
centered over its list.
Documented `LrView.share` header heights align both lists and the compact
90-pixel Add/Remove column. The buttons retain `place_vertical = 0.5` inside
the 220-pixel list region. Numeric widths remain only on fixed controls.
This replaces build 8's separate header/list rows: equal fill fractions did
not compensate for their different intrinsic minimum widths. No dynamic width
binding, custom drawing, or unsupported control styling is used. The documented
system bold font and explicit wording make filter state independent of color.

Highlight a row to read its full name and exact NSID in the wrapped detail
below the lists. Hovering either list also shows that highlighted group's
detail using the documented view tooltip. This is a whole-list tooltip for
the highlighted row; moving the mouse over a different row does not select it
or promise a different tooltip. The SDK documents neither per-row hover callbacks
nor a guaranteed horizontal scrollbar. Duplicate names and a deliberately long
name remain synthetic fixtures for checking identity and clipping after reload.

Clearing the query restores available rows. A group returned from the right
appears on the left only if it matches the current query. The selected list
alone determines the choice; there are no mode radio buttons. For an unpublished
fixture, an empty selected list saves explicit `none`, clearing earlier choices
for that photo/Album. Adding one row saves `groups`; removing the last row
restores `none` and leaves **Save for publish** enabled. Bound and existing
photos need 1–60 additions; zero and 61 disable queue confirmation. Confirmation displays a transient
summary and discards it. Reopening starts clean.

Terry approved the two-list interaction on 2026-10-15 after confirming that
build 0.0.1.5's live search and Add/Remove controls were intuitive and responsive
in Lightroom Classic 15.6. Build 0.0.1.6 refines the copy and layout: one short
preview notice, clear photo/Album context, and no internal scope, debug refresh
instruction, or general timestamp header. Unpublished fixtures omit the empty
membership panel because they perform no membership read. Bound and existing
fixtures retain the read-only membership and protected submission records,
including exact IDs, observation details, and permanent protection explanations.
The equal-width move buttons sit between the two list boxes, centered vertically
within their shared row; the search and headings occupy a separate row. This
uses the SDK's numeric width, horizontal fill, and `place_vertical = 0.5`
layout properties; native alignment still needs review after reload.

Build 0.0.1.7 removes the separate mode controls with Terry’s approval on
2026-10-15. Its confirmation button also shows the current selected count:
**Save for publish: no groups**, **Save for publish: 1 group**, or the plural
count for an unpublished photo; **Queue for 1 group** or the plural count for
a bound/existing photo. The title updates after Add/Remove while query edits
and highlights preserve it. Zero remains disabled for bound/existing photos;
61 remains disabled for every fixture. Saving prepares choices for the ordinary
Publish action; this preview never publishes or queues anything. The initial
`actionVerb` supplies a truthful fallback, while the documented bindable
push-button title attribute in `actionBinding` tracks the live property.

This revised build still needs native presentation review; the prior owner
acceptance does not establish its sizing, focus, keyboard accessibility, or
long-label clipping. The local Lua 5.1 tests simulate documented SDK 15.3
`simple_list` item/value arrays, button actions, and per-edit validation with
`immediate = true`. This fixture remains separate from production eligibility,
catalog validation, and submission behavior.

See `docs/design/photo-group-selection-preview.md` for storyboard and gates.
Run `uv run --frozen python <path-to-tests/test_selection_preview.py>` from the
implementation repository. The test uses its pinned `lupa` dependency; there is
no new runtime dependency in the plug-in.
