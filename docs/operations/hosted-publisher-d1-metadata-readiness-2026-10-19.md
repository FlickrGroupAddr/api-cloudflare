# D1 creation metadata readiness

Date: 2026-10-19. Scope: the finite synthetic publisher operator only.

Cloudflare's [D1 create](https://developers.cloudflare.com/api/resources/d1/subresources/database/methods/create/)
and [exact-ID get](https://developers.cloudflare.com/api/resources/d1/subresources/database/methods/get/)
schemas describe `created_at` as an optional ISO8601 string. The adapter accepts
its omission, represents the unavailable provider value as `None`, and never
substitutes a local clock value. A supplied null, invalid type, malformed time or
impossible date is rejected. Valid fractional timestamps retain all supported
precision, up to eighteen fractional digits, for exact window comparisons.

Ownership still requires a successful create acknowledgement with a nonzero
canonical UUID and the exact requested approved name. The private operator
journal records separate local request-start and response-observation times.
Both must fall within the exact case window, in order. Every supplied valid
provider creation timestamp must independently satisfy the original window.
The selected case window is checked before create admission and before and
after each provisioning mutation's durable reservation. Response observation
is captured once in the provider callback before receipt persistence or
optional-field validation; rejected metadata retains that same immutable time.
Four unique creation receipts, exact plan/scenario binding and fresh-empty
verification remain mandatory before migration and execution.

The concrete runtime supports one common case/plan window. Readiness, permit
construction and every dispatch authorization reject differing case starts or
expiries, so its existing final post-connect TLS check fences the same window.
The abstract offline plan schema still permits narrower case schedules; this
does not claim concrete runtime support for them. The prepared ceremony uses
equal windows for all four cases.

Readback always compares UUID/name. A provider creation timestamp retained from
creation must match exactly; omission or drift of that retained timestamp stops
cleanup. When creation omitted it, any timestamp later supplied is validated but
does not replace the original unavailable value or become retroactive evidence.

If optional metadata or a local response window is rejected after successful
UUID/name acknowledgement, the unknown operation retains a closed private
diagnostic: exact acknowledged identity, provider-time validation category,
valid provider time only, and separate local observation bounds. No raw response,
invalid field value or arbitrary provider prose is persisted. This diagnostic is
not a successful creation receipt, positive qualification, cleanup adoption or
permission to repeat a request. Lost/malformed required identity remains unknown.

The controlling accepted [synthetic provider contract](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/proposals/hosted-operator-provider-strategy-2026-10-17.md)
requires the exact successful fresh-D1 creation receipt and UUID in controlled
disposal condition 1. Its separate Worker identity section explicitly requires
the returned Worker creation time; that requirement is unchanged. The finite
operator still enforces durable intents, original finite windows, no replay,
exact binding, exclusive ownership, separate cleanup authority and the accepted
fixture-only disposal sequence. Production flags and production contracts are
unchanged. An unavailable historical response body cannot establish a historical
root cause from this compatibility finding.

Offline provider, plan and lifecycle fixtures exercise omitted, null, malformed,
fractional, drifted, out-of-window and unknown acknowledgements, plus preserved
empty-database and ordered-disposal gates. Hosted qualification requires a fresh
committed source closure, independently reviewed exact private packet, current
grant, genuine applicable authority and separate review of actual outcomes.
