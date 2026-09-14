# Foundation and release-gate decision handoff, 2026-09-14

Terry approved ADR0058 on 2026-09-14; cards #0002 and #0018 have resumed
implementation. The earlier decision handoff is resolved. This is not a full
release-conformance pass. All other foundation children are completed;
#0018 remains the rollup's final acceptance dependency.

## Accepted decision

Terry accepted architecture
[ADR0058](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/decisions/0058-record-managed-d1-engine-provenance.md):
allow the private managed D1 deployment to record its SQLite-library version as
explicitly undisclosed when the provider does not expose it. Keep actual
provider/runtime, schema, artifact and tooling provenance, with the observation
and reason. Keep every behavioral, mutation, stop/restart, restore and promotion
requirement. An AWS move merely to obtain an engine-version string is not
recommended.

The fresh authenticated read-only query `SELECT sqlite_version() AS sqlite_version`
returned HTTP 400 / Cloudflare error 7500: `not authorized to use function:
sqlite_version at offset 7: SQLITE_ERROR`. The database API returned
`version: production`, which does not disclose a SQLite library version.
The former conformance contract required that version. The accepted amendment
now permits an explicit null and that observed refusal for the private profile.
The [sanitized observation and handoff evidence](../evidence/release-gate-handoff-2026-09-14.json)
contains no credentials or account identifiers.

The accepted contract, runtime fingerprint and verifier were updated together.
Evidence schema version 2 accepts only the exact remote function refusal as the
undisclosed state; missing versions, authentication failures, transport failures,
and unknown provider errors still fail. Disclosed versions retain their remote
source. Observations must fall inside the run interval. Tooling and adapter
identities and the Workers compatibility date are verified against release inputs.

## Completed in this pass

The release verifier now rejects provider tags such as `production` in place of
an actual SQLite-library version and requires an explicit version kind. It also
checks for uncommitted assets, tests, probes, scripts, workflows and tool locks,
in addition to the production source and schema. This prevents a committed
source label from concealing changed release inputs. Regression tests exercise
both invalid provenance and edited/untracked inputs in a temporary Git repository.

Validation after acceptance passed: 111 Python tests, 107 Node tests, native TypeScript, generated
API consistency, and Pyright/Ruff for the changed Python files. Unit-test engine
versions are synthetic fixtures, not observations of hosted D1. The inventory
still contains 56 stable cases and 28 required behavioral mutation classes.
Missing production evidence still fails the promotion command closed.

No production application, cloud resource, credential or Flickr data was changed
in this pass. Both live write gates remain paused, and dispatch remains disabled.

## Remaining implementation

The evidence-format decision is implemented. The read-only
`scripts/d1_engine_provenance.py` collector obtains a fresh observation from the
same DB binding in the private deployment JSON, with its remote migration head.
Its `provenance-only` report deliberately cannot satisfy the full release gate.
The full runner must collect this observation within its own run and emit the
complete schema-version-2 record. No user action is required for this metadata.

The following engineering is still required before #0018, and therefore #0002,
can reach Ready for Review with a full foundation acceptance claim:

1. Implement the full production runner for all 56 cases and all 28 behavioral
   mutations, using the actual optimized production artifact, migrations,
   authentication, transport, allocator and retry paths. Existing bounded crash
   and mutation probes do not satisfy this entire inventory.
2. Complete independent process-stop and deployment-restart adapters. An
   in-process exception or a reset hook is not interchangeable with those tests.
3. Prove a hosted restore of the current schema and reconcile facts newer than
   the backup, including permanent suppression and credential/session revocation.
   The earlier hosted archive to local SQLite roundtrip is not this proof.
4. Complete global Flickr budget and production-path integration coverage,
   including calls outside dispatch where applicable. Use controlled HTTPS peers
   and synthetic identities; record zero live Flickr calls in conformance runs.
5. Add the CI promotion workflow and publish the exact-artifact evidence and
   receipts only after all required cases and mutation controls pass. Keep missing,
   skipped and failing evidence release-blocking.

These items remain engineering work after the accepted owner decision.
Neither card is closed; there is no full production conformance pass and live
Flickr group additions remain disabled.

## Backup investigation resolved

On 2026-09-14, Terry accepted daily backup coverage as sufficient and directed
that the question be marked investigated and resolved. D1 automatic Time Travel
meets that frequency requirement. No separate daily export job is required;
the current-schema hosted restore/reconciliation proof remains part of #0018.
See the [accepted backup baseline](../operations/d1-backup-and-recovery.md).
