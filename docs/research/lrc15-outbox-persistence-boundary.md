# Lightroom Classic 15 local outbox persistence boundary

Date: 2026-10-15. Status: decision-ready research recommendation and isolated
probe source. Not accepted architecture, an implemented production outbox, or
host/crash qualification. The native selection/submission UI review prerequisite
remains unchanged.

## Recommendation

Evaluate **one catalog-wide plug-in property containing a bounded, versioned JSON
outbox**, through documented `catalog:getPropertyForPlugin()` and
`catalog:setPropertyForPlugin()`. Use the synchronous private catalog write gate
if its behavior passes the isolated host checks below. This is a distinct field
from ADR0045's per-photo editable `groupAdditionSelections` metadata. The catalog
already owns persistent local workflow identity; a separate property can retain
an existing-public-photo handoff even when it has no corresponding `LrPhoto`.

This candidate is simpler than a custom file journal: the Lightroom Classic
host owns storage, write serialization and catalog backup. It adds no native
helper, cross-process locking, filename allocation, rename protocol or presumed
disk-flush facility. Do not treat either catalog metadata or an app-data file
as hosted authority; safe proof and service natural keys remain authoritative.

Choose a single bounded record collection first; establish a documented pending
record/byte bound and an explicit refusal when full. Never evict unresolved work
to make space. Retain non-secret binding/status correlation while allowing
completed recovery details to be compacted only under a separate reviewed
retention rule. Splitting into separate property keys requires an enumerable
index and atomic-index proof; do not add that complexity without measured need.

## Accepted requirement versus an invented stronger requirement

Architecture `docs/plugin-service-contract.md:943` requires a recovery record
before upload authorization; `:950` requires the returned photo ID be persisted
before `recordPublishedPhotoId`; `:959` requires the handoff record before hosted
handoff and completion only after all applicable hosted acknowledgments.
`:970`–`:985` forbid replay after an invoked ambiguous upload.
`docs/zero-state-publish-flow.md:1201` and
`docs/plugin-service-contract.md:1740` explicitly leave the precise storage
mechanism open. ADR0045 `:155`–`:175` separates immutable recovery from editable
metadata and retains the selection until the copy is durable.

These sources require persistent recovery and truthful failure handling. They
do not define a plug-in-specific `fsync`, forced directory flush, arbitrary
power-cut guarantee, or a second local transactional database. Do not impose
those as silent new gates. Conversely, SDK callbacks executing and an immediate
readback are not empirical proof of process-crash or power-loss persistence.
Qualify normal restart and abrupt-host-stop behavior independently, document
what was observed, and identify unproven OS/storage failures explicitly.

Accepted ADR0051's private runtime trust exception concerns hosted D1/owning
Durable Object code and guarded writes. It does not independently certify a
Lightroom catalog property or authorize clearing recovery/suppression data. Its
native-first, ordinary-runtime trust direction supports evaluating conventional
host storage before inventing another service; the exact local contract still
needs to be recorded after evidence.

## Primary SDK evidence checked locally

Source tree: architecture repository's Git-ignored
`vendor/LrC SDK/15.3/API Reference/modules/`. Adobe's licensed API text was
inspected locally; no SDK source or documentation is redistributed here.

| Source location | Documented capability | Limit of the evidence |
| --- | --- | --- |
| `LrCatalog.html:1367` | `getPropertyForPlugin` retrieves catalog-wide plug-in data. | No explicit flush/restart timing guarantee. |
| `LrCatalog.html:1551` | `setPropertyForPlugin` sets catalog-wide scalar metadata; no declaration is required; a write gate is required. A JSON string fits the documented value type. | Exact supported private-gate behavior must be exercised on the target host. |
| `LrCatalog.html:1721` and `:1739` | Private write gate applies to plug-in metadata, avoids undo, serializes access; synchronous return distinguishes executed/aborted. | It does not expressly repeat every rollback/disk-flush promise of the ordinary gate. Never treat queued as committed. |
| `LrCatalog.html:1803` | Ordinary write gate documents rollback on callback error and application of changes after successful callback completion. | Ordinary undo behavior would be an outbox correctness concern; do not silently substitute this gate if private-gate qualification fails. |
| `LrPrefs.html:316`, `:341` | Preferences support scalar/table data, with explicit nested-assignment persistence caveats. | No explicit immediate persistent commit boundary; unsuitable as the selected recovery authority on this evidence. |
| `LrFileUtils.html:806` | `move` refuses an existing destination; destination directory must exist. | No documented atomic replace-over-existing or forced flush. Delete-then-move would create an avoidable recovery hole. |
| `LrFileUtils.html:890` | `readFile` is preferred over Lua io for non-ASCII paths. | Successful file reread does not establish power-loss persistence. |

On 2026-10-15 Terry rechecked the Adobe Developer Console and supplied screenshot
confirmation that the newest available SDK remains **15.3 (April 2026)**. This
owner-confirmed current download evidence supports using the local 15.3 API
reference for the installed 15.6 runtime; these version numbers describe
different artifacts. The public [Adobe SDK landing page](https://developer.adobe.com/lightroom-classic)
also confirms Lua, metadata and publish extension capabilities. The owner
reported installed acceptance host is Lightroom Classic 15.6 Release, Camera Raw
18.7, build `202609251514-f839cde9`. Prior host results do not qualify this host.

## Smallest proposed lifecycle

Under one synchronous private gate, read and strictly validate the entire
outbox, check expected local record revision, copy exact immutable selected
IDs/correlation, increment revision, and replace the whole JSON string. Do no
network, render, UI, yield or callback launch inside the gate. Treat aborted,
queued, thrown, malformed or mismatched readback as unconfirmed and perform no
dependent external operation. A simple gate plus compare-and-set revision
prevents older callbacks from overwriting newer local state; do not infer
network exactly-once behavior from local serialization.

After successful gate completion, reread and compare the exact persisted
representation before proceeding. This readback detects immediate mismatch,
not a disk-flush guarantee. Each later step updates the same record before its
next dependent operation. For upload dispatch, persist an upload-may-have-been-
invoked phase before invoking `postMultipart`; an ambiguous phase after restart
never permits automatic upload replay. Store no signed envelope/Authorization.
For a group batch, persist original binding/revision and exact group set; record
validated intent IDs only after full response validation. Ambiguous batch
delivery permits only the accepted idempotent backend reconciliation, never
Flickr replay. Consume editable selection only when the matching selection
revision still exists and durable hosted handoff was validated.

The candidate store is catalog scoped. Switching catalogs must select that
catalog's recovery only. Catalog copying/restoring can resurrect old records;
the safe recovery policy must therefore treat historical upload-dispatch phases
as uncertain and use hosted natural-key/group status reconciliation. Catalog
backup is useful preservation, not permission to repeat an external write.
Removing the plug-in or deleting the catalog cannot be represented as a durable
hosted cancellation. Cross-device catalog copies require explicit local-state
scope review; no new cross-device lock is proposed here. None of these proposed
recovery rules is a verified restore/no-replay guarantee: restore and crash
qualification remain pending, and lost local state must never be interpreted as
proof that an external upload was not invoked.

## Isolated host probe prepared

`probes/FGA-Outbox-Probe.lrplugin/` is an original standalone, manually invoked
fixture probe using only the named SDK APIs. It registers two Library menu
commands, makes no network request, accesses no photo, reads no credential and
writes no file itself. Both commands refuse unless the active catalog's leaf
name is exactly `FGA-Outbox-Probe.lrcat`. This guard is a mistake-prevention
check, not a security sandbox: use a newly created empty fixture catalog, never
rename a real catalog to pass it.

1. Create that empty catalog on the supported Windows installation and load the
   standalone probe. Record host/build, SDK reference version and fixture path
   privately. Keep production and ordinary photo catalogs closed.
2. Run **Outbox fixture: write and test rollback**. It writes only its private
   synthetic catalog property, requires the synchronous result to be executed,
   checks exact readback, then deliberately throws after a replacement and
   checks whether the original value survives. Failure stops the probe.
3. Close the host normally, reopen the same fixture catalog and invoke
   **Outbox fixture: verify after restart**. Record the exact property-match
   result. The command truthfully cannot establish by itself that a restart
   occurred; record the lifecycle independently.
4. In a separate fixture run, repeat the write, then stop the host abruptly
   through the ordinary OS task control after the success message, restart and
   verify. Do not terminate any host with a real catalog open. This is a bounded
   process-crash observation, not power-cut evidence. Also exercise callback
   abort/timeout contention before choosing the production gate options.
5. Retain the fixture/evidence until review. Removing this one isolated probe
   does not erase any production property. No automated installation, execution,
   host termination or catalog deletion is included in this pass.

The probe has been parsed in Lua 5.1 locally, but **has not run inside the host**.
Same-session and restart/crash outcomes are pending. A fake catalog test cannot
substitute for these SDK/host observations.

## Decision and remaining evidence

Recommend accepting the catalog-wide JSON candidate for a bounded host proof;
do not require an external file journal first. If private writes and rollback
work and ordinary/abrupt restart preserve the value, record the exact supported
recovery contract and its ordinary host-storage assumptions. If an owner needs
a stronger power-loss claim, first identify the actual requirement and available
documented SDK evidence; do not claim that Lua close/flush or file rename meets
it. If catalog storage fails qualification, return with that concrete failure
before selecting an external helper or native database.

Additional production tests remain necessary for compare-and-set concurrent
callbacks, malformed/oversize/unknown-version records, rollback/timeout, catalog
switch/restore, storage full/unavailable, matching editable-selection consumption,
and every crash point before/after upload or group handoff. They are scoped
requirements, not outcomes of this source-only probe.

## Raw 202 integration boundary refined

`GroupSubmissionClient.lua:53` returns the injected POST result directly. HTTP
202 does not establish complete local confirmation. A future response validator
must reject: wrong schema/binding/photo correlation; missing/extra/duplicate
requested group; absent or invalid intent ID/state/created; missing, unknown or
contradictory permanent block. A contradictory or partial response retains the
immutable unresolved outbox and must not clear the editable choice. It must not
turn unknown values into eligible checkboxes or default created:true.

The schema-2 batch response contains only intent ID, group ID, state, created
and permanent block per item; it does not carry full status stateRevision or
queue/outcome details (`src/intake_api.ts:40`). Validate that exact bounded
projection, then obtain full read-only status for progress. Do not fabricate
fields or require the batch response to be the full status schema. A fully
existing natural-key result is a confirmed no-op; a mixed existing/new result
is still one durable batch, never a reason to re-post each group separately.
