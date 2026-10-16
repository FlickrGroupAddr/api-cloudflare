# Finite native-network packet review

Date: 2026-10-16. Status: independent source/offline review passed for the fixed
server artifacts and native fixture 0.0.1.1 below. No cloud resources, live
requests, native UI actions, credentials or production changes were used by
this reviewer. Only this evidence note is reviewer-owned.

Accepted ADR0061 authorizes qualification development. The detailed thumbnail
candidate remains Proposed; this packet characterizes a disposable controlled
path and cannot accept or qualify the production transport contract. Previously
completed synthetic hosted and native cache/UI evidence retains its own scope.

## Result and fixed scope

No unresolved material source safety defect was found after the corrections
below. The packet specifies exactly **two fresh Workers and one shared fresh
synthetic D1**, with no Durable Object, production route, Flickr request, queue,
real credential or existing database. Stock configs disable workers.dev and use
inert names/bindings/expiry. There is no deployment automation in these reviewed
artifacts. Any later lifecycle runner/workflow requires a separate delta review.

`probes/existing-photo-native-network/worker.ts` exposes eight fixed source cases:
PNG/JPEG, boundary and oversized image markers, oversized error, a single
16-second delay and fixed same/cross-origin redirects. Maximum response stimulus
is 262145 bytes. There are no client-provided URLs, sizes, delays, headers or
redirect targets. Both HTTPS workers.dev origins derive from one fresh run ID
and reviewed account subdomain. No outbound `fetch` or arbitrary relay exists.

The single parameterized D1 UPDATE atomically admits at most 32 requests per
role across isolates. It updates only total/receiver counts and aggregate
Authorization-present/exact-synthetic-canary Booleans. Runtime configuration,
the same SQL statement's database clock and checks before publication enforce
the 20-minute expiry; delayed responses recheck expiry. Denied traffic receives
small fixed JSON. This bounds admitted payload work, not every incoming request
or provider billing.

## Credential, redirect and observation boundary

The native fixture imports no credential-store or catalog API. Its private
bounded target document accepts only the fixed plan version, fresh run ID,
workers.dev subdomain, 64-hex disposable gate, explicitly `SYNTHETIC-` canary and
expiry within 1200 seconds. URLs, paths, request counts, cases and timeouts are
not configurable. Structural config validation is not attestation of its
producer: the primary must match it to the exact created-resource journal.

The native plan issues at most ten explicit GET calls: baseline report, eight
source cases and final report. SDK redirect requests can add source/receiver
admissions, still subject to the server quotas. Source requests carry only the
disposable gate and synthetic Authorization. Reports are gated and deliberately
omit Authorization. The single run-specific receiver path is ungated so loss of
the custom gate header cannot conceal redirect arrival. It has the same bounded
quota/expiry and stores no header value or token. A report itself never creates
an Authorization/canary-arrival observation.

The source permits redirects only to its own fixed PNG path or the exact
derived receiver path. The receiver observes arrivals and canary presence; it
does not forward, log or persist credentials. Markers are public diagnostic
values, not origin authority. A missing or malformed report, expired plan or
quota failure yields no forwarding conclusion.

## Corrected result classification

Review identified that more than one receiver arrival could be labeled a
complete characterization even though there is only one intended cross-origin
redirect. The native owner corrected this: counts above one remain visible but
make the result incomplete, set `observationConclusive=false` and omit the
inferred `redirectFollowObserved` field. They are not attributed to a specific
cause. Zero-count/Boolean and canary/Authorization contradictions are rejected.
This handles observable SDK repetition/interference without inventing a
guarantee against arbitrary external replacement servers.

Every response branch, including timeout partial data, must also remain within
the finite-plan byte comparisons. Oversized partial data stays measurable but
cannot count as an expected finite completion. The oversized-error case now
checks the closed `text` media category corresponding to its fixed text/plain
stimulus. Regression tests cover these boundaries.

## Private files, cleanup and qualification limits

Target/configuration, origins, account/resource IDs, gates, canary values and
created-ID journals remain private. The native receipt contains fixed case IDs,
closed status/error/media categories, counts, observed timings and Boolean
comparisons only. Body/partial-data bytes, raw headers/errors, URLs, tokens and
photography data are excluded. Checked temporary-file publication is observation
plumbing, not a crash-durability guarantee. No image/cache file is created.

The runbook requires private identity journaling before dependent operations,
single-attempt creation/upload, exact-name read-only reconciliation after an
ambiguous mutation, and deletion/absence verification for only the exact two
created Workers and D1. No broad prefix deletion or guessed identity is allowed.
Expiry is not cleanup. Private local files may be removed only after matching
this run's recorded identity/hash, preserving a later run's file. Forced stops
can leave cleanup unconfirmed and must retain recovery correlation.

This review grants no live resource creation, deployment, CI dispatch, new
plug-in load or command invocation. The primary owns the concrete authorization
and fresh Windows action-time handoff. Generate expiry after that decision;
review/consent waiting must not consume a live window. A future orchestration
runner is outside this packet's reviewed provenance until separately reviewed.

The fixture records post-fetch byte/timing observations. It does not measure
peak process memory, prove native preallocation limits, establish a hard total
deadline, decode marker fixtures or qualify the fixed production origin/edge.
Its receipt explicitly keeps native/production qualification, allocation proof,
total-deadline proof and remote cleanup false. Redirect follow/refusal or canary
forwarding/stripping are measurements using synthetic material, not a production
credential-safety pass.

## Independent verification

- `node --test tests/existing_photo_native_network.test.mjs`, using the existing
  portable Node 24.22.0 runtime: five passed, zero failed. SQL uses the local
  SQLite adapter; this is not hosted D1 contention evidence.
- `uv run --frozen python -m unittest tests.test_existing_photo_network_native`:
  ten passed, zero failed in actual Lua 5.1 with SDK/HTTP stand-ins.

The owners additionally reported native TypeScript 7 and SDK15.3 compilation
passing. No native or hosted execution is inferred from these offline checks.

SHA2-256 digests of reviewed runtime/configuration artifacts:

| File | Digest |
| --- | --- |
| `probes/FGA-ExistingPhoto-Network.lrplugin/Network.lua` | `0eaa1bd69ac8e5cbd622e444446e6b93fded04cfe82c327d70e856310228902d` |
| `probes/FGA-ExistingPhoto-Network.lrplugin/Info.lua` | `65878000cc1f2d4cabcf29f768134ece44c1f43bc272ed4faf48bbe6c3bd1daf` |
| `probes/FGA-ExistingPhoto-Network.lrplugin/Run.lua` | `2e26d3dcea5a82a8a8529865695f68965df681ef8e8ea6d7a46ba954f8a39503` |
| `probes/existing-photo-native-network/worker.ts` | `26858287e2451bc72eb85660f41c7f7d91d5a72379d75aaa517b7a5df9265eb2` |
| `probes/existing-photo-native-network/jpeg.ts` | `1f256737e41e39baa18c4d56aeb83d2d4aaf3159c54ddf3b763fbe613a7be402` |
| `probes/existing-photo-native-network/schema.sql` | `44b4944ef186bb52004d1d5271b733587a7b0dfd17ea8fbf0a150994c403d561` |
| `probes/existing-photo-native-network/source.jsonc` | `6dee0bbda2117d89c94468f913f0cc78ca40113d7d877d55e82d2b7cdf5ad498` |
| `probes/existing-photo-native-network/receiver.jsonc` | `a98f4c5fea17c48cdd14fab8456a744554ec9ec014093a61ca6030f182f88fbe` |

Test-source hashes: `tests/existing_photo_native_network.test.mjs`
`5516916fb45a84b6364f025afa58cb7fb378b48b3a18e5d07f106813d196ca52`;
`tests/test_existing_photo_network_native.py`
`fa278fa65220673f854d7131c7ae3e9466a5c21f7b52fbda308c18c28b990b83`.

## Separate manual CI lifecycle review

Reviewed the subsequently prepared lifecycle runner and manual-dispatch
workflow without live calls. The preceding packet/fixture 0.0.1.1 hashes remain
historical exact-source evidence; this section adds lifecycle scope rather than
replacing that provenance. A new native attribution correction is reviewed
separately after its sources stabilize.

`scripts/existing_photo_native_network_lifecycle.py:150` creates only the two
derived fresh Worker names and one fresh D1. It persists private account/job and
acknowledged resource identities before dependent operations, plus a whitelist
receipt and flushed nonsecret run/name correlation. Fresh names must be absent;
canonical database ID/name and exact acknowledged Worker name are checked.
There is no mutation retry after an ambiguous create, seed, upload, endpoint
enable or delete. Cleanup at `:104` uses acknowledged identities only, checks
the D1's name and verifies absence. A repeated cleanup may reconcile absence
read-only, but an already attempted delete is not blindly repeated.

`hold_cleanup` at `:365` accepts only the same account/GitHub job journal and
derived names/canonical D1 identity. Preparation failure cleans up immediately;
failed ready-artifact publication skips holding. During a published ready
window it polls only a fixed parameterized SELECT over the two quota rows,
at most 121 times. Read-only query repetition is distinct from mutation retry.
The second gated receiver report triggers at most 60 seconds of grace, capped
by the original expiry. That counter is not proof that the native response or
terminal receipt completed; native evidence remains independently required.
Counter failure, expiry and normal completion all enter exact cleanup.

The initial 20-minute hold step could consume its whole budget waiting for the
resource expiry before cleanup began. The owner corrected it to 25 minutes
inside the 35-minute job. Preparation and holding share one original 20-minute
expiry, rather than creating consecutive live windows. The fake-clock regression
waits the full 1200 seconds without a final report, then charges nine cleanup
calls at 30 seconds each: 1470 seconds, below the 1500-second step bound. Forced
job termination or provider failures can still leave cleanup unconfirmed; exact
nonsecret correlation remains available for ownership reconciliation.

The ready artifact contains exactly five nonsecret fields: schema/plan version,
run ID, workers.dev subdomain and expiry. It contains neither gate/canary nor
account/resource ID or URL. The parent combines it privately with its two newly
created temporary Actions secrets. The workflow reuses the existing CI provider
token, grants only repository read permission and cannot manage those temporary
secrets. They must be absent before parent creation and removed by the parent
after the run; accepting this source does not authorize either action.

The synthetic values enter only preparation; provider credentials are limited
to the prepare and hold/cleanup steps. The local bundle helper strips
Cloudflare/FGA environment values. Holding requires no gate/canary and reads
only D1 counters. Uploaded artifacts are only the exact
ready JSON and sanitized cleanup receipt; private journals, configurations,
Wrangler logs and upload bodies are excluded. The receipt projects only fixed
names/flags, validated finite role counters and hashes, with exception class
rather than raw error text.

Review also identified missing generated/deployed configuration provenance.
The owner added separate `dryRunConfigSha2_256` and per-role
`uploadMetadataSecretElidedSha2_256`. Tests extract the actual multipart metadata,
replace both secret-text values with `[SECRET_ELIDED]`, and match the canonical
sorted-JSON hash. No raw configuration, IDs or secret value is published.

Independent `uv run --frozen python -m unittest tests.test_existing_photo_native_network_lifecycle`
passed seven offline fake-provider tests, zero failed. No remaining material
lifecycle source defect was found within this scope. No workflow dispatch,
resource/secret operation, UI action or native qualification was performed.

SHA2-256 lifecycle provenance:

| File | Digest |
| --- | --- |
| `scripts/existing_photo_native_network_lifecycle.py` | `2f87923b5a39a58bb59120364e3b8bb9b743c753c8e5e89ffec55554c1375137` |
| `.github/workflows/existing-photo-native-network.yml` | `6eda3773390c12d0ac61c5233076d8a34441f51dcc40ce707fb459255c211b70` |
| `tests/test_existing_photo_native_network_lifecycle.py` | `690eac3959fa5e518cc8081935ab24865a24dda6257a046843faac168f4ac489` |

The server Worker retains packet hash
`26858287e2451bc72eb85660f41c7f7d91d5a72379d75aaa517b7a5df9265eb2`.

## Native 0.0.1.2 attribution correction

The primary identified a remaining evidence-attribution gap in fixture 0.0.1.1:
one unrelated receiver arrival could coexist with the SDK returning the original
302 and still be labeled a followed redirect. The earlier 0.0.1.1 source review
and hashes above remain historical; they are not qualification of this corrected
fixture or proof that the earlier inference was sufficient.

Reviewed unrun fixture **0.0.1.2** now correlates the cross-origin response with
the final report. An original 302 requires zero receiver arrivals and false
flags. A receiver 200 requires its bounded closed four-field JSON response,
exact schema/reached/Boolean meanings, exactly one arrival and exact agreement
between response and aggregate Authorization/canary flags. Other responses,
multiple arrivals, malformed payloads or disagreements remain inconclusive with
no `redirectFollowObserved` inference. The marker remains public/forgeable; no
new authentication, endpoint, request or production-safety claim was added.

Independent review found that the initial correction still used permissive
dkjson syntax for those JSON responses. The owner added a bounded closed
primitive-object parser for receiver and report payloads: only known literal
ASCII keys, Boolean values and canonical nonnegative integers are accepted
before the exact schema checks. Duplicate names, comments, trailing commas,
unknown keys and trailing data are rejected. This is deliberately the small
fixed experiment wire format, not a new general JSON codec. Private target
decoding and its existing exact-field/value checks remain separate.

Independent
`uv run --frozen python -m unittest tests.test_existing_photo_network_native tests.test_existing_photo_native_network_lifecycle`
passed twenty-one offline tests: fourteen native Lua 5.1 tests and seven fake
lifecycle tests, zero failed. The new cases include unrelated single arrival,
malformed/nonclosed receiver payload, response/report flag disagreement and
duplicate/comment/trailing-comma rejection in both receiver and final reports.
No remaining material source defect was found in these corrected scopes. This
review made no live or UI call; version 0.0.1.2 has not acquired native acceptance
through these tests. Action-time authorization and actual terminal/cleanup
evidence remain required before any resulting qualification conclusion.

SHA2-256 native 0.0.1.2 provenance:

| File | Digest |
| --- | --- |
| `probes/FGA-ExistingPhoto-Network.lrplugin/Network.lua` | `d3369a176cd3ee0d7fc079dd77b10be7da29e9d63b0dc487af21accded41073c` |
| `probes/FGA-ExistingPhoto-Network.lrplugin/Info.lua` | `0e95693de0f92b973c8d8b3e84e4f5295d9211148d2c1cb5214e89b4ad2050e6` |
| `probes/FGA-ExistingPhoto-Network.lrplugin/Run.lua` | `4094a011299fc7f9141e839970ae3bc27c684e49b2dc75526b8341961f8d08df` |
| `tests/test_existing_photo_network_native.py` | `32c02e705905c49103ab5d44224d470b43404212a13b39462e9f7b88c6c1ec67` |
