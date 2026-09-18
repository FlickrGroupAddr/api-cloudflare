# api-cloudflare

Public, Cloudflare-hosted components for FlickrGroupAddr.

## Current production status

The Cloudflare-native foundation and complete fail-polite release gate passed on
2026-09-14. The exact qualified Worker artifact was promoted to production on
2026-09-15 with administration and authenticated reads enabled. Submission
intake and Flickr dispatch remain disabled, and both durable write gates remain
paused. On 2026-09-18, the FGA-LrC15 client in Lightroom Classic 15.5.1
successfully verified its first production installation through the read-only
API. This slice is ready for review; write activation remains separate.

The [group discovery API](docs/operations/group-discovery.md) is implemented and
passed local and isolated hosted synthetic checks. Its production flag remains
off pending the scoped refresh-clock decision and deployment checks.

The Lightroom Classic 15 release bundle is
[`clients/lightroom/FGA-LrC15.lrplugin`](clients/lightroom/FGA-LrC15.lrplugin).
Add that directory in Lightroom Classic 15's Plug-in Manager. Version 0.1.0 stores
the one-time Plugin Code in `LrPasswords` and performs only the qualified
current-installation read; it has no publishing or Flickr group-write entry
point.

FGA client builds are tied to the Lightroom Classic major version they were
qualified against. `FGA-LrC15` supports Lightroom Classic 15.x. It may happen to
load in versions 16, 17 or 18 through compatibility, but support for any later
major requires a separately named, tested and qualified client build. Each
major qualification includes a fresh review of the Lightroom SDK because a new
major can materially change available capabilities, including security-relevant
facilities such as a documented cryptographic random-number generator.

See the [read-only promotion record](docs/operations/read-only-production-promotion.md)
and [complete qualification result](docs/research/2026-09-14-complete-suite-qualification.md).

## Hosted foundation

A [sanitized public architecture snapshot](https://github.com/FlickrGroupAddr/architecture-design-public)
is available for browsing the decisions and contracts. The working architecture
repository retains its private history; publication does not change authority.

The [Cloudflare native authority mapping](docs/research/2026-09-06-cloudflare-native-authority-mapping.md)
records the Durable Objects/D1 authority boundaries, accepted-contract
references, failure cases, and fallback criteria. The native production
foundation and release conformance are complete; real Flickr dispatch remains
disabled pending a later controlled activation.

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
pause, generation matching, retirement and recovery boundaries. The production
administration/API integration is deployed. The existing [AWS proof](probes/secrets/README.md)
is retained fallback evidence.
The [AWS backing-service evaluation checklist](docs/operations/aws-backing-service-evaluation.md)
provides a reusable need, proof, cost, recovery and exit record under the current
accepted native-first decisions. It selects and provisions no service.

The [atomic admission and scheduling proofs](docs/research/2026-09-11-admission-and-scheduling-proof.md)
now pass 65 hosted checks: complete D1 batches, exact FIFO/fencing, archive
restoration, real Durable Object resets/alarms and minutely Cron recovery.
[Reproduction and cleanup](probes/coordination/README.md) describe the isolated
fixtures. The batch route is implemented; production intake and Flickr dispatch
remain disabled.

The [native fail-polite crash proof](docs/research/2026-09-11-fail-polite-crash-proof.md)
adds retained attempts, dispatch markers, atomic terminal/block results and
recovery through the shared D1 claim path. The controlled peer observes actual
POSTs independently of database outcomes. Production clock enforcement and the
complete release conformance gate now pass; real Flickr writes remain disabled.
The [release preparation checkpoint](docs/research/2026-09-13-release-preparation.md)
adds prepared signed transport, current-schema archive coverage and strict
production-evidence verification. The later complete suite qualification closes
that historical conformance gap.
The later [production dispatcher checkpoint](docs/research/2026-09-13-production-dispatch-integration.md)
connects the real coordinator, signed transport, shared D1 reservations and
result policy. It records the remaining rotation decision and release work.
The [Plugin Code lifecycle checkpoint](docs/research/2026-09-13-plugin-code-rotation-integration.md)
records the accepted rotation routes, their implementation and one-time transfer UI.
The historical [status and deployment handoff](docs/research/2026-09-13-status-and-handoff-gates.md)
adds read-only submission history and records the DNS and release gates that have
since been completed.

The [hosted clock investigation](docs/research/2026-09-11-workers-preflight-clock.md)
records the native timer blind interval and the private timing profile accepted
by Terry on 2026-09-12 (ADR 0056).
The [authentication limiter review](docs/research/2026-09-11-authentication-limiter-boundary.md)
records the accepted D1 quota-bookkeeping and admission-order clarification
(ADR 0055). Its production paths are included in the completed release gate.

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
