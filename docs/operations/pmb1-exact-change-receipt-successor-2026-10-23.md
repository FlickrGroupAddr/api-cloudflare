# Prospective exact D1 change-receipt successor

Date: 2026-10-23

Status: Accepted by Terry on 2026-10-23 for bounded prospective source
implementation, independent review and qualification preparation only

## Exact selected source boundary

The accepted PMB-1 contract remains controlling. This narrowly selects a distinct
prospective receipt protocol, `fixed_update_with_exact_count_v1`, rather than
relabeling the historical `single_fixed_update` interface.

One bound operation contains exactly two ordered statements on the same
connection/transaction:

1. The unchanged source-pinned fixed close or reopen UPDATE, with the existing
   canonical signed-int64 generation bound as TEXT.
2. `SELECT CAST(changes() AS TEXT) AS exact_change_count`

No caller chooses SQL, target state, generation, a third statement or ordinary
application work. Preserve the original fixed UPDATE predicates and source pins.
Do not add the optional third in-batch control read; independently requested full
PRIMARY control/schema readback remains mandatory.

This adds one nonmutating SQL statement, ordered-result parsing and response
allocation. Bind the distinct protocol and both exact statements in the source
and request/receipt manifest. Count their actual footprint inside the existing
finite call/query/statement/byte limits; acceptance raises none of those limits.
No new table or resource is part of this choice.

## Count and uncertainty semantics

The SQL function's count concerns the preceding direct mutation on that same
connection; connection-total metadata, trigger work, rows-written estimates or a
later connection's count are not substitutes. Preserve exact decimal TEXT count
parsing. A successful count of exactly one is necessary, never by itself proof
of commit, correct PRIMARY state or lifecycle confirmation. Zero is refusal,
not idempotent success; malformed, missing, late, multiple or uncertain outcomes
cannot confirm an operation or authorize replay.

Preserve durable intent before dispatch, one dispatch, immutable source/target
binding, original generation/headroom, exact fixed windows, retained unknowns,
separate complete PRIMARY schema/row readback and independent reconciliation.
There is no automatic retry, fallback mutation, new generation or reopening.

## Unchanged native proof and action gates

The D1 REST schema accepts batch requests but does not by itself establish the
required ordered same-connection execution, transaction/rollback, commit and
no-interleaving guarantees. Worker API batch documentation cannot silently
qualify a REST path. SQLite tests establish model behavior, not managed behavior.
Those supported native semantics and exact producer/adapter results still need
independent evidence and qualification. Production dispatch remains disabled
while that basis is missing; a JSON field, source hash or owner acceptance cannot
turn it into a qualified receipt.

Terry accepted the independently reviewed bounded source recommendation on
2026-10-23. The alternative was retaining the historical one-statement contract
and write-disabled status pending a supported exact original-protocol receipt.
No additional owner rationale is inferred. This is not a broad PMB-1 waiver and
does not change historical artifacts, contracts or results.

This grants no credential/account/provider/native request, mutation, resource,
migration, deployment, capture, cleanup, run/call budget, replay or positive
qualification. All later exact current-fact, custody, finite-packet and action
gates remain unchanged.

## Primary evidence

- [D1 REST query API](https://developers.cloudflare.com/api/resources/d1/subresources/database/methods/query/)
- [D1 Worker database API](https://developers.cloudflare.com/d1/worker-api/d1-database/)
- [SQLite direct changes](https://sqlite.org/c3ref/changes.html)
- [SQLite SQL functions](https://sqlite.org/lang_corefunc.html)

The independent source review checked this boundary on 2026-10-23. Those sources
explain the capability and evidence limits; they supply no actual run result.
