-- Production dispatcher reservations and expanded retained result classifications.
-- Rebuild only the resolution relation; retain every historical row verbatim.
CREATE TABLE attempt_resolutions_v2 (
 attempt_id TEXT PRIMARY KEY REFERENCES submission_attempts(attempt_id) ON DELETE RESTRICT,
 outcome TEXT NOT NULL CHECK(outcome IN ('added','moderation_submitted','delivery_uncertain','retrying','throttled','needs_attention')),
 reason TEXT NOT NULL CHECK(length(reason) BETWEEN 1 AND 96),
 completed_at_us INTEGER NOT NULL DEFAULT((CAST(strftime('%s','now') AS INTEGER)*1000000 + CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000)),
 flickr_code INTEGER,
 observed_age_us INTEGER,
 CHECK(observed_age_us IS NULL OR observed_age_us>=0)
) STRICT;
INSERT INTO attempt_resolutions_v2(attempt_id,outcome,reason,completed_at_us)
 SELECT attempt_id,outcome,reason,completed_at_us FROM attempt_resolutions;
DROP TABLE attempt_resolutions;
ALTER TABLE attempt_resolutions_v2 RENAME TO attempt_resolutions;
CREATE TRIGGER attempt_resolutions_no_update BEFORE UPDATE ON attempt_resolutions
 BEGIN SELECT RAISE(ABORT,'attempt_evidence_immutable'); END;
CREATE TRIGGER attempt_resolutions_no_delete BEFORE DELETE ON attempt_resolutions
 BEGIN SELECT RAISE(ABORT,'attempt_evidence_immutable'); END;
CREATE TRIGGER attempt_resolutions_no_replace BEFORE INSERT ON attempt_resolutions
 WHEN EXISTS(SELECT 1 FROM attempt_resolutions WHERE attempt_id=NEW.attempt_id)
 BEGIN SELECT RAISE(ABORT,'attempt_evidence_immutable'); END;
CREATE TABLE flickr_rate_window (
 singleton INTEGER PRIMARY KEY CHECK(singleton=1),
 window_id TEXT NOT NULL UNIQUE,
 capacity INTEGER NOT NULL CHECK(capacity BETWEEN 3 AND 3600),
 window_ms INTEGER NOT NULL CHECK(window_ms BETWEEN 1000 AND 3600000),
 expires_at_us INTEGER NOT NULL,
 reserved_slots INTEGER NOT NULL DEFAULT 0 CHECK(reserved_slots>=0 AND reserved_slots<=capacity)
) STRICT;
CREATE TABLE flickr_rate_reservations (
 reservation_id TEXT PRIMARY KEY,
 attempt_id TEXT NOT NULL UNIQUE REFERENCES submission_attempts(attempt_id) ON DELETE RESTRICT,
 window_id TEXT NOT NULL,
 expires_at_us INTEGER NOT NULL,
 released INTEGER NOT NULL DEFAULT 0 CHECK(released IN (0,1)),
 consumed_slots INTEGER CHECK(consumed_slots BETWEEN 0 AND 3)
) STRICT;
CREATE TRIGGER rate_reservation_identity BEFORE UPDATE ON flickr_rate_reservations
 WHEN NEW.reservation_id<>OLD.reservation_id OR NEW.attempt_id<>OLD.attempt_id OR
 NEW.window_id<>OLD.window_id OR NEW.expires_at_us<>OLD.expires_at_us OR
 (OLD.released=1 AND (NEW.released<>1 OR NEW.consumed_slots IS NOT OLD.consumed_slots))
 BEGIN SELECT RAISE(ABORT,'rate_reservation_identity'); END;
CREATE TRIGGER rate_reservation_no_replace BEFORE INSERT ON flickr_rate_reservations
 WHEN EXISTS(SELECT 1 FROM flickr_rate_reservations WHERE reservation_id=NEW.reservation_id OR attempt_id=NEW.attempt_id)
 BEGIN SELECT RAISE(ABORT,'rate_reservation_identity'); END;
CREATE TABLE flickr_write_gate_events (
 event_id TEXT PRIMARY KEY,
 scope TEXT NOT NULL CHECK(scope IN ('deployment','user')),
 scope_id TEXT NOT NULL,
 revision INTEGER NOT NULL,
 reason TEXT NOT NULL,
 flickr_code INTEGER,
 attempt_id TEXT REFERENCES submission_attempts(attempt_id) ON DELETE RESTRICT,
 created_at_us INTEGER NOT NULL DEFAULT((CAST(strftime('%s','now') AS INTEGER)*1000000 + CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000))
) STRICT;
CREATE TRIGGER write_gate_event_no_update BEFORE UPDATE ON flickr_write_gate_events
 BEGIN SELECT RAISE(ABORT,'gate_event_immutable'); END;
CREATE TRIGGER write_gate_event_no_delete BEFORE DELETE ON flickr_write_gate_events
 BEGIN SELECT RAISE(ABORT,'gate_event_immutable'); END;
CREATE TRIGGER write_gate_event_no_replace BEFORE INSERT ON flickr_write_gate_events
 WHEN EXISTS(SELECT 1 FROM flickr_write_gate_events WHERE event_id=NEW.event_id)
 BEGIN SELECT RAISE(ABORT,'gate_event_immutable'); END;

-- Preserve a generic transition record for lifecycle/administrative changes too.
-- Dispatcher-specific evidence is inserted before UPDATE in the same transaction.
CREATE TRIGGER write_gate_transition AFTER UPDATE ON flickr_write_gates
 WHEN NEW.revision<>OLD.revision OR NEW.enabled<>OLD.enabled
 BEGIN
 INSERT INTO flickr_write_gate_events(event_id,scope,scope_id,revision,reason)
 SELECT lower(hex(randomblob(16))),NEW.scope,NEW.scope_id,NEW.revision,
   CASE WHEN NEW.enabled=1 THEN 'gate_enabled' ELSE 'gate_paused' END
 WHERE NOT EXISTS(SELECT 1 FROM flickr_write_gate_events
   WHERE scope=NEW.scope AND scope_id=NEW.scope_id AND revision=NEW.revision);
 END;
