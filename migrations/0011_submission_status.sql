-- Status reads have no authority to schedule, retry, or change group intents.
ALTER TABLE submission_intents ADD COLUMN state_changed_at_us INTEGER;
UPDATE submission_intents SET state_changed_at_us=COALESCE(
 (SELECT MAX(created_at_us) FROM submission_intent_events e WHERE e.intent_id=submission_intents.intent_id),created_at_us);
CREATE TRIGGER intent_initial_status_clock AFTER INSERT ON submission_intents
 BEGIN UPDATE submission_intents SET state_changed_at_us=NEW.created_at_us WHERE intent_id=NEW.intent_id; END;
CREATE TRIGGER intent_status_clock AFTER UPDATE OF state_version ON submission_intents
 WHEN NEW.state_version<>OLD.state_version
 BEGIN UPDATE submission_intents SET state_changed_at_us=(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000) WHERE intent_id=NEW.intent_id; END;
CREATE INDEX status_owner_page ON submission_intents(user_id,created_at_us DESC,intent_id DESC);
CREATE INDEX status_binding_page ON submission_intents(user_id,binding_id,created_at_us DESC,intent_id DESC);
CREATE TABLE status_read_buckets (
 family TEXT NOT NULL CHECK(family IN ('installation','admin')),
 subject_id TEXT NOT NULL,
 tokens REAL NOT NULL CHECK(tokens>=0 AND tokens<=20),
 updated_at_us INTEGER NOT NULL,
 PRIMARY KEY(family,subject_id)
) STRICT;
CREATE TABLE status_read_events (
 event_id TEXT PRIMARY KEY,
 created_at_us INTEGER NOT NULL
) STRICT;
CREATE INDEX status_read_window ON status_read_events(created_at_us);
-- Initial gate observations provide a timestamp without exposing token state.
INSERT INTO flickr_write_gate_events(event_id,scope,scope_id,revision,reason)
 SELECT lower(hex(randomblob(16))),g.scope,g.scope_id,g.revision,'migration_snapshot'
 FROM flickr_write_gates g WHERE NOT EXISTS(SELECT 1 FROM flickr_write_gate_events e
 WHERE e.scope=g.scope AND e.scope_id=g.scope_id AND e.revision=g.revision);
CREATE TRIGGER write_gate_initial_observation AFTER INSERT ON flickr_write_gates
 BEGIN INSERT INTO flickr_write_gate_events(event_id,scope,scope_id,revision,reason)
 VALUES(lower(hex(randomblob(16))),NEW.scope,NEW.scope_id,NEW.revision,
 CASE WHEN NEW.enabled=1 THEN 'initially_enabled' ELSE 'initially_paused' END); END;
