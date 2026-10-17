# Hosted publisher provider strategy — 2026-10-17

Status: **Proposed offline strategy; no hosted action authorized.** Ticket #0157
narrows the #0155 provider gaps without changing the sealed #0121 candidate.
The recommendation is immutable Worker identity plus an explicit owner decision
on controlled disposal of owned synthetic-only fixtures when SQL settlement
is unknown. That proposed scope is narrower than claiming a provider drain
oracle or weakening production cleanup. Seven successful phase receipts alone
do not prove all D1 operations settled for the immutable candidate.

This document supplements the [finite operator procedure](hosted-publisher-finite-operator-2026-10-17.md).
The [qualification packet](hosted-publisher-qualification-packet-2026-10-17.md)
and [action decision](hosted-publisher-action-decision-2026-10-17.md) retain
their authority. This proposal records no Beta selection, owner acceptance,
account access, token inspection, deployment, endpoint request or cleanup.
Production flags remain false; production scheduling, Flickr access, native
Lightroom operation and activation remain outside this work.

## Preserve the candidate; pin the new operator separately

The #0121 identity remains source commit
`aca532af6d570125c5d8bbcbd6ac1b4a10ae74f7`, 113 files, source-artifact
SHA2-256 `718b3dd7e1ec669c7e043f4c3a37142ceaad42a5bd3bcbc0639868a2b1e5aed1`,
and optimized `worker.js` SHA2-256
`b2241f88c94ec6561b2a902a5561bf9f63459e420fbd111861db1636feb2a26f`
(652,967 bytes). The action decision retains all other candidate pins. These
values identify prior evidence; this document does not claim a fresh rehash.

Do not rebuild, recapture or amend that closure. A later action sheet must pin
the independently reviewed operator, client, provider identity/completion
helpers, migrations 0001–0026 and deployment overlay separately, together with
their exact tool versions. Changing the new closure requires review and new
action-time consent, even when the original bundle remains unchanged.

## Resource identity strategy

The Scripts `PUT` upload remains unsuitable for create-only ownership because
it can replace a Worker; an earlier absence read cannot make it atomic.
Cloudflare's separate Workers Beta API documents standalone `POST` creation
and an immutable returned Worker ID. Its edit and delete endpoints accept an
ID or name; the proposed operator must use the returned ID exclusively after
creation. It must never substitute the intended mutable name or a D1 UUID.
See the dated official [create](https://developers.cloudflare.com/api/resources/workers/subresources/beta/subresources/workers/methods/create/),
[edit](https://developers.cloudflare.com/api/resources/workers/subresources/beta/subresources/workers/methods/edit/)
and [delete](https://developers.cloudflare.com/api/resources/workers/subresources/beta/subresources/workers/methods/delete/)
references reviewed on 2026-10-17.

Use ordinary documented Create semantics and explicit exclusive finite
operator ownership, rather than inventing a global collision or CAS oracle.
Stable identity addresses replacement by name; it does not establish
collision behavior, idempotent creation, lost-create recovery, conditional
mutation against a prior version, or exclusive ownership of all account
writers. The full create/version/deployment/readback/disable/delete chain must
be supported and independently reviewed before it replaces the current
adapter's refusal. Beta remains unselected here.

The prepared [Worker identity adapter](../../scripts/hosted_publisher_worker_identity.py)
exposes `BetaWorkerProvider.create_worker`, `inspect_worker`, `disable_worker`
and `delete_worker`. It reuses the bounded provider request/journal hooks and
accepts only identities returned by its own acknowledged creation. Its
32-lowercase-hex ID profile is a conservative parser boundary, not a general
claim that all Cloudflare identity formats are UUIDs. It prepares creation,
exact-ID read, disabled-configuration PATCH and non-forced deletion through
injected offline transports. Default or directly supplied built-in HTTPS transport use refuses with
`workers_beta_not_selected`. Arbitrary injected callables are a trusted offline
fixture seam, not a network sandbox or consent boundary; a callable could
delegate to network code. Both qualification and execution flags are false,
but those flags are reporting metadata and grant no execution authority.
Version upload, deployment, endpoint enablement and a complete lifecycle are
not implemented by that helper.

The remaining deployment chain is mixed: Beta version creation must bind the
exact module/configuration/D1 UUID, while documented deployment uses a Scripts
name. Require exclusive owner-controlled management, matching immutable-ID/name
observations and exact returned version/deployment validation across that seam;
do not describe the entire chain as ID-addressed or atomic. Concurrent dashboard,
CI or other management writers are excluded by an explicit operational
assumption; readback cannot fence an account administrator. The canonical
proposal supplies the dated version/deployment references and tradeoffs.

For a future approved run, reserve each create intent durably before sending
it. Bind a successful exact create response to the private account, scenario,
intended name, actual Worker ID or D1 UUID, response time and plan digest.
Verify actual deployment version, module/configuration, D1 binding and endpoint
before dispatch. A request label is not provider identity evidence.

An absent, malformed, contradictory or lost create response stops provisioning.
Do not repeat create, list the account, discover by prefix, adopt a same-name
resource, or delete a guessed ID. Preserve the unresolved intent and hand it
to the owner for separately scoped recovery. Exact known resources may still
receive their separately authorized cleanup; the missing identity itself has
no automatic recovery or deletion authority.

## Completion and cleanup

A completion proof must bind the exact candidate bytes and exclusive finite
request inventory, not merely inspect a final control-table cursor. It must
account for every submitted operation, including nested timeout paths whose
errors can be caught inside an otherwise successful phase. A response proves
the handler returned; it does not by itself prove all underlying operations
settled. Source review must account for all awaited work, terminal guards,
migrations and verification queries. Any accepted proof would cover only the
closed run's known work, not account-wide or provider-wide quiescence.

The retained source has a concrete unresolved branch argument. The
materialization consumer catches failure of its unknown-state write before
returning `create_outcome_unknown`; the probe then checks that durable marker
and performs repair checks. Attachment and title consumers also reconcile
after uncertain handoffs. These paths do not prove SQL remains pending, but
they prevent equating a successful application outcome with a positive
acknowledgement of every raw promise. See
[materialization](../../src/album_materialization_worker.ts),
[attachment](../../src/album_attachment_worker.ts),
[title](../../src/album_title_worker.ts) and the
[qualification entrypoint](../../probes/publisher-qualification/worker.ts).

Here success means the finite client's exact HTTP 200/schema check, including
the candidate's deliberate `status: NO-GO` and
`productionSchedulerQualified: false`. Those fields remain qualification
limits; the separate nested-operation accounting problem prevents treating
even seven such receipts as a D1 deletion certificate.

The narrow next engineering step is a complete source-and-durable-state
discharge of every potentially detached branch, including authenticated
rejected requests that may submit control SQL. If that proof cannot be made,
a separately scoped new candidate can track operation settlement; the sealed
#0121 candidate stays unchanged. No completion helper was added: the current
journal lacks raw D1 settlement evidence, and accepting `all_sql_awaited=true`
or an arbitrary quiescence boolean would assert the missing conclusion.
Cloudflare's documented [D1 batch semantics](https://developers.cloudflare.com/d1/worker-api/d1-database/)
and [statement results](https://developers.cloudflare.com/d1/worker-api/prepared-statements/)
do not supply an ordinary-query pending-operation census or drain guarantee.

Timeout races do not cancel a submitted D1 operation. Failure sealing, expiry,
endpoint disable and a later successful `SELECT` cannot establish that an
earlier uncertain operation has completed. Unknown phase or management-call
outcomes therefore remain in the residual ledger. Never clear the control
row, replay a phase, or reset the database to manufacture completion evidence.

Under the current settlement gate, cleanup requires its own exact resource,
owner, deadline and budget authority, verified access disablement and reviewed
completion evidence before D1 deletion. Where those premises remain unproved,
cleanup remains pending. Do not infer that the current lifecycle implements a
different rule.

The canonical proposal offers a precise alternative for Terry's decision:
after a durable dispatch fence, verified exact Worker-ID access disablement
and Worker deletion/absence, permit ordinary exact-UUID deletion of the owned
fresh synthetic-only D1 despite unknown settlement of that run's SQL. Record
SQL settlement/cancellation as unknown, not drained. Require the D1 deletion
receipt and exact-UUID absence observation. No `unsafeDelete`, forced deletion,
name/prefix discovery or production/shared database is included. This is a
Proposed change to disposal authority, not an existing permission or proof that
SQL completed. Unknown creates and unresolved deletion outcomes retain an
exact residual handoff; no blind replay follows.

All canonical amendment conditions still apply: a successful fresh-D1 receipt,
verified candidate binding, exclusively synthetic data/credentials, no protected
production history or external reference, and journal/evidence retained outside
the disposable fixtures. No shared binding, route, schedule, service consumer or
real Flickr access is permitted. Preserve all known/unknown operation inventories
and finite cost reservations. If Worker closure is unknown or drifted, retain
D1. Disposal does not prove physical backup erasure or completed business work;
unresolved outcomes prevent a claim of complete qualification or verified
cleanup even if resource disposal is confirmed.

Preserve successful step receipts independently, including Worker deletion
and exact-ID absence, so a later cleanup attempt need not require an already
deleted Worker merely to authorize D1 cleanup. A lost deletion response stays
unknown until a separately reviewed exact-ID reconciliation resolves it.

## Finite limits retained

The existing operator ceilings apply cumulatively across provisioning,
dispatch, stop and all cleanup adapters. A new adapter must not reset counters.

| Boundary | Maximum or exact requirement |
| --- | --- |
| Cases/resources | `happy`, `create_lost`, `attachment_lost`, `title_lost`; four new Worker/D1 pairs, no reuse |
| Phases | `seed`, `http`, `materialize`, `attach`, `title`, `remove`, `finish` once per case; 28 normal requests |
| Lifecycle | 14,400 seconds including cleanup; case access at most 1,800 seconds; phase at most 60 seconds |
| Management calls/mutations | 256 / 160 shared |
| Provider transport | 2 MiB request/response per call; 16 MiB requests / 32 MiB responses shared; 8 KiB request headers / 64 KiB response framing allowance; 20-second socket / 25-second request / 7,200-second adapter lifetime |
| Client | 32 requests per case / 128 shared; 262,144 request bytes / 8,388,608 response bytes shared; 65,536 response-wire bytes per request |
| Candidate SQL reservations | 8,192 calls / 1,048,576 statements shared; reserve before submission, not changed-row counts |
| Synthetic effects | 448 handoffs / 28 POSTs shared; at most 16 / one per phase |
| Plan | Closed duplicate-free JSON, at most 256 KiB; exact account, unique names/endpoints/run IDs, concrete start/expiry/cleanup deadline |

The SQL wrapper has a 256-call, batch-width-128 phase guard. Control and
failure-seal work are additional; the operator reserves 264 calls and 32,776
statements per phase plus migration/emptiness capacity. These bounds do not
prove completion or measure provider billing. The 500 ms body check and
500 ms failure-seal wait are separate from the phase ceiling. Budget headroom
does not authorize invented negative requests or repeated actions.

## Permissions, custody and revocation

Before action-time consent, the owner must review effective API permissions
and the narrowest supported exact account/resource scope for the selected
methods. The existing grant parser requires `D1:Edit` and
`Workers Scripts:Edit`, exact-account-only metadata, issue/expiry and a named
revocation owner. Parser acceptance and `metadata_verified=true` are not
independent provider evidence. Reconcile the selected Beta methods' actual
permissions with that parser before adoption; do not infer API capability
from a permission label or token syntax.

Creation authority may exceed the eight eventual resources. Record that
excess explicitly, with finite expiry, optional supported source-IP controls
and a separate means to revoke the grant. Do not substitute a global API key.
Cloudflare documents [token creation and constraints](https://developers.cloudflare.com/fundamentals/api/get-started/create-token/).

The management credential and four fresh synthetic probe secrets use separate
private in-memory delivery seams. No command arguments, tracked files, query
strings, shell history, journal payloads or receipt prose may contain them.
Probe expiry, local reference removal and credential loss do not revoke a
management grant. The named revocation owner must retain the token identifier,
provider expiry and independent revocation means privately, revoke management
access after the authorized cleanup or emergency stop, and retain sanitized
provider confirmation. If revocation prevents cleanup, retain the exact
residual-resource handoff; do not resume dispatch.

## Remaining decision and implementation boundary

The [canonical Proposed strategy](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/proposals/hosted-operator-provider-strategy-2026-10-17.md)
records the architecture recommendation; it is not accepted policy. The next
owner decision has three concrete options:

1. Adopt the proposed fixture-only Beta identity and controlled-disposal
   direction above, with explicit exclusive operator ownership (recommended).
2. Preserve the strict settlement gate and complete the source-branch proof
   or separately scoped successor candidate with settlement tracking.
3. Defer this hosted run.

Selection must identify the Beta dependency, ownership assumptions,
unknown-outcome handoff, disposal boundary, effective grant and revocation
responsibilities. It is not acceptance of generic residual risk. The later action decision
then binds exact bytes, private inputs, names, staged returned IDs, endpoint,
schedule, limits, cleanup-only continuation and actual human consent.

The current concrete Scripts adapter still refuses upload; the existing
operator still requires a synthetic `observe_pending` contract for deletion.
The identity adapter supplies a bounded offline seam. The strict completion
path still needs the branch proof or separately scoped candidate; the disposal
alternative still needs Terry's explicit adoption and implementation. This
work is not a runnable provisioning ceremony or a provider drain oracle. Keep
live flags false until the reviewed implementation and exact action decision
exist.

## Offline verification handoff

Independent identity and authority reviews passed after correcting incomplete
Worker-reference snapshots. The parent integration run passed all 24 identity
adapter tests. Scoped Ruff checks, formatting and Pyright passed with the pinned
project tools. Tests use injected fixtures; they made no provider request and
supply no Beta execution, complete deployment or SQL settlement evidence.

The canonical provider strategy remains Proposed. Its exact fixture-disposal
tradeoff needs Terry's acceptance before implementation relies on it; the later
complete operator still needs its own review and action-time authorization.
