# Existing-photo disposable hosted qualification preparation

Date: 2026-10-16. Status: local harness verified; hosted qualification pending.

The new [disposable probe](../../probes/existing-photo-qualification/README.md)
executes the actual production router and discovery/thumbnail handlers with a
dedicated synthetic database fixture and closed upstream response scenarios.
The new [Python runner](../../scripts/existing_photo_qualification.py) uses bounded
HTTP reads, refuses redirects and writes sanitized aggregate receipts. The
TypeScript Worker is runtime code; Python owns orchestration and validation.
No dependencies, shared manifests, production source or production flags changed.

Verification completed locally:

- Four Python tests passed, including 22 production-router scenarios through
  Node's existing SQLite adapter, a real 15-second timer, bounded HTTP errors and
  a no-redirect HTTP-reader check.
- Ruff, Pyright and the pinned native TypeScript 7 compiler passed for new code.
- Wrangler 4.116.0 dry-run bundled the disposable Worker successfully. The
  artifact has one placeholder D1 binding and no production secret binding.
- The local adapter confirmed no photo binding or submission intent creation.

The fixture advances link revision monotonically and revokes its synthetic
installation last. Every run requires a new migrated disposable database and
sequential execution. Production/custom-domain resources must never be bound.
The stock configuration exposes no workers.dev endpoint, preview URL or route;
reviewed disposable configuration and a fresh access secret are required before
the separate hosted ceremony. No cloud resource, real provider credential,
real Flickr request, deployment, migration or native host action was performed
by this harness author. Wrangler dry-run is local bundling, not deployment.

The pinned Miniflare/workerd generation predates the 2026-10-16 compatibility
date and was not used as evidence for the newer hosted runtime. The exact
`enable_request_signal` setting is explicit in the disposable config, but its
hosted disconnect behavior is unqualified. Marker fixtures establish the
handler's JPEG/PNG acceptance behavior, not full image decoding.

Next: parent review of isolated provisioning and exact artifact/configuration;
hosted synthetic matrix with private created-resource journal and exact cleanup;
separate production-edge error/auth/disconnect checks; supported native transport
allocation/redirect/UI/cache evidence; narrowly authorized real public-photo
read if needed. Native and production edge configuration are not represented by
the local adapter. Accepting the production contract and enabling any read
capability remain subsequent owner gates. Intake and Flickr writes remain paused.

The Proposed architecture candidate remains the detailed qualification checklist;
this evidence neither accepts it nor claims a full hosted/native gate pass.

## Executable hosted-run preparation

The separate hosted orchestrator and manual-dispatch workflow are now prepared.
They use the existing dedicated CI token/account variable, a fresh disposable D1
and random Worker name, CSPRNG gate, exact acknowledged-resource journal,
reviewed 2026-10-16 date with nodejs_compat/enable_request_signal, fixed artifact
upload and narrow finally cleanup. They neither accept production IDs nor mutate
production configuration. Only sanitized explicit receipts are uploaded.

Six fake-provider orchestration tests pass; combined local suites report ten
tests including the existing 22 production-router scenarios. Ruff and Pyright
pass. No credentials were read, workflow dispatched or cloud operation executed
while preparing/testing this orchestration code. The parent retains the live-run
review/dispatch boundary. The probe README documents ambiguous-mutation and
ephemeral-private-journal recovery limits; forced runner death cannot guarantee
cleanup. This preparation adds no hosted pass claim.


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

## First disposable hosted execution: stopped before matrix cases

The primary dispatched [CI run 38923320751](https://github.com/FlickrGroupAddr/api-cloudflare/actions/runs/38923320751)
for source ea14a93. Provisioning, migrations, fixed Worker upload and disposable
endpoint enablement completed. Preparation of the HTTP matrix failed before the
first case with a ValueError; the original receipt lacks a finer gate/seed reason,
so no cause or provider compatibility result is inferred. The
[retained sanitized receipt](existing-photo-hosted-ci-first-2026-10-16.json)
confirms deletion of both exact created resources. No live Flickr call or
production resource was involved. This is a failed qualification run.

The reviewed follow-up retains closed readiness/seed diagnostic categories,
numeric HTTP status/body length and closed media/cap enums. It preserves bounds,
keeps seed single-attempt and permits only bounded safe readiness GET retries.
A new execution uses entirely fresh resources after the previous cleanup proof;
it is not a replay of an unconfirmed mutation.
