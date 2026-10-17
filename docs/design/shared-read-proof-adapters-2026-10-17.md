# Disabled shared READ and proof protocol adapters

Date: 2026-10-17. Scope: implementation ticket #0057.
Status: offline source checks and independent High review passed after header
parser correction. Production qualification and all transport capabilities remain false.

The shared policy is implemented in
[`SharedReadTransport.lua`](../../clients/lightroom/FGA-LrC15.lrplugin/SharedReadTransport.lua).
[`SharedProofProtocol.lua`](../../clients/lightroom/FGA-LrC15.lrplugin/SharedProofProtocol.lua)
composes the existing installation and existing-photo clients. These modules are
unregistered and supply no native HTTP implementation. They neither enable the
existing workflow factory nor replace the separately owned thumbnail adapter.

## Authority and qualification boundary

The architecture repository's `docs/README.md` defines authority. The accepted
`docs/existing-public-photo-intake.md`, `docs/group-snapshot-and-pagination.md`,
`docs/installation-credential-lifecycle.md`, and ADRs 0032/0034 own the existing
READ/proof semantics. The implementation reuses `ConnectionCore`,
`ExistingPhotoClient`, `GroupDiscoveryClient`, and `SubmissionStatusClient`.
It introduces no alternate wire schema or ownership/visibility authority.

The [feasibility verdict](../operations/fixed-origin-feasibility-verdict-2026-10-16.md)
remains controlling evidence: the SDK15.3 GET call returns a complete string,
provides only a per-phase timeout, and exposes no supported receive cap or GET
abort handle. The current candidate has no qualified supported allocation,
provider-generated response-bound or effective credential-redirect mechanism.
Native cancellation/publication/cleanup and backend abort/disconnect evidence
remain separate. A source allowlist or explicit Location rejection cannot
prove that the host networking stack did not already follow a redirect.

`SharedReadTransport.new()` therefore returns `nil, "qualification_required"`
unconditionally, before reading a credential. `PRODUCTION_QUALIFIED` and
`readTransport`, `thumbnailTransport`, and `proofTransport` remain false.
The exact engineering blocker to production construction is the unresolved
supported method in that verdict, not a failed or absent synthetic assertion.
This output does not close that blocker or authorize live qualification.

## Implemented policy

- The fixed origin is `https://flickrgroupaddr.com`. Only current installation,
  existing-photo discovery, writable-group discovery, binding memberships and
  photo-filtered intent history READ paths are allowed. Canonical encoded opaque
  identifiers and numeric bounds are enforced; duplicate/unknown/incomplete
  parameters, alternate origins, thumbnail and arbitrary API routes are refused.
- A pinned credential is read only through the injected secure-store boundary.
  Candidate rotation, credential replacement, store failure, cancellation or
  loss of the owning context latches the adapter closed. The caller owns the
  exact catalog/session fence through `current()`; false context/cancellation
  stops before secure-store access. Credentials are never switched mid-session.
- GET requests use only the retained Authorization field and a 30-second SDK
  timeout. Returned installation bodies are limited to 64 KiB and other JSON
  bodies to 2 MiB. These checks occur **after allocation**. Observed elapsed
  values must be finite, nonnegative and below 30 seconds after return; this is
  a publication fence using the injected clock, not a monotonic or hard deadline.
- Explicit 3xx, Location, unsupported success status, native error metadata,
  malformed/sparse/duplicate headers, missing JSON/no-store, inconsistent length
  and invalid JSON are rejected. Media-type tokens retain internal whitespace;
  only legal outer/separator OWS is accepted. Cache-Control is parsed by
  directive/token and quoted-string boundaries; only a bare no-store directive
  satisfies the policy. HTTP401 requires the exact invalid-token Bearer
  challenge matching the error. Only interpreted headers are copied onward;
  native error objects and other headers are discarded.
- Strict bounded grammar precedes bundled dkjson. Duplicate decoded keys,
  comments, trailing/missing commas, trailing content, invalid UTF-8/unpaired
  surrogates, nonfinite numbers and excessive nesting fail. Explicit null and
  object/array metatables survive for the existing clients. Decode is synchronous;
  only decoding is protected with built-in Lua5.1 `pcall`.
- Yielding GET and injected proof POST use the owner's injected yield-safe
  protector. Exceptions become empty unavailable responses; no logging or UI or
  outbox path is introduced. Cancellation/context/credential gates run before
  and after protected calls, and late responses cannot publish.

## Callable integration contract

`SharedReadTransport.offline(d)` is deliberately named for synthetic execution.
It accepts `get(url, headers, timeout)`, yield-safe `call(fn)`, synchronous secure
`retrieve(key)`, `current()` (exactly true only in the retained owning catalog
and session), `cancelled()` (exactly false while active), finite `now()`, and
`expectedInstallationId`. It returns `httpGet`, guarded `retrieve`, `cancelled`,
`cancel`, guarded `protect(fn)`, strict `decode`, `encode`, and `jsonNull`.
Fixtures explicitly pass built-in `pcall` only for nonyielding mocks, and test a
coroutine-based protector separately. This is not a native task qualification.

`SharedProofProtocol.new(read, optionalPost)` returns the existing-client
`request(method, path, body)` interface plus `prove(photoId, linkedRevision)`,
strict JSON seams and false capabilities. With no separate POST object, proof
POST fails unavailable and dispatches no POST. An explicitly injected object has
`httpPost(url, bytes, headers, method, timeout)` and
`capabilities.proofTransport == true`; #0061 owns that implementation and its
separate native/effective-edge qualification. The injection is exercised only
with synthetic data here. This module never derives POST authority from READ
capabilities, never supplies `LrHttp.post`, and never retries a POST.

The existing proof encoder preserves high safe-integer revisions, the existing
binding validator enforces photo/link correlation, and existing installation
verification receives `expectedInstallationId`. The response policy permits
201 only at the proof seam. `PROOF_POST_AVAILABLE` stays false.

Required parent integration is narrow:

1. Use `SharedReadTransport.decode`, `encode`, and `jsonNull` together in the
   existing factory; its current local decoder alone allows dkjson extensions.
2. Keep the workflow factory's capability gate before all credential access.
   These disabled modules cannot supply true capabilities to that factory.
3. In a future separately qualified construction, supply `LrTasks.pcall`, the
   retained context/catalog/session checks, cooperative cancellation and an
   explicitly characterized clock. Preserve installation and linked identity
   checks in the existing owner. Do not wire `offline()` to a native entrypoint.
4. Supply separately qualified #0061 POST only after that ticket's own gates.
   Keep the thumbnail implementation and all registrations separately owned.

No existing factory, client, controller, registration or manifest was changed
by this scoped implementation. Any later loadable build must receive its own
parent-owned manifest version increment before native reload/testing.

## Review correction

The first independent review found that deleting all header whitespace could
accept malformed split tokens (`no- store`, `app lication/json`) and that the
cache substring check could mistake a quoted value for a no-store directive.
The parser now trims only legal OWS around media-type separators and scans
Cache-Control tokens, quoted strings/escapes and comma boundaries explicitly.
Dedicated regressions refuse split tokens, malformed parameters and
`private="foo,no-store,bar"`; they accept legal OWS/case, UTF-8 charset forms,
and quoted extension values alongside a real no-store directive.

After this correction the 54-test regression group, static checks and SDK15.3
Lua parse passed. The reviewer's separate offline reproduction script also
passed all 39 checks when rerun by the author; this rerun is supporting evidence,
not independent acceptance. Fresh independent re-review remains required.
## Verification and provenance

The dedicated fixture and `tests/test_shared_read_proof.py` execute actual
Lua5.1 modules with synthetic in-memory credentials and HTTP boundaries.
Seventeen focused tests cover the release constructor, actual discovery,
membership, group and two-pass history clients, origin/path and credential
isolation, strict JSON/null/array/object behavior, status/header/size/error
policy, cancellation/rotation/context/clock fences, yielding protection, absent
POST and separately injected proof correlation/error handling.

The focused suite plus existing factory, status-client and existing-photo
workflow regressions passed **54 tests**. Focused Ruff, Ruff format check and
Pyright passed. The existing Adobe SDK15.3 Windows `luac.exe -p` passed both new
modules and the Lua fixture. No dependency, toolchain, SDK or host upgrade was
performed. No native, cloud, Flickr, real-credential or live operation occurred.

Commands run from the implementation repository:

```console
uv tool run --from uv==0.12.5 uv run --frozen python -m unittest tests.test_shared_read_proof tests.test_group_workflow_adapter_factory tests.test_submission_status_client tests.test_existing_photo_group_workflow
uv tool run --from uv==0.12.5 uv run --frozen ruff check tests/test_shared_read_proof.py
uv tool run --from uv==0.12.5 uv run --frozen ruff format --check tests/test_shared_read_proof.py
uv tool run --from uv==0.12.5 uv run --frozen pyright tests/test_shared_read_proof.py
```

Source base: `8fabd362b78f97ed2c9d80d48fdb7ad0822a48d4`, with concurrent
unrelated work preserved. Policy identifier: `shared-read-v1-2026-10-17`.
Runtime target remains Lightroom Classic15.6 / Adobe SDK15.3; offline execution
uses CPython3.14.7, uv0.12.5 and locked Lupa2.8 Lua5.1. No deployed runtime or
actual hosted configuration was sampled here. `wrangler.example.jsonc` below
is source provenance only, never evidence of deployed configuration.

The licensed local primary reference was SDK15.3
`API Reference/modules/LrHttp.html`: documented GET signature, asynchronous task
requirement, complete response string/status/header shape and per-phase timeout.
Its SHA2-256 is
`1a2a5b44baf22c5f77ba42c90ea2a73988237fd718ef55baac00463bab22ee1b`.
The installed SDK15.3 Windows compiler SHA2-256 is
`da77f3494c5e0797ffc2feb744205aa94fdbe5b15d5c766ff8a28bdb29d5d7ea`.
Licensed reference content is not redistributed.

Exact SHA2-256 source provenance at verification follows. Downstream #0023 can
qualify this READ policy independently of #0024 registration, against these
exact bytes and its own selected runtime/configuration. Independent review is
a separate required parent-owned gate; this author does not self-certify it.

| Source | SHA2-256 |
| --- | --- |
| `clients/lightroom/FGA-LrC15.lrplugin/SharedReadTransport.lua` | `00432c48aa3325acb2314a85e0ac17d44c10fd09839617162e84d4757c77c118` |
| `clients/lightroom/FGA-LrC15.lrplugin/SharedProofProtocol.lua` | `93076f00fd06eb906f8827149a94ea97b1bf56f543fa0e32e5bb128fe10ab602` |
| `clients/lightroom/FGA-LrC15.lrplugin/ConnectionCore.lua` | `a4934ea22bf6c24be0a6df8e47f095c75d1a251bdb65ef6c8f7a96ba72bdfd0e` |
| `clients/lightroom/FGA-LrC15.lrplugin/ExistingPhotoClient.lua` | `2fcd68afae4f933ce83e25aa4cf8c734971f25a5ae12855c23c6f3f68bcfdc54` |
| `clients/lightroom/FGA-LrC15.lrplugin/GroupDiscoveryClient.lua` | `5f20cfcecde11d39e19a68478fc10099830439f4fc8831906a2db6c5595595b7` |
| `clients/lightroom/FGA-LrC15.lrplugin/SubmissionStatusClient.lua` | `ba79c2446e0bd6ade03d70993fb2ad961529b57809ab4e7fa9b6af1330f568f3` |
| `clients/lightroom/FGA-LrC15.lrplugin/dkjson.lua` | `197cb50834c642f84b4cf99fe724932c50e6d9c92faec7ad89aa25e91df4d481` |
| `tests/shared_read_proof_fixture.lua` | `2f63f2c9fc5d54042c286318f04c6dd15d6c3743232f96ff9f9e869ed4cd5be9` |
| `tests/test_shared_read_proof.py` | `e658be1d9e671280446d117ea0c274b0a9a3e09874dd1730d43bf1cc0bfc1520` |
| `pyproject.toml` | `36c79d4a033535fe270b347739609e420a41a2b3f99f93add88765876436b90d` |
| `uv.lock` | `aa94ded3cda190efe788d8b1028bcf57fab22495c19113b1ad8ce1a1d0adafba` |
| `wrangler.example.jsonc` | `98379c9b23a441ea083d2433ef0992616b98465266689011edbf3adbce7fe4df` |


## Independent review and integration

The independent review reproduced malformed media tokens and false `no-store`
matches, including quoted directive values. The corrected parser preserves token
boundaries, trims only legal optional whitespace and recognizes actual bare
`no-store` directives. The final independent run passed 54 affected regressions
and 40 additional actual-Lua checks; SDK15.3 parsing passed.

The disabled workflow factory now reuses this strict decoder. Its original
pre-credential capability gate is unchanged and its 16 existing tests pass.
No synthetic transport constructor is connected to a native entrypoint.
