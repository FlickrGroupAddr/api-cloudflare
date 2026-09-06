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
- The native secret-version question remains open for separate owner review.

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
