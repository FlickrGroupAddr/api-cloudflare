# Release preparation checkpoint

Date: 2026-09-13

Status: Bounded local checks passed. Full production fail-polite conformance
remains incomplete; this checkpoint does not permit live Flickr group adds.

The shared attempt path now requires an already prepared add request before
its final dispatch-marker transaction. The fixture follows the same interface.
The new signed transport candidate uses the existing OAuth library, a fixed
Flickr endpoint, complete bounded membership/moderation validation, exact
attempt/pair binding and a single materialized POST. Its handoff performs no
signing, secret lookup, request construction or body serialization. Invalid
credentials, expiry, a refused marker and an uncertain POST result retain the
existing fail-polite outcomes. The transport is not yet wired into a released
production coordinator.

The current-schema archive codec derives its entire table/guard inventory from
all production migrations. Unlike the historical scoped coordination archive,
it rejects missing, extra or changed schema objects. Exact SQL literals preserve
64-bit integers and NUL-bearing text before JSON transport; rows restore before
allocation/audit triggers. Independent SQLite files round-trip all 28 current
domain tables, including revoked administrative sessions, consumed Google
login transactions and pending Flickr OAuth/lifecycle retirement. This is local
codec evidence, not a hosted D1 restore or reconciliation of post-backup facts.
The caller must stop writers and use an unexposed restore target. Restoration
must still reconcile later protection/revocation facts and current native secret
generations before resuming.

`npm run release:inventory` reads the accepted 56-case inventory and lists 28
expanded mutation variants. The mutation mapping is pinned to the reviewed
contract digest and refuses an unreviewed contract change. `npm run release:verify`
is a promotion verifier, not a test runner. It rejects absent infrastructure,
partial historical probes, omitted/duplicate/skipped/failed IDs, absent crash
entry paths or block seeds, inadequate mutations and mismatched artifact,
configuration, source commit or migration identities. It requires full
production evidence and never substitutes local checks. The complete case
runner, production integration and CI promotion wiring remain work to finish.

Validation at this checkpoint: 68 Node tests, 94 Python tests, TypeScript, Ruff,
Pyright and generated API checks passed. The compiled local workerd/D1 crash
proof passed 84 checks with cleanup confirmed. An isolated mutation that moved
request preparation after marker commit failed the intended behavioral tests;
its baseline passed and working sources remained unchanged. The release
verifier returned failure when production evidence was absent. See the
[sanitized evidence](../evidence/release-preparation-2026-09-13.json).

Remaining integration includes the real coordinator, shared rate reservations,
bounded retry/result policy, complete authenticated status/bypass paths, real
process/deployment stop adapters, hosted current-schema restore/reconciliation,
and every required case and mutation against the exact release artifact. The
[DNS/account handoff](../operations/fga-domain-account-move.md) also remains a
production infrastructure prerequisite. The separate registrar-transfer wait
is not a prerequisite to moving DNS between Cloudflare accounts.

Primary method and runtime references checked for this work:
[Flickr group add](https://www.flickr.com/services/api/flickr.groups.pools.add.html),
[Workers performance/timers](https://developers.cloudflare.com/workers/runtime-apis/performance/),
and the [accepted conformance contract](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/testing/fail-polite-worker-database-conformance.md).
