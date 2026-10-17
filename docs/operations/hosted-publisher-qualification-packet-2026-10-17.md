# Hosted publisher qualification packet — 2026-10-17

Status: **NO-GO for hosted execution**. Ticket #0121 provides an offline,
hash-bound source packet, a disabled buildable qualification Worker, and finite
local diagnostics through the actual current HTTP handler and Album consumers.
It does not qualify production scheduling or a hosted deployment. Credentials
and upstream results in the qualification composition are fixed synthetic
in-memory values. Preparation makes no external provider request, deployment,
real credential lookup, native Lightroom action or production activation.

## Authority and exact scope

The accepted architecture sources are ADR 0005 (backend-signed direct upload),
ADR 0012 (explicit ambiguous-upload reconciliation), the
`album-scoped-publish-contract.md`, `album-write-reconciliation.md`, and
`album-lifecycle-contract.md` in `FlickrGroupAddr/architecture-design/docs`.
Their accepted boundaries require guarded identity, dispatch markers, fresh
membership proof, fencing, non-replay of ambiguous create/upload, and
non-destructive local removal. Proposed wire supplements are not independent
permission to weaken those rules.

The source closure contains the current `src/worker.ts`, every explicitly
listed production TypeScript module, migrations **0001–0026**, the ten public
admin assets, `wrangler.example.jsonc`, package manifest/lockfile, compiler
configuration, this packet's preparer/runbook and the isolated candidate's
entrypoint, disabled config, compiler config, diagnostics/tests and scope
template. The list is closed in `SOURCES`; no directory wildcard
copies private configuration, credentials, SDKs, photos or local runtime files.
Relative TypeScript/JavaScript imports must remain inside that closure;
external package imports are allowlisted and resolved by the lockfile.

The production configuration and package/lockfile bytes are separately pinned
in `PINNED_INPUTS`. A changed compatibility date, enabled capability, provider
resource ID, secret reference or toolchain refuses preparation until its new
bytes receive deliberate review. All present production capability variables
remain `0`; omitted Album capability variables remain disabled by the actual
handler's `=== '1'` checks. The sealed template names no actual provider
resource and grants no deployment. The separate qualification config is
disabled, with placeholder D1 identity, and has no production domain, route,
cron, Durable Object or Secrets Store binding.

The declared tools are Node **24.22.0**, npm **12.2.0**, native TypeScript
**7.0.2**, Wrangler **4.116.0**, Miniflare **4.20260730.0**, and the exact
package-lock transitive dependency graph. The Worker compatibility date is
**2026-10-16**. These declarations and source hashes do not attest installed
tool binaries, emulator parity with the hosted date, or a deployed artifact.
The parent integration gate must retain actual tool version/build receipts.

## Reproduce without network

Run from the implementation checkout using the already installed pinned
Python/Node runtimes. Do not install or upgrade dependencies as part of this
offline packet. The destination's parent must exist; the destination must be a
new private directory outside the checkout. Final preparation runs after the
integrated files are committed; `--require-commit-exact` refuses dirty/untracked
closure bytes. Earlier preparation may omit this flag; non-commit-exact
preparation explicitly records `sourceCommitExact=false`.

```powershell
$candidateHead = git rev-parse HEAD
uv run --offline --no-sync --frozen python scripts/prepare_hosted_publisher_qualification.py C:/Temp/FGA-publisher-packet --expected-source-head $candidateHead --require-commit-exact
```

Retain the printed source packet SHA2-256 independently. Verify with both that
digest and the expected full source commit, for example:

```powershell
uv run --offline --no-sync --frozen python scripts/prepare_hosted_publisher_qualification.py $packetPath --verify --expected-source-head $candidateHead --expected-artifact RETAINED_SHA2_256 --require-commit-exact --require-commit-exact
node probes/publisher-qualification/offline.mjs
node --test probes/publisher-qualification/disabled-boundaries.test.mjs
node_modules/.bin/tsc.cmd --project probes/publisher-qualification/tsconfig.json --noEmit
node --test probes/publisher-qualification/runtime.test.mjs
node --test probes/publisher-qualification/upload_checks.test.mjs
```

The Node commands use the checkout's existing locked dependencies. The
staged closure is also runnable after those exact dependencies are separately
provisioned under an authorized offline process; it does not copy `node_modules`
or silently fetch packages. A staged runtime test must supply pinned Python
through `FGA_QUALIFICATION_PYTHON` for its standalone standard-library SQL parser.
Keep receipts outside the immutable packet; extra files inside it refuse
verification. `manifest.json` binds source HEAD and each file's raw bytes,
length and SHA2-256. `run-plan.json` remains NO-GO and enumerates missing gates.
`authorization-template.json` is ungranted, has no resources/expiry, and grants
no deployment/provider/production action. Altering it invalidates verification.
No command in this packet consumes it as authorization.

Both the retained digest and full expected HEAD are necessary: regenerating
a manifest after editing files is not independent artifact verification. HEAD
alone does not mean a clean tree. The preparer compares copied file Git blob
identities with the exact HEAD tree; `sourceCommitExact=true` attests only this
closure, preserving unrelated worktree changes. The parent must commit integrated sources,
rebuild/restage, and retain fresh final hashes after all sibling changes.

## What the runnable diagnostic proves

The diagnostic imports `createWorker` and the production registry directly.
It sends one finite request for each publisher-scoped registered route with
flags omitted, then with flags explicitly `0`. On 2026-10-17 this executed
**44 actual handler requests**, all refused with HTTP 503. It also invokes the
actual materialization, attachment and title consumers in both configurations:
**six disabled results**. Scheduled handling is called with dispatch disabled.
A throwing database proxy, injected throwing upstream, and replacement global
fetch observe **zero database and provider calls**. The runner caps requests
at 64 and its process lifetime at 30 seconds. It does not construct successful
SQL fixtures or pretend a constructor is an executed qualification test.

The separate `disabled-boundaries.test.mjs` expands refusal spellings and
checks that disabled consumers do not consult database, transport or clock.
These narrow local assertions establish default-off behavior only. They do
not prove valid authentication, storage transactions, successful upload proof,
remote writes, retry recovery or any hosted behavior.

## Isolated executable and production boundary

`src/worker.ts` registers publisher HTTP handlers, but its scheduled path
does not invoke `consumeAlbumMaterialization`, `consumeAlbumAttachment` or
`consumeAlbumTitle`. The consumers explicitly accept internal transport
factories and supply no default credentials/network/scheduler. There is no
production composition of those three pieces for this packet to exercise.
The isolated candidate composes these consumers explicitly through existing
source seams. That different composition does not qualify the production
scheduler.

`probes/publisher-qualification/worker.ts` is the buildable qualification-only
entrypoint; `wrangler.jsonc` is its disabled configuration. The local D1 runtime
test bundles that exact Worker, applies all 26 production migrations and
intercepts every external egress with a throwing boundary. Its emulator date
**2026-07-30** is separate from the declared hosted date **2026-10-16**.
Any later hosted run still needs an independently retained compiled candidate
digest, exact resource/configuration overlay, owner authorization and the
finite lifecycle below. Local evidence cannot substitute for those gates.

The fixed phases are `seed`, `http`, `materialize`, `attach`, `title`, `remove`,
`finish`. Seed refuses a nonempty user census instead of overwriting an owner.
HTTP invokes the actual Worker; Album phases invoke the actual consumers,
guarded durable stores and strict synthetic transport constructors. Fixed
synthetic signing material and an in-memory response generator have no global
fetch/credential-provider fallback. Attachment/title use shared
`createAlbumFlickrAdmission` and the shared fault gate; materialization checks a
real capacity reservation, current authority, fault gate and reservation expiry
immediately before synthetic handoff. There is one rate allocator per operation.

Only POST `/__publisher/{phase}` with an empty body is accepted. Before D1,
the wrapper requires `PROBE_ENABLED=1`, scope `publisher-disposable-v1`, 64-hex
access/artifact/run identities, a nonzero resource UUID, matching
`X-Probe-Access`, `X-Probe-Artifact`, `X-Probe-Run`, `X-Probe-Resource` headers,
and an expiry no more than 30 minutes ahead. The sealed config grants none of
these permissions. Empty streaming bodies have a 500 ms check. A durable
control row pins run/artifact/resource/expiry; atomic reservation requires the
next phase and `busy=0`. Completion advances the cursor. Overlap, replay,
out-of-order phases and changed bindings refuse. Failure is terminal; a failed
seal can leave the row busy, also refusing replay. Never reset it to replay.

Each phase caps DB calls at 256 (batch width 128), synthetic handoffs at 16
and synthetic POSTs at one. Seven accepted phases bound the sequence to 112
synthetic handoffs/seven synthetic POSTs. The finite client plan permits at
most 32 requests including negative cases. Phase execution has a 60-second
budget and consent a 30-minute window. New SQL and synthetic handoffs check
expiry, elapsed time and request abort. SQL waits are bounded; failure sealing
has an additional 500 ms wait allowance. Timers stop follow-on work but cannot
cancel a D1 mutation already submitted. Stop/recovery evidence must retain
this limitation.

The closed scenarios are `happy`, `create_lost`, `attachment_lost`, `title_lost`.
`PROBE_SCENARIO` and `X-Probe-Scenario` must agree; omission means only `happy`.
The scenario is pinned in the durable control identity and cannot change
between phases. Each case uses a fresh disposable Worker/database pair;
never reset or reuse a previous target. The HTTP phase exercises actual upload
authorization, normal upload-origin binding, advisory candidates, explicit
ambiguous-upload reconciliation and replay. Those actual proof bindings become
the Album first candidate and later obligation; no existing-public proof is
seeded to bypass that path. No image upload is performed.

Lost-response scenarios apply the synthetic remote effect before throwing.
Lost create must retain `create_outcome_unknown` and dispatch count one; a
second actual materialization invocation returns `no_work` without another
create. The phase then uses actual HTTP candidate/resolve/replay handlers,
the strict repair reader and shared admission against four fresh synthetic GETs.
The receipt records `createReplayOutcome=no_work`, `repairStatus=materialized`
and the repair request count. Lost attachment/title require their actual
consumers to obtain fresh read proof after the throw with exactly one POST;
receipts record `lostReplyRecovered` and post-handoff reconciliation reads.
These cases do not establish crash/lease/restore behavior or require fake clocks.

Across all four cases the conservative caps are **128 client requests,
448 synthetic provider handoffs, 28 synthetic POSTs, and four fresh Worker/D1
pairs** (eight provider resources). Each case has its own absolute expiry no
more than 30 minutes ahead; four sequential cases have at most 120 minutes of
combined consent windows. The template's `maximumRequests=64` belongs only to
the separate 30-second default-off diagnostic, as `maximumRequestsScope` states.

The parent builds the final optimized bundle after the clean commit, retains
its digest separately from source/configuration hashes, and reruns the same
runtime matrix against those exact bytes using `FGA_PUBLISHER_QUAL_BUNDLE`.
That override accepts an existing local bundle path and skips test rebuilding;
it retrieves no content and executes no caller-supplied command. A local pass
does not become a hosted receipt.

For the optimized build, use the already installed locked esbuild 0.28.1 CLI
from the clean implementation checkout; no provider CLI, download or install is
needed. Choose a fresh durable private build directory outside the immutable
source packet. The fixed compiler arguments are:

```console
node node_modules/esbuild/bin/esbuild probes/publisher-qualification/worker.ts --bundle --minify --format=esm --platform=browser --target=es2022 "--external:node:*" "--external:cloudflare:*" --define:process.env.NODE_ENV='"production"' --legal-comments=external --outfile=PRIVATE_BUILD_DIRECTORY/worker.mjs --metafile=PRIVATE_BUILD_DIRECTORY/metafile.json
```

Replace `PRIVATE_BUILD_DIRECTORY` with that new directory; it is a documented
placeholder. Retain the exact Worker bytes, companion legal notices, compiler
metafile, Node/esbuild versions, full source commit and SHA2-256 hashes of the
bundle, both production/probe configurations and source artifact. Set
`FGA_PUBLISHER_QUAL_BUNDLE` to the retained `worker.mjs`, then run
`node --test probes/publisher-qualification/runtime.test.mjs` from the checkout
with the pinned offline Python/Node tools. The driver tests those exact supplied
bytes. Do not write generated receipts or dependencies into the immutable packet.


On 2026-10-17 the integrated actual D1 matrix passed **27 tests**, including all
four scenarios, all three consumers' fault/revision/rate refusal cases, replay,
concurrency, terminal failure and cancellation. The parent must repeat the
matrix against the final committed/minified bytes before handoff; this dated
development result is not that final artifact receipt.

## Disposable hosted lifecycle — ungranted

The later #0134 decision must name the final compiled/source/configuration
digests, each case's unique disposable Worker and **new empty D1 database**,
run ID, access-token delivery method, start/expiry and cleanup owner. No other
resource/production binding, real Flickr credential/image or native catalog
is allowed. Independent review must inspect these exact bytes and lifecycle.

1. Bind the authorized empty D1; apply only migrations 0001–0026 and retain
   schema/config identity. Probe control/data tables are created by the exact
   candidate and bound by its compiled/source hashes.
2. Configure exact artifact/resource/run identities and at most 30-minute expiry.
   A separately reviewed finite disposable endpoint lifecycle must supply
   reachability; preparation creates none and does not use a production domain.
3. Execute the seven phases once per case, in order, with at most 32 client
   requests per case and 128 across all four. Use at most four fresh resource
   pairs, one per closed scenario; never reuse a target across cases.
   Retain sanitized success/negative receipts. Stop on failure or external access.
4. Disable candidate access on stop; wait for submitted D1 work, inspect durable
   markers and retain the exact named-resource census. Never replay failed phases.
5. Delete only the exact disposable Worker/database named by consent after no
   operation remains in flight. Never list/delete broadly or select by prefix.
   On cleanup failure, keep access disabled/expired and retain an exact-resource
   retry handoff; do not claim cleanup passed.

No deployment/create/delete command is executed by preparation. Exact resource
overlay, endpoint reachability, action-time consent and hosted evidence remain
absent, so #0122 remains NO-GO.

## Required completion evidence before #0134/#0122

| Area | Required finite proof against the final candidate |
| --- | --- |
| Artifact and schema | Optimized bundle digest, exact source commit, config projection, installed tool receipts, migrations 0001–0026 and exact disposable resource binding. |
| Authority and isolation | Synthetic-only credentials/upstreams; cross-user/service/revision denial; no production binding or secret retrieval; exact expiry and abort enforcement. |
| Upload and binding | Normal upload-origin proof, ambiguous upload without image repost, advisory candidates unable to create binding, explicit fresh reconciliation. |
| Album coordination | Idempotent obligations, first-candidate fencing, marked create never replayed after ambiguity, fresh read/add/read attachment and stale worker denial. |
| Repair and lifecycle | Fresh repair authority, bounded title supersession/reconciliation, local removal leaves remote photos/albums/membership intact. |
| Recovery and stop | Crash/mutation tests, intake stop, pending/marked work census, restart, exact rollback, current-schema restore and reconciliation without loss or unsafe replay. |
| Resource lifecycle | Maximum resource/request/write/time budgets, cleanup eligibility, cleanup failure recovery and sanitized receipts; no broad deletion authority. |
| Review and authorization | Independent review of the final bytes, then Terry's exact disposable-run decision on #0134 before any #0122 hosted execution. |

The source packet is reviewable preparation for that work. The parent owns
final integration/build/hash verification; the runtime-adapter implementer
owns the missing production composition; Terry owns the later exact hosted-run
decision. #0122, production activation, controlled trial and native publisher
qualification remain separate unpassed gates.
