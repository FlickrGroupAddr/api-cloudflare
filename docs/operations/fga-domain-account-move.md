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

## Existing access and the remaining inspection gap

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

A separate optional operator inspection token, **FGA Zone Read**, was requested
with **Zone / DNS / Read** and **Zone / SSL and Certificates / Read**, restricted
to `flickrgroupaddr.com` in the destination account. These are the documented
permissions for the two denied endpoints. The token supplements the operator
login; it is not a replacement login or an application runtime binding.
This gap does not block independent release implementation or deployment
preparation. Public apex A and MX queries returned no corresponding records at
this checkpoint; that observation is not a complete DNS inventory or proof that
all source records were preserved.

## Next engineering and owner steps

1. Inspect the destination records and certificate status when inspection access
   is supplied. Existing source-record preservation has not been independently
   certified. Avoid treating an automatic public-DNS scan as proof that proxied
   origin records were copied correctly.
2. Prepare the persistent Worker, D1 and native secret bindings with the accepted
   feature flags initially disabled. The prepared custom-domain configuration
   connects the apex to the Worker; the documented domain-attachment API accepts
   Workers Scripts Write. No broader DNS-write token is requested here.
3. Verify the connected hostname and TLS, then complete the actual owner Google
   sign-in and Flickr authorization/browser validation. The owner performs those
   identity-provider interactions when the deployed flow is ready.
4. Complete the remaining hosted restore/reconciliation, process-stop and full
   conformance/promotion gates before enabling real Flickr group adds. DNS
   activation supplies no production conformance receipt.

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
