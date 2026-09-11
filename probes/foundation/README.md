# D1 foundation and current-installation proof

This fixture exercises `src/worker.ts` and the root `migrations/` on disposable
Cloudflare resources. It never targets a production database. The proof wrapper
is deliberately separate: `/__proof/*`, fixture provisioning, arbitrary synthetic
credentials, and mutation probes are absent from the production entry point.

```powershell
npm ci
npm run check
node --test tests/installations.test.mjs probes/foundation/runtime.test.mjs
uv run --frozen python -m unittest tests.test_foundation_schema tests.test_foundation_probe
uv run --frozen python scripts/generate_api.py --check
uv run --frozen python scripts/foundation_probe.py guards
uv run --frozen python scripts/foundation_probe.py read
```

The Python controller uses the existing Wrangler login and creates random,
collision-checked Worker/D1 names. It checks the pinned native TypeScript compiler
before deploying. Initial deployment installs its proof bearer atomically with
the Worker version, and checks both read and POST readiness. Setup uses seven fixed version IDs with the same credential digests inside one
D1 batch. Concurrent or repeated identical setup is explicitly idempotent;
a different fixture is refused. Bounded retries are limited to this setup and
read-only calls. Guard mutations are not automatically retried. Re-run a fresh
disposable proof after other failures. There are no Flickr or AWS requests.

`guards` tests the actual migrations, writes synthetic protected history, upgrades
the populated database, exercises ordinary SQL guards and failed transaction
rollback, then exports and imports into another disposable database. Ordinary export
rounding is recorded; the exact adapter uses SQLite numeric literals and hex
text literals so JavaScript numbers, NUL and line-ending conversion cannot
change the archived values. An auxiliary
integer table tests exact signed 64-bit values without putting those diagnostics
in the application schema. Backup and Time Travel run only after the controller has removed the Worker
and verified its absence. Restored history is inspected through the
operator connection; the Worker stays removed throughout recovery.

`read` provisions seven CSPRNG credential fixtures in memory via the authenticated
HTTPS proof route. Only digests enter D1. It then tests the real application GET
route and compares aggregate database snapshots before/after the read phase.
It performs no protected write after setup, logs no credential/header/body, and
never exports that fixture database. Unknown/corrupt states rejected by the
schema are additionally exercised by injected-row unit tests. A proof-only
ordinary-operation adapter tests pending-scope rejection without inventing an
unimplemented production route.

Private manifests, provider identities, SQL exports and diagnostics are under
ignored `.foundation-runs/`. A report can be copied to `docs/evidence/` only after
checking its completion, cleanup, source hashes and redaction. Original failed
attempts remain private evidence. Cleanup is in `finally` and can be retried:

```powershell
uv run --frozen python scripts/foundation_probe.py cleanup --run .foundation-runs/rp-<24-hex-digits>
```

This command validates the run directory and generated names, verifies the
recorded database identity against provider inventory, and deletes only those
resources. A separate clone run has its own manifest and cleanup target. An
interrupted process may require both manifests to be cleaned up. Do not delete
private manifests before cleanup has been confirmed.

The local emulator is pinned to `2026-07-30`; hosted tests request `2026-09-11`.
Local results do not certify the later hosted runtime. Python owns provider
orchestration because it is the project's maintenance language. Small Node
bridges are used where native integration is material: Miniflare's runtime API
and importing the executable TypeScript route registry.

`wrangler.example.jsonc` builds only the application entry point and defaults to
reads disabled. It is a deployment template, not a live production configuration.
The diagnostic wrapper, fixture bearer and fixtures must never be deployed as
that application. Current scope is one read route; UI, credential provisioning,
rotation/revocation writes, scheduling, Flickr integration and production
TLS/LrC validation remain separate work.

Application test cases are never retried into a passing result. Only setup/status
calls have bounded retries, recorded in the public report. Each application
response must carry the proof wrapper's expected build marker; this header is
absent from the production entry point. Early provider responses are recorded by
status, safe header-presence flags and a body fingerprint, not by raw body.
An `unmetContractCases` entry makes the read command exit nonzero even when the
full case collection and cleanup complete. That is an owner handoff, not a pass.

Terry approved the private millisecond source-clock boundary and early
provider duplicate-Authorization rejection on 2026-09-11 (architecture ADRs
0053/0054, commit `0cf54f3`). The collector records that authority. The known
provider HTML 400 is accepted only for an authorized duplicate-header or
malformed-target case, with the expected fingerprint, no application marker,
no cookie, no redirect and no application Bearer challenge. Other responses
still fail. Positive and negative regression checks cover that boundary.
Original pre-approval reports are retained; fresh reports record accepted
provider rejections separately from application results.
