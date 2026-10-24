-- MIT License; copyright 2026 Terry Ott.
-- Operator-reviewed source only. No runtime bootstrap or schema installer.
-- ADR0051: broad D1 code can dismantle guards; this is NOT SQL-role isolation.
CREATE TABLE pmb1_evidence_envelopes (
  envelope_id TEXT PRIMARY KEY CHECK(length(envelope_id)=36),
  binding_json TEXT NOT NULL CHECK(json_valid(binding_json) AND length(CAST(binding_json AS BLOB))<=4096),
  header_json TEXT NOT NULL CHECK(json_valid(header_json) AND length(CAST(header_json AS BLOB))<=16384),
  payload_bytes INTEGER NOT NULL CHECK(typeof(payload_bytes)='integer' AND payload_bytes BETWEEN 1 AND 4194304),
  chunk_count INTEGER NOT NULL CHECK(typeof(chunk_count)='integer' AND chunk_count BETWEEN 1 AND 16),
  CHECK(json_extract(header_json,'$.reference.envelopeId')=envelope_id),
  CHECK(json_extract(header_json,'$.payloadBytes')=payload_bytes),
  CHECK(json_extract(header_json,'$.chunkCount')=chunk_count),
  CHECK(json_extract(header_json,'$.binding')=json(binding_json)),
  CHECK(COALESCE((json_extract(header_json,'$.mode')='raw-capture' AND json_array_length(header_json,'$.captureKeys') BETWEEN 1 AND 16)
    OR (json_extract(header_json,'$.mode')='evidence-use' AND json_array_length(header_json,'$.captureKeys')=0
      AND json_extract(header_json,'$.reference.operation') IN ('main-assess','partition-reconcile')),0)),
  CHECK(json_array_length(header_json,'$.captureAttempts')=json_array_length(header_json,'$.captureKeys')),
  CHECK(json_extract(header_json,'$.throughMs')>json_extract(header_json,'$.fromMs')),
  CHECK(json_extract(header_json,'$.throughMs')-json_extract(header_json,'$.fromMs')<=600000)
) STRICT;
CREATE TABLE pmb1_evidence_chunks (
  envelope_id TEXT NOT NULL REFERENCES pmb1_evidence_envelopes(envelope_id),
  ordinal INTEGER NOT NULL CHECK(typeof(ordinal)='integer' AND ordinal BETWEEN 0 AND 15),
  payload TEXT NOT NULL CHECK(length(CAST(payload AS BLOB)) BETWEEN 1 AND 262144 AND payload NOT GLOB '*[^ -~]*'),
  PRIMARY KEY(envelope_id,ordinal)
) STRICT;
CREATE TABLE pmb1_evidence_events (
  envelope_id TEXT NOT NULL REFERENCES pmb1_evidence_envelopes(envelope_id),
  revision INTEGER NOT NULL CHECK(typeof(revision)='integer' AND revision BETWEEN 1 AND 35),
  kind TEXT NOT NULL CHECK(kind IN ('publish','use-reserved','native-consumed','terminal','retire')),
  capture_key TEXT NOT NULL CHECK(length(CAST(capture_key AS BLOB))<=256),
  attempt_id TEXT NOT NULL CHECK(length(attempt_id)=36),
  outcome TEXT NOT NULL CHECK(outcome IN ('','complete','refused','unknown')),
  observed_ms INTEGER NOT NULL CHECK(typeof(observed_ms)='integer' AND observed_ms>=0),
  PRIMARY KEY(envelope_id,revision), UNIQUE(envelope_id,kind,capture_key),
  CHECK((kind='terminal' AND outcome<>'') OR (kind<>'terminal' AND outcome='')),
  CHECK((kind='terminal') OR (kind='native-consumed' AND capture_key<>'') OR
        (kind NOT IN ('native-consumed','terminal') AND capture_key=''))
) STRICT;
CREATE TRIGGER pmb1_evidence_envelope_insert BEFORE INSERT ON pmb1_evidence_envelopes
BEGIN
  SELECT CASE WHEN EXISTS(SELECT 1 FROM pmb1_evidence_envelopes WHERE envelope_id=NEW.envelope_id)
    THEN RAISE(ABORT,'immutable evidence envelope') END;
  SELECT CASE WHEN EXISTS(SELECT 1 FROM pmb1_evidence_envelopes e
    WHERE json_extract(NEW.header_json,'$.reference.attemptId')=json_extract(e.header_json,'$.reference.attemptId')
      OR EXISTS(SELECT 1 FROM json_each(e.header_json,'$.captureAttempts') old
        WHERE json_extract(NEW.header_json,'$.reference.attemptId')=json_extract(old.value,'$.attemptId')))
    THEN RAISE(ABORT,'spent evidence use attempt') END;
  SELECT CASE WHEN EXISTS(SELECT 1 FROM json_each(NEW.header_json,'$.captureAttempts') n,pmb1_evidence_envelopes e
      WHERE json_extract(n.value,'$.attemptId')=json_extract(e.header_json,'$.reference.attemptId')
        OR EXISTS(SELECT 1 FROM json_each(e.header_json,'$.captureAttempts') old
          WHERE json_extract(n.value,'$.attemptId')=json_extract(old.value,'$.attemptId')))
    THEN RAISE(ABORT,'spent or conflicting evidence attempt') END;
  SELECT CASE WHEN EXISTS(SELECT 1 FROM pmb1_evidence_envelopes e
    WHERE json_extract(e.binding_json,'$.databaseId')=json_extract(NEW.binding_json,'$.databaseId')
      AND json_extract(e.binding_json,'$.controlReference')=json_extract(NEW.binding_json,'$.controlReference')
      AND json_extract(e.header_json,'$.reference.operation')=json_extract(NEW.header_json,'$.reference.operation')
      AND json_extract(e.header_json,'$.fromMs')<json_extract(NEW.header_json,'$.throughMs')
      AND json_extract(NEW.header_json,'$.fromMs')<json_extract(e.header_json,'$.throughMs'))
    THEN RAISE(ABORT,'overlapping evidence interval') END;
END;
CREATE TRIGGER pmb1_evidence_chunk_insert BEFORE INSERT ON pmb1_evidence_chunks
BEGIN
  SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM pmb1_evidence_envelopes e WHERE e.envelope_id=NEW.envelope_id
    AND NEW.ordinal<e.chunk_count) OR
    EXISTS(SELECT 1 FROM pmb1_evidence_chunks WHERE envelope_id=NEW.envelope_id AND ordinal=NEW.ordinal) OR
    EXISTS(SELECT 1 FROM pmb1_evidence_events WHERE envelope_id=NEW.envelope_id)
    THEN RAISE(ABORT,'immutable or excessive evidence chunk') END;
END;
CREATE TRIGGER pmb1_evidence_event_insert BEFORE INSERT ON pmb1_evidence_events
BEGIN
  SELECT CASE WHEN NEW.revision<>1+COALESCE((SELECT MAX(revision) FROM pmb1_evidence_events WHERE envelope_id=NEW.envelope_id),0)
    OR EXISTS(SELECT 1 FROM pmb1_evidence_events WHERE envelope_id=NEW.envelope_id AND kind=NEW.kind AND capture_key=NEW.capture_key)
    THEN RAISE(ABORT,'evidence event order') END;
  SELECT CASE WHEN NEW.kind='publish' AND (
    NEW.revision<>1 OR NOT EXISTS(SELECT 1 FROM pmb1_evidence_envelopes e WHERE e.envelope_id=NEW.envelope_id
      AND e.chunk_count=(SELECT COUNT(*) FROM pmb1_evidence_chunks c WHERE c.envelope_id=e.envelope_id)
      AND e.payload_bytes=(SELECT SUM(length(CAST(payload AS BLOB))) FROM pmb1_evidence_chunks c WHERE c.envelope_id=e.envelope_id)))
    THEN RAISE(ABORT,'incomplete evidence publication') END;
  SELECT CASE WHEN NEW.kind<>'publish' AND NOT EXISTS(SELECT 1 FROM pmb1_evidence_events WHERE envelope_id=NEW.envelope_id AND kind='publish')
    THEN RAISE(ABORT,'unpublished evidence') END;
  SELECT CASE WHEN NEW.kind IN ('use-reserved','native-consumed') AND (
    EXISTS(SELECT 1 FROM pmb1_evidence_events WHERE envelope_id=NEW.envelope_id AND (kind='retire' OR (kind='terminal' AND capture_key=NEW.capture_key))) OR
    NOT EXISTS(SELECT 1 FROM pmb1_evidence_envelopes WHERE envelope_id=NEW.envelope_id
      AND NEW.observed_ms>=json_extract(header_json,'$.fromMs') AND NEW.observed_ms<json_extract(header_json,'$.throughMs')))
    THEN RAISE(ABORT,'inactive evidence') END;
  SELECT CASE WHEN NEW.kind='native-consumed' AND NOT EXISTS(SELECT 1 FROM pmb1_evidence_events WHERE envelope_id=NEW.envelope_id AND kind='use-reserved')
    THEN RAISE(ABORT,'unreserved native capture') END;
  SELECT CASE WHEN NEW.kind='terminal' AND NOT EXISTS(SELECT 1 FROM pmb1_evidence_events v
    JOIN pmb1_evidence_envelopes e USING(envelope_id) WHERE v.envelope_id=NEW.envelope_id
      AND ((json_extract(e.header_json,'$.mode')='raw-capture' AND v.kind='native-consumed' AND v.capture_key=NEW.capture_key AND v.attempt_id=NEW.attempt_id)
        OR (json_extract(e.header_json,'$.mode')='evidence-use' AND v.kind='use-reserved' AND NEW.capture_key=''
          AND v.attempt_id=NEW.attempt_id)))
    THEN RAISE(ABORT,'unconsumed native capture') END;
  SELECT CASE WHEN (NEW.kind='native-consumed' OR (NEW.kind='terminal' AND
      (SELECT json_extract(header_json,'$.mode') FROM pmb1_evidence_envelopes WHERE envelope_id=NEW.envelope_id)='raw-capture')) AND NOT EXISTS(
    SELECT 1 FROM pmb1_evidence_envelopes e,json_each(e.header_json,'$.captureAttempts') c WHERE e.envelope_id=NEW.envelope_id
      AND json_extract(c.value,'$.captureKey')=NEW.capture_key AND json_extract(c.value,'$.attemptId')=NEW.attempt_id)
    THEN RAISE(ABORT,'wrong native capture') END;
  SELECT CASE WHEN NEW.kind='terminal' AND
      (SELECT json_extract(header_json,'$.mode') FROM pmb1_evidence_envelopes WHERE envelope_id=NEW.envelope_id)='evidence-use'
      AND (NEW.capture_key<>'' OR NEW.attempt_id<>(SELECT json_extract(header_json,'$.reference.attemptId') FROM pmb1_evidence_envelopes WHERE envelope_id=NEW.envelope_id))
    THEN RAISE(ABORT,'wrong evidence use attempt') END;
  SELECT CASE WHEN NEW.kind NOT IN ('native-consumed','terminal') AND NEW.attempt_id<>(SELECT json_extract(header_json,'$.reference.attemptId') FROM pmb1_evidence_envelopes WHERE envelope_id=NEW.envelope_id)
    THEN RAISE(ABORT,'wrong envelope attempt') END;
END;
CREATE TRIGGER pmb1_evidence_envelope_update BEFORE UPDATE ON pmb1_evidence_envelopes BEGIN SELECT RAISE(ABORT,'immutable evidence'); END;
CREATE TRIGGER pmb1_evidence_envelope_delete BEFORE DELETE ON pmb1_evidence_envelopes BEGIN SELECT RAISE(ABORT,'immutable evidence'); END;
CREATE TRIGGER pmb1_evidence_chunk_update BEFORE UPDATE ON pmb1_evidence_chunks BEGIN SELECT RAISE(ABORT,'immutable evidence'); END;
CREATE TRIGGER pmb1_evidence_chunk_delete BEFORE DELETE ON pmb1_evidence_chunks BEGIN SELECT RAISE(ABORT,'immutable evidence'); END;
CREATE TRIGGER pmb1_evidence_event_update BEFORE UPDATE ON pmb1_evidence_events BEGIN SELECT RAISE(ABORT,'immutable evidence'); END;
CREATE TRIGGER pmb1_evidence_event_delete BEFORE DELETE ON pmb1_evidence_events BEGIN SELECT RAISE(ABORT,'immutable evidence'); END;
