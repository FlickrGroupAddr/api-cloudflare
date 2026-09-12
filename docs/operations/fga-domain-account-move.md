# FGA hostname handoff to the selected Cloudflare account

Terry approved moving FGA to the sixbucks Cloudflare account. The project-specific `fga-sixbucks` operator profile and limited Secrets Store writer token are verified. The existing default Wrangler profile is preserved.

The `flickrgroupaddr.com` zone is active in the old account, not the destination account. Public NS records still point to its old Cloudflare nameservers. Authoritative RDAP identifies Amazon Registrar as the registrar. The current old-account Wrangler credential can identify the zone but its DNS-record listing is denied (HTTP 403); the source DNS records and DNSSEC status have therefore not been certified. No source zone or nameserver has been modified.

## Owner step and migration sequence

1. In the old account, export the zone's current DNS records and inspect DNSSEC and any zone-specific settings. A local export can be supplied to the agent for preparation and comparison; no broader runtime-token scope is needed.
2. Add the same domain to the destination Cloudflare account and import the verified records. Review the new zone and certificate setup before switching nameservers. Do not use a public-DNS scan as proof that proxied origin records were copied correctly.
3. Follow the DNSSEC requirements in Cloudflare's account-move procedure, then set the newly assigned Cloudflare nameservers in Amazon's domain-registration management.
4. Confirm that the destination zone becomes Active and its TLS certificate is ready. Deploy the prepared Worker/D1/native-binding configuration there, with feature flags initially disabled, then perform the real Google/Flickr browser smoke check.

Google's authorized origin stays `https://flickrgroupaddr.com` and its redirect URI stays `https://flickrgroupaddr.com/admin/google-login`. The Flickr profile has been resolved through the official read-only API and its expected owner is recorded in ignored deployment inputs. Credential values must remain in the managed store or local input files, never this document.

The supplied Secrets Store token is intentionally not a DNS-management credential. The accepted permanent token has no expiration and only Secrets Store Edit in the destination account. No AWS application backend is required; Amazon is relevant here because it is the existing domain registrar.

Primary procedure: [Move a domain between Cloudflare accounts](https://developers.cloudflare.com/fundamentals/manage-domains/move-domain/). The registrar/account transfer distinction matters: this handoff changes authoritative DNS/account placement and does not request a registrar transfer or a domain purchase.
