# Hosted publisher: separate provider-token expiry from caller authority

Date: 2026-10-18. Ticket #0134. Status: **Proposed scoped test amendment;
not accepted, implemented or action-authorizing**.

## Problem and existing rule

Terry confirmed the custom-token form still offers Workers Scripts/Edit and
D1/Edit for the selected account. He reports its Today selection as the local
day through 23:59 EDT. This is owner-reported UI interpretation, not a collected
provider grant receipt or verified UTC expiry. No token was created, read or used.

The accepted source's
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

## Proposed one-attempt amendment

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

## Tradeoff requiring Terry's acceptance

The provider token can remain usable outside the finite caller window until
confirmed manual revocation or its actual provider expiry. The caller's local
refusal does not revoke that account-level Workers/D1 capability or prevent its
use through another client. A failed or delayed revocation leaves this exposure
for the remaining token lifetime, up to the ceiling above. Account-level create
authority still reaches resources beyond the four intended synthetic pairs at
the provider policy layer; the reviewed caller limits its own operations only.

Recommended direction: accept this limited lifetime tradeoff and retain the
short caller limits plus prompt manual revocation. The alternative is to retain
the current expiry-by-cleanup rule and use a provider grant with sufficiently
precise earlier expiry, or schedule a later run whose approved window actually
contains the existing grant expiry. No alternative token-creation authority is
approved by mentioning it.

## Implementation and action gates

Acceptance would authorize the scoped successor source change and synthetic
tests, not token issuance, credential reads, account access or execution. Keep
Completed #0155/#0162/#0165 and their original committed/private artifacts intact.
A new implementation card/revision must own any current validator/caller changes;
do not rewrite their old packets or silently use changed bytes under old pins.
Prefer the small explicit policy change over a duplicate transport framework.

Independently review actual issue/expiry preservation, finite ceilings, early
provider expiry, stop/revocation and dispatch/cleanup boundary cases. Then pin
the new committed source closure and prepare the actual private packet. Its
grant evidence, custody, network, owners, windows and fingerprint remain required.
Only the later concrete owner provisioning and exact-run decisions can authorize
token creation/use and provider work. If this proposal is declined, the current
validator continues to refuse the end-of-day token for a run now.

## Observation and verification boundary

This proposal is based on the screenshot, Terry's expiry clarification and
tracked source inspection. No account API, provider-time verification, credential,
token, private record, cloud mutation or native input was used. Documentation
checks and independent review must precede the owner decision. A source change
or synthetic test cannot retroactively authenticate a grant's actual policy.
