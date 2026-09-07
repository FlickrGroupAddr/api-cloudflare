# Flickr credential backing-store recommendation

Date: 2026-09-07

Status: Terry approved the disposable AWS proof on 2026-09-07. Production
adoption and unattended identity remain proposed. No service has been
provisioned by this review, and no live credential test has run.

Approval handoff: AWS credentials are unavailable until Terry returns to his
laptop. [Local protocol preparation](../../probes/secrets/README.md) can proceed
without them. This approval covers synthetic proof work and does not silently
approve long-lived production keys or production credential deletion.

## Recommendation in plain language

Keep the FGA API backend and workers on Cloudflare. Evaluate AWS Secrets Manager
for the dynamic Flickr token/token-secret pair, using a **separate secret object
for each credential generation**, with one initial immutable version. Store the
complete object ARN and exact `VersionId` in the FGA database. Do not use a
mutable current-version label to decide which credential is authorized.

This is a proposed AWS backing-service choice under accepted architecture
[ADR 0050](https://github.com/FlickrGroupAddr/architecture-design/blob/705e9dacf0ae65b2e2039476bef8270c9b12ee71/docs/decisions/0050-select-cloudflare-and-evaluate-native-storage-first.md),
not a change of compute platform or database selection. The governing
[ADR 0017](https://github.com/FlickrGroupAddr/architecture-design/blob/705e9dacf0ae65b2e2039476bef8270c9b12ee71/docs/decisions/0017-explicit-oauth-and-account-lifecycle.md)
and [OAuth lifecycle contract](https://github.com/FlickrGroupAddr/architecture-design/blob/705e9dacf0ae65b2e2039476bef8270c9b12ee71/docs/oauth-and-account-lifecycle.md)
remain unchanged. This recommendation covers dynamic Flickr grants, not every
deployment secret, browser signing key, or installation credential.

An exact version is like a numbered sealed envelope. The FGA database says which
envelope is authorized; the managed store supplies precisely its contents. If
relinking stages envelope B while A is active, nothing starts using B until the
database transaction switches the reference. A failure before that switch leaves
A active; a stale failure from A cannot invalidate B after the switch. A mutable
secret name would let its contents change independently of that transaction.
Version selection alone does not authorize a Flickr operation: current link
state, revision and the applicable write gates still control every operation.

## Current native evidence

Rechecked the documented Cloudflare surfaces on 2026-09-07. A Secrets Store
Worker binding specifies a store and secret name, and its runtime `get()` takes
no version selector. Editing the secret replaces its value for all consumers.
Those interfaces do not expose an immutable version chosen dynamically by the
FGA database. This is an inference from documented interfaces, not a failed
hosted experiment. Reconsider it if those interfaces change.
Sources: [binding/runtime API](https://developers.cloudflare.com/secrets-store/integrations/workers/),
[edit operation](https://developers.cloudflare.com/secrets-store/manage-secrets/how-to/),
[management API](https://developers.cloudflare.com/api/resources/secrets_store/).

| Option | Fit and cost of making it fit |
| --- | --- |
| Secrets Store mutable binding | Simple native access, but does not meet exact dynamic version selection. |
| A new native secret name for every relink | Requires new bindings and deployment coordination for each credential change; unique names do not make provider values immutable. |
| Worker versions for credential history | Selects a deployed program/configuration, not a database-selected secret version within a request. |
| D1, Durable Objects or KV as a credential vault | Ordinary storage is not the accepted versioned managed-secret lifecycle; adding application encryption and key rotation would reopen the accepted boundary. |
| A custom native secret broker | Could introduce its own immutability and access policy, but would add a security service to build, audit and recover. Not recommended over the conventional managed-store fallback. |
| AWS Secrets Manager | Has immutable version lookup. Use independent objects to address the deletion limitation below; identity and actual hosted lifecycle remain proof gates. |

Cloudflare's current management guide describes an open beta with 100 production
secrets per account and one store; management reads do not return secret values.
Neither a larger quota nor a management API token repairs the selector gap.
[Native limits and value-access boundary](https://developers.cloudflare.com/secrets-store/manage-secrets/).
No unverified future paid-tier price is assumed. The native option loses on the
required lifecycle before price decides the comparison.

## AWS correction: version reads are not version deletion

AWS permits an exact `GetSecretValue` request and prevents changes to an existing
version's bytes. Omitting a version selector defaults to the current label,
which the proposed FGA adapter must reject locally.
[GetSecretValue](https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html),
[PutSecretValue immutability](https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_PutSecretValue.html).

The earlier architecture secret-store comparison established the read selector
but did not establish the complete cleanup lifecycle. AWS cannot directly delete
an individual version. Removing labels merely makes it eligible for background
collection. That is insufficient evidence for the contract's confirmed deletion.
Deleting the whole secret is a separate supported operation.
[DeleteSecret](https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_DeleteSecret.html).

Proposed mapping: create a fresh secret object with one initial version for each
verified grant. Keep token and token secret together. The initial version has an
idempotency identifier; retain its exact returned ARN/version, never infer them
from a label. Activate with the existing database compare-and-set, then delete
the old object. No ordinary `PutSecretValue`, label movement, automatic rotation,
or Worker deployment is needed for a Flickr relink.
[CreateSecret](https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_CreateSecret.html).

Propose deletion without a recovery window for these disposable credential
objects, **only after durable authority removal**. It is irreversible and AWS
still completes it asynchronously. A successful delete request is not completion:
keep cleanup pending until the exact object is confirmed absent and reads fail.
Access denial or a timeout alone does not prove deletion. Retain `disconnecting`
and the existing deletion-pending UI while uncertain. This approach preserves
the accepted contract; any proposal to call a recoverable scheduled deletion
`deleted` instead would require explicit contract review.
[Deletion lifecycle](https://docs.aws.amazon.com/secretsmanager/latest/userguide/manage_delete-secret.html).

## Identity, network and runtime boundaries

Cloudflare Workers can call external HTTPS APIs. A maintained SigV4 client is the
candidate signing mechanism; Cloudflare documents `aws4fetch` in its R2 examples.
That establishes a runtime-compatible approach, not a Secrets Manager integration
pass. Verify stable version, license, dependency lock, native TypeScript 7 build
and hosted requests before adding a dependency.
[External services](https://developers.cloudflare.com/workers/configuration/integrations/external-services/),
[aws4fetch example](https://developers.cloudflare.com/r2/examples/aws/aws4fetch/).

AWS recommends temporary role credentials. This review found no verified native
Workers workload identity that can simply assume an AWS role. STS still needs a
trusted starting identity; CI OIDC credentials are not an unattended Worker
identity. Roles Anywhere uses certificates and a CA, and its documented helper
is an external executable. Adopting it here would require a separate Workers
integration and certificate lifecycle proof.
[AWS identity guidance](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html),
[non-AWS roles](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_common-scenarios_non-aws.html),
[Roles Anywhere helper](https://docs.aws.amazon.com/sdkref/latest/guide/access-rolesanywhere.html).

The concrete simple private-deployment candidate is a dedicated AWS access key
per FGA component, held in that component's Cloudflare secret binding. This is
an explicit long-lived bootstrap credential tradeoff, not keyless federation.
Do not share deployment/admin AWS keys with runtime code. For the first bounded
proof, prefer operator-issued short-lived credentials so testing does not create
an unattended long-lived identity. Production bootstrap acceptance is a separate
part of the owner choice below; a temporary probe token does not prove renewal.

The proposed policy boundaries are:

| Identity | Candidate authority, to be verified with denial tests |
| --- | --- |
| FGA refresh/group-submission workers | Exact-value reads within the private deployment's Flickr-grant namespace; no create, delete, list, label or policy management. |
| FGA API backend credential lifecycle | Create/read/describe/delete within that namespace, including required creation tags; no IAM, KMS administration, replication, policy or label management. |
| Deployment/operator identity | Provision and rotate runtime identities; remain separate from ordinary request handling. |

Use one configured AWS region and account, complete ARNs and constrained names;
reject caller-supplied endpoints and references outside that boundary. Runtime
resource permissions alone cannot determine which generation the database has
activated; the FGA adapter must enforce that decision. An API backend able to
delete grants is intentionally more privileged than a read worker. Compromise
of a permitted reader can disclose the grants it can read; encryption at rest
does not prevent that. Prove IAM and any KMS permissions from actual policies,
not from the word "managed."
[IAM examples](https://docs.aws.amazon.com/secretsmanager/latest/userguide/auth-and-access_iam-policies.html).

Use the regional public HTTPS endpoint with verified TLS and signed requests;
no inbound AWS listener or RDS firewall change is needed for this proposal.
This is cross-provider traffic, not a private VPC path. Do not invent a fixed
Workers egress IP allowlist. A private-network requirement would reopen the
network design. Choose the region with owner/account context and measure it.
[AWS regional endpoints](https://docs.aws.amazon.com/general/latest/gr/asm.html).

## Rotation, failures, recovery and cost

Flickr grant rotation remains the accepted owner relink ceremony. AWS automatic
rotation cannot invent a replacement Flickr OAuth grant. Rotate AWS bootstrap
keys separately: provision a replacement, deploy its scoped binding, prove the
new identity works, deactivate the old key and verify rejection, then retire it.
A rollback must not restore an old Flickr reference or require a retired key.

Keep Flickr values only in operation-local memory. Do not adopt generic secret
caching advice that would weaken the accepted lifecycle. Fetch the selected
version before the time-critical Flickr moderation preflight. A secret-store
failure prevents dispatch; it is not proof of Flickr revocation. Use bounded
deadlines and backoff for safe reads. AWS documents eventual consistency, so a
new version may be temporarily unavailable: never substitute an older grant.
[AWS consistency guidance](https://docs.aws.amazon.com/secretsmanager/latest/userguide/troubleshoot.html).

Retain opaque staging/cleanup references durably so a lost create response, lost
activation response, failed compare-and-set, or process crash can be reconciled
without duplicate activation or deleting an active object. Resolve an uncertain
database outcome before cleanup. A restored database may reference a deleted
grant: remain fail-closed and require owner relink rather than restoring token
bytes or erasing safety history. Do not add secret exports, replicas or backups
that silently defeat deletion. AWS and Cloudflare availability both become
dependencies; latency and outage behavior have not been measured.

AWS's published example rates are $0.40 per secret-month, prorated for shorter
storage, plus $0.05 per 10,000 API calls. At those rates, one grant object and
10,000 calls cost about **$0.45/month**; keeping two objects for a whole month
would be $0.85 with the same call count. These are arithmetic examples, not
traffic forecasts or the total deployment bill. Include additional static
secrets, retries, Cloudflare execution, logging, network and any chosen
customer-managed KMS key costs in a regional estimate before rollout.
[AWS pricing](https://aws.amazon.com/secrets-manager/pricing/),
[managed versus customer-managed key cost](https://docs.aws.amazon.com/secretsmanager/latest/userguide/intro.html).

## Owner choice and bounded proof

Recommend accepting AWS Secrets Manager as the **candidate to prove**, with one
object per grant generation and exact ARN/version reads. Terry must separately accept
or reject the long-lived scoped bootstrap-key tradeoff for unattended production
and irreversible cleanup of inactive grant objects. No live provisioning follows
from this document alone. If long-lived keys are unacceptable, investigate a
supported temporary-identity route before production adoption; do not silently
introduce a custom credential broker.

After approval, the disposable synthetic proof must cover:

1. Actual Workers-to-AWS exact reads; missing/wrong version and unexpected
   account/region references fail closed, with no current-label fallback.
2. Stage/activate/cleanup races and lost responses, with immutable fixture
   generations and a modeled database compare-and-set. Distinguish that model
   from a production database-adapter pass.
3. Reader denial of writes/deletion/other namespaces; lifecycle denial of IAM
   and policy changes; expired or revoked AWS identity failure without leakage.
4. Whole-object asynchronous deletion and confirmed absence; unavailable
   cleanup, database restore with a missing grant, and durable orphan recovery.
5. Cold/warm latency, throttling and outages, operation-local secret retention,
   bootstrap replacement and sanitized logs/artifacts. No real Flickr request.

Track these as continuing work on implementation ticket #0009; database recovery
integration also depends on the selected-store work. If the candidate fails,
retain the exact failed requirement before evaluating another store. Migration
would stage a newly verified grant in that store and switch through the same
accepted lifecycle, not copy plaintext into a database or reactivate history.

Review validation: controlling local ADR/contract read; primary provider
interfaces rechecked on the date above; repository-relative links and Markdown
whitespace checked. Documentation-only work; no code, dependency, resource,
secret, identity, database, or production conformance change.
