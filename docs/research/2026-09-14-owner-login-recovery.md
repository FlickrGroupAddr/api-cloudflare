# Owner login recovery and same-site callback completion

Date: 2026-09-14

## Findings

The saved Google subject matches the value supplied during original owner setup.
The deployed configuration also matches that saved value. D1 contains one
administrator, one unrevoked session and an initialized Flickr-link record.
The session belongs to the configured subject. Its last-activity timestamp equals
its creation timestamp; because activity writes are coalesced, this alone does
not prove that every subsequent request failed. No email mapping was stored.
The desired personal email and pending owner change remain only in private input
configuration. No subject binding was changed during this investigation.

A separate browser test reproduced the callback problem using synthetic cookies
and two loopback site names:

| Navigation | Observed protected request |
| --- | --- |
| Cross-site form POST, Set-Cookie Strict, immediate 303 | Cookie missing |
| Follow an ordinary link from the resulting same-site document | Cookie present |
| Cross-site form POST, Set-Cookie Strict, 200 document, first-party continuation | Cookie present |

This is an independent reproduction of the navigation mechanism, not a complete
real-owner authentication trace. The local fixture used no real credential and
made no Flickr call.

## Implementation

Google and Flickr callback completion now returns a minimal same-origin HTTP 200
document before navigating to the fixed administration destination. The existing
Strict, Secure and HttpOnly cookie settings remain unchanged. The continuation
script reads only a server-rendered fixed-target link and allows `/admin/`,
`/admin/?flickr=linked` and `/admin/?flickr=unconfirmed`; it never reads a cookie
or copies the current callback URL. The body contains no assertion, nonce,
OAuth verifier or session token. It is no-store, no-transform and no-referrer.
The canonical contract clarification is architecture commit `accbd7c`.

A temporary operator-only owner-ID check can assist with the separately requested
personal-account binding. It is disabled unless the private deployment supplies
both `GOOGLE_OWNER_DISCOVERY_EMAIL` and `GOOGLE_OWNER_DISCOVERY_UNTIL` (Unix
milliseconds). An expired, absent, malformed or more-than-one-hour deadline fails
closed. After all ordinary admission, GIS CSRF, nonce, issuer, audience and signed
assertion checks, only an exact requested email with Google's positive verified
claim may see its own numeric subject ID. Google's documented boolean true and
literal string "true" encodings are recognized; false or arbitrary truthy values
are not. Normal authorization still uses only the configured subject.

The discovery response remains HTTP 401, creates no principal or session, does
not change the allowlist, and never returns or stores the raw assertion. Its HTML
contains the caller's verified subject only, uses restrictive CSP, and loads no
third-party script. Other accounts receive the existing generic unauthorized
response. Email matching is solely an operator-selected disclosure filter; it
is not a new email-based login method.

## Validation

- 104 backend Node tests passed; affected identity/callback tests passed again
  after matching Google's documented verification encoding.
- Native TypeScript validation passed. Ruff and Pyright passed for the changed
  hosted harness.
- 13 hosted administration/lifecycle cases passed with synthetic identities and
  fake Flickr. Worker, D1 and native-secret cleanup are confirmed. The persistent
  application resources were not part of that cleanup.
- 13 relevant architecture documentation/TLS/logout tests passed.
- Private hosted evidence: `.coordination-runs/rp-efaf640c76a124ca99b74583/report.json`.

These checks do not complete the full production fail-polite release gate or the
real owner's Google/Flickr interaction. Group dispatch remains disabled.

## Next owner step and follow-through

After deployment, ask Terry to start a fresh login and select the requested
personal account. A successful existing match should reach administration through
the repaired cookie continuation. If it is a different subject, the targeted
verification page will show its Google-verified Account ID (sub); ask for that ID,
not an ID token or form payload. Once verified, disable the discovery variables
and apply the explicitly requested sole-owner binding change.

The existing principal identity is immutable under `principal_identity`. Do not
silently update it or remove its SQL guard. Retain historical records, check
whether any owner-bound domain data needs migration, and revoke superseded
sessions through the existing guarded transition. A change to the sole configured
subject must not authorize both accounts or erase history. The final binding
choice must be based on the fresh verified identity and Terry's stated account
preference, not an email-to-ID guess.

[Google's identity claims documentation](https://developers.google.com/identity/openid-connect/openid-connect)
supports using `sub` as the permanent identifier and verified email only for this
bounded selection step.
