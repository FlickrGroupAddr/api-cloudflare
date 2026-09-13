-- Only validated release tooling writes receipts; HTTP/runtime paths only read them.
ALTER TABLE flickr_write_gate_events ADD COLUMN artifact_sha2_256 TEXT;
CREATE TABLE deployment_conformance (
 artifact_sha2_256 TEXT PRIMARY KEY CHECK(length(artifact_sha2_256)=64 AND artifact_sha2_256 NOT GLOB '*[^0-9a-f]*'),
 contract_sha2_256 TEXT NOT NULL CHECK(length(contract_sha2_256)=64),
 evidence_sha2_256 TEXT NOT NULL CHECK(length(evidence_sha2_256)=64),
 verified_at_us INTEGER NOT NULL DEFAULT(CAST(strftime('%s','now') AS INTEGER)*1000000)
) STRICT;
CREATE TRIGGER deployment_conformance_no_update BEFORE UPDATE ON deployment_conformance
 BEGIN SELECT RAISE(ABORT,'release_evidence_immutable'); END;
CREATE TRIGGER deployment_conformance_no_delete BEFORE DELETE ON deployment_conformance
 BEGIN SELECT RAISE(ABORT,'release_evidence_immutable'); END;
CREATE TRIGGER deployment_conformance_no_replace BEFORE INSERT ON deployment_conformance
 WHEN EXISTS(SELECT 1 FROM deployment_conformance WHERE artifact_sha2_256=NEW.artifact_sha2_256)
 BEGIN SELECT RAISE(ABORT,'release_evidence_immutable'); END;
