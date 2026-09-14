# Foundation and release-gate decision handoff, 2026-09-14

Terry approved ADR0058 on 2026-09-14; that decision handoff is resolved.
The CI credential handoff is also resolved. Both cards are back In Progress for
the full release-suite integration. The [CI setup record](../operations/release-ci-setup.md)
contains the authenticated validation result. This is not a full conformance pass. All other foundation children are completed;
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
2. Extend the completed independent local process-kill proof (both entry paths
   at POST handoff) to the full production artifact/transport and required stop
   matrix, including deployment restart. An in-process exception or reset hook
   is not interchangeable with an independent process termination.
3. Integrate the completed 37-table hosted restore and stale-snapshot refusal
   checks into the full production suite, including native-secret generations
   and the required post-backup reconciliation paths. The earlier hosted-to-local
   SQLite roundtrip alone was insufficient; the new hosted evidence is linked below.
4. Complete global Flickr budget and production-path integration coverage,
   including calls outside dispatch where applicable. Use controlled HTTPS peers
   and synthetic identities; record zero live Flickr calls in conformance runs.
5. The dedicated token and manual workflow are verified. Connect the complete
   runner and publish exact-artifact evidence/receipts
   only after all required cases and mutation controls pass. Missing, skipped or
   failing evidence continues to block release.

These items remain engineering work after the accepted owner decision.
Neither card is closed; there is no full production conformance pass and live
Flickr group additions remain disabled.

## Backup investigation resolved

On 2026-09-14, Terry accepted daily backup coverage as sufficient and directed
that the question be marked investigated and resolved. D1 automatic Time Travel
meets that frequency requirement. No separate daily export job is required;
the current-schema hosted restore/reconciliation proof remains part of #0018.
See the [accepted backup baseline](../operations/d1-backup-and-recovery.md).

Terry subsequently confirmed upgrading to Workers Paid on 2026-09-14. The
backup baseline now records the paid plan's 30-day Time Travel retention.

## Completed in the handoff run

- [Hosted current-schema restore](../evidence/hosted-current-schema-restore-2026-09-14.json):
  12 checks passed, all 37 tables compared, stale snapshot rejected, later blocks
  and revocations retained, restored guards enforced, write gates paused, and
  disposable database cleanup confirmed.
- [Independent process stop](../evidence/independent-process-stop-2026-09-14.json):
  forcibly terminated the owned Node/workerd process tree after a simulated POST
  handoff, then restarted from the same disk on both hint and sweep paths.
  The committed marker survived, recovery created a permanent block, and each
  case retained exactly one POST. This is local runtime evidence, not a claim
  to have killed a Cloudflare host process.
- Regression verification: 116 Python and 107 Node tests passed, plus native
  TypeScript, Ruff and changed-file Pyright. No live Flickr call was used.
- Prepared manual CI validation with pinned action commits and a fingerprint-
  checked canonical contract mirror. The known account variable is configured;
  the dedicated CI secret is absent. Component tests cannot satisfy its final
  full-conformance check by themselves.

The full production 56-case/28-mutation integration remains engineering work.
No new architecture waiver or backup-frequency decision is requested. Live
application writes remain disabled. All credential and data paths in the setup
handoff remain private; the board contains pointers only.

The first real GitHub validation run installed dependencies successfully and
stopped at the missing dedicated CI token, as recorded in the
[CI handoff receipt](../evidence/ci-credential-handoff-2026-09-14.json). All six
existing bounded crash mutations were also rerun: every unmutated control passed
and every mutant failed its intended behavioral assertion, with cleanup confirmed.
[Mutation evidence](../evidence/bounded-crash-mutations-2026-09-14.json). These six
mutants do not replace the complete required 28-class inventory.

## Final hosted rerun

The fresh hosted crash/restore probe completed **88 passing assertions**, including
all ten crash boundaries on hint and sweep paths, result classification, strict
manual-clock checks, SQL guards, a real Cron Trigger dispatch, and its bounded
archive checks. Both databases, the test Worker and its coordinator namespace
were cleaned up. [Sanitized hosted report](../evidence/hosted-crash-proof-2026-09-14.json).

The initial attempt failed the cron assertion under a two-minute deadline;
Cloudflare documents up to 15 minutes of Cron Trigger propagation. The harness
now allows that infrastructure window and records cron witnesses. A subsequent
attempt encountered an edge 404 after readiness. Ordinary exact-pair admission
now uses bounded retries with the same request body; race/fault admissions stay
single-shot. Both unsuccessful attempts were cleaned up. The final rerun passed.
These fixture readiness changes do not relax the dispatch freshness deadline.
[Provider cron propagation documentation](https://developers.cloudflare.com/workers/configuration/cron-triggers/).

At that checkpoint the two actionable cards reached Needs Terry for the CI token.
That credential handoff has since been resolved, as recorded below. #0019 remains at its existing registrar-date Blocked gate.
All changes and sanitized results are committed; unrelated generated-route edits
were preserved. No full conformance pass or live-write enablement is claimed.

## Credential handoff resolved; current resume point

Terry supplied the CI token on 2026-09-14. It was securely installed and verified.
After correcting Windows checkout line endings, the authenticated GitHub run
passed every implemented check and stopped at the still-missing complete release
evidence. The CI token is no longer a blocker; both cards are In Progress.
See [the authenticated CI receipt](../evidence/authenticated-ci-2026-09-14.json).

A separate disposable proof also verified Wrangler's supported remote D1 bindings:
a local Miniflare Worker wrote to real hosted D1, and an independent REST read
confirmed the value. Cleanup completed. This supplies a supported path for
independently killable workers against real D1 without requesting a new crash-
semantics exception. The local runtime date is explicitly 2026-07-30; it is not
being relabeled as the hosted 2026-09-11 runtime. Reproduction and boundaries are
in `probes/release/README.md` and `scripts/remote_d1_binding_proof.py`.

Next implementation: integrate the exact production artifact and real adapters
into the complete 56-case/28-mutation runner, then supply its evidence to the
last CI step. All previously listed native-generation, restore/reconciliation,
stop/restart and rate-budget requirements remain. No full release pass or live
Flickr write enablement has occurred.
