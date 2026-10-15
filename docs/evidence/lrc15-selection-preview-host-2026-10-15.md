# Lightroom Classic 15.6 selection preview host evidence — 2026-10-15

This index records the parent-observed native host interactions for FGA #0027 selection preview. Composite checks remain **Partial** when any required step was not observed. The record does not indicate owner preference approval.

## Run metadata

| Field | Observation |
| --- | --- |
| Date | 2026-10-15 |
| Host | Lightroom Classic 15.6 |
| Host build | 202609251514-f839cde9 |
| SDK | 15.3 (owner-confirmed) |
| Observed screenshot dimensions | 3413 × 1440 |
| Display scaling | Not recorded |
| Preview bundle | 0.0.1.4 observed (expected 0.0.1.2 in the earlier checklist) |

## H01–H15 host checklist

| ID | Result | Observations and remaining coverage |
| --- | --- | --- |
| H01 | Partial | New fixture showed Harbor at dawn / DSC_0042.NEF, Coastal light, service 12 / Album 34; 376 rows, default none/0, Save enabled. The unpublished-photo context was observed; launcher cancellation was not separately recorded. |
| H02 | Partial | Protected panel was vertically scrollable; full long safety copy was not completely read. Native resize and full Tab sweep were not run. |
| H03 | Partial | New: Add with 0 disabled; checking one enabled; Space uncheck returned to 0 disabled. None label and Save at 0 produced fixture-only none/0 summary, nothing saved/queued. |
| H04 | Partial | Bound: 59 → click fixture-0007 → 60 enabled; click fixture-0013 → 61 disabled; Space → 60 enabled. |
| H05 | Partial | Exact query fixture-0376 returned 1 of 372; selected count 60 remained while the selection was hidden. Dragging the horizontal scrollbar revealed the exact ID on the long row. Clear-search behavior was not reported. |
| H06 | Partial | `no-such-fixture` returned 0 of 372 with 60 retained and Queue enabled. Queue produced a fixture-only groups/60 summary saying nothing was saved/queued. Cancel, window X and Escape independently returned to root without a summary. Reopen-reset behavior was not reported. |
| H07 | Partial | Shared coastal name returned distinct IDs fixture-0374 and fixture-0375. Checking only 0374 produced 61 with 0375 unchecked; Space returned to 60. |
| H08 | Partial | Query fixture-0376 returned one row; dragging the horizontal scrollbar exposed its exact ID and long row. |
| H09 | Partial | Vertically scrolled protected panel showed current membership for 001, queued intent for 002, moderation protection plus later membership for 003, and uncertainty for 004. Full long safety copy was not completely read. |
| H10 | Partial | Loading, Stale, Unavailable and Contradictory each opened with 0 eligible rows and Queue disabled. Stale was explicitly labeled as diagnostic/stale. |
| H11 | Partial | Complete empty fixture showed a timestamped complete state with 0 rows and disabled action, distinct from Unavailable. |
| H12 | Pending | Existing public fixture test remains pending. |
| H13 | Partial | New none/0 and Bound groups/60 fixture-only summaries were observed; they said nothing was saved/queued. Full dismiss/reopen coverage was not reported. |
| H14 | Partial | Cancel, window X and Escape each returned to root without a summary. Enter behavior and full Tab/query sweep were not run. |
| H15 | Partial | Specific search and selection interactions are recorded above. Full-list sweep and latency benchmark were not run. |

For the Contradictory fixture, Cancel was not confirmed: a window lookup failed, while fresh application inventory still reported the Lightroom host running. No crash is claimed.

## Follow-up

Next manual checks: complete H12, then the remaining ergonomics and keyboard coverage (native resizing, full Tab sweep, Enter behavior), followed by full-list scrolling and latency measurements. Owner preference approval remains **false**.

Separate outbox host evidence: `docs/evidence/lrc15-outbox-host-2026-10-15.json`.

## Owner review of the checkbox/Apply-search build

On 2026-10-15, Terry supplied the requested native screenshot after using the
Unpublished fixture and searching Shared coastal photographers. The two exact
IDs 0374 and 0375 were shown, both unchecked, while one earlier hidden
selection remained counted and Save was enabled in groups mode. This
supports that specific search/hidden-selection observation, not every H05/H07 step.

Terry found the distant bottom-left Apply search button difficult to discover.
He prefers filtering on each character and requested available groups left,
selected additions right, with search above the left list. Click-to-move is
preferred, but two move buttons between lists are explicitly acceptable.
This is a requested interaction revision, not final approval of either view.
The [revised prototype plan](../design/dual-list-group-selection-preview.md)
records the candidate and its own outstanding native checks.

## Owner-reported native dual-list result

On 2026-10-15, Terry confirmed loading preview 0.0.1.5 through Reload
Plug-in, explicitly approved the two-list interaction and reported dynamic
filtering plus Add/Remove as intuitive and responsive. His screenshot
shows only the upper dialog, so list behavior here is attributed to his
report rather than independently inferred from pixels. No measured latency,
full keyboard sweep, 61-boundary host result or existing-public case is
claimed for this build. The earlier H01-H15 table remains historical.

Current owner interaction approval: **true** for the dual-list/live-filter
flow. Technical-text simplification and equal-width, centered move buttons
were requested as follow-up. The earlier checkbox approval-false entries
do not override this later explicit approval.

## Native selected-count and action-title observations

On 2026-10-15, Terry supplied sequential native screenshots of the
unpublished empty-selection preview. They show no radio buttons and the
following states: 3 selected/373 available with Save for publish: 3
groups; 2/374 with the 2 groups label; 1/375 with singular 1 group;
and 0/376 with Save for publish: no groups. Exact synthetic IDs return
to the left list as removed. Terry explicitly reported the singular
and zero cases as correct. This directly supports native title redraw
and these count transitions. The screenshots do not display a plug-in
version field; the tested source is the delivered 0.0.1.7 candidate.
No zero-save click/result, bound-zero queue, 60/61 native boundary,
latency measurement or real submission is inferred from these images.

The same screenshots expose fixed-width lists and NSID-first labels
that clip useful group names despite spare dialog width. Terry requested
name-first labels with NSID last and lists expanding across the available
dialog width, retaining a compact centered move-button column. The
documented SDK supports a whole-view tooltip, but no per-item hover
callback was identified for simple_list. Full highlighted identity must
remain accessible independently of a clipped row or row-specific hover.
