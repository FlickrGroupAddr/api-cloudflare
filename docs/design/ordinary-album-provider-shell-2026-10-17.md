# Unregistered ordinary-Album provider shell

Date: 2026-10-17. Status: isolated implementation for #0096; native integration
and release qualification remain pending.

The original Lua factory in `clients/lightroom/publisher/OrdinaryAlbumProvider.lua`
returns documented callback shapes. `OrdinaryAlbumProviderSettings.lua` owns only
local collection settings. Neither file is registered in `Info.lua`, copied
from Adobe samples, or wired into a production upload path.

Authority remains the accepted architecture repository's
[album-scoped contract](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/album-scoped-publish-contract.md),
[ADR0028](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/decisions/0028-support-ordinary-albums-only.md)
and [accepted #0090 identity wire](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/proposals/publish-service-identity-wire-2026-10-16.md).
This note describes the shell; it creates no new normative schema.

## Implemented boundary

- New ordinary collection settings initialize only `schemaVersion=1` and
  `albumLifecycle=local_unbound`. SDK `LR_canSaveCollection` is a dialog control.
  Existing/partial/unknown settings cannot be reset into an unbound Album.
  Dialog settings are SDK observable proxies: the documented :pairs() method
  enumerates their stored properties. Plain collection-summary records use
  Lua pairs explicitly; built-in pairs is never used for dialog settings.
- The settings view offers local creation text, with no remote Album picker,
  lookup, placeholder photo, identity issuance, or Flickr operation.
- Default, smart, missing-kind, and malformed collection dialogs cannot save.
  Target validation rejects default/smart collections before identity verification.
- Every recorded remote ID or URL is rejected, including empty, malformed,
  orphaned, matching-looking and conflicting values. This shell has no hosted
  album evidence and cannot adopt or reconcile any remote identity. Bound Albums
  need the separate #0116 integration.
- The target key uses the documented numeric `collection.localIdentifier`,
  cross-checked against its summary, and the verified server-issued service ID.
  Canonical decimal formatting uses string.format('%.0f', id) for every
  accepted positive safe integer, preserving distinct IDs near 2^53.
  Parent names and parent remote IDs do not participate. Reparenting local
  collections performs no remote operation.
- `processRenderedPhotos` stops with a fixed message for every target. It never
  enumerates renditions, calls `waitForRender`, writes catalog remote IDs, or
  invokes an upload. Future integration must preserve this target gate before
  any render request; it must not turn shell success into upload authority.

## SDK 15.3 mapping

Inspected local API reference under architecture-design `vendor/LrC SDK/15.3`:

| Callback or API | Shell use |
| --- | --- |
| Publish service provider `titleForPublishedCollection` and standalone form | Album terminology |
| `viewForCollectionSettings(f,publishSettings,info)` | Documented `collectionType`, `isDefaultCollection`, `publishedCollection`, and observable `collectionSettings`; uses `LR_canSaveCollection` |
| `validatePublishedCollectionName` | Local nonempty name check; duplicate names permitted |
| `getCollectionBehaviorInfo` | Deliberately absent: never requests a default collection |
| Export service provider `processRenderedPhotos` | Fixed refusal before rendition iteration |
| `LrExportContext.publishedCollection` / `publishedCollectionInfo` | Actual target and independent default/remote-record checks |
| `LrPublishedCollection:isSmartCollection`, `getService`, `getCollectionInfoSummary`, `localIdentifier` | Task-time target checks and local identity |
| `LrPublishService:getPluginId` | Reject other providers |
| `LrTasks.pcall` | Must be injected for yielding SDK calls; synthetic tests inject Lua `pcall` |

The SDK reference documents smart-collection labels and `collectionType`, but
this inspection did not establish a supported property that hides the host's
Create Smart Album menu. No invented `supportsSmartCollections` switch is used.
The unregistered shell exposes no native menu and refuses smart dialog/target
inputs. Any future registration must establish native menu suppression or
resolve that concrete SDK limitation before claiming the accepted UI boundary.
Native dialog save/cancel persistence and pre-render timing remain host gates.

## Identity injection

`Provider.new { pluginId, pcall, verifyService }` receives no HTTP, random,
provisioning, catalog-write, Flickr, or file capability. `verifyService(settings)`
returns `{ok=true, identity=<complete accepted saved identity>, linkStatus='ready'}`
only after fresh GET and exact durable record verification. #0109 supplies that
independent adapter; this shell never calls its provisioning operation.

`validateTarget(publishSettings,exportContext)` deliberately verifies the
collection summary's documented `publishSettings`, rather than the caller's
untrusted settings argument. The adapter must scope its durable reread to that
configured service. A rejected/malformed/non-ready result yields no target key.
The returned target contains only the service ID, linked revision and canonical
local collection identifier. This is a preliminary key, not a lease or hosted
Album-binding authorization. Every later write still needs transactional fences.

## Verification and limits

Twelve Python unittest cases execute both actual modules under `lupa.lua51` with
synthetic documented SDK objects. They exercise creation, refusal without reset,
default/smart/foreign targets, ID consistency, remote IDs/URLs, reparenting,
identity refusal, stopped rendering, and unchanged registration. Proxy-shaped
observable regressions exercise backing fields invisible to built-in pairs;
near-maximum integer regressions prove exact distinct natural-key strings. The fake SDK
provides no import, catalog-write, network or Flickr capability.

Run using the pinned uv environment without updating global tooling:

```console
uv tool run --from uv==0.12.5 uv run --frozen python -m unittest discover -s tests -p test_ordinary_album_provider.py
uv tool run --from uv==0.12.5 uv run --frozen ruff check tests/test_ordinary_album_provider.py
uv tool run --from uv==0.12.5 uv run --frozen ruff format --check tests/test_ordinary_album_provider.py
uv tool run --from uv==0.12.5 uv run --frozen pyright tests/test_ordinary_album_provider.py
```

Adobe SDK15.3 Windows `luac -p` compiles both new Lua modules. Synthetic success
and compilation do not qualify Lightroom Classic 15.6, live settings durability,
real rendering, hosted execution, or Flickr behavior. No native app, catalog,
cloud service, real SDK object, or Flickr API was invoked.
