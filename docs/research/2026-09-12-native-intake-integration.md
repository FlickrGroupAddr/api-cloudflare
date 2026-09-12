# Native credential and batch integration handoff

Tickets: #0016 and #0017. Status: Needs Terry; implementation checkpoint, not production acceptance.

## Decision needed

Accept proposed architecture ADR 0048 (201 JSON OAuth start response followed by validated top-level navigation) together with proposed ADR 0057 (native lifecycle public representation and writer boundary). The local browser experiment reproduced the current manual-fetch 303 response as `opaqueredirect`, status 0, with no exposed Location. The 201 alternative returned a strictly validated synthetic Flickr authorization URL. The preview never navigates to Flickr.

Recommendation: accept both proposals. Use account-level Secrets Store Edit only for the eventual unattended writer, separated from read-only Worker bindings, with fixed store/slot targets. Cloudflare's scope is account-level; fixed runtime targets do not create per-secret IAM. No management credential has been provisioned. ADR 0057 also closes the wording distinction between retired local payload and external Flickr permission removal. Both ADRs remain Proposed until Terry accepts them.

The review schema is `proposals/native-flickr-connection.schema.json`, deliberately outside the executable production registry. The visual review is `prototypes/native-flickr-admin/`. It covers linked/paused, active, replacing, repair required, relink required, disconnecting, disconnected and unlinked states. Browser checks covered the initial view, repair, relink, disconnecting, unlinked and the local OAuth-response experiment. Responsive layout and a complete authenticated browser journey have not been certified.

## Implemented checkpoint

- Production installation authentication now supports JSON request envelopes while retaining the existing read-only route behavior. Current installation credentials authorize the two new routes; pending credentials do not.
- Native binding reads validate the exact application and generation-tagged grant envelopes. A real OAuth 1.0 signed `photos.getInfo` read checks photo identity, configured owner and public visibility. Credential authority is reread before use and checked again in the atomic D1 binding commit.
- The candidate credential validator signs `auth.oauth.checkToken` and requires the reflected token, configured owner and write/delete permission. It is an internal helper, not a public credential-input endpoint.
- Migration 0005 adds the native consumer reference and append-only photo verification evidence. It is not the pending/retiring lifecycle operation schema or an unattended mutation controller.
- The executable registry exposes the accepted existing-public-photo binding route and schemaVersion 2 batch route. Generated OpenAPI matches it. Admission projects no internal ordinals or hint fields, validates the whole selection, limits it to 60 groups and sends zero or one post-commit native hint.
- The official Lua 5.1 batch adapter submits one complete ordered selection in one request. Host HTTP/JSON callbacks are injected. This is not a finished Lightroom UI/publish-provider integration.

## Validation on 2026-09-12

- Clean `npm ci` succeeded with the pinned lockfile. Four existing high-severity development dependency advisories remain; no forced upgrade was performed.
- TypeScript native check passed (also required before the compiled intake fixture).
- `npm run intake:test`: 26 passing tests, including the compiled production Worker on local workerd/D1, real native Secrets Store bindings, native DO wake fixture and an independently signed synthetic Flickr peer. No real Flickr calls.
- The integration suite exercises 15 named CBA cases: ROUTE-003/004, VALID-001/002, TXN-001 through 005 and HINT-001 through 006. Transaction fault injection verifies rollback and no hint at each injected boundary. It is not the full required mutation campaign.
- Python unittest: 85 passing tests, including six tests in actual Lua 5.1. Three cover the remaining named CBA cases: ROUTE-001/002 and CLIENT-001. Together these exercise all 18 named cases locally; this is not a hosted production CBA gate pass.
- Existing API/foundation suite: 7 passing tests. Generated contract consistency passed. Ruff and Pyright passed after correcting the new preview/test tooling.
- Additional tests reject wrong candidate owner/token/permission/generation, oversized or malformed provider responses and unsafe authorization targets.

## Remaining implementation and release work

#0016: after acceptance, implement the authenticated Google/session/recent-auth/Origin/CSRF foundation and the approved shared D1 admission limits, durable lifecycle operation ownership, pending/retiring metadata, atomic audit, stale callback handling and correlated retirement. The repo had only installation credential authentication; a browser session foundation was not already present. Wire the reviewed UI to those actual routes, provision the reviewed minimum writer capability and exercise the actual process topology, including restoration. Do not reuse the proof controller's local lock as production ownership.

#0017: blocked by #0016. Integrate the resolved shared admission limits and real lifecycle authority, then complete the required nine production mutation gates and hosted end-to-end evidence. Wire the official adapter into the actual host client. Exercise native scheduler recovery in the final topology and verify backup/restore includes the new tables. Historical coordination backup inventories do not yet include migration 0005; do not treat them as complete current-schema backups. Admission itself never authorizes live Flickr writes.

Intake remains disabled in `wrangler.example.jsonc`. Deployment also needs actual DB migrations, two native read bindings, a real COORD namespace and scheduled recovery. The local fixture under `probes/intake` has known synthetic credentials and is LOCAL ONLY: it must not be deployed as-is. Hosted use would first require a random outer admission guard, expiry/budget and cleanup automation. No hosted resources or production credentials were created for this checkpoint.

## Review and reproduction

Run `uv run --frozen python scripts/serve_native_preview.py` from the API repo. The server selects a free loopback port and writes its URL/PID to `.coordination-runs/native-ui-preview-status.json`; it serves only allowlisted synthetic assets. The current review server was left running for Terry. Use `npm run intake:test`, `npm run api:test`, `npm run api:check-generated`, `uv run --frozen python -m unittest discover -s tests`, `uv run --frozen ruff check .` and `uv run --frozen pyright` for the recorded checks.

Primary references: [Flickr OAuth](https://www.flickr.com/services/api/auth.oauth.html), [getInfo](https://www.flickr.com/services/api/flickr.photos.getInfo.html), [checkToken](https://m.flickr.com/services/api/flickr.auth.oauth.checkToken.html), [Cloudflare Secrets Store access control](https://developers.cloudflare.com/secrets-store/access-control/), and [Fetch opaque redirects](https://fetch.spec.whatwg.org/#concept-filtered-response-opaque-redirect). OAuth canonicalization uses pinned oauth-1.0a 2.2.6 with runtime CSPRNG nonces; its MIT notice is retained in THIRD_PARTY_NOTICES.md.
