# FGA development batch, 2026-10-16

Eight unblocked implementation tasks ran in parallel, then freed agent slots
were used for independent reviewers. Authors corrected material findings and
the reviewers rechecked those changes. Model/effort choices followed the global
task policy. This is an engineering handoff, not production activation.

| Ticket | Output and disposition |
| --- | --- |
| #0036 | GET-only inventory collector, bounded CI workflow and ten safety tests; actual partial capture retained. Needs owner access/private-retention input as described in the inventory guide. |
| #0055 | Current group-workflow adapter/ownership map, with documented clock limits and immutable fresh-proof recovery semantics. Independent review passed. |
| #0089 | Proposed publish-service identity create/read wire; unnecessary reservation/activation states removed and link bootstrap clarified. Review passed; #0090 owner acceptance remains separate. |
| #0082 | Proposed unfinished upload outbox and per-photo published correlations; ordinary reopen, explicit known/suspected-restore recovery and justified proposed budgets. Scope/byte-cap/terminal-state review findings resolved; #0083 acceptance and host durability/capacity proof remain open. |
| #0099 | Closed disabled normal upload-origin binding PUT, guarded migration0016 provenance, Worker/auth integration and generated API projection. Private uploads remain valid. Failed/missing Flickr observations are retryable 503 with Retry-After. Independent review passed. |
| #0084 | Documented provider-scoped photo catalog repair lifecycle and isolated Lua proof. Review and four tests passed. New-photo publication-data availability/native Published transition are not host-qualified. |
| #0085 | Proposed advisory upload candidate wire, including all permitted photo classifications and explicit bounded-page restart. Review passed; #0086 acceptance remains separate. |
| #0073 | Fixed read-only stopped-baseline/census/pair observation adapter. Private exact binding/link/generation data participate in drift comparison; public receipts omit them. Review and eighteen focused tests passed; remote use is separate. |

## Verification and boundaries

- Complete frozen offline Python/Lua suite: **406 passed**. The real bootstrap
  template was corrected to include the new disabled flag; earlier bootstrap
  failures are resolved, not ignored.
- Combined offline backend/native-emulator suite: **269 passed** under exact
  Node 24.22.0 and uv 0.12.5, including nested test processes. An earlier run
  used machine uv 0.13.1 in nested subprocesses and failed before those runtime
  cases could execute; the declared toolchain was restored for the passing run.
- Native TypeScript 7, generated API equality, focused Ruff/format and Pyright
  checks passed. Nineteen upload-binding core/Worker tests include authentication,
  paused unrelated features, private proof, idempotency, rollback and races.
- Proposed contracts remain Proposed. Exact host, abrupt-stop, restore/copy,
  capacity, hosted storage and final release qualifications retain their gates.
- The new upload binding flag defaults to `0`. No production migration,
  capability activation, real upload, album/group write or desktop action occurred.
- All 113 open FGA cards were verified P3 after Terry confirmed the localswim
  owner's deployment. The 31 Completed records and all relationships remained
  unchanged. No shared localswim code was changed in this batch.

The rolling implementation-to-independent-review preference is recorded in
global and both FGA project AGENTS. Parent/subagent messages remain summarized.
Detailed private logs stay outside tracked evidence. Owner-selected trial pair
identifiers remain private and do not need to be supplied again.
