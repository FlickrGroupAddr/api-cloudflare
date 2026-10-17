# Exact native provider/render action decision

Date: 2026-10-17. Status: prepared for Terry's decision on #0135; **not
authorized and not executed**. Recommendation: offer the bounded synthetic
fixture below for action-time approval after independent review. #0123 is
Completed source preparation; #0126 retains execution and qualification.

This document records a proposed action scope, not accepted architecture or a
native result. The [completed qualification packet](provider-render-qualification-packet-2026-10-17.md)
owns source preparation and the operator checklist. The accepted Phase 4
publish flow remains authoritative for selection before rendering and the
full-resolution 8-bit sRGB PNG requirement.

## Candidate to approve

| Item | Exact candidate |
| --- | --- |
| Fixture | `FGA-ProviderRender-Qualification.lrplugin`, `0.0.1.2` |
| Stage | Final immutable `provider-render-20261017-v4` recorded privately in `batch0123-packet-evidence.md`; v1/v2/v3 are superseded |
| Artifact SHA2-256 | `cd4281b5a95c34ac127ec05c89ccf0dffe4c3a3112e9128891d304c2a5160e1a` |
| Manifest bytes SHA2-256 | `014b6ff7251981c3dad515ef7737824d3f87c67b76d13b692cccc0b81063fc4a` |
| Closure | Exactly 24 allowlisted Lua files: nine fixture, seven actual publisher, eight actual client dependencies |
| Host | Lightroom Classic 15.6, major 15 only; exact observed build must be retained with action-time approval |
| Declared SDK | 15.3; not an observed runtime SDK version |
| Catalog | One new dedicated `FGA-ProviderRender-Disposable.lrcat`; exact proposed absolute path retained in private `0135-action-scope.md` |
| Scratch | Fixed catalog-sibling directory `FGA-provider-render-qualification-v1`; refuse if it already exists |
| Assets | 15 original generated 8 x 8 RGB TIFFs, no real photo/catalog data |
| Service/Album | One manually created isolated qualification service; one generated ordinary test Album |
| Case-work window | One positive action-time interval of at most 1800 seconds; no appointment or continuing authorization |

The private scope fixes a new workspace; no catalog, scratch directory, consent
or assets have been created for #0135. The existing stage is an offline reviewed
source artifact. Retain both independent pins; its self-consistent manifest is
not an independent authorization. Any source, stage, plan, template or digest
change requires a fresh candidate and decision.

## Finite proposed actions

1. Recheck both artifact pins, source equality, independent review and observed
   host version/build. Through the supported native-control route, first create,
   open and verify the exact new empty disposable catalog. Only while that
   catalog is active, install/enable/load the isolated qualification menu/provider/
   private metadata declaration, then create its one empty qualification service.
   Before the run, require zero photos, no child collection sets, no ordinary
   Albums and no fixture-private records; an empty host default collection may
   exist. A renamed real catalog is not an eligible fixture.
2. Explicitly invoke the fixture's Library menu, choose the separately retained
   owner consent JSON through its Open Panel, then confirm its finite run
   dialog. No automatic run callback exists; ordinary Publish refuses.
3. Generate/import the 15 TIFFs, create the one Album and write only generated
   selection, correlation and attempt fields in this dedicated catalog. Render
   through actual SDK export sessions and actual shared selection/frozen-context/
   rendition/preflight code. The `selection_none` case uses JPEG as a bounded
   diagnostic branch; it does not authorize a production PNG fallback.
4. Run exactly the 14 ordered cases below, including the listed fault injections
   and a **200000001-byte** oversized scratch-file mutation. Synthetic transport
   consumes leased bytes only in memory. No credential reads, OAuth, Flickr,
   hosted/provider network operations, uploads, production registration or
   production activation belong to this scope.
5. Exercise the guarded cleanup and preservation behavior below. Imported photo
   rows and the qualification service persist until later manual disposal of
   the entire dedicated catalog. Retain sanitized native receipts privately.

| Ordered cases | Purpose and limit |
| --- | --- |
| `selection_absent`, `selection_none`, `selection_groups` | Distinguish absent, explicit zero groups and explicit synthetic group choice |
| `selection_edit_after_freeze`, `photo_failure_isolation`, `target_rejected` | Inject a later choice edit, invalid sibling photo state and rejected target |
| `catalog_changed`, `activation_changed`, `cancelled` | Inject boundary invalidation/cancellation; not evidence that the host independently generated these events |
| `render_failed`, `missing_file`, `oversized_file`, `file_changed` | Inject explicit render/file faults only after their applicable boundary is reached |
| `cleanup_revocation` | Check fixture/byte-lease revocation and terminal cleanup accounting |

Every case needs a terminal result. Requested faults and actually applied faults
are separate receipts; an ordinary native render failure cannot pass an injected
failure case. Missing, unknown or not-run results remain inconclusive.

## Cleanup and stop authority

Consent expiry, changed/removed consent bytes, catalog change or cancellation
stops further case work and byte consumption. The 30-minute bound controls new
case work; it cannot promise that already started host rendering stops then.

The decision must separately authorize waits after expiry/revocation solely to
observe termination of **already started** rendering, without consuming or
decoding output bytes. Those waits may exceed 30 minutes. The dispatcher waits
at most once for each observed raw rendition and requires completed enumeration,
exact rendition counts and terminal results for all started work.

Unknown/unseen work, failed drain evidence, nonboolean wait results or incomplete
enumeration preserve **all catalog state and files**, report cleanup incomplete
and force overall false. This is not forced cancellation or a hard-stop
guarantee, and does not qualify #0037.

Only proven terminal rendering permits guarded removal of captured fixture
private fields, the generated Album and known generated files/directories.
Unexpected output is preserved; no recursive cleanup is authorized. Preserve
the catalog/workspace while rendering completion is unresolved. After proven
termination, close Lightroom, remove the qualification plug-in and manually
dispose of the entire dedicated disposable catalog/workspace, with a private
disposal receipt. Do not claim automated cleanup removed photo rows/service.

Preserve Terry's intentional Escape stop. Do not reset, relaunch, disable Escape
or use an alternative automation route to bypass it. A native UI stop ends
computer use in that turn; it does not prove background render termination or
authorize deletion. Preserve unresolved artifacts for later assessment.

## Exact owner decision still needed

After independent review, present Terry with this exact v4 candidate, the private
absolute catalog/scratch paths, the observed host build, all finite actions and
the separate after-expiry wait/cleanup behavior. Record Terry's actual answer;
this document is not that answer. Decline or deferral leaves the fixture dormant
and does not begin #0126.

If approved, retain external consent with exactly `schemaVersion: 1`,
`owner: "Terry"`, both exact pins above, the approved absolute `catalogPath`,
Unix-second `grantedAt`/`expiresAt` and these four true flags:

- `allowQualificationProvider`
- `allowSyntheticCatalogWrites`
- `allow200000001ByteScratch`
- `allowCleanup`

Use a positive interval of at most 1800 seconds that contains the actual action
time. Preserve the immutable stage's null/false consent template unchanged;
never backdate, extend, fabricate or infer approval from prior experiments.
The schema has no host-build field: retain the exact observed build with the
owner decision and compare it with the run's sanitized `actualHost` receipt.

The installed `computer-use/SKILL.md` requires reading
`../../docs/confirmations.md` before native-action decisions. Its section 2 says
"Blocking confirmation required immediately before the action" and includes
software installation via Windows UI and data deletion via an app interface.
Consequently, obtain the applicable immediate confirmation before fixture
installation/load/run through Windows UI; a later manual UI deletion/disposal
needs its own immediate confirmation even if the broad plan was approved.
The fixture's source-internal cleanup is separately bounded by the exact owner
consent and terminal-render guards described above. The native Run dialog and
a syntactically valid JSON file do not substitute for Terry's actual permission.

## Evidence and handoff

Completed #0123 independent review passed final v4 source preparation, all
24-file byte comparisons and both independently retained pins. Its documented
verification includes 40 focused fixture/preparation/asset tests, 53 existing
provider/context/choice/rendition tests and all 24 Lua syntax checks. These are
source evidence, not new #0135 test execution or native measurements.

Private evidence: `batch0123-packet-evidence.md`,
`batch0123-independent-review.md`, and this batch's `0135-action-scope.md` plus
the artifact and case assessments. No native load/run, credentials, external
operation or consent occurred during this decision preparation.

PNG8 output, full dimensions, sRGB/profile correctness, native scheduling,
persistence, cancellation and host cleanup remain unmeasured. ICC presence is
not sRGB verification (`profileVerified` remains false). The SDK documentation
gap for PNG bit-depth is explicit in the completed packet; no format, sizing,
quality or second-render fallback is approved.

This decision preparation passes no #0126, #0037, provider-restoration or final
#0026 gate. Existing #0044 NO-GO, unqualified #0037 and negative #0043 restoration
evidence remain in force. After reviewed preparation, #0135's next meaningful
step is Terry's action-time judgment; dependent #0126/#0026 stay Ready for Work
with their prerequisites intact until separately eligible.
