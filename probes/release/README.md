# Release adapter probes

These probes develop the infrastructure for the full release suite. They do not
produce a full production conformance pass.

## Real D1 behind an independently runnable Worker

Run `uv run --frozen python -m scripts.remote_d1_binding_proof --run` with the
project's local operator login or configured `CLOUDFLARE_ACCOUNT_ID` and
`CLOUDFLARE_API_TOKEN`. A user-supplied `--token-file` is also supported. The Python
controller creates an owned disposable database, invokes the Node helper, verifies
the inserted value through a separate REST request, and removes the database.

The Node helper requires Wrangler/Miniflare and uses the documented
`maybeStartOrUpdateRemoteProxySession` API. No custom D1 emulation or SQL relay is
introduced. It accepts only the generated disposable configuration name; session
and runtime cleanup are awaited. Raw logs remain in the ignored private run folder.
The controller prints only a sanitized result. The live application is not bound
to or changed by these resources.

Observed on 2026-09-14 with the dedicated CI token: remote write/read succeeded,
the independent REST witness matched, and database cleanup was confirmed. The
local worker runs with compatibility date 2026-07-30, as required by the current
pinned Miniflare build. This proves the remote-binding boundary; it does not prove
all release cases or parity with the newer hosted runtime date.

[Cloudflare remote binding API](https://developers.cloudflare.com/workers/local-development/#api).
