# Node and Workers toolchain inventory — 2026-10-16

Scope: this document first records the pre-change repository inventory against official Node.js, TypeScript, npm and Cloudflare sources checked on 2026-10-16. The baseline table remains historical; the applied selection and remaining qualification boundary are recorded below. The lockfile-only regeneration used the specifically assigned npm 12.2.0 command with lifecycle scripts disabled; no dependency installation, test, validation script, or deployment was run.

## Pre-change repository and local pins

| Component | Repository declaration / lock | Observed local runtime | Current stable source snapshot | Inventory |
|---|---|---|---|---|
| Node.js | `engines.node >=24`; GitHub CI pins `24.20.0` in `release-validation.yml` and `native-matrix-diagnostic.yml` | `v24.20.0` | Node 24.22.0 LTS, released 2026-10-14 | LTS major is correct; local and CI runtime are two patch releases behind the current 24.x LTS release. `engines` is a minimum, not an exact runtime pin. |
| npm | `packageManager: npm@12.0.2`; both above GitHub workflows install `npm@12.0.2` | `12.0.2` | npm 12.2.0 is the current `latest` | Local npm and CI agree with the repository's exact package-manager pin; pin is behind current stable npm. |
| TypeScript | `typescript: 7.0.2` in package.json and lock | Installed package metadata is 7.0.2 | npm `latest`: 7.0.2 | Exact current stable TypeScript 7 pin. Microsoft identifies TS7 as its native Go compiler; this is not TS6 or a preview. |
| Node declarations | `@types/node: 24.13.4` | Lock pin | Latest Node 24 line: 24.19.2; package-wide latest 26.6.5 | There is a newer stable declaration package for the project's Node 24 line. The package-wide latest is for Node 26, so do not blindly adopt that major when the approved runtime line is Node 24. |
| Cloudflare CLI | `wrangler: 4.116.0` | Lock pin | npm `latest`: 4.129.1 | Newer stable Wrangler exists, but the primary agent checked releases 4.117–4.129 and found they require Miniflare 5 alpha; the stable-only combo remains on 4.116.0 pending a stable compatible dependency set. Wrangler supports Current, Active, and Maintenance Node releases; Node 24 LTS is within its supported classes. |
| Cloudflare runtime declarations | `@cloudflare/workers-types: 5.20260906.1` | Lock pin | npm `latest`: 5.20261015.1 | Stable update candidate. Cloudflare now recommends generating types with `wrangler types` so declarations match a Worker's compatibility date and flags; this is a separate migration choice from a pin refresh. |
| Local simulator | `miniflare: 4.20260730.0` | Lock pin | npm stable `latest`: 4.20260730.0. 5.x is alpha/beta, not stable. | No newer stable Miniflare candidate found. Do not substitute its 5.x prerelease to chase a newer runtime. |
| Workers runtime engine | Transitive `workerd: 1.20260730.1`, locked beneath both Wrangler and Miniflare; platform binaries are also locked at 1.20260730.1. `package.json` allows its install script. | No version command run | npm `latest`: 1.20261015.1 | The checked-in local runtime is behind the current stable workerd release. Current stable Miniflare remains at the July version and its package metadata pins the same July workerd version; therefore, a newer stable Miniflare/workerd pair is not available from the stable Miniflare line in this snapshot. |
| Bundler | Transitive/direct dev dependency `esbuild: 0.28.1` (also explicitly allowed in `allowScripts`) | Lock pin | npm `latest`: 0.28.2 | Patch update candidate. |
| Worker compatibility date | `wrangler.example.jsonc: 2026-09-18`; runtime-permissions probe config: `2026-09-06` | N/A | Cloudflare says keep the date current; its current guidance example is 2026-10-13. Inventory date is 2026-10-16. | Both checked-in dates trail the research date. Treat a date advance as a runtime behavior change requiring compatibility-flag review and the repository's affected checks. Cloudflare's guidance does not say dates are invalid after a particular day; 2026-10-16 is the current-date candidate, not a claim that a release occurred on that date. |

Evidence in the checkout: `AGENTS.md`'s TypeScript compiler section requires latest stable TypeScript 7 with the native Go compiler, exact package/lock pins, latest Node LTS, compatible stable npm, current compatibility date, and separate reporting of emulator lag. `package.json`, `package-lock.json`, `tsconfig.json`, `wrangler.example.jsonc`, and `probes/runtime-permissions/wrangler.jsonc` contain the pins/configuration above. The lock shows Wrangler 4.116.0 itself depends on Miniflare 4.20260730.0, workerd 1.20260730.1, esbuild 0.28.1, and Workers types compatible with the 2026-07-30 release; the direct Workers-types pin is 2026-09-06.

## Applied selection and current qualification boundary

The owner selected a stable toolchain update that preserves the exact TypeScript 7 rule and avoids prerelease runtime components:

- Added `.node-version` with `24.22.0`, and moved both Windows GitHub workflows from Node 24.20.0 to 24.22.0. `package.json` still expresses the broad engine floor `>=24`; the file and CI supply the exact repository runtime pin.
- Advanced the exact npm package-manager pin and both CI npm installers from 12.0.2 to 12.2.0. Regenerated only `package-lock.json` using `npm exec --yes --package npm@12.2.0 -- npm install --package-lock-only --ignore-scripts`.
- Advanced `@types/node` to 24.19.2, matching the Node 24 line, and `@cloudflare/workers-types` to 5.20261015.1. TypeScript stays pinned at stable native-Go 7.0.2: the npm `latest` tag is 7.0.2, while `next` is the development build `7.1.0-dev.20261016.1`; no stable TypeScript 7.1.0 package was found. The npm `beta` tag remains `6.0.0-beta`, so a scheduled beta is not evidence of an actual 7.1 beta release. Microsoft describes a new/different API as expected in 7.1; the TypeScript release-plan issue targets an RC on 2026-11-10 and stable on 2026-11-24, which are plans, not guarantees.
- Kept Wrangler at 4.116.0 and Miniflare at stable 4.20260730.0. The primary agent checked Wrangler releases 4.117 through 4.129 and found those require Miniflare 5 alpha; those combinations do not meet the stable-dependency requirement. No Wrangler-forced `esbuild` override was added. The lock therefore continues to carry `workerd` 1.20260730.1 beneath the stable local toolchain while the registry has newer workerd releases. This local-runtime lag is explicit and unresolved.
- Advanced the example and runtime-permissions probe compatibility dates to 2026-10-16. This is a runtime behavior change requiring compatibility review and affected checks; it does not itself prove hosted compatibility. Production feature switches remain disabled, the example retains only its existing `nodejs_compat` flag, and no `enable_request_signal` flag was added.

Qualification is still open: this inventory did not install dependencies or run tests. The parent owns validation under actual Node 24.22.0, dependency installation, and the affected local/hosted runtime checks. The local emulator still uses the July workerd build, so its result cannot establish behavior for the October 16 hosted runtime. Revisit the Wrangler/Miniflare pair when a stable Wrangler release has a stable Miniflare dependency.
## Initial inventory candidate view (before integration selection)

- Refresh the local Node LTS patch to 24.22.0 where the toolchain runtime is managed. Keep Node 24 as the line unless the owner changes the Node-LTS requirement.
- Consider advancing the exact npm pin and local npm from 12.0.2 to stable 12.2.0.
- Keep TypeScript at 7.0.2: it already satisfies the explicit stable TS7/native-Go rule. Do not replace it with TS6 or a `next`/nightly/preview build.
- Consider updating `@types/node` within the 24.x line to 24.19.2 alongside the runtime; the newest cross-major `@types/node` package (26.6.5) is not the matching declaration line for Node 24.
- The initial snapshot flagged Wrangler 4.129.1 as newer; the primary agent's later release-graph check withdrew it as a stable-only candidate because Wrangler 4.117–4.129 requires Miniflare 5 alpha. Workers types 5.20261015.1 was selected. esbuild 0.28.2 was not forced because Wrangler remains pinned at 4.116.0.
- Keep Miniflare at its stable 4.x version unless a later stable 4.x is published. Its 5.x tags shown by npm are prerelease. The stable Miniflare package has no matching October workerd refresh, so local emulator lag remains a known limitation even if the CLI/type packages move forward.
- If moving compatibility dates toward 2026-10-16, review Cloudflare compatibility flags and run the pinned native `tsc` plus affected local/hosted checks as the repository guidance requires. A local emulator run cannot establish behavior for runtime dates or workerd builds that the installed emulator does not contain.

## Sources (official primary sources, checked 2026-10-16)

- Repository requirements and pins: [AGENTS.md](../../AGENTS.md), [package.json](../../package.json), [package-lock.json](../../package-lock.json), [.node-version](../../.node-version), [release-validation workflow](../../.github/workflows/release-validation.yml), [native-matrix-diagnostic workflow](../../.github/workflows/native-matrix-diagnostic.yml), [wrangler.example.jsonc](../../wrangler.example.jsonc), [runtime-permissions wrangler config](../../probes/runtime-permissions/wrangler.jsonc).
- Node LTS line and dated release: [Node.js release schedule](https://nodejs.org/en/about/previous-releases), [Node.js 24.22.0 release (2026-10-14)](https://nodejs.org/en/blog/release/v24.22.0).
- npm stable version: [npm 12.2.0 package/version page](https://www.npmjs.com/package/npm?activeTab=versions), [npm CLI docs (12.2.0 latest)](https://docs.npmjs.com/cli-commands/npm/).
- Native compiler architecture and stable release: [Microsoft TypeScript 7.0 announcement](https://devblogs.microsoft.com/typescript/announcing-typescript-7-0/), [TypeScript npm versions and dist-tags](https://www.npmjs.com/package/typescript?activeTab=versions), [TypeScript 7.1 release plan](https://github.com/microsoft/TypeScript/issues/63703).
- Cloudflare tool versions: [Wrangler npm versions](https://www.npmjs.com/package/wrangler?activeTab=versions), [Workers types npm versions and guidance](https://www.npmjs.com/package/%40cloudflare/workers-types?activeTab=versions), [Miniflare npm stable/prerelease tags](https://www.npmjs.com/package/miniflare?activeTab=versions), [workerd npm versions](https://www.npmjs.com/package/workerd?activeTab=versions), [esbuild npm versions](https://www.npmjs.com/package/esbuild?activeTab=versions).
- Node declaration versions: [@types/node npm versions](https://www.npmjs.com/package/%40types/node?activeTab=versions).
- Cloudflare runtime-date guidance: [Compatibility dates](https://developers.cloudflare.com/workers/configuration/compatibility-dates/), [Workers best practices, updated 2026-10-12](https://developers.cloudflare.com/workers/best-practices/workers-best-practices/).

A registry's stable `latest` tag is distinguished from prerelease tags where visible. Search/source snapshots can change after the research date; the versions above describe the sources as observed for this inventory, not a permanent registry assertion.

## Primary integration and stable development-dependency patches

The primary verified the official Node 24.22.0 Windows archive against its
published SHA2-256 checksum and used a portable runtime for locked installation,
native TypeScript checking, generated API verification and 218 runtime tests,
all passing. This did not replace the machine-wide Node installation.

The initial locked install's npm audit reported four high-severity entries in
the development-only Miniflare/Wrangler chain: sharp 0.35.2 and undici 7.28.0,
plus their parent packages. Miniflare pins those vulnerable versions exactly.
The primary selected standard npm overrides for stable sharp 0.35.5 and undici
7.29.1, staying within their existing minor/major API lines respectively. No
alpha/beta Miniflare or forced Wrangler major/runtime override was adopted.
This is a scoped patch to development dependencies, not a production vulnerability
claim. Locked reinstall, affected regressions and a fresh audit must verify the
result before handoff. Registry/advisory provenance: npm audit metadata and
official https://registry.npmjs.org/sharp and https://registry.npmjs.org/undici.

Final scoped patch verification: locked installation under Node 24.22.0 with
npm 12.2.0 completed and npm audit reported zero vulnerabilities. Native TS7.0.2
type checking and all 218 runtime tests passed after both overrides. The combined
Python/Lua suite passed 341 tests; generated API validation, Ruff, Pyright and
Adobe SDK15.3 compilation passed for their affected scopes. Hosted October runtime
qualification remains separate; the July emulator was not relabeled or upgraded
to a prerelease. The portable Node runtime is task-local; default machine Node
remains 24.20.0, while CI and .node-version select 24.22.0.
