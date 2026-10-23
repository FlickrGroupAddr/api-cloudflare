# Prospective integer quota source handoff

Date: 2026-10-22. Source/fixture evidence only.

The FGA API backend contains fixed quota statement builders in
[`src/quota_credit.ts`](../../src/quota_credit.ts), under accepted architecture
ADR0065. At the October 22 source handoff, authentication/status writers did not
import this module. The October 23 prospective integrations are recorded in
[authentication](integer-auth-admission-source-2026-10-23.md) and
[status](integer-status-admission-source-2026-10-23.md); they require the prospective
schema and cannot be deployed against the historical REAL schema.
The source does not select a deployed schema or activate a new profile.

Authentication capacity/charge is 240,000,000/120,000,000 microsecond credits;
status capacity/charge is 100,000,000/5,000,000. The helper prepares statements;
it never executes a batch, issues authority, retries, refunds or dispatches work.
The caller must put the single clock sample, all applicable guards and charges,
required events and scratch cleanup in one complete D1 transaction batch.
Only the specifically named exhaustion check denotes ordinary rate exhaustion;
invariant, schema and unknown-acknowledgement failures remain unavailable.

The prospective STRICT schema is an isolated source fixture, not a migration:
[`tests/integer_quota_fixture.sql`](../../tests/integer_quota_fixture.sql).
Version `fga-prospective-integer-quota-v1` and SHA2-256
`ddcd31e0d3277559131e8b063f2dd5abbed8a304e33a8fcfdce352cac92b6c32`
are bound by source and tests. Preserve its UTF-8/LF bytes across Git checkout.

Validation used the existing native TypeScript 7.0.2 compiler and Node v24.22.0
with bundled SQLite 3.53.4. Twenty-one focused tests passed, including 348 independent
rational-oracle cases, signed64 extremes, type/clock refusal, row identity,
shared-clock sampling and complete rollback after a later statement fails.
Reproduce with the pinned compiler's no-emit check and
`node --test tests/integer_quota.test.mjs` in the repository environment.

Independent review identified that SQLite text length and GLOB checks can ignore
a NUL suffix. The clock fraction guard explicitly rejects every NUL before
accepting the canonical text; six additional malformed-fraction cases verify
refusal and atomic rollback while native and ordinary valid fractions still pass.

Local serialized credit attempts are not evidence of hosted D1 serializability.
Complete no-REAL guards/readers, actual schema fit, census, legacy-balance
retirement, E/R/X transition, installation/migration, deployment and all-store
qualification remain separate. Future writer integrations must preserve their
independent budgets, callback/family namespaces, privacy/expiry, generic
no-store 429/503 responses and conservative acknowledgement-loss behavior.
