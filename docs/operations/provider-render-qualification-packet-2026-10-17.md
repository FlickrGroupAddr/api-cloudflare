# Provider/render qualification packet

Date: 2026-10-17. Status: #0123 native fixture source prepared; no native load,
execution, consent or qualification result. #0135 owns action-time authorization;
#0126 owns the later authorized native run and assessment.

The candidate is `FGA-ProviderRender-Qualification.lrplugin` version `0.0.1.2`,
targeting Lightroom Classic host 15.6 with SDK 15.3, major 15 only. This candidate
supersedes the earlier constructor-only `0.0.1.1` artifact and its digest. Its
qualification-only `Info.lua` registers an explicit Library menu, test publish
provider and actual private photo metadata declaration. Production registration
remains untouched. The test provider refuses ordinary Publish; the menu enters
`Native.run` only after checking exact artifact, catalog and current consent.
No automatic run callback is registered.

The accepted [publish flow Phase 4](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/zero-state-publish-flow.md#phase-4--per-photo-selection-rendering-and-preflight)
controls selection-before-render and full-resolution 8-bit sRGB PNG behavior.
The [frozen-context note](../design/publisher-frozen-context-2026-10-17.md) and
[rendition note](../design/publisher-rendition-adapter-2026-10-17.md) describe
implementation evidence without amending accepted policy. Settled #0027/#0029
UX and historical experiments are not repeated here.

## Exact artifact preparation

Use the pinned repository uv workflow for local source preparation:

```console
uv run --frozen python scripts/prepare_provider_render_qualification.py <new-private-stage>
uv run --frozen python scripts/prepare_provider_render_qualification.py <private-stage> --verify --expected-artifact <retained-SHA2-256>
```

The new stage must have an existing parent outside the source checkout. Use the
private evidence workspace, never a real catalog or retained photo directory.
The preparer copies exactly 24 allowlisted Lua files byte-for-byte: nine fixture
files, seven actual publisher modules and eight actual client dependencies,
including `MetadataDefinition.lua`. The native dispatcher, generated-asset
implementation and test provider are included. Shared behavior remains in actual
shared modules; qualification-only factories do not activate production paths.
No SDK binaries, credentials, private configuration or real photos are copied.

`manifest.json` records source paths, filenames, byte counts and SHA2-256 digests
plus version/host/SDK identity. Its aggregate digest hashes the canonical identity
JSON before adding that digest field. JSON uses sorted keys, two-space indentation,
ASCII escaping and one final LF. No timestamp/machine path enters its identity.
The final manifest bytes have a second independently retained SHA2-256 digest
used by the native consent guard. Retain both digests separately; a replaced
self-consistent manifest is not authentication. Vendored dkjson's existing
optional `debug`/`lpeg` imports are recorded; neither is copied or enabled.

`run-plan.json` records finite scope and unmeasured status. `consent-template.json`
contains exact future consent keys with null owner/catalog/times and false
permissions. **It is invalid consent.** Keep it unchanged in the immutable stage;
after Terry's actual #0135 decision, retain the authorized consent separately
outside the stage. Verification rejects changed/missing/extra/linked files,
changed plan/template and a mismatching independent artifact digest. Source
closure and Config/Info/Package metadata drift refuse before staging. Source
changes require fresh stages, digests and consent to that exact candidate.
Private `batch0123-packet-evidence.md` retains the actual stage/digests; the old
20-file pin is superseded and must not authorize execution.

## Finite native and synthetic scope

`Config.CASES` binds 14 ordered cases: absent selection, explicit none, groups,
edits after freeze, photo failure isolation, target rejection, catalog change,
activation change, cancellation, failed render, missing file, oversized file,
changed file and cleanup/revocation. The dispatcher uses actual SDK catalog,
service, Album, photo and `LrExportSession` objects, finishes actual provider
pre-start preparation before the first `renditions` call, and consumes actual
shared selection/frozen/rendition/preflight code. Ordinary `processRenderedPhotos`
still refuses. Native faults are labeled injections; injected changes do not
prove the host independently generates those conditions. Synthetic transport
consumes leased bytes in memory with no network operation.

Receipts retain bounded fixed case/phase/code/boolean fields; native rows
distinguish injections from host-generated behavior. `faultRequested` records
intent separately from `boundaryFaultInjected`, which becomes true only when
the injection is actually applied. A raw native rendering failure cannot pass
an injection case. Every case needs a terminal
result; missing/unknown/not-run results are inconclusive. `nativeSchedulingProven`
and production qualification stay false pending separate evidence assessment.
Rendered byte metadata is measured only in a future run; ICC presence alone is
not proof of sRGB (`profileVerified` remains false). Native reports retain sanitized
`actualHost` major/minor/revision/build/buildVersion alongside `fixtureVersion`
and `declaredSdkVersion`. These are distinct observed host and declared fixture
provenance; the SDK declaration is not a runtime SDK measurement.

The [SDK rendition research](../research/flickr-rendition-policy-2026-10-17.md)
records the SDK control gap: its guide documents `LR_export_bitDepth` only for
TIFF/PSD. PNG support documentation supplies no documented guarantee that
requesting 8-bit yields 8-bit PNG. Native evidence or a separately accepted
boundary is required. No format/quality/sizing/second-render fallback is
authorized. SDK syntax and synthetic success do not prove native PNG depth,
dimensions, sRGB, scheduling, cancellation or cleanup.

## Action-time consent and future operator checklist

No appointment is proposed. Starting new case work is limited to **30 minutes**. #0135 must
choose exact start/expiry and retain Terry's actual consent. The external JSON
selected through the explicit menu's Open Panel has exactly these fields:

- `schemaVersion: 1`, `owner: "Terry"`, exact `artifactSha2_256`, and separately
  retained exact manifest-byte `manifestSha2_256`.
- `catalogPath`: exact absolute new catalog path, basename
  `FGA-ProviderRender-Disposable.lrcat`.
- `grantedAt`/`expiresAt`: Unix seconds, positive duration at most 1800 seconds;
  current action time must fall inside that interval.
- Four true permissions: `allowQualificationProvider`,
  `allowSyntheticCatalogWrites`, `allow200000001ByteScratch`, `allowCleanup`.

Terry's future approval must explicitly cover the following bounded actions:

1. Load this exact isolated qualification menu/provider/private metadata schema.
   Manually create one empty qualification publish service in the new catalog.
   Start with zero photos, no child sets or ordinary Albums and no fixture-private
   records. An empty host default collection may exist.
2. Generate/import 15 tiny synthetic TIFF assets; create one ordinary test Album;
   write only generated photo/catalog selection/correlation fields and finite
   injected faults. Permit a 200000001-byte oversized scratch file. No real
   retained assets, account credentials, provider/cloud operations or upload.
3. Create fixed sibling scratch directory `FGA-provider-render-qualification-v1`,
   refusing if it exists. Run only 14 cases while consent bytes/time and catalog
   scope remain valid. Changed/removed consent, expiry or catalog change stops
   further case work and consumption; already started host rendering may remain active.
4. Separately authorize cleanup to wait for already started rendering after
   consent expiry/revocation, solely to observe termination, without consuming or
   decoding files. Those waits may exceed the 30-minute case-work window. This
   supplies no forced cancellation or hard-stop guarantee and passes no #0037
   gate. The dispatcher waits at most once on each observed raw rendition and
   requires iterator completion/count evidence for all started session work.
   Only proven terminal rendering permits deletion of owned private fields,
   generated Album or files. Unknown/unseen/failed drain evidence preserves all
   catalog state and files, records cleanup incomplete and forces overall false.
   Unexpected output likewise causes incomplete cleanup, never recursive deletion.
5. If completion is unresolved, preserve the catalog/files and do not dispose
   of anything while host rendering may be active. After confirmed termination,
   close Lightroom Classic, remove the qualification plug-in, then manually
   dispose of the **entire dedicated disposable catalog** and test workspace.
   Generated photo catalog rows and the qualification service remain until this
   manual disposal; automated cleanup does not claim to remove them. Retain a
   private receipt for manual disposal.

Before a future load, verify both pinned digests, current host 15.6/build/SDK,
independent review and the new empty catalog. Manually verify and retain the exact
host build observation with Terry's action-time approval; the consent JSON schema
has no build field. Compare that observation to the future `actualHost` receipt. The native guard refuses foreign/
populated catalogs, wrong basename, extra services, stale/changed consent and
unexpected initial records. Merely labeling an existing real catalog disposable
never authorizes it. Preserve native observations and terminal/cleanup receipts
privately; do not publish catalog paths, identifiers or image bytes.

All native measurements remain **unmeasured** at preparation time. This packet
passes no #0126, #0037, provider-restoration or final #0026 gate. Source preparation
is not evidence of consent or execution.
