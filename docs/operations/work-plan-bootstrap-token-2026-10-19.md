# Finite local work-plan bootstrap issuer

Terry accepted the bootstrap policy on October 19, 2026, decision
`call_8562d3b067e14c66ba2f351e1ea50eb2`. The human creates one **user-owned**
token using Cloudflare's **Create additional tokens** template, containing
**User / API Tokens / Edit (Write)** only. Its actual provider expiry must be
no later than **2026-10-26T12:00:00Z** and at most seven days after actual
issuance. Revoke it earlier when work finishes or Terry stops the plan.

This parent can manage tokens across the user's resources. Account restrictions
on a child and limits in this local script do not narrow the parent's provider
capability. Keep the parent on the qualified local operator host; never deliver
it to the FGA API backend, a Worker, native client or CI runner. Preserve Terry's
independent console access. Parent expiry or deletion proves nothing about
independent child expiry or deletion.

The implementation is `scripts/provision_work_plan_token.py`. Its import and
disabled CLI do no I/O. A trusted primary invokes `run(RuntimeInputs(...))`
only after independent review of the concrete private packet and authentic
owner-decision evidence. There is no daemon, arbitrary profile, ambient token,
token list, automatic retry, recursive issuer or public secret-bearing command.
JSON fields and matching hashes bind evidence; they cannot authenticate a human.

## One human form, technical preparation by the operator

1. Independently review the issuer's exact committed source and the proposed private
   packet layout. Bind the final packet after delivery in step 3, before use. Confirm the requested work remains within the maintained
   plan and the accepted decision; retain the actual decision evidence privately.
2. Supply Terry with one qualified protected secret-file delivery location and
   the parent template, expiry and any reviewed source-IP restriction. Terry
   supplies the one-time parent secret through that protected local path, never
   through chat, argv, environment, logs or Git. Independently qualify ownership,
   ACL, regular-file/no-link behavior, synchronization/backup exposure and private
   retention. This source change does not qualify actual custody or secure erasure.
3. The operator derives the parent fingerprint by a bounded protected local read,
   supplies the actual FGA account and finite window, and prepares the packet.
   Terry need not find permission IDs, a provider token ID or write JSON. For an
   issuance packet, `parent_id: null` permits only the authenticated `/verify`
   response to discover this exact parent's identity. It is retained privately
   and bound before POST. A supplied parent ID must match instead.
4. The issuer authenticates the real parent, maps the three permission IDs from
   one bounded authenticated permission-catalog GET, and reads the exact verified
   parent ID's details. It refuses absent actual issue/expiry, different identity,
   extra policy, broader scope, different condition or an overlong lifetime.
5. Only then may it issue one child and directly deliver its one-time secret to
   the new protected child file. Treat any failure as spent, including interrupted
   setup, unclear mutation, metadata failure and uncertain delivery. Preserve
   private evidence and journal; never replay issuance to find a missing result.

No provider access, actual secret delivery, native ACL qualification, API schema
qualification or effective execution grant was performed for this source card.

## Closed current profile and finite budgets

Only `publisher-d1-workers-account` is implemented. Its one allow policy contains
exactly **D1 Write** and **Workers Scripts Write**, on precisely
`com.cloudflare.api.account.<account_id>: "*"`. It has no zone resource,
user-token permission or arbitrary permission superset. The parent must have one
allow policy containing exactly **API Tokens Write**, with resource
`com.cloudflare.api.user.*: "*"`. Provider details retain all policy metadata
privately; policy IDs and descriptive group fields do not expand these grants.

Each invocation has one current UTC window of at most **600 seconds**, an
absolute monotonic deadline, a per-request allowance of at most **20 seconds**,
at most **5 requests**, **8,192 bytes per outbound request**, **40,960 outbound
bytes total**, **262,144 HTTP response wire bytes per request**, and
**1,310,720 HTTP response wire bytes total**. The reused pinned TLS transport
uses the reviewed global numeric address, verifies `api.cloudflare.com`, and
provides no DNS, proxy, redirect, cookie jar or retry. Validated, budgeted
Set-Cookie fields are discarded as in the accepted metadata transport.

| Request | Issue | Revoke |
| --- | --- | --- |
| 1 | GET `/user/tokens/verify` | Same |
| 2 | GET `/user/tokens/permission_groups` | Same |
| 3 | GET `/user/tokens/<verified-parent-id>` | Same |
| 4 | POST `/user/tokens` | GET `/user/tokens/<recorded-child-id>` |
| 5 | GET `/user/tokens/<acknowledged-child-id>` | DELETE `/user/tokens/<recorded-child-id>` |

All paths use `/client/v4` on the fixed Cloudflare API HTTPS origin. The catalog
is capped at 1,024 groups and a bounded documented schema, including optional
category, description, selectability and pagination metadata. Exactly one
matching name/scope entry per required permission must be present in this
response. Children must be selectable when the flag is present. The existing
special-template parent permission need not be selectable. Missing, ambiguous,
unrecognized or over-budget results stop; no next-page request or inferred
catalog completeness follows. This lookup lists permission definitions, never
tokens or candidate token identities.

Children explicitly receive the chosen expiry and optional single canonical
global source network condition. Parent restrictions are not inherited by
assumption. The child's actual provider expiry must match exactly, be no later
than the parent expiry and the accepted run's cleanup, and cleanup must be
within four hours of the invocation start. For issue, child expiry must also
outlast the administration window. Its actual issue time must fall within that
window. This does not extend the publisher's four-hour run, thirty-minute cases,
separate provider limits or snapshot caller limits. It never revives yesterday's
dated expiry exception. The operator must align actual run/cleanup packets with
these values; issuer success is not run authorization.

## Private packet and durable outcomes

`RuntimeInputs` supplies absolute private plan, approval and genuine human
evidence paths and their SHA2-256 digests, plus the actual source root. The plan's
closed schema binds:

- Version/purpose, owner, operation (`issue` or `revoke`), fixed profile, exact
  account, source commit and SHA2-256 closure, current start/expiry, cleanup,
  child name/expiry/condition, expected parent condition, parent ID or permitted
  verify-self discovery, parent credential fingerprint and pinned API address.
- Distinct protected parent credential, new child delivery, claim, journal and
  evidence paths outside the source tree, a named revoker and explicit retention
  deadline no later than the parent's policy sunset. The issuer enforces that
  retention deadline's finite declaration, not future deletion or erasure.
- The exact constants above in `request_limit`, `request_byte_limit` and
  `response_byte_limit`. Issuance has `issuance: null`; revocation supplies the
  original issuance journal path, its plan digest and exact acknowledged child ID.

The closed approval binds that plan digest, source commit and owner to the real
decision ID, actual evidence digest, recorded time and expiry. Its provenance is
`authorized_automated_local_issuance`; its bootstrap role is
`user_wide_token_management_write_local_only`. These are accurate role labels,
not substitute human approval flags. Independent source review and the trusted
primary remain necessary. Tests show the complete synthetic shape; they are not
operational packets or real evidence.

An exclusive persistent claim and FULL-synchronous SQLite journal consume the
invocation before credential use. Each request has durable intent before
dispatch; POST/DELETE has a distinct mutation intent. The one-time creation
response is parsed only in memory. Its exact acknowledged ID and request-derived
ownership receipt are durably recorded before follow-up metadata or delivery.
The private JSONL evidence contains complete validated parent/catalog/child
metadata and all non-secret creation fields, fingerprints, source/approval
bindings and delivery disposition. The raw secret-bearing creation response is
never written. Untrusted exceptions become a fixed sanitized refusal; no provider
body or exception text is printed or journaled.

An acknowledged child remains independently potentially live even when its later
metadata or delivery fails. The child secret goes only to exclusive-new qualified
private storage after matching actual child identity, policy, condition and expiry.
It is never silently overwritten. A partial delivery remains an uncertainty,
not permission to retry, adopt another token or guess an identity.

## Exact child revocation and successor metadata role

Prepare a separate independently reviewed finite revocation packet. It must bind
the acknowledged original issuance journal and plan digest, the same parent ID
and fingerprint, account, profile, child ID/name/expiry/condition. The original
journal must contain a completed creation ownership receipt. The issuer reads
that exact child's current details and sends DELETE only to that ID. It refuses
unknown creation, unrelated IDs, parent-as-child, changed ownership or policy.
The original child journal gains a permanent retirement latch before child
inspection. An unknown delete therefore also refuses across fresh packets.

The DELETE response must acknowledge that exact ID. The evidence says
`delete_acknowledged`; no extra verification request, cascading deletion or
successful console reconciliation is inferred. A child already expired/inactive,
an unavailable/expired parent, missing ownership, lost response or changed schema
stops this API path. Terry's independent console reconciliation handles those
cases under a separately bounded disposition. Do not delete unrelated tokens or
reuse unknown mutations to discover their state.

The accepted Write parent may serve as the distinct metadata reader under this
successor policy, honestly acknowledging user-wide token management. The child
is an authorized automated issuance, not a human dashboard-issued token. Existing
metadata collectors, old immutable packets and exact publisher grant validators
remain unchanged. Do not set legacy `owner_provisioned` booleans merely to pass
the old contract: prepare and review a concrete successor provenance packet or
required collector amendment before consuming an automated child there. Keep
the original distinct credential/provider-ID checks and three-GET metadata
recipe; never add token management to the executing child or omit residual
capability from evidence. Later profiles require their own reviewed operation
mapping and source change.

### Concrete successor provenance packet

No collector schema change is required merely to encode this accepted
provisioning route. In a fresh, independently reviewed packet only,
`owner_provisioned` means **actually provisioned under the owner's accepted
policy**, not necessarily typed or dashboard-created by the owner personally.
This explicit successor meaning must not be retroactively applied to old packets.

The private `human_evidence` record must retain the genuine accepted decision
reference and the actual human parent-delivery record, and bind the completed
issuer receipt by its private digest. Preserve the issuer's exact source,
issuance plan, actual child ID, acknowledged creation, completed protected
delivery, distinct parent/child fingerprints and provider IDs, and current full
parent/child metadata. Record the methods explicitly as human-provisioned
bootstrap parent and authorized automated execution child; never label the
child human dashboard-issued. Independent review must verify that chain before
setting either `owner_provisioned` flag true. A policy acceptance or unexecuted
issuer template alone is insufficient.

Bind that real record through the existing `human_approval` reference/digest and
actual recording time, source and fresh metadata-plan digest. The reader-policy
acknowledgment must describe the parent's actual Write/mint/manage capability,
not call it read-only or FGA-confined. Keep source-policy and provisioning
responsibilities with the trusted primary; JSON booleans do not authenticate
human intent or an API event. Preserve current windows, actual provider timing,
private storage, distinct-role checks and the exact three-GET collector recipe.
No extra arbitrary permissions may enter the execution grant. This is a
reviewable packet procedure, not evidence that issuance or delivery has happened.

Official schema references: [permission groups](https://developers.cloudflare.com/api/resources/user/subresources/tokens/subresources/permission_groups/methods/list/),
[creation guide](https://developers.cloudflare.com/fundamentals/api/how-to/create-via-api/),
[create token](https://developers.cloudflare.com/api/resources/user/subresources/tokens/methods/create/),
[token details](https://developers.cloudflare.com/api/resources/user/subresources/tokens/methods/get/),
and [delete token](https://developers.cloudflare.com/api/resources/user/subresources/tokens/methods/delete/).
