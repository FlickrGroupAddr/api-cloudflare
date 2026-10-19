# Bootstrap provider-metadata compatibility — 2026-10-19

The first bounded issuance invocation stopped after two GET requests and before
any POST. Its consumed invocation remains spent. This follow-up changes bounded permission-definition prose parsing and the
parent-only user-resource representation; it does not authorize replay or prove any
child issuance, custody, effective grant, or live execution qualification.

## Offline diagnosis

A separately collected, protected permission-definition catalog and diagnostic
receipt were read offline with the existing bounded private-file reader. No
credential, account identifier, old execution journal, or other private packet
was used. The retained normalized JSON is private; no catalog fixture or real
permission IDs are committed here.

The first failing field in the normalized catalog was `result[86].description`,
for `Account Waiting Rooms Read`, scope `com.cloudflare.api.account`. It contains
a line feed (U+000A); the printable-only metadata helper refused that string.
Nineteen descriptions contain line feeds. A second incompatibility affects three
`category` fields whose value is JSON null; the first is `result[291].category`,
for `Page Shield Write`, scope `com.cloudflare.api.account.zone`.

These are observations of the protected normalized catalog, not assertions
about original HTTP headers, raw transport framing, or unobserved catalog pages.
The required canonical names and scopes were present. Parsing this response can
establish this profile's mapping only; it does not prove the full provider
permission catalog is complete.

## Narrow correction

- Accept a null optional `category`; other nonstring values still refuse.
- Permit LF in optional `description` only. Validate a temporary LF-to-space
  copy with the existing 4,096-byte UTF-8 bound and printable-text check. This
  preserves the original byte length, rejects other controls and invalid Unicode,
  and leaves the retained provider response unchanged.
- Keep canonical `API Tokens Write`, `D1 Write`, and `Workers Scripts Write`
  names and their exact scopes. No Edit/Write aliases or additional permissions
  are introduced. Permission IDs still come from unique exact catalog entries.

The parent resource compatibility described below is the only policy-selector
change. Original closed-envelope, unique-ID, selectability, exact permission IDs,
parent Write, two-role child, expiry, committed-source, secret storage,
finite request/byte/time and no-replay checks remain. The shared metadata text
helper is unchanged. The original accepted bootstrap runbook and historical
review records are unchanged.

## Validation and remaining gates

Synthetic regressions exercise a null category and multiline description on an
unrelated permission alongside the exact three required definitions; issue still
uses the exact original two-permission account policy. Regressions reject other
category types, category newlines, null/nonstring descriptions, CR/tab/control
characters, excess original UTF-8 bytes, and permission name/scope aliases.

The issuer suite, scoped Ruff checks and project Pyright are required before
handoff. The protected normalized catalog is also parsed offline after the fix
using a synthetic JSON response wrapper; that check does not qualify real HTTP
headers or authorize a provider call. Fresh independent review and a fresh,
source-bound invocation with current inputs and accepted finite limits remain
necessary before any later live attempt. Never reuse the consumed invocation.


## Parent resource representation follow-up

After the catalog correction, a separate protected own-parent details diagnostic
identified the next exact comparison discrepancy. The unchanged shared metadata
validator accepts the details. The issuer's comparison expected only
`com.cloudflare.api.user.*`; the provider instead returns the sole resource key
`com.cloudflare.api.user.<32 lowercase hexadecimal characters>` with value `*`.
The policy has one allow rule and the exact `API Tokens Write` permission ID.
No real token/user identifiers or fingerprints are included in source or tests.

The issuer now permits that canonical concrete-user selector as an explicit
parent-only structural alternative. The original provider metadata is retained
unchanged. The authenticated verify-self result and its ID-specific details
request still bind the actual parent token. The resource user identifier is not
assumed to be a token or account identifier. This representation does not narrow
the accepted warning: the parent has user-wide token-management power and can
mint access beyond the execution child's local restrictions.

Equality still requires exactly one allow policy, one exact parent Write
permission, one resource key and literal `*` value. Multiple resources, policies
or permissions, malformed or uppercase identifiers, unknown selectors and deny
rules refuse. Child requests and child verification continue to require the
exact planned account selector and the original two permission IDs. Identity,
conditions, issue time, expiry, source binding, finite budgets and no-replay
checks are unchanged; the shared metadata collector is unchanged.

Synthetic tests cover the provider-shaped parent alternative, unchanged child
POST policy, and the hostile variants above. Offline validation against the
protected normalized parent metadata can establish this structural match and
current lifetime checks only. It proves no new provider action, raw HTTP header,
credential custody or child issuance. Previously consumed invocations and their
journals remain untouched; any later attempt needs a fresh reviewed source-bound
packet and current accepted finite limits.
