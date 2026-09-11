# Worker-to-AWS synthetic secret proof

Date: 2026-09-07

Status: The bounded synthetic integration passes, with cleanup confirmed.
Production adoption, unattended AWS identity, complete IAM separation, and
production-database conformance remain open on implementation ticket #0009.
This is evidence under the [credential-store recommendation](2026-09-07-flickr-credential-store-decision.md),
not acceptance of that production design.

Current direction update, 2026-09-11: [ADR 0052](https://github.com/FlickrGroupAddr/architecture-design/blob/abcb2d192063783400634aa50c736c1d0a6a523a/docs/decisions/0052-evaluate-paused-native-credential-replacement.md) accepts
the private pause/repair tradeoff and directs native credential replacement
proof before AWS adoption. The results below remain unchanged; remaining AWS
production work is conditional fallback work, not the next default task.

## What was recovered and completed

The resumed checkout contained uncommitted signing transport, Worker,
controller, and lifecycle model code beyond commit `5cdb151`. An inherited
hosted run had passed the unauthorized-request check, failed on first creation
with HTTP 502 and generic `probe_failure`, and confirmed cleanup. The prior
README still described local-only preparation. The committed
[procedure](../../probes/secrets/README.md) now describes the actual implementation.

The existing local AWS CLI profile uses browser-login temporary credentials
for the dedicated proof IAM user. The controller exports one short-lived
credential snapshot privately into the isolated Worker's secret bindings and
signs regional Secrets Manager requests with `aws4fetch`. There is no
`AssumeRole` call, persistent production access key, or unattended renewal
implementation. AWS documents automatic local CLI refresh within the browser
login session; that mechanism does not run inside the Worker.
[AWS CLI login](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sign-in.html),
[signing API](https://github.com/mhart/aws4fetch).

## Defects and failed runs retained

The new bundled-runtime regression reproduced HTTP 502 before any AWS request:
local workerd throws a TypeError when constructing `redirect: "error"`.
Node's Request implementation accepted it, so the previous tests missed the
runtime mismatch. This reproduces a cause consistent with the inherited
failure; the inherited generic error alone does not prove its precise cause.

The client and signing transport now use `manual` redirect mode and explicitly
reject redirect responses without following their destination. A regression
checks that signed credentials cannot follow a redirect. Cloudflare documents
manual mode for implementing a redirect policy and warns that automatic
following can forward authorization headers to another host. The documentation
also lists `error`, so the observed workerd rejection is retained separately
from the documented surface.
[Cloudflare Request API](https://developers.cloudflare.com/workers/runtime-apis/request/).

A retry failed while Cloudflare enabled the uploaded Worker's hostname (API
code 10013). Another stopped before deployment because the temporary credential
had less than the required ten minutes remaining. A later run received a
non-JSON edge 404 on creation after GET readiness had passed. None of those
runs is a Secrets Manager capability pass. All confirmed cleanup.

The controller now checks authenticated GET and a mutation-free POST through
the actual probe path before starting resource operations. Failure reports
retain sanitized error categories and source/build evidence rather than only
an empty failed result. Unknown remote error strings are discarded.
No failed write is silently replayed; attempted fixtures are reconciled through
the original checkpoint and cleaned up.

## Hosted result

The final run `rp-9b06497e3995a003b6f2293d` passed all **14 cases** using hosted
compatibility date `2026-09-07` and Secrets Manager in `us-east-2`. The source
hashes still matched the checkout when evidence was exported, the bundle had
its own SHA2-256 digest, responses carried the expected build identity and
`no-store`, and the hosted deployment was unchanged across the case sequence.
The [sanitized machine-readable evidence](2026-09-07-secret-store-evidence.json)
retains the final result and earlier failures without account identifiers,
secret ARNs/values, AWS credentials, bearer tokens, or deployment author details.

| Check | Observed result |
| --- | --- |
| Unauthorized Worker request | Rejected with HTTP 401. |
| Two generated secret objects | Worker created both with fixed synthetic-only payloads and retained UUID version IDs. |
| Exact version access | Each object was recovered and read repeatedly by full ARN and exact version. |
| Wrong version | Both returned `ResourceNotFoundException`; no current-label fallback. |
| Disallowed new-version write | Both returned `AccessDeniedException` for `PutSecretValue`. |
| Invalid session token | Both returned `UnrecognizedClientException`. |
| Replace and delete old generation | SQLite model activated the second reference before Worker deletion of the first. |
| Final AWS cleanup | Both objects produced three paired metadata/exact-read not-found observations, separated by two seconds. |
| Final Cloudflare cleanup | The exact temporary Worker was deleted and provider absence confirmed. |

Creation took 325 and 231 ms as measured inside the Worker. The four read
**actions** took 624, 340, 537, and 189 ms; each includes metadata reconciliation
and an additional exact read. These few observations are not a latency
benchmark or a cold/warm classification. Cleanup observations establish the
bounded probe result, not an AWS eventual-consistency guarantee.
[Secrets Manager deletion lifecycle](https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_DeleteSecret.html).

## Local validation and limits

Reproducible `npm ci` completed with the existing lockfile plus exact-pinned
`aws4fetch` 1.0.20. The npm registry reported it as the latest stable release,
MIT licensed; the upstream signing interface is documented for
Workers. No transitive dependency is added by that signing package. Existing
Undici/Miniflare/Wrangler advisories remain as
[previously recorded](2026-09-07-worker-routing-proof.md); no preview toolchain
or force upgrade was substituted. The deployed bundle uses the Workers fetch
implementation; local runtime tests intercept every outbound request.

Validation passed: pinned native TypeScript 7.0.2 checking before provider
bundling, 18 secret JavaScript/runtime tests, 44 Python tests (including 12
secret-controller/model tests), 3 routing regression tests, Ruff lint/format,
Pyright, whitespace, source-hash comparison, and local documentation links.
Node remains 24.20.0; no TypeScript/Node/Worker toolchain dependency was updated.
The local runtime test uses workerd's `2026-07-30` date and is not evidence for
the newer hosted date.

The SQLite model proves only its disposable revision/activation behavior. It
is not the selected production FGA database, the complete accepted link state
machine, audit implementation, dispatch fencing, or a transaction spanning AWS
and the database. Scripted local failures are not hosted fault injection.

The actual IAM evidence covers the operator's successful lifecycle operations
and denied `PutSecretValue`; a separate local policy-inventory request was
also denied. Effective policies were not retrieved, and no separate reader
identity, cross-namespace IAM denial, IAM mutation denial, or policy-management
denial was proved. Production role separation, crash/restore/orphan recovery,
throttling/outage behavior, unattended credential replacement, and sustained
latency evidence remain outstanding on #0009. No real Flickr credential or
Flickr API request was used. The read-only installation-credential slice and
database-store decision remain separate work.
