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

Choose a fixture, try the controls, and cancel to discard. **Apply search**
reopens the same native modal filtered by literal name/ID text, preserving
checkboxes and showing their total, including hidden rows. Clear the search to
recover all rows. This deliberate native-control prototype has no live-search
or custom list-widget dependency; owner review should assess the extra search
action and full-list scrolling cost with 376 groups. Confirmation displays a
summary and discards it. Reopening starts clean. The confirmation labels match
the proposed production verbs, but the window and result explicitly identify
the fixture boundary.

See `docs/design/photo-group-selection-preview.md` for storyboard and gates.
Run `uv run --frozen python <path-to-tests/test_selection_preview.py>` from the
implementation repository. The test uses its pinned `lupa` dependency; there is
no new runtime dependency in the plug-in.
