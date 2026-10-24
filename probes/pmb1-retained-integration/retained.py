"""Reuse the reviewed exact-byte retained reader without a second implementation."""

import importlib.util
from pathlib import Path

_path = Path(__file__).resolve().parent.parent / "pmb1-static-artifact" / "retained.py"
_spec = importlib.util.spec_from_file_location("pmb1_reviewed_retained", _path)
if _spec is None or _spec.loader is None:
    raise RuntimeError("reviewed retained reader unavailable")
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
retained_bytes = _module.retained_bytes
sha2_256 = _module.sha2_256
