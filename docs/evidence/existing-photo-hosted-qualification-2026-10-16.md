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

The next disposable CI run reached the matrix: its PNG case passed, JPEG failed,
and both created resources were confirmed deleted. The older receipt does not
contain the JPEG response observations, so its failure is not attributed to
headers, provider behavior or application status without further evidence.
Source inspection confirms the synthetic JPEG is a six-byte marker fixture,
the handler constructs a typed `image/jpeg` response with exact length, and the
same runner checks are retained. Marker acceptance remains separate from full
image decoding. No JPEG fixture or acceptance check was relaxed.

`caseFailure` now retains only a closed validator/transport reason, numeric HTTP
status/byte count, closed media/cap enums, bounded canonical counter integers,
header-check booleans and a closed application-error code from JSON bodies no
larger than 4 KiB. Unknown codes/media/errors become fixed enum values; absent
observations remain null and `headersObserved` distinguishes transport failures.
Raw response/image bytes, header values, URLs, credentials and exception messages
remain excluded. Fourteen offline orchestration/transport tests cover JPEG
header failure receipt retention, a JPEG JSON application error, and arbitrary
data exclusion. No additional live call or dispatch was made by this author.

## Missing-auth isolation investigation

The third disposable attempt passed PNG, JPEG and discovery, then observed a
404/text response of 17 bytes without probe counters for missing-auth. Cleanup
confirmed both created resources deleted. The receipt does not establish which
upstream edge/component produced that response.

Offline source and bundle inspection found no mutable per-isolate seed/control
state. The fixture is persisted in the dedicated D1; its access secret is an
environment binding. The production missing-auth path does not consult D1 or
Flickr secrets. A new `isolation.mjs` regression runs independent Node JavaScript
isolates with unseeded, throw-on-access database bindings. Valid outer access
with absent installation authorization returns empty 401, the Bearer challenge
and zero probe counters; missing/wrong outer access returns empty 404. Every
isolate reports zero database accesses. Five local tests pass, including that
regression and all 22 original handler cases. Ruff/Pyright pass for the changed
Python test.

The observed nonempty 404 therefore cannot be reproduced as this fixture's
missing-auth or outer-denial path. No fixture, production authentication check,
case retry or accepted response check was changed to force a pass. Attribution
to a provider error, stale artifact or other edge behavior requires additional
hosted evidence; this offline investigation does not claim that cause resolved.
No additional hosted request, resource operation or dispatch was performed.

The harness entry point now adds one fixed public marker to every response it
constructs, including outer denials and the seed response. Receipts retain only
marker-presence/match booleans. A separate provider-response classifier accepts
only an exact bounded `error code:` pattern with one of eight fixed known codes;
everything else becomes an unrecognized/unavailable enum. No raw response text
or marker header value is retained. These observations are diagnostic and
forgeable, not proof of origin or permission to accept a response.

Fresh-isolate regression now verifies the marker on valid missing-auth and both
outer-denial paths. Forged/arbitrary header/body data tests verify exclusion and
confirm an otherwise invalid response still fails with an exact marker present.
Production validation, transport bounds, readiness/case retry policy and seed
isolation are unchanged. The unexplained prior 404 remains unattributed pending
fresh reviewed hosted evidence. No live call or dispatch was made for this work.
