# FGA-LrC15 development handoff - 2026-10-15

## End-of-day sign-off: 2026-10-15

Terry ended the day's work after accepting selection preview **0.0.1.12** and
moving **0027 to Completed** himself. The board state was verified through
localswim-cli. This checkpoint supersedes pending interaction-review statements
in the earlier handoffs below; retain those as historical component evidence.

The accepted fixture interaction includes aligned two-list selection, names before
NSIDs, live filtering with an explicit FILTERED count and Clear filter, selected
count beneath the right list, no radio buttons, valid empty unpublished choices,
contextual singular/plural action titles, and native multi-select batch Add/Remove.
Owner screenshots establish noncontiguous highlights, batch Add, a reported
right-list Shift range and batch Remove. Do not ask Terry to repeat those checks.
The [design](../design/dual-list-group-selection-preview.md) and
[native evidence](../evidence/lrc15-selection-preview-host-2026-10-15.md) hold the
details and bounded verification claims. Latest functional preview commit:
`a8ad1f7`; subsequent commits record observations and owner approval.

The 60-selected-additions limit remains owner-accepted. Flickr's Pro limit has
exceptions for groups allowing unlimited posting; do not describe 60 as an
absolute provider membership ceiling. The preview is still fixture-only, with
no real publication, membership changes, submission, or catalog persistence.

### Where to resume

**Terry's final priority for the next session, Friday 2026-10-16: address the
Needs Terry card 0025 first.** Review the controlled-addition runbook together
and ask him to select the exact existing public Flickr photo and destination
group (photopage/group-page links, with exact IDs resolved and confirmed).
This resolves the immediate owner-selection handoff only. Do not promise the
entire trial can close before 0024 and exact-artifact qualification are complete.
Live write activation remains a separate approval after the evidence packet
and bounded stop/recovery procedure are reviewable. Do not ask for that approval
prematurely. Keep real trial identifiers in the private worksheet/board rather
than these public notes. No overnight run or scheduled reminder was created.

After that owner-input step, the implementation order is:

1. Start with **0023: Browse and verify existing public Flickr photos**, currently
   Ready for Work, bot-owned. Its recorded prerequisite cards 0022, 0031 and 0032
   are Completed. Review the
   [hosted-thumbnail handoff](hosted-thumbnail-handoff-2026-10-15.md), current source
   and remaining hosted/native qualification before activating the disabled path.
2. Then work **0024: Connect Lightroom group selection to submission and status**,
   Ready for Work, bot-owned. Its UI dependency 0027 and outbox dependency 0029
   are Completed; 0023 remains its unfinished dependency. Integrate the accepted
   interaction rather than reopening its design or repeating fixture sign-off.
3. **0025** remains the controlled production-addition gate: finish qualification,
   obtain the exact owner-selected photo/group pair and explicit live activation
   consent. **0026**, new-photo publishing, remains Backlog and depends on 0024.

No new implementation task was started at sign-off. No new production deployment,
live Flickr write, or automation was authorized by this stop-for-the-day request.
At the next work session, follow normal board health/priority and current-source
checks before resuming; board state may have changed since this checkpoint.

## Resume checkpoint: 2026-10-16

The implementation board was reused with synchronized autopush and opened;
the board-specific actor-filtered JSON monitor was started and confirmed running
for this chat. The inception priority barrier passed. No production work ran.

0025 remains Needs Terry: the exact existing public photo and destination group
links were requested first, as agreed at sign-off. The runbook's one-pair
staging, queue census, explicit activation and stop/reconciliation sequence was
reviewed. The owner-selection step cannot complete without the pair; the full
trial additionally depends on 0023/0024 integration and exact-artifact
qualification. Do not interpret selecting a pair as live activation approval.

### Owner-input resolution: 2026-10-16

Terry supplied the exact photo/group pair. Guest photo accessibility was verified
without cookies and the group NSID was resolved from its public feed link.
The selection and private evidence location are recorded on implementation card
0025; the [trial runbook](first-controlled-group-addition.md) records the bounded
verification and remaining gates. This supersedes the pending-pair statement
above. The owner-input step is complete; 0025 returns to bot-owned Ready for Work
with its 0024 dependency intact. Resume implementation with 0023, then 0024.
No real Flickr submission or live activation has been performed or authorized.

## Earlier development handoff (historical)

Latest update: [approved timing decision and disabled hosted-thumbnail candidate](hosted-thumbnail-handoff-2026-10-15.md). The original clock/transport owner decisions below have been resolved; exact hosted/native qualification and interaction review remain.

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
