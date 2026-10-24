# Offline PMB1 metadata binding preparation

This pure Python helper decodes at most 65,536 supplied nonsecret bytes into a
closed target/reference shape and prepares seven disabled metadata GET paths.
It has no file, credential, network, process or native-store access. It imports
no collector or transport. A trusted caller supplies the reviewed existing
`temporary_composition_metadata_projection.endpoint_for` function and exact
expected protected record path independently of the supplied bytes.

`decode_bindings(raw, expected_record_path=...)` checks exact six target keys,
identity grammar, distinct retained/temporary Workers and three distinct D1
identities. Each target reference must select `/targets/<key>` in the same named
record with consistent digest, maximum size, acquisition SID and observation
time. JSON duplicate keys, extra fields, nonfinite numbers, invalid dates,
booleans used as integer limits, oversized bytes and unsupported selectors fail
with finite diagnostic codes. The helper never dereferences these references.

`prepare_metadata_requests(raw, endpoint_for, expected_record_path=...)` adds
three `d1_database` requests and two `deployments`/`versions` pairs. The temporary
oracle is a third independent D1; the external main journal/evidence D1 is one
physical database. The source projector requires a `scriptName` in D1 target
objects although it does not appear in that URL; the helper supplies the retained
Worker for DB/journal and temporary Worker for ORACLE_DB. This shape establishes
no ownership or binding relationship.

The separate grant collector remains indivisible and unchanged: verify test
credential using its bearer, verify metadata reader using its bearer, then read
the verified test-token ID's details using the reader. Its existing independently
reviewed input/source/authority/claim/custody gates all remain required. The
helper emits descriptions only; it never creates an executable collector plan,
consent record, credential binding or run identity.

Output always says `dispatchEnabled=false`, `actualQualification=NO_GO` and
`authenticatesCurrentFacts=false`. Matching syntax, a self-reported digest/SID,
or a well-formed reference cannot establish authenticity, ACLs, current grants,
complete deployed code/configuration, Root judgment, census, remaining campaign
headroom, physical wire cost or actual 41-fact qualification. A caller must retain
this status. Independent genuine acquisition and semantic review remain separate.

Run `uv run --frozen --no-sync python -B
tests/test_prepare_pmb1_metadata_bindings.py` from the API repository root.
Tests use invented in-memory identities and do not read private original records.


## Separate local custody boundary

The pure binding helper does not allocate protected storage. A local execution
packet must separately pin its exact destination, current operator and native
custody implementation. A syntax-valid SID or path is not current custody proof.
Keep the original helpers' historical allowlists unchanged; an exact new path
needs its own reviewed source variant and applicable action scope.

For an execution-capable native wrapper, check current admission immediately
before each native metadata, conversion or operational dispatch, including calls
made inside inherited methods. Checking only the outer method leaves a gap if
admission expires or is revoked between native calls.

Only cleanup of genuinely acquired, tracked resources may continue after the
operational gate closes. Consume each cleanup attempt before native dispatch.
False, nonzero-error or raising results remain unknown and cannot authorize a
second attempt. Preserve that unknown outcome while allowing cleanup of other
owned resources that have not been attempted. A newly acquired resource may reuse
a numeric handle only with a distinct, genuinely observed acquisition generation.

The separate local source variant passed 28 mocked tests and eight independent
checks of these boundaries. No real native creation, private-record collection
or actual custody qualification follows from those tests. The public helper
continues to return disabled requests and NO_GO.
