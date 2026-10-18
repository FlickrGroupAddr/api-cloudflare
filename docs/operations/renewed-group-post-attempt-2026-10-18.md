# Renewed finite synthetic POST attempt

Date: 2026-10-18. Ticket #0161. Status: reviewable offline preparation;
**actionReady: false; nativeRouteReady: false; productionQualified: false**.

The concrete next step is independent review of the supported screenshot-based
controller, new exact runtime caller and later action packet. This packet is not yet
ready for an action-time approval request. No credential, provider or native
operation was performed by this preparation.

## Fresh identity and sealed evidence

The new proposal is `0a8b92d40ed1466fa7de82c1`. Its proposed resource names are
`fga-post-src-0a8b92d40ed1466fa7de82c1`,
`fga-post-recv-0a8b92d40ed1466fa7de82c1`, and
`fga-post-db-0a8b92d40ed1466fa7de82c1`. Exact absence, returned resource identity,
creation journal and same-owner verified teardown remain execution requirements.

The stopped #0060 attempt `c01ba6d2c2754597aa311c9f` remains terminal. It recorded
zero actual native input and zero of 23 measured cases. Its consent was consumed
and its token revoked/deleted; no identity, deadline, consent or credential from
that attempt is reusable. Preserve its stop latch and evidence unchanged. The
[original result](group-post-native-result-2026-10-17.md) remains historical.

The [#0160 rehearsal](group-post-dispatch-rehearsal-2026-10-18.md) proved its
recorded real file roundtrip with fake Sky input only. Its sources and
`dispatch-manifest.json` remain sealed. The new
`probes/group-post-characterization/renewed-manifest.json` pins that exact
manifest separately and pins this packet, the
[new runtime caller](../../scripts/renewed_group_post_attempt.py),
[new preparer](../../scripts/prepare_renewed_group_post_attempt.py) and
[new native controller](../../scripts/group_post_native_dispatch.mjs).
The preparer independently pins the #0160 manifest digest
`f00a330f03dd562a9203905a4c20903e4a542f94a8b0ba9e565a7c52f678ac1b`
and validates its full unchanged transitive source closure. Rehashing modified
sources creates a new review proposal and grants no permission.

## Exact private preparation boundary

The proposed run root is
`C:/Users/TDO-XPS15-2024/Documents/ChatGPT/FGA/.coordination-runs/renewed-group-post/0a8b92d40ed1466fa7de82c1`.
Only its `handshake` directory is the proposed coordination root. Its proposed
`private/config.json`, `private/approved-packet.json` and
`private/operator-token.txt` are fresh paths. The immutable fixture's native
root remains `C:/Temp/FGA-group-post-v1`; retaining that interface does not
establish marker freshness or authorize cleanup of prior files.

Run from the API repository:

```console
uv run --frozen python -m scripts.prepare_renewed_group_post_attempt
```

This verifies source pins and prints public proposal metadata only. Optional
`--prepare` exclusively creates fresh ungranted templates and refuses an existing
run root. It creates no handshake, token or native file. An interrupted
preparation is retained rather than reused. The preparer reads no runtime,
credential, account provenance or photography data and makes no network request.

Its closed configuration adds `actionDeadlineUnix`,
`tokenRequirementsConfirmed` and `actionScopeSha256` to the #0160 configuration
shape. Templates leave the account/subdomain empty, deadline null, token
requirements false, action scope blank and both consent flags false. A future
exact packet must bind the action scope to this packet's exact SHA2-256 bytes
and bind approval to the exact manifest/configuration bytes. The validator returns bounded configuration only after exact account, future
deadline, token-requirements, action-scope, source, configuration and approval
bindings pass. Flags and hashes do not establish human authorization or actual
route readiness. Default ungranted templates fail validation.

## Native route engineering gate

The existing #0160 controller requires the exact command in the observed
accessibility tree and accepts only `elementIndex`. Earlier Lightroom menu
observations did not expose usable accessibility indexes; they used screenshot
coordinates. Fake accessibility trees, guessed indexes and replayed screenshot
IDs cannot bridge this gap.

The new standalone controller offers a bounded screenshot-coordinate route
through supported Computer Use calls. It retains correlated owner checkpoints,
one durable attempt before input, one input, immediate refresh and
acknowledgement, persistent no-replay state and terminal uncertainty/stop handling.
Its exact exported interface and enforced screenshot/coordinate checks are
owned by its source. It never initializes Sky, selects a host, discovers a menu
or derives an input from a file. Synthetic tests prove only these source gates.

Before live readiness can be asserted:

- Independently review the new source closure and its fake-boundary tests.
- Resolve a finite supported observe/inspect/one-input route for the actual
  Lightroom Classic host and exact fixture command. An accessibility miss is
  not permission to invent a tree or click without inspection. Actual-host
  observation itself requires the applicable native authority.
- Prepare the actual in-memory supported observation and action cells before
  any provider lifetime. Keep private screenshots, trees and catalog details
  out of public artifacts. No UI polling/watch loop is permitted.
- Independently review the new exact runtime caller, including the prepared
  controller and the same attached Python cleanup owner. The sealed #0160 apply
  command validates its own different identity and is not this attempt's caller.

On 2026-10-18 the primary performed a separately authorized read-only host
inspection. Lightroom Classic reported version 15.6, build
`202609251514-f839cde9`. Genuine main-window screenshot coordinates opened
About, Help/Extras and Library File/Extras. Both Extras routes reported no
commands defined: the characterization fixture was absent. This inspection
loaded no fixture and used no network or token. It demonstrates only the
observed navigation route and host version; it does not qualify the new
controller, establish the exact fixture command, measure POST or approve fixture
installation/load/input.

This preparation leaves actual execution **NO-GO** until the independently
reviewed exact packet and fresh action-time authorization are complete. After an
initial automatic approval review rejected the runtime source addition, Terry
explicitly approved implementing and synthetically testing execution-capable
source, including a token-loading path reserved for a later separately approved
run. That source-only authorization does not permit actual credential reads,
provider operations, fixture load or native input this turn. Actual-host
navigation and source tests cannot establish exact fixture invocation, native
POST behavior or action permission.

## Concrete caller and finite deadline

The new [runtime caller](../../scripts/renewed_group_post_attempt.py) imports the
sealed #0160 `NativeFiles` protocol and original provider lifecycle unchanged.
Its short composition is separate because the old apply entry point owns a
different run and packet. It accepts only this exact fresh run and coordination
root, waits for the prepared screenshot controller's correlated readiness before
provider work, retains one attached owner through remote teardown, and records
handoff observations separately from measurements using the sealed lifecycle.

The caller's `--apply` accepts only this run's exact `private/approved-packet.json`
and an independently retained `--approved-sha2-256` value. It validates the full
source/configuration/approval binding before opening the exact bounded token
file. It accepts no source code, endpoint, command or UI action from a file.
The approval digest must be supplied only after the later applicable human
decision. This document and source implementation permission do not supply it.

`actionDeadlineUnix` is the reviewed absolute resource-lifetime boundary. At
packet validation and execution entry, between 1,230 and 1,800 seconds must
remain. The additional 30 seconds reserves the finite readiness wait; after
readiness at least 1,200 seconds must remain before any provider request. A
local admission adapter also enforces that bound on every lifecycle clock read
before its first provider call, including initialization after public manifest
I/O, and rechecks immediately before that first call. This prevents preparation
time from pushing the lifecycle's resource expiry beyond the reviewed bound.
The adapter also verifies the underlying account against the exact approved
account at lifecycle identity reads and immediately before delegation, retaining
account-change rejection across readiness and later requests. After admission
the unchanged lifecycle owns its relative expiry and cleanup; deadline admission
does not block teardown. The owner deadline is also no later than that bound minus the 240-second cleanup
reserve. Expiry or insufficient time refuses progress, with owner closure when
already claimed. The original resource expiry, cleanup reserve and provider
request budgets still govern. This is bounded admission and cleanup scheduling,
not a hard wall-clock interruption guarantee for an in-flight socket or abrupt
process death.

The dry-run projection is:

```console
uv run --frozen python -m scripts.renewed_group_post_attempt
```

It checks only the public source closure and opens no private configuration,
credential, native marker or provider connection. No actual `--apply` is
permitted by this preparation turn.

## Missing action inputs and later decision

The primary must first finish the engineering gate above and independently
source the following private inputs; empty/default templates supply none:

- Exact account/subdomain provenance, fresh run/resource absence and retained
  source/configuration/approval digests.
- A finite action-time UTC deadline, fresh temporary token scope/expiry,
  delivery path, effective permission verification and revocation owner.
  `tokenRequirementsConfirmed` must describe reviewed requirements; it is not
  a token check or authority to acquire a token.
- Terry's fresh explicit decision covering this exact cloud/native scope,
  fixture registration/load, one Library command, separately applicable final
  Case cancel and local/UI cleanup. Resolve the earlier Escape withdrawal
  explicitly; no earlier approval carries forward.
- Applicable native marker archival/cleanup authority, freshness observations
  and exact receipts. Never erase evidence simply to make freshness pass.

Only after concrete preparation and independent packet review should the primary
present the exact action and credential requirements to Terry. Until then the
engineering work stays distinct from an owner-decision handoff.

The proposed finite scope retains the original 23 synthetic POST cases, one
input/no replay and Escape boundaries, 30-second dispatch request, 1,200-second
resource lifetime, 240-second cleanup reserve, 120-call provider budget and
20-second socket timeout. The unchanged #0160 owner cutoff is 960 seconds. A
new caller enforces the absolute action deadline as described below. Any scope or budget change
requires separately reviewed exact acceptance. No production, Flickr,
real-photo or catalog-writing action belongs to this proposal.

Retain the same attached owner through remote teardown; resource deletion does
not revoke a credential. Separately establish revocation and exact token-file
removal under applicable authority. Native registration and local/UI cleanup
have separate authority and remain deferred after Escape. Unknown cleanup is
`cleanup_unconfirmed`, never inferred success or eligibility to retry.

Report request/attempt/acknowledgement/actual input separately from terminal and
receiver case observations. Failed, stopped and unmeasured cases remain so.
Independent method-specific result/policy review remains required before #0061
or another adapter consumes any future result; a negative result cannot qualify
POST or enable group additions.

## Source verification

The focused synthetic suite is
`tests.test_prepare_renewed_group_post_attempt`, plus the native controller's
source tests. Required checks include sealed-closure preservation, fresh exact
identity/path sets, ungranted/no-overwrite templates, duplicate/extra-field and
changed-digest refusal, expired/invalid deadline refusal, token-read fencing before validation and
provider fencing before readiness/deadline checks. Test results and independent review are
recorded separately against final bytes. This procedure records no test pass,
provider behavior, native qualification or authorization by itself.
