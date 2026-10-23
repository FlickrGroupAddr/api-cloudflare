"""Exact NEW source binding for the existing finite D1 control adapter.

Local public source only. No provider implementation, target discovery, journal
backend, credentials, state read, campaign allowance or qualification is supplied.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ADAPTER = ROOT / "probes/pmb1-d1-adapter"
sys.path.insert(0, str(ADAPTER))
import adapter  # noqa: E402

if adapter.__file__ is None or Path(adapter.__file__).resolve() != ADAPTER / "adapter.py":
    raise RuntimeError("ambiguous_fixed_adapter_import")


def _sha2_256(raw):
    return hashlib.sha256(raw).hexdigest()


def source_descriptor(expected_source_manifest_sha2_256: str) -> adapter.SourceDescriptor:
    """The expected pin is separately retained/reviewed; never current output.

    The fixed local manifest path and all covered source/artifact bytes are
    rechecked at every existing adapter source check. Only its immutable expected
    schema changes; original SQL/control pins and finite lifecycle remain intact.
    This particular binding includes the explicitly SYNTHETIC provider metadata
    fixture. It cannot be relabeled as an actual D1/schema observation.
    """
    if (
        type(expected_source_manifest_sha2_256) is not str
        or len(expected_source_manifest_sha2_256) != 64
        or any(c not in "0123456789abcdef" for c in expected_source_manifest_sha2_256)
    ):
        raise adapter.Refusal("invalid_prospective_source_pin")

    def verified():
        raw = (HERE / "source-manifest.json").read_bytes()
        if _sha2_256(raw) != expected_source_manifest_sha2_256:
            raise adapter.Refusal("prospective_source_manifest_drift")
        source = json.loads(raw)
        if source.get("profile") != "pmb1-private-application-no-real-v1":
            raise adapter.Refusal("prospective_profile_mismatch")
        artifacts = {}
        for base, records in ((ROOT, source["inputs"]), (HERE, source["artifacts"])):
            for name, expected in records.items():
                path = (base / name).resolve()
                if not path.is_relative_to(base):
                    raise adapter.Refusal("prospective_source_or_artifact_drift")
                checked = path.read_bytes()
                if _sha2_256(checked) != expected:
                    raise adapter.Refusal("prospective_source_or_artifact_drift")
                if base == HERE:
                    artifacts[name] = checked
        return source, json.loads(artifacts["d1-profile-fixture.json"])

    source, fixture = verified()

    def recheck():
        verified()

    schema = fixture["manifest"]["schema"]
    projected = [
        {
            "type": row["type"],
            "name": row["name"],
            "table": row["tbl_name"],
            "sql_sha2_256": None if row["sql"] is None else _sha2_256(row["sql"].encode()),
        }
        for row in schema
    ]
    # Exact immutable bytes, not a request-selected query, source callback result
    # or verifier-returned PASS. Adapter keeps its existing fixed SQL operations.
    manifest = (json.dumps({"candidate_schema": projected}, sort_keys=True) + "\n").encode()
    return adapter.SourceDescriptor(source["candidateSourceSha2_256"], manifest, recheck)
