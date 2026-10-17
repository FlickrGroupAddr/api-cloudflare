# Fixed-origin lifecycle: offline preparation

Date: 2026-10-17. Ticket #0042. Status: offline implementation and test model;
no provider implementation, credential access, deployment or native execution.

The Python lifecycle uses the existing repository's private identity-journal and
acknowledged-deletion conventions. It does not reuse hosted imports because
those import credentials, provider APIs and execution helpers. Its SQLite
journal adds a committed attempt latch before every simulated mutation.
The injected operations interface is exclusively an offline test seam. The
public CLI always refuses with exit status 2 and cannot select a live adapter.

## Exact proposed packet inventory

The still-proposed 2026-10-16 plan used a 24-hex resource suffix. This offline
packet refines it to **one 32-character lowercase hex run identity**, matching
the accepted #0038/#0039 selector and #0040 native packet. There is no second
resource or qualification identity. This refinement requires later packet
review; it grants no live authority.

| Item | Exact identity or scope |
| --- | --- |
| New synthetic D1 | `fga-fixed-origin-db-{run}`; acknowledged exact database ID privately journaled |
| New receiver Worker | `fga-fixed-origin-recv-{run}`; own workers.dev endpoint; only run-specific #0040 receive paths and gated aggregate report |
| Existing production Worker | Existing `fga-api` on `https://flickrgroupaddr.com`, existing whole-host attachment; proposed temporary composition only |
| Qualification binding names | `FIXED_ORIGIN_DB`, `FIXED_ORIGIN_RUN`, `FIXED_ORIGIN_CAPABILITY`, `FIXED_ORIGIN_CANARY`, `FIXED_ORIGIN_RECEIVER` |
| Temporary Actions secret names | `FGA_FIXED_ORIGIN_CAPABILITY`, `FGA_FIXED_ORIGIN_CANARY` |
| Synthetic capabilities | Each secret would contain a fresh 64-character lowercase hex value; this model generates, accepts and stores no secret values |

All four fresh resource/secret names must be absent before the first create.
Each is attempted once. A preexisting name refuses the attempt without any
create, overwrite or removal. The two Actions secret names are explicit future
packet choices, not existing configured secrets or approval to create them.
Delete only names with this journal's acknowledged create and exact identity.
No new route, hostname, DNS record, Durable Object, queue, Secrets Store, OAuth
grant or Flickr identity belongs to this inventory.

The qualification environment is the #0038 explicit synthetic allowlist: this
D1, fixed in-memory application/grant readers, the three read gates and disabled
admin/group/intake/dispatch/upload gates. Keep production environment objects
outside this branch. Receiver destinations derive privately from this run's
receiver identity and finite packet paths; clients cannot choose a URL.

`FIXED_ORIGIN_RECEIVER` is a proposed fifth qualification binding: a narrow
Worker service binding to that exact receiver Worker. The constructor receives
it privately; ordinary request dispatch never looks it up in the production
environment. Same-origin #0040 receive paths and `/report/{run}` forward only
Authorization and the synthetic canary header to the actual receiver. Production
Bearer arrivals are rejected before forwarding or durable receiver access.
Header-stripped arrivals can still record the required missing-auth observation.
This binding addition needs #0044 review and #0045 authorization.

## Closed offline Worker composition

`probes/fixed-origin-lifecycle/composition.mjs` composes the unchanged #0038
ordinary dispatcher and synthetic wrapper with actual durable quota admission
before handler work and a publication fence after the response/edge stimulus.
It supports only the three #0038 cases and ten #0040 post-handler edge cases;
edge cases select only the exact thumbnail route. All other #0039 case IDs are
refused. Full twenty-case native entrypoint integration remains #0041 work.
The Node-only #0039 fault factory is never imported by this Worker module graph.

The small Web API PNG helper preserves #0039's finite PNG/padding bytes. The
edge stimulus accepts only that exact fixture or the unchanged #0038 wrapper
PNG; it does not accept arbitrary upstream callbacks or byte payloads. The
composition uses one matching durable run/start, a maximum ten-minute inner
window and the unchanged twenty-minute outer budget. No ordinary request touches
the quota or receiver. Constructor wiring is offline preparation, not a provider
entrypoint, full execution packet, or native qualification claim.

## Durable budget and time contract

The shared probe's `initializeQuota` and `createQuotaGuard` own the actual SQLite/D1
conditional admissions. Its durable limits are 96 combined FGA qualification
admissions, 16 combined receiver/report admissions and a 1,200,000 ms outer
lifetime. Per-isolate counters are not an authority. Requests check admission
before fixture work and check expiry/admission again before publication.
Every fixed-origin receive and report request consumes the 96 FGA budget before
forwarding, then the receiver consumes its separate combined 16 budget. Only the
finite internal `fixed-origin-receive` and `fixed-origin-report` guard cases
admit this forwarding; clients cannot select them as handler cases. Exhausting
96 prevents forwarding and receiver storage even when its 16 budget remains.
After each awaited scope/admission/publication read, the composition rechecks
the original signal and inner lifetime. The binding Request carries that signal.
These are offline request fences, not a native active-abort qualification claim.
The Python lifecycle validates `inspect()` identity, initialization, exact
limits, start/expiry, enabled state and remaining counts before installing the
simulated qualification composition and after that operation returns.

The #0038 qualification window remains **at most 600,000 ms** from the outer
start, contained within the 20-minute outer resource window. Neither this model
nor the quota probe widens the accepted wrapper's ten-minute window. The second
ten minutes leaves cleanup reserve; expiry stops admission and never substitutes
for exact restoration or deletion. Cleanup remains permitted after expiry.

The receiver stores only aggregate counts and Authorization-present/canary-match
booleans. It does not persist headers, bodies, credentials, URLs or photograph
metadata. Its receive/report requests share one durable budget. Provider traffic
and billing outside admitted work are not capped by these counts.

## One attempt and fail-closed cleanup

1. Capture and privately pin the exact production artifact/configuration and
   digest before any later authorized mutation. #0043 owns the concrete rollback
   capture/restoration proof. Supply that digest to the offline lifecycle.
2. Open a private journal for the exact run and start time. Reopening with another
   run, time, capture digest or resource inventory refuses. Keep the journal and
   SQLite sidecars private and outside tracked/public evidence.
3. Acquire the exclusive lifecycle ownership marker. Competing operators and a
   marker retained after a crash require explicit reconciliation. Never assume
   a marker is stale or remove one automatically.
4. Check every name absent; latch each creation before calling its offline seam.
   Journal only acknowledged exact identities. An exception or missing identity
   leaves the operation attempted and unacknowledged. Never recreate by name,
   retry the mutation, invent an ID or overwrite a secret.
5. Initialize the durable quota state, inspect its readiness, then simulate the
   exact binding installation once. Recheck expiry and durable readiness after
   publication. `attempt()` invokes cleanup in `finally`, including cancellation.
6. Cleanup first durably disables admission, then inspects the matching run to
   confirm `enabled:false`. It requires exact restoration acknowledgment with
   the captured digest, ordinary-route verification, removed qualification
   bindings, disabled write gates and unchanged production state.
7. Only after those acknowledgments, remove this attempt's acknowledged temporary
   secrets, exact receiver and exact synthetic D1 in reverse creation order.
   A delete seam succeeds only after exact identity matching and confirmed
   absence. Failed/ambiguous deletes are retained and never blindly repeated.

An unknown create, failed admission-off check, failed exact restoration or
unconfirmed deletion retains `cleanup_unconfirmed` and the private identities.
Repeated cleanup reads the terminal result and performs no further mutations.
If a crash leaves an attempted operation or owner marker, preserve both for a
later explicitly reviewed reconciliation procedure. No automatic recovery path
is offered by this preparation ticket.

## Verification and remaining gates

Focused tests cover exact inventory, preexisting-name refusal, restart after
ambiguous create, disabled live adapter/CLI, competing owner marker, quotas,
expiry before work and publication, shorter qualification window, restore/off
barriers, cancellation/failure cleanup and unconfirmed delete without replay.
Use the repository's pinned workflow:

```console
uv tool run --from uv==0.12.5 uv run --frozen python -m unittest tests.test_fixed_origin_lifecycle
uv tool run --from uv==0.12.5 uv run --frozen ruff check scripts/fixed_origin_lifecycle.py tests/test_fixed_origin_lifecycle.py
uv tool run --from uv==0.12.5 uv run --frozen pyright scripts/fixed_origin_lifecycle.py tests/test_fixed_origin_lifecycle.py
```

These are offline model results. They do not prove provider behavior, actual
resource cleanup, HTTPS edge behavior or Lightroom Classic host qualification.
The #0037 negative verdict remains negative. #0043 exact restoration rehearsal,
#0044 independent execution-packet review and #0045 concrete live authorization
remain separate gates. No production capability or downstream write gate is
enabled by this implementation.
