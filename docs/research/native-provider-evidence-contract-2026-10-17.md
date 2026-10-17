# Native provider supplemental evidence: SDK entry conditions

Date: 2026-10-17

Status: Research and proposed evidence criteria for #0158. Source preparation
only; no native run, host qualification, production enablement, or amendment of
an accepted pre-render requirement is recorded here.

The supplemental fixture must receive its publish context from the Lightroom
Classic host's registered provider callback. A table assembled by fixture code,
an extra context marker, or a manually completed receipt cannot establish that
entry condition. A separately constructed export session remains useful for
render tests, but its documented contract does not establish a publish callback.

## Sources and limits

Reviewed the licensed local Adobe Lightroom Classic SDK 15.3 Release API
Reference, build `202604090947-8f3672ed`, identified by the bundle's `Readme.txt`.
The module and member locators below permit local reinspection without copying
licensed documentation, samples, assets, or source into this repository.

- `SDK - Export service provider.html`: `processRenderedPhotos`,
  `updateExportSettings`, `startDialog`, `exportPresetFields`,
  `allowFileFormats`, `allowColorSpaces`, `canExportVideo`, `hideSections`.
- `SDK - Publish service provider.html`: `getCollectionBehaviorInfo`,
  `viewForCollectionSettings`, `endDialogForCollectionSettings`.
- `LrExportContext.html`: module description, `propertyTable`, `exportSession`,
  `publishService`, `publishedCollection`, `publishedCollectionInfo`,
  `configureProgress`, `renditions`, `startRendering`.
- `LrExportSession.html`: constructor, `doExportOnCurrentTask`, `photosToExport`,
  `removePhoto`, `renditions`.
- `LrExportRendition.html`: `waitForRender`, `skipRender`, `wasSkipped`.
- `LrPublishedCollection.html`: `getCollectionInfoSummary`, `getService`,
  `isSmartCollection`, `localIdentifier`; `LrPublishService.html`: `getPluginId`.
- `LrCatalog.html`: `getPropertyForPlugin`, `setPropertyForPlugin`,
  `withPrivateWriteAccessDo`; `LrPhoto.html`: `getPropertyForPlugin`,
  `setPropertyForPlugin`.
- `LrFileUtils.html`: `fileAttributes`, `resolveAlias`, `resolveAllAliases`.
- Local SDK Guide, Chapter 3, page 61 (printed and PDF page): built-in property
  keys, Export Location section. This names `LR_export_destinationType`
  (including `specificFolder`), `LR_export_destinationPathPrefix` (destination
  folder), and `LR_export_useSubfolder` (Boolean subfolder choice).

Adobe's public [SDK overview](https://developer.adobe.com/lightroom-classic)
confirms the export/publish extension scope. Its
[Publish workflow help](https://helpx.adobe.com/ie/lightroom-classic/desktop/export-photos/export-hard-drive-using-publish.html)
describes the ordinary Publish action; it is not an API guarantee for a custom
provider. Third-party mirrors and community posts do not override the pinned
local SDK reference. No newer host behavior is inferred from a mirror.

## Genuine callback context and selection

- Register the new fixture's provider through its own manifest and obtain
  `functionContext` and `exportContext` from the host's
  `processRenderedPhotos(functionContext, exportContext)` invocation. Keep this
  observation separate from direct calls to fixture/provider functions in unit
  tests. The callback runs in the host-provided cooperative task; its function
  context ends when the callback returns.
- The SDK exposes `LrExportContext` through that callback, rather than as an
  importable constructor. Its `publishService`, `publishedCollection`, and
  `publishedCollectionInfo` exist only for publishing. A plain export therefore
  cannot substitute for the Album/default-collection observations.
- Inspect the actual callback's collection summary and parent service through
  documented methods. The summary includes `localIdentifier`,
  `isDefaultCollection`, `collectionSettings`, `publishSettings`, `remoteId`, and
  `remoteUrl`. `getService`, `getCollectionInfoSummary`, and `isSmartCollection`
  require the asynchronous task context; do not call `isSmartCollection` inside
  the write gate that created that collection. Compare the actual service's
  `getPluginId()` with the new fixture identifier. Names are display data.
- Walk `exportContext.exportSession:photosToExport()` for the selected session
  work. That iterator snapshots its list at creation. Removing a photo does not
  change an already-open photo iterator, but it excludes that photo from later
  iterations. Record exclusions explicitly; do not assume iterator mutation
  proves the rendering engine had not already begun work.
- Existing accepted selection UX and outbox evidence remain scoped evidence.
  The supplemental observation concerns the actual callback's service/Album/
  photo scope, its saved selection revision, and the durable frozen snapshot.
  A different in-memory table after a save cannot prove a durable snapshot.

## Before-render requirement: preserve the unresolved distinction

The SDK documents `updateExportSettings(exportSettings)` before rendition
objects are generated. It supplies only the settings table, not a documented
publish context or photo-selection argument. It supports settings projection;
it does not establish the accepted per-photo durable selection snapshot.

The SDK describes `processRenderedPhotos` as processing rendered output, while
`LrExportContext:startRendering()` starts rendering in a separate task and
`renditions()` starts it if needed. The reference does not resolve this tension
into an unconditional promise that no render begins before callback entry.

Therefore record the actual callback entry and the order of the fixture's own
operations on the target host. Preparing the snapshot before the fixture calls
`startRendering`, `renditions`, or `doExportOnCurrentTask` proves that local call
order only. It does not prove the stronger accepted requirement that the
rendering engine had not already started. Retain that requirement as unresolved
unless a documented entry contract or additional independently reviewed host
measurement establishes it; do not silently rename it "before waitForRender".

Before calling `exportContext:renditions()`, call the documented
`exportContext:configureProgress()`; the API reference makes this a precondition.

The `LrExportSession` constructor accepts photos and export settings.
`doExportOnCurrentTask()` requires an asynchronous task and waits for rendition
creation. Neither member documents construction of `LrExportContext`, a publish
collection binding, or invocation of this provider's callback. Do not rely on an
undocumented export-setting key to supply those facts.

## Default collection, ordinary Album, and native controls

- `getCollectionBehaviorInfo` can configure the host's built-in default
  collection, including its name/deletability, whether collection creation is
  allowed, and collection-set depth. It is not an API to turn the default
  collection into an ordinary Album or make it publishable under FGA policy.
- Observe the genuine default callback's `isDefaultCollection == true` and
  refuse it before the fixture requests rendition iteration, rendering,
  credential acquisition, or synthetic transport. Record zero calls at those
  fixture boundaries. That proves refusal by plug-in code, not zero rendering
  performed internally by the host before entry.
- Observe a genuine ordinary Album with `isDefaultCollection == false`, an
  ordinary rather than smart collection, the correct parent provider, and
  valid retained collection settings. Never substitute a manufactured
  `publishedCollectionInfo` table for this observation.
- `viewForCollectionSettings` receives an observable `collectionSettings`
  record. `LR_canSaveCollection`, `LR_liveName`, and `LR_canEditName` are
  documented controls. Plug-in settings saved with a collection use scalar
  numbers, strings, or Booleans; the transient `pluginContext` is discarded
  after the dialog. Reopen and read retained settings rather than treating
  dialog-local values as persistence evidence.
- `exportPresetFields` declares retained plug-in fields and initial defaults;
  subsequent activation reuses prior user choices. `allowFileFormats` and
  `allowColorSpaces` restrict dialog choices, `canExportVideo` controls video
  support, and `hideSections` controls visibility. None proves the rendered
  PNG's profile identity. Hiding export location also gives temporary output
  whose lifetime ends with export completion; inspect/copy only inside the
  authorized bounded callback lifetime.
- The Guide's page 61 destination keys can select an explicit folder with
  subfolders disabled. Verify the actual session settings and returned output
  path rather than inferring them from a configured UI. This selects a render
  destination; it does not establish exclusive filesystem ownership.

`LrFileUtils.fileAttributes()` documents size and creation/modification dates,
not reparse-point flags. `resolveAlias()` and `resolveAllAliases()` document
Mac aliases and Windows shortcuts. Their contract does not explicitly cover
every Windows junction, symbolic link, or reparse point. Equal normalized or
alias-resolved paths therefore cannot prove complete reparse protection.

## Persistence and source-ready ordering

Catalog-wide `setPropertyForPlugin` accepts scalar data, requires a documented
write gate, and needs no metadata-provider field declaration. Use a bounded
encoded string and `getPropertyForPlugin` to read it back. The private write
gate explicitly permits that catalog-property operation; an `executed` result
and successful readback differ from `queued` or `aborted`. Per-photo
`setPropertyForPlugin` instead requires a declared `LrMetadataProvider` field
and a catalog write gate. Keep the exact toolkit identifier stable across the
two authorized persistence phases.

An actual normal host close/reopen must be independently observed for a
host-restart claim. Changed clocks, run tokens, globals, callback counters, or
plug-in reloads cannot establish a new host process. A later read of the exact
persisted synthetic record proves the bounded persistence observation only
when that distinct lifecycle is separately established. This note identifies
no documented SDK host-process lifecycle identifier.

Before source readiness, deliberately attempt only the injected synthetic
authorization boundary and require denial with zero synthetic transport calls.
Keep all real credential/network capabilities absent. `waitForRender()` yields
until output is ready and returns success plus a path, but a previously skipped
rendition can return success without a file. Require a non-skipped rendition
and bounded successful file validation before marking source ready or allowing
the synthetic authorization operation. Actual PNG/profile validation remains
separate evidence; marker presence or a profile's display name is insufficient.
`rendition.wasSkipped` is a read-only property, not a callable method.

## Future evidence interpretation

The new fixture needs a new identifier/build/version and a separate receipt
schema. Preserve the prior fixture and its pins. Retain only sanitized stage
names, finite counts, booleans, bounded error categories, and source/build pins
in public evidence; no object serialization, catalog names, paths, photo
metadata, rendered bytes, licensed content, credentials, or authorization data.

Offline tests can verify receipt rejection, explicit order, finite bounds, and
the absence of network/credential capabilities. They cannot pass the actual
callback, default/Album, host-restart, rendered-profile, or rendering-engine
scheduling observations. A future exact native packet and its independent
review must preserve those distinctions before any host action is requested.
