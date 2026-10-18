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

## Current form values — expanded picker correction

The later October 18 screenshot expands the dashboard picker and explicitly
shows **Eastern Daylight Time**, a start of October 18 at 00:00 and an end of
October 19 at 23:59. It also confirms the separate **User / API Tokens / Read**
row. This is a date-time control, not the date-only behavior inferred from the
generic documentation. The parent's earlier advice to move the end date to
October 19 was wrong for this UI and was corrected before issuance.

For **both** token forms, use **October 18, 2026 at 23:59 EDT**, Apply, then
stop at summary. Do not carry the October 19 end-date inference below into this
control. This displayed proposed expiry is within the accepted October 19
00:00 EDT maximum; its actual provider expiry remains unverified until the
later approved metadata read. No token creation or use was authorized by the
screenshot. The metadata reader's broader token-metadata capability still needs
the separate explicit setup/read decision.

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

## Earlier calendar inference (superseded for the expanded picker)

The earlier console summary confirmed the selected account and two Edit
permissions, with October 18 for both start and end; it displayed no time or
timezone. On October 18 the parent rechecked Cloudflare's
[current TTL documentation](https://developers.cloudflare.com/fundamentals/api/how-to/restrict-tokens/):
selected dates are documented as 00:00 UTC. By that documented rule an October
18 end date has passed; October 19 maps to October 18 at 20:00 EDT, earlier than
the accepted 04:00 UTC maximum. Terry was directed back to the form to correct
the end date and stop at summary. That documentation-based mapping was subsequently contradicted by the expanded
EDT date-time picker, as recorded above. It is retained as correction history,
not current form guidance or an issued token's actual policy.

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

## Selected metadata preparation direction — #0174

Terry selected **"Prepare separate read-only metadata access (recommended)"**
in decision `call_5bb323bec4d942e29308415256dce14b`. This resolves the preceding
direction choice only. #0174 owns standalone collector source, synthetic tests
and setup/read instructions; no credential creation, secret read, account API
or hosted test is authorized by the choice. The test token retains exactly the
two reviewed Workers/D1 Edit permissions. A separate current-user API Tokens
Read credential would be used only under later explicit setup/read approval.

The source route is at most three GETs: verify the chosen test credential,
verify the metadata reader, and fetch exactly that test token's details using
the ID acknowledged by its verification response. No token listing, additional
Token Details read, management write, provider-resource operation, redirect,
retry or DNS lookup belongs to this route. The reader verification does not
prove its full permission policy; its owner-provisioning evidence and broader
user-token metadata capability remain explicit in the later decision.

The parent prepared a new **empty** `credential-delivery` child beneath the
private staging directory. Its observed ACL has protected inheritance, the
current operator as owner and no allow rules outside current user, SYSTEM and
Administrators. Existing parent ACLs and files were preserved. No token file
was created or read. This preliminary directory observation does not qualify
future file ownership/access, race resistance, erasure or end-to-end custody.
The parent staging directory remains unsuitable for credentials.

Initially Terry was asked to keep the test-token summary open and prepare a
separate current-user API Tokens Read form in a second tab, with an October 19
end based on the date-only UTC inference. That end-date instruction is
superseded by the expanded-picker correction above. The current instruction is
to set both forms to October 18 at 23:59 EDT, Apply, continue to summary and stop
before creation. The parent has not operated those controls or observed their
completed application/final summaries. No issuance permission has been given.

## Metadata source handoff — #0174

The [separate read-only collector procedure](publisher-grant-metadata-preparation-2026-10-18.md)
and its evidence-only source passed fresh independent High review. All 22
synthetic scenarios passed, including a parent rerun, plus three independent
supplemental fault checks. Ruff, format checks, Pyright and the pinned native
TypeScript compiler passed. Parent findings about global Decimal precision and
the planned em-dash token name were corrected before handoff: timestamp
comparisons use exact integer attoseconds, and bounded printable provider
Unicode/empty optional metadata are retained without relaxing path/ID syntax.

The helper has no live CLI. A trusted parent must supply genuine separately
retained owner authority, exact source/plan/sinks and the two owner-provisioned
credential paths before its three-GET route can run. It returns counts only;
actual full metadata and fingerprints remain private. No token listing, writes,
normalized execution grant, implicit permission or API-method qualification is
supplied. #0173 and its strict whole-second grant parser remain unchanged; if
actual provider fractions cannot be represented there, preserve the evidence
and resolve that separate integration gap before a hosted test.

Preparation order: finish all source/document commits, then stage the private
metadata plan against that exact committed HEAD with an actual twenty-minute
window and independent private pins. Keep the source checkout frozen through
the attempt: the collector checks current HEAD as well as all closure bytes.
Even a documentation-only commit changes HEAD and requires fresh plan/review
and genuine applicable approval; do not weaken the check or reuse old consent.
No approval, human-evidence, credential, claim or spent-journal record may be
fabricated merely to complete a pre-issuance draft. If its window passes,
prepare a fresh unapproved packet before requesting an actual read.

The separate reader's form summary and exact provisioning/read permission are
still missing. No token was created/read, no API request was made and no hosted
case or native action occurred. The empty protected delivery directory remains
a preliminary ACL observation only; actual files must pass custody checks after
separately approved provisioning. #0174 is a source handoff, not a read result.

## Final metadata compatibility correction

The final collector preserves explicit empty IP-condition lists without inferring
their effective policy. Non-list, malformed CIDR and oversized values still
refuse. All 24 synthetic tests passed; the parent and independent High reviewer
also passed the two new regressions. Static checks remain clean. The earlier
unapproved private plan is invalidated by this source change and retained unused;
a fresh committed-source plan and window are required before actual approval.

Terry subsequently supplied the reader's final summary screenshot: **All users /
API Tokens:Read**, with October 18 for both dates. Terry reported both tokens
waiting before Create Token. This supplies the missing reader summary observation,
not token issuance, actual expiry evidence, credential access or read permission.
