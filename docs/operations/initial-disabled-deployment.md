# Initial disabled deployment

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

Validation for the initial implementation: six bootstrap boundary checks,
102 existing Node backend tests, Ruff and Pyright passed; native TypeScript is
also required by the apply command before deployment.
