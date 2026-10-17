"""Prepare byte-exact private restoration inputs and rehearse trusted capture offline.

No provider adapter, credential reader, deployment command or live restore exists.
The integrity index is pinned to the completed #0036 capture, not self-attested.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

INDEX_SHA256 = "ea43ba41d7bb5c6ae7fae569f77a8d126cfcfb7a0a550e5f92856c771b9f8202"
MODULE_SHA256 = "f1cef97fe6e1e62b5ff2b57f7e11516423974e756011750feb1aebe3abb13e6d"
FIXTURE_MANIFEST_SHA256 = "3d217655f6c2f92775e87e95bd521cc0a547776aa0124c07316e8b752b10a035"
FILES = frozenset(
    "account_rulesets_page_0.json active_version_0.json active_version_0_modules.json "
    "custom_domains.json deployments_after.json deployments_before.json page_rules.json "
    "restoration-inputs.json routes.json script_settings.json unversioned_artifact.bin "
    "worker_settings.json zone_lookup.json zone_rulesets_page_0.json zone_settings.json".split()
)
MAX_BYTES = 16 * 1024 * 1024


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_bounded(path: Path) -> bytes:
    with path.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("restoration_input_size")
    return raw


def private_path(path: Path, repository: Path) -> Path:
    resolved = path.resolve()
    if repository.resolve() == resolved or repository.resolve() in resolved.parents:
        raise ValueError("private_destination_required")
    if not any(parent.name == "private-evidence" for parent in resolved.parents):
        raise ValueError("private_destination_required")
    return resolved


def validate_capture(root: Path) -> dict[str, bytes]:
    """Read only finite captured metadata/module files; never discover credentials."""
    index_raw = read_bounded(root / "private-integrity-index.json")
    if digest(index_raw) != INDEX_SHA256:
        raise ValueError("capture_index_mismatch")
    index = json.loads(index_raw)
    rows = index["files"]
    if len(rows) != len(FILES) or {row["name"] for row in rows} != FILES:
        raise ValueError("capture_inventory_mismatch")
    contents = {}
    for row in rows:
        raw = read_bounded(root / "private" / row["name"])
        if len(raw) != row["bytes"] or digest(raw) != row["sha256"]:
            raise ValueError("capture_integrity_mismatch")
        contents[row["name"]] = raw
    restoration = json.loads(contents["restoration-inputs.json"])
    if (
        restoration["deploymentStable"] is not True
        or restoration["artifactBoundToEveryActiveVersion"] is not True
        or contents["deployments_before.json"] != contents["deployments_after.json"]
    ):
        raise ValueError("capture_deployment_mismatch")
    for name, row in restoration["captured"].items():
        filename = name + (".bin" if name == "unversioned_artifact" else ".json")
        if filename not in contents or digest(contents[filename]) != row["SHA2-256"]:
            raise ValueError("restoration_index_mismatch")
    module = json.loads(contents["active_version_0_modules.json"])["result"]
    if module["main_module"] != "worker.js" or len(module["modules"]) != 1:
        raise ValueError("capture_module_shape")
    encoded = module["modules"][0]["content_base64"]
    source = base64.b64decode(encoded, validate=True)
    if digest(source) != MODULE_SHA256 or base64.b64encode(source).decode() != encoded:
        raise ValueError("capture_module_mismatch")
    source.decode("utf-8", errors="strict")
    version = json.loads(contents["active_version_0.json"])["result"]
    if version["id"] != module["id"] or restoration["pinnedActiveVersionWeights"] != {
        version["id"]: 100
    }:
        raise ValueError("capture_version_mismatch")
    bindings = version["resources"]["bindings"]
    flags = {row["name"]: row.get("text") for row in bindings if row["type"] == "plain_text"}
    if (
        flags.get("FGA_ARTIFACT_SHA2_256") != MODULE_SHA256
        or flags.get("FGA_INTAKE_ENABLED") != "0"
        or flags.get("FGA_DISPATCH_ENABLED") != "0"
        or any(row["name"].startswith("FIXED_ORIGIN_") for row in bindings)
    ):
        raise ValueError("captured_capability_mismatch")
    return {**contents, "captured.mjs": source, "private-integrity-index.json": index_raw}


def prepare(repository: Path, capture: Path, output: Path) -> dict[str, Any]:
    """Materialize every exact restoration/configuration/edge input privately."""
    private_path(capture, repository)
    output = private_path(output, repository)
    if output.exists():
        raise ValueError("fresh_private_destination_required")
    contents = validate_capture(capture)
    output.mkdir(parents=True, exist_ok=False)
    for name, raw in contents.items():
        (output / name).write_bytes(raw)
    manifest = {
        "schemaVersion": 1,
        "kind": "offline_exact_restoration_packet",
        "captureIndexSha256": INDEX_SHA256,
        "moduleSha256": MODULE_SHA256,
        "files": {name: digest(raw) for name, raw in contents.items()},
        "providerRestorationVerified": False,
        "changedSecretSemanticsVerified": False,
        "productionStateVerified": False,
        "deploymentAllowed": False,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", newline="\n")
    verify_packet(output)
    return manifest


def verify_packet(packet: Path) -> None:
    manifest = json.loads(read_bounded(packet / "manifest.json"))
    expected = FILES | {"captured.mjs", "private-integrity-index.json"}
    if (
        set(manifest["files"]) != expected
        or manifest["captureIndexSha256"] != INDEX_SHA256
        or manifest["moduleSha256"] != MODULE_SHA256
        or manifest["schemaVersion"] != 1
        or manifest["kind"] != "offline_exact_restoration_packet"
        or any(
            manifest[key] is not False
            for key in (
                "providerRestorationVerified",
                "changedSecretSemanticsVerified",
                "productionStateVerified",
                "deploymentAllowed",
            )
        )
    ):
        raise ValueError("packet_inventory_mismatch")
    index_raw = read_bounded(packet / "private-integrity-index.json")
    if digest(index_raw) != INDEX_SHA256:
        raise ValueError("packet_index_mismatch")
    for row in json.loads(index_raw)["files"]:
        if digest(read_bounded(packet / row["name"])) != row["sha256"]:
            raise ValueError("packet_integrity_mismatch")
    if digest(read_bounded(packet / "captured.mjs")) != MODULE_SHA256:
        raise ValueError("packet_module_mismatch")
    for name, expected_digest in manifest["files"].items():
        if digest(read_bounded(packet / name)) != expected_digest:
            raise ValueError("packet_manifest_mismatch")


# Actual unchanged captured default.fetch executes twice in isolated VM contexts.
# Only synthetic SQLite and the existing reviewed offline host adapter are used.
REHEARSAL = r"""
import assert from 'node:assert/strict';
import {readFileSync,writeFileSync} from 'node:fs';
import {join} from 'node:path';
import {pathToFileURL} from 'node:url';
const [repo,fixture,packet]=process.argv.slice(2);
assert.equal(process.version,'v24.22.0');
const probe=join(repo,'probes/fixed-origin-isolation');
const {loadOfflineModule}=await import(pathToFileURL(join(probe,'offline_modules.mjs')));
const {createSyntheticStore}=await import(pathToFileURL(join(probe,'offline_sqlite.mjs')));
const counters={hostIo:0,globalFetch:0,dynamicImport:0,syntheticSql:0};
const before=await loadOfflineModule(join(fixture,'captured.mjs'),counters);
const restored=await loadOfflineModule(join(packet,'captured.mjs'),counters);
assert.equal(before.ROUTES.length,25);
assert.deepEqual(JSON.parse(JSON.stringify(before.ROUTES)),JSON.parse(JSON.stringify(restored.ROUTES)));
const db=createSyntheticStore(join(fixture,'candidate/migrations'),counters);
db.raw.exec("INSERT INTO flickr_write_gates VALUES"+
 "('deployment','*',0,1),('user','probe-user',0,1)");
const snapshot=()=>JSON.stringify(db.raw.prepare(
 "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").all().map(({name})=>[
 name,db.raw.prepare('SELECT * FROM "'+name.replaceAll('"','""')+'"')
 .all().map(row=>JSON.stringify(row)).sort()]));
const initial=snapshot();
const version=JSON.parse(readFileSync(join(packet,'active_version_0.json'))).result;
const bindings=version.resources.bindings;
const flags=Object.fromEntries(bindings.filter(row=>
 row.type==='plain_text'&&/^FGA_.*_ENABLED$/.test(row.name)).map(row=>[row.name,row.text]));
assert.equal(flags.FGA_INTAKE_ENABLED,'0');assert.equal(flags.FGA_DISPATCH_ENABLED,'0');
assert.ok(!bindings.some(row=>row.name.startsWith('FIXED_ORIGIN_')));
const deny=new Proxy({}, {get(){throw Error('external_binding_denied')}});
const env=Object.freeze({...flags,DB:db,COORD:deny,ASSETS:deny});
const signature=async(module,path,method,headers={})=>{
 const response=await module.default.fetch(new Request('https://flickrgroupaddr.com'+path,{method,headers}),env);
 let body=await response.text();
 if(response.headers.get('Content-Type')?.includes('application/json')){
  const parsed=JSON.parse(body);
  if(parsed.error?.correlationId){
   assert.match(parsed.error.correlationId,
    /^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/);
   parsed.error.correlationId='verified-fresh-correlation';
  }
  body=JSON.stringify(parsed);
 }
 return {status:response.status,headers:[...response.headers],body};
};
let routes=0;
for(const route of before.ROUTES){
 const path=route.pathPattern.replaceAll(/\{[^}]+\}/g,'synthetic');
 assert.deepEqual(await signature(before,path,route.method),
  await signature(restored,path,route.method));routes++;
}
const intended=['/api/v001/installations/current',
 '/api/v001/existing-public-photos?page=1&page_size=1',
 '/api/v001/existing-public-photos/photo/thumbnail'+
 '?page=1&page_size=1&linked_flickr_revision=1'];
const statuses=[];
for(const path of intended){
 const a=await signature(before,path,'GET');const b=await signature(restored,path,'GET');
 assert.deepEqual(a,b);statuses.push(b.status);
}
assert.deepEqual(statuses,[401,404,404]);
assert.equal(snapshot(),initial);
const gates=db.raw.prepare(
 'SELECT scope,enabled,revision FROM flickr_write_gates ORDER BY scope').all();
assert.deepEqual(gates.map(row=>[row.scope,row.enabled,row.revision]),[['deployment',0,1],['user',0,1]]);
assert.equal(counters.hostIo,0);assert.equal(counters.globalFetch,0);assert.equal(counters.dynamicImport,0);
const receipt={schemaVersion:1,kind:'actual_captured_offline_restore_rehearsal',
 ordinaryRoutesCompared:routes,intendedRouteStatuses:statuses,exactCapturedModule:true,
 capturedCapabilityFlagsPreserved:true,qualificationBindingsAbsent:true,
 syntheticDatabaseUnchanged:true,syntheticPausedGatesVerified:2,
 hostIo:0,globalFetch:0,dynamicImport:0,providerRestorationVerified:false,
 changedSecretSemanticsVerified:false,productionStateVerified:false,deploymentAllowed:false};
writeFileSync(join(packet,'rehearsal-receipt.json'),JSON.stringify(receipt,null,2)+'\n');
db.raw.close();
"""


def rehearse(repository: Path, fixture: Path, packet: Path, node: Path) -> dict[str, Any]:
    private_path(fixture, repository)
    private_path(packet, repository)
    verify_packet(packet)
    if digest(read_bounded(fixture / "captured.mjs")) != MODULE_SHA256:
        raise ValueError("rehearsal_fixture_mismatch")
    fixture_manifest_raw = read_bounded(fixture / "manifest.json")
    if digest(fixture_manifest_raw) != FIXTURE_MANIFEST_SHA256:
        raise ValueError("rehearsal_fixture_manifest_mismatch")
    for name, expected_digest in json.loads(fixture_manifest_raw)["candidateSourceFiles"].items():
        if digest(read_bounded(fixture / "candidate" / name)) != expected_digest:
            raise ValueError("rehearsal_fixture_source_mismatch")
    runner = packet / "rehearsal.mjs"
    receipt = packet / "rehearsal-receipt.json"
    if runner.exists() or receipt.exists():
        raise ValueError("rehearsal_already_attempted")
    with runner.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(REHEARSAL)
    try:
        result = subprocess.run(
            [
                str(node),
                "--experimental-vm-modules",
                str(runner),
                str(repository),
                str(fixture),
                str(packet),
            ],
            capture_output=True,
            timeout=60,
            check=False,
        )
    except OSError, subprocess.SubprocessError:
        raise ValueError("offline_rehearsal_refused") from None
    # Never relay raw VM/source diagnostics or provider metadata to stdout.
    if result.returncode != 0:
        raise ValueError("offline_rehearsal_failed")
    verify_packet(packet)
    return json.loads(receipt.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", type=Path)
    parser.add_argument("capture", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("fixture", type=Path)
    parser.add_argument("node", type=Path)
    args = parser.parse_args()
    try:
        prepare(args.repository, args.capture, args.output)
        result = rehearse(args.repository, args.fixture, args.output, args.node)
    except OSError, ValueError, TypeError, KeyError, RecursionError:
        print("fixed_origin_offline_restoration_refused")
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
