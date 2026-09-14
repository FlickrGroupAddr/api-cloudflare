# Foundation and release-gate decision handoff, 2026-09-14

Cards #0002 and #0018 are handed off to Needs Terry. This is a decision gate,
not a full release-conformance pass. All other foundation children are completed;
#0018 remains the rollup's final acceptance dependency.

## Decision needed

Recommend accepting proposed architecture
[ADR0058](https://github.com/FlickrGroupAddr/architecture-design/blob/6dc2138/docs/decisions/0058-record-managed-d1-engine-provenance.md):
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
The current accepted conformance contract requires that version, so its full
release record cannot currently be satisfied by the available provider metadata.
The [sanitized observation and handoff evidence](../evidence/release-gate-handoff-2026-09-14.json)
contains no credentials or account identifiers.

ADR0058 is **proposed**, not accepted. The contract and its pinned fingerprint
are unchanged. This implementation still rejects undisclosed engine versions.
The owner decision is specifically about that evidence requirement; it is not
approval to waive missing engineering or turn on group additions.

## Completed in this pass

The release verifier now rejects provider tags such as `production` in place of
an actual SQLite-library version and requires an explicit version kind. It also
checks for uncommitted assets, tests, probes, scripts, workflows and tool locks,
in addition to the production source and schema. This prevents a committed
source label from concealing changed release inputs. Regression tests exercise
both invalid provenance and edited/untracked inputs in a temporary Git repository.

Validation passed: 104 Python tests, 107 Node tests, native TypeScript, generated
API consistency, and Pyright/Ruff for the changed Python files. Unit-test engine
versions are synthetic fixtures, not observations of hosted D1. The inventory
still contains 56 stable cases and 28 required behavioral mutation classes.
Missing production evidence still fails the promotion command closed.

No production application, cloud resource, credential or Flickr data was changed
in this pass. Both live write gates remain paused, and dispatch remains disabled.

## Resume after the decision

If ADR0058 is accepted, first amend the canonical conformance contract and update
its reviewed SHA2-256 fingerprint, runtime repair-evidence pin, verifier schema
and tests together. Require an explicit null and provider denial evidence for
an undisclosed version; never substitute a local SQLite or tool version.
If the requirement is retained, obtain supported remote engine-version disclosure
from Cloudflare before attempting to qualify a release.

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

These items remain engineering work even after a favorable owner decision.
The proposal does not close either card, constitute a production conformance
pass, or authorize enabling live Flickr group additions.
