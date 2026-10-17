# Lifecycle decision and next implementation batch — 2026-10-17

This batch records Terry's acceptance of #0094 and advances #0044, #0111 and
#0123 through their bounded review handoffs. All selected cards moved In Progress
before work or delegation. No Lightroom Classic fixture was loaded or invoked,
no provider/cloud/Flickr operation ran, and no real photo or credential was read.

## Owner decision #0094

Terry accepted the exact reviewed lifecycle contract at canonical `73b6d0a`.
Canonical commit `3fbb6bf` records acceptance without changing the reviewed routes,
fields, state tables or budgets. Independent review and twelve authority/drift
checks passed. Terry subsequently marked #0094 Completed.

The accepted scope covers revisioned title intent, non-destructive local archive,
retained attachments, surviving service tombstones and administrative creation
repair. Qualification, deployment and live operations retain their later gates.
No further owner decision is needed for this contract's scoped implementation.

## #0044: reviewed packet, execution remains NO-GO

The exact baseline/candidate/capture/resource/matrix/rollback packet and two
independent specialist reports are recorded in:

- [Execution packet](fixed-origin-execution-packet-2026-10-17.md).
- [Isolation review](fixed-origin-packet-isolation-review-2026-10-17.md).
- [Lifecycle review](fixed-origin-packet-lifecycle-review-2026-10-17.md).

Review verified sixteen source hashes and bounded source/VM/SQLite checks.
It did not pass the missing exact-artifact route-conformance phases, provider
restoration/changed-secret/current-production proof or native measurements.

The requested thirty native fault cases would consume 120 FGA admissions before
additional observations, exceeding the retained 96-request limit. The current runner also
consumes its target on one invocation. A complete executable within-budget
schedule/orchestrator and provider-wide temporary-secret ownership remain
unresolved. The quota was not increased, a smaller coverage set was not silently
substituted, and Completed source cards were not reopened. #0037 stays unqualified
and #0043's provider restoration verdict stays negative. Review signoff of this
no-go report cannot authorize execution or turn missing evidence into success.

## #0111: dormant first-photo materialization

The new owning-D1 store/migration, strict upstream dependency and worker preserve
the immutable first photo, fresh complete pre-context, current link/grant/gate
and lease/epoch fences, and commit a durable marker before at most one create.
A returned ID/URL is retained as attempt evidence before fresh owner/membership
proof; failed proof leaves the binding ID null and ambiguity/history retained.
The primary pair completes without addPhoto.

Review corrections added zero-ID refusal, a closed no-creation rejection-code
allowlist, a 45-second invocation budget with operation/commit margins and durable
returned-ID evidence. Broader actual local D1 verification then caught two adapter
assumptions: TEMP tables are forbidden and change metadata includes trigger writes.
Migration 0022 now uses transactional ordinary scratch tables; exact UPDATE
RETURNING rows grant mutation authority. Populated history, rollback, scratch
cleanup and one-shot behavior passed actual local D1 tests and independent
re-review, rather than relying only on a SQLite-shaped adapter.

The worker remains default-off and has no registered route, scheduler, credential
reader or production transport factory. Later attachment/status/title work and
hosted/provider qualification remain separate.

## #0123: exact runnable fixture preparation

Candidate `FGA-ProviderRender-Qualification.lrplugin` version 0.0.1.2 now has an
explicit menu, isolated test-provider/private-metadata registration and actual
SDK bindings. Fixed qualification-only constructors share existing behavior;
production constructors retain their original identity checks. The guarded
future dispatcher creates generated TIFF photos and one test Album in an exact
empty disposable catalog, freezes/readbacks before requesting renditions, and
executes fourteen finite case paths. Fault injections are distinguished from
actual host failures and counted only when applied.

Review rejected the earlier constructor-only artifact as incomplete. Later
review corrected eager-render cleanup: started work is tracked and drained before
catalog/file deletion. Unknown termination preserves the catalog and files and
fails the overall result; the fixture makes no hard cancellation claim. Sanitized
receipts distinguish actual observed host build, declared SDK/candidate version,
requested/injected faults, header observations and incomplete cleanup. Header
markers never claim verified ICC profile or native qualification.

The final private v4 stage binds 24 actual Lua files, an artifact digest and exact
manifest-byte digest. Its consent template is deliberately invalid. Earlier
v1/v2/v3 pins are superseded. The [packet](provider-render-qualification-packet-2026-10-17.md)
contains concrete future #0135 scope, including the isolated test provider,
generated catalog writes, bounded scratch and separate cleanup. Neither source
preparation nor its tests grant consent or establish a #0126/native result.

## Verification and integration

Final parent Python/Lua suite: **757 tests passed**.
Backend/Worker/local-D1/probe suite: **614 tests passed**. Native TypeScript 7.0.2 and
exact API projections passed. Final lint/typing, SDK parsing, staged privacy and
whitespace checks are recorded with the handoff commit and board comments.

Detailed private evidence is under workspace `work-batch-2026-10-17-next`.
No raw captures, catalog paths, provider IDs, credentials, licensed SDK payloads
or native screenshots belong in this public repository. The source toolchain
remains Node 24.22.0, uv 0.12.5, Python 3.14.7/Lua 5.1 and SDK 15.3; global tooling
and dependencies were not changed.

Fourteen implementation/inventory/review roles started while two slots were
reserved for #0094. Authors released slots before fresh reviewers; correction
and re-review used the same bounded rolling workflow. Later source-completion
roles addressed the actual runnable-fixture gap. Every spawn specified its
permitted model/effort, there were no children, and the sixteen-direct-subagent
ceiling was respected. Shared localswim source and ticket priorities were unchanged.
