# Initial disabled deployment

This document records the original deployment sequence. The current production
state is the later [read-only promotion](read-only-production-promotion.md):
administration and authenticated reads are enabled, while intake, dispatch and
both durable write gates remain paused.

The bootstrap implements the approved first persistent deployment after the
sixbucks domain move. It is an operator action, not a release-conformance pass.
The production dispatcher and all other application features remain disabled.

From the implementation repository, use:

```console
uv run --frozen python -m scripts.bootstrap_deployment
uv run --frozen python -m scripts.bootstrap_deployment --apply
```

The default command only plans. It verifies the approved account, active zone,
private input-file formats, current DNS inventory and resource-name availability.
The apply command creates `fga-api`, `fga-production`, `fga-managed` and the nine
bindings declared by `wrangler.example.jsonc`. It applies the production D1
migrations, runs native TypeScript validation, bundles once, records the optimized
Worker artifact's SHA2-256 digest and deploys that bundle on the custom domain.

The Flickr application credentials and the previously approved runtime writer
are loaded from their existing private files. A new random authentication-limiter
key is generated. The Flickr grant and five OAuth staging slots begin as retired
payloads containing no account authorization. The separate zone-read token is
used only by the local operator; it is never installed in the Worker.

All four feature flags must equal the string `0`; the bootstrap rejects an
edited template that enables one, changes the hostname, or enables workers.dev.
It refuses an existing unowned FGA Worker/database/store or preexisting DNS on a
first run. Its ignored journal records attempted creations before requests and
provider identities afterward, permitting a known interrupted bootstrap to
resume without resetting successful secret values. Once complete, the command
leaves that deployment alone; future application changes use ordinary reviewed
deployment work, not a fresh bootstrap.

The ignored `.coordination-runs/production/` directory contains the journal,
resolved configuration, optimized bundle and private command logs. Configuration
includes owner identifiers and must stay private. No credential or log contents
may be copied into public evidence. A failed bootstrap leaves its recorded
resources available for diagnosis/resume; it performs no broad cleanup or
unrelated resource deletion.

Verify the remote feature flags, migration head, Worker custom-domain binding,
and HTTPS behavior after deployment. Disabled API/admin endpoints should return
the application JSON 503 without a session cookie. Unknown paths remain JSON
404. No live Flickr call is part of this bootstrap. The initial disabled
responses do not constitute the owner browser smoke check or any of the full
production release/restore/mutation gates.

Validation for the initial implementation: seven bootstrap boundary checks,
102 existing Node backend tests, Ruff and Pyright passed; native TypeScript is
also required by the apply command before deployment.

## Deployed checkpoint - 2026-09-13

The bootstrap completed successfully. The domain resolves to the real
`fga-api` Worker; `fga-production` contains migrations through
`0012_protocol_repair_evidence.sql`. The schema matches the 36 current domain
tables plus retained D1 migration history. The initial 37-table quiescent D1
archive was restored and compared in a separate local SQLite database. This is
not a hosted restore/restart or post-backup reconciliation conformance result.

After disabled-edge verification, the same optimized artifact was deployed in
**administration-only** mode for the approved real owner browser check:

| Feature | Current value |
| --- | --- |
| `FGA_ADMIN_ENABLED` | `1` |
| `FGA_READ_ENABLED` | `0` |
| `FGA_INTAKE_ENABLED` | `0` |
| `FGA_DISPATCH_ENABLED` | `0` |

The remote settings were read back. `/admin/` redirects to `/admin/login`, the
login page returns HTML 200, anonymous session reads return JSON 401, disabled
installation reads return JSON 503, and the synthetic probe path returns JSON
404. Each checked response is no-store and creates no application session cookie.
See [sanitized evidence](../evidence/initial-deployment-2026-09-13.json).

The embedded-browser check displayed Google's sign-in control, but the provider
logged that the origin is not allowed for the supplied client ID; the button
also rendered without its expected sizing. The deployed client matches the
owner's supplied credential file. This does not prove the live Google Console
origin configuration or a page-policy cause. The next owner action is to open
`https://flickrgroupaddr.com/admin/` in regular Chrome, try Google sign-in, and
report success or the exact provider error. Do not repeat Cloudflare login,
rotate the supplied token, or blindly change Google settings in response.

Google's [integration guidance](https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid)
recommends a cross-origin referrer policy, while the accepted administrative
contract currently requires no-referrer. No referrer-policy exception has been
implemented or accepted. Two direct stylesheet diagnostics, with no referrer and
with only the FGA origin, both returned 403 and do not establish that changing
this policy will solve the browser failure. If policy is shown to be the cause,
prepare a narrow anonymous-login change against the canonical contract first.

No Google owner login or Flickr grant was completed by the agent, and no live
Flickr call was made. Full production conformance remains unfinished. Initial
configuration and archive files remain ignored; the completed bootstrap must
not be rerun as an ordinary deployment updater.

## Login repair follow-up

The owner reproduced the oversized control in Chrome and supplied its CSP
stylesheet error. The [Google button repair](../research/2026-09-13-google-button-style-fix.md)
is deployed for both login and reauthentication. The live control now renders
normally and its click reaches Google sign-in. Terry can refresh the login page
and complete the owner sign-in. Administration-only flags remain in effect.
The earlier embedded-browser origin warning persists but did not block that
redirect; no Google setting or referrer-policy change was made.

## Login health follow-up

The remaining Google origin error and Cloudflare analytics injection are now
resolved. The owner's Google settings were correct. Only the public, query-free
login page uses an origin-only referrer; protected pages and callbacks retain
no-referrer. Administrative HTML prevents intermediary script injection.
The live framed Google button renders without console errors and opens Google
sign-in. See the [verified correction](../research/2026-09-13-google-login-origin-fix.md). The next owner action is
to refresh the login page and complete sign-in; no Google Console edit is needed.
