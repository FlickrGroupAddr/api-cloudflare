"""Prepare a sanitized, history-free architecture publication snapshot.

No network mutation or Git commit occurs here. Private values remain in memory
and are never written into the destination, report, or diagnostic output.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

try:
    from . import audit_architecture_publication as audit
except ImportError:
    import audit_architecture_publication as audit

SOURCE = audit.ARCHITECTURE
DESTINATION = Path("C:/Projects/FGA/architecture-design-public")
EXCLUDED = {
    "docs/evidence/architecture-publication-audit-2026-09-11.json",
    "docs/research/2026-09-11-architecture-publication-audit.md",
}
PLUGIN = "lightroom/FGA Diagnostics.lrdevplugin/"

CONFIG_LOADER = """local function localSelection()
    local path = LrPathUtils.child(_PLUGIN.path, "DirectUpload.local.json")
    if LrFileUtils.exists(path) ~= "file" then
        error("Configure the ignored DirectUpload.local.json before running this probe")
    end
    local content = LrFileUtils.readFile(path)
    if type(content) ~= "string" or #content > 4096 then
        error("The local probe configuration is unavailable or oversized")
    end
    local config, _, decodeError = Json.decode(content)
    if decodeError or type(config) ~= "table" then
        error("The local probe configuration must be a JSON object")
    end
    if type(config.photoUuid) ~= "string" or #config.photoUuid ~= 36
        or not string.match(config.photoUuid, "^[%x%-]+$")
        or config.photoUuid == "00000000-0000-4000-8000-000000000000"
        or type(config.sourceFilename) ~= "string" or config.sourceFilename == ""
        or string.find(config.sourceFilename, "[/\\\\]")
        or type(config.publicFlickrUrl) ~= "string"
        or not string.match(config.publicFlickrUrl, "^https://www%.flickr%.com/photos/[%w_%-]+/%d+/$")
    then
        error("Configure one verified public photo using the documented local fields")
    end
    return config
end
"""


def tracked_tree() -> tuple[str, dict[str, bytes]]:
    head = audit.git("rev-parse", "HEAD").strip()
    if audit.git("status", "--porcelain").strip():
        raise RuntimeError("Source checkout must be clean before snapshot export.")
    result = {}
    for record in audit.command(["git", "ls-tree", "-r", "-z", head]).split(b"\0"):
        if not record:
            continue
        prefix, raw_name = record.split(b"\t", 1)
        mode, kind, oid = prefix.decode().split()
        name = raw_name.decode()
        relative = PurePosixPath(name)
        if mode != "100644" or kind != "blob" or relative.is_absolute() or ".." in relative.parts:
            raise RuntimeError("Snapshot contains an unsupported path or file mode.")
        if name not in EXCLUDED:
            result[name] = audit.command(["git", "cat-file", "blob", oid])
    return head, result


def indicators(files: dict[str, bytes]) -> dict[str, list[bytes]]:
    result = audit.indicator_values()
    names = set()
    for data in files.values():
        for value in re.findall(rb"[^\s`\"<>/\\]+\.(?:CR2|CR3|NEF|ARW|DNG|RAF)\b", data, re.I):
            names.add(value.rsplit(b".", 1)[0])
    result["private_source_stem"] = sorted(names)
    result["private_archive_location"] = sorted(
        set(
            re.findall(
                rb"`([A-Za-z]:[\\/][^`\r\n]+)`",
                files["docs/project-log/2026-08-20-raw-archive-survey.md"],
            )
        )
    )
    return result


def transform(name: str, data: bytes, private: dict[str, list[bytes]]) -> bytes:
    try:
        text = data.decode("utf-8")
    except UnicodeError:
        return data
    for rule, values in private.items():
        for index, value in enumerate(values, 1):
            replacement = (
                f"SYNTHETIC-PHOTO-{index:02}"
                if rule == "private_source_stem"
                else f"[private {rule.replace('_', ' ')} omitted]"
            )
            text = re.sub(
                re.escape(value.decode()),
                lambda _, replacement=replacement: replacement,
                text,
                flags=re.I,
            )
    if name == "docs/project-log/2026-08-20-raw-archive-survey.md":
        text = """# RAW archive survey

Date: 2026-08-20

Publication summary: the read-only survey established that RAW file size alone
does not bound a demosaiced lossless RGB export. Private archive locations,
source filenames, per-photo capture metadata, scene descriptions and inventory
statistics are retained only in the private architecture record.

The resulting format experiment and accepted decision are summarized in
[the PNG research](../research/png-experiment.md) and
[ADR 0002](../decisions/0002-lossless-png-output.md).
"""
    if name == "docs/research/png-experiment.md":
        text = """# PNG size and fidelity experiment

Status: Complete historical experiment; public summary

Date: 2026-08-20

The FGA LrC diagnostic plug-in compared full-resolution PNG bit-depth/color-space
variants with a maximum-quality JPEG baseline. The tested 8-bit sRGB PNGs fit
the configured Flickr upload limit; the tested 16-bit variants did not. This
sample is not a guarantee about another image. Every actual render must be
checked against the configured byte limit before upload authorization.

The private Flickr round trip confirmed that the tested PNG Original was
retained byte-for-byte. Credentials, private photo IDs, original URLs, hashes,
source filenames, archive locations, capture metadata and per-photo observations
are omitted from this public summary and retained only in the private record.
No photo, preview, catalog or private probe report is included in this snapshot.

[ADR 0002](../decisions/0002-lossless-png-output.md) records the accepted
full-resolution 8-bit sRGB PNG decision. The
[diagnostic plug-in](../../lightroom/FGA%20Diagnostics.lrdevplugin/README.md) and
[round-trip procedure](../operations/flickr-roundtrip.md) preserve the tooling.
Historical probe authorization does not authorize another upload.
"""
    if name == "docs/operations/photography-data-handling.md":
        start = text.index("## Source catalog")
        end = text.index("## Default classification")
        text = (
            text[:start]
            + """## Source catalog

The owner's working Lightroom Classic catalog and all referenced photographs
are private, read-only research inputs. Its location and inventory are kept
outside this public snapshot. Never copy a catalog, preview or private image
into Git or treat it as generally available test data.

"""
            + text[end:]
        )
    if name == "docs/project-log/2026-08-20-production-catalog-flickr-state.md":
        text = """# Production catalog Flickr-state inspection

Date: 2026-08-20

Publication summary: a read-only schema inspection confirmed that
`AgRemotePhoto.photo` links through `Adobe_images.rootFile` to `AgLibraryFile`,
while `AgRemotePhoto.remoteId` holds the provider identifier. A catalog record
is a candidate-discovery clue, not proof of current public Flickr visibility.

An independently checked public Flickr photo was used for the historical
direct-upload probe. Reimporting a source created a different catalog-record
UUID, confirming that Lightroom photo UUIDs are catalog-local identifiers.
Source filenames, catalog UUIDs and local paths are omitted here. The public
probe requires ignored local configuration and still checks the exact selected
UUID before rendering or network access. The original private evidence remains
in the private architecture repository.
"""
    if name == PLUGIN + "DirectUploadProbe.lua":
        text = re.sub(
            (
                r"local VERIFIED_LIGHTROOM_PHOTO_UUID = .*\n"
                r"local VERIFIED_SOURCE_FILENAME = .*\n"
                r"local VERIFIED_PUBLIC_FLICKR_URL = .*\n"
            ),
            lambda _: CONFIG_LOADER + "\n",
            text,
        )
        text = text.replace(
            "function DirectUploadProbe.run(context)\n",
            "function DirectUploadProbe.run(context)\n    local selection = localSelection()\n",
        )
        text = text.replace("VERIFIED_LIGHTROOM_PHOTO_UUID", "selection.photoUuid")
        text = text.replace("VERIFIED_SOURCE_FILENAME", "selection.sourceFilename")
        text = text.replace("VERIFIED_PUBLIC_FLICKR_URL", "selection.publicFlickrUrl")
    if name == PLUGIN + "README.md":
        start = text.index("This command proves that Lightroom")
        end = text.index("Lightroom renders a temporary", start)
        text = (
            text[:start]
            + """This diagnostic is locked to one explicitly configured catalog record. Copy
`DirectUpload.example.json` to the ignored `DirectUpload.local.json` in this
plug-in directory. Fill in the exact catalog photo UUID, source filename and
public Flickr page only after independently verifying that page without Flickr
authentication. The example values are intentionally unusable. Missing or
malformed configuration fails before reading a catalog photo or making a
network request. Never commit the local file or copy its values into reports.

Start the one-request loopback signer described in
`docs/operations/flickr-roundtrip.md`, select the configured photo, and choose
**Library â†’ Plug-in Extras â†’ Test Direct Flickr Upload from Public Photo**.
The confirmation remains mandatory; this snapshot authorizes no live upload.

"""
            + text[end:]
        )
    if name == "docs/operations/flickr-roundtrip.md":
        text = re.sub(r"--image '[^']+'", "--image '<approved-local-export.png>'", text)
        start = text.index("The command is locked to")
        end = text.index("The FGA Diagnostics plug-in", start)
        text = (
            text[:start]
            + """Configure the ignored `DirectUpload.local.json` as described in the diagnostic
plug-in README. The command checks the exact configured photo UUID. Independently
verify the public page without Flickr authentication before configuring it;
source filenames and catalog UUIDs belong only in the ignored local file.
Select that photo and choose **Library â†’ Plug-in Extras â†’ Test Direct Flickr
Upload from Public Photo**. This historical procedure does not authorize a new
live upload.

"""
            + text[end:]
        )
    if name == "README.md":
        text = text.replace(
            "# FlickrGroupAddr (FGA)\n",
            """# FlickrGroupAddr (FGA)

This is the owner-approved sanitized public snapshot of the architecture
repository. It begins with a new root commit and includes no inherited Git
history. The existing private architecture repository remains the working
source; see [snapshot provenance](PUBLICATION.md) for scope and validation.
""",
            1,
        )
    if name == "AGENTS.md":
        text = (
            """# Public snapshot context

This checkout is a publication snapshot. The private architecture-design
repository remains the working source. Do not start private board services or
perform live diagnostic actions merely by opening this public snapshot. Follow
an explicit owner task for any subsequent update. The sanitized original
working agreement is retained below as architecture context.

"""
            + text
        )
    if name == ".gitignore":
        text += (
            "\n# Machine-local diagnostic selection; never publish catalog identifiers.\n"
            "/lightroom/FGA Diagnostics.lrdevplugin/DirectUpload.local.json\n"
        )
    return text.encode()


def prepare() -> Path:
    if DESTINATION.exists():
        raise RuntimeError("Refusing to overwrite an existing snapshot checkout.")
    head, files = tracked_tree()
    private = indicators(files)
    clean = {name: transform(name, data, private) for name, data in files.items()}
    clean[PLUGIN + "DirectUpload.example.json"] = (
        json.dumps(
            {
                "photoUuid": "00000000-0000-4000-8000-000000000000",
                "sourceFilename": "SYNTHETIC-EXAMPLE.PNG",
                "publicFlickrUrl": "https://www.flickr.com/photos/YOUR_ACCOUNT/YOUR_PHOTO_ID/",
            },
            indent=2,
        )
        + "\n"
    ).encode()
    clean["PUBLICATION.md"] = f"""# Public architecture snapshot

Terry Ott approved publication of a sanitized snapshot in a new public repository
while retaining the existing private architecture history. This snapshot was
prepared from private source commit `{head}` at {datetime.now(UTC).isoformat()}.
The source repository remains private and is not rewritten or mirrored here.

Only tracked regular files from the selected source tree were considered. Git
objects, old refs, local secrets, diagnostic outputs, licensed SDK payloads and
private board state were not copied. The detailed private publication audit is
omitted. Private catalog/archive references and photo research inventories were
removed or replaced with public summaries. The direct-upload diagnostic now
requires ignored local configuration and fails closed without it.

Accepted ADRs and scoped contracts retain their original content and status;
this publication is not an architecture or production-conformance change.
The seven PNG assets are generated synthetic fixtures. Other image content in
the diagrams consists of SVG icons/wordmarks covered by existing provenance and
third-party notices. No private photograph or preview is included.

Validation results are recorded in `PUBLICATION-CHECKS.json`. Detailed local
scan output is kept outside this repository. Future updates must repeat the
content audit and publish only a clean tree, without importing private history.
""".encode()
    for name, data in clean.items():
        if audit.find_sensitive(data, private) or audit.find_sensitive(name.encode(), private):
            raise RuntimeError("Private indicator survived transformation: " + name)
    for name in files:
        if name.startswith("docs/decisions/") and clean[name] != files[name]:
            raise RuntimeError("An ADR was changed by sanitization.")
    DESTINATION.mkdir()
    for name, data in clean.items():
        path = DESTINATION.joinpath(*PurePosixPath(name).parts)
        if not path.resolve().is_relative_to(DESTINATION.resolve()):
            raise RuntimeError("Snapshot path escaped destination.")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    manifest = {
        "sourceCommit": head,
        "fileCount": len(clean),
        "excluded": sorted(EXCLUDED),
        "changed": [name for name in clean if clean[name] != files.get(name)],
        "fileHashes": {name: hashlib.sha256(data).hexdigest() for name, data in clean.items()},
    }
    report = audit.RUNS / "public-snapshot-preparation.json"
    report.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {"destination": str(DESTINATION), "files": len(clean), "changed": manifest["changed"]}
        )
    )
    return DESTINATION


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    prepare()


if __name__ == "__main__":
    main()
