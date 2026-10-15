# Publisher preflight building block

Date: 2026-10-15. Original source, separate from the registered release bundle.
This module has no production provider registration and performs no upload,
authorization request, catalog write, image conversion, or resize.

`PreflightCore.lua` validates a caller-supplied positive exact byte limit and
completed-file size. `RenderPreflight.lua` waits for each supplied rendition,
checks file identity/attributes, rejects zero-length/oversized files, and proves
readability before returning a `ready` result. Equality with the configured
limit passes. `checkAll` preserves a result at each array index after an
individual failure; it makes no promise about concurrent scheduling or remote
completion order. Results contain only fixed codes and numeric byte counts,
plus the required oversized explanation; raw host exceptions, paths and image
data are excluded.

The future provider must persist each photo's immutable selection/context
before calling this adapter, provide its configured byte limit, and request
authorization only after `ok == true`. No current Flickr numeric limit is
invented here. Default render settings and format policy remain provider
integration work; the adapter respects the supplied rendition without changing
its settings or interpreting bytes as a new format.

## Documented SDK boundary

Verified against local Adobe SDK 15.3 API Reference, confirmed by Terry as the
latest available SDK on 2026-10-15. Target host qualification is Lightroom
Classic 15.6, Camera Raw 18.7, build `202609251514-f839cde9`.
The local SDK is at
`C:\Projects\FGA\architecture-design\vendor\LrC SDK\15.3`.

- `API Reference/modules/LrExportRendition.html`, `waitForRender`: yields
  until generation finishes and returns success/path. A skipped rendition may
  return true without a file, so file existence is checked independently.
- `API Reference/modules/LrFileUtils.html`, `exists` and `fileAttributes`:
  distinguish a file from directories/missing paths and obtain `fileSize`
  in bytes.
- The same reference's `readFile`: reads a string and is preferred over Lua
  `io` for paths containing non-ASCII characters. There is no documented
  metadata-only readability proof in the inspected API, so the adapter reads
  the size-approved file into memory briefly. This deliberate simple choice
  matches the project's memory priority; do not claim streaming preflight.
- `API Reference/modules/LrTasks.html`, `pcall(func, ...)`: protects yielding
  SDK operations; ordinary Lua `pcall` is used only by the synthetic test shim.

The content string is not returned or retained. Comparing its byte length to
the inspected file size rejects an observed size change. This cannot lock the
file against later edits or prove the same bytes will be uploaded; revalidation
and file lifecycle ownership belong to subsequent integration. It neither
claims file-format validation nor relies on an SDK secure-random generator.

## Validation

On 2026-10-15, eight Python unittest cases executed both modules in actual
Lua 5.1 (`lupa.lua51`) with synthetic SDK adapters. They cover limit-1/equal/+1,
invalid limits/sizes, missing/directory/empty/unreadable/changed files, render
errors/exceptions, ordered per-photo result retention after another failure,
and unchanged rendition settings. The shim refuses any import besides
`LrFileUtils`/`LrTasks`; no auth/network/catalog API is available to the adapter.
Adobe's SDK15.3 `luac -p` passed and Luacheck reported zero warnings/errors.

Run after integration from the implementation repository:

```console
uv run --frozen python -m unittest discover -s tests -p test_publisher_preflight.py
```

No Lightroom host render, production catalog access, or Flickr operation was
performed. SDK adapter behavior still requires isolated current-host
qualification when the provider is integrated; pure/synthetic success does
not pass that gate.
