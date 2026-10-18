# Publisher grant metadata: separate read-only preparation

Date: 2026-10-18. Ticket #0174. Status: **Source/preparation only; no token issuance, credential access or provider request authority**.

## Purpose and current boundary

Terry selected separate read-only metadata preparation in decision
`call_5bb323bec4d942e29308415256dce14b`. This document describes the later
owner-mediated setup and bounded metadata read. It does not authorize those
actions. No token, current grant, verified fingerprint or credential-ready
delivery location is established by this source work.

The test token remains exactly the reviewed selected-account **Workers
Scripts / Edit + D1 / Edit** grant. Do not add token-management permissions to
it. A different temporary **current-user API Tokens / Read** token supplies the
metadata reader. Its provider capability can reach other user-token metadata;
the collector's one-details restriction limits this implementation, not the
credential's provider authority. Terry must explicitly accept that exposure
and its prompt revocation before provisioning/use. Never substitute API Tokens
Write, a broad template, an account-owned token or the global API key.

This is separate from the
[accepted expiry amendment](hosted-publisher-token-expiry-amendment-2026-10-18.md)
and the [private runtime packet procedure](hosted-publisher-private-packet-preparation-2026-10-18.md).
The metadata collector produces evidence only. It neither executes #0173's
grant policy nor authorizes the hosted publisher test, cleanup, native input,
production scheduling or activation. Candidate Worker, migration and earlier
artifact pins remain unchanged.

## Why a separate reader is needed

Cloudflare's [Verify Token API](https://developers.cloudflare.com/api/resources/user/subresources/tokens/methods/verify/)
returns a token ID/status and optional validity timestamps. It does not supply
actual issue time or the full policy. `not_before` is the earliest validity
boundary; it is never evidence of `issued_on`.

Cloudflare's [Token Details API](https://developers.cloudflare.com/api/resources/user/subresources/tokens/methods/get/)
is `GET /user/tokens/{token_id}` and accepts API Tokens Read or Write. Read is
the selected authority. Its schema includes optional `issued_on`, `expires_on`,
`not_before`, `condition`, policies and status fields. An optional public schema
field is not a guarantee that the actual response contains the evidence needed
here. Missing required evidence, conflicting IDs/status/times or an unsupported
shape must fail closed; do not invent defaults.

The collector requires the critical evidence fields even when the public API
schema marks them optional. It accepts exact UTC `Z` timestamps with up to 18
fractional digits; other timestamp shapes refuse. Retain accepted provider
timestamp strings at their exact RFC3339 precision, including fractional seconds, and preserve complete validated policy/condition
content privately. Do not round an issue time, strip permissions, infer creation
from an observed interval or relabel a local deadline as provider expiry. If
later strict grant parsing cannot represent actual timestamps, record that
separate gap and keep execution NO-GO; this collector must not covertly change
the shared grant validator. A successful read is not proof that every planned
Workers/D1 method works or that source-IP restrictions were enforced. The
reader's own verify also does not prove its complete policy; independently
retain its reviewed owner-provisioning summary.

No ordinary console export of all required metadata has been demonstrated.
Do not promise one or require a HAR, DevTools capture or secret-bearing creation
response to fill the gap.

## Normal dashboard preparation: stop before creation

The documented [user-token flow](https://developers.cloudflare.com/fundamentals/api/get-started/create-token/)
starts at **My Profile > API Tokens**, then **Create Token**, custom token,
name, permissions/resources, restrictions and **Continue to summary**.
Use that normal view for each proposed token; keep secrets off screenshots.

1. For the test token, retain the exact selected account and two reviewed Edit
   permissions. For the separate reader, select **User / API Tokens / Read**
   for the current user. The parent observed that reader form as a single
   permission row with no account-scope selector; no token was created. Give
   the reader a clearly temporary metadata purpose.
2. Review the selected resource scope, outbound source-IP restrictions and finite
   TTL for each token. Stop if the offered scope or permission labels differ;
   do not expand authority merely to make a later request succeed.
3. In both forms, use the explicitly displayed Eastern Daylight Time picker:
   set **End: October 18, 2026, 23:59 EDT**, select **Apply**, then continue
   to summary and review the non-secret proposed policy. **Stop here;
   do not select the final Create Token button under this preparation authority.**
   The separate setup decision below controls issuance and delivery.

Cloudflare's [restriction guide](https://developers.cloudflare.com/fundamentals/api/how-to/restrict-tokens/)
defines calendar-only selections at **00:00 UTC**. The parent's later expanded
picker observation showed an explicit **Eastern Daylight Time** timezone,
**Start: 2026-10-18 00:00** and **End: 2026-10-19 23:59**. That explicit
date-time UI overrides the earlier calendar-only inference for these forms:
do not convert the displayed EDT end date to 20:00 EDT. The parent instructed
Terry to set both forms' proposed end to **October 18, 2026, 23:59 EDT**,
select Apply, continue to summary and stop before creation. The applied
settings and final summary have not been observed. This is parent-reported
screenshot evidence and guidance; neither the parent nor this runbook author
operated the form, and this runbook author did not inspect the screenshot.

The accepted test-token ceiling remains **2026-10-19T04:00:00Z = October 19
at 00:00 EDT**. Actual API expiry remains unverified until the separately
authorized read; the displayed proposal does not establish an issued grant's
policy or actual issue time. The actual earlier expiry controls. Recheck the
proposed window against the current clock before issuance; do not silently
reuse an expired packet.

The restriction guide also says that omission of expiry leaves tokens
long-lived and that verify does not apply source-IP filtering. A verify result
therefore cannot qualify that restriction. Precise API-based issuance would
need separate token-creation authority and is outside this route.

## Private delivery and custody preparation

The parent operator must first prepare and independently review the **exact
absolute paths** for two distinct credential files, private evidence, spent
journal and exclusive claim. Review the enclosing directories, owners, ACLs,
reparse/link boundaries, non-overlap and output handling before any secret is
placed there. The existing staging parent's ACL preflight found additional
allow rules outside the reader's trusted set. That parent is **not credential
ready**. No real credential path or directory has yet been qualified here.
The parent subsequently prepared an empty protected `credential-delivery` child
under the existing `0134/publisher-expiry-oct18-staging` private staging area.
Its summarized ACL observation reported inheritance protected, current owner
and no unexpected allow rules; no files or secrets were created/read. This is
a parent-reported preliminary observation, not end-to-end custody qualification.
The proposed `operator-token.txt` and `metadata-reader-token.txt` files remain
subject to exact later approval and file/parent custody checks. Never deliver
secrets to the unqualified staging parent. This document grants no ACL action.

After explicit setup permission, Terry creates only the two reviewed grants
and transfers each one-time secret directly to its approved private delivery
file as bounded raw ASCII bytes, with no trailing newline. The ordinary console
shows a secret once. Do not use its sample test command, clipboard history,
chat, tracked files, shell history, arguments, environment variables, logs,
receipts or exceptions as secret transport. Do not expose the one-time secret
while retaining non-secret policy evidence.

Reuse the existing bounded credential-file and Windows custody checks: only
the current owner, SYSTEM and Administrators are trusted allow principals.
File checks do not prove secure erasure or eliminate privileged replacement
races. Retain actual credential fingerprints only in protected private evidence
for the later exact hosted-run binding; never publish them in chat or tracked
receipts. Unknown token IDs and fingerprints are not pre-issuance prerequisites:
the setup decision binds exact purposes/files and the returned-ID discovery
rule, then actual evidence supplies the later identities.

## Finite metadata-read contract

The implementation owner is
[`scripts/collect_publisher_grant_metadata.py`](../../scripts/collect_publisher_grant_metadata.py).
Use its closed plan/approval validation as the field authority rather than
maintaining another schema here. The collector has no live CLI: its `main`
refuses. A later explicitly authorized trusted parent caller supplies
`RuntimeInputs` to `run`, including externally retained human evidence and
independently retained plan/approval digests. JSON decision strings alone do
not authenticate Terry's identity or consent.

The exact plan binds the committed source closure, UTC window, independently
supplied numeric global address for `api.cloudflare.com`, credential purposes
and all input/output paths. Validate every non-secret bound and external
approval before reading credential bytes. Claim the exclusive one-attempt
path and spent journal before secret access; preserve them after success or
failure. Credential files and values must be distinct.

A successful attempt makes exactly these three GETs, in this order:

1. `GET /client/v4/user/tokens/verify`, authenticated with the selected test token.
2. The same verify path, authenticated with the separate reader token.
3. `GET /client/v4/user/tokens/{id}`, authenticated with the reader, where `{id}`
   is only the selected test token's ID returned by step 1 and validated by the
   collector. The details response must identify that same token.

A failed attempt can stop after fewer requests. The maximum is three requests:
no token listing, other token details, resource requests, writes, redirects,
retry, fallback, automatic revocation or native action. Use the existing
bounded HTTPS implementation with the fixed hostname and numeric address;
no runtime DNS lookup is part of this read. Keep the 20-second per-request
ceiling and the remaining monotonic budget within the at-most-20-minute absolute
caller window. Each response is bounded to 64 KiB wire bytes and the total to
192 KiB or the implementation's tighter bound.

The #0176 source candidate has an explicit **Proposed** metadata-only cookie
response policy. It discards Set-Cookie fields, including repeats, only after
raw syntax and all field-count/wire bounds are checked; it never stores or sends
cookies. Other repeated fields and forbidden trailer/framing/routing semantics
remain refused. Strict hosted defaults remain strict. This is a change to the
metadata reader's prior all-duplicate refusal and must be identified in the
next exact owner decision; source review alone does not accept or run it. The
[operation history](hosted-publisher-token-expiry-amendment-2026-10-18.md#proposed-metadata-response-cookie-policy--0176)
records the actual duplicate-header measurement, standard reference, unknown
offending field and proposed redline. Do not infer that cookies caused the
actual failure or that token validity was measured. A different refusal stops
without widening or replay.

Successful private output retains complete validated verify/details results,
exact provider times/policies, private fingerprints and source/plan/approval
bindings. Public-facing status contains only sanitized outcome, request and
wire-byte counts and, on refusal, closed static stage/category/cause codes;
provider bodies and raw failures stay out of logs. The output is **not** an
execution-ready normalized grant, `metadata_verified` authorization flag,
complete reader-policy proof or hosted-test pass. Later independent review must
interpret the actual evidence and construct/review the actual runtime packet.

Failure diagnostics use a closed vocabulary, never arbitrary exception text,
class names, chains, tracebacks, request headers or provider bodies. The existing
private journal records the safe refusal reason when writable; the raised
sanitized refusal also carries bounded diagnostics and counts. Dispatch counts
are attempts to call the transport, not proof of accepted HTTP requests. Wire-byte
counts cover only fully returned and accounted responses; they do not measure
partial failed transfers or TLS overhead. A failed receipt write can leave an
intent rather than an unknown receipt, but the exclusive claim and journal still
prevent replay. Preserve the original bounded diagnostic instead of replacing it
with a receipt-write exception or treating missing diagnostics as success.

## Later permissions and handoff

The parent must make the following decisions concrete before requesting them.
Do not ask Terry to approve placeholder paths or unspecified network actions.

1. **Setup and metadata-read permission.** Present the reviewed source commit
   and closure, exact token policies/purposes and broader reader capability,
   proposed finite expiry/source-IP rules, exact qualified delivery/evidence/
   journal/claim paths and owners, proposed approval-evidence location and
   retention procedure, address provenance,
   fresh UTC window, three-GET discovery rule, private output handling and
   independent revocation method. Ask for issuance/delivery and the bounded
   credential reads/provider requests explicitly. Any new address resolution,
   ACL setup or private preparation access needs its own exact authorized scope;
   prior staging approval does not imply those actions. Materialize the actual
   approval record, external human-decision evidence and bound digests only
   after Terry makes the real decision; they are not pre-approval inputs.
2. **After the approved metadata attempt.** Terry revokes the reader promptly
   through the independently available console and records sanitized confirmation.
   The collector does not revoke it. Review actual test issue/expiry/policy,
   fingerprint and custody privately. Retain any missing evidence or parser
   incompatibility as NO-GO rather than fabricating a grant.
3. **Separate exact hosted-run/cleanup permission.** Only after the actual
   evidence and freshly bound complete runtime packet pass their remaining
   source, custody, owner, stop and expiry gates may Terry approve that exact
   test/cleanup attempt. Metadata-read approval supplies no such permission.
   Rebuild expired windows through the reviewed process. Terry revokes the test
   token promptly after approved test cleanup, following the independent stop/
   cleanup/revocation procedure if an emergency occurs.

On any metadata failure, stop and preserve the spent journal/claim. Do not
rerun with the same invocation, erase the journal, retry a provider request or
silently broaden permissions. Hand Terry a sanitized failure category, attempted
request count, private evidence reference and revocation obligation. A new
attempt needs fresh explicit authority and a new reviewed packet. No metadata
failure permits resource cleanup or token mutation by this collector. File
deletion, dropping a Python reference and local deadline expiry do not revoke a
provider token. Record any unconfirmed revocation as a residual exposure.

## Verification scope

Source review and synthetic fixture checks can qualify the bounded collector;
they cannot authenticate an actual human decision, grant, credential, address,
provider response or hosted behavior. This document's external API/UI claims
were checked against the linked official Cloudflare documentation on
2026-10-18. The source-only work inspected no private inputs, issued/read no
credential and performed no account, DNS, hosted or native action.
