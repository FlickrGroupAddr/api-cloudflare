# Prospective integer status admission source

Date: 2026-10-23

Status: source implementation and local synthetic verification; independent
review and managed D1 qualification remain separate gates.

Authority: accepted architecture
[ADR0065](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/decisions/0065-accept-prospective-integer-accounting-and-no-real-profile.md)
and its
[prospective integer accounting contract](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/prospective-integer-accounting-and-state-profile.md).
The [queue-status contract](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/queue-status-api.md)
continues to own status identities, rates, projection and failures.

## Source behavior

`admitStatusRead` in `src/submission_status.ts` uses the shared
`src/quota_credit.ts` builders. One D1 batch samples and validates a database
clock, validates and charges the `(family, subject_id)` integer bucket, checks
the deployment sliding window, records the status event and removes its scratch
guards and clock. Installation and administrator session families remain
independent. Capacity is 100,000,000 credits; each admission costs 5,000,000.

The shared bounded integer formula retains fractional accrual, saturates before
addition, and never decreases a stored watermark. Equal or reversed clocks may
spend existing credits but add no refill. All subject and deployment changes
roll back if any batch statement refuses or fails. The deployment limit remains
600 events with `created_at_us > sampled_clock - 600000000`; future events count
conservatively.

Only the shared specifically named `quota_credit_exhausted` CHECK maps to generic
`429 status_rate_limited`. Clock, state, schema, unexpected CHECK and unknown
acknowledgement failures map to `503 status_unavailable`. Both retain no-store
responses and coarse `Retry-After: 5`. Lost success acknowledgement can spend
capacity, but the caller does not proceed to the status projection, retry, or
refund. Confirmed admission still precedes projection/domain validation and a
later failure does not undo its cost.

`cleanupStatusReads` retains bounded deletion of at most 1,000 status events older
than the strict existing cleanup boundary. Its database clock and deletion run
in one batch. **Status buckets have no expiry and are never deleted by this
cleanup**, including after 24 hours. No historical migration is rewritten.

## Exact prospective fixture and compatibility

Local tests explicitly overlay `tests/integer_quota_fixture.sql` into synthetic
databases after applying historical migrations. The shared fixture version is
`fga-prospective-integer-quota-v1`, with UTF-8/LF SHA2-256:

`ddcd31e0d3277559131e8b063f2dd5abbed8a304e33a8fcfdce352cac92b6c32`.

This source requires the prospective credit columns and quota scratch schema.
The unchanged historical migration head still defines REAL `tokens` buckets
and lacks that scratch schema. A migration-only status request therefore fails
closed as unavailable; tests explicitly exercise that incompatibility. The
synthetic overlay is not an installable migration, deployed-state census,
old-balance conversion, compatibility fallback, or authority to deploy.

## Local verification

Node.js 24.22.0 and the existing native TypeScript 7.0.2 compiler are pinned;
no toolchain or dependency update was made. Required local commands:

```text
node --test tests/submission_status.test.mjs tests/submission_status_ui.test.mjs tests/integer_quota.test.mjs
node_modules/@typescript/typescript-win32-x64/lib/tsc.exe --noEmit
```

Result: all 39 focused tests passed; native `tsc --noEmit` passed.

Focused cases cover burst 20, a one-credit-short refusal and exact refill,
tiny accrual, saturation at signed64 maximum, equal/reversed clocks, hidden-rowid
preservation, family/subject isolation, exact deployment-window capacity and
boundary, future events, invalid clock/state, later-statement rollback, unknown
CHECK/schema faults, lost acknowledgement and event-only cleanup. Existing route
projection, pagination, domain non-mutation and UI presentation tests continue
against the explicit prospective synthetic fixture. Shared quota tests supply
the independent arbitrary-precision rational oracle.

These checks establish exercised local source behavior only. Actual D1
last-credit/global-window concurrency, complete no-REAL guards and readers,
schema transition/recovery, writer closure, provider qualification, deployment
and the prospective all-store preservation gate remain unpassed. No actual
state/provider, credential, native or live execution action is included.

## Independent source review

Fresh independent High review passed 39 focused tests, native compilation and
the affected local runtime suites. An independent 1,800-step BigInt integration
oracle and every admission/cleanup fault position passed. Primary reproduced
76 combined auth/status tests and 12 local runtime tests; all passed.
These results do not establish managed D1 concurrency or actual schema fit.
