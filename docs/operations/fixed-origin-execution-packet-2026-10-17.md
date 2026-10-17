# Fixed-origin execution packet review

Date: 2026-10-17. Ticket #0044. Status: review-ready offline packet inventory;
**NO-GO for execution and promotion.** This is an evidence and gap report, not
an accepted architecture contract, deployable configuration or live runbook.

The reviewed preparation baseline is API commit
`dc7234ac59eda9acc74972268296abbc251efae8`. Its ordinary dispatcher is the
unchanged #0036 captured module, while its synthetic qualification branch
executes the separately approved candidate
`b599ca828d2a645b686aca0354d6c8ee2c2a0250`. These are different artifacts.
The accepted architecture authority index is
`architecture-design/docs/README.md`; accepted ADR0061 and the accepted
non-destructive existing-photo boundary control preparation. The hosted-thumbnail
candidate remains Proposed. Neither this review nor completed preparation cards
accept that candidate or authorize production, provider-preview or native work.

## Disposition and required next work

- #0037 remains **unqualified**: supported effective-path allocation,
  provider-response bounds and credential redirect protection are unresolved.
  Native complete-body returns and process-memory samples cannot close them.
- #0043 remains **negative/open for exact provider restoration**. Its byte-exact
  private packet and local rehearsal pass within their offline scope; provider
  retained-version/changed-secret semantics, current edge/configuration,
  production state and both paused durable gates remain unverified.
- The temporary Worker upload, full deployment/configuration diff, receiver
  entrypoint/configuration, concrete resource identities and integrated finite
  execution schedule do not yet exist as a reviewed deployable packet.
- The five required route-conformance phases have not passed for either the
  temporary composition or exact captured rollback configuration. The existing
  routing fixture and VM refusal comparisons are insufficient substitutes.
- Bot can prepare the missing exact adapters, schedule and finite evidence
  definitions offline. No new owner design choice is identified by those
  engineering gaps alone. #0045 must receive a complete concrete packet before
  resolving any specifically uncovered live scope. No blanket approval request
  follows from this report.

These gaps prevent an execution-ready acceptance claim. Preserve false
`deploymentAllowed`, `providerRestorationVerified`,
`changedSecretSemanticsVerified`, `productionStateVerified`, hosted/native
qualification, feasibility-change and release capability fields.

## Exact source and proposed deployment delta

The capture's decoded exact-version module is 445699 bytes, SHA256
`f1cef97fe6e1e62b5ff2b57f7e11516423974e756011750feb1aebe3abb13e6d`.
Its 25 registered ordinary routes produce 401/404/404 on the three intended
read paths; it has no existing-photo discovery or thumbnail handler. It remains
both the ordinary dispatcher and rollback artifact. The private captured
active-version/weight map selects one retained version at weight100. Resolve
identities from its verified private index; never publish them or select latest.

The b599ca8 archived unchanged candidate bundle is 601051 bytes, SHA256
`c1edd7e5e721119030085c9c0705de5d2f3a32b9cffc6bbed56f363df3432e36`.
`prepare_fixture.py` verifies archived source/migration hashes before actual
VM/SQLite handler execution. The wrapper/lifecycle/native sources below belong
to dc7234a; the current API tree's later implementation changes do not silently
change this pinned candidate or qualify a newer production build.

| Proposed field | Reviewed boundary / unresolved concrete artifact |
| --- | --- |
| Existing deployment | `fga-api`, whole-host `https://flickrgroupaddr.com` attachment retained |
| Ordinary branch | Original Request/environment delegated to exact captured default fetch |
| Qualification branch | Closed constructor composition of captured dispatcher, b599ca8 candidate, isolated D1, durable quota and exact receiver binding |
| Production bindings/settings/assets | Preserve captured references and bytes; no production data/schema, secret value/generation or object lifecycle change |
| New binding names | `FIXED_ORIGIN_DB`, `FIXED_ORIGIN_RUN`, `FIXED_ORIGIN_CAPABILITY`, `FIXED_ORIGIN_CANARY`, `FIXED_ORIGIN_RECEIVER` |
| Effective edge | Preserve captured domain/routes, Page Rules, ruleset descendants, cache/redirect/transform/firewall/challenge/settings inputs; fresh finite readback required |
| Final upload/configuration | Missing exact bundled module, hash, entrypoint wiring and complete baseline-to-temporary configuration diff; local template is not deployed evidence |

The source composition is a factory, not a deployable provider entrypoint.
The proposed receiver service binding must select only the exact new receiver.
No new DNS/route/hostname, Durable Object, queue, Secrets Store, OAuth grant,
Flickr identity, application public seed endpoint or real upstream fetch belongs
to this delta. Existing paused production intake/dispatch flags and both durable
write gates must remain paused; synthetic gate observations cannot prove this.

Source SHA256 inventory (paths relative to API repository):

| Source | SHA256 |
| --- | --- |
| `probes/fixed-origin-isolation/wrapper.mjs` | `a894a7f94a3c18dc094057109eab80319cc3b9ceaaef430270ab89d939617ba9` |
| `probes/fixed-origin-isolation/edge_faults.mjs` | `a48e008298cd3b68329bb6577a638657baf84f2f78b886eacab2c1b281d4ffa1` |
| `probes/fixed-origin-lifecycle/composition.mjs` | `95f476064fc41ada338a8ce80d2a8fe7b135f4a9174248fa697b3fdb33e55cf8` |
| `probes/fixed-origin-lifecycle/handler_cases.mjs` | `cb41173c4fa6b1fcbfb7f8fa2a98b4669568ef9c89d10586438f5796cf916ebb` |
| `probes/fixed-origin-lifecycle/quota_receiver.mjs` | `6293ff60e22300cf1082d9c7243d541f7079348735f7fe16f77fbcd087dcf583` |
| `scripts/fixed_origin_lifecycle.py` | `452086d17541eea904c50c18dd810cd597e200fca278404636b84420a75816d9` |
| `scripts/fixed_origin_restore.py` | `e00a4722e7fdbac4e00242d3ead056de88175bd85987f929f1e39add71d02a4b` |
| `scripts/route_conformance.py` | `85ed64f345fc3f61f0997582f5f826847c9a2a817526bd4f51e17468f7a5b5b9` |
| `probes/lightroom/FGA-FixedOrigin-v1.lrplugin/Info.lua` | `c77afca644fce2b0caf87ad709a5c6e73cbc70f496aa30d3efb71a5f1f2c3592` |
| `probes/lightroom/FGA-FixedOrigin-v1.lrplugin/Config.lua` | `0fe3ad66742ee498c179fd145ba0f2979d05ab262bca9d8295d23d98b3d5a2ca` |
| `probes/lightroom/FGA-FixedOrigin-v1.lrplugin/Qualification.lua` | `db255cfcd811b0b0854c9505a5d47cc37034f0238cc1a450d3fcde9ad3157c90` |
| `probes/lightroom/FGA-FixedOrigin-v1.lrplugin/Run.lua` | `fdee54f1396f00a1ad8f052ccb9f18a15fc60d92c7e7341cdb2730f22e4f1c20` |
| `clients/lightroom/FGA-LrC15.lrplugin/ConnectionCore.lua` | `a4934ea22bf6c24be0a6df8e47f095c75d1a251bdb65ef6c8f7a96ba72bdfd0e` |
| `clients/lightroom/FGA-LrC15.lrplugin/ExistingPhotoClient.lua` | `2fcd68afae4f933ce83e25aa4cf8c734971f25a5ae12855c23c6f3f68bcfdc54` |
| `clients/lightroom/FGA-LrC15.lrplugin/SharedReadTransport.lua` | `b91120ac2f27eb4c3a1e31f4d1be04cc9c425595ff2be9f05be37c94fc915007` |
| `clients/lightroom/FGA-LrC15.lrplugin/dkjson.lua` | `197cb50834c642f84b4cf99fe724932c50e6d9c92faec7ad89aa25e91df4d481` |

The full dc7234a tree binds remaining transitive source and test inputs. This
selected source inventory does not replace a final bundled-module/configuration
manifest or the archived candidate's per-input verification.

## Finite inventory, selectors and budget

One fresh 32-lowercase-hex run identifies all resources and selectors. Exact
future values/IDs remain uninstantiated: this packet creates no target/secret.

| Item | Exact template / lifecycle |
| --- | --- |
| Synthetic D1 | `fga-fixed-origin-db-{run}`; fresh exact ID privately acknowledged |
| Receiver Worker | `fga-fixed-origin-recv-{run}`; own workers.dev endpoint, no production resources |
| Temporary Actions secrets | `FGA_FIXED_ORIGIN_CAPABILITY`, `FGA_FIXED_ORIGIN_CANARY`; each must be absent, created once, removed only with acknowledged ownership |
| Ephemeral capability/canary | Fresh 64-lowercase-hex synthetic values; never real installation/OAuth credentials; private target/used-target only |
| Durable quotas | 96 combined FGA admissions and 16 combined receiver/report admissions; no retries |
| Lifetime | At most 600000 ms inner qualification from common start; 1200000 ms outer lifecycle; latter half is cleanup reserve |

The model checks absence separately from create for the fixed global Actions
secret names. A future provider adapter/ownership protocol must prevent an
intervening operator's secret from being overwritten between those operations
and establish exact owned cleanup. A name-absence preflight and local exclusive
journal marker alone do not establish provider-wide exclusion. This remains an
implementation prerequisite, not evidence of safe provider create semantics.

Every same-origin receiver/report forwarding consumes FGA admission before
receiver work, then the receiver's shared 16 budget. Expiry/quota/cancellation
are checked before fixture work and again before publication, including after
awaits. Expiry disables useful admission; it never proves restoration/deletion
or bounds unsolicited provider traffic and billing.

`handler_cases.mjs` and `Config.lua` own the closed path/case matrix. Exact GET
paths are installation-current, discovery page1/page_size1, and photo thumbnail
page1/page_size1/linked_flickr_revision1; browser mode adds the two page_size2
pages and three corresponding photo1/photo2/photo3 thumbnails. Unknown selector
headers, origins, paths/query spellings, body/framing, methods and expired or
aborted requests fail closed. `ok` aliases `png`; `invalid-auth` aliases
`bad-auth`. These aliases add no independent observations.

| Matrix class | Finite cases / expected boundary |
| --- | --- |
| Success | `png`, `jpeg`, `exact-limit`: 200; valid synthetic image, at most 262144 bytes |
| Upstream refusal | `declared-excess`, `undeclared-excess`, `upstream-error`, `truncation`, `wrong-media`, `wrong-signature`, `redirect`, `stall`: 503 sanitized application errors |
| Admission input | `missing-auth`, `bad-auth`, `bad-query`: 401, 401, 400 |
| Final authority | `final-installation`, `final-link`, `final-grant`: 401, 409, 409; no publication |
| Foreign/private data | `foreign-identity`, `private-photo`, `foreign-destination`: 503 before image fetch |
| Post-handler redirects | `edge-redirect-301`, `-302`, `-303`, `-307`, `-308`: those exact codes, empty body; fixed same-origin receiver path for run/code |
| Other final stimuli | `edge-wrong-media`, `edge-malformed-png`, `edge-truncated-png`, `edge-declared-excess`, `edge-undeclared-excess` |

The actual-handler oversize fixtures are fixed 262145-byte inputs. Its upstream
error is HTTP 502 with a fixed 22-byte marker body; its upstream redirect is
HTTP 302 with that same marker body. Its stalled body is fixed at 16000 ms.
The edge cases first execute the compliant handler, then inject a distinct
stimulus. Final excess is exactly 262145 bytes. Receiver destinations are
`/api/v001/existing-public-photos/photo/thumbnail/qualification-receiver/{run}/{code}`;
the gated aggregate report is `/report/{run}`. They are qualification-only path
reservations, not evidence of a cross-origin redirect experiment. Actual
provider/native preservation or rejection of malformed Content-Length is unknown.
The handler collector's 4096-byte denial ceiling does not cap provider errors.

**Schedule gap:** source offers twenty handler cases plus ten edge cases, but a
native fault invocation performs three PNG preflight requests before its selected
thumbnail. All thirty therefore require at least 120 FGA admissions, before
receiver/report and browser/cancel/stale observations, exceeding 96. The native
used-target rule also refuses a second target for the same run. No integrated
single-attempt ordering/target plan covering these observations exists. Do not
increase quota, reuse a consumed target, reset namespaces, silently omit required
cases or infer authority for extra runs. Resolve the exact required observation
subset versus offline-only matrix and the once-only execution design before
claiming a finite executable schedule.

## Native entrypoint and measurement boundary

`FGA-FixedOrigin-v1.lrplugin` is separate major15 source for LrC15.6/SDK15.3.
It is unregistered and has not been loaded or invoked for this packet. Its
closed <=16 KiB target binds eight source SHA256 values, Worker/configuration
SHA256, one run/case/mode and <=600-second UTC interval. The synthetic credential
stays in memory; no SDK secure store/catalog is imported. Verification/discovery
select PNG preflight; only the exact fault thumbnail selects its stimulus.

The SDK documented GET returns a whole body. Requested 30/15-second timeouts
are connection-phase observations, not monotonic total deadlines. Cancellation
is cooperative after yielding GET; no native GET abort handle is claimed.
Native image rendering/human page confirmation, Next/Previous/Cancel,
stale-result refusal, owned-cache deletion and backend abort/disconnect require
separate actual observations. SDK parsing and fake network delivery prove none
of allocation, redirect credential protection, provider cleanup or host decoder
behavior. Keep native terminal receipt distinct from remote restoration/deletion.

## Ordinary path, restoration and cleanup barriers

Qualification uses an explicit isolated environment and static synthetic fetch
seam; no production environment enumeration/read, real bearer or network fetch
is admitted. Ordinary delegation retains original Request and environment;
existing tests compare refusal outputs and object identity. The captured
rollback's 25 VM route comparisons cover unauthenticated refusal behavior.
They do not cover authenticated ordinary reads, assets, scheduled work, secrets,
background data changes or live effective routing. Reserve-path interception
must be included in the final explicit configuration/behavior delta.

The [restoration protocol](fixed-origin-restoration-2026-10-17.md) owns detailed
rollback semantics. Before any future installation, refresh the complete finite
capture and privately compare retained version/weight/module, production binding
and resource continuity, edge inputs and both current paused durable gate
values/revisions. Drift requires a fresh capture and review. Synthetic provider
cases A/B must independently establish unchanged-state restoration and changed-
secret refusal/drift semantics for every captured secret-binding type. They are
separate proposed resources/operations; their exact inventory and authorization
are not included in this fixed-origin run's one-D1/one-receiver inventory.

Cleanup must durably disable and inspect admission first, then perform one
latched nonforced deployment of the exact retained weight100 version, with
`force=false`. Independently verify active version/module/configuration, no
qualification bindings, ordinary authenticated safe reads/effective edge,
unchanged production facts and paused gates/revisions. The finite authenticated
probe definitions and bounded consistent production-data proof remain missing;
row counts and synthetic snapshots cannot substitute. Existing background work
must be accounted for under its own authorized mechanism.

Only after those acknowledgments may the lifecycle delete this run's acknowledged
Actions secrets, exact receiver and exact D1, and verify absence. Remove only
matching-run private targets/used-targets/ephemeral material and native cache.
Preserve captures, production resources and unrelated secrets. Unknown creates,
lost acknowledgments, failed disable/restore/readback/delete and crash owner
markers retain private identities and `cleanup_unconfirmed`. Never retry an
ambiguous mutation, force rollback, guess identities or auto-remove an owner
marker. The current lifecycle is an offline seam and its CLI refuses live use.

## Required verification phases and actual evidence

The accepted architecture `docs/operations/http-route-conformance.md` requires
all five phases for the **exact temporary artifact and rollback configuration**:

| Phase | Current packet evidence / remaining gap |
| --- | --- |
| 1. Compiled inventory validation | Candidate's generated projections and source tests passed previously; no composite inventory binding captured ordinary routes plus reserved qualification routes |
| 2. Exact configuration projection | Factory/source isolation checks exist; final development/deployment artifacts and exact effective-edge delta absent |
| 3. Development HTTP black box | VM handler/refusal tests exist; actual built temporary/rollback topology HTTP matrix not established |
| 4. Same-build isolated public HTTPS black box | Not run for these artifacts; no provider action in this task's authority; exact isolated inventory/mutation/cleanup scope must be reconciled before execution |
| 5. Artifact binding | Baseline/candidate/capture digests available; no final build/inventory/dev-router/deploy digests plus opaque preview deployment ID/pass time |

`scripts/route_conformance.py` generates `probes/routes/worker.ts`, an isolated
routing-proof fixture, with distinct local/provider compatibility dates. Its
success would bind that fixture rather than the composite or captured rollback.
Do not run it as a substitute, report a missing phase as skipped-success, reuse
another artifact's preview receipt, or infer production-domain authority from
any isolated-preview authorization. No permissive skip-preview option is valid.

Prior independently reviewed evidence at dc7234a is bounded as follows:

- The previous batch handoff records native TypeScript7.0.2 and generated API
  projection checks, 717 Python/Lua and 531 backend/probe checks, plus SDK15.3
  parsing for sixteen changed/new Lua sources. These are prior baseline checks,
  not fresh #0044 whole-packet conformance receipts.
- #0041 independent review records 31 Lua/source and 114 actual VM/SQLite
  checks, zero host/global-network counters, and correction/re-review of fault
  preflight reachability. Source files above bind that corrected preparation.
- #0043 independent review records eight tests and a fresh private actual-capture
  rehearsal with unchanged synthetic data/gates and 25 refusal routes. All four
  provider/production/deployment fields remain false.

Private retrieval: workspace `work-batch-2026-10-17-width16` holds named
`batch0041-independent-review.md`, `batch0043-independent-review.md` and detailed
receipts; original #0038 fixture remains under
`private-evidence/0038/parent-final-20261016`. Preserve original private captures
and #0043 exact packet/rehearsal evidence outside Git. Public outputs contain
only sanitized digests, booleans, finite labels/counts and evidence references;
no credentials, raw headers/bodies, provider identities, photographs or licensed
SDK source. Current #0044 independent review receipts belong to the parent batch
and must be reconciled before handoff. No provider bundle or deployment was
created in assembling this documentation.
