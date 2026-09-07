# Synthetic Secrets Manager proof preparation

Date: 2026-09-07

Status: Local protocol preparation only. Terry approved a disposable AWS proof;
AWS credentials are pending his return to the laptop. Production adoption and
unattended AWS identity are not accepted by that approval.

The [decision review](../../docs/research/2026-09-07-flickr-credential-store-decision.md)
owns the recommendation and links the controlling architecture lifecycle.

## Run the offline checks

```console
npm ci
npm run check
npm run secrets:test
```

The client takes an explicit transport. Tests supply scripted responses; there
is no global `fetch` fallback, AWS credential lookup, or network request. No new
dependency is installed by this change. TypeScript is appropriate here because
the client is intended to execute inside the eventual Cloudflare proof Worker.
The small Node test file uses the native test runner and native TypeScript
stripping, matching the existing routing tests. Future orchestration remains
Python under the repository's `uv run --frozen` workflow.

The local tests exercise full-ARN/exact-version requests, input and response
identity checks, synthetic-only creation, lost-create-response reconciliation,
asynchronous deletion observations, provider denial/expiry/error handling and
redaction. The generated namespace is `fga-proof/<24-hex-run-id>/<UUID>`; the
secret value is a fixed synthetic marker plus the generation UUID. There is no
interface to provide real Flickr tokens. Those IDs are not authentication.

The scope rejects production names and different accounts/regions. It is a
client guard, not IAM enforcement or proof that a reference is currently active.
`requestDeletion` is deliberately named as a request, never a completion result.
`observeAbsence` requires not-found observations from both metadata and the exact
read. A denial, expired credential, timeout or generic error does not establish
absence. AWS eventual consistency still requires bounded repeat observations
in the future hosted controller; one local observation cannot prove convergence.

Before `create`, a controller must persist the generated name/version. If the
response is lost, `recover` describes that retained name and verifies the exact
synthetic version. A temporarily missing object is an uncertain observation,
not permission to discard the cleanup record or create a different generation.
The client makes one request per operation and does not silently replay a write.

## Remaining work on implementation ticket #0009

This is not a deployable Worker or the complete lifecycle harness. Still needed:

- A maintained SigV4 transport with an enforced request/body deadline, explicit
  AWS credential injection, no redirects and no credential-bearing diagnostics.
- A Python controller and authenticated isolated Worker; checkpoint generated
  resources before mutations, bind reports to source/build identity, and resume
  cleanup safely after interruption. Never target existing secrets for deletion.
- Database compare-and-set modeling and crash/race tests, followed separately
  by tests of the selected production store. The protocol tests do not prove
  concurrent activation, dispatch fencing, durable cleanup or database recovery.
- Actual hosted creation, reads, IAM denial cases, repeated deletion checks,
  throttling/latency and resource cleanup, using synthetic grants only.

At the hotel, establish AWS credentials through the machine's local credential
workflow, not chat or command-line arguments. Prefer a named profile that supplies
short-lived credentials, including its session token. The exact AWS account,
region and narrowly scoped reader/lifecycle proof permissions must be selected
before deployment. The hosted controller is not yet implemented, so there is
intentionally no credential-install or deploy command to run from this document.
Do not deploy a broad personal/admin AWS key into a Worker.

No provisioned resource, AWS permission test, hosted runtime pass, production
secret, or Flickr call is claimed. Local failures must remain visible, and local
passes must not be presented as provider evidence.

Validation on 2026-09-07: pinned native TypeScript 7 checking passed; all 12
secret-client tests and all 3 existing routing tests passed on Node 24.20.0.
No Python source or dependency changed. No hosted or IAM check was run.

Primary API references checked 2026-09-07:
[CreateSecret](https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_CreateSecret.html),
[GetSecretValue](https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html),
[DescribeSecret](https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_DescribeSecret.html),
[DeleteSecret](https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_DeleteSecret.html).
