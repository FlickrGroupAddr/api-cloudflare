# Fixed-origin split wrapper: offline isolation proof

Date: 2026-10-16. Ticket #0038. Status: implemented for independent review;
no hosted/native qualification, deployment or production acceptance.

## Approved source boundary

The #0036 exact production capture remains the ordinary-request dispatcher and
rollback baseline. Its decoded module has 445,699 bytes, SHA2-256
`f1cef97fe6e1e62b5ff2b57f7e11516423974e756011750feb1aebe3abb13e6d`.
Its 25 registered routes include installation-current but omit existing-photo
discovery and thumbnail. Independent Sol / High review executed the unmodified
capture offline and measured 401/404/404 on the three intended GET paths with
zero database, binding, upstream or host-I/O calls. The earlier missing-handler
finding remains an observation about that capture.

Terry explicitly approved correcting the source scope on 2026-10-16: candidate
commit `b599ca828d2a645b686aca0354d6c8ee2c2a0250` supplies the synthetic
qualification branch only. The captured ordinary dispatcher remains unchanged.
This decision supplies the previously missing candidate source boundary; it does
not waive #0037, authorize deployment/native execution or qualify production.

`prepare_fixture.py` extracts source and migrations with `git archive` of that
exact commit, rather than the working tree. It hashes every source input and
builds the unchanged candidate entrypoint with the installed pinned esbuild
0.28.1 API and Node.js 24.22.0. Candidate bundle: 601,051 bytes, SHA2-256
`c1edd7e5e721119030085c9c0705de5d2f3a32b9cffc6bbed56f363df3432e36`.
No router, authentication or thumbnail source is rewritten. Bundle size/digest
and each source input are checked before the integration tests execute.

## Small temporary composition

`probes/fixed-origin-isolation/wrapper.mjs` exports only a factory and finite
constants. It adds no public seed/control endpoint, configuration file, deployment
binding, arbitrary URL, secret reader or provider access. It has no scheduled
entrypoint. Ordinary requests pass their original Request and production
environment objects directly to the exact captured default fetch dispatcher.

Any header beginning `X-FGA-Qualification` or an Authorization scheme beginning
`FGA-Qualification` opts into closed selector validation. Invalid selected
requests receive an empty 404/no-store and never reach either dispatcher.
The trusted constructor supplies one 32-hex run, one 64-hex capability and an
inclusive-start/exclusive-expiry lifetime of at most ten minutes. Test constants
are public synthetic markers and are not a deployment credential. Three finite
cases exist: `ok`, `missing-auth`, `invalid-auth`. Only HTTPS origin
`https://flickrgroupaddr.com`, GET, and these exact path/query strings qualify:

| Path/query | Candidate behavior exercised |
| --- | --- |
| `/api/v001/installations/current` | Installation authentication/current representation |
| `/api/v001/existing-public-photos?page=1&page_size=1` | Authenticated public-photo discovery |
| `/api/v001/existing-public-photos/photo/thumbnail?page=1&page_size=1&linked_flickr_revision=1` | Authentication, discovery, thumbnail request and response |

Missing, duplicate, foreign, malformed or expired selectors; unknown control
headers; other methods/origins/paths/query order/extra query fields; encoded photo
identity, bodies, nonzero Content-Length, Transfer-Encoding and already-aborted
requests fail closed before dispatch. There is no requested expiry or destination
input. Cases do not permit resource creation, writes or broader faults.
The selected branch compares the full observable Request URL to the exact
allowlist, including empty `?` and `#` delimiters. This proves behavior for the
URL exposed by the host; it cannot recover raw wire syntax already normalized
by the host networking stack. Ordinary captured delegation is unchanged.

The external capability uses the exact `FGA-Qualification <capability>` scheme.
Production installation credentials use `Bearer <credential>` and therefore
cannot equal it regardless of credential value. No real bearer is read to prove
this namespace separation. Only after all selectors pass does the wrapper
construct a new synthetic Authorization header; candidate authentication remains
unchanged and validates the fixed synthetic installation using its real SQL.
Missing/invalid-auth cases exercise its real refusal paths. All client headers,
including qualification selectors, cookies and credentials, are stripped at this
seam. The synthetic request is never sent to the captured ordinary dispatcher.

The synthetic environment is an explicit frozen allowlist: one isolated database,
fixed in-memory application/grant readers, the three required read gates, and
explicitly disabled admin/group/intake/dispatch/upload gates. It never reads,
enumerates or spreads the production environment. The candidate createWorker
fetch seam receives a fixed memory responder. It admits only the exact signed
Flickr discovery operation/parameters and one fixed credential-free image URL;
responses are static synthetic JSON and PNG bytes. No network implementation is
available through that seam and no redirect is followed.

## Offline evidence and limits

**59 JavaScript integration checks and 11 Python checks passed.** The actual
unmodified captured and candidate bundles execute in separate Node.js VM
contexts. Actual Node SQLite applies migrations from the pinned candidate and
supplies D1 prepare/bind/batch semantics, including transactions and foreign keys.
Nine candidate cases cover all three actual handlers and authentication outcomes.
Ordinary-path tests assert identical original Request/environment objects,
expected captured statuses and matching response headers. The candidate branch
runs with a production-environment proxy that throws on reads/enumeration.

Counters observed zero production-environment reads, production database calls,
global fetches, filesystem/network host calls and dynamic imports. Two discovery
pages and one PNG were served in memory. No photo binding or submission intent
was created. Synthetic rate-budget writes remain inside the in-memory database.
VM instrumentation links only pure helper imports and throwing host-I/O proxies;
it is a test harness for trusted pinned source, not a security sandbox for
arbitrary executable code. Node VM modules remain experimental. This is SQLite
adapter evidence, not Miniflare, D1/provider, HTTPS edge or Lightroom host proof.

The Python inspector remains a separate textual prerequisite tool. Its exit 1
for the old capture is expected and is not an isolation failure after the approved
split. A positive textual result alone never qualifies behavior. It validates
version/module shape, canonical base64/UTF-8 and bounded sizes without executing
source. Python preparation refuses wrong capture digest, nonprivate/repository
output, existing output directories and archive traversal. It never overwrites
evidence. Ruff check/format and Pyright passed for all new Python files.

## Reproduction and private evidence

Retrieve the exact capture through
[the inventory guide](existing-photo-inventory-2026-10-16.md), final capture
20261016T214740Z. Keep raw module source, provider configuration, identities,
restoration inputs, test logs and decoded artifacts outside Git. Preparation
requires a new output directory beneath an existing `private-evidence` ancestor,
outside the repository, and leaves the original capture untouched.

```console
uv tool run --from uv==0.12.5 uv run --frozen python probes/fixed-origin-isolation/prepare_fixture.py <repository> <private-version-modules-json> <fresh-private-output> <pinned-node-24.22.0>
```

Set `FGA_OFFLINE_FIXTURE` to that output directory, then execute with pinned Node:

```console
node --experimental-vm-modules --test probes/fixed-origin-isolation/isolation.test.mjs
uv tool run --from uv==0.12.5 uv run --frozen python -m unittest tests.test_fixed_origin_capture_prerequisites tests.test_fixed_origin_fixture_preparation
```

The integration test emits a closed sanitized receipt containing commit/digests,
fixed counts and false hosted/native qualification booleans. Parent integration
must retain independent Sol / High review of this new composition and correct any
material findings. #0039/#0040 own broader fault/native-facing matrices; #0042
owns lifecycle provisioning. A later deployable composition needs its concrete
resources, finite lifecycle, cleanup/restoration and unchanged-handler review.
No such live step is authorized or qualified by these offline results.
