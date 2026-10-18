# Cloudflare management response policy candidate — 2026-10-18

Status: **Proposed; disabled in execution callers. Offline qualification only.**
Ticket #0178 prepares a narrow stateless response-cookie policy for later owner
review. It does not accept that policy or authorize any provider request.

## Authority and observed evidence

The canonical [documentation authority policy](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/README.md)
and [accepted #0157 scoped contract](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/proposals/hosted-operator-provider-strategy-2026-10-17.md)
control. The accepted contract retains finite requests, exact returned resource
identity, durable intents, unknown latching and no replay. The current
[execution caller procedure](hosted-publisher-execution-caller-2026-10-18.md#concrete-transport-boundary)
refuses duplicate response headers. This proposal cannot amend that boundary by
being implemented or passing synthetic tests.

The [metadata collection record](hosted-publisher-token-expiry-amendment-2026-10-18.md#accepted-metadata-only-policy-and-successful-v4-collection)
records two separate facts: v3 stopped at a duplicate-header refusal whose field
name/value were not retained; v4 completed three GETs under Terry's accepted
metadata-only cookie-discard policy. The actual v3 field remains unknown. No
creation, mutation or deletion response headers were observed by this work.
Metadata acceptance and successful GETs do not establish management-response
compatibility, resource-method qualification or new execution authority.

## Standards review and proposed exception

[RFC 9110 sections 5.2–5.3](https://www.rfc-editor.org/rfc/rfc9110.html#section-5.2)
distinguish field-specific list semantics from a universal duplicate rule.
Repeated Set-Cookie is a special case that cannot safely be comma-combined.
This supports discarding those irrelevant fields in a stateless API client;
it does not justify accepting every repeated field. The candidate deliberately
keeps the existing conservative refusal for every other duplicate, including
fields whose general HTTP definition allows lists. General list handling would
need its own reviewed policy and is outside #0178.

[RFC 9112 section 6.3](https://www.rfc-editor.org/rfc/rfc9112.html#section-6.3)
describes response framing and incomplete-message handling. This finite client
continues to require explicit framing and a complete JSON acknowledgement;
it does not adopt the standard's possible recovery of identical repeated lengths
or a close-delimited response. Cookies cannot repair framing ambiguity.

**Proposed owner redline:** permit the reviewed finite Cloudflare management
client to ignore each syntactically valid Set-Cookie response header, including
repeats, only after charging every raw line and byte to the existing limits.
Do not combine, parse as a cookie, persist, return, log or resend its value.
Refuse every other duplicate as before. Keep the probe client strict. Accepting
this redline would authorize the policy direction only; integration and a later
exact action decision still require their own source and packet review.

The proposal is confined to separately reviewed, exact-target management calls
to `https://api.cloudflare.com`, with the existing account/resource and operation
inventory. It supplies no new route, method, permission, request or recovery
operation. A refusal on another field must stop normally; it cannot trigger a
wider policy, fallback connection or replay.

## Disabled source branch

[`_ManagementTransport`](../../scripts/hosted_publisher_execution_provider.py)
adds the private boolean `proposed_discard_set_cookie=False`. Synthetic tests
select `True` through the existing trusted injected-transport seam to exercise
the proposed management path with the actual raw HTTP parser. Non-booleans
refuse before socket creation. The option is a qualification seam, not human
consent or a sandbox against trusted Python code making network calls.

`ExecutionBetaPublisherProvider` still constructs `_ManagementTransport` with
its strict default and exposes no policy selector. No execution caller or CLI
selects the candidate. `ExecutionClientTransport`, private D1 snapshot readers
and qualifiers, and other direct strict `_pinned_https` callers retain their
existing behavior. The accepted metadata-only `discard_set_cookie=True` route
is unchanged. These separate callers cannot inherit a management exception
from metadata acceptance or from this proposal.

The proposed branch delegates to that same validated/budgeted cookie-discard
parser instead of creating a second HTTP parser. It changes no response body,
status, resource identity or provider acknowledgement validation.

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

Fresh independent High review passed the disabled candidate, dedicated tests and
final policy wording after correcting the metadata provenance link. Eighteen
policy tests and eight independent mocked fault checks passed. The author passed
78 affected policy/metadata/execution/collector tests plus Ruff/format/Pyright;
the parent separately passed the eighteen dedicated tests. No unresolved finding
remains in this offline handoff. These checks do not accept the redline, select
it in an execution caller or establish provider behavior.

Before any later use:

1. Obtain explicit owner acceptance of the narrow management redline above;
   record it without broadening the metadata-only acceptance.
2. Review and implement explicit selection for each intended management caller.
   Preserve strict probe defaults and all existing gates; rerun affected tests
   and obtain fresh independent review of the selected path.
3. Prepare fresh source/recipe/packet bindings for the intended operation and
   exact finite window, retaining all spent invocation records and unknowns.
   Do not refresh a sealed candidate or silently amend a closed private draft.
4. Obtain the separate exact action authority before credential access or any
   request. Actual create/delete headers and behavior remain unqualified until
   an authorized measurement; a failure still stops without replay.

No credential content, account operation, DNS lookup, native input, provider
request, source-manifest refresh or live measurement belongs to this ticket.
