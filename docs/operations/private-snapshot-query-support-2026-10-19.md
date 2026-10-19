# Private snapshot SQL surface and encoding witness

Date: 2026-10-19. Source audit only; no new D1 query, current-grant observation,
actual snapshot or qualification is established. Full-state preservation and
provider-owned-table inclusion remain strict. No live successor is proposed
while the reserved-table contract conflict remains unresolved.

## Encoding correction

The collector and exact independent reader now use:

```sql
SELECT hex(CAST('A' AS BLOB)) AS encoding_probe
```

The codec accepts exactly `[{"encoding_probe":"41"}]`. Missing/extra rows,
additional keys, wrong types, unknown results and either UTF-16 byte order
refuse. The TEXT decoder still strictly decodes UTF-8 and preserves embedded
NUL, integer, BLOB, NULL, row identity and full schema rules. REAL remains
unsupported. Nothing is coerced, omitted or treated as an empty successful read.

This is behavioral SQLite byte-representation evidence. It is not a returned
`PRAGMA encoding` value, a disclosed D1 build or an assumed UTF-8 default. Exact
SQL/source provenance stays in the approved ordered query manifest and source
closure. The response guard validates the actual returned witness.

[SQLite documents](https://sqlite.org/lang_expr.html#castexpr) CAST-to-BLOB as
TEXT in the database connection's encoding reinterpreted as BLOB; its
[hex contract](https://sqlite.org/lang_corefunc.html#hex) exposes those BLOB bytes.
Consequently UTF-8 yields `41`, UTF-16le `4100`, and UTF-16be `0041` for this
literal. The existing database encoding is immutable under
[SQLite's encoding rules](https://sqlite.org/pragma.html#pragma_encoding).
These semantics and local controls justify the source route; they do not
substitute for a hosted result.

## Complete fixed-query audit

Both paths call `private_d1_snapshot_codec.collect_snapshot`. The collector
records its exact ordered SQL; `private_d1_snapshot_reader` admits that bound
manifest, checks its three-query prefix and consumes every entry exactly once.
There is no additional independent-reader SQL family hidden behind that path.

| Family | Operations/functions | Primary support and remaining condition |
| --- | --- | --- |
| Schema census | `SELECT type,name,tbl_name,sql FROM main.sqlite_schema ORDER BY ... LIMIT ...` | D1 documents schema-table reads; SQLite defines `sqlite_schema`/`sqlite_master` aliases. Source and actual earlier census acknowledgement agree on this limited metadata surface. |
| Storage census | `SELECT ... FROM pragma_table_list WHERE schema='main' ORDER BY ... LIMIT ...` | D1 documents `table_list`, including system-table names. Workerd explicitly allows it. Listing a name grants no permission to read its data. |
| Encoding witness | `hex(CAST('A' AS BLOB))` | `hex` is in D1's linked workerd function list; documented SQLite CAST semantics supply the exact representation witness. Only `41` passes. |
| Column census | `pragma_table_xinfo(quoted_table_name)`, ordered and bounded | Workerd explicitly allows `table_xinfo` only when its regulator permits the named table. Ordinary supported tables qualify this condition; reserved provider tables do not. |
| Complete count | `CAST(count(*) AS TEXT)` from each quoted `main` table | `count` is allowlisted; CAST is SQLite SQL syntax. The named table must be readable. The count still must be canonical, bounded and followed by complete pages. |
| Typed pages and empty sentinel | rowid/key ordering; `typeof`, integer CAST-to-TEXT, TEXT CAST-to-BLOB/`hex`, BLOB `hex`, CASE, BINARY ordering, LIMIT/OFFSET | `typeof` and `hex` are allowlisted. Standard SQLite expressions preserve the existing exact typed codec. Every named table, including provider-owned tables, must remain readable; unsupported cells and inaccessible identities refuse. |

The [D1 SQL documentation](https://developers.cloudflare.com/d1/sql-api/sql-statements/)
documents selected PRAGMAs, schema reads and links this
[immutable workerd function/policy source](https://github.com/cloudflare/workerd/blob/4c42a4a9d3390c88e9bd977091c9d3395a6cd665/src/workerd/util/sqlite.c%2B%2B#L248).
Its allowlist contains `hex`, `typeof` and aggregate `count`; its authorizer
special-cases `table_list` and conditionally `table_xinfo`, and denies unsupported
PRAGMAs such as encoding. This source reference does not identify the deployed
D1 engine build. General expression and schema semantics are documented by
[SQLite](https://sqlite.org/lang_expr.html) and its
[schema-table reference](https://sqlite.org/schematab.html).

No query string itself establishes provider access to every enumerated table.
The local policy regression covers the entire collector/isolated-reader recipe,
allowing only these three functions and these two PRAGMAs. It is deliberately
a bounded synthetic control, not a complete workerd/D1 emulator or hosted pass.
The VALUES seed remains one existing statement/POST; this correction introduces
no extra request and preserves every finite query/row/byte/time ceiling.

## Concrete reserved-table blocker before another attempt

Cloudflare's [D1 import/export documentation](https://developers.cloudflare.com/d1/best-practices/import-export-data/)
says `_cf_KV` is reserved internal storage and cannot be queried. Workerd's
[immutable SQL regulator](https://github.com/cloudflare/workerd/blob/4c42a4a9d3390c88e9bd977091c9d3395a6cd665/src/workerd/api/sql.c%2B%2B#L88)
rejects `_cf_` names; its metadata authorization also consults the name regulator.
The independent actual reviewer confirmed that the stopped v2 census exposes
exactly one reserved `_cf_` table, `_cf_KV`. Its contents were not queried before
the encoding refusal. This audit reads no actual provider records itself.

The current codec explicitly includes every enumerated table, including
provider-owned ones. Even if a column-metadata request happens to be accepted,
the documented data-read restriction prevents asserting complete typed contents
through the current supported SQL surface. Filtering that table, substituting
an empty table or relaxing schema/census equality would change preservation
scope. This correction does none of those things. A focused denial regression
proves refusal instead of silent omission.

Therefore the encoding correction is useful source work, but does not make a
new live qualification foreseeably complete. No additional attempt should be
proposed while this concrete conflict remains unresolved. The separate owner
contract decision (#0219) must identify an acceptable supported full-state route
or explicitly decide a changed scope with its consequences. ADR 0058's narrow
engine-version exception does not waive encoding or provider-table preservation.

## Validation and retained boundaries

Focused synthetic coverage verifies both UTF-16 orders refuse, malformed/unknown
witness rows refuse, embedded-NUL and multibyte TEXT stay exact, and the full
collector plus same-process isolated reader use only the audited function and
PRAGMA set. An authorization refusal for a provider-owned table aborts the
complete snapshot. Existing equality-before-cleanup, no replay, unknown retention,
private custody and false production/cleanup flags remain unchanged.

Historical attempts and their residual D1s are not replayed, discovered, deleted
or reclassified. This source change performs no account, credential, provider,
DNS, native or private-data operation and supplies no new action authority.
