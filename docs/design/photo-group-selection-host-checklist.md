# Group-selection preview: actual-host acceptance

Current recorded results: [actual-host selection evidence](../evidence/lrc15-selection-preview-host-2026-10-15.md). The Not run cells below preserve the original test-plan baseline; consult that evidence index for later partial observations and remaining checks.

Copyright 2026 Terry Ott. MIT License.

Ticket #0027; prepared 2026-10-15. The parent agent owns live UI operation and
records results. This checklist is an unexecuted host plan. A passed local
model or mock-host check does not fill any host-result cell below.

Use the explicitly separate `FGA-LrC15-SelectionPreview.lrplugin` entry, toolkit
ID `com.sixbuckssolutions.flickrgroupaddr.lrc15.selectionpreview`. The production
`FGA-LrC15.lrplugin` entry must remain distinct. Target: owner-confirmed
Lightroom Classic 15.6 / Camera Raw 18.7, build 202609251514-f839cde9, using the
owner-reconfirmed SDK 15.3 (April 2026) API boundary.

Enter each case through **Library > Plug-in Extras > FGA: Preview group
selection (fixtures only)…** and choose the stated fixture. No actual catalog
photo/source is required. Every selected photo, Album and ID is synthetic.
Never invoke the production publish service while following this checklist.
Confirmation in this preview must display a transient summary only.

## Mechanical checks to execute on the actual host

Record result as pass/fail/not run, observed elapsed time where relevant, host
build, display resolution/scaling and date. Keep screenshots/catalog details
out of tracked evidence. A concise sanitized observation is sufficient.

| ID | Steps | Exact expected result | Host result |
| --- | --- | --- | --- |
| H01 | Open launcher; cancel it. Reopen and choose Unpublished. | Launcher cancel opens no selector or result. New fixture shows Harbor at dawn / DSC_0042.NEF, Coastal light, service 12 / Album 34, “Not yet published by this FGA collection.” Both radio choices are visible; Save for publish is enabled with none selected. | Not run |
| H02 | Inspect initial size; resize smaller/larger; Tab through top, readonly area, radios, query, checkboxes and buttons. | Title, photo/Album context, count and confirmation/cancel controls remain readable/reachable. Scrollbars reveal all content. No clipped or overlapping safety text. Record smallest usable size and whether resizing expands usable viewport or only margins. | Not run |
| H03 | New: choose Add to selected groups with no boxes. Check first box using Space; uncheck. Switch to No group additions after checking several. | Groups mode at 0 disables Save; one check selects groups mode, shows 1/60, enables Save. Uncheck leaves groups mode at 0 disabled. None clears all marks and enables Save at 0. Keyboard and mouse produce the same state. | Not run |
| H04 | New or Bound: use ordinary boxes to reach 60, then 61; clear one. | Count displays 60 and action enabled; 61 displays over-limit count and action disabled; returning to 60 restores action. No implicit truncation or silent dropped selection. Mock tests already prove observer logic; actual-host execution remains distinct. | Not run |
| H05 | Bound: search `fixture-0007@N00`, press Apply search, check its row. Change search to `fixture-0008@N00`, apply. Clear search and apply. | Each exact-ID query yields its one eligible row. First selection remains counted when hidden. Clearing restores 372 eligible ordinary checkboxes with its mark intact. Unpublished instead has 376. Search does not remove membership or intent rows. Record apply/reopen latency and any focus/scroll reset. | Not run |
| H06 | Select one eligible row, search `no-such-fixture`, apply. Cancel; reopen same fixture. | No eligible rows match; hidden selection remains counted and confirmable. Cancel sends no result dialog. Reopen starts at zero with blank search. New defaults to none; Bound stays disabled at zero. | Not run |
| H07 | With the staged scanability-fixture amendment installed, search `Shared coastal photographers`, apply; check only ID `fixture-0374@N00`. Search exact ID `fixture-0375@N00`, apply. | Two identical labels are separately distinguishable by exact IDs. First is selected; second remains unchecked. Both remain eligible. Display name never owns checkbox identity. | Not run |
| H08 | With the staged amendment installed, search `fixture-0376@N00`, apply; inspect long label and exact ID; use horizontal scrolling if shown. | Long synthetic group name cannot make the exact identity inaccessible. Record clipping/tooltip/scroll behavior. If ID is unreachable, this is a mechanical defect requiring layout repair, not owner approval of hidden identity. | Not run |
| H09 | Bound: inspect both readonly panels using scroll; search exact `fixture-0001@N00`. | Architecture photographers 001 is current membership only. Birds photographers 002 has retained queued intent. Coast photographers 003 has permanent moderation protection **and** later observed membership. Landscape photographers 004 has uncertain-delivery permanent protection. None has a checkbox; protected copy stays visible when membership also exists. Search for 0001 yields zero eligible rows, never a selectable membership. | Not run |
| H10 | Loading, Stale, Unavailable, Contradictory: open each separately. | All four expose zero eligible checkboxes and disabled confirmation. Loading explicitly says loading. Stale labels prior observation stale/diagnostic and current membership unavailable. Other failures expose Unavailable. No partial/current-looking rows or inferred empty observation. | Not run |
| H11 | Complete empty fixture. | Complete successful timestamped state, zero eligible rows and no current memberships/history. Queue stays disabled. This state never claims Unavailable. | Not run |
| H12 | Existing public fixture: inspect context, check one eligible box, confirm. | Existing public Flickr photo / fixture-photo-A, binding fixture-existing-A, no Album attachment. Queue enabled only after 1–60. Result says fixture-only, no render/upload, fresh proof prerequisite and nothing saved/queued. No catalog photo or published collection is created. | Not run |
| H13 | New with none: Save; repeat with one selected group. Bound with one: Queue. Dismiss each summary and reopen. | Summary reports choice none/0, groups/1 and groups/1 respectively. New explains separate ordinary Publish. Bound explains outbox/Phase 6 without render/upload. All say nothing saved or queued; every reopen resets. | Not run |
| H14 | Query field focused: type query, explicitly press Apply search. Separately observe Enter, Tab then Enter, Escape and window close after selections. | Apply search commits typed text before reopening. Record Enter's actual default-button behavior; pressing it must never contact a service. Escape/window close must cancel without result or retained choices. Reopening a modal must not strand keyboard focus outside its controls. | Not run |
| H15 | Open full New and Bound lists, scroll end-to-end, select/deselect and apply search repeatedly. | No hangs, errors, missing end rows or duplicate controls. Record actual first-open, selection-response and search/reopen elapsed times rather than infer host speed from mocks. | Not run |

H07/H08 require the amendment to the synthetic model: IDs 0374 and 0375 share a
display name, and ID 0376 has a deliberately long display name. Counts remain
376 writable / 372 eligible in a bound fixture. Earlier installed copies had
only short unique names, so they cannot supply those two pieces of evidence.

## Owner decisions after mechanical checks

These are preference or design-review choices. A mechanically successful host
run does not imply that Terry has accepted them.

- Is filename/title plus Album and explicit scope enough photo context, or is
  a thumbnail required before production implementation?
- Is the Apply search/reopen step acceptable with hundreds of groups, including
  lost focus/scroll position if the host resets them, or should search be revised?
- Are 125-pixel readonly and 220-pixel eligible scroll regions comfortable on
  Terry's display, especially when reading permanent-protection copy?
- Is the default confirmable No group additions state clear enough, and are
  separate Save for publish / ordinary Publish and bound Queue actions clear?
- Does Terry approve the complete interaction/storyboard for #0024/#0026, or
  request specific revisions? This explicit approval is separate from host
  correctness, installation success and ticket lane movement.

Long labels hiding exact IDs, clipped safety copy, incorrect action enablement,
unreachable Cancel, lost hidden choices or any actual mutation are defects.
They do not become acceptable solely through a subjective usability decision.

## Local audit evidence and limits

The unchanged integrated Lua5.1 model test passed. The independent mocked SDK
view/observer harness passed 424 checks in 0.821 seconds on this machine across
all eight fixtures. With the staged scanability amendment, the same harness
again passed 424 checks; added model checks prove distinct ID filtering and
independent selection for the duplicate labels and retain the 376-row count.
The amended model also passed the Adobe SDK 15.3 compiler parse.

The fixture model repeats complete validation while classifying each row,
which makes list assembly quadratic in its fixed 376-row fixture count. No
performance change is justified by the sub-second mock run alone; the actual
host must measure widget construction/scrolling separately in H15. This preview
is a bounded review fixture and is not production pagination or performance
qualification. No additional native behavior defect was demonstrated by this
offline audit. Actual host fit, focus, wrapping, resizing and latency remain
unexecuted here and are owned by the parent agent's UI session.
