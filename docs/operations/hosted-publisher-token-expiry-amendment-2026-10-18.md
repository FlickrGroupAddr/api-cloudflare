# Hosted publisher: separate provider-token expiry from caller authority

Date: 2026-10-18. Ticket #0134. Status: **Accepted scoped test amendment; successor implementation #0173
independently reviewed; no credential or execution authority**.

## Owner acceptance

On 2026-10-18 Terry answered **"Accept the scoped amendment (recommended)"**
to the exact proposal at API commit `db1012d`. The decision reference is
`call_db0854bafa8748aca10153fc4d4a8a7b`. This explicitly accepts the one-attempt
longer-provider-lifetime tradeoff below while retaining all short caller limits.
It authorizes successor code and synthetic tests only. It grants no issuance,
credential access, account request, cloud/native action or final run permission.
Completed source cards and their historical artifact pins remain unchanged.

## Problem and existing rule

Terry confirmed the custom-token form still offers Workers Scripts/Edit and
D1/Edit for the selected account. He reports its Today selection as the local
day through 23:59 EDT. This is owner-reported UI interpretation, not a collected
provider grant receipt or verified UTC expiry. No token was created, read or used.

The pre-amendment accepted source's
[`validate_operator_grant`](../../scripts/hosted_publisher_operator_plan.py)
rejects a provider grant whose `expires_at` exceeds the plan's
`cleanup_deadline`. The plan permits at most four hours and the concrete provider
adapter separately imposes its existing two-hour lifetime. Consequently a token
lasting through this evening cannot support a run now under the current rule.
Do not replace its real expiry with the caller deadline merely to pass validation.

The [private packet procedure](hosted-publisher-private-packet-preparation-2026-10-18.md)
records the existing rule and unresolved expiry controls. The
[accepted Beta/source handoff](hosted-publisher-beta-integration-2026-10-18.md)
and [caller procedure](hosted-publisher-execution-caller-2026-10-18.md) otherwise
retain their exact authority, resources, budgets, custody and cleanup conditions.

## Accepted one-attempt amendment

For one newly reviewed disposable hosted-publisher qualification packet only:

1. Record the actual provider grant's independently supported issue and expiry
   timestamps separately from the caller's dispatch and cleanup deadlines. Keep
   ambiguous or unverifiable provider timing unavailable; owner-reported date
   text alone does not authenticate provider policy. Never label a shorter local
   deadline as the actual provider expiry.
2. Permit provider expiry later than cleanup only if it is finite, no more than
   24 hours after actual issue, and no later than **2026-10-19 00:00 EDT
   (04:00 UTC)** for the token currently being prepared. This is a maximum
   permitted ceiling, not an assertion that Cloudflare's date field produces it.
   An actual earlier provider expiry controls. A different day or later ceiling
   requires a new scoped owner decision.
3. Keep every existing caller, phase, case, provider-adapter and cleanup deadline
   and request/byte/SQL ceiling. Effective dispatch ends at the earliest applicable
   caller, provider-token or case deadline. The longer provider validity grants
   no additional request, cleanup replay, second attempt or unattended run.
4. Require Terry as the named revoker, using the independent Cloudflare console,
   to revoke the token promptly after approved cleanup. Emergency stop follows
   the reviewed stop/revocation sequence; inability to clean up or revoke is an
   explicit residual, not permission to extend deadlines or replay mutations.
5. Preserve exact-account scope, the reviewed Workers/D1 permission set, fresh
   token/custody/fingerprint bindings, exclusive operator, immutable candidate,
   exact owned-resource receipts and separately approved execution/cleanup.
   No production data, Flickr, native work, broad Admin template, token-creation
   API or global API key is added by this amendment.

## Concrete expiry evidence gate

Before any authorized issuance, review the non-secret console summary and
independently supported provider expiry controls against the finite ceiling.
If their timezone/expiry semantics remain ambiguous, do not issue a token under
this proposal. This pre-issuance check concerns the proposed policy, not an
already-created token. After separately authorized issuance, retain the actual
grant's issue/expiry and effective permission evidence privately before use;
unavailable or conflicting actual metadata keeps execution NO-GO. Neither the
local caller deadline nor a fabricated timestamp can fill missing evidence.

## Explicitly accepted lifetime tradeoff

The provider token can remain usable outside the finite caller window until
confirmed manual revocation or its actual provider expiry. The caller's local
refusal does not revoke that account-level Workers/D1 capability or prevent its
use through another client. A failed or delayed revocation leaves this exposure
for the remaining token lifetime, up to the ceiling above. Account-level create
authority still reaches resources beyond the four intended synthetic pairs at
the provider policy layer; the reviewed caller limits its own operations only.

Terry selected this limited lifetime tradeoff with the short caller limits and
prompt manual revocation. The unselected alternative was to retain
the current expiry-by-cleanup rule and use a provider grant with sufficiently
precise earlier expiry, or schedule a later run whose approved window actually
contains the existing grant expiry. No alternative token-creation authority is
approved by mentioning it.

## Implementation and action gates

Acceptance authorizes the scoped successor source change and synthetic tests
under #0173, not token issuance, credential reads, account access or execution. Keep
Completed #0155/#0162/#0165 and their original committed/private artifacts intact.
A new implementation card/revision must own any current validator/caller changes;
do not rewrite their old packets or silently use changed bytes under old pins.
Prefer the small explicit policy change over a duplicate transport framework.

Independently review actual issue/expiry preservation, finite ceilings, early
provider expiry, stop/revocation and dispatch/cleanup boundary cases. Then pin
the new committed source closure and prepare the actual private packet. Its
grant evidence, custody, network, owners, windows and fingerprint remain required.
Only the later concrete owner provisioning and exact-run decisions can authorize
token creation/use and provider work. Until independently reviewed successor source and an actual bound packet are
ready, the old source continues to refuse an end-of-day token for a run now.

## Observation and verification boundary

This proposal is based on the screenshot, Terry's expiry clarification and
tracked source inspection. No account API, provider-time verification, credential,
token, private record, cloud mutation or native input was used. Documentation
checks and independent High review passed before the owner decision; the
expiry-evidence gate was re-reviewed with no remaining findings. A source change
or synthetic test cannot retroactively authenticate a grant's actual policy.

## Reviewed successor interface — #0173

The new revision changes only the shared `validate_operator_grant` policy and
adds its regression module. No transport, preparer, candidate Worker, migration,
caller deadline or historical packet is rebuilt or changed. All grant admission
paths continue to use this validator. Existing source manifests already include
the shared module; reprepare the runtime packet against the new committed source
and independently retain its new digests before an actual decision. Old pins
cannot bless changed source.

Without `expiry_policy`, the existing `expires_at <= cleanup_deadline` rule
remains. An exception grant must contain this exact additional closed object:

```json
{
  "expiry_policy": {
    "amendment_id": "hosted-publisher-token-expiry-amendment-2026-10-18",
    "decision_id": "call_db0854bafa8748aca10153fc4d4a8a7b",
    "plan_digest": "<the exact independently retained plan digest>"
  }
}
```

The real grant issue/expiry fields are unchanged. This branch requires the
plan's named revoker to be `Terry Ott`, plus the accepted 24-hour and absolute
UTC ceilings. A present but invalid/foreign/extra-field policy refuses; it does
not fall back to a permissive path. Provider grant expiry still clamps remaining
authorization, while earlier caller/case/cleanup/approval and adapter deadlines
remain independent. Consent, credential fingerprint, source/packet/grant evidence,
stop, cleanup authority and single-use journal checks remain required.

The policy object selects a reviewed rule and binds supplied metadata. Its
strings, the revoker name and a digest do not authenticate human identity,
provider effectiveness or metadata provenance. Existing exact owner decisions
and independently retained grant evidence establish those externally. The
single-use claim/journal prevents the supported exact invocation's replay; this
change does not establish universal single use across forged independent
packets or operators. Only one actual packet/attempt is authorized by this
scoped amendment.

Source verification and independent High review use synthetic inputs only.
No token, account request, endpoint qualification or actual private runtime
packet exists from these checks. The attempted historical-metadata/DNS staging
was rejected by automatic approval review before execution: code/tests approval
does not cover reading those private identities and disclosing derived names to
DNS. That separate preparation scope still needs explicit approval, alongside
the earlier token-policy, provisioning and exact-run gates.

## Calendar interpretation and later metadata collection

The subsequent console summary confirmed the selected account and two Edit
permissions, with October 18 for both start and end; it displayed no time or
timezone. On October 18 the parent rechecked Cloudflare's
[current TTL documentation](https://developers.cloudflare.com/fundamentals/api/how-to/restrict-tokens/):
selected dates are documented as 00:00 UTC. By that documented rule an October
18 end date has passed; October 19 maps to October 18 at 20:00 EDT, earlier than
the accepted 04:00 UTC maximum. Terry was directed back to the form to correct
the end date and stop at summary. This mapping is documentation-based, not an
observation of a newly issued token's actual policy.

The [Verify Token response](https://developers.cloudflare.com/api/resources/user/subresources/tokens/methods/verify/)
can report `expires_on` and `not_before`; it does not establish every effective
permission or actual issue time. `not_before` is a validity boundary, not an
issue timestamp. The separate
[Token Details response](https://developers.cloudflare.com/api/resources/user/subresources/tokens/methods/get/)
documents `issued_on`, `expires_on` and policies, but using it would require its
own independently reviewed authority and credential path. No token verification
or details request is authorized or performed by this source handoff. Never
broaden token permissions or substitute validity-start for issue time to fill
the evidence gap.

## Final source verification (before subsequent metadata approval)

For #0173, all 13 new synthetic amendment tests and 66 existing operator,
execution, preparer and provider regression tests passed. The first author
invocation also named a nonexistent test module; the corrected 66-test command
completed cleanly without source changes. The parent independently ran 29 new
amendment/default-plan boundary tests. Fresh High source review passed, including
seven independently executed boundary cases and inspection of the unchanged
caller/cleanup/fingerprint/journal paths. No actionable findings remained.

Ruff checks, format checks, Pyright and the pinned native TypeScript compiler
passed. Final accepted-document/preparation-scope review passed. These are local
source/synthetic results only: no token creation/read, account API, hosted case,
private namespace/DNS staging or native action occurred. The rejected staging
directory was confirmed absent; that preparation still awaits explicit approval.

## Subsequent approved private preparation

Terry explicitly approved the pinned historical metadata read and five DNS
resolution operations in decision `call_220ec44519d24316a4334ce1830a222d`.
Those operations completed: four fresh intended Worker/D1 pairs were staged,
all five endpoint roles resolved, and no credential or account API was accessed.
The resolver received the derived hostnames under that approval. These are five
resolution operations, not a claim about the resolver's DNS wire-query count.
Historical account provenance remains historical; successful DNS is not an
observed Worker deployment or current token policy.

The initial runtime-draft assembly was separately stopped by automatic approval
review over retained-artifact access/scope. A check of tracked public Git paths
and the prior sanitized verification receipt established that all 113 artifact
inputs are the public candidate source at `aca532af6d570125c5d8bbcbd6ac1b4a10ae74f7`;
the 652,967-byte compiled bundle already matched published pins. No denied
private read occurred in that check. The same assembly action was then allowed
under Terry's earlier explicit "Prepare it with me now" request and approved
metadata inputs. No alternative execution route or credential access was used.

The actual private NO-GO runtime draft was created and byte-verified against
source `3e64a2d13b845f46abf2b96aef5e8c4cd9342faf`. Fresh High private-draft review
passed 26 targeted checks: 17 staged public source files, namespace relationships,
recorded global numeric DNS selections, independent pins and the finite budgets.
The proposed October 18 window is 13:00–13:30 EDT for dispatch and 15:00 EDT for
cleanup; **it is not approved**. Do not use it after expiry or silently move its
timestamps. Source acceptance, actual grant/credential/fingerprint evidence,
exclusive owner control, stop binding, custody and separate run/cleanup authority
remain unresolved. No resources were created, no endpoint was invoked and no
token was issued or read.

Private retrieval: under the operator's existing `private-evidence` root, use
`0134/publisher-expiry-oct18-staging`. Its namespace/DNS draft, runtime packet,
separately retained packet pins and private action sheet stay outside Git and
must not be dumped to chat/logs. The staging directory's ACL preflight found
additional allow rules outside the credential reader's trusted set; no credential
may be delivered there without an approved protected child or other reviewed
delivery location. File/parent custody remains unqualified; no ACL was changed.

The smallest remaining grant-evidence decision is an owner-mediated exact
metadata handoff from the existing console if its normal view/export actually
exposes issue/expiry/full policy, or a separately authorized one-resource Token
Details read with an API Tokens Read credential. No such ordinary console export
was demonstrated; do not promise one or request a HAR/creation response containing
secrets. Do not broaden the Workers/D1 test token, add API Tokens Write, use a
global API key or treat `not_before`/a guessed creation interval as actual
`issued_at`. A separate metadata reader would have broader user-token metadata
capability than this caller's one permitted GET and needs an explicit owner
choice plus a bounded reviewed preparation/action scope. Its token value would
remain private and revocation would be separately accounted for.
