# Supplemental native evidence preparation

Date: 2026-10-17. Status: source preparation for #0158; **no native action
authorized or performed**. This supplement feeds the later #0124 packet and
#0128 execution review. #0137 retains the exact action-time decision. The old
#0135 decision and #0126 execution do not cover this new fixture.

The new `FGA-ProviderRender-Evidence.lrplugin` version **0.0.1.1** has toolkit
identifier `com.sixbuckssolutions.fga.providerrender.evidence.lrc15`, targets
Lightroom Classic host **15.6**, and declares SDK **15.3**. It is separate from
the immutable 0.0.1.2 qualification fixture. Declared SDK metadata does not
identify the runtime SDK or prove scheduling.

`Config.lua` and `Package.lua` keep native readiness, native scheduling proof
and production qualification false. The source-only artifact therefore refuses
execution. A later reviewed executable candidate must resolve the readiness
gate and receive new source/manifest pins before any action-time consent.
Documented SDK interfaces do not presently establish Windows reparse-path
identity, exclusive atomic output creation, bounded SDK waits or default-target
host drain. These are explicit unresolved boundaries; this candidate is
unavailable for native actions even with a newly filled consent record.
Source preparation, mocked tests, manually assembled contexts and an
`LrExportSession` constructor do not prove an SDK-created callback capability.

## Actual source interfaces and pins

From the implementation checkout, the offline preparation interface is:

```text
uv run --frozen python scripts/prepare_native_evidence_checks.py NEW_PRIVATE_STAGE
uv run --frozen python scripts/prepare_native_evidence_checks.py PRIVATE_STAGE --verify --expected-artifact RETAINED_ARTIFACT_SHA2_256
```

The parent operator selects the new private destination outside the checkout.
The preparer only copies its explicit source closure, never loads the fixture,
and emits `manifest.json`, `run-plan.json` and `consent-template.json`. The
manifest binds the 24 Lua files and the actual offline preparation/profile
checking Python sources. SHA2-256 covers exact bytes, source paths, version and
host/SDK metadata; the printed manifest digest also pins its exact bytes.
The preparer independently pins the complete reviewed `Config.lua`,
`Package.lua` and `Info.lua` bytes. Duplicate declarations, executable
expressions and any other metadata edit require review and explicit pin
updates; the preparer never evaluates Lua to inspect metadata.
Retain both digests independently and reverify after staging. The final parent
commit and private staging receipt bind the reviewed source revision; no
uncomputed hash or earlier fixture pin is substituted here.

The consent template is deliberately invalid: owner, run/action identifiers,
phase, exact catalog path and times are null; every permission is false.
Actual consent belongs in a separate private action-time record. Never edit the
staged template or treat a prepared plan as a grant. Each finite phase requires
its own run/action binding, bounded positive consent interval of at most 1800
seconds and source-verified consumed-once checks. Unknown outcomes stop the
program; retrying or replaying a phase is not authorized by the prior grant.
The 1800 seconds bound consent validity only. It does not bound elapsed native
execution, `waitForRender()` or host abort/cleanup time. The plan explicitly
records `hostWaitBoundProven=false`.

## Future finite program

These are future operations requiring a complete reviewed #0124 packet and
fresh exact owner decisions. They are not instructions to set up a catalog now.
Use the fixture's actual `Run.lua` menu entry and `Native.run()` phase handling;
publish callbacks enter through
`EvidenceProvider.processRenderedPhotos(functionContext, exportContext)` and
`Native.callback(functionContext, exportContext)`.

| Phase | Future observation and boundary |
| --- | --- |
| `prepare` | Guard the exact new empty disposable catalog `FGA-NativeEvidence-Disposable.lrcat`, exact fixture identity and one fixture publish service. Generate/import exactly one original 8 x 8 RGB TIFF, create one ordinary Album and bind the finite scope. No real photo, provider account or credential. |
| `default_callback` | One future actual host Publish action for the default target could observe refusal and zero plug-in render requests. The source does not iterate renditions in this branch and reports `renderCompletionProven=false`; host drain remains unknown and requires separate evidence. Preserve native work while that outcome is unresolved. A manually injected target flag does not replace an actual host observation. |
| `album_callback` | One actual host Publish action for the ordinary Album. Observe the SDK-created callback and finite rendition handling; stage only the owned synthetic rendered PNG, bounded to 32 MiB, in private `FGA-native-evidence-v1`. Source trace ordering does not prove undocumented SDK internals. |
| `restart_prepare` | Use the `Persistence.new(...)` object's `prepare(actionId)` through the native phase to seed/read the actual selection/outbox, upload-attempt and correlation fields. Retain a private hash-bound restart envelope. This in-process readback alone does not pass restart persistence. |
| `restart_observe` | After independently observed normal host exit and manual reopen of the same exact catalog, use that object's `observe(actionId)` through the native phase and fresh consent. Join its consumed-once readback with separate process/catalog observations. The Lua result deliberately keeps `restartProven=false`; no SDK process-lifecycle identity is invented. |

The callback module forwards the actual two host callback arguments. Qualification
of this route remains a future native measurement; the source does not turn a
manual context into an actual SDK callback. Keep only the missing profile,
callback, restart/default/Album and source-ready/no-auth observations here.
Reuse accepted UX/outbox scope rather than reopening unrelated product choices.
Default-target rejection can establish zero plug-in render requests, but cannot
establish that the host rendering engine had not already started preparation.
The [SDK evidence contract](../research/native-provider-evidence-contract-2026-10-17.md)
records that remaining scheduling limit and the actual callback interface.

## Private profile evidence

The actual offline analyzer interface, applied only to a newly authorized
synthetic PNG, is:

```text
uv run --frozen python scripts/native_profile_evidence.py PRIVATE_SYNTHETIC_PNG
```

`analyze_png(bytes)` and `analyze_file(Path)` validate bounded static RGB PNG
framing, chunk CRCs and bounded iCCP decompression. The fixed independent
reference is ICC's published `sRGB2014.icc`, 3024 bytes, SHA2-256
`384b832de3412066743b52a75ee906b6fb9fb8d9e09e936fc2c43223815c6e0a`.
The analyzer source records its official provenance, profile meaning and
license/specification links. No observed PNG can supply its own trusted pin.
There is no runtime download or separately staged ICC binary to publish.

Only an exact reference match establishes that embedded profile's identity.
A marker/name alone fails; different bytes are an unresolved identity result,
not proof that the profile is not sRGB. This does not validate rendered pixel
conversion or production behavior. Preserve the source PNG privately until
its pinned analysis and review complete; retain only the sanitized result and
digests for publication. The removed #0126 outputs cannot be retroactively
profile-qualified from their old receipts.
Require the analyzer's `input_png_sha2_256` to equal the native receipt's
`renderedPngSha2_256` and `input_png_bytes` to equal `renderedPngBytes` for the
exact staged fixture run/action and fixed owned PNG filename. Filename and
byte count alone do not establish this join.
A profile match for an unrelated PNG is not evidence for this fixture run.

## Manual reopen and disposal boundary

The future operator must record normal host closure, observed process exit and
the same exact catalog reopened, separately from fixture observations. There is
no automatic host restart or cleanup phase. After all terminal rendition and
consumption evidence is retained, obtain the exact separate disposal decision.
Unregister only this fixture, close the host normally, verify exit, resolve the
exact approved disposable folder inside its allowed boundary, reject linked
paths and active locks, and then dispose only that folder. Preserve immutable
source/manifest/plan, actual consents, phase receipts and sanitized analysis
outside it. Private rendered bytes and catalog data have their own explicit
retention/disposal decision; they are never committed.

Any host, catalog, fixture pin, phase, time window or scope mismatch stops the
future run. No provider/network, credential, production activation, automatic
replay or general catalog access follows from this preparation. The final
#0124/#0128 assessment must distinguish source checks, native observations and
remaining qualification limits, even when every finite case passes.

## Offline verification handoff

Fresh independent reviews passed for the profile analyzer, disabled fixture
and packet preparation. The parent integration run passed 50 tests: 11 profile,
30 Lua fixture/source tests and 9 packet integrity tests. The Lua checks include
compilation of every new fixture module without host initialization. Scoped
Ruff checks, formatting and Pyright passed with the pinned project tools.

Corrections independently rechecked include bounded evidence reads, late-write
fencing, consumed-once artifact/phase binding, complete reviewed metadata pins
and exact native-to-analyzer PNG hash/size joins. These are source and mocked
observations. No fixture was loaded, no catalog was written, no rendered image
was acquired and no native qualification was performed by this work.
