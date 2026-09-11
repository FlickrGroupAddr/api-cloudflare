# api-cloudflare

Public, Cloudflare-hosted components for FlickrGroupAddr.

## Hosted foundation

The [Cloudflare native authority mapping](docs/research/2026-09-06-cloudflare-native-authority-mapping.md)
records the proposed Durable Objects/D1 proof boundaries, accepted-contract
references, failure cases, and fallback criteria. Production storage selection
and live provider conformance remain outstanding.

Accepted [ADR 0051](https://github.com/FlickrGroupAddr/architecture-design/blob/b6676de7e9af78d352344d720ca81b96e6d2e8c1/docs/decisions/0051-trust-private-storage-runtime-with-guarded-writes.md) now permits guarded native writes
with trusted deployed code for the private deployment. The runtime-permission
finding alone no longer forces an RDS fallback. The new [D1 foundation and installation-read handoff](docs/research/2026-09-11-d1-foundation-and-installation-read.md)
records the implementation, migration/guard/recovery evidence, and Terry's
approved clock-resolution and early-authentication-rejection clarifications. See the
[proof procedure](probes/foundation/README.md) and the generated
[API description](generated/openapi.json). The
[earlier runtime decision handoff](docs/research/2026-09-06-native-runtime-permission-evidence.md)
remains historical capability evidence.

The [runtime permission probe](probes/runtime-permissions/README.md) evaluates
insert-only record protection through isolated Worker D1 and Durable Object
bindings, with reproducible local/hosted runs and scoped cleanup.

The [Flickr credential-store recommendation](docs/research/2026-09-07-flickr-credential-store-decision.md)
now follows accepted [ADR 0052](https://github.com/FlickrGroupAddr/architecture-design/blob/abcb2d192063783400634aa50c736c1d0a6a523a/docs/decisions/0052-evaluate-paused-native-credential-replacement.md): evaluate paused native
replacement with generation checks before AWS. The [native lifecycle proof](docs/research/2026-09-11-native-secret-lifecycle-proof.md)
now passes all 29 hosted cases with confirmed cleanup. Its
[reproduction procedure](probes/native-secrets/README.md) explains the tested
pause, generation matching, retirement and recovery boundaries. Production
UI/API integration remains separate. The existing [AWS proof](probes/secrets/README.md)
is retained fallback evidence.

The [atomic admission and scheduling proofs](docs/research/2026-09-11-admission-and-scheduling-proof.md)
now pass 65 hosted checks: complete D1 batches, exact FIFO/fencing, archive
restoration, real Durable Object resets/alarms and minutely Cron recovery.
[Reproduction and cleanup](probes/coordination/README.md) describe the isolated
fixtures. Public batch-route integration and Flickr dispatch remain separate.

## Routing proof

The [Worker routing proof](probes/routes/README.md) derives a route inventory and
OpenAPI from one typed registry and tests local HTTP plus isolated Cloudflare
HTTPS with real static assets. Its [current evidence](docs/research/2026-09-07-worker-routing-clarification.md)
records passing fixture gates after the accepted malformed-target clarification.
It is not a production API or a production release approval.

## Local session hooks

Codex session hooks start and gracefully stop the **FGA implementation** localswim
board at <http://127.0.0.1:8795/>. The Windows setup follows the sibling
`architecture-design` project's lifecycle pattern, scoped to this repository's
board. See [the operating procedure](docs/localswim-session-hooks.md), including
the one-time Codex hook review and manual commands.

## License

Original FlickrGroupAddr source code and documentation in this repository are
licensed under the [MIT License](LICENSE), copyright 2026 Terry Ott.
Third-party components retain their own copyright and license terms.
