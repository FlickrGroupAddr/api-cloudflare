# Status integration and deployment handoff

Date: 2026-09-13

Status: Local integration and bounded regression checks passed. The initial
persistent deployment is running in administration-only mode. Production
conformance and owner browser validation remain incomplete; real Flickr writes
stay disabled.

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

## Current deployment handoff

The owner completed the approved DNS move later on 2026-09-13. The destination
zone is active; both checked public resolvers return `norah.ns.cloudflare.com`
and `valentin.ns.cloudflare.com`. The read-only readiness report at
`2026-09-13T21:59:17Z` confirms account/delegation readiness. Registrar DNSSEC is
not configured. The prior target-zone-missing owner step is resolved; the later
registrar transfer remains independent.

The existing Wrangler profile still accesses Worker, D1 and Secrets Store
inventories. A separate zone-restricted read token was supplied and verified active. Both
DNS-record and certificate inspection now return HTTP 200; the destination DNS
inventory is empty and its Universal SSL certificate covers the apex and is
active. Existing credential input files are available. See the updated
[DNS/account procedure](../operations/fga-domain-account-move.md) for current
access evidence and the exact two read permissions, plus the initial disabled
deployment procedure. No repeat operator login or
Google owner setup is required to continue engineering work.

The apex is now connected to the persistent Worker. The current D1 schema was
verified and the initial quiescent 37-table archive round-tripped through a
separate local SQLite database. Administration alone is enabled; installation
reads, intake and dispatch remain disabled. The embedded browser reaches Google
sign-in but records a provider origin/client-ID error. Terry has been asked to
check the real flow in regular Chrome. No Google session or Flickr grant was
created by the agent. See the
[deployed checkpoint](../operations/initial-disabled-deployment.md) and its
sanitized evidence for exact scope, flags and pending browser findings.

Continue hosted lifecycle/status/bypass, process/deployment-stop, current-schema
restore/reconciliation and complete conformance/promotion work. The initial
archive check and DNS activation are not a production release pass. No
referrer-policy change or additional Google configuration change is approved or
inferred from the embedded-browser error.

## Owner browser follow-up

Terry reproduced the broken button in Chrome. A blocked Google stylesheet was
identified, fixed using fresh style nonces, tested and deployed. The repaired
control renders normally and reaches Google's sign-in page. See the
[repair and current owner step](2026-09-13-google-button-style-fix.md).
No additional Google settings or referrer-policy amendment was required for
this result. The owner authentication callback is still pending.
