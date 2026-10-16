# Current fixed-origin provider inventory

Date: 2026-10-16. Ticket #0036. The preparation and CI sections below record
the earlier packet and partial run. The later local-capture section records
the owner-supplied read-only access and durable private retention. No production
mutation, deployment or restoration rehearsal is authorized by this inventory.

## Original preparation packet (historical)

The following describes the initial collector before the local hardening below.

`scripts/existing_photo_inventory.py` implements a closed GET-only collector for
the existing `fga-api` Worker and `flickrgroupaddr.com`. It rejects redirects and
arbitrary resources before HTTP. It uses only the established
`FGA_CLOUDFLARE_CI_TOKEN` and `FGA_CLOUDFLARE_ACCOUNT_ID` CI route. No token creation,
scope expansion, write API, SQL, application request or Flickr request is included.

The workflow `existing-photo-inventory.yml` is manual. Review its exact committed
source and offline safety results before parent-owned dispatch. Workflow success
means the collector ran; it does not mean inventory completeness or restoration
readiness. Its receipt always keeps those assertions false until the missing
evidence has been independently resolved.

The collector captures deployment metadata before and after the operation,
active version metadata, downloaded Worker content, Worker/script settings,
account custom domains, the exact zone lookup, Worker routes, zone settings,
Page Rules and ten relevant zone Ruleset Engine entrypoints. Failed reads record
only HTTP status or a closed failure label. A 403/404 is never interpreted as no
rule. Paginated responses explicitly remain incomplete. Deployment stability
does not prove atomic consistency of all edge settings.

The CLI runs collection in one child process with a 180-second subprocess
watchdog. This bounds the complete operation even during DNS/TLS or a slow-drip
body; the 30-second socket timeout alone is not a total deadline. Collection
permits at most 32 requests, eight weighted version entries and 16 MiB per
response. Missing or malformed pagination metadata remains incomplete. Active
version percentages must sum to 100; duplicate identities are combined and
queried once. The exact version/weight index remains private. The downloaded
`unversioned_artifact.bin` is **not tied to every weighted active version** and
cannot support an exact-artifact rollback assertion. That binding is explicitly
unknown; version metadata capture does not resolve it.

Only the explicitly named receipt may be uploaded. Provider payloads, exact
identities, configuration and downloaded source are saved under `private/` in
the fresh run directory. Treat those files as sensitive: plaintext configuration
or source may contain sensitive values, although secret-text binding values are
not readable from these APIs. Do not log, commit or publicly upload that folder.
The public receipt includes only fixed labels, booleans, lengths and SHA2-256
digests; it contains no raw headers, source, arbitrary provider errors or IDs.

The private `restoration-inputs.json` is an input index, not a deployable or
complete rollback manifest. Hosted ephemeral runner output has **no durable
private retention route in this workflow**. The existing public repository
artifact route cannot be used to publish private inputs. A secure existing
private evidence transport must be established by the parent before treating a
CI run as a rollback capture. This is an unavailable input/transport boundary,
not a request for future deployment permission or new credentials.

A local availability-only check on 2026-10-16 found neither documented Reader
environment input present (`CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN`) and no
standard `%APPDATA%/.wrangler/config/default.toml` file. No tokens or config
contents were read or printed, no secret search or remote auth probe was made,
and historical promotion records were not treated as current credentials.
Consequently this packet cannot currently perform durable private local
collection with its supported Reader interface. Existing CI credentials remain
the documented remote-read route, with actual read scopes still unmeasured and
private output ephemeral. The parent owns any live invocation.

Unresolved scope remains explicit: account-level rules and recursively executed
managed rules, provider-error/challenge behavior on the actual three paths,
secret preservation/restoration semantics, durable private capture and an exact
restoration rehearsal. No live fault probe or production request is part of
this metadata-only task. The three intended routes are installations/current,
existing-public-photos and existing-public-photos/{syntheticPhotoId}/thumbnail
under `/api/v001/`; metadata reads cannot certify their runtime behavior.

Offline verification (use the pinned tool without replacing global uv):

```powershell
uv tool run --from uv==0.12.5 uv run --frozen python -m unittest tests.test_existing_photo_inventory
uv tool run --from uv==0.12.5 uv run --frozen ruff check scripts/existing_photo_inventory.py tests/test_existing_photo_inventory.py
uv tool run --from uv==0.12.5 uv run --frozen pyright scripts/existing_photo_inventory.py tests/test_existing_photo_inventory.py
```

Endpoint provenance checked against the provider API reference on 2026-10-16:
[Workers API](https://developers.cloudflare.com/api/resources/workers/) and
[deployment list](https://developers.cloudflare.com/api/resources/workers/subresources/scripts/subresources/deployments/methods/list/).
The first deployment is the currently serving deployment; it may contain multiple
weighted versions. A local Wrangler template is never substituted for provider
readback.

## Actual bounded capture, 2026-10-16

[CI 38967001129](https://github.com/FlickrGroupAddr/api-cloudflare/actions/runs/38967001129)
completed the reviewed GET-only packet successfully. The
[sanitized receipt](../evidence/existing-photo-inventory-ci-2026-10-16.json)
records 21 requests, stable deployment metadata across the capture and the
expected custom-domain attachment. Worker settings, script settings, one active
version's metadata and unversioned content were captured privately on the runner.
This is a partial observation, not an exact rollback qualification.

The current CI credential received HTTP 403 for zone routes, zone settings,
page rules and all ten queried ruleset phases. Missing pagination metadata for
the deployment/domain lists remains explicitly unresolved. Unversioned content
is not proved identical to every active weighted version. No private runner
payload was uploaded; only the allowlisted receipt was retained. Therefore
`inventoryComplete`, `restorationReady` and `privateCaptureDurablyRetained`
remain false. No deployment, binding, credential or feature gate was changed.

#0036's owner handoff is concrete: provide an authorized reader covering those
blocked zone metadata operations and a durable private local capture route for
the exact restoration inputs. A local read-only token/account configuration is
one option; existing permission should be reused when it genuinely covers the
scope. Do not broaden or replace the existing CI credential implicitly, publish
private inputs to this public repository, or treat historical local artifacts
as current readback. Exact-version binding and complete effective-edge coverage
still require evidence after access/retention is available.


## Local capture and endpoint-contract correction

Terry supplied a separate temporary Cloudflare token after reviewing its scoped
Read permissions. The first local run made 21 GET requests, observed stable
deployment metadata and the expected domain attachment, and resolved the
previous route/settings/Page Rules permission failures. Its ruleset phase
responses (400/404) were retained as unknown, never silently treated as absence.

Private evidence is retained under
`C:/Users/TDO-XPS15-2024/Documents/ChatGPT/FGA/private-evidence/0036/`, outside
the public repository. Each run owns a new UTC-named directory. Windows ACL
inheritance is removed on that root; the current owner and SYSTEM have access.
The temporary token stays in the owner-designated file and is not copied into
the evidence. This is local retention, not an assertion of a separate backup.

The earlier generic pagination check was too strict for some endpoint shapes
and insufficient for complete deployment history. Primary-source checks found:

- [Deployment lists](https://developers.cloudflare.com/api/resources/workers/subresources/scripts/subresources/deployments/methods/list/)
  support bounded page/per_page enumeration. First-page success alone does not
  prove complete history. Pin and re-read the active version/weight tuple.
- [Domains](https://developers.cloudflare.com/api/resources/workers/subresources/domains/methods/list/)
  expose hostname/service filters and optional totals; missing total_pages alone
  is not proof of incomplete results. Conflicting or additional-page evidence
  still refuses completion.
- [Page Rules](https://developers.cloudflare.com/api/resources/page_rules/methods/list/)
  are a documented single list, without required pagination metadata. An empty
  successful array is a meaningful configured-none observation.
- [Ruleset lists](https://developers.cloudflare.com/api/resources/rulesets/methods/list/)
  use cursors. Capture both account and zone scope, listed root/zone entrypoints
  and execute descendants with concrete versions and overrides. A complete
  empty list can establish no configured entrypoint; generic 400/404 cannot.
- The [beta version GET](https://developers.cloudflare.com/api/resources/workers/subresources/beta/subresources/workers/subresources/versions/methods/get/)
  accepts a fixed Worker name and a full version UUID with include=modules.
  Validate the returned identity and complete module payload rather than
  relabeling an unversioned artifact as an exact version download.

Unreadable secret values do not by themselves block a configuration inventory.
[Documented deployment preservation](https://developers.cloudflare.com/workers/configuration/secrets/)
and [retained-version rollback](https://developers.cloudflare.com/workers/versions-and-deployments/rollbacks/)
are available preservation routes. Capture binding names/types and target
identities privately; changed-secret compatibility, resource continuity and any
forced rollback semantics must be resolved before a later execution packet.
No force path is authorized here. Recreating a deleted Worker or lost secret
state is outside this preservation assumption.

#0036 captures inputs and explicit unknowns. #0043 owns the nonproduction
restoration rehearsal, and #0037/later edge work own actual-path behavior.
Keep restorationReady false until those separate gates pass; do not demand a
live restoration or edge test merely to finish the metadata inventory.


## Final local input inventory: ready for review

The final capture at 2026-10-16 21:47:40 UTC made **14 GET requests**. All required
metadata inputs passed validation, the deployment stayed stable, and the expected
domain attachment was enabled. The exact active version response matched the
pinned full UUID and its modules validated. Successful account and zone ruleset
catalogues contained managed definitions but **zero configured root/zone
entrypoints**. That is not a claim that provider defaults or runtime errors do
not exist. Page Rules and routing/settings were captured successfully.

The [sanitized local receipt](../evidence/existing-photo-inventory-local-2026-10-16.json)
records inventoryComplete, metadataInputsComplete and exact-version artifact
binding as true. The collector intentionally leaves its generic retention flag
false: the separate parent-owned local attestation verifies the actual
destination. It checked restricted root and descendant ACLs, all captured manifest digests and token
absence in **15 private files / 1,083,133 bytes**. Raw settings, identities,
binding names, source/modules and exact restoration inputs remain private.

Current collector bounds are 96 GET requests, eight pages per ruleset scope,
32 ruleset nodes, eight active versions, 128 modules per version, 16 MiB per
response, 64 MiB aggregate response bytes (plus a one-byte refusal sentinel) and
a 180-second process watchdog. It supports documented optional cursors.after
and the installed SDK's older singular cursor, refusing malformed or conflicting
forms. Missing optional pagination metadata alone is terminal for ruleset lists.
Known digit-bearing phases such as ddos_l7 are valid bounded metadata labels.

Independent Sol / High review reproduced and closed malformed-result false
completion, cursor/list shape, context zone binding, cycle detection and byte
budget issues. All **31 focused tests**, Ruff/format and Pyright passed. No live
application request, provider write, migration, deployment, Flickr request or
desktop action occurred.

Private retrieval: use the UTC run directory `20261016T214740Z` beneath the local
root above. `private/restoration-inputs.json` indexes exact captured endpoint
payloads and their SHA2-256 digests, pinned version weights and module metadata;
the complete version response retains module bytes in base64. The sibling
private-integrity-index.json records every retained file and its hash. Neither
the raw capture nor that private index belongs in Git or a public artifact.

#0036 no longer needs an owner access/retention input. It can hand off for review
as an input inventory. `restorationReady` and `edgeBehaviorQualified` remain
false: #0043 must demonstrate preservation/restoration under its reviewed packet;
#0037 and subsequent edge work must qualify effective actual-path behavior.
Settings remain capture-time observations without an atomic cross-service
fence and must be refreshed before a later live change. Retaining an existing
version is not a backup of deleted provider resources or lost secret state.
