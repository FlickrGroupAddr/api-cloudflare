# Authentication limiter storage and admission ordering

Date: 2026-09-11

Status: ADR 0055 accepted by Terry on 2026-09-12; admission-order clarification
and bounded proof plan complete. Production limiter integration remains pending.

Accepted decision: use the existing D1 database as the sole owner of atomic
source/global quota bookkeeping and canonical OAuth transaction rows. Clarify
that admission precedes creation of application authentication records; the
limiter's own short-lived SQL bookkeeping is permitted during admission. This
avoids a second store and a reservation/compensation protocol across services.

## Authority and approved clarification

The canonical administrative contract requires admission before JWT parsing,
signature validation, FGA database insertion or a request-triggered JWKS refresh.
The accepted browser-session contract creates login-start state only after
admission. The prior wording did not explicitly exempt limiter bookkeeping from "insertion."
[Accepted ADR 0055](https://github.com/FlickrGroupAddr/architecture-design/blob/78240c077d21f9546f3e728a02d234497c63c053/docs/decisions/0055-keep-authentication-admission-bookkeeping-in-d1.md) records that narrow exemption under Terry's explicit approval. The canonical
administrative and browser-session contracts now reference it. The private runtime trust exception in ADR 0051 does
not independently amend admission ordering.

The accepted decision retains the current limits without copying a new canonical table:
see `docs/administrative-control-plane-contract.md`, "Unauthenticated admission
and cost boundary," in the private architecture source. The fixed OAuth live
cap is checked against its canonical initiating/pending/in-flight rows, not a
second count stored in a Durable Object. Callback completion uses its existing
slot. No transaction stays open during Google or Flickr I/O.

## Remaining implementation proof plan

Use fresh isolated local workerd/D1 and hosted D1 fixtures, maintained
Google-authentication interfaces with a controlled JWKS peer, a controlled
Flickr OAuth peer, and a separate observer for external-call and inserted-row
counts. No real Google assertion or Flickr token enters a fixture. Use the
same limiter and authentication entry code as deployment; test helper routes
must not grant admission or bypass the normal transaction.

| Case | Required evidence |
| --- | --- |
| AUTH-LIM-001 | Two immediate source-bucket admissions succeed; the next is refused. Refill follows exactly 5 tokens per 10 minutes with burst 2, using database time and integer arithmetic. |
| AUTH-LIM-002 | Source rotation cannot exceed the deployment's exact 30-per-10-minute sliding window; just-before and exact expiry boundaries are exercised. |
| AUTH-LIM-003 | Race every applicable source/global bucket at one remaining allowance. Exactly the allowed requests enter validation; partial charge or failed admission never creates a session, OAuth/login state or JWKS call. |
| AUTH-LIM-004 | Invalid Google-login and Flickr callback accounting is shared at the accepted 20/source and 120/deployment windows. Include concurrently in-flight validation, malformed input, invalid CSRF, invalid/unknown keys and callback failures. Late classification cannot overshoot the bound. |
| AUTH-LIM-005 | Force a failure after each statement in the admission batch. Observe real rollback, no downstream work and no partial admission authority. |
| AUTH-LIM-006 | Lose the response after a committed charge and kill/recreate the worker. The original request cannot continue on an assumed admission; retries consume ordinary available capacity. No distributed refund or reusable permission token appears. |
| AUTH-LIM-007 | Trusted-edge IPv4 and IPv6 /64 inputs produce stable scoped HMAC keys. Spoofed forwarding headers and missing source/key authority fail closed. SQL, logs and audit contain no raw address, credential, CSRF token or source key leakage. |
| AUTH-LIM-008 | Limiter unavailability returns generic no-store 503 before parsing/verification/JWKS/domain insertion. Limit refusal returns generic no-store 429 with coarse Retry-After and no bucket disclosure. |
| AUTH-LIM-009 | Concurrent recently authenticated OAuth starts create at most five live canonical transactions, including initialization before external request-token work. A sixth start makes no external call. |
| AUTH-LIM-010 | All five existing callbacks can finish while the cap is full. Replayed, expired, foreign or unconfirmed state cannot exchange credentials or create a second grant. |
| AUTH-LIM-011 | Failure and response loss around OAuth row creation, external request-token work and callback consumption leave one bounded five-minute transaction, not orphaned extra slots or an extended expiry. |
| AUTH-LIM-012 | Physical cleanup is delayed, repeated or interrupted. Expired quota/OAuth rows remain unusable; current rows cannot be prematurely reclaimed. Advancing or regressing injected audit wall time does not invent refill. |
| AUTH-LIM-013 | Stop authentication admissions, restore an old database and run recovery. Expired quota/OAuth rows never revive. Do not reopen authentication until current quota authority is reconstructed or the maximum relevant window has elapsed. |
| AUTH-LIM-014 | Observe bounded row growth and cleanup under rotated sources. Retention never exceeds the approved live-row policy; provider Time Travel remains a separately disclosed physical-retention limit. |
| AUTH-LIM-015 | Missing, duplicate or selected-out cases fail the gate. Mutations that split source/global commits, validate before admission, use per-instance counters, ignore in-flight invalid work, move the OAuth cap to an independent counter, or refund an ambiguous commit must fail behavioral assertions. |

The scope includes login-start and recent-reauthentication admission as required
by the accepted session contract; their exact configured policies must be
explicitly mapped before implementation rather than silently borrowing a POST
bucket. The maintained authentication-library choice, detailed route schemas
and the separate Flickr credential lifecycle remain their existing integration
work. No custom JWT, CSRF, signature or cross-service reservation code is
licensed by this plan.

## Failure ownership and implementation constraints

D1 owns short-lived cost accounting and canonical OAuth transactions. Successful
application authentication transitions plus their required audit share the
accepted application transaction. An opaque local correlation ID identifies a
single physical request for diagnostics; it is not client-controlled admission
idempotency. Unknown admission outcome means no expensive downstream work.
Conservative lost capacity may last until the normal window expires.

Use fixed parameterized operations, database-generated times, bounded indexed
window queries and explicit returned rows instead of assuming `meta.changes`
counts only application rows. Capture actual external-call ordering and durable
row absence, not only status codes. Keep detailed synthetic witness data in
private run artifacts and publish allowlisted results/hashes.

The conditional-invalid-budget algorithm must be explicit and tested before
coding the route. The plan deliberately does not hide that issue behind a
post-validation counter increment. It also does not preselect a new reservation
protocol: a candidate must meet the atomic in-flight bounds within the one D1
authority, or return with the concrete unmet requirement.

## Provider evidence and consequences

Cloudflare documents [transactional D1 batches](https://developers.cloudflare.com/d1/worker-api/d1-database/#batch).
Its [rate-limiting binding](https://developers.cloudflare.com/workers/runtime-apis/bindings/rate-limit/)
is location-local and eventually consistent, which does not meet the exact
shared accounting requirement by itself. A separate Durable Object limiter
would add a cross-service failure boundary for the OAuth cap without removing
an identified requirement that one D1 transaction cannot satisfy.

[D1 Time Travel](https://developers.cloudflare.com/d1/reference/time-travel/)
retains historical states beyond 24 hours. The accepted decision treats expiry as
loss of authority plus live-table cleanup, not physical all-version erasure.
Manual exports should omit source-key bookkeeping; restoration must retain a
closed authentication gate until quota recovery is safe. Terry explicitly accepted this limitation on 2026-09-12; it must not be
described as 24-hour physical deletion.

No new production service, dependency, billing resource or AWS fallback was
created for #0015. The deliverable is the scoped architecture clarification
and executable acceptance plan requested by the ticket, not a hosted limiter
conformance claim.

## Approval handoff, 2026-09-12

The owner decision is resolved. The scoped #0015 deliverable is the accepted
clarification and proof plan above. It did not request implementation of a new
authentication subsystem. The production integrations and their full tests
remain with the existing downstream work; no new service or reservation
protocol was added by this approval.
