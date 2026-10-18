# Cloudflare management response policy — 2026-10-18

Status: **Accepted scoped management-only policy; offline caller integration.**
On 2026-10-18 Terry explicitly wrote “0178 is accepted” after reviewing the
recommendation. This accepts only the bounded management response-cookie policy
and offline caller integration described here. It authorizes no credential
access, account request or live execution. The primitive and probe client retain
their strict defaults; provider-method qualification remains outstanding.

## Authority and observed evidence

The canonical [documentation authority policy](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/README.md)
and [accepted #0157 scoped contract](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/proposals/hosted-operator-provider-strategy-2026-10-17.md)
control. The accepted contract retains finite requests, exact returned resource
identity, durable intents, unknown latching and no replay. The current
[execution caller procedure](hosted-publisher-execution-caller-2026-10-18.md#concrete-transport-boundary)
records the prior blanket duplicate-header refusal. Terry's subsequent explicit
acceptance amends that boundary only for the management callers named below;
passing synthetic tests alone did not amend it. All other duplicate refusals
and the accepted contract's identity, finite-budget and no-replay rules remain.

The [metadata collection record](hosted-publisher-token-expiry-amendment-2026-10-18.md#accepted-metadata-only-policy-and-successful-v4-collection)
records two separate facts: v3 stopped at a duplicate-header refusal whose field
name/value were not retained; v4 completed three GETs under Terry's accepted
metadata-only cookie-discard policy. The actual v3 field remains unknown. No
creation, mutation or deletion response headers were observed by this work.
Metadata acceptance and successful GETs do not establish management-response
compatibility, resource-method qualification or new execution authority.

## Standards review and accepted exception

[RFC 9110 sections 5.2–5.3](https://www.rfc-editor.org/rfc/rfc9110.html#section-5.2)
distinguish field-specific list semantics from a universal duplicate rule.
Repeated Set-Cookie is a special case that cannot safely be comma-combined.
This supports discarding those irrelevant fields in a stateless API client;
it does not justify accepting every repeated field. The management policy deliberately
keeps the existing conservative refusal for every other duplicate, including
fields whose general HTTP definition allows lists. General list handling would
need its own reviewed policy and is outside #0178.

[RFC 9112 section 6.3](https://www.rfc-editor.org/rfc/rfc9112.html#section-6.3)
describes response framing and incomplete-message handling. This finite client
continues to require explicit framing and a complete JSON acknowledgement;
it does not adopt the standard's possible recovery of identical repeated lengths
or a close-delimited response. Cookies cannot repair framing ambiguity.

**Accepted scoped amendment:** permit the reviewed finite Cloudflare management
client to ignore each syntactically valid Set-Cookie response header, including
repeats, only after charging every raw line and byte to the existing limits.
Do not combine, parse as a cookie, persist, return, log or resend its value.
Refuse every other duplicate as before. Keep the probe client strict. Acceptance
adopts this policy direction and offline integration; fresh independent review
and the later exact action decision remain separate gates.

The policy is confined to separately reviewed, exact-target management calls
to `https://api.cloudflare.com`, with the existing account/resource and operation
inventory. It supplies no new route, method, permission, request or recovery
operation. A refusal on another field must stop normally; it cannot trigger a
wider policy, fallback connection or replay.

## Explicit management caller selection

[`ExecutionBetaPublisherProvider`](../../scripts/hosted_publisher_execution_provider.py)
constructs `_ManagementTransport` with the explicit boolean
`discard_set_cookie=True`. The private transport retains a strict default for
unselected synthetic callers, validates the option before socket creation and
delegates cookie handling to the existing raw HTTP parser.

[`private_d1_snapshot_reader._IsolatedTransport`](../../scripts/private_d1_snapshot_reader.py)
and the concrete dispatch path in
[`qualify_private_d1_snapshot`](../../scripts/qualify_private_d1_snapshot.py)
also explicitly select `discard_set_cookie=True` for their Cloudflare management
requests. Their same-process fresh-database permit, source/packet/consent guards,
exact target inventory, retained uncertainty and cleanup gates are unchanged.
The injected-transport seam remains trusted synthetic test code, not human
consent or a sandbox against trusted Python code making network calls.

`_pinned_https` retains `discard_set_cookie=False` by default.
`ExecutionClientTransport` never selects the exception. Other direct strict
callers retain their behavior. The accepted metadata-only opt-in is unchanged;
it did not itself authorize management selection. This integration creates no
second parser, cookie state or alternative acknowledgement/identity validator.

## Preserved refusal and accounting boundaries

- Raw status/header syntax, field-name case folding, control-character refusal,
  no folded fields, count/line/header ceilings and the total HTTP wire ceiling
  apply before cookie discard. The existing header count admits at most 99
  fields; ignored fields do not gain extra slots.
- Every non-cookie duplicate remains refused. Framing, content, authentication
  and redirect fields gain no exception. Existing closed duplicate categories
  contain no arbitrary provider field name or value.
- Explicit Content-Length or valid chunk termination, length agreement,
  identity content encoding, redirect refusal, body limits and complete raw
  chunk/trailer validation remain required. Trailer rules are unchanged;
  the cookie exception applies only to initial response headers.
- One numeric-address TLS connection, hostname verification, no DNS/proxy/
  redirect/retry/address fallback, admission and absolute deadlines, permit
  rechecks, operation/byte caps and shared reservations remain unchanged.
- Cookies have no jar or subsequent request state. The management request
  header allowlist supplies no Cookie field. No raw response header values
  belong in journals, sanitized failures, ticket prose or tracked evidence.

The provider retains its existing conservative reservation/accounting after a
failed request; a transport refusal does not refund a consumed request or turn
unknown bytes into a measured zero. The response parser's wire count includes
ignored header bytes on complete returns. Partial failures remain uncertain.

## Unknown creates and deletes

A cookie-discarded response is still only a candidate acknowledgement until the
existing exact status, JSON, account/name and immutable Worker-ID or D1-UUID
checks pass. Transport/framing failures, malformed JSON, unsuccessful envelopes
and late or lost responses still latch the provider unknown and suppress its
HTTP completion hook. That hook acknowledges HTTP/envelope processing only;
resource identity validation follows separately. A complete HTTP receipt cannot
establish ownership or resolve an identity mismatch. A rejected create identity
still closes the provider without registering the resource.

An unknown create retains its durable intent, consumed name/key and absent
acknowledged identity. No retry, listing, prefix search, same-name adoption or
guessed deletion follows. An unknown delete retains the exact known identity
and unresolved deletion record. It is not proof of deletion or absence and
cannot authorize repeating DELETE. Separate reviewed exact-ID reconciliation
and the existing cleanup authority remain necessary. The accepted fixture-only
disposal conditions do not establish SQL settlement or resolve a lost response.

## Offline evidence and remaining gates

The dedicated synthetic management-policy tests exercise raw-wire cookies and
other duplicates, syntax/limits/deadlines/framing/trailers, strict defaults and
provider create/delete unknown outcomes. Existing metadata and execution
transport regressions remain required. The author handoff records the exact
commands and results; independent review must assess the final source before
owner handoff. Passing fixtures supplies no provider/API or live qualification.

Initial fresh independent High review passed the disabled candidate, dedicated
tests and policy wording after correcting the metadata provenance link. Eighteen
policy tests and eight independent mocked fault checks passed. The author passed
78 affected policy/metadata/execution/collector tests plus Ruff/format/Pyright;
the parent separately passed the eighteen dedicated tests. These were offline
candidate results before acceptance and do not qualify the later integration or
actual provider behavior.

The accepted caller integration passed 61 affected synthetic tests: 21 policy
cases plus execution transport, private reader and qualifier regressions. The
author independently reran that same affected set and the four changed Python
files passed pinned Ruff, format and Pyright checks. The new cases exercise both
direct snapshot dispatch routes through raw-wire cookie responses, including
unknown create/delete no-replay outcomes. Fresh independent High review of the integrated source passed five focused
integration checks and four additional mocked fault checks, with no actionable
findings. No provider request or live qualification occurred.

## Acceptance timeline and remaining gates

- The initial candidate was Proposed and unselected by execution callers.
  Independent review and passing tests supplied evidence, not acceptance.
- Terry's response to recommendation prompt `call_b4883eeadbd04843acee922d83c5482f`
  asked for the recommendation; that response was not acceptance.
- Terry subsequently typed “0178 is accepted” on 2026-10-18. That explicit owner
  directive accepts the narrow management policy and offline caller integration.
  It does not broaden the metadata-only acceptance or grant live authority.
- The selected management paths passed their separate fresh independent High
  integration review. The earlier candidate review was not used as a substitute.

Before any later use:

1. Retain the completed integration checks and fresh independent review. Any
   material source change requires renewed verification/review; strict primitive/
   probe defaults and every existing boundary remain required.
2. Prepare fresh source/recipe/packet bindings for the intended operation and
   exact finite window, retaining all spent invocation records and unknowns.
   This source change makes older closure pins stale; do not refresh a sealed
   candidate or silently amend a closed private draft. Rebinding is later work.
3. Obtain the separate exact action authority before credential access or any
   request. Actual create/delete headers and behavior remain unqualified until
   an authorized measurement; a failure still stops without replay.

No credential content, account operation, DNS lookup, native input, provider
request, source-manifest refresh or live measurement belongs to this ticket.
