# Disposable existing-photo qualification

Status: all 22 disposable synthetic hosted cases passed on 2026-10-16; production
edge and real native HTTP transport qualification remain pending.

[CI run 38929606706](https://github.com/FlickrGroupAddr/api-cloudflare/actions/runs/38929606706)
on source `1fb7ca8` used date `2026-10-16`, `nodejs_compat` and
`enable_request_signal`; both created resources were confirmed deleted. See the
[sanitized receipt](../../docs/evidence/existing-photo-hosted-ci-passed-2026-10-16.json)
and [scope/history handoff](../../docs/evidence/existing-photo-hosted-qualification-2026-10-16.md).
Earlier failed attempts retain their recorded failures and unresolved causes;
the fourth attempt failed offline from a missing committed fixture and created
no resources. The primary's separate ten native fixture scenarios passed; real
`LrHttp.get` transport remains an independent gate.
Governing scope: architecture ADR 0061 and its Proposed
`docs/hosted-thumbnail-candidate.md`. Production flags remain disabled.

The Worker imports the actual production `createWorker` router, discovery and
thumbnail implementations. Only synthetic fixed upstream responses exist; there
is no call to global `fetch`, real Flickr endpoint, or arbitrary URL relay.
The separate probe gate precedes seeding, production authentication and D1
access. Production installation authentication still executes behind that gate.
No scheduled handler, assets, production secrets, write route, or dispatch binding
is exported. Only two exact GET API paths and one secret-gated synthetic fixture
seed path are allowed. The seed GET mutates only the disposable fixture database.
The public synthetic installation bearer is deliberately not an access secret.

Local checks from the repository root:

```console
uv run --frozen python -m unittest tests.test_existing_photo_qualification
uv run --frozen ruff check scripts/existing_photo_qualification.py tests/test_existing_photo_qualification.py
uv run --frozen pyright scripts/existing_photo_qualification.py tests/test_existing_photo_qualification.py
node node_modules/typescript/bin/tsc --ignoreConfig --noEmit --strict --target ES2023 --module ESNext --moduleResolution Bundler --types @cloudflare/workers-types,node --skipLibCheck --allowImportingTsExtensions probes/existing-photo-qualification/worker.ts
```

Python owns orchestration, bounded HTTP consumption, response validation and
sanitized receipts. TypeScript is necessary for executing the actual Workers
router artifact; the small Node adapter uses the existing SQLite test adapter,
which cannot execute inside Workers. No dependency or shared manifest changed.

## Isolated hosted ceremony

1. Create exactly one new disposable D1 database, record its created ID privately,
   and apply the repository's existing migrations to that database only. Never
   bind an existing database or copy real data. Use a fresh DB for every run.
2. Copy this directory's config to a temporary qualification config. Replace
   only its disposable database binding/worker name and explicitly enable that
   disposable Worker's `workers.dev` endpoint. No custom domain, production route,
   production deployment configuration, or Secrets Store binding is needed.
   Keep `nodejs_compat`, `enable_request_signal`, disabled observability and the
   exact reviewed compatibility date. Record the actual generated config and
   upload artifact hashes privately alongside the sanitized source receipt.
3. Generate a fresh CSPRNG access secret of at least 32 characters. Install it as
   the disposable Worker's `PROBE_ACCESS_TOKEN` secret and pass it to the runner
   through `FGA_PHOTO_PROBE_ACCESS`. Never echo it, place it in an argument or URL,
   write it to tracked evidence, or reuse an installation/Flickr credential.
4. Deploy only that reviewed disposable artifact. Run one sequential matrix:

   ```console
   uv run --frozen python scripts/existing_photo_qualification.py https://DISPOSABLE_WORKER_ORIGIN --seed --output PRIVATE_RECEIPT.json
   ```

   The runner refuses redirects, caps every response at 256 KiB, caps JSON errors
   at 4 KiB, and keeps bodies, URLs, credentials, headers and raw exceptions out
   of its receipt. It records case names, status, byte counts, elapsed observed
   time and local source hashes. Review the receipt before publication. It
   aborts after the first failure. An outer gate/seed failure produces a failing
   receipt; inspect privately rather than publishing diagnostics. The suite
   deliberately advances the linked revision to 2 and permanently revokes the
   fixture installation last. Do not rerun, parallelize, or share the database.
5. Destroy only the exact Worker and database created in this ceremony, using the
   private created-ID journal. Record cleanup success separately. Do not select
   resources by broad prefix or delete any pre-existing resource.

The stock config has `workers_dev: false`, no routes and a zero placeholder D1
ID, preventing accidental use as a ready-to-deploy production configuration.
Provisioning and cloud cleanup are intentionally separate from the HTTP runner;
it never discovers credentials or calls provider control-plane APIs.

## Conclusions the matrix cannot supply

The synthetic matrix covers the actual application handlers on whichever runtime
executes it, including JPEG/PNG marker acceptance (not full decoding), discovery,
authentication, malformed query, requested revision, ownership/public validation,
exact identity/destination, upstream redirects/errors, declared and streaming
byte excess, truncation, MIME/signature rejection, a real 15-second abort timer,
stream cancellation and final link/grant/credential fences. It asserts zero
binding and intent creation in its local adapter.

Synthetic `Response`/stream inputs do not prove upstream network parser,
compression, redirect forwarding, edge-generated error behavior, or provider
allocation controls. The dedicated Worker path does not reproduce production
custom-domain, Access, cache, firewall or routing configuration. Host disconnect
notification with `enable_request_signal`, zero publication on disconnect,
actual provider error bodies, duplicate wire Authorization, supported native
`LrHttp.get` allocation/redirect behavior and complete-page UI/cache cleanup
remain explicit independent checks. A narrow real-account public-photo read
still requires authorization and private evidence. Production contract acceptance
and explicit activation remain separate gates after those checks pass.

Pinned local workerd/Miniflare in the repository predates the probe's
2026-10-16 compatibility date. Node integration and Wrangler dry-run bundling
must never be reported as hosted runtime qualification. No local emulator result
waives a newer hosted setting. If this exact compatibility date/flag combination
is rejected by the provider, stop and review it; do not silently downgrade.

## Dedicated-CI execution and recovery

`scripts/existing_photo_qualification_hosted.py` implements the ceremony above:

```console
uv run --frozen python -m scripts.existing_photo_qualification_hosted --from-env --output-directory .coordination-runs/existing-photo-qualification
```

The manual workflow uses the dedicated `FGA_CLOUDFLARE_CI_TOKEN` and account
variable, Node 24.22.0, npm 12.2.0 and frozen dependencies. It uploads only the
explicitly named sanitized receipt. Credentials, actual resource IDs, private
journals, generated config, Wrangler logs, bundles and raw HTTP payloads are not
uploaded. The token must already permit Worker and D1 operations; this runner
never broadens token scope or loads local operator credential files.

The runner checks its fresh exact Worker name is absent, creates one new D1,
journals its acknowledged ID before dependent operations, applies current
migrations, builds the fixed probe and uploads it once with a fresh CSPRNG gate.
It records the acknowledged Worker identity before enabling that Worker's
workers.dev endpoint. The generated config has no production routes/domains.
Provider REST responses and HTTP case bodies are bounded; redirects are refused.
Readiness GETs may retry transient failures at most ten times. Seed, create,
upload, case execution and cleanup mutations are never retried.

An eight-minute observed operation deadline is checked between operations; one
in-flight bounded call or the 120-second local build can finish afterward.
Acknowledged-resource cleanup then uses separately bounded calls. The runner
step has fourteen minutes inside the twenty-minute job. Forced process/job
termination can prevent cleanup or artifact retention; it never becomes a pass.
`matrixPassed` is separate from overall `passed`, which stays false until cleanup
absence checks succeed.

Before provider operations and around mutation phases, the runner atomically
persists its sanitized receipt: fresh synthetic Worker/database names, phase,
attempted/acknowledged/deleted flags and artifact/configuration hashes. It also
flushes only the synthetic names to CI logs. The actual IDs remain in
`OUTPUT/private/RUN/journal.json`, which is not retained on ephemeral CI. If an
outcome is ambiguous, use retained exact names and expected artifact provenance
for read-only inspection of exact resource/audit records. Establish ownership
and identity before reviewing narrow cleanup. Never retry create/upload to
discover an earlier result or perform broad prefix scans/deletes.

Cleanup deletes only acknowledged resources created by the invocation, checks
the D1 name and confirms both identities absent. An ambiguous mutation leaves
cleanup unconfirmed and the run failed. The public receipt identifies uploaded
JavaScript bytes separately from dry-run config and the exact upload metadata
with only its secret text replaced by `[SECRET_ELIDED]` before sorted-key JSON
hashing. All digests use SHA2-256.

Closed diagnostics retain phase/case reason, observed numeric status/byte count,
bounded counter integers, media/cap enums, expected-header booleans and a closed
application error code from JSON no larger than 4 KiB. A fixed public marker is
added to every harness-owned response, including denials; only its presence/
match booleans are retained. Exact bounded known provider-error patterns yield
a closed enum. Arbitrary values, raw bodies/headers/URLs/images and exception
messages never enter receipts. Markers/classifiers are forgeable observations,
not origin authority or a replacement for validation.

Offline tests include fresh independent Node isolates with unseeded,
throw-on-access database bindings: missing installation authentication returns
empty 401 without any database access; missing/wrong outer access returns empty
404. The fixture must be committed as
`probes/existing-photo-qualification/isolation.mjs`; its absence in a clean
checkout stops pre-cloud verification. Prior hosted failures and their unresolved
causes remain recorded in the linked handoff; the final pass does not amend them.

References: [Worker module upload](https://developers.cloudflare.com/api/resources/workers/subresources/scripts/methods/update/)
and [Worker subdomain configuration](https://developers.cloudflare.com/api/resources/workers/subresources/scripts/subresources/subdomain/).

The successful disposable matrix establishes only its exercised synthetic edge
scope. The independent production-edge, disconnect, native HTTP transport and
activation gates above remain.
