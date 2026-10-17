# Staged FGA batch handoff, 2026-10-17

Later same-day update: #0092 was accepted and the #0095 follow-up passed review.
See the [next-priority batch handoff](fga-next-priority-batch-2026-10-17.md) for
current status; the pending-decision description below records the earlier point.

Terry resumed the eight tickets staged at the previous stopping point. Seven
deliverables reached independent review handoff. The dormant upload store has
corrected code and remains Ready for Work, dependent on the existing #0092
vocabulary decision;
this is not a full #0095 contract-completion or production qualification claim.

## Delivered work

| Ticket | Output | Evidence and boundary |
| --- | --- | --- |
| #0039 | Finite actual pinned-handler faults and sanitized collector | [Fault matrix](fixed-origin-fault-matrix-2026-10-17.md); 22 focused checks, independent image decoding and collector boundaries |
| #0057 | Disabled shared READ/proof policy and strict JSON decoder | [Shared adapters](../design/shared-read-proof-adapters-2026-10-17.md); release constructor refuses before credentials, capability flags remain false |
| #0065 | Immutable scoped frozen-choice consumption adapter | [Frozen choices](../design/frozen-choice-consumption-2026-10-17.md); fully validated exact acknowledgements only, no replay authority |
| #0091 | Canonical Album status/create-repair wire proposal | Canonical architecture `403e603`, `docs/proposals/album-status-create-repair-wire-2026-10-17.md`; Proposed until #0092 acceptance |
| #0096 | Original unregistered ordinary-Album provider shell | [Provider shell](../design/ordinary-album-provider-shell-2026-10-17.md); no render/remote operations or native menu qualification |
| #0105 | Advisory upload candidates and original issuance authority snapshot | [Candidate reader](../design/upload-candidates-2026-10-17.md); default disabled, legacy missing snapshots unavailable, no automatic binding |
| #0109 | Guarded service-identity create/read and client persistence adapter | [Service identity](../design/publish-service-identity-2026-10-17.md); default disabled, safe lost-response orphan, save and fresh verification before use |
| #0095 | Dormant bounded upload store, strict codec and private photo field | [Upload store](../design/upload-attempt-store-2026-10-17.md); safe retention is implemented, initial hosted-state acknowledgement remains blocked |

The six reviewed API deliverables above are committed in `30d97a1`. Parent
integration owns shared registry/Worker framing and exact generated API schemas,
the original issuance snapshot migration, and the disabled factory decoder.
No `Info.lua` registration or production configuration was enabled.

## Independent findings and corrections

- #0057 rejected malformed header tokens and false `no-store` matches only
  after correcting whitespace and quoted-directive parsing. Final independent
  review passed 54 affected regressions and 40 additional actual-Lua checks.
- #0096 now uses the documented observable-table iterator and exact decimal
  formatting for safe-integer local IDs. Both reproduced findings were fixed;
  independent re-review passed 12 Lua tests and SDK15.3 parsing.
- #0109 now preserves `Retry-After: 5` for every service 503 at the Worker
  boundary, including disabled/auth-store failure. Generated service path IDs,
  status/code/retryability and headers match the accepted closed wire. Common
  405/Allow and accepted early provider errors retain their existing scope.
- #0095 no longer demands a hosted Album identity before first render/proof or
  freezes a legitimate advancing hosted binding revision. The local natural
  key stays immutable; validated post-proof correlation is checked against exact
  transient scope evidence. Its numeric scanner rejects unsafe/nonintegral
  persisted number lexemes before lossy floating-point decode.

All independent review details and adversarial receipts remain in the private
workspace batch directory. The public design notes preserve their sanitized
findings, interfaces, bounds and limitations. No raw private evidence is copied
into the repositories.

## Pick up at #0092, then finish #0095

The reviewed #0091 proposal supplies the missing proposed initial obligation
states `waiting_for_album` and `attachment_pending`, plus the closed status/
repair wire, finite budgets and narrow administrative repair allowlist. Existing
server-side session and CSRF policy remain controlling. It accepts no new
authentication ceremony and grants no deployment/live authority.

#0092 must accept or return that exact proposal. Keep the #0092-blocks-#0095 relationship and #0095 in Ready for Work.
The Blocked lane is reserved for external obstacles neither Terry nor Bot can
advance. Do not request a duplicate owner decision or treat proposal review as acceptance.
Until then, #0095 retains pending local work and refuses invented hosted-state
acknowledgements. Existing accepted membership states remain representable.
Compaction immediately after an unmaterialized obligation admission is not
claimed as passed.

After a recorded acceptance, extend the strict local checkpoint validator to
the accepted initial vocabulary, add focused acknowledgement/retirement refusal
and success regressions, and obtain independent High re-review before handing
off full #0095 completion. Do not fabricate a hosted binding before photo proof,
infer verified membership from admission, loosen retention or replay uploads.

## Verification and preserved gates

- Final integrated Python/Lua suite: **623 tests passed** after the #0095 fixes.
- Integrated backend/Worker/fault suite: **407 tests passed**. No backend source
  changed after that run; later corrections were isolated Lua/store work.
- Canonical architecture authority/drift suite: **12 tests passed**.
- Pinned native TypeScript7.0.2, API projection equality, changed Python Ruff/
  Pyright and SDK15.3 Lua parsing passed. Node24.22.0 and uv0.12.5 frozen tooling
  were used without global tooling changes.
- Parent verified staged privacy against 36 retained private capture IDs and
  preserved all nine #0058 POST baseline artifact identities. Reviewed files
  were normalized to committed LF bytes and their source provenance refreshed.

#0037 remains unqualified/return-to-design; accepting its investigation did not
qualify native allocation, effective-edge redirects or cancellation behavior.
The pinned #0038 synthetic candidate remains separate from the unchanged captured
ordinary dispatcher/rollback baseline. These source tests grant no live promotion.

#0059 still needs its dedicated future token and exact action-time decision.
#0141 still needs release/rehearsal, scope and writer-drain evidence. Reuse the
retained account/subdomain/selected pair; no repeated UX/outbox/real-account input
was requested. No provider/Flickr request, real credential read, catalog/native
action, deployment or production activation occurred. Local SQLite/D1 emulation
is offline evidence, not hosted conformance.

## Agent guidance and board monitor

The original five Medium/three High implementation assignments were launched as
planned. Fresh independent reviewers used freed slots; no idle fixed pairs or
grandchildren were created. New names use full words and four-digit tickets,
for example `sol_high_0105_review`, observed by Terry as `Sol high 0105 review`.
Global guidance and every active FGA AGENTS copy record the convention; the
historical publication audit snapshot retains its original exact bytes. FGA
public-snapshot naming-only commit: `89a3df3`.

The existing board service was healthy on loopback port8795. Its stopped shared
monitor was resumed with the original thread target, actor `bot`, and existing
status/target/lock paths. Running actor-filter version2 and a live PID were
verified. No shared localswim code, ticket priority or Completed-card history
was changed. Use shared CLI for future card/dependency updates.
