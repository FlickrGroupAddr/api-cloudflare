# Atomic D1 admission and Durable Object wake recovery

Date: 2026-09-11. Implementation cards #0004 and #0005, under parent #0002.
Status: Work in progress; no new hosted conformance result yet.

Terry authorized the next two highest-priority executable tickets through Needs
Terry or Ready for review without further intervention. The board's first entry,
#0002, is the umbrella plan; its next concrete P1 children are #0004 and #0005.
The accepted architecture baseline is `286b972` in architecture-design. ADRs
0015, 0020, 0033 and 0050–0054 plus the binding, admission and persistence
contracts control this work. The prior #0007 scoped D1 proof has passed.

## Scope

Build and test a production-shaped D1 transaction adapter for a complete
one-photo group selection (1–60 unique group IDs). Derive photo/owner/source
from the existing verified binding, enforce its installation/owner/link/revision
and 15-second existing-photo proof rules, preserve global exact-pair identity,
allocate committed per-partition FIFO ordinals, and preserve permanent blocks.
One transaction must contain all inserts, ordinal/due changes and events.
After commit the adapter may send only one hint for the canonical-lowest newly
eligible partition; fully idempotent retries and appended non-head work send none.
Hints are disposable, and hint failure cannot undo committed admission.

D1 remains the sole authority for partitions, ordinals, exact due times,
lease IDs/generations, gates and retained events. The DO candidate coordinates
wakeups and alarms only. Every hint, alarm and minutely sweep returns through
the same D1 conditional claim. No transaction is assumed to span D1 and DO
storage. Lost alarm/hint writes recover through indexed D1 due sweeps. Test
concurrency, expiry, renewal/release fencing, process eviction and stale-owner
rejection without any Flickr operation. Lease generations and ordinals use
signed-64-bit SQL values and text projections across JavaScript boundaries.

This is the bounded adapter/provider proof requested by the two cards, not a
claim that the full courteous-admission or fail-polite release suite has passed.
Actual Flickr dispatch/markers and monotonic preflight belong to #0006/#0013;
production auth/UI integration, official-client no-slicing and production timing
remain separate. Synthetic fixture controls must stay outside the public API
entry point. No new service is justified merely because an API is inconvenient.

## Planned verification

- Native TypeScript compiler before Worker bundling; real local D1/DO tests.
- Whole-request syntax/binding rejection, mixed/identical retries, 60-group
  boundary, concurrent overlaps, rollback after each stage, original ordinals,
  exact integer boundaries, append-only events and zero-or-one committed hint.
- Due time and paused gates, duplicate/stale hints, one lease winner, late
  renew/release/mutation rejection after takeover, alarm and minutely recovery,
  real object eviction with unchanged D1 authority, no external Flickr traffic.
- Fresh random disposable namespaces, authenticated/expiring fixture controls,
  source fingerprints, safe result records, and verified DO/Worker/D1 cleanup.

## Provider references

[Cloudflare D1 batch API](https://developers.cloudflare.com/d1/worker-api/d1-database/#batch)
documents transactional batches with whole-sequence rollback on error.
[DO alarms](https://developers.cloudflare.com/durable-objects/api/alarms/),
[DO state](https://developers.cloudflare.com/durable-objects/api/state/) and
[Worker Cron Triggers](https://developers.cloudflare.com/workers/configuration/cron-triggers/)
provide the candidate wake mechanisms. Their documented behavior must be tested
against the hosted runtime; emulator results alone are not that evidence.
