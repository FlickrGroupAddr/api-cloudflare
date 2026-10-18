# Hosted publisher private packet preparation — 2026-10-18

Status: **Preparation procedure only; no provider, credential or native action authorized.**
#0165 source is accepted Completed. #0134 remains the decision gate for one
actual private run; #0122 owns subsequently authorized execution. This guide
explains how to reach a reviewable decision using the existing runtime, without
pretending missing inputs or returned resource identities already exist.

The [caller procedure](hosted-publisher-execution-caller-2026-10-18.md) owns runtime
invocation and custody checks. The [Beta integration procedure](hosted-publisher-beta-integration-2026-10-18.md)
and accepted #0157 contract own execution and disposal semantics. Preserve the
immutable [#0121 candidate](hosted-publisher-qualification-packet-2026-10-17.md)
and sealed #0162/#0165 evidence. This guide does not amend those artifacts.

## Later scoped token-expiry decision

Terry accepted the [one-attempt expiry amendment](hosted-publisher-token-expiry-amendment-2026-10-18.md)
on October 18. It separates actual provider-token expiry from finite caller
authority, with a 24-hour-from-issue limit and a ceiling of October 19 00:00 EDT.
Manual revocation after cleanup and the residual lifetime tradeoff are explicit.
The #0173 successor source has independent review; the old packets retain their
strict expiry-by-cleanup rule. Reprepare against the new committed source and
bind the exact exception object before an actual decision; absent that object,
the default remains strict.
This decision is code/test authority only. Proposed expiry controls still need
review before issuance, and actual grant evidence and exact run approval remain
required. No longer caller, case, phase, adapter or cleanup deadline is accepted.

## Verified retained source and finite budget

On 2026-10-18 the parent verified the retained #0121 candidate against its
published pins: source commit `aca532af6d570125c5d8bbcbd6ac1b4a10ae74f7`,
113 source files, source artifact
`718b3dd7e1ec669c7e043f4c3a37142ceaad42a5bd3bcbc0639868a2b1e5aed1`,
manifest `f3ce7b2ba3cded646c825a6435a7217db742f226927f3633ae6ea61bc52a26c8`,
and optimized module `b2241f88c94ec6561b2a902a5561bf9f63459e420fbd111861db1636feb2a26f`
(652,967 bytes). All 26 retained migration files match the current migration
bytes; their byte-semicolon-plus-one reservation sum is 690. The sanitized
parent receipt is `0134-retained-source-receipt.json` in the private dated
2026-10-18 next-batch handoff. No rebuild, provider request or credential read
occurred. This resolves retained-source verification, not live qualification.

Source analysis of the existing caller gives the following nominal envelope
for all four cases, including each first complete cleanup:

| Work | Management calls | Mutations |
| --- | ---: | ---: |
| Four runs, including stop | 188 | 132 |
| Four first complete cleanups | 56 | 12 |
| Total | 244 | 144 |
| Shared ceiling | 256 | 160 |
| Remaining headroom | 12 | 16 |

The concrete client performs 28 empty-body phase POSTs. SQL reservations total
7,500 calls and `917,732 + 4 × 690 = 920,492` statements under the respective
8,192 and 1,048,576 ceilings. These are conservative reservations, not evidence
of query settlement, changed rows or billing. The caller procedure and
[renewed action sheet](hosted-publisher-renewed-action-decision-2026-10-18.md)
retain the other fixed byte, time and lifecycle ceilings. The private plan may
reduce ceilings only while preserving a feasible intended closure.

Headroom supplies no new authority and cannot fund another complete four-case
cleanup pass. Interrupted prefixes may retain resources; unknown creates lack
an acknowledged identity and cannot be discovered or adopted. Token/policy
inspection, issuance, verification/revocation and independent address sourcing
are outside this trace and need separately reviewed finite authority.

The current trace does not perform real edge bad-token, malformed-header,
expired-token, wrong-origin, wrong-method or replay probes. The three synthetic
upstream lost-reply cases do not test lost management creates. Any required
external negative suite needs its own reviewed finite request list before use.
Independent recipe review passed after corrections; 40 local synthetic checks
passed without constructing a socket. Neither result qualifies actual endpoints.

## Prepare in dependency order

1. **Freeze the source and retained candidate.** The accepted runtime source
   baseline is commit `8dcfb119488f2a8d902fb53747d98f3f0e28112b`. The parent
   verifies the exact retained #0121 source directory and optimized module;
   use those bytes without rebuilding or recapturing them. Retain the original
   pins, frozen Python/uv identities, independent review and test/procedure
   identities separately. The runtime preparer does not include every test or
   procedure in its manifest. If later integration changes a runtime dependency,
   define and review the new closure and committed revision before preparing
   the actual packet; do not silently keep the old source pin.

2. **Fix the non-secret private action sheet.** Record the exact account;
   four fresh intended Worker/D1 name pairs, case run IDs and workers.dev
   endpoint URLs; UTC start, dispatch expiry and cleanup deadline; named
   operator, stop, cleanup, revocation and residual owners; exclusive management
   control; fixed absolute custody paths; stop mechanism and residual escalation
   deadline. Use `happy`, `create_lost`, `attachment_lost`, `title_lost` once
   each. The parent may assemble safe non-secret staging within authorized
   scope; account inspection, token creation and provider requests require
   their own later concrete authority. No account search is implied here.

3. **Supply the network record independently.** Bind one public numeric
   `management_address` for TLS to `api.cloudflare.com`, plus
   `client_addresses` keyed by all four exact endpoint URLs. Record provenance
   and the selected operator's outbound public source IP separately. A
   destination address pin and a token's source-IP restriction are different
   controls. The runtime performs no DNS, proxy, redirect, retry or alternate
   address fallback. Do not use guessed addresses or invent endpoint readbacks.
   A changed/unavailable pin requires a reviewed replacement packet.

4. **Create and verify the non-secret runtime packet.** Use
   [`prepare()`](../../scripts/prepare_hosted_publisher_runtime.py) with the new
   destination, complete supplied scope bytes, verified retained source/module,
   exact current committed source and network bytes. The function creates
   `plan.json`, `manifest.json` and `source/`; it accepts neither consent nor a
   credential. Independently retain its packet and plan digests. Run its
   documented `--verify` command against that independent digest. Review the
   finite method/request/cleanup budget against the actual plan. Verification
   remains NO-GO and proves byte/shape bindings, not provider qualification.

5. **Review a concrete grant and credential-provisioning proposal.** Before any
   token action, state the exact account, required method permissions, excess
   create authority, UTC validity, source-IP policy, named custodian, private
   delivery path, revocation owner and independent revocation means. Obtain
   separate authority for the necessary metadata inspection/token issuance/
   local secret provisioning. That limited authority does not authorize fixture
   creation or execution. The recipe below is guidance for that later step;
   no token or account is accessed by this document.

6. **After that limited authority, retain the actual grant evidence and
   credential binding.** Independently review effective provider policy for
   every planned method and retain bounded non-secret evidence privately.
   Provision the management credential through the approved custody path;
   independently retain its exact SHA2-256 fingerprint for the later approval.
   Do not ask Terry to paste a token in chat. Do not fabricate grant identifiers,
   permission evidence, a fingerprint or `metadata_verified=true` merely to
   satisfy a parser. If provisioning changes the planned grant/window/custody,
   review and replace dependent records before final approval.

7. **Present the exact run for Terry's approve/decline/defer decision.** The
   review copy must identify the actual packet/plan/source and grant evidence,
   intended names/endpoints, custody and stop ownership, finite action budget,
   windows, separate cleanup authority and accepted synthetic disposal tradeoff.
   Keep private grant/fingerprint values out of public records. After actual
   approval, the parent records consent and approval with their independently
   retained digests and real human-decision reference/evidence. The approval
   binds the actual credential fingerprint. No affirmative record exists
   before that decision, and JSON cannot authenticate its human author.

8. **Only then use readiness and any authorized caller.** `readiness` requires
   current consent, grant, approval, grant evidence and an existing bounded
   private credential file. It checks custody/existence without reading token
   bytes and deliberately returns NO-GO/exit 2. It cannot be used to manufacture
   preapproval. Later `execute` additionally reserves once-only authority before
   reading the credential. Separate `cleanup` retains original journal,
   deadlines, spent budgets and execution authority and adds current cleanup
   authority; it cannot regain dispatch. The caller procedure owns exact syntax.

## Returned identities are a later stage

Before approval, bind intended names, account, endpoint mechanism and precise
creation operations. Worker IDs, D1 UUIDs, version/deployment IDs and the
enabled projection digest depend on acknowledged authorized provider results.
Do not require fabricated pre-run IDs or create resources merely to complete
the packet. The actual run binds each successful create to its returned
immutable identity before migration, deployment or enablement; the separately
computed projection then binds the retained module to that actual D1 UUID.

A lost acknowledgement remains unresolved. No retry, name adoption, listing,
prefix search or guessed cleanup follows. Preserve the journal and residual
ownership. Cleanup needs verified exact identity and the six accepted disposal
conditions; available budget alone supplies no recovery authority.

## Token creation guide for a later authorized custodian

Use an API token, not a global API key. Cloudflare's
[D1 dashboard guide](https://developers.cloudflare.com/d1/tutorials/import-to-d1-with-rest-api/)
describes **API Tokens → Create Token → Custom token → Get started**, a
descriptive token name, and **Account → D1 → Edit**. Scope account resources to
the one reviewed account; do not accept an all-accounts default. Add only the
reviewed Workers capability that covers the exact Beta and Scripts operations.

Permission names need explicit reconciliation. The runtime's grant record
requires `D1:Edit` and `Workers Scripts:Edit`. Public method references list
[D1 Write for D1 creation](https://developers.cloudflare.com/api/resources/d1/subresources/database/methods/create/),
[Workers Scripts Write for Beta Worker creation](https://developers.cloudflare.com/api/resources/workers/subresources/beta/subresources/workers/methods/create/)
and [Workers Scripts Write among deployment permissions](https://developers.cloudflare.com/api/resources/workers/subresources/scripts/subresources/deployments/methods/create/).
The separate [Workers roles guide](https://developers.cloudflare.com/workers/authorization/workers/)
describes a role migration, product-level Admin for new Workers and continued
legacy permission support. These public descriptions do not prove an actual
token's effective policy or the least available authority. Retain the actual
policy and method mapping, review account-wide excess, and stop if the offered
permissions differ. Do not automatically expand to Admin or broad templates
to make a request pass. Existing-resource Worker scopes do not by themselves
authorize creating the four new Workers.

Configure the reviewed outbound source-IP restriction and finite token TTL;
retain the exact policy summary before issuance. Cloudflare's
[restriction guide](https://developers.cloudflare.com/fundamentals/api/how-to/restrict-tokens/)
states that tokens otherwise have no expiry and token verification does not
apply source-IP filtering. Its date-only note describes 00:00 UTC. The later
observed October 18 picker explicitly offers EDT date-times; for this workflow
use October 18 at 23:59 EDT on both forms, as recorded in the
[picker correction](hosted-publisher-token-expiry-amendment-2026-10-18.md#current-form-values--expanded-picker-correction).
Do not override an explicit displayed timezone/time with the earlier date-only
inference. The actual provider timestamps still require later evidence. If the
dashboard cannot express the reviewed expiry, resolve that limitation before
issuance. The [API issuance guide](https://developers.cloudflare.com/fundamentals/api/how-to/create-via-api/)
supports precise UTC times but needs separate token-creation authority; do not
introduce a powerful parent token merely as a convenience.

Review the summary, then create only after the provisioning decision. The
secret is shown once. Transfer it directly into the separately reviewed
private delivery file with no trailing newline and approved owner/access
metadata. Never use the sample `curl` command, environment variables, command
arguments, shell history, chat, tracked files or receipts to transport it.
The caller expects raw ASCII token bytes and permits only the current owner,
SYSTEM and Administrators in its Windows custody checks. Those checks do not
establish secure erasure or eliminate privileged replacement races. Record
the private fingerprint and grant binding independently; no public hash is
needed. Token verify is not proof of every planned permission and is not an
unbudgeted authorized request.

After authorized cleanup, or emergency stop when required, the named owner
revokes through the independently available approved means and retains
sanitized confirmation. Local file deletion, probe expiry and dropping Python
references do not revoke a provider grant. If revocation prevents cleanup,
retain exact residuals and a new decision rather than restoring dispatch.

## Minimum remaining owner inputs

The parent should request only unresolved choices after exhausting safe
non-secret preparation: the exact account/context and resource namespace;
actual operator/stop/cleanup/revocation/residual ownership and exclusive-control
commitment; acceptable UTC run/cleanup and token windows; source-IP/custody/
independent revocation choices; and limited authority to obtain the exact
missing grant/credential inputs. The parent supplies reviewed source and
candidate identities, generated packet digests, bounded action list and
implementation evidence; Terry need not invent them. Final run approval waits
for the complete exact packet, actual grant/fingerprint binding and review.

No current account policy, endpoint/address, credential, provider result or
human run approval is established here. Production scheduling, real Flickr,
native Lightroom, activation and production conformance keep their separate
gates and all production capability flags remain false.
