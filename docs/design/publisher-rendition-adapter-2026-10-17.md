# Publisher rendition composition

Date: 2026-10-17. Disabled implementation candidate for #0098, targeting
Lightroom Classic 15.6 and Adobe SDK15.3 only. This is an engineering integration
note, not a native qualification or lifecycle-wire approval.

The accepted [publish flow, Phase4](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/zero-state-publish-flow.md#phase-4--per-photo-selection-rendering-and-preflight)
owns the full-resolution 8-bit sRGB PNG default and completed-render checks.
[RenditionPolicy](../../clients/lightroom/publisher/RenditionPolicy.lua) owns the
finite configured format/byte policy and its external source provenance. Its
companion policy note records current Flickr evidence and the conservative
configured ceiling; this adapter does not invent another provider limit.

## Composition contract

Require `RenditionAdapter` from the separate, unregistered publisher source.
`Adapter.new(deps)` requires a `current(context)` function;
`cancelled()` is optional. Run in an SDK task; all yielding protected operations
use the actual `LrTasks.pcall`.

The provider must resolve the policy and apply its returned `exportSettings` to
the actual export property table before Lightroom starts rendering. Pass those
validated settings to `adapter:process(rendition, settings, preparedContext, consume)`.
The provider wrapper passes the actual property table and checks it against a
detached normalized policy record at every current-context fence. The adapter validates
the settings but never changes an already scheduled rendition. A desired or
detached settings record cannot establish what Lightroom actually rendered.
The default is full-resolution PNG, 8-bit, sRGB. Explicit JPEG is the supported
alternate; unsupported formats, depth, profile, resize and JPEG byte targeting
fail policy validation. There is no automatic conversion or retry fallback.

The owning provider must prepare every candidate photo's opaque durable context
before starting the export session's rendering. SDK `exportContext:renditions()`
starts rendering; calling `waitForRender()` later only waits for its completion.
Consequently preparation inside this adapter would be too late to establish the
accepted before-render ordering. The dormant provider `prepareBeforeRendering`
seam enumerates `photosToExport()` and invokes the owning #0097 context adapter
before any rendering operation. That adapter supplies durability and immutability,
including frozen selection and upload-attempt preparation. This adapter accepts
the already prepared context, performs no preparation or freeze, and rejects nil
or false with `context_required`. The provider wrapper binds the prepared context
by the exact `rendition.photo` object; the raw adapter trusts that mapping.
The future dispatcher must connect the pre-start
seam to this per-rendition consumer; `processRenderedPhotos` remains disabled.
`current(context)`
must return exactly true while the context remains usable. Errors and any other
return fail closed. Cancellation and current-context checks fence waiting,
consumer entry and completed-byte reads.

The adapter calls the existing #0028 `RenderPreflight.checkRendition` with a
private proxy. That proxy calls the real `waitForRender` once and captures only
the resulting path. Invalid configuration and missing/stale context never wait
for or consume a rendition; this alone does not stop already scheduled rendering.
Failed rendering or preflight never enters the consumer. All later checks use
the cached path without another render. #0028 continues to own exact size
comparison, equality acceptance, missing/empty/unreadable-file checks and its
fixed failure explanation. Settled preflight policy is unchanged.

After preflight, the adapter reads a baseline of the completed bytes within the
same export callback. `consume(lease, context, config)` receives a detached
configuration view and an expiring lease; it receives no path or rendition.
`lease:read()` reruns actual #0028 preflight, reads the file again, compares the
exact bytes with that baseline and rechecks cancellation/context. A same-size
replacement with different bytes fails `file_changed`; a failure permanently
poisons that lease. The adapter does not claim a filesystem lock or atomic
identity check. A byte-identical replacement is equivalent for this boundary.
The future multipart builder must use the returned immutable Lua string as its
body input synchronously, rather than reopen a path later. Bytes must not enter
logs, results or durable state.

Returning true from the consumer after at least one successful lease read
produces `{ok=true, code="handed_off"}`. This records only that bounded handoff,
never upload, publication, authorization or Album success. Exceptions, false or
nil produce `handoff_failed`; a true result without reading produces
`file_not_read`. Any observed lease/fence failure wins over consumer success.
All other public results retain fixed codes and numeric byte counts only.
The provider must retain exactly one result per photo and continue independently
after another photo fails. Reusing the same rendition in this adapter instance
fails `duplicate_rendition` before a second wait or consumer call.

## File and SDK lifetime

The lease expires unconditionally when its callback returns, including failures.
Its private path and baseline are cleared. Retained leases return `lease_expired`;
no rendition or path is returned for later use. The SDK owns temporary-file
deletion; this adapter neither deletes nor moves Lightroom's output.

The local SDK15.3 `LrExportContext.renditions` reference documents that iteration
starts rendering. Its `LrExportRendition.waitForRender` reference documents yielding until the
render is complete, with a successful skipped-render exception that need not
produce a file. Existing #0028 independently checks existence. The export
provider reference's `canExportToTemporaryLocation`, `hideSections` and
`showSections` explain that temporary output is deleted when the export finishes.
`renditionIsDone` applies to export filters; it is not a provider file-retention
API and is not called here. `LrFileUtils.readFile` supports non-ASCII paths;
`fileAttributes` exposes size and dates, not a content identity guarantee.
Licensed reference material is consulted locally and is not redistributed.

Exact-byte revalidation deliberately retains one bounded baseline string and
temporarily reads additional strings. It makes no streaming or constant-memory
claim. Settings validation and byte stability do not decode the image or prove
its embedded color profile, dimensions or bit depth. Private current-host
qualification must establish that the provider applies these SDK settings.

The separate provider remains unregistered and live composition remains gated.
No real render, native fixture, network request, credential access, upload,
catalog publication write or #0094 proposed-wire assumption is introduced.
Focused synthetic tests exercise actual #0028 Lua modules and this composition;
the independent review and parent aggregate checks remain required for handoff.
