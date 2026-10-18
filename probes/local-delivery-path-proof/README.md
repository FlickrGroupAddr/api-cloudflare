# Source-only local delivery path proof

Ticket #0183. This standalone probe is not registered in an application or live
credential workflow. Its entry point is unconditionally NO APPLY; no real DLL
loader or credential/runtime-path binding is provided.

The pure guard and complete Win32 adapter source are reviewed under ordinary
trusted-local-host assumptions. They require participating directory handles,
separate attribute/EA/security checks, same-handle identity/security, exclusive
protected creation and effect-time accounting. They do not prove actual host
custody or defend against trusted principals dismantling the namespace.

From the repository root, using the pinned uv/Python environment:

```console
uv run --frozen python -m unittest discover -s probes/local-delivery-path-proof -p "test_*.py"
```

All tests use injected synthetic APIs. They do not invoke real Win32 bindings,
read credentials, inspect private paths or contact a provider. The reviewed
source pair also passed the repository's standard Windows/Python 3.14 Pyright
policy with only standalone-probe import/environment paths projected.

See the operations record for evidence and remaining integration/action gates.
