# Next-priority FGA batch handoff, 2026-10-17

This later handoff supersedes the earlier same-day #0092/#0095 pending-decision
status in the [staged batch record](fga-staged-batch-handoff-2026-10-17.md).
All outputs below are source/design or offline evidence. No deployment,
provider resource creation, native Lightroom action, real credential read or
Flickr operation occurred.

## Decision and deliverables

| Ticket | Output and handoff boundary |
| --- | --- |
| #0092 | Terry explicitly accepted the reviewed Album status/repair contract as proposed; canonical acceptance/admin supplement is committed at `01c909e`. Wire tables and budgets remain identical to reviewed `403e603`; no duplicate approval is required. |
| #0095 | [Upload recovery store](../design/upload-attempt-store-2026-10-17.md) now accepts the two approved initial obligation states with strict identity/null/scoped-proof validation. The former vocabulary dependency is resolved; source checks do not qualify native storage. |
| #0108 | [Disabled Album binding ensure/read](../design/album-binding-admission-2026-10-17.md), migration0020 and guarded atomic first obligation. General association/delivery remains #0110 and later work. |
| #0040 | [Finite post-handler edge faults](fixed-origin-edge-faults-2026-10-17.md), closed redirect paths and bounded malformed/truncated/oversize stimuli. This is not native/edge qualification. |
| #0042 | [Offline lifecycle and closed composition](fixed-origin-lifecycle-2026-10-17.md), durable quotas/expiry, exact receiver service binding, identity journal and fail-closed cleanup model. No live provider adapter or completed execution packet is claimed. |
| #0093 | Corrected title/local-removal wire proposal, canonical `73b6d0a`, `docs/proposals/album-title-local-removal-wire-2026-10-17.md`. It remains Proposed until the separate #0094 owner decision. |

The #0092 acceptance grants scoped implementation authority. Qualification,
deployment and real-account operations retain their separate later gates.
The source backend routes remain default-off; plug-in registration and
production configuration/toolchain were not enabled or changed.

## Material independent-review corrections

- #0040 now requires primitive run strings before validation/interpolation,
  refusing stateful coercion without consuming the source body. A Worker-safe
  PNG helper preserves fixed source bytes; deployed-module graph checks find
  no Node/fault-factory/Buffer dependency. The two finite source truncation
  pairs are 55/67 and 56/68 actual/declared bytes, not arbitrary body sizes.
- #0042 now composes the actual #0038 wrapper and #0040 stimuli with the actual
  durable quota guard. Admission precedes candidate work; expiry/disable is
  rechecked before publication. The exact captured ordinary dispatcher receives
  ordinary Request/environment objects without quota or receiver activity.
- Same-origin receive/report paths reach the receiver through a constructor-
  supplied narrow service binding. Production Bearer credentials refuse before
  forwarding/storage; missing redirect authorization can still be observed.
  Every fixed-origin receive/report consumes the 96 FGA total as well as the
  independent 16 receiver/report limit. SQLite replacement cannot reset exhausted,
  expired or disabled singleton state.
- Original cancellation and the inner lifetime are checked after awaited scope,
  admission and publication operations, with signal propagation. Exact reviewer
  probes for exhausted 96, abort during inspection and 601000-ms expiry now refuse
  without forwarding or receiver work. These are source fences, not proof of
  native active cancellation or provider disconnect behavior.
- #0093 preserves the original accepted first-photo create path after archive,
  using frozen metadata/current fences. It permits no post-archive title write
  or replacement creation. Later ambiguity has an admin-only repair handoff;
  replay preserves the original removal receipt. Schema union pipes render
  correctly. The new title/archive wire still needs #0094 acceptance.

## Concrete remaining preparation boundaries

The proposed #0042 packet uses one 32-hex run ID, a 20-minute outer resource window
and the unchanged at-most 10-minute qualification window. It names one synthetic
D1, one receiver Worker, two absent-before/create-once temporary Actions secrets
and five exact qualification bindings, including `FIXED_ORIGIN_RECEIVER`.
These names/budgets are future packet inputs, not live authority.

The closed composition exposes only the three original wrapper cases plus ten
finite edge cases. The full twenty-case #0039 factory is Node-only offline
evidence and is deliberately refused by this Worker composition. #0041 owns
that native entrypoint/remaining case integration before a complete execution
packet can be reviewed. Do not import the Node factory into a Worker or describe
nineteen exercised core/edge admissions as full matrix/native qualification.

#0037 remains unqualified/return-to-design. #0043 exact restoration rehearsal,
#0044 final packet review and #0045 concrete execution authorization remain open.
The offline Python provider seam and disabled CLI do not provision anything or
prove real cleanup. #0059's separate token/action-time gate and #0141's release,
rehearsal, scope and writer-drain requirements are unchanged. Reuse retained
identity/pair evidence; no repeated owner input was requested.

## Verification

- Integrated Python/Lua suite: **638 tests passed**. The final five-binding
  lifecycle change was additionally rerun through its 11 focused Python tests.
- Final integrated backend/Worker/fault/composition suite: **477 tests passed**.
- Independent #0095 follow-up: 43 actual Lua tests and 36 added adversarial cases;
  SDK15.3 parsing passed. Full and compact records enforce truthful initial
  state/photoset combinations and retain uncertain/malformed work.
- Independent #0108 review: 18 SQLite/Worker tests, eight extra adversarial
  scenarios and exact agreement of five schemas with accepted #0088.
- Independent #0042 final re-review: 39 focused composition/quota cases and
  original failure replays pass. #0040 independent source/fixture/VM checks pass.
- Canonical authority/drift: 12 tests passed, with independent #0092 table/budget
  comparison and #0093 link/schema-column/timeline checks.
- Native TypeScript 7.0.2, API projection equality, changed Python Ruff/Pyright
  and focused source checks passed. Node 24.22.0 and pinned uv 0.12.5 frozen
  workflows were used without dependency or global tool updates.

Private receipts and raw capture remain outside Git. The original wrapper,
toolchain, production configuration and plug-in Info registration remain
unchanged; exact source provenance is recoverable from the commits.

## Board and agent workflow

Implementation/test/inventory agents used the eight-slot ceiling. They finished
and released slots before fresh independent reviewers were assigned. Review
findings returned for correction and re-review; no idle fixed reviewer pairs or
grandchildren were created. New task names use full model/effort words and
four-digit ticket numbers.

The parent initially delayed the lane update and corrected it at Terry's prompt.
All nine active global/FGA AGENTS files now require In Progress
before ticket work or delegation, including acceptance recording/tests/review.
Subsequent correction/review turns verified the lane first. Dependencies belong
in relationships/Ready for Work; external obstacles alone belong in Blocked.

#0146 retains Terry's Blocked/P4 TS7.1 upgrade/watch scope. Existing cards #0048,
#0074, #0076 and #0121 reference it for compiler/artifact provenance. No blocking
dependency, compiler upgrade, release-status lookup or automation was added.
Their brief In Progress intervals were relationship maintenance only; original
lanes were restored. Shared localswim code and ticket priorities were unchanged.
