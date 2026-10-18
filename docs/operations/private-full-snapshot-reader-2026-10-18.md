# Private full-state snapshot reader: preparation and qualification

Date: 2026-10-18. Ticket #0170. Status: **source preparation and synthetic
qualification proposal**. Terry approved developing and qualifying a private
full-state reader, including database authentication/session cells. That selects
the private full-data direction discussed in the
[preservation design](../design/temporary-composition-preservation-proof-2026-10-18.md).
It does not authorize account access, a production capture, credentials, provider
mutations, deployment, native input or publishing private evidence. No such
action is recorded here.

## Authority and purpose

The [preservation contract](fixed-origin-preservation-2026-10-17.md#paused-gates-and-consistent-full-data)
continues to require exact complete relational state, schema, row identity and
unchanged paused-gate revisions. This reader supplies a source seam; it does not
weaken that contract or establish the other restoration/configuration/resource
facts. The [documentation hierarchy](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/README.md)
and accepted persistence/conformance authority still control. The earlier
[metadata-only collection](temporary-composition-metadata-collection-2026-10-18.md)
cannot supply these private inputs and has no implicit broader access grant.

A source flag, declared barrier receipt, matching sweeps, digest, local test or
successful private write cannot make this reader production eligible. The exact
all-writer barrier, D1 transport representation and consistency semantics need
independent hosted qualification. Production composition remains NO-GO until
the complete source, authority and preservation gates are satisfied.

## Implemented source interface

`scripts/private_d1_snapshot_reader.py:collect(plan, expected_plan_sha256,
consent, credential, output_path, journal_path, *, now=..., clock=...,
transport=...)` accepts a trusted synthetic transport and credential callback.
It uses the existing finite client's `Request`/`Response` types; this entry point
has no default provider dispatch. Supplying JSON evidence pins or `approved=true` cannot
enable networking. The CLI has no synthetic transport injector, so it refuses
before calling the deferred token-file reader. It is not a production command.
`collect_isolated(..., permit=...)` is a separate qualification-only entry point:
it requires a same-process permit issued after creation acknowledgment of a
fresh synthetic database by `scripts/qualify_private_d1_snapshot.py`. A plan
flag or serialized receipt cannot substitute for that permit. This permits no
existing/production database read and proves no production barrier.

The closed plan pins the reader/dependency source digests, exact resource and
endpoint address, run/window, approved output/journal paths, complete ordered
query list, artifact/barrier/grant/qualification evidence and credential binding.
The consent record repeats the exact plan/source/evidence pins and decision
reference. These are integrity checks on supplied inputs; the caller remains
responsible for genuine owner authority and independent evidence provenance.
The credential binding is authentication-derived private evidence and belongs
with the private plan, never in a public receipt.

The current plan limits are 2,048 ordered queries, 32KiB per query, 256KiB per
response's decrypted HTTP wire bytes, 16MiB aggregate decrypted HTTP wire bytes,
effective page size at most 256
(the codec's stricter bound),
60 seconds per request and a window at most twenty minutes. The complete plan
must fit 1MiB. A fixed query must exactly match its next manifest entry; extra,
unused or mismatched entries refuse. The manifest depends on the actual schema
and continuation results. There is no live plan-discovery/preparer in this
revision; do not guess production queries or claim a synthetic manifest proves
actual completeness.

Both wire allowances include headers, body and chunk/trailer framing. Each
request's cap is the minimum of its per-response wire ceiling and the positive
remaining aggregate allowance before intent/dispatch, with no extra framing
allowance. A body-only count does not establish either limit. The finite
transport must report actual wire consumption at least equal to body length and
within the cap; exhaustion refuses before another intent/dispatch.

Synthetic requests describe only the official exact-account/database D1 query
endpoint, using POST for fixed read SQL. Responses require the closed expected
success/result shape, identity encoding and no redirect/pagination/truncation
signals. There are no automatic retries. The injected callback is trusted test
code; this alone does not prove those wire properties in a hosted transport.

Output and journal are distinct, exact bound absolute paths opened exclusively.
Existing paths refuse. The journal records intent before each query and retains
an aborted no-replay state after an uncertain run. Partial files/tombstones are
preserved; choose a fresh reviewed attempt rather than deleting them to rerun.
This does not supply cross-process directory/ACL qualification or an automatic
secure cleanup mechanism. The API returns only a closed completeness/query
summary with `productionQualified=false`, never rows.

`scripts/private_d1_snapshot_codec.py:collect_snapshot(query, *, page_size=256)`
discovers the actual schema and returns complete relational `schema`/`tables`
inputs to the typed comparator. It does not execute a SQL dump, restore data,
read a path, establish a transaction or prove a writer barrier. It retains
schema objects without SQL normalization or silent provider/bookkeeping
exclusions, duplicate rows, ordered columns and hidden rowids or WITHOUT ROWID
key contents. Integers are extracted as text before JSON conversion to avoid
JavaScript integer rounding, then decoded to exact signed 64-bit integer cells;
BLOBs use hex and text requires valid UTF-8,
including embedded NUL. NULL-SQL autoindexes and generated columns are retained.
Virtual/shadow tables and inaccessible hidden identities
refuse rather than disappearing from the census.
The encoding census requires actual UTF-8; unsupported database encoding refuses.

Codec bounds also retain at most 128 tables, 2,048 schema objects, 256 columns
per table, 10,000 total rows and 4MiB canonical snapshot content. Every table
requires a complete count, exact-sized pages and an empty terminal sentinel.
These detect observed incompleteness; they do not create transaction isolation.

**Current unsupported value: every SQL REAL cell refuses the whole snapshot.**
Lossless binary64 extraction through D1 has not been implemented/qualified.
Consequently this is not a universally complete D1 reader: any REAL in actual
data makes capture unavailable. No sampling, coercion to text/rounded numbers,
ignored column or accepted drift exception closes that gap. The existing
synthetic comparator's ability to compare canonical REAL cells does not prove
that this source can extract them.

## Private data and custody

Every captured cell is private, including authentication/session/CSRF fields,
photo metadata, identifiers, revocations and history. Full comparison deliberately
receives these values; hashing or suppressing output afterward does not undo
the read/export. Database-cell permission does not permit reading Worker binding
values, managed secret-store values, token files, private native storage or
unrelated databases. A later exact action packet must identify the permitted
credential and secret-valued database-cell handling explicitly.

Before any actual capture, pin the exact account/database, owner identity,
schema/artifact, tool/source digests, operator, run, observation window, effective
grants, finite budget and approved destination. Independently establish resource
identity; a caller-supplied identifier or token target is not proof. Keep tokens
out of arguments and packets. Effective capability must be reviewed separately
from the implementation's SELECT-only request surface.

Use an owner-controlled private location outside every checkout, synchronized
share, public support bundle and temporary cache. Review its actual Windows
access, backup/sync behavior, available space and independent reader access
before use; a directory name is not an ACL or encryption guarantee. Retain the
input plan, complete snapshots, barrier/provenance records and any partial
failure artifacts together. Only sanitized outcome labels and private retrieval
references belong in chat, tickets or public evidence. Roots/manifests and
digests of private values remain private unless specifically reviewed for
disclosure; they are not anonymization.

Retention and deletion are **unresolved for actual snapshots**: no finite
production retention period, encrypted storage qualification, secure erasure
guarantee or automated remote/local cleanup is established by this source.
The exact action packet must settle retention, responsible custodian, review
access and deletion/absence evidence before capture. A failed/interrupted run
must account for partial files and process/transport buffers without exposing
their contents. Do not claim a sanitized failure receipt proves erasure.

The source validates sink binding and exclusive creation; the custody location
restrictions above are operator requirements still awaiting qualification, not
claims that path validation enforces ACLs, encryption, no-sync or erasure.

## Required writer barrier

Identify every writer for the exact captured and temporary artifacts: ordinary
authenticated routes and their audit/session effects, intake, schedulers and
maintenance, dispatch/recovery, queue consumers, Durable Object alarms and
callers, migrations, stale invocations and direct provider operators. Disabled
Flickr capabilities and paused gate rows do not stop all these writes.

The independently qualified mechanism must close admission, acknowledge drain
or fence admitted work at commit, and continuously cover schema discovery,
every page, fresh preflight, exact retained-version restoration and restored
readback. It must survive crash, restart, old-version execution, configuration
propagation and inability to read its authority. Its expiry cannot automatically
resume writes. A local boolean or two equal observations cannot detect a
mutate-and-revert interval and cannot provide that barrier.

Do not add a trigger/table/wrapper or alter the retained artifact during an
attempt merely to manufacture evidence. If the original artifact lacks a
restoration-surviving barrier, stop for the owning design decision. Likewise,
an ordinary authenticated check that writes audit/session state conflicts with
the exact full-equality freeze; neither omit its changes nor disable required
audit to obtain a pass.

## Isolated qualification source and broader campaign

`scripts/qualify_private_d1_snapshot.py` owns the separate small synthetic D1
transport qualification. Its fresh-create acknowledgment is the only source of
the same-process database permit consumed by `collect_isolated`; it cannot
import a preexisting production identity as qualification input. The intended
sequence is one create, one fixed synthetic seed, a bounded discovery capture,
one exact reader capture using the discovered query manifest, one exact
delete and one GET of that same fresh UUID. Account access, provisioning,
fixture mutation and deletion still need
the later concrete isolated action decision.

The implemented ceiling is **26 total requests**: one create, one fixed seed,
at most 11 discovery/capture SQL requests, at most 11 exact reader SQL requests,
one delete and one exact UUID GET. The census
permits at most two tables in total (including provider bookkeeping), with at
most 256 rows per table. Unexpected tables/denied metadata/unsupported values
refuse rather than being excluded. The fixed seed tests NULL, signed 64-bit
extremes, empty and embedded-NUL/Unicode text, and a BLOB. It independently checks
those expected cells, then exact equality between discovery and reader results.
Its REAL negative is a local decoder refusal check, not hosted REAL extraction.

The closed private packet binds account, numeric endpoint, run/source, exact
three private sink paths, credential binding, effective-grant evidence, custody
evidence, caller start/expiry and separately recorded provider token expiry.
The caller window is at most twenty minutes; that deadline does not shorten or
revoke a provider token. Actual D1 Write scope, provisioning authority, token
delivery/revocation owner and private custody need independent review before a
run. There is no accepted existing-database ID, preexisting-resource lookup, Worker deployment,
retry or resume option. Synthetic injected transport cannot count as hosted
qualification.

After that exact action decision, the implemented CLI shape is:

```console
uv run --frozen python -m scripts.qualify_private_d1_snapshot --packet PRIVATE_PACKET --expected-packet-sha256 REVIEWED_PACKET_DIGEST --consent PRIVATE_DECISION --token-file PRIVATE_TOKEN_FILE --journal PRIVATE_JOURNAL
```

This command is documented for a later action packet; it has not run. Existing
sinks refuse. The private journal retains an acknowledged fresh database UUID
when available; any uncertain dispatch/reader result retains state without
deletion or replay. Failure before a create acknowledgment can leave an unknown
resource outcome requiring later reviewed reconciliation. After terminal DELETE
acknowledgment, the one exact UUID GET can record only the closed provider
not-found response: HTTP 404 with the expected Cloudflare envelope and one
error code 7404. This is **not verified absence, physical erasure or cleanup
completion**. Generic 404, authentication failure, HTTP 200, malformed result,
timeout or uncertain delete/GET remains cleanup unconfirmed, with no replay.
Unknown SQL/reader outcome retains the database without deletion. The
26-request budget includes no credential revocation. These cleanup and retention
gaps need explicit disposition before an actual run; do not silently add
requests. Private output/journals remain retained for review under the separately
settled custody decision.

`complete=true` means only that the finite recipe finished. The result retains
`cleanupVerified=false`; `providerNotFoundObserved=true` names the provider
response and the journal retains `cleanup_unconfirmed_provider_not_found`.
Neither field licenses a claim that the database is absent or cleanup passed.

The official [D1 database GET reference](https://developers.cloudflare.com/api/resources/d1/subresources/database/methods/get/)
documents a 200 response, without a normative post-delete absence contract.
A [public reporter's issue](https://github.com/cloudflare/developer-platform/issues/69)
(transferred from workers-sdk issue 15144) reports error 7404 while that
database remained usable through other interfaces. This is cautionary reported
evidence, not a qualified GET error contract. The source's closed 404/7404
classification therefore remains only a provider response observation.

This transport exercise cannot test a production-restoration-surviving writer
barrier, every production table/type, all fault paths or production custody by
itself. Keep its result separate from the broader proposed campaign below.

## Finite barrier and fault campaign proposal

This is a reviewable experiment recipe, **not an executable provider action
packet or permission to create resources**. Proposed campaign ceiling: 24
isolated runs, at most three reader captures each (72 total), one isolated
database and one writer artifact, with at most one create and one exact delete
attempt per resource. Each run needs an exact synthetic fixture/reset manifest;
these writes are counted separately. Final query/request count depends on the
fixed schema/page manifest and reader bounds; freeze that count before any
account request. Do not invent provider switches or turn local fixtures into
observed resource acknowledgments.

1. Select one fresh, separately owned isolated D1 database, one synthetic writer
   and one reviewed reader identity, with exact acknowledged identifiers and
   no production binding, route, account record or secret. Approve their create,
   fixture-write, read and eventual exact-delete operations separately. Use one
   primary operator, one run and one immutable source/budget packet.
2. Apply the exact supported fixture schema. Seed synthetic authentication,
   session and photo markers, all supported cell classes, signed 64-bit boundary
   integers, UTF-8/NUL text, empty/large BLOBs,
   duplicate rows, hidden rowid aliases, WITHOUT ROWID keys, migration and
   sequence bookkeeping. Include exactly identified paused deployment/user
   gates and pinned revisions. Separately inject finite REAL boundaries/signed
   zero as refusal cases until lossless extraction is implemented and qualified.
   Unsupported schema/value forms must refuse the whole snapshot.
3. Execute one baseline, one fresh preflight and one restored-state capture
   under the candidate barrier, with one query attempt per fixed page and no
   automatic retries. Bind the complete snapshots to the same source/schema,
   resource, barrier generation and window. Compare against independently
   retained fixture facts using the full typed comparator. Equality covers
   stored relational state and row identities, not physical database pages.
4. Use fresh isolated runs for the finite fault matrix: same-count replacement;
   hidden-rowid/schema/type drift; gate or revision drift; malformed/truncated
   provider results; oversized cells/pages/aggregate state; exhausted page/query/
   time budgets; timeout, interrupted private write and cleanup failure. Require
   refusal and no successful partial snapshot. Verify exact integer and REAL
   round trips through the actual D1 transport, rather than trusting JSON number
   behavior or a local SQLite result. SQL REAL currently refuses rather than
   asserting a lossless round trip; its mere presence prevents a full snapshot.
5. Qualify the barrier against a writer before admission closure, in-flight work,
   a delayed callback, a stale/restarted writer, direct-operator bypass,
   mutate-and-revert, schema change between pages and barrier loss during
   retained-version restoration. The safe result is proven fencing or refusal;
   equal sweeps alone fail this qualification. If the barrier is not implemented
   and reviewable, this phase remains unavailable.
6. Inspect public stdout/stderr, exception handling, trace/support artifacts,
   process arguments and sanitized receipts using synthetic markers only.
   Confirm no marker leaks on success, refusal or interruption. Independently
   verify the retained private snapshot's completeness and typed equality.
7. Stop the isolated writer; independently account for pending operations. After
   retaining the approved review evidence, delete only exact acknowledged owned
   resources under the experiment's reviewed cleanup rule, and independently
   observe absence. Unknown deletion or lost acknowledgment remains
   `cleanup_unconfirmed`; do not replay mutations, guess ownership or recreate
   resources. Apply the separately settled private retention/disposal decision.

The isolated packet must assign every case within the 24-run ceiling and fix
finite pages, queries, bytes,
elapsed time, fault cases, mutation attempts and cleanup observations. Exceeding
one limit stops that run; increasing a bound requires a new reviewed packet.
No open-ended polling, sampling, silent truncation, forced restore, production
repair or enabling Flickr writes belongs to qualification.

The publisher-only synthetic disposal exception accepted elsewhere cannot be
reused here without a scoped decision. This experiment contains database
authentication/session fields and has different resource/custody semantics.
Deleting a test resource does not prove preservation, SQL settlement or private
artifact erasure. Exact resource absence also does not establish removal from
provider recovery history, telemetry, backups or filesystem recovery media;
their retention/disposal behavior remains an explicit qualification gap.

## Later production capture gate

After independent source review and isolated hosted qualification, prepare one
concrete action packet with the exact read surface, resource identities,
effective grants, credential delivery, finite request/byte/time budget, sensitive
cell custody, qualified barrier evidence, retention and cleanup responsibilities.
Terry's actual account/data-access decision applies to that packet; no extra
interactive CLI confirmation ceremony is introduced here.

This work does not observe the current production schema or owner/gate revisions,
prove provider restoration/changed-secret behavior, reconcile native-secret
generations, qualify ordinary authenticated routes, or complete #0163's baseline.
The existing backup strategy and restoration requirements remain with
[D1 backup and recovery](d1-backup-and-recovery.md); this reader introduces no
scheduled export or replacement backup policy.
