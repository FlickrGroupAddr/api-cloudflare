# Synthetic Actions secret ownership: provider evidence

Date: 2026-10-17. Ticket #0151. Status: research and offline design evidence;
current fixed-name lifecycle **NO-GO**. No provider experiment or qualification.

The documented GitHub interface cannot establish the existing packet's required
no-overwrite and exact-owned-delete properties. The simplest proposed response
is to remove temporary Actions secrets from this experiment, retain synthetic
values inside the private operator lifecycle, and review the resulting exact
packet. This is a design alternative, not an implemented orchestrator.

## Scope and authority

#0151 was confirmed In Progress through the shared localswim CLI before research.
Only public official documentation and repository source were inspected. No
account API, secret existence/value query, credential access, permission change,
provider mutation, native input or execution occurred.

The controlling preparation records are the
[execution packet](../operations/fixed-origin-execution-packet-2026-10-17.md),
[authorization disposition](../operations/fixed-origin-authorization-disposition-2026-10-17.md),
and [offline lifecycle](../operations/fixed-origin-lifecycle-2026-10-17.md).
The packet has two repository Actions secret names:
`FGA_FIXED_ORIGIN_CAPABILITY` and `FGA_FIXED_ORIGIN_CANARY`.
It requires absence, one creation, and deletion only of acknowledged owned
identities. `scripts/fixed_origin_lifecycle.py` is an offline test seam;
its local SQLite latch and exclusive marker cannot constrain another provider
client. Neither the source model nor this research provides a live adapter.

## GitHub's documented interface

Official pages retrieved on 2026-10-17; no authenticated request was made.
The `apiVersion=2022-11-28` query was requested, but the rendered examples use
`X-GitHub-Api-Version: 2026-03-10`. This research does not silently pin either
version for a future adapter. That adapter must select a supported exact version
and bind its reviewed behavior to the final packet.

| Interface | Documented semantics relevant here |
| --- | --- |
| Repository secret GET | Metadata includes name and creation/update times; no secret value or immutable secret-generation identity. |
| Repository secret PUT | `PUT /repos/{owner}/{repo}/actions/secrets/{secret_name}` creates or updates. Body contains encrypted value and public-key ID; 201 means creation, 204 update. |
| Repository secret DELETE | Deletes by repository and secret name; 204 acknowledges deletion. |
| Repository permission | Fine-grained metadata retrieval needs repository Secrets read; PUT/DELETE need Secrets write. Classic tokens use `repo`. |
| Environment secrets | Same create-or-update and name-delete shape in an environment namespace; fine-grained Environments read/write permissions. |

Source: [GitHub Actions secrets REST reference](https://docs.github.com/en/rest/actions/secrets?apiVersion=2022-11-28#get-a-repository-secret),
[PUT](https://docs.github.com/en/rest/actions/secrets?apiVersion=2022-11-28#create-or-update-a-repository-secret),
[DELETE](https://docs.github.com/en/rest/actions/secrets?apiVersion=2022-11-28#delete-a-repository-secret),
and [environment PUT](https://docs.github.com/en/rest/actions/secrets?apiVersion=2022-11-28#create-or-update-an-environment-secret).

GitHub documents ETag/Last-Modified conditional GET for caching. Its general
rule explicitly excludes conditional unsafe methods (POST/PUT/PATCH/DELETE)
unless a particular endpoint documents an exception. The secret endpoints
above document none. `If-None-Match: *` is therefore not a supported create-only
contract here; `If-Match` is not a supported generation-conditional delete.
A successful cached GET would still not lock a later mutation.
[GitHub REST best practices](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api#use-conditional-requests).

GitHub's concurrency groups serialize participating jobs/workflows sharing that
group. They do not document exclusion of UI operators, direct REST clients or
jobs outside the group. Therefore adding `concurrency:` would coordinate
cooperative runners, not make secret PUT/DELETE ownership conditional.
[GitHub workflow concurrency](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency).

## Safety conclusion and adversarial cases

These are deductions from the documented interface, not observations of hosted
behavior or claims about undocumented implementation internals.

1. Our absence read completes; another writer creates the same name; our PUT
   updates that writer's secret. Seeing 204 afterward detects the overwrite
   only after it happened. Refusing later cleanup cannot undo it.
2. Our create returns 201; another writer replaces the same name; our DELETE
   removes the replacement. The earlier create receipt identifies a historical
   operation, not the current generation.
3. Another writer deletes/recreates between our metadata check and deletion.
   Comparing timestamps or an ETag before DELETE leaves the same race; there is
   no documented conditional mutation to close it.
4. A PUT/DELETE acknowledgement is lost. A name lookup cannot establish which
   generation remains. Do not retry or adopt/delete the current name as ours.
5. A second local lifecycle is excluded by the journal marker while a foreign
   writer remains unconstrained. Local success is not provider-wide exclusion.

Random per-run names reduce accidental collision; they do not turn an upsert
into create-only. A comment, owner nonce inside an unreadable secret, two extra
GETs, or an assumed human quiet window also provides no provider-side fence.
The offline adversarial model is [scripts/secret_ownership_model.py](../../scripts/secret_ownership_model.py)
with [tests/test_secret_ownership_model.py](../../tests/test_secret_ownership_model.py).
It enumerates independent-writer insertion at each local operation gap, labels
test-oracle lineage as unavailable to the real client, and exercises the
zero-Actions-operation alternative. These tests demonstrate counterexamples;
they cannot qualify GitHub or the private runtime/native handoff.

## Concrete options and operational cost

| Option | Scope, cleanup and consequence |
| --- | --- |
| Keep shared fixed names | Requires a real writer-exclusion mechanism spanning every capable provider writer for the entire create/use/delete interval. None is supplied by these APIs. A cooperative lock or owner promise is insufficient. Retain NO-GO. |
| Per-run names in the existing repository | Same repository Secrets-write authority, plus dynamic workflow selection and cleanup by name. Lower collision probability supplies neither generation ownership nor exact deletion. Reject as a proof. |
| Isolated GitHub environment | Adds an environment and two environment secrets; environment creation/deletion require repository Administration write, while secret operations need Environments write. Environment PUT itself creates or updates; deletion addresses its name. Required reviewers gate workflow consumption, not secret writers. Needs separately established exclusive administrative ownership, workflow/job selection, and environment/secret cleanup; not a turnkey solution. |
| Dedicated repository owned exclusively by an experiment identity | Could narrow the ownership boundary if actual access is proven and held, but adds repository administration, workflow/artifact transfer, trust and deletion. Administrator intervention and unknown operations still require reconciliation. No such resource or exclusion proof exists in this batch. |
| No temporary Actions secret storage (recommended proposal) | The operator orchestration holds fresh synthetic capability/canary privately and supplies only the exact reviewed runtime/native handoffs. Zero GitHub secret metadata/PUT/DELETE operations; no new GitHub Secrets, Environments or Administration permission. Removes this provider race rather than claiming it solved. Local handoff security and provider runtime cleanup remain required engineering work. |

Environment facts: [create/update and delete environment API](https://docs.github.com/en/rest/deployments/environments#create-or-update-an-environment).
Consumption/reviewer distinction: [GitHub secrets concepts](https://docs.github.com/en/actions/concepts/security/secrets#how-secrets-work).

The concrete inventory, value handling and failure contract for the recommended
option are in the canonical
[Proposed alternative](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/proposals/synthetic-secret-ownership-alternative-2026-10-17.md).
It changes only the Proposed experiment packet; it does not waive a production
requirement or grant live authority. Until reviewed implementation, secure
handoff and exact cleanup evidence exist, #0046 remains gated. #0044 NO-GO,
#0037 unqualified and #0043 negative provider-restoration evidence remain.
