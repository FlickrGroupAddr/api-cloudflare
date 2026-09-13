# Production dispatcher integration checkpoint

Date: 2026-09-13

Status: Local implementation checks passed. Full production conformance remains
incomplete and requires the outstanding Plugin Code rotation decision. Real
Flickr group adds remain disabled in the deployment template.

This advances the earlier [release preparation checkpoint](2026-09-13-release-preparation.md).
Its historical evidence remains unchanged; the current migration head is now
`0009_dispatch_policy.sql` and the current archive inventory covers 32 tables.

## Implementation

The production `PartitionWorker` now receives bounded private hints and alarms
and invokes the same D1 claim/attempt/recovery path. The ordinary scheduled
sweep publishes hints to that class. Durable Object storage retains only
advisory wake metadata; D1 owns every intent, lease, attempt and permanent
block. A paused deployment setting prevents dispatch. One terminal head yields
before the next head, and lost hints retain D1 due work.

The FGA group-submission worker selects the currently verified native grant,
rejects a changed owner/revision/generation or lifecycle pause, and uses the
signed transport prepared before final marker I/O. Immediately before
moderation it also verifies that more than 30 seconds remain in the lease and
invocation budget. The final D1 marker checks the exact active reservation as
well as the existing lease/head/link/gate/block fences. A proven expired
non-handoff retains the marker but removes that non-dispatched operation from
the intent's add-dispatch count.

The D1 reservation allocator atomically charges all three operations before
membership. Its initial private dispatcher budget is 60 operation slots per
60-second window. Scope and expiry checks prevent stale leases and changed
windows from authorizing operations. Proven-unused capacity is refunded once;
an unconfirmed refund remains conservatively charged until expiry. Tests cover
real D1 contention for the last two complete reservations, rollback and a late
refund that cannot decrement a successor window. Other Flickr-reading paths
still need final application-key budget integration in the full release work.

The complete documented add-result classifier preserves code 6/7 and uncertain
permanent blocks. Explicit temporary failures keep the FIFO head with bounded
exponential jitter: a 5-second initial ceiling, capped at 5 minutes, with the
actual delay in the upper half of its window. Counters remain durable; a
transient outage does not silently discard an accepted intent. Code 5 retains
a throttled head with a 24-hour lower bound. Documented photo/group/policy
failures become terminal attention states. Credential and shared configuration
faults become terminal attention states and pause their scope in the result
transaction. Unknown codes block the pair and pause deployment. A definitive
current-grant rejection also schedules only the matching native retirement.
No path clears a protected pair or offers resubmission.

The new migration preserves historical resolution rows while expanding result
metadata, shared rate reservations and append-only gate events. A separate
file-backed test injects failure after the migration and verifies rollback of
both data and schema, then verifies a successful migration retains the original
resolution, first block evidence and guards. The current-schema archive still
requires stopped writers and a new unexposed target. Its contents include
private authentication/CSRF state and belong outside Git and logs.

## Validation and limits

The complete local regression passed 82 Node tests and 95 Python tests.
TypeScript, Ruff, Pyright and generated API checks passed. The actual optimized
production Worker/class ran with local workerd/D1 and native secret bindings;
its controlled outbound adapter recomputed OAuth signatures from the actual
wire URLs/bodies. Runtime scenarios covered hints, sweeps, permanent suppression,
temporary and terminal results, concurrent reservations, group throttling and
correlated native retirement. No real Flickr request was sent.

The current shared core also passed all 84 bounded compiled crash checks.
All six existing crash mutations and the separate deferred-preparation mutation
were detected, with passing controls and unchanged working sources. The six
crash mutations now run in copied workspaces rather than editing the checkout.
Local fixture teardown was confirmed. See the [sanitized evidence](../evidence/production-dispatch-integration-2026-09-13.json).

The D1 API refused `sqlite_version()`. Initial optional provenance capture
therefore failed, followed by a package-location correction; the final report
records the engine version as unavailable and identifies the installed
Miniflare version and artifact digest. It does not substitute the wrapper's
version for SQLite's. The requested compatibility date is 2026-09-11 and the
local emulator date is 2026-07-30. This is not hosted-runtime or full-release
provenance; the production verifier continues to refuse absent/incomplete
production evidence.

## Required owner decision and continuation

The accepted fail-polite gate includes rotation in `FP-BLOCK-005`, and accepted
ADR 0019 requires rotation conformance before deployment. Accepted ADR 0040
leaves the replacement FGA User API rotation routes unresolved. The existing
[ADR 0049 proposal](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/decisions/0049-use-plugin-code-rotation-candidate-resources.md)
is still **Proposed**. Implementing it as accepted policy would invent approval.

Recommendation: accept ADR 0049's subordinate rotation-candidate resources.
It adds one Plugin Code detail GET, one candidate-creation POST, and one
candidate PATCH for completion or cancellation while preserving the already
accepted one-current/one-pending state machine, one-time reveal and revisioned
confirmation. It introduces no second credential protocol or force-resubmit
path. Upon acceptance, update the canonical lifecycle/allowlist/wire projection
and implement those actual authenticated paths before testing the bypass case.

The remaining release work includes those credential lifecycle routes, the
accepted read-only status paths and bypass matrix, complete process/deployment
stop adapters, hosted current-schema restore and post-backup reconciliation,
protocol/classifier repair evidence before resuming a tripped deployment gate,
and the complete 56-case/28-mutation runner and CI promotion wiring. The existing
`release:verify` command verifies evidence; it does not execute that suite.
Its successful unit tests cannot be called a production conformance pass.
The [DNS/account handoff](../operations/fga-domain-account-move.md) remains a
separate production prerequisite; the later registrar transfer does not block
that DNS move. No AWS service was selected or provisioned.
