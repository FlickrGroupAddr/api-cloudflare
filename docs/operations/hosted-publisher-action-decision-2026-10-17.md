# Hosted publisher action decision — 2026-10-17

Status: **OWNER DECISION PENDING; NO-GO for hosted execution.** This #0134
packet identifies the completed #0121 offline candidate and the exact limits
of a proposed disposable synthetic run. It records no owner consent. The
hosted endpoint, finite hosted client, provider lifecycle operator, exact
resource overlay and reviewed delivery procedure remain missing. Approval of
the scope below alone cannot make those components executable or reviewed.

The controlling accepted architecture and the source closure are linked from
[the #0121 qualification packet](hosted-publisher-qualification-packet-2026-10-17.md).
This is a decision aid, not an amendment to those contracts. Completed #0121
remains completed preparation; #0122 remains unexecuted. Production publishing,
real Flickr requests, credential retrieval, image upload, native Lightroom
operation and production activation are outside this decision.

## Exact candidate and retained evidence

The final private evidence is retained outside Git under workspace
`private-evidence/0121/publisher-aca532af6d57-source` and
`private-evidence/0121/publisher-aca532af6d57-optimized-3`. Hashes below are
SHA2-256; source-artifact digest and manifest-file digest are distinct.

| Identity | Exact value |
| --- | --- |
| Source commit | `aca532af6d570125c5d8bbcbd6ac1b4a10ae74f7` |
| Source closure | 113 files; `sourceCommitExact=true` |
| Source-artifact digest | `718b3dd7e1ec669c7e043f4c3a37142ceaad42a5bd3bcbc0639868a2b1e5aed1` |
| Manifest raw-byte digest | `f3ce7b2ba3cded646c825a6435a7217db742f226927f3633ae6ea61bc52a26c8` |
| Optimized `worker.js` | 652,967 bytes; `b2241f88c94ec6561b2a902a5561bf9f63459e420fbd111861db1636feb2a26f` |
| Disabled qualification config | `c22298581a4d1586c0861dd8609cde4c219c70f8d1d9244e5fdc7e250ebdfe28` |
| Disabled production config | `98379c9b23a441ea083d2433ef0992616b98465266689011edbf3adbce7fe4df` |
| Package lock | `6894a3dcecffb784baae9751677b0c231250ae9e99a2cb6ddacc6011a0dc0048` |
| Compiler metafile | `d9333652e1b1d0bf04b0fdceb308cbae55a2ed5dbd6f99f426845b0b5bc9afc3` |
| Compiler network guard | `a373763b350c637593c6dec0027f01ddf6fde6c7d836df58430cd2d9d878ee1d` |

`final-artifact-receipt.json` binds those identities to the retained optimized
bytes and reports 27 runtime tests passed, zero failed/skipped, using those
same bytes. Its runtime-log digest is
`c91d65af87dbc5eaace8ed1ca48980f3c86c21a2821c92d62991933097c2b5c7`.
Two compiler audit entries report zero blocked network attempts. These are
local receipts, not hosted attestations. The declared build tools are Node
24.22.0, Wrangler 4.116.0 and locked esbuild 0.28.1; the source packet also pins
npm 12.2.0 and native TypeScript 7.0.2. Hosted compatibility date 2026-10-16
does not erase local Miniflare's separate 2026-07-30 runtime date.

The sealed authorization template remains `granted=false`, with no owner,
expiry or resources and all action permissions false. No implementation
consumes it as authorization. Keep immutable packet contents unchanged;
retain new overlays, decisions, secrets and receipts separately.

## Proposed finite scope for Terry's decision

The recommendation is to finish and independently review the missing hosted
operator and delivery mechanism, then seek action-time approval of their exact
bytes, identities and schedule. Terry may accept this bounded scope in
principle now, defer it, or decline it. A scope decision is not action-time
permission to create, deploy, request or delete resources.

The action-time decision must explicitly name four isolated pairs:

| Case | New Worker / new empty D1 | Purpose |
| --- | --- | --- |
| `happy` | Pair H; identities not allocated or authorized | Normal finite HTTP/Album sequence |
| `create_lost` | Pair C; identities not allocated or authorized | Synthetic create effect then lost reply, no replay, explicit repair |
| `attachment_lost` | Pair A; identities not allocated or authorized | Synthetic attachment effect then lost reply and fresh read recovery |
| `title_lost` | Pair T; identities not allocated or authorized | Synthetic title effect then lost reply and fresh read recovery |

These labels grant no prefix-based authority. For each pair, record exact
account context, Worker name and deployed version, D1 name and actual UUID,
endpoint, resource label, run ID, scenario, start/expiry, reviewed overlay
digest and cleanup owner in a private action sheet. Never substitute an
existing database, reset a previous target or reuse a pair for another case.
Apply only migrations 0001–0026 to each new empty D1 and retain schema and
migration identity. The candidate creates its own probe control/data tables.

Each case runs `seed`, `http`, `materialize`, `attach`, `title`, `remove`,
`finish` once, in that order. Requests are empty-body POSTs to
`/__publisher/{phase}` with no query. Only the closed scenario set above is
allowed. Synthetic responses and signing material stay in memory; no image
upload or real Flickr transport is permitted.

| Budget | Per case | Four-case ceiling |
| --- | --- | --- |
| Provider resources | One Worker and one new D1 | Four pairs / eight resources |
| Hosted client requests, including negative cases | At most 32 | At most 128 |
| Accepted phases | Seven | 28 |
| Synthetic handoffs | At most 16 per phase / 112 per case | At most 448 |
| Synthetic POSTs | At most one per phase / seven per case | At most 28 |
| SQL work | At most 256 calls per phase; batch width at most 128 | Same per-phase guard on all 28 phases |
| Phase execution | 60 seconds; failure sealing adds at most 500 ms wait | No parallel phase or automatic retry |
| Empty streaming body check | 500 ms | Applies to each request with a body stream |
| Access window | Absolute expiry no more than 30 minutes ahead | At most 120 minutes combined windows if sequential |

The 256-call guard bounds the `runPhase` database wrapper; it is not a published
total count of D1 rows changed or a whole-provider billing ceiling. Control
reservation/completion/sealing statements are additional wrapper work. The
finite client's 32-request ceiling must be implemented and reviewed: it is
currently a plan, not a host-side request counter. The separate 64-request,
30-second default-off diagnostic is not the hosted request budget.
The 60-second phase clock starts after the separate body check; neither it
nor the failure-seal wait guarantees that submitted D1 work has finished.

No complete create-to-delete lifecycle wall-clock deadline is implemented.
The action-time sheet must add finite provisioning, readiness, dispatch,
drain/inspection and cleanup deadlines, with an exact-resource cleanup handoff
when they expire. Do not infer that four access windows authorize unattended
resource retention or 120 minutes of arbitrary provider operations.
New provider-assigned IDs need an explicitly approved staged creation and
verification seam: consent must define exact intended names and bounded create
actions, then bind returned actual IDs before migration/enablement. It cannot
pretend those IDs are already known or authorize broad account discovery.

## Configuration, delivery and actual driver readiness

The retained configuration is deliberately disabled: `PROBE_ENABLED=0`,
zero D1/resource UUIDs, empty access/artifact/run/expiry values,
`workers_dev=false`, `preview_urls=false`, and no route, cron, Durable Object
or Secrets Store binding. It provides no reachable disposable endpoint.
Changing those bytes requires a separately retained and reviewed exact overlay;
the disabled-config hash cannot attest the enabled deployment.

The actual executable driver in `runtime.test.mjs` uses local Miniflare
`dispatchFetch`, direct local D1 migration setup and an outbound rejection
hook. It is not a hosted client, deployment operator, schema installer or
cleanup driver. The final bundle is buildable, but no reviewed executable
path presently provisions the four pairs, delivers access material, exposes a
finite endpoint, checks deployed identities, dispatches the capped request
plan, collects sanitized receipts or performs bounded cleanup.

Before action-time consent, the operator must make these steps concrete:

- Verify both retained source digests and the exact optimized Worker bytes;
  deploy those bytes without an implicit rebuild or source drift. Pin the
  overlay, migration bytes, operator/client bytes and installed tool receipts.
- Select and review one disposable reachability mechanism. It must name the
  exact endpoint and its access/disable/cleanup lifecycle without adding a
  production domain, route or binding by implication.
- Define a private, reviewed delivery procedure for a fresh 64-lowercase-hex
  access token per case. Supply it as the intended private Worker binding and
  matching `X-Probe-Access` request header without source commits, command-line
  exposure or logging. The current sealed config's variable slot is not a
  secret-delivery implementation. No secret has been read, checked or created
  for this packet.
- Bind `PROBE_ARTIFACT_SHA2_256` and `X-Probe-Artifact` consistently to the
  reviewed source-artifact digest above; bind `PROBE_RUN_ID` and `X-Probe-Run`
  to a fresh 64-hex run ID. Record the separate deployed Worker-byte digest.
  Supply the nonzero resource UUID label, matching header, exact scenario and
  expiry. `PROBE_RESOURCE_ID` is a caller-supplied label; the candidate does not
  prove that it equals the actual bound D1 UUID. The operator must verify that
  mapping against the real deployed binding and retain its receipt.
- Confirm no production resource, account secret service, real Flickr
  credential, image, native catalog or production scheduler is connected.
  Bound operator/provider calls separately from the synthetic handoff budget.
- Implement request counting, deadlines, no automatic replay, stop behavior,
  response assertions, exact-resource census and sanitized receipt redaction.
  An unexpected provider egress, identity mismatch or external access stops
  the run; never turn a negative test into permission to continue.
- Enumerate the exact negative requests inside the 32-request ceiling and any
  separately authorized test mutations. Local tests manipulate D1 fixtures for
  fault/revision/rate/restart cases; the seven hosted phases do not reproduce
  all of that coverage. Rejected requests may still consult control SQL.
- Define least-privilege control-plane authentication and revocation without
  inspecting credentials during preparation. The probe's 30-minute expiry is
  not a provider-management token expiry or revocation mechanism.
  Name its separate revocation owner and retain provider revocation proof;
  deleting a local credential file does not establish revocation.

## Stop, cleanup and evidence

The candidate pins run/artifact/resource/expiry/scenario in a durable control
row. Atomic reservation requires the expected next phase, `busy=0` and no
terminal failure. Overlap, replay and changed bindings refuse. A failed phase
is terminal; failure sealing can leave `busy=1`, which also refuses replay.
Never edit/reset the row to retry. An absent or failed receipt is not success.

Stop first closes new endpoint access and prevents new dispatch. Expiry,
elapsed-time and abort checks limit subsequent SQL/handoffs but cannot cancel
a D1 mutation already submitted. Configuration disablement is not an active
revocation check inside a running phase. Retain stop time and final durable
markers; the operator must establish quiescence before cleanup. If it cannot
prove no operation remains in flight, keep access disabled/expired and hand
off the exact remaining resources rather than asserting cleanup passed.

Cleanup may delete only the exact consent-listed Worker and D1 UUID/name,
after verifying their deployed version/config/run identity and eligibility.
No broad listing/deletion, wildcard, prefix selection, name reuse or cleanup
of an unexplained resource is authorized. Retain deletion receipts and an
exact residual census. Cleanup failure retains disabled access and a named
owner/deadline for an identity-checked retry; it never turns into broad delete
permission. No provider create/deploy/delete request is made by this packet.

Receipts must bind candidate and overlay hashes, real resource identities,
scenario/run/expiry, migration head, deployed version, request/phase counters,
durable outcome markers, stop/quiescence proof and cleanup result. Keep
tokens, provider credentials, private identities and payloads out of tracked
evidence and logs. Sanitized phase outcomes may be public; private resource
identity and authorization evidence stays in the private action sheet.
Maintain an exact known/unknown resource ledger when create/delete responses
are ambiguous; reconcile the recorded identity before any retry. A run expiry
does not grant cleanup actions indefinitely. The owner decision must separately
bound any cleanup-only continuation after the probe window closes.

## Residual no-go gates and handoff

- Complete and independently review the hosted operator, finite client,
  endpoint mechanism, configuration projection and private access delivery.
- Fill the exact private action sheet, total operator/time budgets, resource
  identity verification, stop/drain and cleanup-failure handoff. Obtain
  Terry's explicit decision for those exact actions and window.
- Independently review the final candidate and lifecycle together; changes to
  source, bundle, overlay, client, operator or consent scope require renewed
  comparison and review rather than inheriting #0121's local pass.
- Run #0122 only after those gates pass, retaining hosted receipts. The four
  cases establish their finite synthetic outcomes only. Crash/lease/mutation,
  intake stop/restart, rollback, current-schema restore/reconciliation and
  hosted-runtime behavior remain required separate evidence where the
  qualification contract calls for them.
- Production Album scheduling and credential/transport composition remain
  absent from `src/worker.ts`; the isolated qualification entrypoint does not
  qualify production scheduling. Controlled trial, activation and native
  publisher qualification remain separate unpassed gates.

The later exact-run owner decision belongs on #0134 after the missing
engineering and review produce a concrete action sheet; no token or immediate
execution approval is requested now. #0122 retains its dependency and
stays NO-GO; a normal dependency is not an external Blocked-lane obstacle.
This packet supplies reviewable scope and explicit missing work, not consent,
a deployment recipe or a hosted qualification pass.
