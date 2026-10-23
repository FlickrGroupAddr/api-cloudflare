# Prospective integer PMB-1 candidate source assembly

This NEW unregistered candidate selects `pmb1-private-application-no-real-v1`
under accepted ADR0065 and the explicit prospective consumer selection. It
composes the existing main-entry admission/drain bridge, complete partition
worker/maintenance bridge, native wake controls and complete no-REAL reader.
It introduces no provider API, active Worker registration or migration.

`candidate.ts:compose` supplies one fetch/scheduled composition and its partition
class. The caller must provide the existing trusted durable journal/independent
observer, explicit Flickr transport, disposition and reconciliation ports.
There is no default network transport or synthetic production implementation.
The journal belongs outside every compared store. Supplying ports is not proof
that they are durable, independently complete or qualified.

The single fetch entry gives only canonical `GET
/api/v001/installations/current` its intrinsic read capability. It calls the
unchanged ordinary worker, registry, authentication and D1 lookup. The capability
allows the exact `LOOKUP_SQL` and ordinary `bind(...).first()` only. It preserves
the read feature gate, request/body/query/authentication refusals, ordinary result
and security headers. A future lookup write or other SQL cannot silently succeed.
All other paths/methods and scheduled handlers use the existing maintenance bridge;
the partition class always requires its maintenance bridge. No required mutation
or safety settlement is omitted to obtain success. The read exception creates no
closure authority and must be exercised inside a separately proved closed interval.

## Exact declared domain

- The D1 source fixture applies all 26 historical migrations to a NEW isolated
  in-memory database, explicitly overlays the accepted integer quota schema,
  installs the existing singleton control, and derives guards over every table.
  It includes 65 tables, all columns/generated cells, hidden identities, ordinary
  maintenance guards and the new post-affinity no-REAL guards. Historical
  migrations, balances, snapshots and artifacts are unchanged.
- The object fixture invokes actual `bootstrapPartitionMaintenance`, including
  its six SQL tables, full schema/guards, admission/revision/sequence KV keys,
  wake value/results and alarm. It is the partition source domain, rather than
  the earlier two-table object probe. Complete KV is read; no object exemption
  exists. The reader uses the existing wake admission sequence and observes a
  null alarm, required by actual close. No legacy alarm marker is written.
  A pending native wake alarm refuses this closed profile instead of being
  converted into the older structured-marker format.
- Store and guard manifests include full exact SQL definitions and cells.
  Source inventory covers all `src` modules and their local runtime imports,
  complete migrations, accepted reader/control modules and their local Python
  dependencies, configuration, pinned packages/lockfile and this assembly.
  Effect-line locations aid review; they do not establish an actual writer census.
- The actual D1/provider metadata, complete namespace population, resources,
  immutable versions and current configuration are unknown. Manifest nulls are
  explicit missing actual inputs. An unexpected table, provider backing table or
  metadata difference requires full discovery/review; it is never ignored to
  match the fixture. The separate `d1-profile-fixture.json` explicitly emulates
  provider metadata with one SYNTHETIC `_cf_KV` table solely to exercise the
  existing reader's accepted exact-manifest content exclusion. Its full observable
  metadata and all 65 application tables are bound; excluded contents stay
  unobserved, unfrozen and unverified. This invented local test table is never
  presented as actual D1 metadata. The complete D1 reader/transport source test
  uses that profile, checks all tables against an independent direct SQLite
  reference, and never requests the excluded contents.

`d1-schema.sql` and `object-schema.sql` are local construction fixtures. In
particular, the integer overlay's DROP statements are allowed only because the
assembler itself constructs a NEW in-memory database. Neither file is an
installable actual schema transition or an E/R/X procedure. No database path or
private state input is accepted by the assembler.

## Reproduction and evidence

Use the already installed pinned Node 24.22.0, native TypeScript 7.0.2 and uv
0.12.5/Python 3.14.7 environment. No dependency sync, upgrade or network is needed.
From the repository root, with the existing pinned executables on PATH:

```text
uv run --frozen --no-sync python probes/pmb1-integer-candidate/assemble.py --write
uv run --frozen --no-sync python probes/pmb1-integer-candidate/assemble.py
node_modules/@typescript/typescript-win32-x64/lib/tsc.exe -p probes/pmb1-integer-candidate/tsconfig.json --noEmit
node --test probes/pmb1-integer-candidate/candidate.test.mjs
uv run --frozen --no-sync python -m unittest discover -s probes/pmb1-integer-candidate -p test_*.py
uv run --frozen --no-sync python probes/pmb1-integer-candidate/build.py --out <new-private-evidence-directory>
```

`--node` selects an existing Node executable when PATH points elsewhere. The
assembler refuses a Node version other than the existing pinned 24.22.0. Default
mode recomputes and verifies all generated bytes; `--write` explicitly regenerates
the local artifacts. UTF-8/LF output is reproducible. Python owns source inventory,
schema/guard composition and pin checks because that is the repository's normal
maintainable scripting language. The tiny JavaScript fixture imports TypeScript
under Node to execute the existing object bootstrap, avoiding a parallel schema
implementation. TypeScript owns the existing Worker/runtime integration.

`build.py` verifies all generated source bytes, runs the actual pinned native
compiler check, then emits the complete imported ESM source module tree with
rewritten `.js` relative imports. It writes exact compiled-module, source,
toolchain and package-lock receipts to a NEW private evidence directory. Existing
npm dependencies remain external and locked. The entry exports the composition
factory; it is unregistered and has no default handler with invented durable
ports. This is a source build, not a provider-compatible bundle. The existing
Google-auth/CommonJS and node builtin graph requires the normal Workers
`nodejs_compat` packaging; a plain esbuild browser build cannot provide it. No
custom compatibility shim, Worker configuration, provider command or
deployed/immutable version is produced.

Synthetic integration checks the actual ordinary authenticated success and
negative responses, complete frozen D1/SQL/KV/alarm equality, stopped route and
schedule admission, stale partition fetch/alarm refusal, full six-table reader
fit, exact source pins and immutable nonforced target request construction.
The restoration helper constructs only the exact `force=false` request. It
neither executes nor acknowledges restoration, and never rebuilds rollback bytes.

Native compilation/build and synthetic tests establish source behavior only.
There is no actual qualified durable main-entry journal/observer adapter,
complete supported object namespace enumeration/custody adapter, independently
qualified managed SQL/KV/alarm source oracle, current binding census, actual
schema/guard installation, immutable retained target, common interval, allocation
or positive PMB-1 result. Actual API transaction/reader effects, old-version and
provider/CI/operator writer disposition, alarm delivery, stop/restart, nonforced
restoration, independent equality and later reopening remain separate gates.
Source acceptance cannot pass actual all-store qualification.

The complete D1 source integration uses explicit no-REAL-only local bounds of
2 MiB for plan/consent/CLI input and 512 KiB per response. Historical/default
profiles retain 1 MiB input and 256 KiB response bounds. The existing 16 MiB
aggregate and 2,048-query ceilings remain. These are finite SOURCE admission
limits, not new actual campaign budgets, run slots, capture allowances or
credential/dispatch authority. Oversize input/response limits refuse before
credential delivery or transport. `prospective_control.py` supplies a trusted
construction-time local byte descriptor to the existing finite D1 adapter; the
old default verifies its original pins unchanged. Fixed SQL, journal/latch,
single dispatch, readback, reconciliation and finite lifecycle remain shared.
