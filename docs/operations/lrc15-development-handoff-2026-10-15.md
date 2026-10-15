# FGA-LrC15 development handoff - 2026-10-15

The subsequent [parallel implementation and native-host handoff](lrc15-parallel-handoff-2026-10-15.md) records release 0.2.0 build3, successful actual-host group browsing, new fixture receipts and the disabled upload-authorization candidate. Use that update for current acceptance state; the source-only batch evidence below remains historical.

## Host and SDK

Terry's About Lightroom screenshot identifies Lightroom Classic **15.6 Release**,
Camera Raw **18.7**, build `202609251514-f839cde9`. His Adobe Developer Console
screenshot confirms that **SDK 15.3 (April 2026)** remains the newest offered SDK.
The major-specific client identity and secure-store namespace stay FGA-LrC15.
Earlier 15.5.1 host results are historical evidence.

## Artifacts and review gates

| Work | Artifact | Next acceptance |
| --- | --- | --- |
| Group browser | `clients/lightroom/FGA-LrC15.lrplugin`, version 0.2.0 build 1 | Reload in 15.6 and exercise authenticated browsing, reload and closure |
| Photo/group selection preview | `clients/lightroom/prototypes/FGA-LrC15-SelectionPreview.lrplugin` | Review the fixture interaction in 15.6 before selection/submission implementation |
| Existing-photo discovery and memberships | New handlers, migration 0014 and disabled native client | Resolve hosted elapsed-time and native thumbnail boundaries before activation |
| Submission readiness | [Readiness assessment](../planning/group-selection-submission-readiness.md) | Selection-preview review and durable local outbox proof |
| Local outbox candidate | `probes/FGA-Outbox-Probe.lrplugin` | Use a new empty `FGA-Outbox-Probe.lrcat`; qualify rollback/restart behavior |
| Rendition preflight | `clients/lightroom/publisher`, unregistered | Review the isolated policy/SDK adapter before provider integration |
| Controlled first addition | [Runbook](first-controlled-group-addition.md), fixed pause adapter and isolated scheduler tests | Exact-artifact qualification, owner-selected pair and explicit write activation |

No deployment, production migration, image upload or group submission was performed
by this batch. The existing-photo flag defaults to `0` and its native action is
unregistered and qualification-gated. Local runtime tests use synthetic provider
responses; they do not supply a live Flickr compatibility or hosted clock pass.

## Group browser host check

Reload the existing release bundle in Plug-in Manager. Secure-store keys are
unchanged, so an existing Plugin Code does not need replacing. Open **Library > Plug-in Extras >
FlickrGroupAddr: Browse writable groups...**. Confirm complete names/IDs, snapshot
status and observation time, explicit reload, responsiveness and closure during
loading. The September observation of 373 groups is historical, not an expected
fixed current count. Closing discards later results and follow-up requests; an
already-running native HTTP request can take up to its 30-second timeout.

The standalone fixture preview has a separate toolkit identifier and never reads
credentials, contacts a service, changes the catalog or submits a group addition.
Its [storyboard and checklist](../design/photo-group-selection-preview.md) cover
unpublished, bound and existing-public-photo paths, unavailable projections,
protected rows and 0/1/60/61 choices among 376 synthetic groups.

## Existing-photo release boundaries

The new `GET /api/v001/existing-public-photos` and binding-scoped membership GET
require read enablement plus `FGA_EXISTING_PHOTOS_ENABLED=1`. With that gate
explicitly enabled, non-destructive binding verification can run while submission
intake stays closed. Group-batch admission still requires its own intake flag.
Migration 0014 stores one replaceable advisory membership observation and reduced
paging rows; failed initial reads invalidate old paging without substituting an
old snapshot as current. Each page and publication revalidates current authority.

The accepted membership contract requires 15 seconds of monotonic elapsed time.
Observed clock checks, abort timers and finite byte/entry limits are implemented,
but the prior Workers clock evidence does not establish a hard elapsed-time
guarantee. ADR 0059 applies only to writable-group refresh. A conforming proof or
explicit scoped architecture decision is still needed for membership activation.

The documented SDK GET interface offers phase timeouts and returned bytes, but
does not document redirect suppression, final-URL inspection or a streaming byte
cap. The production thumbnail boundary requires those behaviors. After-fetch
size/signature checks bound cache publication, not the network transfer. Qualify
that boundary or accept an explicitly reviewed alternative before enabling the
existing-photo action; do not silently add an external downloader.

## Independent publisher work

The [publisher workplan](../planning/lrc15-new-photo-publisher-workplan.md) splits
the broad milestone into bounded tasks. The completed-rendition preflight module
has no provider registration or network authority. It checks configured size
limits, exact-limit acceptance, missing/unreadable/empty files and per-photo
failure isolation. Its documented native readability check temporarily loads an
approved-size file and cannot lock it against later changes.

The separate [outbox investigation](../research/lrc15-outbox-persistence-boundary.md)
proposes catalog-wide private JSON storage with a guarded disposable-catalog
probe. Editable per-photo group choices are a distinct record. Mocked tests and
normal readback do not prove abrupt-stop, restored-catalog or power-loss behavior.

## Verification

The [local evidence record](../evidence/lrc15-parallel-local-2026-10-15.json)
records 207 Python/Lua tests, 150 runtime tests, static checks, generated API
verification and Adobe compilation of 21 Lua files. The
[disposable hosted pause proof](../evidence/controlled-trial-pause-hosted-2026-10-15.json)
also passed all nine assertions and confirmed cleanup in
[CI run 38752805316](https://github.com/FlickrGroupAddr/api-cloudflare/actions/runs/38752805316).
These are component results, not complete hosted release qualification. Required host interaction remains
pending; the attempted desktop check was cancelled before Lightroom input ran.
The first controlled production addition retains its separate owner consent gate.
