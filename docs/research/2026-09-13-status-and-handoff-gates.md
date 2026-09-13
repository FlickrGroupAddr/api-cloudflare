# Status integration and deployment handoff

Date: 2026-09-13

Status: Local integration and bounded regression checks passed. Production
conformance and deployment remain incomplete; real Flickr writes stay disabled.

## Completed continuation

Terry accepted ADR 0049. The canonical acceptance and closed Plugin Code HTTP
projection are pushed as architecture-design `fb91f42`; the implemented
credential lifecycle and one-time transfer UI are in api-cloudflare `3d35317`.
See the [rotation checkpoint](2026-09-13-plugin-code-rotation-integration.md).
No further rotation-route approval is pending.

The FGA API backend now exposes the accepted installation- and browser-session-
authenticated submission-status collection/item routes. A single SQLite read
statement obtains database observation time, scoped counts, gate projections
and bounded page rows. The page joins permanent blocks by exact server-owned
photo/group identity. Unknown outcomes, contradictory states/blocks and invalid
continuations fail the whole response. There is no Flickr/identity-provider
call, worker wake, intent mutation or bypass action on a status read.

The status limiter uses a per-installation or independent per-session bucket,
a 20-request burst with 120-per-ten-minute refill, and the 600-read deployment
sliding window. Its bookkeeping is separate from domain state. Status cleanup
failure cannot starve the durable scheduler. Exact paired keyset continuation
retains microseconds and owner/binding scope. The current implementation uses
nullable advisory group names rather than inventing names from IDs.

The read-only history panel uses protection-first copy, bounded pages and the
server's minimum polling interval. State, FIFO-ahead count, due time and holds
determine queue wording; a polling interval never becomes an ETA. A failed read
keeps prior data labeled stale, while session loss clears protected UI data.
There is no retry, reopen, force, clear-block or cancellation control. Browser
review used explicitly simulated data and confirmed moderation protection copy
and the available read-only controls.

A protocol or unknown-code deployment pause now also requires a different
artifact with retained conformance evidence before a fresh token check and the
usual gate compare-and-set. The runtime and release verifier share the reviewed
contract identity. No HTTP route can insert that evidence. Production receipt
publication still belongs to the unfinished full release pipeline; no production
receipt was inserted here. Existing initial/user gate verification remains
independent of this protocol-repair requirement.

## Validation and scope

The final local suite passed **102 Node tests** and **95 Python tests**. Native
TypeScript, Ruff, Pyright, generated API checks and the canonical architecture
checks passed. Native D1 tests cover concurrent rotation, both status credential
families, real dispatcher outcomes and no extra provider calls. The compiled
bounded crash matrix passed **84 checks**. All six existing crash mutations and
the deferred-preparation mutation were detected with passing controls and
unchanged working sources. Local runtime fixtures were disposed.

Migration `0012_protocol_repair_evidence.sql` is the current head; the exact
archive covers **36 tables**. The identifier guard now safely permits digits
in fingerprint column names, and nonempty receipt rows round-trip with guards.
These checks do not establish hosted D1 restore/reconciliation, independently
killed production processes, every required bypass, or the complete 56-case /
28-mutation release run. The existing `release:verify` command still refuses
missing production evidence. It remains an evidence verifier, not a substitute
for the unfinished full runner and CI promotion wiring. See the
[sanitized evidence](../evidence/status-and-rotation-integration-2026-09-13.json).

## Current owner handoff

The read-only `uv run --frozen python -m scripts.deployment_readiness` check
confirms that the destination Cloudflare account still has no
`flickrgroupaddr.com` zone. The source zone exists, but both DNS-record and
DNSSEC reads return HTTP 403 with the existing source profile. Authentication
works; repeating the login flow will not supply those missing permissions.
No DNS record, nameserver, production resource or Flickr grant was changed.

The next owner input is the old account's zone export and current DNSSEC/settings,
or completion of the already-approved account/zone move on #0016. Follow the
[DNS/account procedure](../operations/fga-domain-account-move.md). The registrar
transfer tracked by #0019 is separate and does not delay this DNS work.

After that input, finish the exact destination configuration and continue the
remaining hosted lifecycle/status/bypass, process/deployment-stop, current-schema
restore/reconciliation and complete conformance/promotion work. The production
UI still needs the real owner's Google/Flickr browser smoke check. Do not treat
these local results or the accepted ADR as permission to enable real group adds.
