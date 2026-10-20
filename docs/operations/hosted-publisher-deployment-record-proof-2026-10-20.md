# Prospective deployment acknowledgement and exact-record proof

Status: Accepted scoped qualification contract. Terry Ott explicitly approved
#0228 on 2026-10-20. This supplements the [accepted hosted provider strategy](hosted-publisher-provider-strategy-2026-10-17.md)
for synthetic hosted publisher qualification. It changes no production
architecture and grants no provider action or positive qualification.

## Additional response branch

The existing strict complete-POST validator remains controlling. Only a
successful, once-unwrapped ordinary object with exactly `{id}` selects the new
branch. Its ID must pass the existing lowercase, hyphenated, nonzero UUID
validator and must not have appeared among any earlier acknowledged deployment
IDs in the same finite provider session. Local no-reuse establishes no provider
freshness or administrator-fencing guarantee.

Deployment intent is consumed before the single POST. The ID-only acknowledgement
is provisional within that pending operation. Before success or terminal unknown,
admit at most one GET under the same account and exact owned script name, at
`/workers/scripts/{owned-name}/deployments/{acknowledged-id}`. Use the shared
transport, cumulative budgets, request hooks and distinct `:record` journal key.
Admission failure stops unknown. A terminal unknown permits no later request.

Other partial objects, extra keys, contradictory supplied fields, malformed
complete responses, invalid IDs, failed or lost responses never select the
fallback. There is no repair, second POST, polling, retry, alternate path/ID,
name discovery, list adoption, or resumed read after interruption.

## Required proof

The exact GET must return a successful complete Deployment with the identical
acknowledged ID, timezone-aware `created_on`, `strategy=percentage`, and exactly
one allocation: the verified version UUID at 100 percent. Apply the original
complete validator; never fill fields from expectations, local clocks or metadata.
Keep version/module/configuration/D1 checks and immutable Worker-ID/name
observations around the POST/GET seam. The separate bounded current-deployment
list comparison remains mandatory: a historical GET does not prove active service.

Register or return the original usable receipt only after the complete proof,
post-identity observation, all windows and durable provenance succeed. The receipt
projection stays `{id, workerId, versionId, created_on}`. An acknowledgement alone
cannot authorize binding, endpoint enablement, expanded ownership or disposal.

## Time and authority

Preserve exact GET `created_on` verbatim, including offset and fractional spelling.
Parse only for validation and comparison. Its asserted instant must satisfy
`case.starts_at <= created_on < min(case.expires_at, plan.expires_at)`. No offset
inference, skew allowance, rounding, repair or fallback is permitted. This checks
the provider's assertion and proves neither clock accuracy nor physical timing.

Separately capture local POST admission/start, POST response observation, exact
GET admission/start and exact GET response observation. Each lies within the
intersection of the original case, plan dispatch and effective execution-grant
windows. Require nondecreasing POST-then-GET observations; unavailable observations
or reversal fail closed. Reject known invalid observations before admitting GET,
and recheck after durable reservation. Recheck stop, authority, case and monotonic
lifecycle deadlines after GET and immediately before receipt registration.
Persistence consumes those original windows. There is no completion grace period,
cleanup extension or relaxation of request/socket/overall deadlines.

Do not require provider creation time between local POST start and end. No
cross-clock bound, immediate read-after-create, immutable-field or external
administrator exclusion guarantee is inferred. Missing, incomplete or mismatched
immediate readback stops without retry. The accepted exclusive finite-owner
assumption remains controlling.

## Closed private provenance

Private proof kind is `id-only-exact-record-v1`; complete POST operation receipts
use `complete-post-v1`. The closed record proof schema contains exactly:

- `proofKind`, `planDigest`, `scenario`, `operationRef`;
- `postRequestRef`, `recordRequestRef`, `versionReadbackRef`,
  `beforeIdentityRef`, `afterIdentityRef`;
- `accountId`, `workerName`, `workerId`, `versionId`, `moduleSha2_256`, `databaseId`;
- `acknowledgedId`, `returnedId`, `providerCreatedOn`;
- `postStartedAt`, `postResponseAt`, `recordStartedAt`, `recordResponseAt`.

The operator derives bindings from its canonical plan, acknowledged creation
receipts and verified version. Both exact request journal entries must be complete
and successful. `proof:{operation-key}` is durably sealed before receipt
registration. The completed operation retains `proofKind` and `proofRef`, binding
the private proof to that operation. Its immutable completion records remote proof
facts; it does not by itself establish usable publication. After the final
operation sync, the operator rechecks the original case/plan/grant/lifecycle/stop
bounds and observation order. Only then, without another journal write or I/O,
does it mark the operation published in the current operator instance and register/return
the usable receipt. A successful final sync that crosses a governing boundary
therefore fails closed. The provider is closed and the candidate discarded; a
separate `publication:{operation-key}` unknown record preserves that failure without
rewriting the completed operation. The in-memory close/stop/discard happens before
any failure-audit read or write; unavailable audit storage cannot reopen dispatch
or publication. A failed final write leaves operation unknown.

Binding, deployment verification and cleanup require this operator-instance publication
gate for exact-record proof and explicitly recognize only `complete-post-v1` or
`id-only-exact-record-v1`; absent, malformed or unrecognized proof kinds fail closed.
A new operator instance, including one in the same OS process, cannot prove that its predecessor
passed the final live fence, even when operation/proof/binding records are complete.
It must not adopt that deployment receipt or replay the operation. Original exact
Worker creation receipts still permit their existing reviewed cleanup; D1 remains
retained when that binding cannot qualify. Successful publication in the same operator instance
retains the original cleanup route. No proof record with unknown operation, missing
publication gate or publication failure authorizes a usable receipt. Never persist arbitrary provider
objects, messages, annotations, email, keys or response prose. Public diagnostics
remain closed presence/type/status projections.

## Failure, cleanup and finite cost

Failed admission, timeout, lost response, 404, invalid or mismatched record,
identity drift, window/stop failure or persistence failure retains consumed intent
and the shared unknown latch. Future runs do not reuse operation or resource
identity to improve evidence. Historical unknowns remain unknown after cleanup.
Original exact resource receipts, independent cleanup review and accepted
synthetic disposal conditions remain required. Ineligible D1 bindings stay retained;
unknown SQL/deployment settlement remains separate from disposal.

At most one extra GET in each of four cases adds four calls and zero mutations:
the nominal recipe including its existing cleanup stages changes from 248/144 to
252/144 under unchanged 256-call/160-mutation caps. Four calls and sixteen mutations
are nominal headroom, not retries or an all-failure cleanup guarantee. Byte caps,
per-request reservation, SQL/client limits, cumulative ledger, windows and separate
issuer accounting remain unchanged. Each fresh concrete packet must rederive
success and failure/cleanup request, byte and elapsed capacity against actual
source. A full response reservation is still required before each request.

## Source and qualification boundary

This source contract authorizes implementation, meaningful positive/hostile tests
and independent nonauthor review only. A new concrete packet must bind accepted
source to new identities, current grant/custody, exact resources, windows,
cumulative budgets and cleanup authority, and pass its existing independent
packet/launch gates. No routine additional live-approval gate is created; no spent
attempt, credential or historical record is revived.

Provider reference contracts: [create deployment](https://developers.cloudflare.com/api/resources/workers/subresources/scripts/subresources/deployments/methods/create/),
[exact deployment GET](https://developers.cloudflare.com/api/resources/workers/subresources/scripts/subresources/deployments/methods/get/),
and [deployment list](https://developers.cloudflare.com/api/resources/workers/subresources/scripts/subresources/deployments/methods/list/).
These links establish API shapes, not stronger timing, consistency or fencing guarantees.
