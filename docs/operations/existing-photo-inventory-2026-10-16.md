# Current fixed-origin provider inventory preparation

Date: 2026-10-16. Ticket #0036. Status: prepared offline; no remote read,
production mutation, deployment or exact-restoration claim is recorded here.

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
