# Existing-public group workflow independent review

Date: 2026-10-16. Reviewer: GPT-6.1 Sol / High, independent of the workflow and
controller author. Scope: the disabled `ExistingPhotoGroupWorkflow.lua`
composition and `tests/test_existing_photo_group_workflow.py`, with surrounding
actual client/controller/dialog/store code inspected for their integration
contracts. This review owns no workflow source changes and performs no SDK,
desktop, catalog, filesystem-cache or provider operation outside synthetic
tests. Production qualification remains false.

## Authority and composition boundary

The architecture repository's accepted ADR0021/0022/0038, existing-public-photo
intake contract and plug-in/service contract permit explicit queue-only
existing-public-photo intake without an LrPhoto or Album. The workflow uses the
separate catalog-private binding-only recovery store; it creates no
published-photo record, fabricated UUID or album association. Accepted
ADR0045's editable photo metadata is not repurposed for this path. The
`group-selection-controller.md` composition appendix accurately identifies
injected capabilities as caller assertions, not evidence of host qualification.

The reviewed composition loads actual modules and keeps one workflow active.
Its caller must provide a task-safe protected-call adapter, function context,
secure credential reads, verified installation/link identity and separately
qualified transport/storage adapters. Missing capability assertions or task
context refuse before credential/network/dialog work. Browser cleanup remains
owned by that caller's function context; the composition does not create or
claim a native SDK task itself.

The workflow obtains browser selection, fresh initial binding and complete
membership, then reads a fresh writable-group aggregate and complete retained
history through the existing strict protocol clients. The eligibility assembler
receives those validated complete aggregates; failed history or a stale group
snapshot does not become an empty successful projection. It opens the actual
native group dialog only after assembly and controller initialization succeed.

Credential, rotation, installation, link, catalog and cancellation checks guard
every transport entry and return. The explicit existing-public workflow context
requires final proof even when the stable binding retains
`sourceKind:"fga_direct_upload"`; it never rewrites provenance. The controller
snapshots the complete nonempty group set before one batch request and records
the fully validated durable response. A lost response preserves a prepared
record. Read-only pending enumeration blocks a later invocation with
`reconciliation_required` and original handoff IDs rather than replaying it.

## Resolved findings and verification

Two narrow fail-closed findings were corrected by the workflow owner during
this review, then independently checked against the final source:

1. The initial identity check originally accepted any table. A missing
   installation ID disabled the expected-installation comparison in the common
   credential verifier; a malformed link revision could likewise permit browser
   reads and initial proof before later refusal. Independent synthetic injection
   reproduced those reads/proof/dialogs, with no group batch or local outbox
   write. The final correction validates the exact identity shape, opaque
   installation ID and positive safe-integer link revision before any such
   operation, and repeats validation in context checks. The regression covers
   missing/invalid IDs, string/zero/nonfinite revisions and an unknown field;
   all refuse before requests, proof, dialogs or outbox writes.
2. The pending-handoff return path originally omitted a workflow context check
   after its potentially yielding catalog read. The store fences catalog and
   identity, but intentionally has no credential API. The final correction
   rechecks cancellation/current credential/rotation before exposing pending
   IDs after that gate. Independent injection reproduced the former gap without
   causing another batch. The final regression changes rotation/current
   credential/cancellation during gate acquisition; each withholds IDs and
   creates no second batch.

The final independent run of workflow, controller and both store suites passed
54 actual Lua5.1 tests, including seven workflow test methods with the
correction scenarios. Workflow Ruff lint/format and targeted Pyright checks also
passed. The reviewed `ExistingPhotoGroupWorkflow.lua` SHA2-256 is
`230bb364aa0de476b84160517ab9ebda47d01a81605ede8d32c25e875270efed`.
Additional independent
synthetic injections confirmed candidate-credential and absent task-context
refusal before reads/proofs/dialogs, and no batch after a catalog change before
commit. None of these mocks establishes native task lifetime, HTTP redirect or
allocation limits, thumbnail cache behavior, catalog crash/restore persistence,
live provider behavior or production registration. Those remain explicit
qualification/integration work.

No unresolved defect was found in this bounded disabled composition after
those corrections. The result supports source integration with its asserted
adapters; it does not enable production or replace the outstanding independent
host/storage/transport gates or a user-facing reconciliation workflow.
