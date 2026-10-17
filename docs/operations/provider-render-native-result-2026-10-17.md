# Native provider/render fixture result

Date: 2026-10-17. The exact approved fixture **0.0.1.2** completed its finite
synthetic run on Lightroom Classic **15.6**, build
`202609251514-f839cde9`. All **14 ordered fixture cases passed**, with all
**13 started render sessions** observed terminal. Independent review found no
blocking defect in this bounded run or its stated interpretation.

This is native measurement of the reviewed disposable-catalog fixture. It is
not production publisher qualification, a real upload, an authentication-path
measurement or permission to activate a feature.

## Identity and provenance

- Source artifact SHA2-256:
  `cd4281b5a95c34ac127ec05c89ccf0dffe4c3a3112e9128891d304c2a5160e1a`.
- Manifest bytes SHA2-256:
  `014b6ff7251981c3dad515ef7737824d3f87c67b76d13b692cccc0b81063fc4a`.
- Exactly 24 staged Lua files matched the pinned closure and source identity.
- Declared SDK: **15.3**. This is fixture provenance, not an observed runtime SDK
  version.
- Exact native receipt SHA2-256:
  `96914693fdbe66fde601e7ca24133988ffad85fc1ff084bfd4dc9146d8ccc129`.
- [Sanitized native receipt](../evidence/provider-render-native-2026-10-17.json).

The first consent window expired before any case was started. The stale Run
dialog was cancelled with zero photos still observed. Terry then explicitly
confirmed running now; that actual confirmation established a new positive
1800-second interval for the same artifact, catalog and action scope. The old
consent and both decisions were retained privately. One actual Run input was
dispatched under the renewed scope; no render or case was replayed.

## Observations

| Area | Native fixture observation |
| --- | --- |
| Selection | Absent, explicit zero and group choices passed; the edit-after-freeze and invalid-sibling cases reached their intended boundaries. |
| Preparation | The fixture returned from preparation and read the prepared attempt record back before its first rendition iteration. This observes its dispatcher ordering, not SDK-internal scheduling. |
| Target/context checks | The injected default-target, stale catalog, stale activation and cancellation cases returned the expected closed outcomes. These were controlled injections, not independent host-generated events. |
| Rendered bytes | Ten outputs were inspected: nine PNG and one diagnostic JPEG. Each measured output was 8-bit and 8 x 8, matching the generated input dimensions. This does not generalize sizing behavior to larger photographs. |
| File/error handling | Render failure, missing file, 200000001-byte oversized file and changed-file injections passed their expected outcomes. |
| Revocation | Retained byte leases refused after finish; the cleanup case refused reusing the closed fixture handle. |
| Termination | 13 observed renditions and 13 terminal renditions; ten adapter render waits plus three stale/cancel drains. |

The JPEG branch is an explicitly approved diagnostic case. It does not select a
production JPEG fallback. Synthetic handoff means in-memory consumption; it
does not mean a Flickr upload or group submission.

## Cleanup and retained limitations

The terminal native receipt reports scope revocation, private records cleared,
generated Album removed and known owned files deleted. A separate filesystem
check found only `receipts.json` in the scratch directory. A byte-identical copy
was retained outside the disposable catalog before proposing disposal.

At native completion, the **15 imported synthetic photo rows and test publish
service remained** pending separate whole-catalog disposal. Automatic cleanup
did not remove them. Terry subsequently gave the applicable immediate
confirmation; the verified disposal is recorded below.

These explicit receipt limits remain in force:

- `profileVerified=false`: an ICC marker was present, but the compressed profile
  was not validated as the expected sRGB profile. No retained rendered output
  remains from which to retroactively establish profile identity.
- `nativeSchedulingProven=false`: the dispatcher used actual SDK sessions and
  renditions, but was not an actual SDK-created export callback context.
- `productionQualified=false`: no production provider, credentials, real photo
  or hosted endpoint was used. Zero network calls are a source-isolation claim
  of this fixture, not an independent packet trace or production-auth test.
- Selection/attempt readback occurred in this host process. The run did not
  close and reopen the catalog to establish restart persistence.
- The target-rejection test injected a default flag; it did not qualify the
  production provider's complete Album/default-collection UX.

The named finite run and assessment can be reviewed on #0126. The remaining
profile, actual callback/scheduling and release evidence must be kept explicit
before later production or live-publication gates. Completing this run does not
amend the accepted format contract or clear unrelated qualification gates.

Supplemental source checks are tracked by #0158 for integration into the later
#0124 packet and #0128 run; #0137 retains the exact action-time decision.
The downstream #0128/#0129/#0131 relationships preserve these unpassed gates.

## Subsequent approved disposal

Terry explicitly approved fixture unregistration, normal host closure and
removal of the exact disposable folder. Lightroom had already been closed by
Terry, so the operator reopened it once through the supported launcher solely
for this cleanup; no fixture case was invoked again.

- The exact qualification fixture path/version 0.0.1.2 was observed before one
  Remove action. Its entry was absent afterward; the disposable service showed
  missing plug-in. The other plug-ins remained registered.
- Lightroom was closed normally. Both the returned window inventory and a
  process check confirmed exit; no force termination was used.
- Before deletion, the exact resolved target was checked against its approved
  workspace boundary, linked ancestors/descendants were refused, and catalog
  lock absence and the retained 13/13 terminal-render evidence were verified.
- Only the separately approved disposable folder was removed, and its absence
  was verified. This disposed of the synthetic catalog, its photo rows, service
  and generated cache data.
- The immutable fixture/manifest, consent and owner-decision records, and copied
  native receipt remain outside that folder. Their expected hashes/retention
  were checked. Private task-workspace operator receipt: `private-evidence/0126/disposal-v4.json`.

The original native JSON remains byte-identical. Its `catalogDisposalRequired`
field describes the native fixture's earlier completion state; this later
operator record establishes manual disposal without rewriting that measurement.
All profile, callback/scheduling and production qualification limits above remain.
