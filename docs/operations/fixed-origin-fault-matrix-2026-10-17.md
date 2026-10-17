# Fixed-origin actual-handler fault matrix

Date: 2026-10-17. Ticket #0039. Status: offline implementation ready for
independent review. This is implementation evidence, not qualification.

The dedicated finite harness exercises the unchanged pinned candidate Worker
from commit `b599ca828d2a645b686aca0354d6c8ee2c2a0250`, through its actual router,
authentication, discovery, image buffering and final authority checks. Before
execution it verifies the candidate bundle SHA2-256
`c1edd7e5e721119030085c9c0705de5d2f3a32b9cffc6bbed56f363df3432e36`, the exact
captured ordinary dispatcher digest and every archived candidate source digest.
The source preparation and split-source authority remain described in
[the #0038 isolation record](fixed-origin-isolation-2026-10-16.md).

## Finite cases and measured result

Twenty actual-handler cases and two collector/receipt checks passed with
Node.js 24.22.0 and the existing VM/SQLite adapters. Fresh in-memory SQLite
stores apply the pinned migrations for every case. The only upstream seam is
`createWorker`'s fetch dependency: it supplies fixed in-memory Flickr-shaped
discovery and static-image responses, with no network implementation.

| Cases | Actual result |
| --- | --- |
| Decodable PNG, decodable JPEG, exact 262144-byte PNG | 200; exact expected bytes and private/no-store |
| Declared and undeclared 262145-byte bodies | 503; bounded application JSON |
| Finite upstream 502, declared truncation, wrong media, wrong signature | 503; bounded application JSON |
| Upstream 302 with foreign Location | 503; exactly one image request, no redirect follow |
| One 16000-ms stalled image body | 503 at 15013 ms; actual deadline cancelled the stream before its timer completed |
| Missing authentication, invalid authentication, bad query | 401 empty challenge, 401 JSON, 400 JSON; zero upstream requests |
| Final installation revocation, link revision change, grant generation change | 401, 409, 409 after image selection; no image publication |
| Foreign discovered identity, nonpublic photo, foreign image destination | 503 before image request |

The PNG generator creates a complete grayscale image with valid PNG chunk CRCs,
compressed scanline and IEND. The boundary image uses an ancillary padding chunk,
preserving a decodable image at exactly 262144 bytes. The JPEG is the existing
generated solid-color 2x2 fixture, not a signature-only marker. Independent local
System.Drawing pixel decoding succeeded for both PNG sizes (1x1) and JPEG (2x2).
That fixture check is not Lightroom Classic host decoder evidence.

The fixed responder checks the exact discovery parameters, signed discovery
request, fixed credential-free static image destination, GET/manual redirect
policy and absent Authorization/Cookie/Referer on image requests. Unexpected
responder assertions or SQL mutation failures are counted and fail the test;
they cannot be mistaken for a passing expected 503. Authority mutations occur
only in the isolated store, after image selection, using the valid revocation
transaction where required. Candidate SQL guards remain installed.

## Sanitized collection

`collector.mjs` consumes and discards the response stream. Its closed receipt
contains only status, observed byte length, applicable limit and acceptance.
Successful image bodies have a 262144-byte limit; all other responses have a
4096-byte limit. An over-limit body cancels collection and yields a failing
length-only receipt, without content, headers, body prefixes or exception text.
Tests cover exact 4096 and 4097-byte denials plus an oversized synthetic private
error string. Actual application error bodies measured 170–189 bytes; missing
authentication measured zero. The runner asserts JSON error shape and excludes
synthetic upstream error markers from published denials without logging bodies.

The final runner receipt contains only finite case labels, statuses, lengths,
timings, pinned commit, zero host-I/O/global-fetch/dynamic-import counters, and
explicit false hosted/native qualification and feasibility-change booleans.
No installation credential, OAuth header, private identity or raw source appears
in its output. All fixture credentials and photo identities are public synthetic
markers.

## Reproduction and boundaries

Prepare or reuse the verified private #0038 fixture using its documented
procedure, then run the focused suite from the API repository:

```console
node --experimental-vm-modules --test probes/fixed-origin-isolation/fault_matrix.test.mjs
```

`FGA_OFFLINE_FIXTURE` must point to that private fixture and `node` must be the
pinned 24.22.0 executable. No dependencies, toolchain or application sources were
updated. JavaScript is used here because the actual unchanged Worker bundles,
Node VM/SQLite adapters and Web Streams must execute in one runtime; Python
retains fixture preparation ownership.

The #0038 wrapper and its three public synthetic selectors remain unchanged.
This runner adds no endpoint or deployment artifact and does not route ordinary
traffic. Integrating these finite cases into a future selected qualification
branch requires explicit wrapper review and the separate entrypoint/lifecycle
work. Its offline success does not pass the #0037 feasibility verdict, native
decoder observation, edge/provider timing, cleanup/restoration, or any live
execution gate. The exact captured ordinary dispatcher remains the rollback
baseline. No cloud resource, real Flickr fetch, credential reader, native
qualification session or deployment was used. Existing accepted architecture
contracts continue to control production behavior.
