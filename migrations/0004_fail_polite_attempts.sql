-- Candidate fail-polite durable facts. D1 is the sole authority for every row.
CREATE TABLE submission_attempts (
 attempt_id TEXT PRIMARY KEY NOT NULL,
 intent_id TEXT NOT NULL REFERENCES submission_intents(intent_id) ON DELETE RESTRICT,
 ordinal INTEGER NOT NULL CHECK(ordinal>0),
 lease_id TEXT NOT NULL,
 lease_generation INTEGER NOT NULL CHECK(lease_generation>0),
 deployment_revision INTEGER NOT NULL,
 user_revision INTEGER NOT NULL,
 link_revision INTEGER NOT NULL,
 created_at_us INTEGER NOT NULL DEFAULT((CAST(strftime('%s','now') AS INTEGER)*1000000 + CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000)),
 UNIQUE(intent_id,ordinal)
) STRICT;
CREATE TABLE attempt_membership (
 attempt_id TEXT PRIMARY KEY REFERENCES submission_attempts(attempt_id) ON DELETE RESTRICT,
 target_absent INTEGER NOT NULL CHECK(target_absent IN (0,1)),
 observed_at_us INTEGER NOT NULL DEFAULT((CAST(strftime('%s','now') AS INTEGER)*1000000 + CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000))
) STRICT;
CREATE TABLE attempt_preflights (
 attempt_id TEXT PRIMARY KEY REFERENCES submission_attempts(attempt_id) ON DELETE RESTRICT,
 moderated INTEGER NOT NULL CHECK(moderated IN (0,1)),
 observed_at_us INTEGER NOT NULL DEFAULT((CAST(strftime('%s','now') AS INTEGER)*1000000 + CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000))
) STRICT;
CREATE TABLE attempt_dispatches (
 attempt_id TEXT PRIMARY KEY REFERENCES submission_attempts(attempt_id) ON DELETE RESTRICT,
 started_at_us INTEGER NOT NULL DEFAULT((CAST(strftime('%s','now') AS INTEGER)*1000000 + CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000))
) STRICT;
CREATE TABLE attempt_resolutions (
 attempt_id TEXT PRIMARY KEY REFERENCES submission_attempts(attempt_id) ON DELETE RESTRICT,
 outcome TEXT NOT NULL CHECK(outcome IN ('added','moderation_submitted','delivery_uncertain','retrying')),
 reason TEXT NOT NULL CHECK(reason IN ('pre_add_membership_observation','flickr_added','flickr_code_3','flickr_code_6','flickr_code_7','unknown_code','unresolved_dispatch','safe_read_unavailable','flickr_code_105','flickr_code_106','abandoned_before_dispatch','not_dispatched_preflight_expired')),
 completed_at_us INTEGER NOT NULL DEFAULT((CAST(strftime('%s','now') AS INTEGER)*1000000 + CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000))
) STRICT;
CREATE TRIGGER submission_attempts_no_update BEFORE UPDATE ON submission_attempts
 BEGIN SELECT RAISE(ABORT,'attempt_evidence_immutable'); END;
CREATE TRIGGER submission_attempts_no_delete BEFORE DELETE ON submission_attempts
 BEGIN SELECT RAISE(ABORT,'attempt_evidence_immutable'); END;
CREATE TRIGGER submission_attempts_no_replace BEFORE INSERT ON submission_attempts
 WHEN EXISTS(SELECT 1 FROM submission_attempts WHERE attempt_id=NEW.attempt_id)
 BEGIN SELECT RAISE(ABORT,'attempt_evidence_immutable'); END;
CREATE TRIGGER attempt_membership_no_update BEFORE UPDATE ON attempt_membership
 BEGIN SELECT RAISE(ABORT,'attempt_evidence_immutable'); END;
CREATE TRIGGER attempt_membership_no_delete BEFORE DELETE ON attempt_membership
 BEGIN SELECT RAISE(ABORT,'attempt_evidence_immutable'); END;
CREATE TRIGGER attempt_membership_no_replace BEFORE INSERT ON attempt_membership
 WHEN EXISTS(SELECT 1 FROM attempt_membership WHERE attempt_id=NEW.attempt_id)
 BEGIN SELECT RAISE(ABORT,'attempt_evidence_immutable'); END;
CREATE TRIGGER attempt_preflights_no_update BEFORE UPDATE ON attempt_preflights
 BEGIN SELECT RAISE(ABORT,'attempt_evidence_immutable'); END;
CREATE TRIGGER attempt_preflights_no_delete BEFORE DELETE ON attempt_preflights
 BEGIN SELECT RAISE(ABORT,'attempt_evidence_immutable'); END;
CREATE TRIGGER attempt_preflights_no_replace BEFORE INSERT ON attempt_preflights
 WHEN EXISTS(SELECT 1 FROM attempt_preflights WHERE attempt_id=NEW.attempt_id)
 BEGIN SELECT RAISE(ABORT,'attempt_evidence_immutable'); END;
CREATE TRIGGER attempt_dispatches_no_update BEFORE UPDATE ON attempt_dispatches
 BEGIN SELECT RAISE(ABORT,'attempt_evidence_immutable'); END;
CREATE TRIGGER attempt_dispatches_no_delete BEFORE DELETE ON attempt_dispatches
 BEGIN SELECT RAISE(ABORT,'attempt_evidence_immutable'); END;
CREATE TRIGGER attempt_dispatches_no_replace BEFORE INSERT ON attempt_dispatches
 WHEN EXISTS(SELECT 1 FROM attempt_dispatches WHERE attempt_id=NEW.attempt_id)
 BEGIN SELECT RAISE(ABORT,'attempt_evidence_immutable'); END;
CREATE TRIGGER attempt_resolutions_no_update BEFORE UPDATE ON attempt_resolutions
 BEGIN SELECT RAISE(ABORT,'attempt_evidence_immutable'); END;
CREATE TRIGGER attempt_resolutions_no_delete BEFORE DELETE ON attempt_resolutions
 BEGIN SELECT RAISE(ABORT,'attempt_evidence_immutable'); END;
CREATE TRIGGER attempt_resolutions_no_replace BEFORE INSERT ON attempt_resolutions
 WHEN EXISTS(SELECT 1 FROM attempt_resolutions WHERE attempt_id=NEW.attempt_id)
 BEGIN SELECT RAISE(ABORT,'attempt_evidence_immutable'); END;
