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

## Approved managed D1 engine provenance

Terry accepted architecture ADR0058 on 2026-09-14. For the private single-owner
D1 deployment, record an explicitly undisclosed SQLite-library version with a
fresh remote query refusal when the provider does not expose it. Keep the
provider generation tag separate, record schema/artifact/configuration and
pinned tooling/adapter provenance, and retain the full behavioral, mutation,
stop/restart, restore/reconciliation and CI gates. This is a metadata exception;
it does not pass conformance, enable group additions, or justify an AWS move.
The canonical details are in the accepted architecture test contract and
`docs/decisions/0058-record-managed-d1-engine-provenance.md`.

## Accepted backup baseline

Terry resolved the backup investigation on 2026-09-14: daily backup coverage is
sufficient for this private project. Use D1 automatic Time Travel to meet that
frequency requirement; a separate scheduled daily export is not required. The
current-schema hosted restore and post-backup reconciliation checks remain
release requirements. See `docs/operations/d1-backup-and-recovery.md` for the
implemented baseline, provider retention and outstanding validation.

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

## UI typography and loading preference

Terry specified on 2026-09-14 that he likes **Inter** for the FGA UI and values
avoiding visible font-swap/redraw flicker during initial loading. The desired
result is the preference; he explicitly did not prescribe the implementation
suggested by another model in the ItineraryWatch example. Choose an appropriate
loading strategy during UI work rather than copying that implementation by
rote. Keep the existing CSP and private credential-transfer boundaries intact.
See [the typography note](docs/ui-preferences.md) for the reference and findings.

## Lightroom Classic client versioning

Terry directed on 2026-09-15 that production Lightroom client builds are tied
to the Lightroom Classic major version against which they are qualified. Name
the Lightroom 15 client and bundle `FGA-LrC15` / `FGA-LrC15.lrplugin`, and use a
major-specific toolkit identifier so separately qualified clients do not
silently replace one another. A build may happen to load under a later major,
but do not claim or assume support across Lightroom Classic 16, 17, 18, or any
other major until that combination has its own review and test evidence. Each
major qualification must include a fresh review of the documented Lightroom
SDK capabilities because they may materially change, including security-
relevant facilities such as a cryptographic random-number generator.

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

## Ticket priority default

Terry clarified on 2026-10-16 that **P3 (Normal)** is the default for FGA tickets,
superseding the earlier P2 instruction. Use higher priority only for concrete
urgency, impact, deadlines or explicit direction; blocking other tickets alone
does not justify a higher priority. Keep dependency links and ordering explicit.
The current priority reset applies only to open cards. Leave Completed cards'
priorities, contents and histories unchanged by this correction.

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

### Board-write alert preference

Terry's standing preference, stated 2026-09-19, is that changes authored only by
`bot` must not queue a next-turn alert or cause a redundant board inspection.
When monitoring this board, use the shared `localswim-monitor` command from
`C:\Projects\localswim` with its optional `monitor` extra, this board's path,
port 8795 and the existing board-specific status/target/lock paths. Do not copy
filtering logic into this project. Preserve other boards' target threads when
upgrading their monitors. It queries sanitized `localswim-cli activity between
--json` metadata after the quiet window; it alerts for Terry, other actors, or
empty/failed/malformed or unknown-actor activity and suppresses nonempty
bot-only results regardless of filesystem write count. Filesystem notifications
and activity events are not one-to-one; count mismatch alone must not alert.
Never read card prose inside the monitor. If an old-style alert is already queued,
check its activity bounds; when every event is by `bot`, no further card inspection
is needed. This preference applies in future sessions as well as this one.

## Lightroom native automation

For LrC host tests, read the installed computer-use skill and follow
`docs/operations/lightroom-automation.md`. Use the supported Node REPL / sky API
with `scripts/lightroom_automation.mjs` to launch once or reuse a returned window.
Startup can falsely report no targetable window even when Lightroom has started;
re-enumerate and rehydrate before deciding to launch or repeat an input. Preserve
intentional Escape stops; never bypass them with resets or another automation
route. Observe after each action and keep screenshot payloads, catalog names,
photo metadata and credentials out of tracked evidence. Launcher success does
not replace each workflow's fixture, consent, and release qualification gates.

## Codex agent configuration

Terry approved this task-based model and effort policy on 2026-10-15:

- Parent default and ordinary implementation/test subagents: GPT-6.1 Sol
  (`gpt-6.1-sol`) with Medium reasoning (`medium`).
- Authentication, SQL transactions, recovery and concurrency review:
  GPT-6.1 Sol with High reasoning (`high`).
- Narrow mechanical documentation edits, file inventories and prescribed test
  execution: GPT-6 Luna (`gpt-6-luna`) with Low reasoning (`low`). Keep code
  interpretation, safety conclusions and integration with a Sol agent.
- Particularly difficult debugging, design or architecture problems: GPT-6
  Astra (`gpt-6-astra`) with Medium reasoning (`medium`) is an option only
  after Terry explicitly approves using one or more Astra subagents for that
  turn. Ask again on each later turn that would use Astra; prior approval
  does not carry forward. Terry added this requirement on 2026-10-15.

These role-based choices supersede the earlier requirement that every subagent
use Sol Medium. A typical eight-agent batch may use five Sol Medium, one Sol
High and two Luna Low, but assign by actual work rather than filling a quota.
Do not escalate effort or model indiscriminately; the primary owns integration,
required verification, commits/pushes and truthful handoff.

Terry clarified on 2026-10-15 that the mix of models and reasoning efforts may
vary each turn. Reassess the complexity of each agent's task for that turn;
there is no fixed distribution or permanent per-agent model assignment. Select
GPT-6 Luna Low (called Light), GPT-6.1 Sol Medium or GPT-6.1 Sol High as appropriate
to the authorized work. Use a freshly configured agent when an existing one
cannot be retuned, preserving the eight-active-direct-subagent/depth-1 limits.

Use Standard speed for the parent and all subagents. Subagents inherit the root
session's service tier. Keep `service_tier = "default"` in the user Codex
configuration; do not re-enable Fast mode unless Terry requests it. Terry
confirmed switching the active session to Standard on 2026-10-15.

## Subagents on authorized tickets

Terry's preferred workflow, clarified on 2026-10-16, is a rolling implementation
and review pipeline. Use available subagent slots for eligible implementation
work first. As an implementation agent finishes, use the freed slot for a
fresh independent reviewer at the model/effort appropriate to that review.
Do not reserve fixed developer/reviewer pairs that leave reviewers idle while
implementation runs. Independent review remains required before handoff; the
author must not review its own work. Route findings back for correction and
re-review material changes. Keep within the current concurrency/depth limits
and retain the parent's integration and verification responsibilities.

Terry authorizes practical parallel work on authorized tickets: one primary
agent plus up to eight concurrently active direct subagents, nine total active
agents, maximum depth 1. Subagents must not spawn subagents. Eight is a ceiling,
not a quota. Separate independent implementation, verification, documentation
and review when useful. No separate per-ticket delegation approval is needed;
this does not authorize other tickets or unrelated work.

Always specify both the selected model and reasoning effort explicitly in
every subagent spawn call. Also identify that model/effort pair in the
user-facing delegation update so Terry can see the choice; do not rely on
defaults, inheritance or a model name without its effort level. Terry
reaffirmed this requirement on 2026-10-15.

Set the chosen model and effort explicitly when spawning. Use a fresh context
when required for overrides and supply the task, authority, file ownership,
constraints and handoff criteria. Preserve unrelated work and avoid conflicting
edits; keep desktop input under one primary operator.

## Parent/subagent communication

Terry requires aggressively summarized messages in both directions between all
subagents and their parent, including progress updates and final reports, to limit
token usage (2026-10-15). No raw data may pass from a subagent to its parent:
no raw logs, tool output, datasets, transcripts, source dumps or full diffs.

Report only the outcome, material findings or blockers, verification summary and
concise file/line references. Keep detailed evidence in appropriate files and send
references so the parent can inspect it directly when needed. Parent instructions
should likewise be compact and reference shared files instead of pasting data.

## Subagent model display

Terry revised the preferred user-facing format on 2026-10-16 to
`[version, only when not the latest release of that family] [model family] / [effort level]`.
Omit the version for the latest release of a model family; include it for older
releases. At this update, Sol's latest release is 6.1, so `Sol / Medium` means
6.1 Sol, while `6 Sol / XHigh` and `5.6 Sol / Medium` identify older releases.
For the current permitted latest-family choices, use `Luna / Light`,
`Sol / Medium`, `Sol / High`, and, only when approved for that turn,
`Astra / Medium`. Reassess the latest-family mapping when releases change;
do not assume the 6.1 Sol mapping remains current forever.

Use spaces around `/`. Render API effort `low` as `Light` and `xhigh` as
`XHigh`; always display the family and effort in delegation updates. This
presentation rule and its examples do not authorize additional models or
effort levels, change per-turn Astra approval, or remove the requirement to
pass full explicit model and reasoning-effort identifiers in every spawn call.
