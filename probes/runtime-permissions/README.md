# Runtime permission probe

This development-only probe tests implementation ticket #0007's narrow question:
can an ordinary Worker D1 binding, or the runtime owning a SQLite-backed Durable
Object, erase records protected by append-only SQL guards?

It uses fresh synthetic tables. It does not implement the production FGA schema,
invoke Flickr, or establish production conformance. The architecture
[worker persistence contract](https://github.com/FlickrGroupAddr/architecture-design/blob/a02d02558fe0a384f27c6b9c5aee59f340f2fc4a/docs/worker-persistence-scheduler-contract.md)
and [fail-polite conformance contract](https://github.com/FlickrGroupAddr/architecture-design/blob/a02d02558fe0a384f27c6b9c5aee59f340f2fc4a/docs/testing/fail-polite-worker-database-conformance.md)
own the requirements. A successful collection of counterexamples is a failed
protection property, not a production test pass.

See the [findings and decision handoff](../../docs/research/2026-09-06-native-runtime-permission-evidence.md)
and its sanitized evidence.

## Run

From the repository root:

```console
npm ci
npm run check
uv run --frozen python scripts/runtime_permissions_probe.py local
uv run --frozen python scripts/runtime_permissions_probe.py cloudflare
```

The Cloudflare command creates one uniquely named D1 database, one Worker and its
SQLite-backed Durable Object namespace in the existing Wrangler account. It
requires an authenticated Wrangler session with exactly one visible account.
It provisions only synthetic fixtures, installs an ephemeral probe secret,
collects the cases, and deletes those exact resources. It never accepts an
existing database or Worker as a target. This command requires authorization
for the isolated hosted probe; Terry granted it on 2026-09-06.

The checked-in Wrangler config is deliberately unconfigured. The controller
writes the real account/database bindings into its ignored run directory.
Do not deploy that template directly or add production bindings.

Each run prints its directory under `.probe-runs/`. It contains a checkpoint,
private CLI logs, fixture SQL and the report. Logs, account/resource identities,
and ephemeral secrets stay out of Git. The controller never logs the Cloudflare
authentication token: it sets `WRANGLER_WRITE_LOGS=false` for vendor commands
and obtains that token only in memory for a fixed Cloudflare
API cleanup request with `force=false`. This avoids Wrangler's noninteractive
confirmation defaults accidentally authorizing dependency-breaking deletion.

If interruption or network loss prevents cleanup, resume only cleanup for the
reported directory:

```console
uv run --frozen python scripts/runtime_permissions_probe.py cleanup --run .probe-runs/rp-<run-id>
```

The cleanup command validates the generated names and checks the database's
identity before deletion. It verifies Worker absence and the D1 inventory.
A failed cleanup remains recorded as unconfirmed. Never force deletion to
resolve an unexpected dependency.

A lost response from an attack phase makes that run incomplete. The collector
does not replay it. Complete cleanup, then create a fresh run. Read-only
connectivity checks do not provide evidence of a completed mutation.

## Cases and evidence

For both suppression-like and audit-like tables, the probe checks:

- ordinary reads and insertion of a new record;
- guarded update, delete, replacement insert, upsert and parent cascade;
- actual CHECK and foreign-key failures;
- removal of an update/delete trigger followed by an edit;
- table deletion and rename; and
- disabling CHECK enforcement and committing an invalid value.

The Durable Object also tests its own `storage.deleteAll()` capability. Fixtures
are created once, with a separate table per scenario; no fixture helper resets a
record between its before/after observations. D1 provisioning uses the operator
CLI, while attack statements execute through the deployed Worker binding.
Durable Object initialization and attacks both use that object's runtime,
which is not represented as an independent migration identity.

There are 28 D1 cases and 29 Durable Object cases. D1 work is split into four
cases per request to stay bounded within invocation query budgets. A database
compare-and-set consumes each phase; the collector refuses missing, duplicate,
reordered or wrongly scoped results.

The report records observed table/row/trigger changes, constraint outcomes,
engine-version availability, source/bundle/lockfile SHA2-256 fingerprints,
tool versions, and the hosted deployment identity. A denied metadata query is
recorded as unavailable metadata. An operation error is inconclusive and never
becomes a permission-denial pass.

Local checks also exercise absent/incorrect authentication, method/path/query/
body rejection, wrong-fixture rejection, terminal replay rejection, and a
transport boundary that refuses external network calls. The report excludes
the probe secret, and the controller rejects its appearance before saving
evidence. Only reviewed, sanitized reports belong in `docs/evidence/`.

## Toolchain audit, 2026-09-06

| Component | Selected/observed version | Reason or available update |
| --- | --- | --- |
| Node.js | 24.20.0 LTS after probe closeout | Upgraded from 24.19.0 at Terry's request. The retained permission-probe evidence correctly records its original 24.19.0 environment. |
| npm | 12.0.2 | Current stable release; compatible with the installed Node LTS. |
| TypeScript | 7.0.2 | Current stable TS7, with the native Go compiler. The installed launcher executes the Windows native `tsc.exe`. |
| Wrangler | 4.116.0 | Newest inspected release using stable Miniflare. Latest Wrangler 4.129.0 selects Miniflare 5 alpha. |
| Miniflare | 4.20260730.0 | Stable direct dependency, matched to Wrangler. |
| Workers types | 5.20260906.1 | Current stable direct dependency. |
| Hosted compatibility date | 2026-09-06 | Kept current as an explicit dependency. |
| Local compatibility date | 2026-08-06 | Maximum accepted by the selected stable emulator binary; local evidence is a separately dated comparison. |

The lockfile still includes vendor-pinned `unenv 2.0.0-rc.24` and
`youch 4.1.0-beta.10`. Thus the direct probe dependencies are stable, while the
entire transitive tree is not prerelease-free. These vendor helpers were not
force-overridden to unrelated versions. Recheck that tradeoff when refreshing
Wrangler; do not silently substitute the alpha simulator.

Python owns orchestration, validation and cleanup under `uv run --frozen`.
The Worker and fixture registry use TypeScript because they execute in the
Cloudflare runtime and are bundled by Wrangler. The small Node helper uses
JavaScript because Miniflare's programmatic runtime/lifecycle API is Node-native;
it disposes the emulator through its supported API. These are scoped integration
reasons, not a change to the repository's Python scripting preference.

Sources checked on 2026-09-06:
[Node releases](https://nodejs.org/en/download),
[TS7 native release](https://devblogs.microsoft.com/typescript/announcing-typescript-7-0/),
[Wrangler commands](https://developers.cloudflare.com/workers/wrangler/commands/general/),
[D1 bindings](https://developers.cloudflare.com/d1/worker-api/d1-database/),
[D1 limits](https://developers.cloudflare.com/d1/platform/limits/),
[Durable Object storage](https://developers.cloudflare.com/durable-objects/api/sqlite-storage-api/).
Exact package versions/dependency ranges were also checked against npm registry
metadata and the installed package/lockfile contents.

## HTTP client interoperability

The collector identifies itself truthfully as
`FlickrGroupAddr-RuntimePermissionProbe/0.0.0`. On 2026-09-06, Python's default
User-Agent received Cloudflare HTTP 403/error 1010 before the probe handler;
the application User-Agent reached the endpoint normally. No browser identity
was impersonated and no edge security setting was changed. The first hosted
attempt collected no permission cases and confirmed resource cleanup.
See [Cloudflare error 1010](https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-1xxx-errors/error-1010/).

The FGA LrC plug-in's actual documented networking client still needs its own
edge compatibility evidence in the routing and installation-read work. This
probe's HTTP client does not establish Lightroom Classic host compatibility.

Final credential review found that Wrangler's default debug logger mirrors
`auth token --json` output to disk. Three matching copies in this task's private
Wrangler log windows were redacted; unrelated logs and the canonical login
configuration were preserved. The controller now disables vendor disk logging
and retains sanitization, and a synthetic-token check verifies the logging
boundary. This was a local diagnostic-copy issue; the public probe evidence
contains no Cloudflare credential.

## Node LTS upgrade after probe closeout

On 2026-09-06, Terry requested the machine upgrade from Node 24.19.0 to
24.20.0 LTS. WinGet identified the existing MSI installation but had not yet
indexed 24.20.0, so the upgrade used the official
[Node 24.20.0 x64 MSI](https://nodejs.org/dist/v24.20.0/node-v24.20.0-x64.msi).
Its SHA2-256 matched Node's release manifest, and Windows verified a valid
OpenJS Foundation signature. Installer exit status was 0; no reboot was required.

Fresh processes reported Node `v24.20.0`, LTS name `Krypton`, and npm `12.0.2`.
The existing npm installation was retained. Native TS7 checking (`npm run check`)
and the local Wrangler dry-run build (`npm run probe:build`) passed. The earlier
local/hosted permission reports retain Node 24.19.0 as historical evidence;
no hosted permission probe was rerun for this toolchain-only update.
