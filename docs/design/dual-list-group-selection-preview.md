# Dual-list group-selection preview

Date: 2026-10-15. Ticket #0027. Status: two-list interaction accepted by Terry;
copy/layout follow-up and remaining mechanical checks are separate.

## Owner request and chosen candidate

Terry found the bottom-left Apply search button difficult to discover. He
prefers filtering on every added or removed character; if an explicit action is
necessary, it must sit beside the field. He then requested available groups on
the left and intended additions on the right, with search above the left list.
He prefers clicking a row to move it but explicitly accepts two move buttons
between the lists as an alternative.

The revised fixture uses documented native `simple_list` controls and an
immediate edit-field validator. Selecting a list row highlights it. The center
Add/Remove buttons perform the explicit move; list highlight changes do not
mutate the chosen group set. The SDK selection value alone does not identify
whether a change came from a mouse click, keyboard navigation or an item-list
refresh. Explicit buttons avoid depending on that distinction. No actual host
auto-selection defect is asserted by this design choice.

The left list contains eligible, not-yet-selected groups matching literal name
or exact-ID search. The right list always contains all selected additions,
independent of search. Duplicate names retain distinct exact IDs. Row labels
put IDs first so the long synthetic group name cannot hide its identity behind
the name. Readonly current membership and retained/protected intents stay
separate from both editable lists.

The selected list is the sole choice: an empty unpublished selection means
no group additions and Save remains enabled. Removing the last selected
group clears any previous additions and returns to that valid empty choice.
There are no mode radio buttons. Bound and existing-public contexts still
require 1 through 60 selected groups;
61 disables confirmation without silently truncating the set. Returning a
selected group to available groups edits only the proposed addition; it never
removes Flickr membership or clears retained intent/protection.

## Native review sequence for the revised build

Record only synthetic observations. Earlier build 0.0.1.4 evidence remains
historical and does not qualify the revised view. Check the exact delivered
version in Plug-in Manager before testing.

1. Open Unpublished: left has 376 groups, right is empty, no radio buttons
   appear and Save is enabled.
2. Highlight one left row: the selected-addition count stays zero. Use Add to
   move exactly that ID right; it disappears left, count becomes one and Save
   stays enabled. Highlighting another row alone must not add it.
3. Type and erase search characters without leaving the field. Left matches
   update without Apply or closing/reopening the dialog; right remains intact.
   Confirm focus and typed text remain stable.
4. Search Shared coastal photographers: distinguish exact IDs 0374 and 0375.
   Add one and verify only that exact ID moves. Search the long-label fixture
   0376 and verify its exact identity is accessible in both lists.
5. Highlight a right row and use Remove: exactly that ID returns left if it
   matches the active query. It may stay hidden by that query, but it is no
   longer counted or shown right. Clearing search restores all available rows.
6. Remove the last selected addition: the right list becomes empty and Save
   remains enabled for an unpublished photo. All eligible groups return left
   subject to query. Cancel/reopen resets search, highlight and additions.
7. Open Bound limit test: 59 selected right. Add an available row to 60, another
   to 61, then Remove one to 60. Confirmation is enabled/disabled/enabled.
   Current/protected rows must never appear as available additions.
8. Open Existing public: confirm exact binding/no Album context, Add one, then
   Queue. The transient summary must say fixture-only, no render/upload, fresh
   proof prerequisite and nothing saved/queued.
9. Check Loading/Stale/Unavailable/Contradictory and complete empty separately.
   Confirmation stays disabled; empty success remains distinct from failure.
10. Inspect fit, full readonly safety text, long identities, keyboard traversal,
    Enter/Escape, list scrolling and responsiveness with the full group set.
    Keyboard highlight changes alone must not transfer rows. Report actual
    behavior; model tests do not prove host focus, sizing or timing.

The separate fixture continues to use no account credentials, network,
catalog reads/writes, persistence or real submissions. Production selection
implementation and release qualification remain separate gates.

## Local verification of build 0.0.1.5

The integrated Python/Lua suite passed 246 tests. Its revised native control
model passed 76 structural checks. Four canonical event methods, 14 independent
synchronous/deferred scenarios, the explicit bound59 limit test, deferred entry
test and preserved pure model/isolation test passed. Ruff, Pyright and Adobe
SDK 15.3 compilation of all three fixture Lua files passed. These are offline
results, not native list-rendering or live-keystroke acceptance.

The [independent review](../evidence/dual-list-selection-review-2026-10-15.md)
records the source digest and query/radio race corrections. Its reusable harness
is `clients/lightroom/prototypes/tests/test_dual_list_review.py`; pass the
fixture bundle directory and `SelectionModel.lua` path as its two arguments
through the repository's `uv run --frozen python` environment.

## Owner acceptance and copy/layout follow-up

On 2026-10-15, Terry explicitly approved the two-list interaction and asked
to simplify the technical text. He separately confirmed that dynamic
filtering and the Add/Remove buttons were intuitive and responsive in the
actual Lightroom Classic 15.6 preview. This is owner acceptance of that
interaction, not a measured latency benchmark or completion of every
mechanical acceptance scenario. Do not request the same interaction approval
again. Remaining mechanical verification stays with the implementing agent.

The follow-up copy/layout build must keep the useful photo/Album identity
and protected-state guidance while removing unnecessary fixture/debug
explanation and empty unpublished membership space. Terry also requested
equal-width Add/Remove buttons vertically centered against the two list
boxes. These refinements do not change selection or submission semantics.

This resolves #0024's owner interaction prerequisite. Existing-photo
qualification remains a separate integration dependency; no intake,
deployment, Flickr write or publisher activation follows from UX approval.

## Delivered follow-up: build 0.0.1.6

Build 0.0.1.6 shortens the preview notice and preserves useful photo/Album
identity. It omits the empty membership panel for unpublished fixtures and
removes general technical scope/refresh narration. Bound-photo readonly
membership and protected-submission facts remain. The two move buttons
use equal 90-pixel widths and a centered column in a row containing only
the two list boxes; search and headings occupy a separate row.

Local verification passed 247 Python/Lua tests, 75 revised control-model
checks, 14 independent event scenarios, the explicit 59/60/61 limit
check, Ruff, Pyright and Adobe SDK 15.3 compilation. Native alignment of
this cosmetic build is not yet recorded. Existing build 0.0.1.5 owner
interaction acceptance remains valid and is not requested again.

## Approved empty-selection refinement

On 2026-10-15, Terry approved removing the radio buttons and deriving
the no-additions choice from an empty selected list. Preview 0.0.1.7
implements that requested refinement. Saving an empty unpublished
selection is valid, including clearing an earlier selection; an empty
bound/existing-public selection remains ineligible for Queue. No fake
empty batch is sent. Ordinary publication without groups does not
require opening this dialog. All protection, availability, exact-ID,
one-through-60 nonempty batch and cancel semantics remain unchanged.

## Contextual action labels

Terry requested that the action button describe what the current choice
will do, including its selected-group count. The native SDK documents
action-button bindings through `LrDialogs.presentModalDialog` and the
bindable push-button attributes. The preview binds its title as well
as its enabled state. Unpublished labels are Save for publish: no
groups, Save for publish: 1 group, or Save for publish: N groups.
Bound/existing-public labels are Queue for 1 group or Queue for N
groups; zero remains disabled. Search and highlight changes alone
never change the selected count or cause a submission.

These labels retain the actual action boundary: Save records the
group choice; ordinary Publish remains separate. Publish-to-Flickr
wording belongs only on an action that actually initiates publication.
No publication runtime is introduced by this label change.

## Local verification of build 0.0.1.7

The integrated Python/Lua suite passed 249 tests, including seven
adversarial event methods and 102 revised structural checks. Fourteen
independent synchronous/deferred scenarios, pure model/isolation,
explicit 59/60/61 limits and deferred-entry checks passed. Ruff, Pyright
and Adobe SDK 15.3 compilation passed. Twenty-four related architecture
authority/interaction/moderation/API contract tests passed.

The [independent review](../evidence/empty-selection-review-2026-10-15.md)
records the exact model/view digests and count-aware title checks.
These are offline results; native title redraw and the revised empty
Save/Queue affordances are not claimed as observed for this build.
The owner's semantic approval is recorded separately and does not need
to be requested again. No publication, intake or dispatch was activated.
