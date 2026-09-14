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

## Production artifact matrix

`scripts.production_matrix` builds the minified production Worker and imports those
same bytes through the external `matrix-driver.mjs`. The driver provides private
fixture controls and optional fault/clock hooks; it adds no production HTTP route.
`matrix-runtime.mjs` supplies Miniflare, real native coordinator storage, D1, and a
loopback HTTPS Flickr peer that verifies the actual OAuth signatures. Real Flickr
requests are never sent. Driver/runtime bytes are frozen for every process restart.

Local sections:

```powershell
uv run --frozen python -m scripts.production_matrix --environment local --section core
uv run --frozen python -m scripts.production_matrix --environment local --section queue
uv run --frozen python -m scripts.production_matrix --environment local --section crash
uv run --frozen python -m scripts.production_matrix --environment local --section blocks --block-ids FP-BLOCK-001 FP-BLOCK-002 FP-BLOCK-004 FP-BLOCK-005 FP-BLOCK-006 FP-BLOCK-007 FP-BLOCK-008 FP-BLOCK-009 FP-BLOCK-010
```

`--environment hosted-db` uses Wrangler's supported remote D1 binding.
`--native` additionally creates six synthetic Secrets Store slots and a private
service-binding bridge, referencing the existing narrow writer binding. Broad
operator credentials stay in the controller. Cleanup deletes only owned fixture
resources. Local mode emulates provider PATCH using Miniflare native secrets;
it is not evidence of the real Secrets Store API.

All output remains explicitly `partial-production-matrix`, with
`fullConformancePassed: false`. New reports retain case-specific recovery/seed
witnesses plus artifact, driver and runtime-adapter hashes. Do not combine component
reports from different runs into a full release claim. Miniflare's 2026-07-30
compatibility date is distinct from production's 2026-09-11 date.

FP-BLOCK-003 requires hosted snapshots and is not supported locally. Terry approved
that operation; all four integrated restore seeds passed. The old hold is resolved.

The complete command is `uv run --frozen python -m scripts.production_release_suite`.
It combines all 56 cases, all 28 mutations, fresh engine provenance, native cleanup
and the exact-module hosted runtime/redeployment supplement. The latter imports
the unchanged optimized module and uses synthetic provider responses. Its endpoint
has an expiring bearer guard and is removed after the run. Ordinary section runs
remain partial. See [the qualification checkpoint](../../docs/research/2026-09-14-complete-suite-qualification.md).

The manual `Native matrix diagnostic (not release qualification)` workflow runs a
fixed partial case with the same hosted setup and provenance read. Its output is
sanitized diagnostic evidence only; a successful diagnostic cannot replace the
complete Release validation workflow. Failed cases record invocation phases,
provider/native-read failures, call methods and durable resolution reasons.
