# Production observation/preflight approval packet — 2026-10-16

Ticket #0141; parent #0025; execution #0078. **Preparation only; no decision has
been recorded. This packet is not yet ready for an execution approval request.**
The concrete prerequisites below remain open. Production must remain stopped.

## Authority disposition

The architecture repository's `AGENTS.md` and `docs/README.md` authority hierarchy,
accepted ADRs 0007 and 0021, and the accepted existing-public-photo intake contract
control this scope. The [trial runbook](first-controlled-group-addition.md) and
[reviewed adapter](controlled-trial-observation-adapter.md) preserve their gates.

The recorded owner-selected pair is reusable. The documented ignored
`.probe-runs/controlled-trial-2026-10-16/selected-pair.json` exists and records
selection, guest accessibility and `liveActivationAuthorized=false`. Do not ask
for another pair. Private card #0025's six comments preserve the selection-only
handoff and separate live authority. Terry's 2026-10-16 approval on #0073 accepts
the reviewed adapter; the immediately preceding handoff explicitly records no
remote query and retains the external stopped-writer/configuration barrier.
Neither record approves the exact production D1/preflight operation below.
Standing commit/push approval and the temporary #0036 metadata-reader grant do
not establish D1 SQL or authenticated Flickr/binding authority.

Disposition: **applicable exact execution approval not found in the inspected
records**. No approve/decline/defer decision is fabricated. Reuse any later
explicit directive covering the completed exact packet; otherwise present it
once prerequisites and independent review are complete. #0141 is not completed
by preparing this document.

## Proposed operation and resource boundary

The primary Codex operator would perform one bounded stopped-baseline observation
for the existing `fga-api` Worker at `flickrgroupaddr.com`, its currently bound
production D1 database and COORD namespace, and the previously selected pair.
Exact account/database/namespace/version and pair identifiers remain in the
private #0036 inventory and #0141 evidence; they are omitted here.

The retained #0036 local capture (`20261016T214740Z`) supplies a usable resource
index and exact captured version/modules. Its `private/restoration-inputs.json`
and integrity index are retained outside this public checkout. It observed
intake=0 and dispatch=0 and retained exact DB/COORD bindings. These are capture-time
facts, not a current freeze or permission to redeploy. Its captured existing-photo
flag is absent; current source defaults that path to disabled. Local migration
head is `0017_upload_ambiguity_resolutions.sql`; deployed schema/head and digest
must be established independently rather than assumed from the checkout.

The fixed D1 helper is `scripts/controlled_trial_observations.py`, inspected at
source `b599ca828d2a645b686aca0354d6c8ee2c2a0250`, SHA2-256
`8bb7f0327638b4977495f7edac0c9bf60f8f4ded4c1ed9c8fedc575a36f8fab8`.
It imports `scripts/controlled_trial_pause.py` **only for transport**, SHA2-256
`421dd4104118b6960afa11ffa1a169abd5bad278bf77ad6b4d7e73f1175665c2`.
Recheck both before freezing the final packet; a changed helper needs review.

The six-field private plan is exactly `schemaVersion=1`, `accountId`,
`databaseId`, `fgaUserId`, `photoId`, `groupId`. Account/DB must match the captured
production binding; pair values come from the existing worksheet. The intended
FGA user/owner/installation mapping still needs a current approved private
identity reference. Tokens are neither fields nor command arguments.

After authorization and the barrier, the exact D1 command shape is:

```console
uv tool run --from uv==0.12.5 uv run --frozen python -m scripts.controlled_trial_observations --plan PRIVATE_PLAN --observe --token-file PRIVATE_D1_READ_TOKEN_FILE --private-output FRESH_PRIVATE_INVENTORY
```

The uppercase paths are unresolved private inputs, not runnable values. Plan
validation without `--observe` is offline. Use locked CPython 3.14/uv 0.12.5;
record lockfile digests and exact interpreter version in the final manifest.
The provider credential needs only authorized D1 read/query access to this
account/database. Its availability and effective scope are unverified; do not
read unrelated credentials, reuse CI authority implicitly or change permissions.

## Exact SQL, limits and evidence

The reviewed source, not the runbook's older illustrative LIMIT 101 queries,
is the executable SQL manifest. `INVENTORIES`, `PAIR_SQL` and `statement()` define
the complete fixed SELECT set: users, gates, partitions, intents, attempts,
blocks, counts and pair. There is no arbitrary SQL/table/projection/URL input.
Each inventory uses `WHERE key COLLATE BINARY > ?1 ORDER BY key COLLATE BINARY
LIMIT ?2`, with bound continuation and page size 100. All users/partitions,
terminal and active intents, future-due work, retained leases and attempts are
included. Attempts LEFT JOIN membership/preflight/dispatch/resolution evidence.
Pair parameters are bound user/photo/group values; pair output retains ownership,
verification/link revisions, native generation/lifecycle authority, blocks,
retained intents and advisory membership facts without native secret contents.

Two complete identical sweeps each perform counts-before, six inventories,
pair and counts-after. Limit: 10,000 pages per inventory per sweep, at most
120,006 provider requests; an exact page multiple needs the terminal empty page.
Count mismatch, cursor failure, changed projection or exhaustion refuses the
observation. Every request is POST to the fixed official Cloudflare
`/client/v4/accounts/{accountId}/d1/database/{databaseId}/query` endpoint with a
SELECT body, 30-second socket timeout, 64 KiB response limit, no redirects and
no automatic retry. This helper has **no total operation watchdog**; the final
packet must name an acceptable run deadline and interruption procedure rather
than imply the socket timeout bounds the full run.

The output file is new, outside the repository, and must never overwrite the
plan/token/evidence. Preserve complete private inventories, interval, plan and
source digests, schema/configuration provenance and approval reference. Stdout
contains only constructed counts/booleans, `observed_only_not_authorization`,
and `freshFlickrPreflightRequired=true`, or `observation_refused`. No IDs, provider
bodies, tokens, photo metadata or raw configuration enter public receipts.
Interrupted/partial/failed evidence is unusable. Any subsequent attempt requires
a fresh filename and separately applicable execution scope; never raise limits
or replay writes to obtain a pass.

## Stopped-writer and edge barrier

Before both sweeps, privately pin the actual active version/weights, exact module
and configuration, DB/COORD bindings, deployed migration head, disabled intake and
dispatch, both paused gate revisions, and absence of in-flight invocations and
other writers. Hold configuration and all writers fixed through both sweeps.
Include cron, admission hints, Durable Object alarms, administrative/background
maintenance, other operator SQL and authenticated status/bookkeeping callers.
Disabled dispatch/intake does not stop all D1 writes. Equal sweeps are drift
detection, not a multi-request serializable snapshot or proof of quiescence.

The #0036 collector can refresh bounded provider metadata but supplies no
runtime drain/freeze proof or atomic effective-edge fence. Before any ordinary
application preflight, the exact same-origin edge route, bindings, feature flags,
caller, methods and authenticated runtime must be verified. #0037/later edge
qualification is separate from metadata inventory. If the required barrier cannot
be established through a supported reviewed procedure, stop; this approval must
not silently authorize deployment, config edits, disabling maintenance or gate
changes to manufacture it.

## Fresh Flickr and ordinary-path boundary

D1 pair facts are not fresh Flickr ownership/public eligibility or membership.
If a binding must be created/refreshed, the normal path is installation-Bearer
`POST /api/v001/existing-public-photo-bindings`, body
`{schemaVersion:1,flickrPhotoId:<selected>,expectedLinkedFlickrRevision:<verified>}`.
It calls signed `flickr.photos.getInfo`, then creates/refreshes binding proof and
history; admission/rate/audit effects also apply. It admits no submission intent.

Fresh membership uses the same approved installation's
`GET /api/v001/photo-bindings/{exactBindingId}/group-memberships?page_size=100`,
then only returned revision/group continuations until complete. The first page
calls signed `flickr.photos.getAllContexts`, invalidates the old view and commits
replacement observation/cache rows. These are real-account API operations with
durable writes, not SELECT-only observations. Backend runtime resolves its
existing Flickr grant internally; the operator must not retrieve the native
credential bundle or pass OAuth values. Failed-grant handling can durably pause
or reject authority and must be included in any proposed scope.

No bounded approved ordinary-path caller/credential interface, exact binding and
revision, page/run cap, response/time limits or enabled qualified production
artifact has yet been frozen for these actions. Do not substitute direct OAuth,
an ad-hoc SQL binding or a Lightroom invocation. If native client use is proposed,
its exact FGA-LrC15 bundle, Lightroom Classic 15.6 / SDK 15.3 actions and required
action-time confirmation belong in the completed packet. No native action is
included in the present proposal.

Fresh attempt-scoped `getAllContexts` followed by `flickr.groups.getInfo` remains
mandatory immediately before any later authorized add under ADR 0007. Preflight
here cannot bank those reads for dispatch. This packet does not include an add,
gate resume/pause, intake enablement, submission admission, deployment, resource
creation, repair/relink, credential replacement or queue changes.

## Concrete readiness gaps

1. Freeze the private observation manifest: verified intended FGA user/owner and
   installation reference, exact plan/path/digest, read credential reference and
   authorized effective D1 scope, output location/retention, tool identities and
   approved run deadline. Pair/account/DB references are already available.
2. Supply an executable supported stopped-writer/drain/configuration barrier and
   current metadata/schema capture procedure; metadata and disabled flags alone
   cannot meet it. No freeze operation is silently authorized here.
3. Choose D1-only partial observation or complete #0078 preflight explicitly.
   Complete preflight needs the exact qualified ordinary binding/membership
   caller, required real-account/bookkeeping scope, caps and edge/feature-state
   readiness above. Any required production change needs its own concrete scope.
4. Preserve #0078's release/rehearsal prerequisites (#0076/#0077), then independent
   review of the completed manifest/procedure. Their unfinished state is not an
   owner decision. Present the exact reviewed digest and approve/decline/defer
   choice only after these engineering prerequisites are resolved.

No live SQL, provider/Flickr request, token read, native action, deployment,
permission change or approval request was performed while preparing this packet.
