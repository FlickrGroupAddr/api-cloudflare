# Explicit supported-state object reader successor

Status: implemented SOURCE increment under accepted ADR0066, pending fresh
independent review. Complete native source and actual qualification remain NO-GO.
This records the later successor; prior source-subset reviews are the preceding
baseline, not evidence that this increment was already implemented.

`object-kv-interface.ts` exports `captureSupportedBoundary` and explicitly selects
`pmb1-private-object-kv-interface-v1` inside the existing prospective no-REAL
profile. Its distinct manifest revision is
`adr0066-object-kv-interface-source-v1`. There is no implicit/default selection.

Each independently supplied object manifest binds the exact namespace/object,
selector/revision/profile, original application guard manifest, full observable
metadata and source pins. The request separately pins its canonical manifest
bytes. Required source inputs include the unchanged original reader, this
successor and accepted ADR0066. `boundary-source-manifest.json` identifies the
exact source increment; runtime source/manifest custody remains a separate gate.

The successor collects and exactly compares the complete observable schema,
table list and every discovered table's column metadata against the independently
retained manifest, before and after reading application facts. The exact
automatic `__cf_kv` schema/census stays in both observations in the new output.
Metadata acquisition and retained metadata consume the existing aggregate byte,
query/time, schema/table/column limits. No limit is enlarged.

Only an internal, explicitly labeled application SQL projection is passed to the
unchanged original complete reader. That reuses its all-cell guard reconstruction,
schema/identity checks, signed64 decimal transport, actual REAL refusal, complete
supported typed KV/binary codec, alarm generation/order, source/population,
fence/closure and common interval checks. The old reader's returned object is
never presented as a complete original capture. The successor returns its own
boundary/revision, full observable metadata, application census and facts, exact
manifest pin, and an explicit excluded-representation declaration.

Only inaccessible raw SQL contents and rowids of the exact automatic `__cf_kv`
table are excluded. No raw SQL count, cell or rowid query is issued for that table;
no provider representation is guessed from typed KV. Its representation remains
**unobserved, unfrozen and unverified** and may change undetected. A hidden-only
change can therefore leave this boundary's result equal. Supported KV changes
remain included exactly. There is no prefix, whole-census or general metadata
exemption, and the distinct D1 `_cf_KV` boundary supplies no permission here.

The manifest must explicitly classify the exact table as provider automatic and
declare no application dependence on its excluded representation. This is an
independently retained input, not a classification inferred from an observed
name. The source refuses missing/mixed pins, unknown automatic metadata, extra
objects related to the hidden table, inaccessible application data and any
application SQL schema dependency on `__cf_kv`. Automatic metadata shapes outside
this source's support refuse rather than silently widening the boundary. Actual
provider provenance and application nondependence still need independent proof.

`expected-observable.json` is a separately retained **synthetic** metadata oracle,
generated from explicit fixture DDL before constructing the observed adapter. It
is not actual provider metadata. Tests separately retain literal signed64 rowids,
cells and typed KV/binary expectations. The observed adapter denies raw hidden
SQL access and never creates the expected inventory from observations. Tests
cover full metadata drift/races, selector/source/manifest mismatch, unknown
metadata, application inaccessibility/dependence, unsupported values, unchanged
alarm/closure gates and aggregate full-census bounds. The old reader/default and
all historical frozen manifests remain unchanged and separately refuse this
native-inaccessible raw-table model.

There is no new SupportedSource population factory, remote RPC, native capture,
HTTP implementation, grant or action budget. The actual HTTP entry stays
disabled. Local SQL preflight cannot interrupt synchronous engine work and does
not prove a complete heap/deadline bound. Expected population/source provenance, creator/all-writer closure,
common custody, callback disposition, native implementation/transport bounds,
retained artifact and actual qualification remain mandatory unresolved gates.
REST pagination is not a frozen snapshot; a null alarm is not callback completion.

`readLocalSupportedBoundary` supplies the explicit native-helper composition.
It validates the exact selected manifest/hash and source bytes before admitting
only the one generated `__cf_kv` column-metadata pragma for the declared column
bound. Raw SQL cells/counts/rowids remain unavailable; the original `readLocal`
default still refuses hidden-table metadata/content requests. The composed model
test exercises full before/after observable metadata, native SQL/fence, typed KV
and alarm reads in one transaction with zero raw hidden reads.

Native KV retains a 2 MiB worst-case pre-acquisition reservation, then replaces
it with a bounded conservative measured typed-fact charge after acquisition.
Unused reserve is released. Small KV plus terminal pages fit under the existing
4 MiB aggregate cap; large retained facts refuse the next worst-case acquisition
before dispatch. Traversal has explicit depth/node/time/byte limits, rejects
unsupported types without invoking accessors, and poisons failed sessions. It
does not construct a new preservation codec or infer an engine/JS heap bound;
the original reader still owns exact typed encoding. Source/manifest verification
bytes also count toward the native boundary session's retained allowance.

Authority: [accepted ADR0066](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/decisions/0066-scope-prospective-object-preservation-to-supported-state.md)
and its prospective state-profile contract. Cloudflare's
[SQLite storage API](https://developers.cloudflare.com/durable-objects/api/sqlite-storage-api/)
supplies the specific hidden-table capability finding. Owner acceptance changes
only the selected preservation boundary; it supplies none of the actual facts.
