# Disposable existing-photo hosted runner review

Date: 2026-10-16. Status: source review passed after corrections; no remaining
review blocker to the separately authorized disposable CI run. No credentials,
live API calls, provider mutations, deployment or
desktop operation were used. Only this evidence note is reviewer-owned.

Scope: `scripts/existing_photo_qualification_hosted.py`,
`.github/workflows/existing-photo-qualification.yml`, the disposable probe
Worker and their local test/transport dependencies. Accepted architecture
ADR0061 permits qualification development; the detailed thumbnail candidate
remains Proposed. A disposable synthetic edge pass cannot establish the
production custom-domain/edge configuration, supported native transport or
real-account Flickr qualification.

## Initial material findings

1. The private created-ID journal is excluded from the CI artifact and the
   sanitized receipt was saved only in `finally`, without the fresh run name.
   An ambiguous create/upload or terminated ephemeral runner could therefore
   lose the exact resource correlation needed for safe reconciliation. Before
   dispatch, retain a sanitized nonsecret recovery marker before the first
   mutation and update it at each stage. It may contain the fresh synthetic
   Worker/database names and stage/attempt/cleanup flags; it must contain no
   account ID, token, private journal, raw provider payload or credential.
2. The initial 20-minute job timeout includes dependency installation and a
   runner whose worst-case sequential call budgets exceed that limit. The
   matrix alone allows 22 socket waits of 25 seconds, migrations allow 15 waits
   of 30 seconds, and readiness, building, provisioning and cleanup add more.
   Reserve practical runner-step and artifact headroom below the job deadline;
   never depend on `finally` executing after a forced job termination.
3. `generatedConfigSha2_256` identifies the dry-run configuration, while the
   Worker is uploaded through separately constructed multipart metadata.
   Distinguish these artifacts and identify the actual secret-elided deployed
   metadata configuration in the receipt rather than implying the dry-run
   configuration alone identifies the control-plane upload.

These findings were sent to the owning implementation agent and primary before
any dispatch. They were corrected by the owner and independently reviewed as
recorded below.

## Boundaries already supported by source

The orchestrator generates a CSPRNG run name, checks that exact Worker name is
absent, creates one new D1, validates the returned canonical UUID and expected
database name, and records acknowledged identities before dependent operations.
Create/upload/control mutations are single-attempt. Ambiguous mutations are not
retried and unknown resources are not guessed or deleted by prefix. Normal
cleanup is restricted to acknowledged identities; D1 cleanup also checks its
expected name and both cleanup paths verify absence.

Provider transport fixes the HTTPS Cloudflare origin, refuses redirects, bounds
response allocation and keeps bearer material out of arguments and output.
The local dry-run build strips Cloudflare/Wrangler/FGA environment credentials.
The fresh probe access token is supplied only in upload metadata and request
headers, not in URLs, receipts or logs. The workflow scopes provider secrets to
the single qualification step and uploads only the specifically named sanitized
receipt, with pinned actions and read-only repository permission.

The probe exports only a secret-gated GET surface for fixed synthetic paths and
one fresh fixture seed. It binds only the newly created D1 and synthetic Flickr
material, supplies an injected fixed upstream responder, exports no scheduled
handler and provides no production custom-domain, dispatch, queue or secret-store
binding. The public synthetic installation bearer is intentionally not the outer
access secret. Neither synthetic redirects nor application-created streams prove
actual production upstream/edge parser or native SDK behavior.

## Required ambiguity handling

A failing or incomplete receipt never authorizes another create/upload attempt
to resolve the first result. Preserve the exact synthetic names and expected
artifact/configuration provenance, inspect the provider's exact resource/audit
record read-only, establish ownership and identity, then review narrowly scoped
cleanup. No broad resource scan/delete or unconfirmed mutation retry belongs to
recovery. A forced runner stop may leave resources behind; retained correlation
must make that condition visible and recoverable without exposing secrets.

## Correction review and remaining practical limits

`scripts/existing_photo_qualification_hosted.py:230` now atomically persists
the sanitized receipt before the first provider operation and around mutation
phases. It records fresh nonsecret Worker/database names and attempted,
acknowledged and deleted flags. The initial exact-name correlation is also
flushed to CI stdout at `:250`, so ordinary retained job logs can support
reconciliation if whole-job termination prevents the artifact step. Account ID,
database ID, provider token, probe access token, raw responses and private
journal remain excluded from those public channels.

`checkpoint` at `:242` enforces an eight-minute observed operation budget
between calls. One in-flight socket wait or the bounded 120-second build may
finish later; exact acknowledged-resource cleanup has its own bounded calls.
The runner step is capped at fourteen minutes inside the twenty-minute job
(`.github/workflows/existing-photo-qualification.yml:39`), with an always-run
artifact step at `:44`. Whole-job cancellation/timeout can still skip cleanup
and artifact upload; this is not presented as guaranteed cleanup. Retained
flushed exact names make that outcome practically reconcilable through narrowly
scoped provider inspection rather than a blind rerun or broad deletion.

`upload_metadata` at `:123` supplies the actual multipart metadata. Its sorted
JSON hash with only secret text replaced by `[SECRET_ELIDED]` is recorded
separately from the dry-run configuration hash and uploaded JavaScript hash.
The fake-provider test extracts actual multipart metadata and verifies this
digest, preserving provenance without recording secret material.

A follow-up review caught an interim receipt that could have said `passed:true`
after matrix success but before cleanup. This is corrected: `matrixPassed`
tracks only the synthetic cases, while overall `passed` stays false throughout
provisioning/cleanup and is assigned only from matrix success plus confirmed
cleanup at `:391`. Tests inspect the persisted false result before every
mutation, including deletes. Incomplete/aborted receipts are not qualification
passes and never imply resource absence.

No remaining material source/ownership/secret-handling defect was found in this
bounded runner. The primary agent must still inspect the actual CI result and
cleanup evidence. This review does not establish token permissions, provider
API compatibility, actual edge behavior, production settings or native host
qualification; the first real execution supplies that distinct evidence.

## Independent verification and exact sources

`uv run --frozen python -m unittest tests.test_existing_photo_qualification tests.test_existing_photo_qualification_hosted`
passed 11 tests, zero failed, in the repository's locked environment. These are
local synthetic matrix/fake-provider checks and made no live provider call.

SHA2-256 digests of the final reviewed sources:

| File | Digest |
| --- | --- |
| `scripts/existing_photo_qualification_hosted.py` | `b738741aa5746c53cfd93992d734c9e599eecc541e83eadc2e029e78bf425ce5` |
| `.github/workflows/existing-photo-qualification.yml` | `b38cd2c44594ba623807c821824061f753e5759f330d5ac0dbeef702aeef1b1d` |
| `probes/existing-photo-qualification/worker.ts` | `11e0aa8479f55b48fe84efbe6483d6d413a10e9131be2bd97a23d82b6edc8cba` |
| `scripts/existing_photo_qualification.py` | `3bc9679d56115c705eedb82678add55c2d7eefb34493b3af8c5fb5b1c3e9593e` |

## Preparation-diagnostic follow-up

The primary agent reported that the first actual CI attempt failed before matrix
cases and confirmed deletion of its created resources. This reviewer did not
make a live call or independently inspect provider state. The initial attempt
is not a qualification pass.

Reviewed the owner's diagnostic delta before a fresh-name rerun. The new
`preparation_exchange` (`scripts/existing_photo_qualification_hosted.py:60`)
records only closed phase/reason labels, attempt count, numeric HTTP status and
body-byte count when available, and closed media/cap categories. Raw body bytes,
content-type parameters, headers, URLs, credentials and exception text never
enter the receipt. Missing observations remain null; byte-limit failures report
only the bounded 262145-byte prefix observation and an exceeded category.

`run_matrix` at `:209` repeats only the unauthenticated readiness GET, at most
ten attempts, for the enumerated transient transport/404-body/429/5xx cases.
Deadline checkpoints remain before attempts. The fixture seed remains one
single-attempt call outside that loop; seed timeout or unexpected response
fails without replay. Matrix requests and control-plane mutations gained no
retry. Redirect refusal, 256 KiB allocation limit, overall operation deadline,
exact-resource cleanup and final pass-after-cleanup semantics are unchanged.
`edge_diagnostic` at `:336` persists the preparation phase before cleanup, so the
failure location survives the failing run's final receipt.

No material safety or truthfulness defect was found in this delta. Independent
`uv run --frozen python -m unittest tests.test_existing_photo_qualification_hosted`
passed eleven offline fake-provider/orchestration tests, zero failed. There is
no remaining source-review blocker to the separately authorized fresh-resource
rerun; actual edge qualification and cleanup still require the resulting receipt.

Updated SHA2-256 digests:

| File | Digest |
| --- | --- |
| `scripts/existing_photo_qualification_hosted.py` | `ee394f978415f2e3de642a74fb48caccc532982a4a141057d5a6d01e009d320b` |
| `tests/test_existing_photo_qualification_hosted.py` | `034c34b74183f3a5a8921f45065bcd3b234f084c9a6ca0214b62a52426f324be` |

The HTTP transport and dedicated workflow retain the previously recorded hashes.
