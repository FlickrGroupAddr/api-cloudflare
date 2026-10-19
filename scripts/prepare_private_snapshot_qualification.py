"""Prepare immutable public-source pins and ungranted isolated-D1 templates offline.

No account lookup, credential read, provider request or live packet is produced.
The existing qualifier owns all execution; this preparer adds no execution path.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from scripts.private_d1_snapshot_reader import SOURCE_FILES
from scripts.qualify_private_d1_snapshot import EVIDENCE_SOURCE_FILES
from scripts.temporary_composition_metadata_collector import canonical, digest

ROOT = Path(__file__).resolve().parents[1]
QUALIFIER_SOURCE_FILES = (*SOURCE_FILES, *EVIDENCE_SOURCE_FILES)
FILES = ("source-pins.json", "recipe.json", "packet-template.json", "consent-template.json")


def source_sha256(root: Path = ROOT) -> dict[str, str]:
    """Read only the closed public source set, never a private configuration."""
    names = (*QUALIFIER_SOURCE_FILES, Path(__file__).name)
    result = {}
    for name in names:
        path = root / "scripts" / name
        if path.is_symlink() or path.is_junction() or not path.is_file():
            raise ValueError("Source must be an ordinary allowlisted file")
        result[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def packet_template(source_pins: dict[str, str]) -> dict[str, object]:
    """Exact qualifier keys with unknown action-time inputs deliberately invalid."""
    return {
        "schemaVersion": 1,
        "kind": "fresh_synthetic_d1_qualification",
        "sourceSha256": {
            name: value for name, value in source_pins.items() if name in QUALIFIER_SOURCE_FILES
        },
        **dict.fromkeys(
            (
                "runId",
                "accountId",
                "endpointAddress",
                "startsAt",
                "expiresAt",
                "providerTokenExpiresAt",
                "credentialBinding",
                "grantEvidenceSha256",
                "privateCustodySha256",
                "journalPath",
                "outputPath",
                "readerJournalPath",
            )
        ),
    }


def consent_template() -> dict[str, object]:
    return {"approved": False, "decisionRef": None, "packetSha256": None}


def recipe(source_pins: dict[str, str]) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "kind": "private_snapshot_qualification_preparation",
        "status": "source_prepared_live_ungranted",
        "sourceSha256": source_pins,
        "qualifier": "scripts.qualify_private_d1_snapshot",
        "maximumRequests": 26,
        "orderedRequestBounds": [
            {"operation": "fresh_create", "maximum": 1},
            {"operation": "fixed_synthetic_seed", "maximum": 1},
            {"operation": "discovery_capture_sql", "maximum": 11},
            {"operation": "exact_reader_sql", "maximum": 11},
            {"operation": "same_acknowledged_uuid_delete", "maximum": 1},
            {"operation": "same_uuid_get_observation", "maximum": 1},
        ],
        "maximumCallerSeconds": 1200,
        "maximumRequestSeconds": 30,
        "maximumTablesIncludingProviderTables": 2,
        "maximumRowsPerTable": 256,
        "maximumResponseBodyBytes": 262144,
        "outerResponseWireCapBytes": 327680,
        "readerResponseWireCapBytes": 262144,
        "readerAggregateResponseWireCapBytes": 2621440,
        "maximumAggregateResponseWireBytes": 7536640,
        "existingDatabaseIdAccepted": False,
        "automaticRetries": False,
        "resumeOrReconcile": False,
        "liveExecutionGranted": False,
        "effectiveGrantsVerified": False,
        "privateCustodyVerified": False,
        "sqlSettlementQualified": False,
        "cleanupVerified": False,
        "productionQualified": False,
        "realExtractionQualified": False,
        "providerNotFoundMeaning": "exact_response_observation_only",
        "publisherDisposalExceptionApplicable": False,
    }


def _documents(root: Path) -> dict[str, bytes]:
    pins = source_sha256(root)
    return {
        "source-pins.json": canonical(pins),
        "recipe.json": canonical(recipe(pins)),
        "packet-template.json": canonical(packet_template(pins)),
        "consent-template.json": canonical(consent_template()),
    }


def verify(
    destination: Path, expected_recipe_sha256: str | None = None, root: Path = ROOT
) -> dict[str, object]:
    """Reject source/artifact drift and compare an independently retained recipe pin."""
    if destination.is_symlink() or destination.is_junction():
        raise ValueError("Stage links are not supported")
    destination = destination.resolve(strict=True)
    actual = set()
    for path in destination.iterdir():
        if path.is_symlink() or path.is_junction() or not path.is_file():
            raise ValueError("Stage must contain only the closed ordinary file set")
        actual.add(path.name)
    if actual != set(FILES):
        raise ValueError("Stage file set differs")
    documents = _documents(root)
    for name, expected in documents.items():
        if (destination / name).read_bytes() != expected:
            raise ValueError("Stage or source changed; prepare a fresh reviewed candidate")
    result = recipe(source_sha256(root))
    if expected_recipe_sha256 is not None and digest(result) != expected_recipe_sha256:
        raise ValueError("Independent recipe pin differs")
    return result


def prepare(destination: Path, root: Path = ROOT) -> dict[str, object]:
    """Create a new offline stage. These files contain public source facts only."""
    root = root.resolve(strict=True)
    if destination.exists() or destination.is_symlink() or destination.is_junction():
        raise ValueError("Use a new staging directory")
    destination = destination.parent.resolve(strict=True) / destination.name
    if destination.is_relative_to(root):
        raise ValueError("Stage must be outside the source checkout")
    documents = _documents(root)
    destination.mkdir(exist_ok=False)
    for name, data in documents.items():
        with (destination / name).open("xb") as handle:
            handle.write(data)
    return verify(destination, root=root)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--expected-recipe-sha256")
    args = parser.parse_args(argv)
    try:
        if args.expected_recipe_sha256 and not args.verify:
            raise ValueError("Independent pin applies to verification only")
        result = (
            verify(args.destination, args.expected_recipe_sha256)
            if args.verify
            else prepare(args.destination)
        )
    except OSError, ValueError:
        print("private_snapshot_preparation_refused")
        return 1
    print("Source-only recipe SHA2-256: " + digest(result))
    print("Live account access remains ungranted; templates are invalid consent and inputs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
