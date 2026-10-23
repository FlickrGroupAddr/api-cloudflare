# Prospective positional D1 generation successor

Date: 2026-10-23

Status: Accepted by Terry for prospective source implementation and independent
review only, in the #0250 decision returned this turn.

## Exact exception to the unchanged-byte contract

The [accepted exact-count contract](pmb1-exact-change-receipt-successor-2026-10-23.md)
continues to control except for this separately selected source variant.
For each historical fixed close/reopen UPDATE, replace only its two literal
`:expected_generation` tokens with the same ordered `?1` parameter. Bind exactly
one canonical positive signed-int64 decimal TEXT value to that first slot.
Preserve every other byte, predicate and effect. Do not substitute SQL literals,
two anonymous slots, numeric conversion or caller-selected SQL.

Give this variant its own protocol identifier, source pins and exact request/
receipt manifests. Keep the historical SQL files, named-source protocol,
`single_fixed_update`, default behavior, source pins and old evidence unchanged.
The new source bytes cannot inherit qualification from historical evidence.

## Preserved requirements and tradeoff

Retain the exact-count SELECT on the same connection/transaction, separate full
PRIMARY schema/row readback, source/target/custody binding, root generation
headroom, durable single-use dispatch and reconciliation, fixed finite windows
and budgets, uncertain outcomes and no replay. No bound or resource is added.

Cloudflare's prepared-statement documentation supports positional parameters
and describes named parameters as future support. The alternative was retaining
the literal named-source contract while leaving native dispatch unavailable
until a supported exact-byte path is established. Terry accepted the narrow
positional source variant. Its cost is separate source/request pins and fresh
exact qualification; model equivalence alone does not prove managed semantics.

Production dispatch remains disabled while the exact selected native connection,
ordering, transaction/rollback, commit and no-interleaving basis is missing.
Worker API documentation does not establish REST execution semantics. Source
acceptance is not a qualified receipt, current grant or permission to execute.

This decision grants no credential/account/provider/native access, deployment,
resource, migration, live test, cleanup, retry, replay or positive qualification.
All unamended contract and later current-fact/action gates remain controlling.

## Evidence

- Terry accepted the exact #0250 choice on 2026-10-23 in response to the reviewed
  source-only question. No broader owner rationale is inferred.
- Independent review verified exactly two token replacements per UPDATE, all
  other bytes unchanged, and 30 invented SQLite equivalence cases. Those are
  model results, not native D1 qualification.
- [Cloudflare prepared-statement guidance](https://developers.cloudflare.com/d1/worker-api/prepared-statements/)
- [D1 REST query schema](https://developers.cloudflare.com/api/resources/d1/subresources/database/methods/query/)

The original accepted exact-count contract and all historical records remain
unchanged. Independent implementation review and actual qualification are
separate from this owner decision.
