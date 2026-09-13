# Public Google login origin and analytics repair

Date: 2026-09-13

Terry confirmed the exact OAuth client in Google Console with JavaScript origin
`https://flickrgroupaddr.com` and redirect URI
`https://flickrgroupaddr.com/admin/google-login`. Both values were correct. The
origin needs no path, wildcard or extra subdomain; no Google setting was changed.

Two page-integration problems remained after the stylesheet repair:

1. The public login response suppressed the referrer entirely. Google's embedded
   button consequently returned HTTP 400 and logged an origin/client-ID error.
   The fixed, query-free public `GET /admin/login` page now uses `strict-origin`,
   sending only the public site origin. A fresh live browser load then rendered
   Google's actual framed button with zero new console errors or warnings.
2. Cloudflare automatically injected a Web Analytics script outside the accepted
   CSP allowlist. Administrative HTML now sends `Cache-Control: no-store,
   no-transform`; live inspection confirmed that injection stopped. The analytics
   host was not added to CSP and zone security settings were not changed.

The public-login referrer adjustment is deliberately narrow. Authenticated HTML,
Plugin Code transfer, Google/Flickr callbacks and JSON APIs retain no-referrer.
Rejected login queries also retain no-referrer. The stylesheet nonce and inline-
script restrictions remain intact. The canonical control-plane contract records
this verified interoperability correction in architecture commit `cb311b5`.

Validation: native TypeScript and the compiled Worker authentication regression
passed, including the authenticated shell and callback/JSON referrer assertions.
Thirteen relevant architecture documentation/TLS/logout checks passed. Live HTTP
checks confirmed public login 200/strict-origin, rejected query 400/no-referrer,
anonymous session 401/no-referrer and unauthenticated admin redirect 303/no-referrer.
Google's framed button opened its normal account sign-in flow; the agent entered
no owner credentials and did not complete owner authentication. The exact artifact,
flags and sanitized checks are in
[the evidence](../evidence/login-page-health-2026-09-13.json).

The default Python HTTP client was challenged by Cloudflare before reaching the
application. The existing identified FGA diagnostic client successfully performed
the checks above; no provider security toggle was changed. Earlier command-line
requests directly to Google's frame were inconclusive and did not substitute for
the successful live browser comparison.

Next owner step: refresh `https://flickrgroupaddr.com/admin/login` and complete
Google sign-in. Administration remains the only enabled feature; installation
reads, submission intake and Flickr group dispatch stay disabled. Full production
release conformance and the owner authentication callback are still pending.

Primary references: [Google Identity Services setup and referrer guidance](https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid)
and [Cloudflare Web Analytics no-transform behavior](https://developers.cloudflare.com/web-analytics/faq/).
