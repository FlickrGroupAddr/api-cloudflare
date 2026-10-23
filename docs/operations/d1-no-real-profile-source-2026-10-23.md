# Complete D1 no-REAL profile source

Date: 2026-10-23

Status: Bounded source implementation for #0238; independent source review and
managed qualification remain separate gates. This is no actual census or
production preservation result.

The accepted [ADR0065 normative contract](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/prospective-integer-accounting-and-state-profile.md)
authorizes the separately named `pmb1-private-application-no-real-v1` profile.
The original strict reader and `adr0064-private-d1-application-state-v1` retain
their existing semantics. The exact-REAL reader work (#0192) remains separate.

## Closed selection and complete evidence

`scripts/private_d1_snapshot_profile.py` accepts the new profile only with
`contractRevision: adr0065-private-d1-application-no-real-v1`. Its manifest has
all the existing ADR0064 fields and exactly two additional fields:

- `guardManifest`: the complete #0237 `private_no_real_guards` manifest.
- `guardManifestSha256`: the exact SHA2-256 pin retained in the reviewed candidate.

The enclosing plan and consent bind the same profile ID and entire manifest.
Source pins include the guard implementation. A manifest pin supplied by its
author does not establish independent review or actual installation.

The reader binds the full discovered `sqlite_schema` and `pragma_table_list`
census, all included `pragma_table_xinfo` metadata and exact generated query
sequence. It checks the guard definition against its deterministic source,
compares actual included schema/columns to that manifest, then issues the
manifest's bounded `LIMIT 0` cell-access probes before reading rows. Probe SQL
uses canonical table-name order and is part of the separately approved query
plan. A probe proves accessible expressions, not guard effectiveness or closure.

Every included cell independently passes `typeof` plus engine-side transport:
INTEGER becomes canonical signed64 decimal TEXT before JSON, TEXT becomes strict
UTF-8 bytes encoded as hex, BLOB remains exact hex, and NULL remains distinct.
The Python decoder uses arbitrary-precision integers. No delivered JSON number
can establish integer-cell or hidden-rowid authority. Every actual REAL refuses,
including integral REAL or a value outside the quota fields, even when the exact
guards were bypassed before capture. Supplied decoded snapshots are checked for
the same restricted typed domain before preservation comparison.

Complete row counts, exact-sized pages and empty terminal sentinels remain
mandatory. Duplicate cell rows retain their distinct hidden rowids; WITHOUT
ROWID tables retain complete non-NULL typed primary-key identities. Schema,
guards, generated values, migration rows and all other included state remain
exact compared facts. Unsupported identities, hidden/virtual state, malformed
tags, decimal/UTF-8 corruption and exhausted finite limits refuse.

## Exact visibility boundary and refusal

Only the already manifest-qualified exact D1 `main._cf_KV` table contents are
excluded. Full observable metadata remains bound. Only its exact table and
table-list rows are projected out of #0237's guard-validation input; no other
table is skipped. Application dependency on excluded contents still refuses.
Those contents remain **unobserved, unfrozen and unverified**, and may affect
provider behavior. This D1 exclusion does not apply to object-local KV.

The existing #0237 guard builder refuses SQLite-owned tables on which it cannot
install triggers, including discovered `sqlite_sequence` or statistics tables.
This adapter preserves that complete refusal. It does not omit bookkeeping,
manufacture its emptiness or grant a name-prefix exception. A candidate with
such state needs a separately reviewed supported prevention solution before
this profile can qualify. The old ADR0064 profile still captures addressable
bookkeeping under its original requirements.

## Validation and operational boundary

Focused synthetic tests compare the captured included schema, typed cells,
duplicates and rowids to the unchanged local `capture_sqlite` source oracle.
Fixtures include signed64 extremes, safe-Number neighbors, generated values,
composite keys and migration history. Adversarial tests cover REAL introduced
with guards bypassed and restored, guard/schema/column/probe drift, corrupt wire
values, incomplete pages, duplicate identities and finite bounds. Preservation
tests reject equal-count cell, migration and hidden-rowid changes. Reader tests
retain consent, profile-identity and no-replay gates.

These local source tests are not an independent managed-adapter source oracle.
They prove no actual D1 inventory, source-bit observation, custody, common closed
interval, prevention on the managed engine, restoration/reopen or #0182 pass.
The reader retains its private sink, bounded transport, credential/grant,
admission, writer closure and no-replay seams. Default production networking
remains unavailable. No actual read, credential, provider operation, guard
installation, migration, deployment, native action or live qualification was
performed for this source handoff.

## Independent source review

Fresh independent High review passed the corrected source and 174 affected tests,
scoped formatting/lint/type checks and eight separate synthetic oracle/adversarial
tests. Primary reproduced the affected suite and scoped checks. The correction
aligns external WITHOUT ROWID snapshot validation with capture invariants: duplicate
or NULL primary keys and malformed table shapes refuse before aggregate counts.
These results establish local source behavior only; the operational and managed
qualification gates above remain unchanged.
