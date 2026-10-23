# Prospective no-REAL SQL guard source handoff

Date: 2026-10-23. Source and local synthetic SQLite evidence only.

Accepted architecture [ADR0065](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/decisions/0065-accept-prospective-integer-accounting-and-no-real-profile.md)
and its [normative contract](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/prospective-integer-accounting-and-state-profile.md)
govern the separately selected `pmb1-private-application-no-real-v1` profile.
This source supplies SQL type guards for a bounded supplied schema. It does not
select the profile for an existing candidate or establish actual resource state.

## Source interface and exact binding

[`private_no_real_guards.py`](../../scripts/private_no_real_guards.py) accepts the
existing codec's `SCHEMA_SQL`, `TABLE_LIST_SQL` and `columns_sql` result shapes.
`build_guard_manifest(schema_rows, storage_rows, columns_by_table)` produces
fixed DDL strings and metadata; it executes no SQL. The supplied synthetic
schema must be complete, bounded and supported by the existing codec planner.

The manifest retains the exact original schema, expected installed schema,
table list, complete `table_xinfo` metadata, covered cells and both trigger
definitions for every table. Generated columns (`hidden=2/3`) and an accessible
hidden rowid alias are included. WITHOUT ROWID tables retain every key cell.
There is no bookkeeping, provider-name or column-name exemption. Supported
existing triggers, indexes and views remain part of the exact schema binding.

Retain `manifest_sha256(manifest)` as a separate reviewed candidate pin, together
with exact source/artifact pins. A digest computed from an incoming untrusted
manifest is not evidence of review. `validate_guard_manifest` requires that pin,
reconstructs the fixed definitions, compares all supplied installed metadata
exactly, and uses the caller's approved query interface for bounded zero-row
cell-access probes. Metadata or guard removal, replacement, addition, generated
column changes and manifest mutation refuse. Probe failures return a closed
category without leaking SQL diagnostics.

Access probes establish that the engine can prepare the cell references. They
do not evaluate every generated expression or certify existing contents. The
independent complete reader must still read every included actual value and
refuse inaccessible values, unknown types and every actual REAL. A complete
writer closure and common interval must surround actual discovery and use.

## Guard behavior and local proof

For each table, AFTER INSERT and AFTER UPDATE guards test
`typeof(NEW.<cell>)='real'` for every covered cell. This observes actual values
after affinity. INTEGER affinity may accept integral REAL input by persisting
INTEGER; a REAL still present in an untyped, BLOB-affinity or STRICT ANY cell
refuses, including numerically integral REAL. Generated INTEGER affinity follows
the same rule. No cast is used to conceal the actual storage type.

`RAISE(ABORT,'pmb1_no_real')` aborts the complete failing statement, including
its trigger and cascade changes. The transaction owner must propagate the
failure and roll back the entire batch; catching it inside a transaction and
continuing would retain earlier statements. Guard source does not replace that
batch contract. Required D1 transaction behavior remains a managed qualification
gate.

[`test_private_no_real_guards.py`](../../tests/test_private_no_real_guards.py)
uses only in-memory synthetic SQLite, including the accepted prospective
[`integer quota fixture`](../../tests/integer_quota_fixture.sql). It exercises:

- Actual INTEGER acceptance, signed64 extrema, NULL/TEXT/BLOB preservation and
  actual REAL refusal, including integral REAL in cells without INTEGER affinity.
- Stored and virtual generated cells, INSERT/UPDATE trigger writes with recursive
  triggers enabled and disabled, and a cascading key update producing a REAL
  generated child cell.
- Multirow INSERT/UPDATE/UPSERT, REPLACE and conflict modifiers, with complete
  statement rollback; caller-owned transaction rollback of earlier statements.
- Exact manifest, guard, schema and column drift refusal, quoted identifiers,
  unknown metadata and failed access probes.

Validation used pinned uv 0.12.5 with `run --frozen --no-sync`, Python 3.14.7
and local SQLite 3.53.1. All 16 focused tests passed. Scoped Ruff formatting,
lint and Pyright checks passed. Reproduce with `python -m unittest
tests.test_private_no_real_guards -v`, `ruff format --check --no-cache`,
`ruff check --no-cache` and `pyright` through that pinned uv environment, passing
the two Python files to the last three checks. No dependency was installed.

## Unsupported schemas and remaining boundaries

Independent review reproduced an unsafe ordering of otherwise identical
`sqlite_schema` definitions: a base AFTER trigger using `RAISE(IGNORE)` or
`RAISE(FAIL,...)` can
suppress a later guard and retain the REAL row. Trigger creation order is not
represented by the compared schema and must never supply enforcement authority.
The source now refuses the whole package if any base trigger SQL is unavailable,
empty or contains both the case-insensitive substring `raise` and either `ignore`
or `fail`. This deliberately includes harmless comments, literals and names that
contain those paired substrings. Plain `RAISE(ABORT,...)` and `RAISE(ROLLBACK,...)`
invariant/PMB-1 guards remain supported and have compatibility regressions. The
conservative availability limit avoids a SQL parser; comments or quoting around
the contiguous keyword tokens do not evade it. Generated guard definitions remain
exact compared state. Adversarial INSERT and UPDATE regressions reproduce the
order-dependent IGNORE and FAIL bypasses and prove that both source construction
and incoming-manifest validation refuse them, including externally pinned
old-style manifests.

Virtual/shadow tables, ordinary hidden columns, inaccessible hidden rowids,
unknown metadata and exhausted planner/manifest bounds refuse the complete
package. SQLite prohibits triggers on SQLite-owned `sqlite_*` tables, including
`sqlite_sequence`; this implementation therefore refuses any supplied schema
containing such a table. It never silently omits that table or certifies it by
name. Actual schemas containing these tables need a separately reviewed solution
before this source can support them. The exact ADR0064 D1 `main._cf_KV` contents
boundary is separate; this module invents no exclusion manifest or exception.

The fixed DDL can be evaluated for supported D1 and owning-object SQL through
their separately reviewed interfaces. No installer or provider adapter is
included. Each managed engine must qualify generated-cell access, affinity,
trigger/cascade/conflict behavior and complete batch rollback for its exact
candidate and schema. Local SQLite results supply no managed compatibility PASS.

These type guards do not freeze DDL, schema replacement, imports/restores,
guard removal, mutate-and-revert activity, KV or alarms. PMB-1 mutation-closure
guards, all-writer/old-deployment embargo, operator/provider/CI custody, independent
readers and complete SQL/KV/alarm coverage remain separate requirements. Existing
REAL facts require the accepted E/R/X decision boundary; this source performs no
actual census, retirement, installation, migration, deployment or live action.

Fresh independent High re-review passed the corrected source, all 16 repository
tests and 15 adversarial probes. Primary reproduced the 16-test suite and scoped
format/lint/type checks. These checks preserve the unsupported-schema and managed
qualification limits above.
