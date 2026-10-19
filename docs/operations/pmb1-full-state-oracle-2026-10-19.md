# Independent complete-state oracle: synthetic source proof

Date: 2026-10-19. Status: **unregistered synthetic source; independent High review
passed**. This supplies a local persisted-state oracle and finite fault checks.
It supplies no managed D1 or Durable Object source oracle and cannot pass PMB-1
qualification. No account, provider, native, private-data or cleanup action was
performed.

The controlling contract remains the
[accepted PMB-1 decision](prospective-maintenance-contract-decision-2026-10-18.md)
and [complete typed preservation contract](fixed-origin-preservation-2026-10-17.md#paused-gates-and-consistent-full-data).
The [typed REAL proof](typed-real-encoding-proof-2026-10-19.md) remains separately
scoped. No numeric domain, equality rule, accepted exception, existing reader or
Completed source is changed. Canonical architecture authority remains its
[documentation hierarchy](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/README.md).

## Independent expected state

`probes/pmb1-full-state-oracle/fixture.py` creates one exclusively new synthetic
SQLite file using fixed public DDL, parameterized fixture writes and explicit
binary64 bit-pattern inputs. It commits and closes the writer before opening a
fresh read-only connection. The generator records SHA-256 of the persisted file,
generator and oracle source, local SQLite version and expected fixture row count.
Reopen verifies source/file pins and checks the file pin again after the read.
These are local provenance/integrity facts, not a claim that a digest authenticates
an external source. The fixture refuses an existing file rather than adopting it.

`full_state_oracle.py:read_reference(connection)` obtains a complete independent
reference directly from this reopened SQLite connection. It imports no candidate
formatter, decoder, planner, canonicalizer, comparator or assembler. Every column
is selected together with its original `typeof()` in one statement. Binding
types must agree with that tag. REAL values become `struct.pack('>d', value)`
bytes; signed int64 values remain Python integers; text including embedded NUL
remains Unicode; BLOBs remain bytes. Expected cells never pass through candidate
decimal or hexadecimal text. Standard SQLite/Python bindings and IEEE binary64
`struct` layout are explicit local trust assumptions.

The reference retains exact `sqlite_schema` object SQL and NULL-SQL autoindexes,
declared column order including generated columns, every table, all rows and
paired hidden rowids. WITHOUT ROWID tables retain all explicit key columns.
There is no provider/bookkeeping exclusion list. A multiset comparison retains
duplicate multiplicity; pairing each row with its identity catches identity
reassignment. Physical pages/free space are outside the existing relational
equality contract.

The fixture separately checks its full known schema manifest, aggregate row
count and selected exact persisted int64/REAL/text/BLOB facts against public
generator constants. Its REAL corpus covers both signs at minimum subnormal,
maximum subnormal, minimum normal and neighbor, values immediately adjacent to
one, one, one-tenth and maximum finite. Both zero signs are also checked.

Local SQLite 3.53.1 preserved negative zero in the no-affinity fixture column
after close/reopen, while the REAL-affinity fixture returned positive zero for
both inserted signs. Both profiles are asserted independently from the reopened
read. Insertion parameters alone are never the expected persisted state. This
observation cannot establish either profile in a managed engine or authorize
normalizing a stored negative zero during capture.

## Observed-state check and finite faults

`check(reference, snapshot)` checks only the existing snapshot's `schema` and
`tables` relational representation. It does not validate or issue an envelope,
scope, gate, barrier, custody, campaign or hosted verdict. The existing caller
still owns those gates. In particular, a caller-controlled connection or synthetic
label does not authenticate its provenance; use only newly generated fixtures.

Only observed canonical REAL/hex-BLOB cells are translated into the independent
raw reference model. The expected path never calls the candidate codec. Schema
order, schema SQL, exact table census and column order must agree. Observed
canonical row ordering is checked independently using compact JSON; it does not
assemble expected rows. Missing/extra rows, unknown table fields, malformed tags,
out-of-range integers and noncanonical/nonfinite REALs refuse. No tolerance,
signed-zero collapse, type coercion or ignored schema field is introduced.

The direct reference read is one explicit read transaction, rolled back afterward.
It refuses an active caller transaction, nondefault bindings, unsupported encoding,
virtual/shadow tables, inaccessible hidden rowids and nonfinite values. Explicit
bounds are 128 tables, 2,048 schema objects, 256 columns per table, 10,000 rows,
4MiB conservatively accounted reference content and about ten million SQLite VM
instructions. Bound failures yield no partial successful reference. Conservative
reference accounting can refuse before the existing canonical 4MiB bound; this
is oracle availability, never weaker equality or silent omission.

Twelve tests cover:

- Persisted close/reopen equality, fixture/source provenance and unchanged pins
  for the existing reader, codec, typed REAL prototype and accepted PMB-1 record.
- One-bit and sign changes for every fixture REAL, including both zero signs;
  int64 boundary/JavaScript-rounding drift; type changes; text/NUL/BLOB drift.
- Missing/extra/changed/reordered schema, table omissions/additions, column order,
  missing/extra/duplicate replacement rows, hidden rowids, WITHOUT ROWID keys and
  canonical row order.
- Shared candidate `_cell` corruption: two identically corrupted candidate
  captures agree with each other but both fail against the independent reference.
- Malformed observed cells; changed fixture bytes before reopen; existing-file
  refusal; inaccessible rowid, 10,001-row and nonfinite reference refusals; active
  caller transaction preservation.

The corpus is finite. It neither proves all SQLite schemas nor supplies a
universal managed REAL extraction proof. No active registration, production
import, migration, provider adapter or execution CLI was added.

## Required actual managed-source oracle

Before a later managed campaign can claim fidelity, its reviewed profile must
supply a **trusted observation of the actual persisted source**, independent of
the candidate formatter/transport decoder/assembler. It must bind the exact
resource and artifact/schema, continuous qualified barrier generation/window,
complete store/table/column census, schema objects, row identities, actual cell
tags, exact int64 and binary64 bytes (including zero sign), text bytes/encoding
and BLOBs. Object KV and alarms additionally need their separately complete
trusted persisted-source representation. Local SQL state alone cannot cover
those stores.

An independently authenticated persisted SQLite image can supply such a reference
only if the actual managed profile establishes that its direct reopened reads
have the same persisted type/value semantics as the managed source. A reconstructed
SQL export, insertion fixture, decimal roundtrip, matching sweeps or second
invocation of the candidate decoder supplies no such assurance. A separate
supported direct source observation would likewise need independent completeness,
bit/sign fidelity, provenance and same-barrier binding; calling it independent
is insufficient.

No such managed image/observation path or equivalence evidence is supplied here.
The supported outcome remains unavailable/refused until that evidence exists.
This is an implementation/evidence gap under unchanged full typed equality,
not a new policy gate or permission to narrow the domain. Unknown, inaccessible,
unreadable or unfenced stores refuse. The existing reader's REAL refusal and
the actual qualification NO-GO remain in force.

## Reproduce local verification

Use the existing uv 0.12.5 executable from the project batch tooling record,
without changing tooling. From the API root run each with `uv run --frozen --no-sync`:

```text
python -W error::ResourceWarning -m unittest discover -s probes/pmb1-full-state-oracle -v
ruff check probes/pmb1-full-state-oracle
ruff format --check probes/pmb1-full-state-oracle
pyright --project probes/pmb1-full-state-oracle/pyrightconfig.json
```

Author verification: all 12 tests pass; Ruff and standard Pyright pass on Python
3.14.7 / SQLite 3.53.1. Tool pins remain unchanged. Independent High review passed; its outcome is recorded below.

## Independent review and integration

Fresh independent High review passed with no material findings. Twelve tests,
Ruff, formatting and standard Pyright pass; the reviewer independently exercised
1,286 state/schema/type/bit/identity/multiplicity faults and additional bounds.
The parent reproduced twelve installed tests with ResourceWarning treated as an
error. Expected local persisted-state independence is supported; no managed
trusted-source oracle or actual PMB-1 qualification is supplied.
