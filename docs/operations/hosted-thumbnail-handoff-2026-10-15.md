# Existing-photo timing and hosted thumbnail handoff

Date: 2026-10-15. Status: locally verified disabled candidate, ready for review.

## Approved decisions

Terry approved the private read-only membership observed-time amendment and
development of bounded hosted thumbnail transport. Canonical architecture
commit `26c33e3` records accepted ADR 0060 and ADR 0061, updates the normative
membership contracts and preserves the detailed thumbnail contract as Proposed.
ADR 0060 does not change write preflight, fresh ownership/public proof, permanent
pair protection, or the authority/publication fences. Its 15-second observed
read/body-validation budget is not a hard real elapsed guarantee across a host
stall. The thumbnail direction is authorization to develop and qualify the
candidate, not evidence that the deployed edge or native transport has passed.

## Implemented candidate

The authenticated route is
`GET /api/v001/existing-public-photos/{photoId}/thumbnail` with required unique
`page`, `page_size` and `linked_flickr_revision` query parameters. The FGA API
backend repeats a complete owner-fixed public discovery page, finds the exact
requested photo and validates its corresponding static Flickr thumbnail URL.
It accepts no client URL or owner override. The separate image fetch carries no
installation bearer, Flickr OAuth, cookies or referrer and refuses redirects.

The FGA API backend bounds the complete operation with a 15-second observed
timer/abort budget and the image body with a streaming 256 KiB cap. It checks
declared/actual length and JPEG/PNG signatures, then fences current installation,
linked revision and grant generation before returning validated image bytes.
Success is private/no-store with nosniff and same-origin resource policy; failures
return the existing sanitized JSON envelope and no image prefix. Signature
checks establish the tested completeness markers, not full image decoding.

The FGA LrC plug-in derives the fixed same-origin route from a validated complete
discovery page. It validates returned image bytes/headers before opaque cache
publication. A failed thumbnail invalidates the whole page; failure to delete a
prior page stops navigation and photo proof. Current credential checks and
cancellation remain in the existing request path. The release bundle is
**0.2.0.4**; no reload or host acceptance is claimed for this new build.

The dedicated `FGA_PHOTO_THUMBNAILS_ENABLED` flag is explicitly `0` in the
deployment template and missing means disabled. Existing-photo flags and client
production qualification remain disabled/false; the action remains unregistered.
No provider call, deployment, migration, photo write or dispatch was performed.

## Verification

- 218 combined Node runtime tests passed, including HTTP authentication/framing,
  feature gates and independent thumbnail regressions.
- 249 Python/actual Lua 5.1 tests passed; the separate existing native control
  harness also reports 424 assertions plus 98 group-browser assertions.
- Pinned native TypeScript 7, generated API consistency, Ruff and Pyright passed.
- The client agent ran Adobe SDK 15.3 compilation successfully for changed Lua.
- 18 related architecture authority/interaction/API contract tests passed.

The independent [review receipt](../evidence/hosted-thumbnail-review-2026-10-15.json)
records source hashes, fixes and bounded conclusions. Its staged commands are
historical review provenance; integrated regression files live in `tests`.

## Exact next work and review boundary

The next engineering step is a disposable hosted/native qualification matrix for
the exact endpoint, edge configuration and client build. Cover bounded success
and error bodies, oversize/truncation/timeouts, redirects and bearer handling,
disconnect behavior, current-authority changes, complete-page UI and cache
cleanup. Workers incoming request disconnect signals require a reviewed
`enable_request_signal` compatibility setting; no production configuration or
qualification has been claimed. The hard abort timer remains separate from
disconnect notification. Re-reading discovery for every image is deliberately
simple but its rate-budget/latency cost remains to be measured.

Use the detailed Proposed candidate in architecture-design for the full matrix.
Qualify the fixed trusted FGA endpoint and edge invariants; do not invent a
universal guarantee against an arbitrary replacement server or imply documented
native streaming controls exist. Return to design if the actual supported host
cannot satisfy the accepted transport boundary. Only then consider accepting
the production contract and enabling the read-only workflow. Intake and Flickr
write gates are independent and must remain paused during this work.

For group-selection review, use the separate
[actual-host evidence index](../evidence/lrc15-selection-preview-host-2026-10-15.md).
It records the later 60/61, search, duplicate/long identity and failure-state
observations, with the existing-public fixture and remaining ergonomics still
pending. The outbox proof is already independently recorded and was completed
by Terry on the board; do not ask him to repeat it or reinstall approved fixtures.

Terry's subjective selection interaction review still gates submission UI.
The first production trial still needs his exact photo/group pair and later
explicit activation approval after qualification; choosing a pair alone never
enables writes.
