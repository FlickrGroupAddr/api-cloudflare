# Google button stylesheet integration repair

Date: 2026-09-13

The first real owner browser check reproduced the oversized Google logo seen in
the embedded browser. Terry's Chrome console explicitly reported a blocked
injected stylesheet under the FGA login page's `style-src` policy. This was an
application integration defect, not evidence that Terry had used the wrong
browser or needed another Cloudflare credential.

The FGA administrative control plane now generates a fresh 192-bit CSPRNG nonce
for each login or authenticated HTML response. It places that value on the
Google loader and permits it only in `style-src`. The authenticated HTML passes
the nonce through its existing application module to the lazy Google loader used
for reauthentication. The external script allowlist remains unchanged; there is
no inline-script permission, broad unsafe-inline style permission, or changed
referrer policy. The style nonce is independent of the OIDC transaction nonce.
The hosted library continues to load directly from Google.

The compiled Worker regression passed with real local D1 and synthetic signed
Google assertions. It checks per-response nonce uniqueness, policy/loader nonce
agreement, absence of inline-script permission, the authenticated shell nonce,
and the existing session/CSRF/login/logout behavior. Native TypeScript validation
also passed. The final deployed page rendered a normal **40-pixel-high** Google
sign-in button. Clicking the repaired button reached Google's account sign-in
page for this application; the agent entered no account credentials and created
no owner session.

Google's personalized-button iframe still logs an origin/client-ID warning.
That warning did not prevent the tested button-to-Google redirect. Do not infer
that the owner's Google configuration or the accepted no-referrer policy must
change solely from that warning. The full owner authentication callback remains
to be exercised. The separate blocked Cloudflare analytics script was not
allowlisted as part of this repair.

The final artifact and verified administration-only switches are in
[the sanitized evidence](../evidence/google-button-style-fix-2026-09-13.json).
Administration is enabled; installation reads, submission intake and group
adds remain disabled. No database migration, native credential replacement or
Flickr group operation was performed for this fix.

The next owner action is to refresh `https://flickrgroupaddr.com/admin/login`
and use the repaired Google sign-in button. This supersedes the initial request
to diagnose the oversized control in another browser.

References: [Google Identity Services integration](https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid)
and the live browser/Chrome console evidence described above. This repair fits
the accepted narrow GIS integration and keeps the administrative control-plane
contract's script and referrer boundaries.
