# Workers preflight-clock investigation

Date: 2026-09-11

Status: Investigation complete; Terry accepted the scoped private clock profile
in ADR 0056 on 2026-09-12. A hard monotonic guarantee is still not claimed.
Real Flickr group-add capability remains disabled pending production integration.

Terry accepted the narrowly documented private approximation: prepare the
entire signed request before the final D1 marker transaction, then make only an
immediate check of the I/O-refreshed clock and the transport handoff. Keep the
strict observed-age threshold and every marker, lease, gate, ambiguity and
permanent-block rule. This accepts the residual CPU/scheduling/clock-adjustment
gap explicitly; it does not rename the native clock a monotonic guarantee.
The alternative is to retain the current rule and separately evaluate an
ordinary-process dispatch adapter. Changing D1 to RDS cannot change Worker time.

## Observed deployed behavior

The final controlled run completed 37 diagnostic checks across a Worker and a
SQLite Durable Object. These are successful investigation checks, not a passing
clock conformance gate. The peer received actual authenticated HTTPS requests
and checked that the D1 marker already existed. It held no Flickr credentials
and made no real Flickr request.

| Runtime and injected interval | Age reported by the worker at its final check | Independent peer receipt gap | POST observed |
| --- | ---: | ---: | --- |
| Worker: CPU after marker | 65 ms | 2,515 ms | One |
| Worker: CPU after an extra I/O refresh | 133 ms | 2,285 ms | One |
| Durable Object: CPU after marker | 74 ms | 2,704 ms | One |
| Durable Object: CPU after an extra I/O refresh | 83 ms | 2,341 ms | One |

In both hosted paths, `performance.now()` and `process.hrtime.bigint()` advanced
by zero across the CPU-only interval, and the performance value equaled the
wall-clock value. The final local run observed advancing clocks instead.
The deliberately heavy loop is a bounded diagnostic and must not appear in the
production handoff interval.

The peer gap compares wall samples taken in separate request contexts. It
includes transport latency and is not an exact process-local monotonic handoff
timestamp. The independent Python observer also measures full request duration
with its monotonic clock; that includes all network and database time. Neither
measurement is used to assert a universal minimum CPU duration. Together with
the directly observed frozen timers and provider documentation, the record
establishes why this clock cannot prove the current elapsed-time guarantee.
It does not estimate the frequency of a real production stall.

The positive controls confirmed that a 1,200 ms injected marker delay and a
1,200 ms post-marker I/O wait cause refusal before POST. Work before the final
marker, or followed by another I/O read, was reflected in the refreshed sample
in the final stress run. Extra I/O still left a final CPU-only blind interval.
An injected negative clock delta was refused; a separately injected wall jump
did not control the shared comparison. Those injections do not claim that the
provider's actual wall clock was moved or its process scheduler was forcibly
suspended.

## Artifact and reproducibility

Final source snapshot: `9da37299c74478e6bef36fae5f495e23b64eccf5`.
The public [hosted record](../evidence/workers-clock-hosted-2026-09-11.json) and
[local record](../evidence/workers-clock-local-2026-09-11.json) each contain
37 completed diagnostic checks, safe timing observations and exact source/bundle
hashes. Every source hash was compared against that Git commit.

The [84-check crash regression](../evidence/clock-policy-crash-regression-2026-09-11.json)
passed with the extracted shared comparison. An
[inclusive-boundary mutation](../evidence/clock-boundary-mutation-2026-09-11.json)
was detected by its behavioral assertion and the exact original source restored.
Native TypeScript, Ruff/format, Pyright, 79 Python tests and the shared-policy
Node test passed. [Cleanup](../evidence/workers-clock-cleanup-2026-09-11.json)
confirms all five runs' resources were removed.

The TypeScript 7.0.2 native compiler ran before a minified provider bundle was
created. The hosted deployment uploaded that exact bundle with `no_bundle`
enabled; its SHA2-256 digest is retained in the evidence. Compatibility date
was 2026-09-11 hosted and 2026-07-30 locally. Both profiles declare
`nodejs_compat` and `global_fetch_strictly_public`; the second flag is required
for this controlled peer's public Worker-to-Worker route. The fixture has a
5,000 ms per-invocation CPU ceiling, a finite 800-million-iteration stress bound,
a 100-trial database bound and a thirty-minute authenticated lifetime.

The shared `src/dispatch_freshness.ts` comparison is also called by the existing
fail-polite candidate. It rejects invalid/non-integer microsecond inputs,
negative elapsed time and age at or above 1,000,000 microseconds. Extracting that
comparison did not select a production clock. The public Worker still exposes
no real Flickr dispatch path.

Four exploratory hosted runs remain failed: two could not route the synthetic
peer before the documented public-fetch flag was applied; one saw an early
provider 404; and one used an HTTP-derived calibration that did not establish
the expected pre-marker expiry. The final run used stable peer/D1 readiness and
a fixed bounded hosted workload. No failed mutating case was replayed into a
pass. All five hosted runs' disposable Workers, namespaces and D1 databases were
removed and absence verified. Detailed records stay in ignored local run
artifacts; public evidence contains allowlisted check results and safe numeric
observations without credentials or provider identifiers.

## Approved owner handoff

[Accepted architecture ADR 0056](https://github.com/FlickrGroupAddr/architecture-design/blob/78240c077d21f9546f3e728a02d234497c63c053/docs/decisions/0056-accept-private-workers-observed-preflight-time.md) describes the exact private exception, the
required prepared-request boundary, the remaining timing risk and the authority
that changed with approval on 2026-09-12. ADR 0007 and the scoped contracts
now explicitly qualify their preflight-clock wording for the private profile.
Other profiles retain the monotonic-clock requirement.
The broader production conformance gate remains implementation #0018.

No timer service, container, AWS service or new production resource was added.
If the current strict rule is retained, the next step is an evidence-backed
compute/transport decision with full identity, network, recovery, cost and
maintenance review. The lack of one preferred API alone does not establish an
AWS requirement.

## Primary provider sources

Cloudflare's [performance documentation](https://developers.cloudflare.com/workers/runtime-apis/performance/)
and [web standards notes](https://developers.cloudflare.com/workers/runtime-apis/web-standards/#performancetimeorigin-and-performancenow)
explain the frozen-I/O clock behavior and its wall-clock relationship. The
[Node process notes](https://developers.cloudflare.com/workers/runtime-apis/nodejs/process/#hrtime)
identify the compatibility timer's limitation. The
[fetch documentation](https://developers.cloudflare.com/workers/runtime-apis/fetch/)
and [compatibility flag reference](https://developers.cloudflare.com/workers/configuration/compatibility-flags/#global-fetch-strictly-public)
control the fixture's public peer routing. These references corroborate the
observations; they do not turn local tests into a deployed clock guarantee.

## Approval and implementation boundary

Approval resolves #0013 through its scoped owner-decision path. Historical
diagnostic records remain unchanged and are not relabeled as conformance.
Before production use, #0018 must prove the actual prepared-request transport,
with no deferred preparation after marker I/O, and every remaining release
requirement. The bounded candidate and its deliberate fault hooks are not
promoted to production by this documentation change.
