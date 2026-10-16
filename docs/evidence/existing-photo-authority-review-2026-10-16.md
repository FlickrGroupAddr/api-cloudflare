# Existing-photo authority and qualification review

Date: 2026-10-16. Scope: independent source, contract and offline-test review for
ticket 0023. Baseline implementation HEAD: `388a5ca7c6ca98e5d49873e6e3a7f2a9a56e8315`.
No hosted deployment, provider operation, credentials, desktop operation or real
Flickr photo was used. This evidence is not a production qualification receipt.

## Result

No new material authority or security defect was found in the reviewed disabled
candidate. Activation remains unqualified: exact hosted-edge and supported
Lightroom Classic transport evidence, the accepted production contract and
explicit capability activation are still required. Passing source tests cannot
substitute for those gates.

## Controlling authority

The architecture repository's `AGENTS.md` and `docs/README.md` hierarchy control;
accepted ADRs precede scoped accepted contracts, and Proposed documents remain
reviewable recommendations. The relevant canonical sources are:

- `architecture-design/docs/decisions/0060-accept-private-membership-observed-time.md:5`:
  accepted on 2026-10-15. Native observed-time checks, a 15-second abort timer,
  strict response validation and finite byte/entry limits are the approved
  private read-only membership profile. The real elapsed stall/scheduling/clock
  adjustment gap is explicitly accepted. It is not a defect requiring a new
  monotonic service or another timing decision.
- `architecture-design/docs/decisions/0061-develop-bounded-hosted-thumbnails.md:5`:
  accepted development and qualification direction only. Its detailed candidate
  has not been accepted as a production contract.
- `architecture-design/docs/hosted-thumbnail-candidate.md:5` and `:69`:
  Proposed, production disabled. The qualification matrix applies to the exact
  trusted backend/edge and supported native client path. It does not require a
  universal guarantee against an arbitrary malicious replacement server.
- `architecture-design/docs/existing-public-photo-intake.md:170` and `:249`:
  discovery and thumbnail presentation remain advisory. A fresh exact-photo
  owner/public binding proof still precedes any later non-idempotent group
  handoff; thumbnail success never supplies write authority.

## Reviewed implementation boundaries

- `src/existing_photo_discovery.ts:98` and `:126`: complete page validation,
  owner-fixed signed public-photo read, reduced transient response and final
  current-installation/link/grant checks. Invalid pages are unavailable rather
  than salvaged into partial or empty observations.
- `src/photo_memberships.ts:23`, `:44`, `:58` and `:77`: combined set/pool entry
  limits, exact binding ownership, SQL transaction guards for current
  installation/link/grant/binding authority, atomic observation replacement,
  revision-bound keyset reads and invalidation before a new initial read.
  Failed initial reads do not restore an old observation as current.
- `src/photo_thumbnails.ts:17`, `:37`, `:72` and `:88`: exact selected photo
  URL identity, fixed HTTPS static-Flickr allowlist, credential-free image
  request, manual redirects, streaming byte cap, declared/actual length and
  type/signature checks, whole-operation observed deadline, cancellation and
  final authority fences before returning complete bytes.
- `clients/lightroom/FGA-LrC15.lrplugin/ExistingPhotoClient.lua:119`, `:153`
  and `:290`: thumbnail route derives from a validated page row and goes through
  the fixed authenticated FGA origin. Returned image checks occur after the
  host request; they qualify cache publication, not response allocation or
  redirect credential handling inside `LrHttp.get`.
- `clients/lightroom/FGA-LrC15.lrplugin/ExistingPhotoBrowser.lua:42`, `:144`
  and `:195`: complete-page staging, failure before selection, registered
  dialog cleanup and fail-closed navigation after prior-page deletion failure.
  The selected photo obtains fresh binding proof before membership reads.
- `src/worker.ts:46`, `wrangler.example.jsonc:19`,
  `clients/lightroom/FGA-LrC15.lrplugin/ExistingPhotoClient.lua:7` and
  `clients/lightroom/FGA-LrC15.lrplugin/RunExistingPhotoBrowser.lua:12`:
  explicit configuration/client activation boundaries remain. The exported
  host-qualification booleans are evidence labels, not runtime substitutes for
  the environment flags and client gates.

## Material remaining proof

The candidate's exact-build/configuration qualification must establish actual
hosted success/error response bounds, timeout and redirect behavior, request
disconnect support, sanitized failure behavior and authority-race rejection.
The incoming request signal needs the reviewed compatibility setting; source
abort tests alone cannot establish provider disconnect notification.

Actual supported Lightroom Classic host tests must measure `LrHttp.get`
response allocation and Authorization behavior on redirects and establish a
documented mechanism plus qualified fixed-edge configuration that enforce the
supported path. Post-fetch Lua byte checks and injected request mocks do not
prove those properties. Complete recognizable rendering, navigation,
cancellation and temporary-cache cleanup also need exact-client host evidence.
The older fixture presentation proof is useful within its recorded scope and
does not qualify the new downloader. A narrowly authorized real-account public
read remains distinct from synthetic transport qualification.

JPEG/PNG validation checks bounded completeness/signature markers, not full
image decoding. This is already stated in the 2026-10-15 handoff; successful
native rendering must not be inferred from those source checks alone.

## Targeted verification

- `node --test tests/existing_photos.test.mjs tests/photo_thumbnails.test.mjs tests/thumbnail_review.test.mjs tests/photo_routes.test.mjs`:
  28 passed, zero failed.
- `uv run --frozen python -m unittest discover -s tests -p test_existing_photo_client.py`:
  33 passed, zero failed, exercising actual Lua 5.1. The ordinary sandbox and a
  temp-cache retry could not persist uv interpreter cache metadata; an approved
  outside-sandbox run of the same locked command passed. No alternate Python
  environment was substituted.

These tests exercise local SQL adapters, injected fetch/request behavior and
Lua protocol handling. They establish no live Workers edge, native SDK transport
or real Flickr response claim.

## Nonblocking wording drift

`src/photo_memberships.ts:7` still calls the release gap “Hosted monotonic15s
qualification,” and
`docs/operations/lrc15-development-handoff-2026-10-15.md:140` still describes a
missing scoped timing decision. The latter document has a newer resolved-status
note at `:85`. Accepted ADR0060 controls: the remaining task is qualification of
the accepted observed-time profile, not reopening the already accepted stall
limitation. This review changed no source or existing documentation.
