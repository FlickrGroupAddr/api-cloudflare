# api-cloudflare

Public, Cloudflare-hosted components for FlickrGroupAddr.

## Hosted foundation

The [Cloudflare native authority mapping](docs/research/2026-09-06-cloudflare-native-authority-mapping.md)
records the proposed Durable Objects/D1 proof boundaries, accepted-contract
references, failure cases, and fallback criteria. Production storage selection
and live provider conformance remain outstanding.

The [runtime permission probe](probes/runtime-permissions/README.md) evaluates
insert-only record protection through isolated Worker D1 and Durable Object
bindings, with reproducible local/hosted runs and scoped cleanup.

The [Flickr credential-store recommendation](docs/research/2026-09-07-flickr-credential-store-decision.md)
compares native secrets with AWS Secrets Manager, including exact version reads,
independent credential deletion and Workers authentication. It awaits owner
decision for production; the disposable synthetic proof is approved. Its
[disposable proof](probes/secrets/README.md) now includes a signed Worker,
checkpointed controller and lifecycle model. The [hosted evidence](docs/research/2026-09-07-secret-store-proof.md)
records the run results and remaining acceptance gates.

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
