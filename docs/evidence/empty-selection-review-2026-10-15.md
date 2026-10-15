# Selected-set authority independent review, 2026-10-15

Reviewed staged #0027 revision under `batch7/ui`. No source findings remain.
The selected exact-ID set now solely determines additions. `M.choice(s)` derives
`none`/`groups`; the model has no mutable mode API or fixture choice field, and
the UI has no radio controls, choice binding, or choice observer.

`SelectionModel.lua:90`, `:102`, and `:120` consistently derive choice and
confirmation from the selected set. An unpublished photo with zero additions
can Save, including after removing every prior addition. Bound/existing photos
with zero additions cannot Queue. Counts 1–60 pass and 61 fails. Unknown or
protected selected IDs and incomplete/contradictory projections still fail
confirmation and result production. A legacy injected `s.choice` field has no
authority over selection, result choice, or confirmation.

`Preview.lua:70` and `:74` retain model-owned confirmation, explicit moves,
current-side exact-ID validation, and the pending-query refresh guard. Native
highlight changes never move rows. Search affects the available list and keeps
all selected rows available for explicit removal.

Verification: `test_empty_selection_review.py` passed independent model checks
and 14 synchronous/deferred UI scenarios through `uv run --frozen python` in
the implementation repository environment. Ruff passed. Cases include stale
legacy choice writes, last-item removal to zero, removal of all 60 selections
while available search matches nothing, rapid query replacement and a button
action before query notification, duplicate labels with distinct exact IDs,
protected/unknown input, no automatic highlight movement, and 0/1/60/61 bounds.

The approved dynamic action-label extension also passed the same 14 scenarios.
Every Add/Remove count check validates exact wording and singular/plural forms,
including last removal to `Save for publish: no groups`, and disabled bound zero
as `Queue for 0 groups`. Query/highlight changes leave the count-specific title
unchanged. The initial `actionVerb` exactly matches the initial bound title, and
the title/enabled bindings reference the same property table. SDK 15.3
`LrDialogs.html:532` documents `actionBinding` and references push-button bindable
attributes; `LrView.html:818` documents the push-button `title` attribute. This
supports the source design; actual native title redraw remains a host check.

Reviewed SHA2-256 digests:

- `SelectionModel.lua`: `5164DD29FAC274F0B1EAA5D8A90450F70FA2AC139E73367D96C6C58056B9AD75`
- `Preview.lua`: `133EA9DCBA5C7E80684A1A1EC08438CFD956210977E81C6D616E1CA426F12182`

These are offline model/control-event checks. They do not qualify the actual
Lightroom Classic host. Revised native layout, immediate edit binding, keyboard
focus/navigation, button actions, and empty Save/Queue affordances still require
the parent's bounded actual-host checks and owner review.
