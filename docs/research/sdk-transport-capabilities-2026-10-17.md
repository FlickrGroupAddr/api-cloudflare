# Lightroom SDK 15.3 transport capability evidence

Status: Research only; ticket #0147. Inspected 2026-10-17 while the card was In Progress.

## Outcome

The inspected Adobe SDK 15.3 documentation does not supply a supported `LrHttp` interface that proves a receive-allocation ceiling, pre-follow redirect rejection, Bearer forwarding policy, or caller-driven abort of an active request. This is an evidence gap in the documented interface, not proof of every possible runtime behavior or a claim that all supported alternatives are impossible. A returned-body length check and a discarded late result cannot establish these properties before their relevant effects.

A supported external-process integration seam exists. Its HTTP guarantees would belong to the separately selected helper and its complete integration; the SDK does not provide them merely by launching it. No helper was selected, built, launched or qualified in this research.

## Pinned source and scope

The local, licensed Adobe bundle is `C:/Projects/FGA/architecture-design/vendor/LrC SDK/15.3/`. `Readme.txt` identifies **15.3 Release**, build `202604090947-8f3672ed`. Paths and line references below are relative to that bundle. They are provenance pointers, not redistributable SDK content. No SDK sample source, sample asset or substantial documentation excerpt is included.

The previously recorded Lightroom Classic 15.6 host/build is historical only. No host was observed, initialized or exercised for this note, and SDK 15.3 documentation is not host 15.6 qualification.

## Documented facilities and gaps

| Facility | Documented scope and version | What this establishes; remaining gap |
| --- | --- | --- |
| `LrHttp.get(url, headers, timeout)` | `API Reference/modules/LrHttp.html:351-381`; first supported SDK 1.3 | HTTP/HTTPS GET with request headers; returns response body string and headers/status table. No documented receive sink/chunk callback, receive-byte ceiling, redirect mode, final/effective URL or active request handle. Internal allocation strategy is unspecified; do not infer it from the string return. |
| `LrHttp.post(url, postBody, headers, method, timeout, totalSize)` | Same page `:444-486`; first supported SDK 1.3, outbound body producer and `totalSize` support 4.1 | Optional HTTP method and chunk-producing **request** body. `totalSize` describes that outbound body; it is not a response limit. Same missing response/redirect/abort controls. |
| `LrHttp.postMultipart(...)` | Same page `:500-539`; first supported SDK 1.3, outbound producer 4.0, `suppressFormData` 5.0 | File/string/chunk-producing multipart **request** body and upload progress callback. These are not receive streaming, response-byte accounting or documented cancellation callbacks. Returns response body string. |
| HTTP `timeout` | Same page `:366`, `:465`, `:518` | Timeout applies during each connection phase. It does not document one total wall-clock deadline across phases or a separate caller-triggered abort API. |
| Error metadata | Same page `:316` (description before its example) | Error categories include cancellation, timeout and redirect errors, and metadata may contain partial response data. An error name does not establish caller control, redirect policy or a receive-allocation bound. |
| Progress cancellation | `API Reference/modules/LrProgressScope.html:460-462`, `:582-591`; first supported SDK 1.3 | `cancel()` signals cancellation; work responds by polling `isCanceled()`. Documentation expressly distinguishes this from immediate stopping. No documented link that aborts an outstanding `LrHttp` request. |
| Tasks | `API Reference/modules/LrTasks.html:316`, `:324-342` | Cooperatively scheduled tasks and their enumerated functions do not provide an active HTTP cancellation handle. Starting a second task or suppressing late delivery is not evidence of stopping the first request. |
| Shell helper | `API Reference/modules/LrTasks.html:375-392`; SDK 1.3. `Manual/Lightroom Classic SDK Guide.pdf`, pages 48 and 52 (same printed/PDF numbering) | `LrTasks.execute(cmd)` passes a command to the OS shell and returns its exit status while blocking only the calling task. Guide documents external application integration. No documented process handle, termination/deadline control or network policy is supplied by this API. Mac sandbox restrictions are documented separately; Windows helper feasibility is not host qualification. |
| Local helper IPC | `API Reference/modules/LrSocket.html:351-368`, `:377-379`; SDK 6.0 | `bind` supports localhost send/receive sockets and `close` closes that connection; automatic closure occurs on plug-in disable/removal. This is a supported IPC seam, not HTTPS/TLS support or cancellation of helper-owned HTTP. No documented inbound message allocation ceiling is supplied. |

`LrHttp` function index (`:324-337`) contains GET, POST, multipart POST, browser opening and cookie parsing. No HTTP download-to-file function is documented there. A search of the supplied API Reference for download/redirect/receive-limit terms found no alternative HTTP-to-file or redirect-control API; relevant Manual HTTP/download references did not document one. `LrFileUtils` file operations do not themselves provide a network receive path. This finding is scoped to the inspected 15.3 documentation, not an assertion about undocumented internals or future SDKs.

Authorization headers can be supplied as generic request headers. The reference does not specify whether any redirect is followed, which redirect statuses/method transformations occur, whether or when Authorization is stripped or forwarded, or whether effective-origin metadata is returned. Do not infer a safe Bearer policy from generic header support, an HTTP status returned after the call, or a redirect error category.

## Consequences for the qualification method

- A fixed URL constructed before a request proves that input URL only. It does not prove every internally followed destination or credential-forwarding behavior.
- Response length/status validation after return can bound accepted application data. It cannot prove a pre-acceptance transport allocation ceiling or prevent an already-followed redirect.
- Timeout values, progress cancellation and stale-result rejection do not document an active total deadline with transport termination.
- A helper is a candidate supported integration route, not an accepted transport design. Before relying on it, pin its implementation/version, receive/decompression/header bounds, redirect refusal and credential behavior, total deadline and active cancellation, IPC allocation/identity protections, packaging, lifecycle and cleanup. Demonstrate those guarantees in the complete effective path and obtain any required architecture acceptance.
- Native negative tests can supply observations for their exact version/configuration and cases; they cannot expand an undocumented universal API guarantee. This note supplies no native, hosted or credential-bearing evidence.

## Public official source cross-check

[Adobe's Lightroom Classic developer page](https://developer.adobe.com/lightroom-classic), retrieved 2026-10-17, confirms the Lua SDK and export/publish customization model. It does not specify these low-level transport controls or identify the pinned bundle version. No community/mirror page is used as authority for the 15.3 claims; local Adobe documentation is the exact-version source.

## Reproduction and evidence identity

Read-only operations: local source-reference inventory, text extraction from relevant Manual pages with bundled `pypdf`, API name/parameter/return review and public official-page retrieval. No account/provider request, native initialization, credential file/probe, new dependency, real-photo input or live qualification occurred. This is author evidence, not the final independent review.

SHA-256 of inspected reference files:

| File | SHA-256 |
| --- | --- |
| `API Reference/modules/LrHttp.html` | `1a2a5b44baf22c5f77ba42c90ea2a73988237fd718ef55baac00463bab22ee1b` |
| `API Reference/modules/LrTasks.html` | `fca7f6856eb4fb8cac3e968d044a74adeaa3c6be3c3cee24c14c12f2de750858` |
| `API Reference/modules/LrSocket.html` | `f76dc9757f9232afad72fa07432c42c1c3df951ab2ec586431c6377763f5b516` |
| `API Reference/modules/LrProgressScope.html` | `88a2ed946147f41341fbff91f14628228bc921ea01af3bed024a59f76c754623` |
| `Manual/Lightroom Classic SDK Guide.pdf` | `8361b7174194c7fee222dcaa15a1946ba105485e96e5fae2b86cd0ab7c6be5d3` |
