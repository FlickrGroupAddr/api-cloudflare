# Hosted publisher execution caller â€” 2026-10-18

Status: **Source-only execution preparation; no hosted action authorized.**
Ticket #0165 adds a concrete caller to the separately completed #0162 offline
operator. Finishing this source, its synthetic tests and independent review
can support a later exact #0134 decision. It supplies neither that decision
nor Cloudflare API qualification. No account, grant, credential or provider
state was inspected in preparing this procedure.

The [accepted #0157 scoped contract](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/proposals/hosted-operator-provider-strategy-2026-10-17.md)
controls the Beta identity direction, exclusive finite operator assumption and
six-condition synthetic-fixture disposal exception. This procedure is a derived
implementation guide. The [#0162 integration procedure](hosted-publisher-beta-integration-2026-10-18.md)
remains its historical source handoff; the
[renewed #0134 packet](hosted-publisher-renewed-action-decision-2026-10-18.md)
records the earlier unresolved engineering gate. Parent integration must bind
the new committed caller closure and review before renewing that packet.

## Scoped October 18 provider-expiry successor

Terry accepted the [one-attempt expiry amendment](hosted-publisher-token-expiry-amendment-2026-10-18.md).
The #0173 successor adds its exact-plan-bound optional grant policy through the
shared validator. Provider timing remains real metadata; all earlier caller,
case, phase, adapter, cleanup and approval deadlines, counters, fingerprint,
stop and journal checks below remain unchanged. Reprepare with the new committed
source and fresh independent packet pins. This does not modify old #0165 packets
or authorize token issuance, credential reads, account/DNS preparation or a run.

## Freeze the source and private action sheet

Preserve the [immutable #0121 candidate](hosted-publisher-qualification-packet-2026-10-17.md),
its original source, optimized module, migration bytes and receipts. Preserve
sealed #0162 evidence. Do not rebuild or recapture either to make the caller
appear qualified. The new execution closure has its own committed revision,
manifest, byte digests and independent review. A changed caller, transport,
procedure or projection requires a new comparison and review.

Before any later action, record these exact inputs privately, outside Git:

- The reviewed committed source closure, independently retained packet digest,
  original candidate pins, plan digest and deployment projection rules. Enabled
  configuration is a separate projection bound to the returned D1 UUID; a disabled
  configuration digest cannot attest it.
- One account, four fresh unique Worker/D1 intended names, exact HTTPS endpoints,
  run IDs and the cases `happy`, `create_lost`, `attachment_lost`, `title_lost`.
  Provider-returned Worker IDs, D1 UUIDs, versions and deployment IDs are staged
  only from acknowledged create/readback receipts, never invented beforehand.
- Fixed absolute packet, consent, grant, credential, journal, retained-candidate,
  bundle, source and stop-control locations. Review their ownership and access;
  record the private evidence location and owner. No example directory, synthetic
  test input, blank envelope or metadata flag establishes actual provenance.
- Concrete UTC start, dispatch expiry and cleanup deadline, operator/stop/cleanup
  owners, revocation owner and residual escalation deadline. Keep exclusive owner
  control throughout: no dashboard, CI or other management writer. This is an
  operational assumption; a readback cannot fence an account administrator.
- Exact human authorization tied to the plan, reviewed closure, actions and window;
  separate exact cleanup authority, decision reference and finite expiry. Parser
  acceptance of `granted=true` is insufficient evidence of actual consent.
- Independently reviewed effective grants for the actual Beta, Scripts and D1
  methods, exact account scope, grant issue/expiry, excess creation authority,
  private grant identifier and independent revocation means. Matching `D1:Edit`,
  `Workers Scripts:Edit` and `metadata_verified=true` proves no provider permission.
- Reviewed custody and removal of the management credential and fresh synthetic
  probe secrets. Never place their values in arguments, environment variables,
  URLs, shell history, tracked files, receipts, journals or exception reports.
  Do not substitute a global API key or expand permissions automatically.

The final action sheet must fix these values; this source-only procedure does
not fill them in or authorize collecting them. A new credential delivery file
is a separately reviewed private custody boundary, not evidence that OS access
controls, secure erasure or provider revocation have been qualified.

## Prepare, verify and invoke the caller

The [runtime preparer](../../scripts/prepare_hosted_publisher_runtime.py) is
separate from the historical #0134 preparer. Its `prepare()` function accepts
independently supplied scope/network bytes, retained source/bundle paths, the
current source root and exact reviewed committed HEAD. It writes a new packet
containing `plan.json`, `manifest.json` and `source/`. It never accepts consent
or a credential. `PLAN_FILES` and `SOURCE_FILES` own its precise closure: the
existing operator/adapter/client/configuration closure plus the new caller,
execution provider, runtime preparer and frozen Python tooling locks. Retain
reviewed test/procedure byte identities separately; they are not implicitly
included in that manifest.

The manifest binds the exact source commit, candidate pins, plan digest, source
bytes and the network record's `management_address` and exact endpoint-keyed
`client_addresses`. It deliberately retains `status: NO-GO`,
`live_execution_allowed: false`, `provider_qualified: false` and
`native_execution_allowed: false`. Verification cannot promote those fields.

After a later authorized private preparation, this is the offline verification
syntax; angle-bracket values must come from the actual reviewed action sheet:

```text
uv run --frozen python -m scripts.prepare_hosted_publisher_runtime --verify <absolute-packet-directory> --packet-digest <independently-retained-digest>
```

Use the pinned project Python/uv environment with `uv run --frozen`; do not update
locks or rebuild the retained Worker. The [caller](../../scripts/hosted_publisher_execution.py)
uses this common argument set for `readiness`, `execute` and `cleanup`:

```text
uv run --frozen python -m scripts.hosted_publisher_execution <action>
  --packet <absolute-packet-directory> --packet-digest <independent-digest>
  --consent <absolute-consent-file> --consent-digest <independent-digest>
  --grant <absolute-grant-file> --grant-digest <independent-digest>
  --approval <absolute-approval-file> --approval-digest <independent-digest>
  --grant-evidence <absolute-reviewed-grant-evidence-file>
  --credential-file <absolute-private-credential-file>
  --journal <absolute-private-journal-file>
  --candidate-root <absolute-retained-source-directory>
  --bundle <absolute-retained-worker-file> --current-root <absolute-reviewed-repository>
  --stop-file <absolute-private-stop-marker>
```

This is syntax documentation, not a command authorized for this turn. Join its
lines using the selected shell's normal argument syntax only after fixing all
paths/digests privately. No credential value is a command argument. The stop
marker is optional in the source interface; the later private action sheet must
explicitly select and assign its stop mechanism rather than silently omit it.

- `readiness` validates packet/source/candidate identities, consent, current grant
  and approval bindings, evidence digest and private journal paths. It also checks
  credential-file existence, private custody metadata and bounded size, without
  reading credential bytes. It reads no
  management credential and dispatches no request. Successful readiness deliberately
  returns NO-GO/exit 2; it grants no action permission.
- `execute` requires the actual later human decision and independently retained
  approval digest, then durably reserves once-only execution before reading the
  credential or constructing the concrete provider/client. Missing inputs default
  to refusal. It runs only from the exact committed source root bound to the packet.
- `cleanup` adds `--cleanup-authority <absolute-private-file>` and
  `--cleanup-digest <independent-digest>`. It requires the original execution
  authority and started marker in the same journal, plus separate current cleanup
  authority. It cannot resume phase dispatch or provisioning.

The approval record binds source/packet/plan/consent/grant/evidence identities,
exact actions, finite expiry and isolation assertions. Its `human_approval`
record names the actual decision reference, retained evidence digest and recorded
UTC time. JSON does not authenticate its author: the authorized parent must
materialize this record and independently retain its digest only after the real
exact-plan human approval. No CLI switch or typed phrase substitutes for that
approval. Grant-evidence bytes remain independent input; hashing them proves
identity, not the truth or effectiveness of the grant.

The private approval record also requires `credential_sha2_256`: the exact
credential fingerprint independently sourced during separately authorized
credential provisioning and bound to the reviewed grant packet. An absent field
refuses; after all non-secret gates and once-only reservation, the caller hashes
the bounded credential bytes and refuses a mismatch before constructing the
provider. Keep this fingerprint private in the approval evidence; it is never
a CLI argument, journal field or public receipt. This source-only work supplies
no fingerprint and inspects no actual credential. Neither this hash nor the
approval JSON proves human authorship or effective provider policy.

Private documents use bounded regular-file reads and independent digest checks.
The credential file contains only the approved raw ASCII management credential,
without a newline; the caller reads it only after non-secret gates and durable
reservation. It inspects owner/access metadata, refuses links/hardlinks and
changes detected across the bounded read. Windows checks allow only the current
owner, SYSTEM and Administrators; unsupported or unexpected ACL metadata refuses.
These source checks do not qualify actual OS custody, eliminate all privileged
replacement races, or securely erase Python strings. The actual file/parent
ownership, provisioning and eventual removal still need review on the action
sheet. Fresh probe secrets are generated in memory; cleanup generates none.

An existing selected stop marker refuses normal readiness/execution before
credential loading. A marker or operator stop observed after admission permanently
latches the permit against provisioning and phase dispatch, even if the marker
is later removed. It does not recall admitted work. Only the existing operator's
bounded `_stopping` disable/readback path remains available while the permit is
otherwise valid; separately authorized cleanup may perform its closure actions.
Preserve the marker and journal; never remove either to regain dispatch. At exit the caller drops
local probe/provider credential references. Provider grant revocation remains
an external owner action.

## Concrete transport boundary

The new [execution provider](../../scripts/hosted_publisher_execution_provider.py)
selects the concrete path explicitly; the sealed offline provider defaults are
unchanged. Its runtime permit authorizes construction and every possible
request. Callback injection remains trusted synthetic test code and cannot
supply an alternative authority boundary.

Management connects only to the packet's reviewed public numeric address on
port 443, with TLS hostname verification for `api.cloudflare.com`. The probe
client connects only to each exact approved HTTPS origin and its separately
pinned public numeric address. There is no DNS lookup, proxy, redirect, retry
or alternate-address fallback. Independently source those address pins before
the later decision; this source preparation performs no resolution or traffic.
Changed or unavailable addresses require a new reviewed packet rather than
opportunistic fallback.

Inherited provider action/byte/deadline guards and durable unknown handling
remain active. Management request headers are capped at 8 KiB; response wire
capacity is bounded payload plus the 64 KiB framing allowance. Client response
wire capacity is at most 64 KiB including headers, chunks and trailers.
Both concrete readers bound each socket read by the remaining inclusive wire
capacity before receiving bytes. Exhaustion refuses any further read, including
an EOF probe; it never substitutes a zero-length socket read for EOF. An explicit
length or chunk terminator fully parsed within the capacity can complete at the
exact boundary. A response needing another byte to finish framing or establish
EOF is unknown at that boundary, even if the peer has closed the connection.
The transport checks raw status/header/trailer syntax before accepting HTTP
framing, refuses duplicate headers, malformed or conflicting lengths/transfer
encoding, redirects, incomplete chunks and trailers that revise framing or
routing. Unsolicited interim/bodyless acknowledgements are refused. A single
absolute admitted request deadline is rechecked before connect, TLS and send;
remaining time bounds each stage and response reads. Expiry is not permission
to replay an uncertain request. TLS and framing checks are implementation
boundaries, not evidence that the actual provider API accepts the reviewed
requests or that grants are effective.

## Finite execution and stop

Use one lifetime journal and its owner latch outside the disposable resources.
Durable intent precedes each create, phase and mutation. Process replacement,
new adapters and cleanup-only continuation retain every spent reservation,
unknown latch and original deadline. The durable `execution:authority` receipt
records original `startedAt`, `adapterDeadline` (start plus 7,200 seconds) and
`lifecycleDeadline` (start plus the plan's lifecycle cap, at most 14,400 seconds).
Cleanup validates and restores those same absolute deadlines; it does not gain
a fresh 7,200-second adapter lifetime or lifecycle window. Remaining grant,
approval/cleanup and plan windows can shorten them. Exhausted original provider
capacity or an expired permit refuses before credential loading. Never replace
the journal, clear control
rows or start a fresh run to bypass an interrupted operation.

The private plan may lower the [existing cumulative limits](hosted-publisher-beta-integration-2026-10-18.md#finite-budget-and-journal-boundary);
it cannot raise them. The principal ceilings are four fresh Worker/D1 pairs,
28 ordered normal phase requests, 256 management calls, 160 management mutations,
128 client requests, 8,192 SQL calls and 1,048,576 SQL statements. The whole
lifecycle including cleanup is at most 14,400 seconds; case access is at most
1,800 seconds and each phase at most 60 seconds. All byte, framing, socket,
request and adapter-lifetime limits still apply across stop and cleanup.
Reservations bound submitted work, not billing, changed rows or settlement.

After readiness and the exact action decision, the caller must validate the
private packet, source/candidate bytes, consent, grants, times and delivery
boundary before loading a credential or constructing a live request path.
Provision through the existing operator: exact D1 creation/emptiness, returned
immutable Worker identity, migrations 0001â€“0026, exact module/configuration
version, Scripts deployment and binding/endpoint readback. Only then dispatch
`seed`, `http`, `materialize`, `attach`, `title`, `remove`, `finish` once per case.
The candidate's deliberate `status: NO-GO` and
`productionSchedulerQualified: false` responses remain qualification limits.

Unknown responses, drift, stop, deadline or exhausted budget permanently fence
provisioning and phase dispatch. A lost create is an unresolved intent: no
retry, account listing, prefix discovery, same-name adoption or guessed deletion.
Retain known exact resources for separately authorized cleanup. Unknown phase
work is never replayed. Stop, expiry, endpoint disablement, sleeps or later
SELECT success do not cancel previously submitted SQL.

## Cleanup, residuals and revocation

Apply every condition of the accepted #0157 exception:

1. Retain the successful fresh-D1 receipt and exact UUID; verify candidate binding,
   exclusively synthetic data/credentials and absence of production data/history,
   real Flickr access, shared bindings, routes, schedules, service consumers or
   external production references.
2. Durably fence dispatch/provisioning and preserve journals and evidence outside
   fixtures, accounting for all known/unknown submitted work and reservations.
3. Disable the owned Worker by returned immutable ID and verify it; confirm
   non-forced deletion and independent exact-ID absence before D1 disposal.
   Unknown or drifted Worker closure retains its D1.
4. Use separate exact cleanup authority for ordinary deletion of the acknowledged
   D1 UUID within original remaining budgets/deadline. No `unsafeDelete`, force,
   name selection, broad recovery or unrelated resource is permitted.
5. Preserve D1 deletion acknowledgement and independent exact-UUID absence.
   Lost deletes remain unknown pending separately reviewed exact observation;
   absence alone cannot authorize mutation replay. Preserve successful receipts
   independently so an already absent Worker need not be recreated or rediscovered.
6. Report resource disposal separately from phase/query outcomes. Unproved SQL
   settlement/cancellation stays unknown after disposal; disposal proves neither
   business completion, physical backup erasure, global quiescence nor production
   conformance. Unresolved outcomes preclude complete qualification or verified
   cleanup claims.

A cleanup-only continuation uses the same journal and separately reviewed
plan-bound authority; it cannot resume provisioning/phase dispatch or replenish
budgets. At exhaustion or unresolved identity/closure, hand off exact known
identities, unresolved intents, remaining reservations, owner and next decision
privately. Do not infer recovery authority from available budget.

After authorized cleanup, or immediately on emergency stop when required, the
named revocation owner independently revokes the management grant and retains
sanitized provider confirmation. Probe expiry, local credential-reference
removal and loss of a delivery file do not revoke it. If revocation prevents
cleanup, preserve residuals and never regain dispatch to finish. Credential-file
removal follows the approved private custody procedure; do not claim secure
erasure or provider revocation from local deletion.

## Source handoff and later decision

The parent records final source revision, closure/packet digests, focused tests
and independent review after integration. Any private packet and actual action
sheet remain separate evidence. Source completion changes no historical #0134
disposition and supplies no actual provider receipt. A later #0134 decision may
approve, decline or defer one exact completed private plan; #0122 owns any
subsequently authorized hosted run.

Production Album scheduling, real Flickr credential use or transport, image
upload, native Lightroom operation, restore/reconciliation, controlled trial and
capability activation retain their separate gates. Hosted-only scope assumes
no native permission. Keep all production capability flags false.
