# Disposable Worker-to-Secrets-Manager proof

Date: 2026-09-07

Status: Terry approved disposable synthetic AWS testing. The signed transport,
authenticated Worker, Python controller, and SQLite lifecycle model are now
implemented. Production adoption, unattended identity, and production-store
conformance remain unaccepted. See the [hosted evidence](../../docs/research/2026-09-07-secret-store-proof.md)
for actual results and incomplete gates; passing local tests does not establish
provider behavior.

The [decision review](../../docs/research/2026-09-07-flickr-credential-store-decision.md)
links the controlling accepted ADR 0017 and OAuth lifecycle contract.

## Local validation

```console
npm ci
npm run check
npm run secrets:test
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pyright
uv run --frozen python -m unittest discover -s tests
npm run routes:test
```

The protocol and signing tests use fixed synthetic credentials and scripted
responses. The runtime regression test compiles with the pinned native
TypeScript 7 compiler before Wrangler bundling, then executes the bundled
Worker in Miniflare with all external requests intercepted. It uses local
compatibility date `2026-07-30`, matching the installed workerd release;
the hosted proof uses `2026-09-07`. The local result cannot prove that newer
hosted runtime. Temporary test bundles are written under the system-temp root.

TypeScript implements the code that executes inside the Cloudflare Worker.
Node is necessary for Miniflare's programmatic API and supplies the native test
runner; credential handling, orchestration, persistence, and cleanup use Python
with `uv run --frozen`. The only new dependency is exact-pinned `aws4fetch`
1.0.20 (MIT), used only for signing; its fetch/retry implementation is not used.
The existing development-tool advisories and stable-version tradeoff remain
[recorded separately](../../docs/research/2026-09-07-worker-routing-proof.md).

## Identity and hosted execution

The current machine uses the AWS CLI in WSL Ubuntu at
`/home/tdo/.local/bin/aws`, with named profile `fga-proof`. That profile uses
AWS's browser-based `login_session` flow for IAM user `fga-proof-operator`.
It is not an STS `AssumeRole` implementation. The AWS CLI refreshes temporary
credentials within the login session; exporting one snapshot into a Worker
does not give the Worker automatic renewal. The controller checks the exact
caller account/user and requires at least ten minutes of credential lifetime
before deploying. No long-lived access key is installed by this controller.
[AWS CLI login and refresh](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sign-in.html).

The pre-existing identity must have create, describe, exact-value read and
delete permission for the disposable `fga-proof/` namespace in `us-east-2`.
The current harness expects `PutSecretValue` to be denied. Identity naming and
local namespace checks do not prove all IAM restrictions. The controller does
not create identities, edit policies, or install broader permissions.

With that scoped local login established, run from this repository:

```console
uv run --frozen python scripts/secret_store_probe.py run --account <approved-account-id> --profile fga-proof
```

The account ID is an identifier, not a credential. Never put AWS credential
values into chat, command-line arguments, evidence, or this repository.
If the AWS login has expired, renew it locally through the existing AWS CLI
browser flow. If a valid cached credential has less than ten minutes left,
retry after the CLI refreshes it; the preflight leaves no hosted resource.

Each run checkpoints `.secret-runs/rp-<24-hex>/manifest.json` and
`lifecycle.sqlite` before any secret creation. The generated namespace is
`fga-proof/<24-hex>/<UUID>`; values contain only a fixed synthetic marker and
the generation UUID. No input accepts real Flickr tokens. This namespace and
the run IDs are not authentication.

The isolated Worker requires a random bearer token and has a one-hour fixture
TTL. The controller sends the bearer and temporary AWS credential snapshot
to Wrangler's secret-binding command over standard input and retains neither
its output nor credentials on disk. The AWS login cache remains outside the
checkout. Request signing permits only the fixed regional HTTPS endpoint.
Manual redirect mode plus explicit rejection prevents forwarding signed
credentials; workerd rejects `redirect: "error"` before sending a request.
The AWS request/body deadline is ten seconds, and client replies are bounded
to 16 KiB. There is no implicit write retry or current-version fallback.
[Cloudflare redirect behavior](https://developers.cloudflare.com/workers/runtime-apis/request/),
[aws4fetch signing API](https://github.com/mhart/aws4fetch).

The controller checks unauthorized access, creates two generations, resolves
their exact immutable versions, models their successive activation, reads each
repeatedly, tests wrong-version/write-denial/invalid-session failures, and
requests deletion of the replaced generation from the Worker. It hashes source
and bundle, checks response build identity and cache policy, and compares the
hosted deployment before and after the case sequence. Timings include each
action's reconciliation requests; they are not individual GetSecretValue
latencies or independently classified cold/warm measurements.

## Cleanup and recovery

Every exit attempts cleanup. The controller first removes authority durably
in the disposable SQLite model, validates each attempted generation, and only
then requests irreversible whole-object deletion of its synthetic fixtures.
Deletion acknowledgement is not completion: both metadata and exact-version
reads must report not-found three times, separated by two seconds. Denial,
expiry, timeout, and generic failure never prove absence. These bounded
observations are evidence of convergence, not an AWS consistency guarantee.

A lost create response retains the generated name/version for reconciliation.
Cleanup validates the described name, version membership, and full ARN before
deleting. A failed AWS cleanup still attempts to remove the exact isolated
Worker and its bindings. A failed or interrupted cleanup retains its checkpoint;
resume only that recorded run:

```console
uv run --frozen python scripts/secret_store_probe.py cleanup --run-directory .secret-runs/rp-<24-hex>
```

Retain the ignored run directory until cleanup is confirmed. Never substitute
an existing secret or Worker into a run manifest. The cleanup command updates
the manifest; an earlier report remains the original execution result.
Failure reports retain sanitized failure categories and source identity.
Private manifests/logs are not public evidence; publish only reviewed,
minimized results.

The SQLite model exercises competing replacements, stale-revision rejection,
reopening after a lost activation response, and authority removal before
cleanup. It is not the production FGA database adapter, complete link state
machine, audit implementation, or a transaction spanning SQLite and AWS.

Remaining acceptance work belongs to implementation ticket #0009: separate
reader/lifecycle identities and complete actual IAM denial checks; hosted
outage/throttling and crash/recovery injection; orphan and restored-database
reconciliation against the selected production store; repeatable cold/warm
latency; and unattended credential replacement/renewal. The controller's
bounded synthetic case result does not accept those production gates.
