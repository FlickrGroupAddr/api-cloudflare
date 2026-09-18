# Writable-group discovery

Status (2026-09-18): implementation and isolated synthetic validation complete;
production activation pending owner decision on the refresh-clock contract.

## Behavior

`GET /api/v001/groups?page_size=100` authenticates each installation read and
resolves the current linked owner. `FGA_READ_ENABLED=1` and
`FGA_GROUPS_ENABLED=1` are both required. Submission intake, Flickr dispatch,
and durable write gates remain independent and are not enabled by discovery.

Migration `0013_group_discovery.sql` introduces a disposable snapshot cache,
one refresh-control row per user, and staging rows. The existing minute cron
claims at most one queued refresh per invocation. That invocation owns the
whole page walk, including a fresh OAuth signature and shared Flickr budget
reservation for each page. There are no per-page jobs or retained generations.
This adds no service or Durable Object class.

The API serves the last complete snapshot for 15 minutes as fresh. Older data
is explicitly stale while a refresh is queued/running or has failed. Initial
empty-cache responses are `202` with `Retry-After: 60` and the closed body
`{"schemaVersion":1,"status":"refreshing"}`. A failed refresh with no usable
snapshot returns `503 group_refresh_unavailable`. The 60-second per-user
admission interval applies to failures as well as successes.

The cron can take up to the next minute to start a newly queued job. Queued work
expires after two minutes; a claimed invocation has a 60-second D1 deadline.
Request and scheduled cleanup fail expired jobs and clear abandoned staging.
A subsequent initial read may admit a new attempt after the cooldown. A stale
worker's job ID, installation version, linked revision and secret generation
must still match at staging and publication; revoked or replaced authority
cannot publish. Loss of a result after commit does not replay the job.

Publication uses one D1 transaction to replace all visible rows and advance
the revision. Page metadata and rows are read in one D1 batch transaction.
Continuation requires both `snapshot_revision` and `after_group_id`; a changed
revision returns `409 snapshot_changed`. Every response is `no-store`.

The upstream page parser accepts Flickr's documented `per_page` metadata and
the JSON `perpage` spelling, rejects conflicting aliases, validates all reduced
ID/name rows, rejects duplicate IDs and drifting pagination, and never records
raw provider payloads. Limits are 25 pages, 10,000 rows, 2 MiB per response and
60 seconds of observed elapsed time. Empty validated snapshots remain distinct
from failed or incomplete discovery.

## Clock decision required before production

The accepted group snapshot contract says **monotonic** elapsed time. The
previous hosted clock investigation proved that Workers' performance and Node
clocks can remain fixed across CPU-only work. Accepted ADR 0056 applies to the
group-add preflight window; its exact scope does not amend group-refresh time.

The implemented, currently disabled refresh path checks the native observed
clock before and after page work, rejects backwards time and elapsed values of
60 seconds or more, aborts fetch/body waits on a 60-second timer, and requires
an unexpired D1 deadline before every staging/publication transaction. Page,
row and byte caps remain unconditional. Those checks do not constitute a hard
monotonic real-elapsed-time guarantee during unobservable stalls or wall-clock
adjustments.

Recommendation awaiting Terry: explicitly accept this practical native timing
model for read-only group refresh as well. A delayed cache refresh cannot add a
photo to a group. Record the scoped owner decision in the canonical accepted
contract/ADR before production activation. If declined, retain the disabled
flag and evaluate alternatives without claiming the current implementation
satisfies the strict requirement.

## Validation and remaining activation work

- Fifteen Node/SQLite tests cover query grammar, signatures, complete page
  walks, exact 25-page/10,000-row boundary, failures retaining the old snapshot,
  atomic publication rollback, credential/relink fencing, expired-worker
  replacement, duplicate invocations, stalled fetch/body cancellation, and the
  production cron's shared rate budget with intake disabled.
- One compiled workerd/native D1 test covers concurrent admission, ordering,
  continuation, revision rejection, and absence of dispatch attempts.
- The [hosted synthetic record](../evidence/group-discovery-hosted-2026-09-18.json)
  covers a disposable Worker/D1 deployment at compatibility date 2026-09-11.
  Its temporary resources were deleted. No production resource or real Flickr
  credential was used. This proves the hosted SQL/API path, not real Flickr
  account integration or a strict clock guarantee.
- Affected authentication, status and rate-budget tests and current-schema
  archive/restore checks pass. Local workerd supports 2026-07-30, so its runtime
  result is recorded separately from the hosted compatibility date.

After the clock decision, apply migration 0013 and qualify the exact proposed
production artifact/configuration. Enable only discovery and perform the
bounded owner-authorized real Flickr read. Record the result and keep all
submission/write controls paused. Ticket #0022 then consumes this endpoint in
the FGA-LrC15 browser.

Operational stop: set `FGA_GROUPS_ENABLED=0`. Existing current-installation
reads and administration continue independently. Rollback to the prior Worker
artifact can leave the additive cache tables in place; it must not roll back
or delete permanent submission history. New jobs stop while discovery is off;
expired cache jobs are failed when discovery resumes.

Reproduce the synthetic hosted check with:
`uv run --frozen python -m scripts.group_discovery_hosted --token-file <local-token-file>`.
An interrupted run retains its private journal under
`.coordination-runs/fga-groups-<random>`; pass that basename with `--cleanup-run`
to delete only its recorded disposable resources.

## Sources

Accepted authority: architecture-design/docs/group-snapshot-and-pagination.md,
plugin-service-contract.md section 2, zero-state-publish-flow.md Phase 3, and
ADR 0030. The clock limitation and scoped prior exception are recorded in
ADR 0056 and this repository's Workers preflight-clock investigation.

Provider references checked 2026-09-18:
[Flickr writable groups API](https://www.flickr.com/services/api/flickr.groups.pools.getGroups.html)
and [Cloudflare timers](https://developers.cloudflare.com/workers/runtime-apis/performance/).
