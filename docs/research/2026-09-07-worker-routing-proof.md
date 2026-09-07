# Initial Worker and Static Assets routing proof

Date: 2026-09-07

Status: Historical failure record for implementation commit `0919c1d`.
Terry subsequently accepted the malformed-target clarification on 2026-09-07;
see the [current implementation and passing evidence](2026-09-07-worker-routing-clarification.md).
The original results below are retained as history, not current contract authority.

## Result and decision

The implementation uses one typed registry for handler dispatch, generated
inventory, OpenAPI, and Worker-first asset configuration. The final matrix has
100 cases. Local HTTP passes all 100. Both final isolated Cloudflare HTTPS
sweeps pass 97/100, with failures retained independently. The repeatable
malformed request is `GET /api/%00`: the provider responds `400` with
`text/html` and without `Cache-Control: no-store`, instead of the gate's required
JSON/no-store discriminator. This is rejection of a malformed request, **not**
an administrative shell response, successful authentication, or evidence of
credential exposure. The gate remains nonzero.

The final sweeps also retain intermittent provider `404` responses, including
error `1042`, on different otherwise valid paths. The first sweep fails DELETE
batch-admission and installation-current probes with 1042; the second fails
the startup HEAD navigation probe with an HTML 404 and the shell with 1042.
An earlier run passed 99/100, but it is not substituted for the final results.
Sustained readiness does not establish that these provider failures are resolved.
Their cause remains unproven and must be investigated before routing acceptance,
regardless of the malformed-target decision.

The exact accepted text in the health contract is: “Server-owned `404`, `405`,
and malformed-request responses in these namespaces are also JSON and
`Cache-Control: no-store`.” The routing contract separately requires malformed
targets to be rejected before static fallback. The distinction needing review
is whether a provider's rejection before application routing falls within that
JSON/no-store promise. The implementation does not silently exempt it.

Recommended owner clarification: permit a provider-generated HTTP 400 for a
malformed target rejected before application routing, provided it never serves
application-shell content, redirects to a registered operation, or returns
application/session data. Preserve JSON/no-store for all application-generated
API and health responses and retain explicit tests for both boundaries.
This is a proposed scoped clarification, not an adopted exception.

If strict JSON/no-store must also cover the provider's early HTTP parser,
evaluate the actual custom-domain error-handling boundary and its supported
configuration before selecting another adapter. A Worker cannot rewrite a
response for a request it does not receive. No zone settings, WAF rules, custom
domain, or production deployment were changed during this proof.

## Authority and implementation scope

Architecture baseline: `a02d02558fe0a384f27c6b9c5aee59f340f2fc4a`.
Controlling sources in the architecture repository:

- Accepted ADR 0016, `docs/decisions/0016-derived-route-conformance.md`.
- Accepted `docs/operations/http-route-conformance.md`, including method-independent
  ownership, namespace guards, generated configuration, both real HTTP boundaries,
  artifact binding, and the fixed non-destructive matrix.
- Accepted ADR 0037 and `docs/operations/health-and-diagnostics.md`.
- Accepted ADR 0043 for the exact Google-login URI; ADR 0031 for API naming.
- Accepted ADR 0050 for Cloudflare selection and native-service evaluation.

The [operating procedure](../../probes/routes/README.md) describes reproduction,
cleanup, and the source files. This is a routing fixture: it rejects protected
operations, performs no database or Flickr call, creates no login transaction,
and has no production secrets. The generated OpenAPI explicitly represents
only that fixture; neither successful authentication nor the installation-read
slice is implemented. The fixed startup handler does not claim production
startup invariants. Route fixture success alone cannot approve production.

## Evidence

The [sanitized machine-readable evidence](2026-09-07-worker-routing-evidence.json)
contains the final case results, opaque deployment/version identities, pass/fail
counts, compatibility dates, and SHA2-256 artifact digests. Private run logs and
manifests remain ignored under `.route-runs/`; they are not public artifacts.

The matrix covers every registered safe handler, unsupported methods, browser
navigation requests, exact/prefix API ownership, retired routes, invalid
callback/login inputs, shell and hashed asset bytes, unsafe asset methods,
health invariance, malformed targets, and matching files that could otherwise
intercept handlers. Local outbound fetch count is zero. The same prebuilt Worker
bundle is used locally and remotely, with configuration hashes recording the
explicit local compatibility-date difference. Deployment identity is checked
before and after collection. Temporary hosted Workers were deleted through a
non-forcing operation and absence was verified.

Native TypeScript 7.0.2 validation, Ruff lint/format, Pyright, 30 Python tests,
and three Node regression tests pass. `npm ci` reproduced the existing lockfile.
Node is 24.20.0 LTS, npm 12.0.2, Wrangler 4.116.0, and Miniflare 4.20260730.0.
Cloudflare accepted compatibility date `2026-09-07`; the pinned local runtime
uses `2026-08-06` and supplies no evidence about the newer deployed runtime.

## Findings incorporated during implementation

The first local topology let the emulator turn raw `/admin\` into `/admin/`
before the Worker saw the request. The real local adapter now validates the
raw Node HTTP request target with the shared validator before forwarding it
unchanged to Miniflare. The hosted boundary already rejects that input. This
is why Worker unit tests alone are insufficient for routing acceptance.

Fresh workers.dev deployments initially returned intermittent provider 404s.
A single successful health sample was insufficient. The collector now requires
five consecutive successful health/API/shell sample sets and at least 30 seconds
of settling, retains the complete readiness history, then runs two full unchanged
matrices. Both sweeps must pass. Early runs are failed attempts, not additional
conformance passes. The deployment is never promoted by retrying individual
failing matrix cases. Some failures persisted after settling; attributing all
of them to propagation would overstate the evidence.

Cloudflare's [Worker error reference](https://developers.cloudflare.com/workers/observability/errors/)
associates 1042 with an unsupported same-zone Worker fetch. The fixture uses an
ASSETS service binding and makes no global fetch; the unsupported-method branches
do not call that binding either. No compatibility flag was changed by inference
from the error code. A provider reproduction should distinguish the asset router,
public workers.dev boundary, and application dispatch before selecting a fix.

Cloudflare's [asset configuration](https://developers.cloudflare.com/workers/static-assets/binding/)
supports running the Worker before assets. Its
[normalization documentation](https://developers.cloudflare.com/rules/normalization/how-it-works/)
describes backslash conversion as part of Cloudflare normalization.
The [raw URI field documentation](https://developers.cloudflare.com/ruleset-engine/rules-language/fields/reference/raw.http.request.uri.path/)
also warns that HTTP-server normalization can precede raw rule fields. These
sources support testing the actual boundary; they do not prove an untested
custom-domain rule can rewrite an early parser error.

## Remaining limits

The architecture's `docs/plugin-service-contract.md` documents `LrHttp.get`
with caller-supplied `Authorization`, using the locally restored licensed SDK
as primary evidence. This run used a truthful collector User-Agent and no real
credential. It does not establish the Lightroom Classic host's default
User-Agent, TLS behavior, or an actual LrHttp call. Real host compatibility
remains outstanding before the installation-read slice can be accepted.

The reproducible npm install also reports existing development-tool advisories:
Undici below 7.29.0, inherited by the pinned Miniflare and Wrangler (one high and
two moderate package findings). The suggested direct Miniflare upgrade is an
alpha, conflicting with the current stable-tooling preference. No automatic
force upgrade or new override was introduced. The dev server stays loopback,
and the Worker fixture has no outbound dependency calls. These controls are
scope limits, not a claim that the toolchain is vulnerability-free; reconcile
the stable toolchain before broadening the development exposure.
