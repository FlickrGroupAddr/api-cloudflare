# FGA hostname handoff to the selected Cloudflare account

## Current state - 2026-09-13

The approved DNS account move is complete. Terry added `flickrgroupaddr.com` to
his sixbucks Cloudflare account and changed its registered nameservers at Amazon
to `norah.ns.cloudflare.com` and `valentin.ns.cloudflare.com`. His Route 53
confirmation shows DNSSEC **Not configured**. Both public resolvers `1.1.1.1`
and `8.8.8.8` independently returned that new pair.

The read-only `uv run --frozen python -m scripts.deployment_readiness` check at
`2026-09-13T21:59:17Z` confirmed that the destination zone exists and is **active**.
The owner also supplied its active Cloudflare dashboard confirmation. The
previous target-zone-missing handoff is resolved. This establishes delegation
and account activation, not application deployment or release conformance.

Amazon remains the registrar. The later registrar transfer is separate from this
completed DNS move and does not block application work. No further registered
nameserver change is required for the current destination account.

## Existing access and verified inspection token

The project-specific `fga-sixbucks` Wrangler operator login remains usable; the
existing default profile is preserved. A subsequent read-only API check returned:

| Inspection | HTTP result |
| --- | --- |
| Destination Worker inventory | 200 |
| Destination Worker custom-domain inventory | 200; FGA hostname not connected |
| Destination D1 inventory | 200 |
| Destination Secrets Store inventory | 200 |
| Destination DNS records | 403 |
| Destination SSL certificate packs | 403 |

These inventory responses demonstrate current read access, not a new deployment
or proof that every future write operation will succeed. The existing operator
profile was authorized with Worker script/route, D1 and Secrets Store write
scopes. The separate managed-runtime writer token intentionally has only Secrets
Store Edit; do not broaden that token to resolve operator inspection needs.
Existing local Google configuration and Flickr/writer credential input files
are present. Their contents must remain private.

The owner supplied the separate **FGA Zone Read** token on 2026-09-13 and
approved keeping it without expiration. The existing local input manifest now
contains `zoneReadTokenFile`; the token bytes remain only in the supplied private
file. At `2026-09-13T22:08:31Z`, `user/tokens/verify` returned active, DNS listing
returned HTTP 200 with **zero records** (complete, single-page inventory), and
certificate listing returned HTTP 200 with an **active Universal SSL certificate
covering the apex**. The earlier operator inspection gap is resolved.

This token has the requested Zone / DNS / Read and Zone / SSL and Certificates /
Read scope for the destination domain. It supplements the operator login and is
not an application runtime binding. Source-record preservation remains a
historical unverified fact; the destination account contains no existing DNS
records for the initial Worker connection to replace.

## Current application handoff

The [initial persistent deployment](initial-disabled-deployment.md) is now
complete. The Worker is connected to the apex with working TLS and the current
D1 schema. Administration alone is enabled for the approved owner browser
validation; reads, submission intake and group dispatch stay disabled.

The owner browser check identified a blocked Google stylesheet. The
[button integration repair](../research/2026-09-13-google-button-style-fix.md)
is deployed and verified: the normal-sized button reaches Google sign-in.
The remaining origin warning and analytics injection were also
[resolved](../research/2026-09-13-google-login-origin-fix.md); the live login
page now has a clean console. The next owner step is to refresh and sign in.
Existing Cloudflare access is sufficient; no additional Cloudflare token or
nameserver change is currently requested. Remaining hosted release gates are
engineering work and are not waived by this deployment.

Google's authorized origin stays `https://flickrgroupaddr.com` and its redirect
URI stays `https://flickrgroupaddr.com/admin/google-login`. The Flickr owner
identity is already recorded in ignored deployment inputs. No new Google owner
setup or Cloudflare operator login is currently required.

## Sources and earlier handoff

- [Move a domain between Cloudflare accounts](https://developers.cloudflare.com/fundamentals/manage-domains/move-domain/).
- [Amazon registered-domain nameservers](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/domain-name-servers-glue-records.html).
- [DNS record listing and accepted permissions](https://developers.cloudflare.com/api/resources/dns/subresources/records/methods/list/).
- [Certificate-pack listing and accepted permissions](https://developers.cloudflare.com/api/resources/ssl/subresources/certificate_packs/methods/list/).
- [Worker domain attachment and accepted permissions](https://developers.cloudflare.com/api/resources/workers/subresources/domains/methods/update/).

Before the owner move, the source zone used `braden.ns.cloudflare.com` and
`walk.ns.cloudflare.com`; the destination zone was absent. The source operator
could identify the zone but DNS-record and DNSSEC reads returned 403. No source
DNS or nameserver was changed by an agent. The owner's later move supersedes
that target-zone blocker without retroactively certifying the source export.
