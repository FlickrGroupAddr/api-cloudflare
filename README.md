# api-cloudflare

Public, Cloudflare-hosted components for FlickrGroupAddr.

## Hosted foundation

The [Cloudflare native authority mapping](docs/research/2026-09-06-cloudflare-native-authority-mapping.md)
records the proposed Durable Objects/D1 proof boundaries, accepted-contract
references, failure cases, and fallback criteria. Production storage selection
and live provider conformance remain outstanding.

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
