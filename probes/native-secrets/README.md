# Paused native credential lifecycle proof

Date: 2026-09-11

Status: The bounded hosted proof passes all 29 cases with resource cleanup
confirmed. [Results and limits](../../docs/research/2026-09-11-native-secret-lifecycle-proof.md)
record the evidence under accepted architecture ADR 0052. This is a synthetic
provider/lifecycle proof, not the production FGA API or a real Flickr grant.

## Run and validate

```console
npm ci
npm run check
npm run native-secrets:test
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pyright
uv run --frozen python -m unittest discover -s tests
uv run --frozen python scripts/native_secret_probe.py run
```

The controller requires the existing Wrangler login with one account. Terry
explicitly authorized the necessary disposable native lifecycle tests on
2026-09-11. The hosted command creates only generated synthetic resources,
checkpoints their identities before mutations, and attempts cleanup on every
exit. It reuses an existing unambiguous Secrets Store without deleting it, or
creates a temporary store if none exists. Secret names are unique to the run;
it never targets an existing user secret, Worker, or database.

The native TypeScript 7.0.2 compiler runs before Wrangler bundling. npm's stable
tag was rechecked on 2026-09-11 and remained 7.0.2. No dependency was added or
upgraded; Node remains 24.20.0. The local runtime test uses the pinned workerd's
2026-07-30 compatibility date, while the hosted proof uses 2026-09-11.

Node supplies Miniflare's programmatic D1/Secrets Store APIs and the native
test runner. It tests a real local database/binding, disposes the runtime,
reopens its persisted state, and intercepts every external request. The Python
controller owns provider orchestration and evidence through `uv run --frozen`.

## What the fixture implements

`schema.sql` contains a single revisioned link, a pending lifecycle operation,
the next or retiring generation, an append-only transition audit, and a
start-attempt journal. A conditional D1 update admits only one competing
replacement. The pending operation has no automatic expiry or takeover that
could silently overlap another native mutation. Application writes remain
paused throughout this proof; there is no Flickr transport.

Each secret value contains a fixed synthetic token pair and an application
generation. The client rejects a mixed/malformed bundle, a missing value,
generation mismatch, and authority that changes during the read. It returns
only a diagnostic outcome and non-secret fixture generation, never token bytes.
Real Flickr values cannot be supplied through the CLI or probe request schema.

The active slot is overwritten during replacement. Credential retirement
replaces it with a noncredential marker naming the exact retiring generation.
D1 removes ordinary authority first and retains the retiring generation.
The controller requires three consecutive matching native observations,
separated by two seconds; the Worker independently rechecks the matching marker
before the conditional disconnect completion. Missing/denied reads, malformed
values, and an old generation's retirement marker never prove completion.

The empty slot stays bound so relinking can replace its value without a Worker
deployment. This is removal of the credential payload, not deletion of the
provider's secret object or proof of physical erasure from provider backups.
Teardown separately removes the Worker, D1 fixture, secret object, and any
run-owned empty store, with provider absence checks. No existing store or
unrelated entry is removed.

## Failure cases and evidence boundaries

The hosted sequence tests authentication refusals, native binding reads,
competing starts, pause enforcement, an actual deployment replacement while
paused, secret-update reconciliation, failed activation/audit atomicity,
lost activation-response reconciliation, late old values, malformed values,
repair, disconnect/relink serialization, retirement correlation, and reuse of
the same native binding after disconnect. Source and bundle hashes bind the
results to the exact code. The controller admits only the known instances of
that identical build during the deliberately tested deployment overlap.

The audit failure is an actual failed D1 batch: a CHECK violation follows the
activation statement, and both activation and its trigger-created audit event
must roll back. Lost-response cases deliberately discard acknowledgements of
real completed operations and recover from D1/native observations. They do not
claim an independently occurring provider outage. Late/malformed value cases
are deliberate operator fault injection that bypasses the ordinary lifecycle
check to test fail-closed consumption; they are not permitted runtime paths.

Read-only Worker requests use bounded retries for transient edge failures.
Conditional D1 transitions can be reconciled against durable state and retried
at the same expected revision. Native secret API writes are not implicitly
replayed. The controller's exclusive run lock prevents overlapping local
execution/cleanup; production writers must preserve durable operation ownership
across their actual process topology rather than rely on this local lock.

The Worker carries a native read binding and no Cloudflare management token.
The local operator sends management requests with its existing Wrangler
credential. A callable-looking `put` property on the hosted binding was not
proof of write authority: the actual scoped invocation was rejected. This is
one observed denial and the documented read surface, not an exhaustive audit
of undocumented methods or a least-privilege production management-token test.

## Credentials, recovery, and cleanup

The random probe bearer is included in the initial Worker version through
Wrangler's `--secrets-file`. A temporary JSON transport file under system temp
is deleted immediately after upload, including failure paths; it is not a run
artifact. Provider credentials remain in process memory. Wrangler disk logs
are disabled; the upload helper checks retained logs and redacts/refuses any
unexpected bearer diagnostic.

Ignored `.native-secret-runs/rp-<24-hex>/` directories contain manifests,
source/bundle identity, sanitized case results, fixture SQL and private provider
logs. They contain no real Flickr credential. Publish only the reviewed
minimized evidence, never arbitrary private logs or account inventories.

After interruption or an unconfirmed cleanup, resume the exact checkpoint:

```console
uv run --frozen python scripts/native_secret_probe.py cleanup --run .native-secret-runs/rp-<24-hex>
```

Cleanup checks generated names, provider IDs and ownership, refuses a
same-name replacement, never deletes a nonempty/unowned store, and refuses
secret deletion while Worker cleanup is uncertain. Never edit a manifest to
point at another resource. An earlier report remains the original execution
result; resumed cleanup updates the manifest.

Production integration still needs authenticated UI/API routes, real
owner/permission validation, reviewed management-token scope, migration and
wire-schema integration, and the separate Flickr dispatch/recovery gates.
The native store capability proof does not accept those unimplemented pieces.
