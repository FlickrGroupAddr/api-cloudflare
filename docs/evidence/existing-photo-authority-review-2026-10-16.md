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

## Browser factory follow-up for native fixture 0.0.1.5

The primary agent reported that fixture 0.0.1.4 stopped at `load_browser` on
Lightroom Classic 15.6 because `setfenv` was unavailable, before any request or
page presentation. This is primary-observer evidence, not a host observation
made by this reviewer. That failure does not qualify browser behavior or
transport.

Reviewed `ExistingPhotoBrowser.lua:7` now constructs an explicit
`Browser.new(sdk, client)` instance. The fixture loads the actual release module
and supplies its narrow SDK adapters and actual client directly
(`probes/FGA-ExistingPhoto-Qualification.lrplugin/Qualification.lua:140`). It no
longer rewrites environments, globals or module caches to substitute dependencies.
Reading the presence of standard functions in sanitized diagnostics is not an
environment mutation. No new networking, credential or catalog capability was
introduced by the factory.

The default `Browser.run` API remains a lazy singleton
(`ExistingPhotoBrowser.lua:226`): it imports the documented SDK modules and
requires the existing client only on first use. The singleton retains the prior
busy guard. Explicit fixture instances keep their own busy/cancellation state.
Complete-page staging, per-image/client and aggregate page bounds, opaque
temporary files, cleanup registration, failed-deletion refusal, cancellation
checks, selected-row verification and read-only membership behavior remain in
the instance implementation. The default image validator still delegates to the
same client validator. The source candidate's transport qualification gate
remains required before a browser request.

Review caught compounded UTF-8 encoding in three UI literals during the wrapper
rewrite. The owner corrected the ellipsis and observation separators to plain
ASCII; the final source was inspected explicitly as UTF-8. No remaining material
behavior or security defect was found in the factory/fixture change.

Independent final verification:
`uv run --frozen python -m unittest tests.test_existing_photo_qualification_native tests.test_existing_photo_client`
passed 42 tests, zero failed. This includes the explicit factory with
`setfenv=nil`, lazy module loading, fixture scenarios and existing cache/protocol
checks. These are actual Lua 5.1 tests with injected SDK/HTTP adapters; they do
not prove the supported native host, `LrHttp` transport or production behavior.
The primary agent owns the release version increment and subsequent host Reload.
This reviewer performed no host action or runtime-source edit.

SHA2-256 digests of the final reviewed sources:

| File | Digest |
| --- | --- |
| `clients/lightroom/FGA-LrC15.lrplugin/ExistingPhotoBrowser.lua` | `c879fc04f84667661a1073ab526ef094644292cbc21f1504f6b38ae0b2a38aad` |
| `probes/FGA-ExistingPhoto-Qualification.lrplugin/Qualification.lua` | `114edef625417f2b792579a18a6514302ead5341abd85b60cc3172c4f6262feb` |
| `probes/FGA-ExistingPhoto-Qualification.lrplugin/Info.lua` | `47e2c3755256bf17619c8ebf97fc9a1103cf1ae582382b5d538c0adb5ceadf63` |
