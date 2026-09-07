# Worker routing after the provider-rejection clarification

Date: 2026-09-07

Status: Passing isolated routing proof, ready for owner review. This is not a
production API, authentication implementation, or production release approval.

## Accepted boundary

Terry accepted the recommended clarification on 2026-09-07: a provider's own
HTTP 400 for a malformed target rejected before application routing may use a
non-JSON body without the application's `Cache-Control: no-store`. It must not
serve application-shell content, redirect to an operation, or expose
application/session data. Every application-generated API/health response
retains the existing JSON/no-store requirement. Valid-path provider failures
are not exempt.

Architecture commit `705e9da` records this decision in the accepted
`docs/operations/http-route-conformance.md` and
`docs/operations/health-and-diagnostics.md`, with an explicit clarification in
ADR 0037. The architecture repository's 162 existing tests pass. This replaces
the pending recommendation in the [initial failure record](2026-09-07-worker-routing-proof.md),
without reclassifying that historical run as a pass.

## Implementation and evidence

The collector recognizes the exact observed provider bad-request body by its
SHA2-256 fingerprint, only for a malformed-target case with HTTP 400 and no
fixture response marker. It still rejects unknown HTML, cookies, redirects,
application-generated HTML errors, and errors on valid routes. A changed
provider page fails closed for investigation; the fingerprint is a bounded
probe discriminator, not a production response dependency or a blanket HTML
exception. Regression tests exercise the allowed case and each forbidden
extension.

The isolated Worker and local raw-target guard now mark their responses with
their component and source-derived build ID. Normal gate responses must carry
the expected build, preventing a stale response or wrong owner from satisfying
only a coincidentally correct status. These headers exist only in this fixture,
as permitted by the accepted preview-adapter contract. They do not amend the
production health response. Generated JSON now uses LF explicitly, including on
Windows, so runtime inventory bytes match the tracked generated snapshots.

Two fresh deployments of the same source build each passed:

| Phase | Cases | Result |
| --- | ---: | --- |
| Local HTTP with the actual Miniflare/Static Assets router | 100 | All pass |
| First complete hosted HTTPS sweep | 100 | All pass |
| Second complete hosted HTTPS sweep | 100 | All pass |

That is 200 local and 400 hosted checks across the independent runs. Both gates
returned zero, both deployment identities remained unchanged during probing,
and both temporary Workers have confirmed non-forcing cleanup. The
[sanitized evidence](2026-09-07-worker-routing-clarified-evidence.json) binds the
case sets, accepted provider response, source/runtime artifact hashes, readiness
sample counts, and opaque deployment/version identities to each run. Private
logs and full raw reports remain under the ignored `.route-runs/` directories.

Native TypeScript 7.0.2, Ruff lint and format, Pyright, 32 Python tests, and
three Node regression tests pass. Hosted compatibility date remains
`2026-09-07`; the stable pinned local runtime uses `2026-08-06`. No dependency,
public-fetch compatibility flag, custom-domain rule, or production resource
was changed to obtain these results. The fixture makes no global fetch and has
no database or production secrets. Local outbound Worker fetch count is zero.

## Limits and follow-up

The earlier intermittent provider 404/1042 responses did not recur in the final
four complete hosted sweeps. Their root cause remains unproven. The successful
samples do not demonstrate that response markers fixed them, that they were
all propagation effects, or that they cannot recur. Retain the unchanged strict
checks on valid paths for future runs; do not retry individual failed cases
into a passing report. Any recurrence still fails the complete gate.

The fixture still implements only safe routing responses. Authentication,
durable storage, successful login transactions, production startup invariants,
and business APIs remain outside this proof. Its OpenAPI describes the fixture
and must not be published as an implemented production API contract.

Actual Lightroom Classic host execution remains unverified. The documented
SDK call and header behavior are recorded in the [operating procedure](../../probes/routes/README.md);
the truthful Python collector User-Agent is not a Lightroom compatibility pass.
The existing stable-development-tool advisories in the initial evidence also
remain unchanged. Neither limit is erased by this routing fixture pass.
