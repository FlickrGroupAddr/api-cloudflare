# Implementation-board session hooks

Added 2026-09-06 at Terry's request, following the sibling FGA
`architecture-design` project's start/exit pattern. These hooks operate only the
implementation board identified in [AGENTS.md](../AGENTS.md#local-swimlane-board).
They do not manage the architecture board, inception board, or their monitors.

## Enable and use

The hook definitions are in [`.codex/hooks.json`](../.codex/hooks.json). In a
trusted Codex project, use `/hooks` to review and trust both definitions once.
Changed definitions require another review. This is Codex's built-in trust
checkpoint; do not bypass it or write trust records programmatically.
[Official Codex hook documentation](https://learn.chatgpt.com/docs/hooks#review-and-trust-hooks)
describes discovery and review.

Start or resume a Codex session in this checkout to ensure the service is running
with autopush and open its browser page. A `clear` event also ensures the service
but does not open another tab. Use a clean `/exit` to initiate teardown. An abrupt
process kill or lost power cannot guarantee an exit hook. This is a session exit
hook, not a hook that stops the board after every assistant response.

Codex allows `SessionEnd` at most three seconds, so it launches a hidden detached
shutdown coordinator and returns promptly. The coordinator asks `localswim-cli`
to quiesce writes, complete final autopush, and remove its service descriptor.
The service remains running if final push fails. A later startup waits behind a
pending shutdown and the shared lifecycle lock before reusing or starting the
service. [Official lifecycle documentation](https://learn.chatgpt.com/docs/hooks)
explains the timeout and session events.

## Local tooling and manual commands

The hook definitions use this laptop's absolute checkout and installed `uv`
paths, so starting Codex in a subdirectory still works. The Python environment
uses the sibling project's installed CPython 3.14.7 and uv 0.12.5 conventions.
`pyproject.toml` and `uv.lock` own the tooling environment; localswim remains an
installed machine-level tool, not a project dependency. No hosted runtime choice
is implied by these development scripts.

Run from this repository:

```powershell
uv run --frozen --no-dev python scripts/localswim_session.py start
uv run --frozen --no-dev python scripts/localswim_session.py start --no-browser
uv run --frozen --no-dev python scripts/localswim_session.py trigger-stop
uv run --frozen --no-dev python scripts/localswim_session.py stop
```

`trigger-stop` returns immediately after launching cleanup. `stop` waits for
graceful cleanup and is useful for manual recovery. Both target the exact board
through the installed CLI; neither reads or prints its credential-bearing service
descriptor. Board content stays in the private state-store repository.

The launcher keeps orchestration and validation in Python. A fixed PowerShell
command uses `Start-Process -WindowStyle Hidden` for the service, with UTF-8
output, unbuffered logging, and `--autopush`. The exit coordinator uses Python's
native detached Windows process flags, matching the sibling's exit launcher and
avoiding a second shell startup within the three-second deadline. Browser launch
is deliberately visible.

The trusted [project configuration](../.codex/config.toml) supplies the
sandbox-writable system-temp uv cache. During the current session or from an
untrusted context where that configuration has not loaded, the equivalent is:

```powershell
$env:UV_CACHE_DIR = Join-Path $env:TEMP 'localswim-uv-cache'
```

Detached children explicitly use `C:\Temp\localswim-uv-cache`. Launch/shutdown
write runtime files outside the checkout and may require an approved invocation
outside the command sandbox. Keep those files outside Git.

## Health and recovery

Startup requires `ok: true`, `push.state: ok`, a push detail of
`repository synchronized` or `committed and pushed`, and HTTP 200 from the board
page. It reuses a healthy service. If autopush is off, it gracefully stops that
service and relaunches with autopush. A health error, failed push, timeout, or
malformed HTTP response does not authorize launching a duplicate.

All runtime paths below are in `C:\Temp`:

| File | Purpose |
| --- | --- |
| `api-cloudflare-localswim.out.log` / `.err.log` | Installed server logs |
| `api-cloudflare-localswim-session-hook-status.json` | Sanitized startup state: `starting`, `ready`, or `error` |
| `api-cloudflare-localswim-session-end-hook-status.json` | Sanitized shutdown state: `launching`, `stopping`, `stopped`, or `error` |
| `api-cloudflare-localswim-session-end.out.log` / `.err.log` | Detached coordinator and CLI shutdown logs |
| `api-cloudflare-localswim-session-lifecycle.lock` | Exclusive Windows byte-range lock for startup/shutdown |

Inspect the matching handoff and logs after a failure. Restore connectivity if
autopush failed, then retry `stop` to finish graceful shutdown, or `start` to reuse
a service whose health has recovered. Do not kill the service to work around a
failed push. If a crashed coordinator leaves a stale `launching` or `stopping`
handoff, inspect the logs and retry `stop`; its exclusive lock prevents overlap
with a coordinator still doing cleanup. Do not manually delete a live lock.

The board is shared by this checkout's sessions, as in the sibling project:
exiting one session initiates shutdown of this board even if another session is
open. Prefer one active session per board. Other projects' boards are unaffected.

## Verification

```powershell
uv run --frozen python -m unittest discover -s tests -v
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pyright
```

The tests cover service reuse, initial push readiness, disabled-autopush restart,
failed shutdown/push, refusal versus uncertain health, lifecycle exclusion,
detached exit, sanitized errors, and browser launch conditions. A live check uses
`start --no-browser`, `trigger-stop`, and `start --no-browser` again, observing
the handoff, synchronized status, and HTTP 200. End that check with the board
running for the current working session.

Verified on this laptop on 2026-09-06 with Codex CLI 0.153.4 (`hooks` enabled):
all 17 unit tests, Ruff checks/formatting, and Pyright passed. Live startup
launched a hidden service, reached synchronized autopush and HTTP 200, and a
second startup reused the same listening process. The exit command returned in
0.153 seconds; its detached coordinator then reported `stopped` and the loopback
listener was gone. A subsequent resume command from the `scripts` subdirectory
restarted the service, verified health, and opened the browser successfully.
The hook definitions still require the user's normal `/hooks` trust review;
these live checks invoked the configured script commands directly.

Two Windows details were confirmed during that check: this laptop takes about
two seconds to report loopback connection refusal, so the health probe allows
three seconds; and detached descendants can retain captured pipe handles, so
the PowerShell launch boundaries use `DEVNULL` while the server writes to its
explicit log files. The tests preserve both conditions.
