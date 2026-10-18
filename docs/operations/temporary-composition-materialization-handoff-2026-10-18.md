# Temporary-composition materialization: October 18 handoff

Date: 2026-10-18. Ticket #0163. Status: **engineering handoff; actual private
materialization remains unavailable**. This dated update records Terry's two
delivery decisions and their implementation boundaries. It supplements the
[original collection proposal](temporary-composition-collection-decision-2026-10-18.md),
whose earlier manual-export recommendation is historical, and does not grant
account access or amend the preservation/restoration contracts.

## Decisions and resulting source

Terry chose Bot-operated bounded collection rather than manual metadata export.
The [metadata collector procedure](temporary-composition-metadata-collection-2026-10-18.md)
now specifies a finite, pinned, read-only source implementation. Its six endpoint
families exclude settings/content/secret-bearing responses and D1 record queries.
The 18-request maximum and private projection cannot supply a complete baseline.
Missing fields remain unavailable, never inferred empty.

Terry subsequently selected **private full snapshots processed only by bounded
code**, including authentication/session database cells, with no raw records in
chat, logs or Git. This authorizes developing and qualifying that direction.
It does not approve actual database reads, credential access, provisioning or
capture. The [preservation proof design](../design/temporary-composition-preservation-proof-2026-10-18.md)
records this choice. Its alternative in-Cloudflare witness remains unselected;
no proof-trust amendment was accepted.

The new [private reader and isolated qualifier](private-full-snapshot-reader-2026-10-18.md)
provide bounded typed extraction source and a separate fresh-synthetic-D1 route.
Production dispatch stays closed. REAL cells refuse the whole capture until
lossless extraction is implemented and qualified. Source tests do not establish
actual D1 representation, complete production coverage, custody or a writer barrier.

The separate [staged builder](temporary-composition-staged-binding-2026-10-18.md)
compiles immutable temporary/receiver bytes before a provider-assigned version
exists. Finalization binds supplied returned receipts without rebuilding those
bytes. It checks offline consistency, not actual provider provenance or authority.
The prior fully supplied builder and sealed artifacts remain unchanged.

## What still prevents materialization

1. **Qualified complete state and barrier.** Qualify the isolated reader first.
   Establish an all-writer admission/drain or fencing mechanism that remains
   effective across exact retained-version restoration and covers session/audit,
   maintenance, scheduler, stale invocation and direct-operator writers. Equal
   sweeps or paused Flickr gates cannot prove this. Do not change the retained
   original merely to manufacture a pass.
2. **Complete configuration provenance.** Obtain all eleven baseline sections,
   current original-version availability and effective edge relationships with
   separately reviewed capture authority/custody. The safe metadata subset cannot
   supply omitted settings or establish their emptiness. Database-cell approval
   does not authorize Worker binding/managed-secret value reads.
3. **Real isolated-resource and receiver receipts.** Supply independently verified
   existing run-owned receipts or implement/review a bounded provisioning,
   initialization, upload/readback and cleanup action packet. No such creation or
   upload was executed here; returned identities cannot be invented.
4. **Exact later actions.** Freeze actual source/targets, grant evidence, private
   custody and retention, credential delivery/revocation, numeric endpoints,
   finite UTC windows and cleanup/recovery ownership. Obtain concrete owner
   approval before each applicable account/capture/run scope. No old token or
   unrelated publisher-only cleanup exception supplies this authority.

The downstream exact-route preparation and native attempt remain gated by a
genuinely complete private packet. They are not unlocked by accepting these
source deliverables. Keep #0163 Ready for Work after this handoff with its explicit
engineering/qualification dependencies; the delivery/privacy question is resolved.
New #0171 owns the barrier design and #0172 owns the separately approved isolated
reader qualification; #0172 first depends on accepting #0170 source.

## Verification and provenance

The integrated source sweep passed **79 synthetic tests**: metadata projection/
collector, staged binding, private codec/reader and isolated qualifier. Ruff and
Pyright passed for all twelve new Python source/test files. The pinned native
TypeScript compiler passed `npm run check`. The first parent sweep lacked the
required pinned Node PATH for eight local bundling tests; the corrected invocation
passed all 79 without source changes. No dependency was upgraded.

Fresh independent reviews passed metadata collection, staged binding, proof
design, codec/reader and qualifier, with response-byte budget and cleanup wording
corrections incorporated before handoff. The 26-request qualifier records provider
not-found observations separately and keeps cleanup verification false. These are
source/fault-test outcomes, not hosted results.

Parent also verified the previously retained publisher candidate's 113-file
source closure, 26 unchanged migrations and immutable optimized bundle without
rebuilding it; the separate [publisher preparation guide](hosted-publisher-private-packet-preparation-2026-10-18.md)
owns those public pins and budgets. That check provides no temporary-composition
baseline or account observation.

No provider requests, current account observations, credential reads, production
record reads, cloud mutations, native actions, private composition assembly,
deployment, restoration or live qualification occurred in this batch. Private
working reports remain outside Git; durable sanitized procedures and decisions
are the linked repository documents.
