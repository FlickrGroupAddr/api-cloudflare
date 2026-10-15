# Lightroom fixture host checkpoint

Current follow-up: [hosted thumbnail and timing handoff](hosted-thumbnail-handoff-2026-10-15.md) and [later selection observations](../evidence/lrc15-selection-preview-host-2026-10-15.md). The selection-popup instructions below are the earlier checkpoint, not the latest test state.

Date: 2026-10-15. Status: bounded host evidence; selection review in progress.

## Agent policy and speed

Terry approved role-based model and effort choices and Standard speed. Global
and project AGENTS.md now record Sol Medium for ordinary work, Sol High for
authentication/transaction/recovery review, Luna Low for narrow mechanical
work, and selective Astra Medium for difficult architecture/debugging. The
user configuration's `service_tier = "default"` was verified. This pass used
Sol High for independent persistence evidence, Luna Low for an empty checklist,
and Sol Medium for probe/fixture changes; only the parent operated native UI.

## Installed fixtures and disposable catalog

Terry explicitly approved installing both local fixture bundles and creating
a new empty outbox catalog. The parent installed the separate selection preview
and outbox probe, then created `FGA-Outbox-Probe.lrcat` beneath the approved
temporary test location. The native host displayed All Photographs count0.
No photography catalog was used for the probe. The test catalog and transient
receipts remain outside Git; do not delete them as part of ordinary cleanup.

## Outbox result

Probe0.0.2.4 initially produced no complete receipt. A diagnostic build isolated
successful file write/close followed by failed SDK move. Using a Windows-native
root and documented `LrPathUtils.child` in build0.0.2.6 repaired this observed
host failure. No universal slash restriction is inferred from that experiment.
A new receipt-only preflight performed no catalog API operation and passed.

The subsequent fresh synthetic run passed private-gate completion, exact
immediate readback and rollback after an intentionally failing callback. The
parent normally closed the host, independently observed it no longer running
with no windows, and reopened the exact empty fixture. A matching-run receipt
then confirmed the same record. One launch reported no targetable window even
though the host started; fresh enumeration recovered its current window without
a second launch. This is a bounded normal-restart observation, not crash, power
loss, restore/copy, storage-full, concurrency or production-outbox qualification.

The independent [evidence receipt](../evidence/lrc15-outbox-host-2026-10-15.json)
contains source/receipt digests, valid host context and attributed lifecycle
timestamps. Machine receipts retain their false lifecycle-qualification flags;
the separate observer evidence establishes only the normal lifecycle above.
Owner acceptance remains separate. The bounded proof can be reviewed on#0029.

## Selection preview checkpoint

The parent installed0.0.1.2 and observed the initial unpublished-photo view:
376groups, synthetic photo/Album/scope, explicit No group additions default,
visible Cancel and Save. Add-to-groups at0disabled Save; one ordinary checkbox
enabled Save/count1; keyboard Space unchecked it and returned to0disabled.
Choosing the No group additions label enabled zero-group Save, and its summary
reported none/0 and explicitly nothing saved or queued. A first circle-target
click did not visibly settle that mode; a subsequent label click worked. This
does not establish a host observer defect.

Build0.0.1.4 is now loaded. It adds a clearly labeled Bound limit fixture with
59preselected eligible groups, leaving two visible ordinary checkboxes for the
60/61boundary check. It also adds regression-tested guards for modeled delayed
observer delivery; that modeled failure is not presented as a proven15.6host
defect. The parent is currently at the fixture launcher's open popup. Next:
choose the Bound limit fixture, check0007to60, check0013to61, clear0013to60,
then continue exact-ID/name search, hidden selections, long/duplicate labels,
protected rows and unavailable/empty contexts in the host checklist. These
remaining native cases have not passed merely because their mocks pass.
Terry's subjective interaction approval is still required before production
selection/submission implementation.

## Interruption diagnosis

Terry supplied a screenshot of a platform notice saying content could not be
shown, with cybersecurity guidance, and reported seeing it twice. That notice
is distinct from the probe's receipt guard and from the Node REPL losing its
`sky` binding. The parent initially misidentified which guard Terry meant.
No internal content-filter trigger or remedy was established. Preserve actual
tool errors separately; after the missing binding, documented initialization
and fresh app/window selection recovered supported native observation. Do not
infer that a platform notice is an approval-review rejection or silently claim
the Windows helper failed. Checkpoint source and evidence before continuing.
