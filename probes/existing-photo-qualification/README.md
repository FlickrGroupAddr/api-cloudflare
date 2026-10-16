# Disposable existing-photo qualification

Status: executable local harness; hosted and native qualification pending.
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

## Parent-reviewed hosted ceremony (not executed by this harness author)

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

## Executable dedicated-CI ceremony

The separate `scripts/existing_photo_qualification_hosted.py` now implements the
preceding ceremony with only `--from-env` and an output-directory argument:

```console
uv run --frozen python -m scripts.existing_photo_qualification_hosted --from-env --output-directory .coordination-runs/existing-photo-qualification
```

The manual-dispatch `.github/workflows/existing-photo-qualification.yml` uses the
existing dedicated `FGA_CLOUDFLARE_CI_TOKEN` and account variable, Node 24.22.0,
npm 12.2.0 and frozen dependencies. Its only uploaded artifact is the explicitly
named sanitized receipt. No credential, resource journal, generated config,
Wrangler diagnostic, bundle or raw HTTP payload is uploaded. No workflow has been
dispatched as part of preparing this implementation.

Provider operations use the official bounded no-redirect REST transport. The
orchestrator checks its fresh random Worker name is absent, creates one fresh
D1, journals its exact acknowledged ID, applies current repository migrations,
builds the fixed probe locally, and uploads it once with its CSPRNG secret in
multipart metadata. It records the acknowledged Worker identity before enabling
only that Worker's workers.dev endpoint. The generated disposable config has
workers_dev true, the reviewed date/flags and no production routes/domains.
The stock checked-in config stays unreachable and unbound.

Cleanup deletes only acknowledged identities created by that invocation and
confirms absence. An ambiguous creation/upload is never retried or guessed:
its attempted state stays in the private journal, cleanup is unconfirmed and
the run fails. Known D1 cleanup still proceeds after ambiguous Worker upload.
No broad resource enumeration or name-prefix deletion exists. The journal is
under `OUTPUT/private/RUN/journal.json` and must remain private; on ephemeral CI
it is not retained after job teardown. A timeout/ambiguous mutation therefore
requires a reviewed private reconciliation using the provider's audit trail,
not a blind rerun or public journal upload. Parent review must account for that
recovery limitation before dispatch. Cleanup also cannot be guaranteed after
forced runner termination.

Six fake-provider tests cover success, migration/enable/matrix failures,
ambiguous create/upload, cleanup refusal and missing credentials. They make no
provider call. The dedicated CI token must already permit the required Worker
and D1 operations; this runner never broadens token scope or reads local operator
credential files.

Transport references: [Worker module upload](https://developers.cloudflare.com/api/resources/workers/subresources/scripts/methods/update/)
and [Worker subdomain configuration](https://developers.cloudflare.com/api/resources/workers/subresources/scripts/subresources/subdomain/).

Executing this workflow can establish the disposable synthetic hosted matrix;
all independent production-edge, disconnect and native gates above remain.


## Pre-dispatch recovery review corrections

The runner now atomically persists its sanitized receipt before the first
provider operation and before/after mutation phases. It retains only the fresh
synthetic `runName`, exact expected `databaseName`, stage, attempted/acknowledged/
deleted flags and artifact/configuration hashes. Account ID, database ID,
credentials and private journals stay excluded. The workflow's always-artifact
step retains this same exact receipt even when the qualification step is stopped.

On an incomplete/ambiguous run, use those exact fresh names and expected artifact
digest to inspect the provider's exact-name resource/audit records read-only.
Establish ownership and identity before reviewing narrowly scoped cleanup.
Never retry create/upload to discover the result, scan broadly by prefix, or
delete an unconfirmed identity. The retained names preserve correlation after
ephemeral CI teardown; they do not prove that an ambiguous mutation succeeded.
Forced termination can still prevent cleanup, and an entire cancelled job can
prevent artifact retention; inspect its last persisted receipt when available.

Ordinary operations have an eight-minute observed deadline checked between
provider/matrix operations. One in-flight bounded call or the 120-second local
bundle can finish after that deadline; acknowledged-resource cleanup then gets
its own bounded calls. The workflow gives the runner step fourteen minutes
inside its twenty-minute job, reserving practical setup/artifact headroom rather
than relying on finally after forced termination. No mutation retry was added.

The receipt distinguishes `dryRunConfigSha2_256` from
`uploadMetadataSecretElidedSha2_256`. The latter hashes the exact upload metadata
with only the fresh secret text replaced by `[SECRET_ELIDED]`, using sorted-key
JSON; `artifactSha2_256` identifies the uploaded JavaScript bytes. It therefore
identifies the deployed flags/bindings metadata separately from local bundling.

Seven fake-provider tests now pass, including pre-mutation receipt assertions,
secret-elided actual multipart provenance and operation-deadline refusal before
the first provider call. Ruff and Pyright pass. No live call or dispatch occurred.


Final review correction: `matrixPassed` records only the synthetic matrix result;
overall `passed` stays false throughout provisioning and cleanup and becomes true
only after cleanup absence checks succeed. Fake-provider tests assert false
overall status before every mutation, including deletes. Before any provider
operation, the runner also flushes only its fresh nonsecret Worker/database
names to CI stdout, preserving exact-name correlation in retained job logs if a
whole-job termination prevents receipt artifact upload. No account, ID, token or
URL is printed. Whole-job termination can still prevent cleanup and artifact
retention; the exact-name reconciliation procedure above remains required.


The first disposable CI attempt failed before any matrix case, after successful
provisioning/upload/enable, and confirmed both created resources deleted. Its
older `ValueError` receipt does not distinguish readiness transport/status/body
failure from the single seed attempt; no narrower cause is inferred.

The runner now retains closed `edgePreparation` diagnostics for gate readiness,
seed fixture and matrix start. Fields are phase/reason enums, attempt, observed
numeric HTTP status/body byte count, a closed media-type enum and cap category.
Unavailable observations are null; a cap failure records the bounded excess
read count. No raw body, header value, URL, exception text or credential appears.
Transient readiness GET failures can retry within the existing ten-attempt and
operation-deadline bounds. A seed failure is recorded immediately and never
retried. This instrumentation makes no change to image/error response caps.
Fake tests cover exact gate/seed reasons, exhausted readiness bodies, transient
safe-GET rollout, oversized response and a single ambiguous seed response.
No additional live call or dispatch was performed while preparing this change.
