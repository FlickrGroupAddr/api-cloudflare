# Release CI credential handoff

Status: Needs Terry setup, 2026-09-14. The workflow is reviewable; it is not a
complete conformance runner or a release pass.

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

## Required owner input

Provide a dedicated Cloudflare API token for unattended FGA CI tests, restricted
to the FGA account. Use the name **FGA CI tests**. The complete planned native
release tests need these account permissions:

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

Save the token in a local text file, for example `C:\Temp\FGACICreds.txt`, and
provide its path. Do not paste it into a board comment or source file. On receipt,
install it as repository secret **FGA_CLOUDFLARE_CI_TOKEN**, verify the scoped
resource operations on disposable fixtures, and dispatch the prepared workflow.
The owner's existing preference permits a token without an expiration date.

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
