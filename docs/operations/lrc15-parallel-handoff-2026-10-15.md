# Lightroom 15.6 implementation and host-validation handoff

Date: 2026-10-15. Status: development evidence and bounded owner handoff;
not production deployment or complete publishing qualification.

## Writable-group browser

The FGA-LrC15 release is **0.2.0 build 3**. Native validation used Lightroom
Classic 15.6, Camera Raw 18.7, build `202609251514-f839cde9`, against SDK15.3.
The installed release retained its existing secure-store namespace and credential.

The parent agent opened the registered Library command and observed all373
writable groups. The old snapshot was honestly labeled stale/refreshing;
explicit reload later displayed revision2, observed UTC
`2026-10-15T15:07:55.007Z`. Native local name search filtered the complete list,
clearing search restored it, and a literal punctuation query produced0matches
without misreporting a complete empty service snapshot. Final build3 exact-ID
search returned one group out of373. Highlighting showed its exact ID plainly;
the full-name detail dialog opened and closed correctly. Reload and normal
closure returned control to the host. No submission controls, group writes,
photo operations or credential entry were involved.

Build2 testing found a real SDK layout issue: a bound static label initially
measured from an empty string did not expose its later ID. Build3 reserves
space for the ID and uses a populated-at-creation detail modal for the full raw
name. The source does not invent an undocumented read-only edit-field property.
Long/duplicate-name synthetic behavior is covered by fixtures; the real account
run does not claim a1024-character native stress pass. The cooperative close
guard and suspended coroutine cancellation are exercised by Lua5.1 tests;
the native run does not claim an instrumented close during a confirmed slow GET.

The client also now rejects strict-JSON grammar violations before the existing
dkjson decoder: comments, missing/trailing commas, non-JSON whitespace and
leading-zero numbers previously could appear successful. Duplicate escaped
keys, depth, body/page limits and exact continuation identities remain guarded.
Native tests and mocks are distinct evidence sources.

## Selection preview

The separate fixture-only preview is **0.0.1 build2**, at
`clients/lightroom/prototypes/FGA-LrC15-SelectionPreview.lrplugin`. Its376groups
now include two identical display names with different IDs and one long label,
closing a documented fixture-coverage gap. Seven new adversarial Lua5.1
interaction tests cover hidden selections across search/reopen,0/1/60/61,
unavailable projection changes, protected memberships and cancellation.

The [host checklist](../design/photo-group-selection-host-checklist.md) owns
the concrete native scenarios and separates subjective owner decisions. This
preview has not been installed or executed in the host during this batch.
Next owner gate: approve loading that separate fixture plugin, then run the
native checklist and review search interaction, scanability and presentation.
It uses no production credentials, network, catalog writes or submission.
Production selection/submission implementation remains gated on that review.

## Catalog outbox proof

The isolated probe is **0.0.2 build4**, at `probes/FGA-Outbox-Probe.lrplugin`.
It refuses every catalog except the exact fixture leaf
`FGA-Outbox-Probe.lrcat`; create a new empty disposable catalog, never rename
a real catalog to satisfy that guard. No fixture catalog was created or mutated
by this batch and no probe host result is claimed.

The probe now emits bounded closed JSON receipts beneath `C:\Temp`, using
`FGA-Outbox-Probe-<runId>-{same_session,rollback,restart,failure}.json`.
See the probe README for exact monitoring semantics. Receipts retain the current
run, probe version, documented host version/build, UTC write time, stage result
and honest qualification flags. Intermediate same-session success is not
whole-command success. Temporary files are never terminal receipts. Eleven
Lua5.1 tests exercise guards, rollback errors, stale runs, receipt failure,
version matching and fractional clock seconds.

Next owner gate: approve loading the isolated probe and using the new empty
catalog. Observe same-session and private-gate rollback, then independently
observe normal restart before accepting its matching restart receipt. Process
crash, restore/copy, power loss and production persistence remain unqualified.
See the [independent review](../research/lrc15-outbox-host-proof-review.md).
An older or absent restored local record can conceal a later external upload;
production recovery cannot treat absence as proof of no dispatch. This requires
an explicit restore/copy recovery policy before production upload integration.

The installed computer-use confirmation policy requires action-time confirmation
for software installation through Windows UI, even after general task approval.
This is why the two fixture installation steps are owner handoffs. It does not
block read-only validation of the already-installed release.

## Hosted upload authorization

The independently scoped implementation is metadata-only
`POST /api/v001/upload-authorizations`. The backend never receives image bytes
or calls Flickr for this operation. The executable registry owns its closed
schemas. Existing installation bearer authentication and JSON framing precede
issuance; the independent feature flag defaults to0. Both applicable write gates
must be enabled, and installation, linked owner, credential generation and gate
revisions are fenced again during the issuance transaction.

Migration0015 retains only authorization ID, installation, user, database issue
time and nullable photo association. Issuance plus sanitized success audit is
atomic. The signed OAuth header and photo metadata remain in memory and in the
no-store response, never SQL or logs. The mature existing OAuth dependency signs
the exact allowlisted metadata for the fixed Flickr upload URL using a runtime
CSPRNG nonce. No Flickr-enforced single use or artificial expiry is promised.

Independent tests verify the HMAC separately from the signing library, strict
input, auth/media/framing, paused gates, twelve authority races at each of two
boundaries, five transaction failure points, retention and secrecy. The
[review record](../research/2026-10-15-upload-authorization-review.md) separates
local synthetic evidence from hosted qualification. No deployment, production
migration, real envelope issuance, live upload or write activation occurred.
Next review gate: source/schema/migration and test review, followed by separate
exact-artifact hosted qualification. Upload-result photo proof, local outbox,
album integration, publisher wiring and controlled uploads remain separate.

## Evidence and remaining state

See [the machine-readable receipt](../evidence/lrc15-parallel-handoff-2026-10-15.json)
for integrated checks. The release browser and upload-authorization candidate
can be reviewed; fixture preview and outbox native work retain the precise owner
steps above. The broad publisher milestone stays split rather than presented
as complete. All host dialogs were closed; Lightroom was left open, with the
full-screen presentation restored through its native screen-mode cycle.
