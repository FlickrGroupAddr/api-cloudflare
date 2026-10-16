# Existing-photo disposable hosted qualification

Date: 2026-10-16. Status: disposable synthetic hosted matrix passed; production
edge and real native HTTP transport qualification remain pending.

[CI run 38929606706](https://github.com/FlickrGroupAddr/api-cloudflare/actions/runs/38929606706)
on source `1fb7ca8` passed all 22 cases and confirmed its newly created Worker
and D1 deleted. The [sanitized successful receipt](existing-photo-hosted-ci-passed-2026-10-16.json)
retains source, migration, exact uploaded artifact, dry-run configuration and
secret-elided upload-metadata SHA2-256 hashes, case outcomes, observed timings
and cleanup flags. It contains no account/resource IDs, credentials, raw HTTP
payloads, image bytes or private journals. Fresh synthetic resource names are
nonsecret recovery correlation only.

## Exercised scope

The disposable Worker used compatibility date `2026-10-16`, `nodejs_compat` and
`enable_request_signal`, a new migrated synthetic D1 and its own workers.dev
endpoint. The wrapper imports the actual production router, authentication,
discovery and thumbnail handlers. Its fixed synthetic upstream responder makes
no real Flickr request and exposes no generic proxy, production domain, real
credential, dispatch binding or write route. Production feature flags were not
enabled by this proof.

All cases passed: PNG and JPEG marker responses, discovery, missing/invalid
authentication, malformed query, requested revision, owner/public/exact-photo
and destination checks, rejected upstream redirect/large error, declared and
streaming byte excess, truncation, media/signature rejection, the real abort
timer and final link/grant/installation fences. The timeout returned sanitized
503 after 15,103 ms of runner-observed time. That observation is not a hard elapsed
guarantee across host stalls. All 22 responses matched the fixed public harness
marker; the marker remains a forgeable diagnostic, not origin authority.

## Earlier attempts remain failures

| CI run | Observed outcome | Cleanup |
| --- | --- | --- |
| `38923320751` | Failed before cases with the older undifferentiated ValueError receipt; exact gate/seed cause unresolved | Both acknowledged resources deleted |
| `38925097716` | PNG passed; JPEG failed without per-case response detail; cause unresolved | Both acknowledged resources deleted |
| `38926857739` | PNG/JPEG/discovery passed; missing-auth observed nonempty 404/text without probe counters; source of that response unresolved | Both acknowledged resources deleted |
| `38928453236` | Offline verification failed because its checkout omitted the newly added isolate fixture | Cloud step skipped; no resources or hosted receipt |
| `38929606706` | Corrected checkout passed all 22 disposable synthetic cases | Both acknowledged resources deleted |

The final pass does not retroactively qualify earlier failures or establish their
cause. Offline independent Node isolates with an unseeded, throw-on-access DB
return the expected empty 401 for missing installation authentication and empty
404 for missing/wrong outer access, with zero DB accesses. No mutable per-isolate
fixture/control state was found. The unexplained nonempty 404 was not reproduced
as a fixture defect; checks and fixture behavior were not relaxed to pass it.

## Local verification and handoff

The exact pre-cloud commands passed using portable Node 24.22.0, cached npm
12.2.0 and frozen Python tooling: native TypeScript 7 check and 20 offline tests.
Ruff, Pyright and scoped whitespace checks also passed. The [probe README](../../probes/existing-photo-qualification/README.md)
documents bounded transport, fixed provisioning, single-attempt mutations,
sanitized diagnostics, exact-name recovery and narrow cleanup. The independent
[runner review](existing-photo-hosted-runner-review-2026-10-16.md) records source
reviews and their limits. The original local emulator generation predates the
hosted compatibility date and supplies no newer-runtime conformance claim.

The primary's [ten native fixture scenarios](existing-photo-native-synthetic-2026-10-16.json)
passed separately. Those supported
host/UI observations do not establish real `LrHttp.get` response-allocation,
redirect-Authorization behavior or the production edge's behavior. The combined
release boundary still needs the applicable production custom-domain/cache/
firewall/auth/error/disconnect checks, actual supported native HTTP transport
qualification, and any narrowly authorized real public-photo read. The hosted
request-signal flag's presence alone does not prove disconnect behavior; JPEG/PNG
marker acceptance does not prove full image decoding.

The detailed architecture thumbnail candidate remains Proposed under accepted
ADR 0061. Its production acceptance, read-capability activation and intake/Flickr
write activation remain independent owner gates. This handoff performs no further
CI dispatch, hosted request or resource operation.
