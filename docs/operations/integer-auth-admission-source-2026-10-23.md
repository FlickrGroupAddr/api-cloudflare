# Prospective integer authentication admission source

Date: 2026-10-23

Status: Source implementation and local synthetic verification. Independent
review and actual qualification are separate gates. This is not a migration,
deployment, old-balance conversion, or a positive hosted-conformance result.

Authority: accepted architecture [ADR0065](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/decisions/0065-accept-prospective-integer-accounting-and-no-real-profile.md)
and its [prospective integer accounting contract](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/prospective-integer-accounting-and-state-profile.md),
with the retained [ADR0055 admission boundary](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/decisions/0055-keep-authentication-admission-bookkeeping-in-d1.md).
The shared fixed integer operations are in [`quota_credit.ts`](../../src/quota_credit.ts).

## Source behavior

[`auth_admission.ts`](../../src/auth_admission.ts) now samples and validates one
database clock inside the complete admission batch. Shared fixed SQL owns the
credit invariant, refill, charge, and nondecreasing watermark. The remaining
source/deployment invalid-or-inflight and route-window checks, event insertion,
and scratch removal use the same transaction and sampled clock. A later refusal
or statement fault rolls back all earlier changes, including a new bucket.

Normalized IPv4 and IPv6 `/64` HMAC keys retain their privacy boundary. Login
and hashed login-start buckets remain separate. Callbacks retain the existing
credit and route-window exemption while sharing invalid-or-inflight limits.
The five-live-OAuth cap remains with canonical transaction creation in
[`flickr_oauth.ts`](../../src/flickr_oauth.ts); this source does not create a
second cap or admission authority.

Only the shared named exhaustion constraint maps to `rate_limited`. Clock,
state, schema, unrelated-constraint, and acknowledgement faults map to
`admission_unavailable`. Existing HTTP handling retains generic no-store 429/503
responses and the coarse 120-second Retry-After for exhaustion. An unconfirmed
admission cannot reach the parser, JWT validation, or JWKS work; it receives no
automatic retry or refund. Confirmed admission remains conservatively charged
if later validation fails.

`finishAuthentication` changes only the matching invalid-or-inflight flag.
It never alters the event time or bucket watermark. Ordinary cleanup now uses
one validated clock for its complete batch and retains the original 24-hour
event/bucket expiry basis, existing bounded deletion, Google-transaction
retention, and administrative-session retention. A denied request never
refreshes a stale bucket. A successful ordinary request may advance its
watermark as the accepted formula permits. No transition or re-aging path is
introduced, and status buckets are not deleted by authentication cleanup.

## Local evidence and release limits

The synthetic overlay uses the unchanged
[`integer_quota_fixture.sql`](../../tests/integer_quota_fixture.sql), UTF-8/LF
SHA2-256 `ddcd31e0d3277559131e8b063f2dd5abbed8a304e33a8fcfdce352cac92b6c32`.
Historical migrations remain unchanged. Existing auth unit tests and the local
compiled-Worker harness provision this prospective fixture explicitly; the
default historical schema is not silently rewritten.

- Node.js 24.22.0 and pinned TypeScript 7.0.2 native compiler: `tsc --noEmit`
  passed.
- 58 tests passed across `auth_admission_integer`, `admin_core`, `integer_quota`,
  `flickr_oauth`, `google_identity`, and `session_inventory` suites.
- Focused auth tests exercise burst, one-credit boundary, retained fractional
  refill, equal/backward and signed64-maximum time, both namespaces, callback
  exemptions, independent-budget rollback, window boundaries/future events,
  completion, original expiry/cleanup, statement faults, corrupt state/clock,
  unrelated constraints, and acknowledgement loss.
- Direct HTTP tests verify the generic no-store errors and parser/JWKS closure.
  The historical untransitioned schema explicitly refuses admission without
  changing its quota facts.
- The primary separately verified 12 tests in `admin_runtime`,
  `plugin_codes_runtime`, and `dispatch_runtime` against the explicit prospective
  synthetic overlay. These are local compiled-Worker tests.

These tests exercise source SQL in local SQLite and existing synthetic
authentication dependencies. They do not prove managed D1 last-credit/global
window serializability, actual deployed schema/types, complete no-REAL coverage,
an E/R/X transition, recovery qualification, or actual all-store preservation.
This source cannot be released against an untransitioned historical REAL schema.

## Independent source review

Fresh independent High review passed the affected suite and native compiler,
864 combined boundary cases and eight fault/cleanup probes. Primary integration
reproduced 76 combined auth/status tests and 12 local runtime tests; all passed.
These are independent local source checks, not managed qualification.
