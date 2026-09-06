# Native runtime permission evidence

Date: 2026-09-06

Status: Runtime capability investigation complete; storage-boundary decision
required from Terry. Production storage adoption and full ticket #0007
migration/backup/restore conformance remain outstanding.

## Finding

The tested direct D1 binding and SQLite-backed Durable Object ownership patterns
fail the accepted requirement that ordinary application runtimes cannot alter
or erase permanent suppression and audit records. Their SQL guards rejected
ordinary edits, but the runtimes could remove the guards, change records, and
drop tables. The owning Durable Object could also erase its entire storage.

This is observed hosted behavior, not an inference from missing PostgreSQL syntax.
The [hosted report][hosted] records 57 cases at compatibility date 2026-09-06.
The [local report][local] is a separately dated emulator comparison. Each report
contains the precise source/bundle/lockfile fingerprints and tool versions.

| Observation | Worker D1 binding | Owning Durable Object |
| --- | --- | --- |
| Read and new-record insert controls | 4 allowed | 4 allowed |
| Update/delete/replace/upsert/cascade and CHECK/FK controls | 14 denied; original records retained | 14 denied; original records retained |
| Remove guard, then rewrite/delete a record | 4 successful forbidden changes | 4 successful forbidden changes |
| Drop or rename a protected table | 4 successful forbidden changes | 4 successful forbidden changes |
| Disable CHECK enforcement and write an invalid value | 2 successful forbidden changes | 2 successful forbidden changes |
| Erase all object storage | Not a D1 binding method | 1 successful forbidden change |
| Total collected cases | 28 | 29 |

Both runs recorded 21 forbidden changes and no inconclusive attack cases. Engine
version retrieval was unavailable through both tested runtime SQL interfaces;
the reports preserve that limitation instead of inventing an engine version.
A successful evidence-collection command does not mean the protection property
passed. The reports explicitly set `productionConformance: false`.

## What was tested

The [probe and operating procedure][probe] create a fresh synthetic D1 database,
Worker and SQLite-backed Durable Object namespace. The operator provisions D1
fixtures, and the attack statements then execute through the deployed Worker's
ordinary D1 binding. Object-local fixture initialization and attacks both execute
inside the owning Durable Object runtime.

The endpoint accepts only an authenticated, fixed sequence of operations, checks
the fresh fixture identity, and consumes bounded phases through a database
compare-and-set. It exposes no caller-selected SQL. The authority being measured
belongs to code holding the storage capability. This is not evidence of a
production API vulnerability or an unauthenticated remote delete route.

Each case has its own initially protected table and before/after observations.
The probe preserves the seed through ordinary guard tests before attempting
schema or storage-level changes. It exercises suppression-like and audit-like
records without real Flickr identifiers, photographs, sessions, or credentials.
It makes no Flickr call.

The collector verifies every expected case ID, baseline, guard result and
claimed state change. It refuses missing/duplicate phases, source changes during
execution, production-conformance claims and credential material in evidence.
The hosted deployment identity was unchanged before and after collection.

## Controlling requirement and scope

The accepted [worker persistence contract][worker] requires application roles
that can select/insert permanent blocks but cannot update/delete them or change
their table definition. [Fail-polite conformance][fail-polite] includes direct
runtime database writes in `FP-BLOCK-009`; client-route checks alone do not meet
that boundary. [ADR 0050][adr50] preserves these semantics while authorizing
native evaluation.

The probe isolates that requirement. It does not instantiate the complete
production schema, all application identities, a fail-polite worker, batch
admission, stale-worker fencing, or backup recovery. It supplies concrete
counterexamples for the direct capabilities tested.

A different native architecture could remove raw SQL bindings from some FGA
components. That is a separate security boundary to evaluate. A private
method-limited storage Worker or Durable Object still has an owning runtime
with broader capabilities; it must not silently be reclassified as an exempt
migration principal. Whether such a service satisfies the intended contract
needs explicit architecture review.

## Decision for Terry

Recommend preserving the accepted runtime protection boundary and proceeding
with the existing RDS fallback's scoped evaluation. Keep Cloudflare compute
selected. A custom native privilege service would put new application code at
the exact boundary that must preserve permanent moderator-protection memory.

| Approach | Security and maintenance consequence | Disposition |
| --- | --- | --- |
| Direct D1 binding plus SQL guards | Ordinary code with the binding can dismantle its enforcement and alter/delete protected state. | Tested failure of the current requirement. |
| Owning aggregate Durable Object plus SQL guards | Object isolation limits other objects' access, but the owning runtime retains schema and whole-storage erasure capabilities. | Tested failure for the owning-runtime boundary. |
| Separate native storage service with narrow operations | Can restrict callers, while its own trusted code owns the broader capability. Requires a reviewed method/identity boundary, migration isolation, bypass tests and an explicit interpretation or amendment of the accepted runtime rule. | No such service was implemented or accepted. This is additional security code and operational coupling for Terry to maintain. |
| Existing RDS PostgreSQL fallback | Conventional database roles can separate runtime DML from table ownership and migration authority. The real role/schema design must also prevent destructive cascades and privileged-function bypasses. | Recommended next evaluation under accepted ADRs 0046/0050; no RDS connection or mutation occurred in this probe. |

[ADR 0046][adr46] records the existing PostgreSQL 18.6 target and three years of
prepaid compute. That makes reusing the instance a concrete cost advantage,
without establishing a zero incremental bill. The fallback still needs measured
Cloudflare connectivity/pooling compatibility, narrow network access, verified
TLS, fresh authorization/transaction reads, separate runtime and maintenance
identities, backups/restore, latency and incremental cost evidence. Unrestricted
PostgreSQL ingress is prohibited. Implementation #0010 owns the complete
fallback evidence record before adoption.

The choice is therefore whether to retain the strict boundary and advance the
already-authorized RDS fallback evaluation, or ask for a separately reviewed
native storage-service boundary. This report accepts neither a security
exception nor a production deployment. The full #0007 ticket belongs in
**Needs Terry** at this decision point, rather than being marked complete after
only its runtime-permission inquiry.

## Remaining gates

Migration, export, point-in-time restoration, protected-history recovery and
native audit-precision conformance were not completed by this permission probe.
The destructive fixture operations are not migration or recovery passes.

The managed immutable-secret-version choice remains with #0009. The deployed
monotonic freshness question remains with #0013; an RDS database does not change
Worker timer behavior. #0014 retains the native audit precision question.
Routing and the read-only installation slice remain independently gated; their
actual FGA LrC plug-in HTTP client also needs edge compatibility evidence.

## Operational evidence and cleanup

The first hosted attempt deployed successfully but stopped before collecting
permission cases because Python's default User-Agent received Cloudflare error
1010. A truthful application User-Agent resolved the rejection. No browser
identity was impersonated and no Cloudflare security setting was changed.
[Cloudflare documents the browser-signature cause][error1010].

The controller deletes only its generated Worker/database identities and sends
`force=false` for Worker deletion. Worker absence and D1 absence were verified.
The [cleanup audit][cleanup] additionally checked the account's paginated Durable
Object namespace inventory for the probe script identities and found none left.
Its namespace query used the documented
[List Namespaces API][namespaces], with credentials only in memory.

Credential review found three private debug-log copies emitted by Wrangler's
`auth token --json` command during the task. Those exact copies were redacted;
the canonical login and unrelated logs were preserved. The controller now
suppresses vendor disk logs, keeps sanitization enabled and retains its own
bounded private diagnostics. A synthetic-token execution proved that the token
command can return data in memory without writing a debug log.

The [toolchain audit][probe] records TS7 7.0.2's native Go compiler, Node LTS,
the subsequent Node 24.20.0 upgrade, retained npm 12.0.2, the stable
Wrangler/Miniflare pairing, vendor prerelease helper exceptions, and the local
2026-08-06 versus hosted 2026-09-06 compatibility dates. No machine-wide Node
installation was changed during the permission probes. Terry subsequently
requested the Node 24.20.0 LTS upgrade recorded in that audit; the original
probe environment remains unchanged in the retained evidence.

Validation includes a clean `npm ci`, native TS7 checking, Ruff, Pyright,
26 Python tests, local/hosted capability collection, source-integrity checks,
credential checks, and scoped cleanup. This is validated probe tooling and
negative capability evidence, not a production conformance pass.

[hosted]: ../evidence/runtime-permissions-cloudflare-2026-09-06.json
[local]: ../evidence/runtime-permissions-local-2026-09-06.json
[cleanup]: ../evidence/runtime-permissions-cleanup-2026-09-06.json
[probe]: ../../probes/runtime-permissions/README.md
[worker]: https://github.com/FlickrGroupAddr/architecture-design/blob/a02d02558fe0a384f27c6b9c5aee59f340f2fc4a/docs/worker-persistence-scheduler-contract.md
[fail-polite]: https://github.com/FlickrGroupAddr/architecture-design/blob/a02d02558fe0a384f27c6b9c5aee59f340f2fc4a/docs/testing/fail-polite-worker-database-conformance.md
[adr50]: https://github.com/FlickrGroupAddr/architecture-design/blob/a02d02558fe0a384f27c6b9c5aee59f340f2fc4a/docs/decisions/0050-select-cloudflare-and-evaluate-native-storage-first.md
[adr46]: https://github.com/FlickrGroupAddr/architecture-design/blob/a02d02558fe0a384f27c6b9c5aee59f340f2fc4a/docs/decisions/0046-use-existing-amazon-rds-postgresql.md
[error1010]: https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-1xxx-errors/error-1010/
[namespaces]: https://developers.cloudflare.com/api/resources/durable_objects/subresources/namespaces/methods/list/
