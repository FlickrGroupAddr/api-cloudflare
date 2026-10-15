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

Choose a fixture, try the controls, and cancel to discard. Build **0.0.1.5**
shows available groups on the left and selected additions on the right.
Search above the left list filters literal name/ID text on every edit,
including deletion, without reopening the modal. The right list always shows
every selected addition. Highlight one row and use the center **Add →** or
**← Remove** button to move its exact ID. Highlighting alone makes no change;
this avoids treating native highlight changes during list updates as new
addition requests. Both lists stay sorted by display name, with exact IDs
first so a long name cannot hide the identity at the end of the row.

Clearing the query restores available rows. A group returned from the right
appears on the left only if it matches the current query. **No group additions**
clears every selected addition for an unpublished fixture. A bound photo needs
1–60 additions; 61 disables confirmation. Confirmation displays a transient
summary and discards it. Reopening starts clean.

This is a source-backed SDK prototype, pending native review on Lightroom
Classic 15.6. SDK 15.3 documents bound `simple_list` item/value arrays,
single-selection lists, push-button actions, and per-edit validation with
`immediate = true`. The local Lua 5.1 tests simulate those contracts; they do
not establish native list rebinding, focus retention, keyboard behavior, label
clipping, scrolling, sizing, or typing latency with 376 rows. The SDK does not
establish safe automatic one-click movement when replacing a list's items;
this build uses explicit move buttons as Terry accepted on 2026-10-15.

See `docs/design/photo-group-selection-preview.md` for storyboard and gates.
Run `uv run --frozen python <path-to-tests/test_selection_preview.py>` from the
implementation repository. The test uses its pinned `lupa` dependency; there is
no new runtime dependency in the plug-in.
