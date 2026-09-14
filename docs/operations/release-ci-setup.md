# Release CI credential handoff

Status: Credential setup resolved and verified in GitHub Actions, 2026-09-14.
The full conformance runner remains incomplete; there is no release pass.

## Prepared

`.github/workflows/release-validation.yml` is manual-dispatch only, uses pinned
action commits and locked project dependencies, and grants GitHub contents-read
permission only. It runs compiler/generated-API checks, Python/Node regressions,
independent process-stop tests and a disposable hosted restore. Its final verifier
continues to fail unless the complete exact-artifact evidence is supplied.
No step deploys the live application or enables Flickr writes.

`FGA_CLOUDFLARE_ACCOUNT_ID` is configured as a repository variable for the approved
account. A byte-for-byte, fingerprint-checked public contract mirror removes any
need to grant CI access to the private architecture repository. Private run
folders and provider/credential logs are never uploaded as public artifacts.

## Configured credential

Terry supplied the dedicated **FGA CI tests** token locally on 2026-09-14. It
was verified active, checked against the intended account APIs, and installed as
**FGA_CLOUDFLARE_CI_TOKEN** through encrypted GitHub secret storage. No value was
printed or committed. The planned native release tests use these account permissions:

| Permission | Purpose |
| --- | --- |
| D1 Edit | Create, migrate, query, restore and remove isolated test databases |
| Workers Scripts Edit | Deploy and remove isolated test Workers and their native coordinator resources |
| Secrets Store Edit | Provision and retire synthetic native credential fixtures |

The currently wired hosted restore step uses D1 Edit. The other permissions are
for the remaining full native runner, not access to unrelated zones. DNS or zone
editing permission is unnecessary. Existing project token files supply only
Secrets Store editing or zone reads; they cannot provide this combined CI scope.
The local Wrangler operator login is not installed as a CI credential.

The account variable and dedicated token are configured. The authenticated CI
run successfully created, migrated, restored and deleted disposable D1 databases.
No further credential action is currently required from Terry. The owner's
existing preference permits a token without an expiration date.

## Work remaining after credential setup

The full 56-case/28-mutation production runner is still incomplete. Combine the
production authentication, admission, OAuth transport, allocator, native lifecycle,
status and administrative-repair paths with the infrastructure proofs. Complete
the full independent-stop/deployment-restart matrix and post-backup reconciliation,
including native secret generations. Bind all evidence to the optimized production
artifact and exact schema; then wire generated evidence into the final CI verifier.
The prepared workflow intentionally cannot promote from the component tests alone.

The standalone process-stop proof currently uses a compiled coordination harness
with the production attempt implementation; it is not yet the full production
artifact/transport integration. The hosted restore compares a complete frozen
recovery snapshot and rejects older snapshots. It does not merge missing facts
from an unavailable recovery source or assert that secret generations were tested.

No additional architecture exception is requested. These are explicit remaining
implementation tasks in #0018, whose completion also controls rollup #0002.

## Verified CI setup boundary

The first real [GitHub Actions run](https://github.com/FlickrGroupAddr/api-cloudflare/actions/runs/34859438245)
at commit `42ffb00` successfully checked out the repository, configured Node/uv,
and installed locked dependencies. It failed at the dedicated-credential check
with exactly `FGA_CLOUDFLARE_CI_TOKEN` missing; the account variable was accepted.
No hosted resource operation or release verification ran in that failed CI job.
The [sanitized receipt](../evidence/ci-credential-handoff-2026-09-14.json) records
that concrete boundary. Workflow syntax and dependency installation have therefore
been exercised on the actual GitHub runner, not only inspected locally.

## Authenticated validation result

[Run 34861968320](https://github.com/FlickrGroupAddr/api-cloudflare/actions/runs/34861968320)
at `e4bf83d` passed credential preflight, compilation/generated API checks,
Python and Node regression suites, independent process-stop checks, and the
hosted current-schema restore with cleanup. The overall run is intentionally
**failed** at the final complete-evidence check: the 56-case/28-mutation release
runner is still unfinished. That is implementation work, not a credential issue.
[Sanitized result](../evidence/authenticated-ci-2026-09-14.json).

The first authenticated run exposed CRLF conversion of the reviewed contract
mirror in a Windows checkout. `.gitattributes` now keeps detected text files as LF
without altering binary files. A real Git checkout test with `core.autocrlf=true`
proves the reviewed fingerprint survives; the fingerprint check was not relaxed.

## Current execution hold (2026-09-14)

The dedicated token still works. Automatic approval review rejected the integrated
FP-BLOCK-003 snapshot import even after adding fresh-target identity/emptiness and
synthetic-source checks. Do not dispatch this workflow as an indirect way to run
that rejected operation. Obtain specific owner approval to copy synthetic snapshots
between newly created empty test D1 databases, then resume the integrated proof.
This is a tool execution authorization handoff, not a new Cloudflare permission,
architecture decision, or request to restore production.

The production matrix now exercises 55 stable IDs across component runs, including
real hosted D1 core cases, native Secrets Store disconnect/relink/rotation, and the
complete independent local process-stop boundaries. The full 28-class mutation
runner, integrated restore, one-candidate provenance receipt and CI wiring remain
incomplete. See [the current checkpoint](../research/2026-09-14-production-matrix-handoff.md).
The final release verifier remains mandatory and cannot consume partial reports.
