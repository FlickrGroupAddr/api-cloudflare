# Exact local preparation source candidate

Ticket #0161. Source only; no live invocation or current action-ready packet.
Both CLI entries unconditionally return `NO_APPLY_source_only` with false
native/POST consent. `local_action.live_factory` is a deferred Python callable,
with no command-line registration, configuration read or automatic caller.

`local_action.py` supplies the concrete Windows process identity, exact path
binding, claim/receipt and preparation implementation. It reuses the unchanged
#0183 adapter's handle/security/volume plumbing and the unchanged pure guard.
Its subclass replaces fixture path checks explicitly; it does not change the
reviewed module's constants or the historical helpers/manifests. `binding.py`
also retains a fixed synthetic packet coordinator for reviewable regressions.

From the repository root in an isolated pinned uv Python process:

```powershell
$env:PYTHONPATH='probes/post-local-preparation;probes/local-delivery-path-proof'
uv run --frozen python -m unittest discover -s probes/post-local-preparation -p 'test_*.py'
uv run --frozen ruff check probes/post-local-preparation
uv run --frozen ruff format --check probes/post-local-preparation
uv run --frozen pyright --project probes/post-local-preparation/pyrightconfig.json
```

The standalone Pyright configuration projects source/import/venv paths only;
Windows, Python 3.14 and standard checking match repository policy. Tests inject
invented identities, paths, handles, clocks and APIs, including the live-factory
route. They never call a real DLL loader, current-process query or private path.
The explicit PYTHONPATH is confined to this child process; no shared import or
tool configuration changes are needed.

See [the operations record](../../docs/operations/post-local-preparation-binding-2026-10-19.md)
for historical boundaries and finite remaining action/input gates.
The subsequent [#0189 role-chain correction](../../docs/operations/post-local-path-roles-2026-10-19.md)
records the distinct parent schema and isolated path-policy extension; the
historical record is preserved unchanged. Passing source
tests cannot establish actual current-host custody, token validity or consent.


`LocalPacket` now binds complete `ParentChain(roots, private_from)` values for
source, destination, each native marker, claim and receipt. The seven native
names are fixed and remain disjoint from the four other file roles. Shared
ancestors are acquired once, inspected through the same held handle on reuse,
and qualified under each role's explicit private boundary. All parents must
already exist. Missing or unsafe chains, any present/unknown native marker or
local output, and uncertain cleanup refuse without replay.

`role_policy.py` preserves the #0183 metadata/chain/parent rules with one lexical
extension for the exact ordinary `.coordination-runs` component. It does not
rewrite paths or modify the pinned #0183 module. Its independent source pin is
part of the exact packet; old single-parent packets cannot be reused.
