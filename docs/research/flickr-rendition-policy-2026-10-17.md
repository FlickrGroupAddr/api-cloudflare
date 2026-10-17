# Flickr rendition configuration evidence

Date checked: 2026-10-17. Scope: #0098 offline integration for Lightroom
Classic 15.6 / SDK 15.3. This research records engineering configuration within
accepted ADR 0002; it does not accept a new product contract or qualify native
rendering, account eligibility, transport, or Flickr uploads.

## Authority and configuration

[Accepted ADR 0002](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/decisions/0002-lossless-png-output.md)
owns the full-resolution 8-bit sRGB PNG default, separately selected JPEG,
hard completed-file preflight, and absence of automatic conversion, resizing,
quality reduction, or in-flow fallback. Its explicit 16-bit mode remains gated
on a private under-limit round trip. This task does not offer that mode or
enable a new settings control; the first usable provider's disabled PNG control
remains an independent UI requirement.

The reusable implementation is
[`RenditionPolicy.lua`](../../clients/lightroom/publisher/RenditionPolicy.lua).
`resolve(settings)` returns a fresh configuration or `nil, fixedCode`.

| Field | Configuration |
| --- | --- |
| `policyId` | `flickr-photo-decimal-200mb-2026-10-17` |
| `maximumBytes` | Exactly `200000000` bytes, inclusive |
| `format` | `PNG` by default; `JPEG` only when explicitly selected |
| `LR_export_bitDepth` | `8` |
| `LR_export_colorSpace` | `sRGB` |
| `LR_size_doConstrain` | `false` (full resolution) |
| `LR_jpeg_useLimitSize` | `false` (no file-size-driven quality selection) |
| `LR_jpeg_quality` | JPEG only: finite number in `[0,1]`; default `1` |

Absent relevant settings receive these defaults. Explicit incompatible format,
depth, color space, resizing, size targeting, or invalid JPEG quality fails
resolution. Unknown settings are not copied into the normalized export-setting
projection; the integration owns unrelated export/session fields. Stale JPEG
quality is irrelevant for PNG. Neither caller fields nor returned-table mutation
can change later resolutions' configured ceiling. The adapter must retain its
own resolved snapshot through the rendition's file lifecycle.

## Current official Flickr evidence

- [Upload requirements](https://www.flickrhelp.com/hc/en-us/articles/4404079649300-Flickr-upload-requirements),
  opened 2026-10-17, displays an update date of 2026-07-01. It permits PNG and
  JPEG, reports a per-photo maximum of 200 MB, rejects RAW, and describes a
  width-to-height cap of 31.25. TIFF/BMP involve provider conversion; HEIF/HEIC
  support is restricted to the Flickr app and involves conversion. Those
  formats, GIF, and video are outside this finite FGA rendition policy.
- [Official Pro plans](https://www.flickr.com/account/upgrade/pro) advertises
  unlimited storage. That storage entitlement does not remove the separately
  documented per-photo constraints. No account-specific entitlement was read.
- [Upload API specification](https://www.flickr.com/services/api/upload.api.html)
  identifies `https://up.flickr.com/services/upload/` as the binary upload
  endpoint, directs clients to account upload-status information for limits,
  and documents oversized-file rejection. No authenticated method was called.

The help article does **not** define MB in bytes. Therefore this implementation
does not claim that Flickr's exact server cutoff is 200,000,000 or 209,715,200.
It deliberately configures the smaller decimal interpretation, 200,000,000
bytes (about 190.735 MiB), which fits either interpretation. This is a
conservative engineering ceiling sourced from current provider wording, not
an invented historical maximum or a measured provider boundary. Files above
this configured value fail even if a provider might accept them. Files equal
to it retain #0028's inclusive boundary behavior. Changing this finite
configuration requires renewed source review and focused integration checks;
unlimited storage must never become an unlimited-byte setting.

Passing the byte preflight does not guarantee Flickr accepts a photograph:
aspect ratio, content rules, account state, and provider availability remain
provider constraints. This task neither introduces speculative dimension limits
nor claims decoded-image validation. A filename extension cannot prove format.

## Adobe SDK 15.3 evidence and limits

The [official Lightroom Classic developer page](https://developer.adobe.com/lightroom-classic/)
describes SDK extension of export/publish and rendering. The official page was
searched on 2026-10-17; direct browser fetch timed out. Exact property evidence
comes from the locally licensed Adobe SDK 15.3, read without executing its
samples or redistributing the SDK:

- `API Reference/modules/LrExportSettings.html`,
  `LrExportSettings.extensionForFormat`: the current format enumeration includes
  PNG and JPEG (alongside other Lightroom formats that this policy rejects).
- `Manual/Lightroom Classic SDK Guide.pdf`, printed pages 65-66:
  `LR_export_colorSpace`, `LR_jpeg_quality`, `LR_jpeg_useLimitSize`, and
  `LR_size_doConstrain` document the normalized settings above. File-size
  targeting lets Lightroom choose quality, so it is explicitly disabled.
- The guide's older still-format list omits PNG and describes
  `LR_export_bitDepth` only for TIFF/PSD. The newer LuaDoc establishes PNG
  support but does not independently establish PNG bit-depth behavior.
  Accepted ADR 0002 and the project's prior PNG matrix supply the existing
  evidence for requesting `LR_export_bitDepth=8` with PNG. This research
  preserves that accepted setting; it does not claim the stale guide alone
  proves PNG depth or requalifies it on 15.6.

The module validates requested configuration. It does not inspect rendered
pixel depth, ICC profile, dimensions, or decoded file type. SDK compilation
and offline shim tests likewise do not prove native rendering honors settings.
The later native qualification packet retains those checks, along with all
existing transport and private upload gates.

## Integration boundary

The dormant provider preparation seam owns freezing per-photo context before
render scheduling; its documented settings callback applies resolved settings.
The rendition adapter consumes that already-prepared context, waits for the
completed file, and calls the existing #0028 preflight with the resolved exact
ceiling. The later #0103 dispatcher and native qualification must establish the
actual scheduling order before this becomes an enabled provider. Render/preflight failure cannot authorize an upload.
It owns completed-file identity/revalidation until multipart consumes the file;
the resolved configuration's source metadata stays available for evidence.
JPEG requires a separate deliberate settings selection and a new publish
action. No error path selects it, reduces quality, resizes, or renders a second
candidate. #0028's pure boundary proof remains unchanged.
