# Project guidance

## Architecture authority

This repository implements the hosted side of FlickrGroupAddr. The canonical
architecture repository is `C:\Projects\FGA\architecture-design`. Read its
`AGENTS.md` before architecture or implementation work and use
`docs/README.md` there to resolve authority: repository guidance and explicit
owner directives come first, followed by accepted ADRs, then accepted scoped
contracts. Proposed ADRs, research, diagrams, and OpenAPI projections do not
independently authorize a production design.

The current hosted direction is recorded in architecture ADR 0050:

- Cloudflare is the selected hosted platform.
- Evaluate Durable Objects and D1 first for storage and coordination.
- AWS backing services, including RDS PostgreSQL and Secrets Manager, are
  acceptable fallbacks when Cloudflare-native services cannot satisfy an FGA
  requirement. Before choosing one, document the unmet requirement, native
  evidence, alternatives, identity and network boundary, cost, and operational
  tradeoff so Terry can understand the decision.
- Cloudflare selection does not waive atomic admission, durable ordering,
  dispatch markers, stale-worker fencing, permanent exact-pair suppression,
  backup/restore, authentication, or least-privilege requirements.
- Never assume one atomic transaction spans Durable Objects and D1. Assign each
  durable fact one explicit authority and prove all cross-service failure cases.
- Accepted ADR 0052 directs the paused native credential replacement proof
  before AWS; its availability tradeoff is approved and hosted conformance
  remains pending.

Terry approved [architecture ADR 0051](https://github.com/FlickrGroupAddr/architecture-design/blob/b6676de7e9af78d352344d720ca81b96e6d2e8c1/docs/decisions/0051-trust-private-storage-runtime-with-guarded-writes.md) on 2026-09-11.
For the private single-owner deployment, trust deployed native storage-owning
code not to dismantle its SQL guards. Broad D1/owning Durable Object schema or
erasure capability alone does not require RDS or a custom privilege service.
Keep guarded ordinary writes, parameterized fixed operations, permanent
suppression, append-only history, hostile-client checks, atomicity, fencing,
and backup/restore. This is a scoped runtime-isolation exception, not a waiver
of other least-privilege requirements or a production-storage conformance pass.
Revisit the trust model before public or multi-user operation.

Terry approved [architecture ADR 0052](https://github.com/FlickrGroupAddr/architecture-design/blob/abcb2d192063783400634aa50c736c1d0a6a523a/docs/decisions/0052-evaluate-paused-native-credential-replacement.md) on 2026-09-11.
The bar for adding AWS services is high. First evaluate a simpler native
implementation or owner-approved workflow; identify a concrete unmet
private-deployment requirement and why it matters, then compare the full
identity, network, recovery, cost, and maintenance burden. Missing a preferred
API or having a working AWS prototype does not establish need. Do not invent
elaborate native machinery to avoid an otherwise justified AWS fallback.
For Flickr credentials, evaluate one native token-pair bundle with an application
generation, durable pause during replacement, mismatch rejection, and repair
or relink after failure. The lack of provider version history alone does not
force AWS. This accepts the private availability tradeoff and synthetic proof
direction, not a native production conformance pass or broader safety waiver.

Terry approved architecture [ADR 0053](https://github.com/FlickrGroupAddr/architecture-design/blob/0cf54f37cd4c293a0b62d467b9a9394fea1a486c/docs/decisions/0053-accept-millisecond-private-database-clocks.md) and
[ADR 0054](https://github.com/FlickrGroupAddr/architecture-design/blob/0cf54f37cd4c293a0b62d467b9a9394fea1a486c/docs/decisions/0054-accept-early-duplicate-authorization-rejection.md) on 2026-09-11.
Database-generated persisted UTC times may use millisecond source resolution for
the private deployment. Six-digit formatting is not finer resolution; explicit
sequence/revision fields own durable ordering, and live monotonic preflight
timing is unchanged. The provider's early HTTP 400 for duplicate Authorization
fields may use its own non-JSON response without the application no-store or
Bearer challenge, subject to the bounded no-data/no-shell/no-redirect rules.
Application-generated authentication errors retain JSON/no-store and matching
Bearer codes. These decisions resolve the #0007/#0011 owner handoffs; they do
not require AWS or waive the remaining independent production gates.

The first planned end-to-end slice is a read-only validation of one FGA LrC
plug-in installation credential through the same-origin Cloudflare HTTPS edge,
the FGA API backend, and the selected durable store. It makes no Flickr call and
performs no protected mutation after fixture provisioning.

Accepted architecture ADR 0003 licenses original FGA source code and
documentation, including this hosted implementation, under the MIT License,
copyright 2026 Terry Ott. Terry reaffirmed this project-wide choice on
2026-09-06 and directed that this implementation repository be public. The
Localswim state-store repository remains private because its board content is
sensitive. Third-party components and separately licensed materials retain
their own terms and notices.

## TypeScript compiler

Terry made the TypeScript compiler requirement explicit on 2026-09-06: all
TypeScript code must use the latest stable TypeScript 7 release and its native
Go compiler. Verify the current stable 7.x version when adding or updating
TypeScript tooling, pin that exact version in `package.json` and the npm lockfile,
and use `npm ci` for reproducible installs. Do not substitute TypeScript 6, the
legacy JavaScript compiler, or a nightly/preview build. Run the pinned native
`tsc` as the required TypeScript validation gate before provider bundling.

Treat Cloudflare `compatibility_date` as a versioned dependency, as Terry directed
on 2026-09-06. Keep it current with the latest supported production date when
updating the Worker toolchain, review compatibility changes, and rerun the
TypeScript and affected local/hosted probe checks. Record any local emulator
lag separately; never present a local run as proof of a newer hosted runtime.

Use the latest Node.js LTS line, as Terry directed on 2026-09-06; prefer stable
dependencies and ordinary tooling. If a newer tool release requires a prerelease
dependency, prefer the newest stable dependency combination and document the
version tradeoff. Keep npm on a compatible stable release.

## Git workflow

Terry reaffirmed the standing order on 2026-09-12: "all commits and pushes are
approved at all times." This continues the 2026-09-06 authorization. Commit and
push validated, in-scope project work to the current branch without asking for
commit, push, or publication approval again, including pushes to this existing
public implementation repository. The authorization remains in effect across
turns and sessions unless Terry changes it. Preserve unrelated changes and keep
credentials and private data out of commits. This does not authorize
force-pushing, changing repository visibility, or publishing packages or
releases.

## Local swimlane board

When Terry asks to launch or open this project's localswim board, use these known
locations directly; do not search neighboring repositories to rediscover them.

- Board name: **FGA implementation**.
- Board file: `C:\Projects\localswim-state-store\flickgroupaddr\api-cloudflare-localswim.json`.
- Autopush destination: `https://github.com/TerryOtt/localswim-state-store.git`
  (private repository, verified 2026-09-06; this board is already tracked there).
- Browser URL: `http://127.0.0.1:8795/`.
- Health endpoint: `http://127.0.0.1:8795/api/v001/status`.
- Installed server: `C:\Users\TDO-XPS15-2024\.local\bin\localswim.exe`.
- Installed CLI: `C:\Users\TDO-XPS15-2024\.local\bin\localswim-cli.exe`.
- Server logs: `C:\Temp\api-cloudflare-localswim.out.log` and
  `C:\Temp\api-cloudflare-localswim.err.log`.

This is distinct from the architecture board, `fga-localswim.json`, and the
localswim project's own inception board. Use this implementation board here.

### Launch procedure

Terry requested project-local Codex lifecycle hooks on 2026-09-06. The normal
launch path is now `.codex/hooks.json`, which invokes
`scripts/localswim_session.py start` on `startup`, `resume`, and `clear`. Startup
and resume open the board in the default browser; clear only ensures health.
`SessionEnd` invokes `trigger-stop` with a three-second timeout; it starts a
hidden detached coordinator that uses `localswim-cli` for final autopush and
graceful shutdown. A failed final push must leave the service running and report
an error, never force termination. These hooks manage only the implementation
board. Do not import the sibling project's two-board/monitor scope here.

Use [docs/localswim-session-hooks.md](docs/localswim-session-hooks.md) for the
hook trust step, lifecycle handoff paths, failure recovery, and verification.
Repository Python tooling uses `uv run --frozen`; keep localswim itself installed
as a machine-level tool, outside this project's dependencies. The hook scripts
use Python; fixed PowerShell is limited to hidden server launch and opening the
browser. For a manual launch without the hook, use the procedure below.

1. Request the health endpoint with a short timeout. Reuse a service reporting
   `ok: true` with autopush enabled; never start a duplicate. If autopush is off,
   stop it gracefully with `localswim-cli <board-file> board shutdown`, wait for
   shutdown to finish, then relaunch with `--autopush`. If it responds with
   `ok: false` or reports a push failure, inspect the reported problem and logs
   before attempting recovery.
2. If no service is listening, start the installed server as a hidden background
   process using the command below. The board file supplies port 8795; no port
   override is needed. The required runtime service descriptor is outside this
   checkout, so startup may require execution outside the filesystem sandbox.
3. Poll the health endpoint until `ok: true`, confirm `push.state` reaches `ok`
   with `push.detail` reporting `repository synchronized` or `committed and
   pushed` after the initial push check, and check that the browser URL returns
   HTTP 200. If startup fails, inspect the logs instead of launching another copy.
4. Open the browser URL with `Start-Process 'http://127.0.0.1:8795/'`, then give
   Terry the clickable URL.

Run this startup command only after confirming the service is not already running:

```powershell
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUNBUFFERED = '1'
Start-Process `
    -FilePath 'C:\Users\TDO-XPS15-2024\.local\bin\localswim.exe' `
    -ArgumentList @('--autopush', 'C:\Projects\localswim-state-store\flickgroupaddr\api-cloudflare-localswim.json') `
    -WorkingDirectory 'C:\Projects\FGA\api-cloudflare' `
    -WindowStyle Hidden `
    -RedirectStandardOutput 'C:\Temp\api-cloudflare-localswim.out.log' `
    -RedirectStandardError 'C:\Temp\api-cloudflare-localswim.err.log'
```

Keep the service bound to loopback. Terry authorized autopush for this board on
2026-09-06: use `--autopush` by default so board snapshots are automatically
committed and pushed to the state-store repository's configured remote. This
authorization covers board snapshots. Opening the board does not authorize
moving cards or starting queued implementation work.
Use `localswim-cli` for board inspection and mutations; do not edit the board JSON
directly or print its runtime service descriptor, which contains a credential.
