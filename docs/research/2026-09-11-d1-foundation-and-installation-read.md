# D1 protection/recovery and current-installation read

Date: 2026-09-11. Cards: #0007 and #0011.

The FGA API backend now implements the accepted read-only installation endpoint
against a scoped native D1 foundation schema. Disposable hosted tests exercise
ordinary SQL guards, migration/restore behavior and the real HTTPS read route.
This is implementation and provider evidence, not a production release approval.
Two owner decisions remain; neither finding establishes a need for AWS.

## Owner handoff

### #0007: database-clock precision

The accepted [administrative audit contract](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/administrative-control-plane-contract.md)
asks for UTC timestamps with microsecond precision. The FGA database supplies
persisted times. D1/SQLite's documented clock resolution is milliseconds. Twelve
hosted observations used six fractional digits but all had a zero remainder
modulo 1,000 microseconds. Formatting `.123000Z` does not create microsecond
resolution. Card #0014 remains the dependency for settling this distinction.

**Recommendation for Terry:** explicitly accept millisecond source resolution
for persisted UTC timestamps in the private deployment. Keep six-digit UTC
serialization if desired, document the lower three zeros, and use explicit
revisions/sequences for ordering. Do not relax atomicity, lease fencing, expiry
comparisons or the independent monotonic preflight timing requirements. Proposed
wording: “For the private single-owner deployment, database-generated persisted
UTC timestamps may have millisecond source resolution. Formatting and integer
microsecond units do not imply finer resolution. Durable order is supplied by
explicit sequence/revision fields, never inferred from clock uniqueness.”

This report does not accept that amendment. Adding RDS merely to gain a finer
clock is not recommended for this hobby deployment.

### #0011: early rejection of duplicate authentication headers

Cloudflare rejected two Authorization header fields with its stock 155-byte
HTTP 400 HTML response, before the application JSON error response appeared.
The body has SHA2-256 fingerprint
`efca0895b4d88b27a94249f8e7ac0083eff0a4ff3ac37c2841b3f6d7e11c1905`, matching
the provider page in the earlier routing proof. It has no application
`Cache-Control: no-store`. Application-delivered duplicate/comma-separated
Authorization is rejected with the required JSON `invalid_request` and matching
Bearer challenge. No credential is accepted by either rejection path.

The [accepted early-rejection clarification](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/operations/http-route-conformance.md#provider-rejection-before-application-routing)
currently covers malformed request targets and explicitly excludes authentication.
The existing decision cannot silently be stretched to cover this result.

**Recommendation for Terry:** extend that narrow clarification to duplicate
Authorization header fields rejected by the provider HTTP parser before the
Worker. Require HTTP 400, no redirect, no application shell or application/session
data, and retain JSON/no-store plus matching Bearer error codes for every
application-generated authentication response. Do not exempt successful
requests, ordinary route errors, or arbitrary provider failures on valid targets.
Clients already need to handle the same early non-JSON 400 for malformed targets.
An extra proxy solely to restyle this rejection is not recommended.

This amendment is proposed, not accepted. #0011 remains a truthful conformance
handoff even though its normal credential lookup behavior is implemented.

## Implementation

- `src/worker.ts` registers only `GET /api/v001/installations/current` as a
  business API. `src/installations.ts` validates the canonical 64-character
  Crockford credential, hashes its entire ASCII form including hyphens with
  SHA2-256, performs one parameterized D1 lookup, and emits the exact five fields.
- Current and unexpired pending credentials can read their installation. Pending
  credentials are denied ordinary-operation scope. Malformed, unknown, replaced,
  revoked and expired credentials share the accepted invalid-token response.
  Unknown/corrupt storage states fail closed with a fixed, sanitized alert.
  There is no cross-request positive authentication cache.
- The typed registry generates `generated/route-inventory.json` and
  `generated/openapi.json`. The older routing-probe artifacts remain separate.
  Missing authentication is an empty 401 with a bare Bearer challenge; application
  errors are JSON/no-store. Unregistered API/health paths cannot become assets.
- Root migrations enforce one current and at most one pending version, matching
  installation pointers, ownership/class immutability, legal state transitions,
  monotonic revisions/ordinals, terminal revocation and retained credential
  history. Deferred cyclic foreign keys make pointer/state consistency a commit
  constraint. Ordinary changes cannot rewrite/delete/replace permanent blocks or
  append-only audit records. Creation and expiry metadata are guarded.
- `FGA_READ_ENABLED` defaults to disabled outside the database. The example
  deployment configuration also disables the public preview and supplies a
  placeholder database ID. It is not a production deployment.

## Backup and recovery findings

Ordinary `wrangler d1 export` rounded `9007199254740993` to
`9007199254740992`, and emitted signed-64-bit boundary values as rounded values
outside their intended integer representation. This export cannot be treated as
an exact archival backup for arbitrary 64-bit ordering/fencing fields. It is a
[documented export limitation](https://developers.cloudflare.com/d1/best-practices/import-export-data/),
not evidence that D1 itself loses those integers.

The tested small export adapter uses the provider's schema-only export and
SQLite `quote()` for ordinary values, with hex text literals only when a text
value contains NUL, to serialize values inside D1 before JSON or JavaScript can
coerce an integer. This preserves apostrophes, Unicode, CR/LF and embedded NUL,
which plain SQLite `quote(TEXT)` would truncate. It omits generated columns and writes credential
versions in parent/ordinal order. The controller imports the result into a new
empty database with deferred foreign keys. This adds no service or identity
boundary. It is deliberately scoped to the known foundation tables; adding a
table requires extending the exporter and its restore checks.

The controller removes the disposable Worker and confirms its absence before
backup and Time Travel. All earlier requests have completed, there are no
schedulers or other writers, and subsequent SQL operations come only from this
one operator process. The stop is outside the restored database, so rolling back
a database row cannot reopen the application. An exact export requires this
quiescent boundary: multiple independently queried tables are not a single
cross-request snapshot while writers are active.

The Time Travel scenario captures a bookmark, adds a later permanent block/audit
and credential revocation, then restores the earlier point. It confirms those
new facts are missing and leaves the Worker removed. Restoring the later complete
bookmark recovers the facts, exact integers and SQL guards. The proof never
resumes from incomplete history or discards the omitted interval. If a complete
history cannot be recovered, the correct state remains stopped pending recovery.

[Cloudflare Time Travel](https://developers.cloudflare.com/d1/reference/time-travel/)
is an in-place operation with finite retention (7 days Free / 30 days Paid).
It does not replace longer-lived exact backups. Archive destination, retention,
backup scheduling, encryption/access controls and a full deployed-service
quiescence procedure must be configured before production; this disposable proof
is evidence for the mechanism, not an operational backup service.

## Final validation evidence

| Evidence | Result |
| --- | --- |
| [Hosted D1 guards, migrations, exact export/import and Time Travel](../evidence/foundation-guards-2026-09-11.json) | 46 checks pass; clock source-resolution decision remains open |
| [Hosted installation-read sweep](../evidence/foundation-read-2026-09-11.json) | 25 checks pass; one unmet duplicate-Authorization response contract; command exits nonzero |
| Python tests | 66 pass |
| Node/Worker integration and existing route/credential regressions | 36 pass |
| Pinned native TypeScript, Ruff, Pyright and generated artifact checks | Pass |

Both hosted reports fingerprint implementation commit `706a51c`. The only later
controller change wraps one long Python string expression; an AST comparison
confirms identical executable code. The application, migrations and deployed
proof wrapper are unchanged. Application cases have zero retries. Each final
run records one bounded setup/status retry separately. Every application result
must carry the expected proof-build marker, which the production entry point
does not emit.

[Cleanup evidence](../evidence/foundation-cleanup-2026-09-11.json) covers all 24
created disposable databases and 17 deployed Workers across the completed and
failed attempts, including the focused import diagnostic. Every attempted
resource has confirmed cleanup. Earlier failed runs are not reclassified as
passes. They include harness corrections, provider readiness errors, and an
intermittent provider 404 on the encoded-separator case. Its root cause remains
unproved; the final strict sweep did not reproduce it. This report grants no
exception for such responses and makes no claim that readiness checks fixed them.

## Scope and reproduction

See [the proof procedure](../../probes/foundation/README.md). The production entry
point imports no fixture routes or provisioning functions. The separate proof
wrapper is bearer-protected, expiring and tied to generated disposable resources.
Read fixtures use fresh random credential material kept in memory, and retain
only credential digests in D1. Public evidence contains neither credential nor
individual digest. No read fixture database is exported. An aggregate before/after
snapshot checks that the entire read phase has no durable changes.

The local tests use the pinned emulator's `2026-07-30` compatibility date. Hosted
runs use `2026-09-11`, native TypeScript 7.0.2, Node 24.20.0, Wrangler 4.116.0 and
the locked dependencies. The application-only bundle has no third-party runtime
imports. Existing development-tool advisories remain in the pinned stable
Wrangler/Miniflare dependency graph; this work does not claim a clean npm audit.

Neither card proves group admission, FIFO scheduling, stale-worker fencing,
dispatch recovery, complete production domain migrations, Flickr integration,
real Lightroom Classic host behavior or production TLS/certificate lifecycle.
Those remain their own accepted gates. No AWS resource, production database,
public custom-domain route or Flickr authorization was changed.
