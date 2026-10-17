# Fixed-origin post-handler edge fault definitions

Date: 2026-10-17. Ticket #0040. Status: finite offline implementation;
supported native transport method unresolved. No hosted/native qualification.

The [#0037 verdict](fixed-origin-feasibility-verdict-2026-10-16.md) remains
unqualified: no supported effective-path allocation and credential-redirect
protection method has been established. These definitions preserve that obstacle
for later native/edge execution. They do not turn an older redirect observation
into evidence for another code, resolve the method, or authorize a live run.

## Boundary and exact finite cases

`probes/fixed-origin-isolation/edge_faults.mjs` replaces a response only after
the unchanged actual pinned b599ca8 thumbnail handler has completed successfully.
The harness first measures its exact synthetic PNG and its 200/private-no-store/
nosniff response, then separately measures the injected final response. The
original handler response is compliant; injected responses are qualification
stimuli, not claims about production output. See the approved source boundary in
[the #0038 isolation record](fixed-origin-isolation-2026-10-16.md) and actual
upstream refusal cases in [the #0039 matrix](fixed-origin-fault-matrix-2026-10-17.md).

Only the exact #0038 thumbnail path/query is eligible. Closed case identifiers
select the following fixed responses; maximum final body size is **262145 bytes**.
There is no caller-supplied destination, delay, body, header or size.

| Case | Final stimulus |
| --- | --- |
| `edge-redirect-301` | HTTP 301, empty body, fixed receiver suffix `/301` |
| `edge-redirect-302` | HTTP 302, empty body, fixed receiver suffix `/302` |
| `edge-redirect-303` | HTTP 303, empty body, fixed receiver suffix `/303` |
| `edge-redirect-307` | HTTP 307, empty body, fixed receiver suffix `/307` |
| `edge-redirect-308` | HTTP 308, empty body, fixed receiver suffix `/308` |
| `edge-wrong-media` | HTTP 200, `text/html`, 33 synthetic bytes |
| `edge-malformed-png` | HTTP 200, `image/png`, 12 bytes: PNG signature followed by four zero bytes, no image chunks |
| `edge-truncated-png` | HTTP 200, `image/png`, 55 bytes / declared 67 for the #0039 PNG, or 56 bytes / declared 68 for the unchanged #0038 wrapper PNG; each removes its 12-byte IEND chunk |
| `edge-declared-excess` | HTTP 200, `image/png`, decodable padded PNG of 262145 bytes with that declared length |
| `edge-undeclared-excess` | Same fixed 262145-byte PNG, no Content-Length |

Each redirect Location is exactly
`https://flickrgroupaddr.com/api/v001/existing-public-photos/photo/thumbnail/qualification-receiver/<run>/<code>`.
`<run>` is the trusted constructor's existing primitive string of 32 lowercase hexadecimal characters;
`<code>` is exactly the corresponding code in the table. No query, fragment,
credential or supplied destination is appended. The run and code validator
refuses other values before coercion or response consumption, including boxed
strings, arrays and objects with stateful `toString`. These are receiver destination specifications only: this
module registers no receiver or public route and follows no redirect.

## Offline verification and remaining obligations

The focused Node.js 24.22.0 suite has 13 passing tests. Every one of the ten
stimuli executes the actual pinned candidate router, authentication, discovery,
thumbnail buffering and final fences against isolated SQLite first. Bundle,
captured rollback and archived candidate source digests are checked before
execution. Candidate and captured bundles are never copied into tracked files.
Ten discovery calls and ten image calls occur solely in memory; global fetch,
host I/O and dynamic import counters remain zero, and no photo binding or
submission intent is created.

The separate receipt records compliant-handler status, injected status and
observed byte count, with hosted/native/method flags explicitly false. The
#0039 collector checks only a status-dependent byte ceiling. Its `accepted`
field is a length measurement, not successful image decoding or semantic
acceptance: malformed and truncated bodies can fit the ceiling. Oversize cases
exceed the fixed success ceiling by one byte.

Node Response exposes the deliberately inconsistent truncation Content-Length;
this does not prove that an HTTPS provider will preserve it or how the native
host networking stack will deliver or reject it. No native decoder, allocation,
credential forwarding, redirect following, receiver delivery, cancellation or
cleanup behavior is observed here. No receiver request is made. Later receiver
lifecycle and native entrypoint work must enforce the same run/capability/expiry
boundary and obtain the required concrete authorization. The #0037 missing
supported method remains unresolved and blocks complete native/edge
qualification; this offline matrix cannot unlock it.

JavaScript is needed here because the composition exercises the unchanged Worker
Response boundary and Node VM candidate; no Python orchestration or dependency
change is required. Reuse the private #0038 fixture, set `FGA_OFFLINE_FIXTURE`, and
run from the API repository with pinned Node:

```console
node --experimental-vm-modules --test probes/fixed-origin-isolation/edge_faults.test.mjs
```

The two accepted compliant source PNGs are fixed: the #0039 fixture is 67 bytes
and the unchanged #0038 wrapper fixture is 68 bytes. Their corresponding
truncation stimuli are 55/67 and 56/68 actual/declared bytes. These are finite
source-dependent cases, not arbitrary lengths or proof of native decoding.
