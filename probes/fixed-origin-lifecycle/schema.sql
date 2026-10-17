-- Dedicated disposable synthetic D1 only. Never a production migration.
CREATE TABLE qualification_run (
  singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
  run TEXT NOT NULL CHECK(length(run) = 32 AND run NOT GLOB '*[^0-9a-f]*'),
  starts_at INTEGER NOT NULL CHECK(starts_at >= 0),
  expires_at INTEGER NOT NULL CHECK(expires_at = starts_at + 1200000),
  enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0,1)),
  fga_count INTEGER NOT NULL DEFAULT 0 CHECK(fga_count BETWEEN 0 AND 96),
  receiver_count INTEGER NOT NULL DEFAULT 0 CHECK(receiver_count BETWEEN 0 AND 16),
  arrivals INTEGER NOT NULL DEFAULT 0 CHECK(arrivals BETWEEN 0 AND receiver_count),
  authorization_present INTEGER NOT NULL DEFAULT 0 CHECK(authorization_present IN (0,1)),
  canary_match INTEGER NOT NULL DEFAULT 0 CHECK(canary_match IN (0,1))
) STRICT;
-- REPLACE implicitly deletes without firing DELETE triggers under SQLite defaults.
-- Refuse before conflict handling, independently of recursive_triggers.
CREATE TRIGGER qualification_no_replace BEFORE INSERT ON qualification_run
WHEN EXISTS(SELECT 1 FROM qualification_run WHERE singleton=1)
BEGIN SELECT RAISE(ABORT, 'qualification_no_replace'); END;
CREATE TRIGGER qualification_no_reenable BEFORE UPDATE ON qualification_run
WHEN NEW.enabled > OLD.enabled OR NEW.fga_count < OLD.fga_count
 OR NEW.receiver_count < OLD.receiver_count OR NEW.arrivals < OLD.arrivals
 OR NEW.authorization_present < OLD.authorization_present OR NEW.canary_match < OLD.canary_match
 OR NEW.run <> OLD.run OR NEW.starts_at <> OLD.starts_at OR NEW.expires_at <> OLD.expires_at
BEGIN SELECT RAISE(ABORT, 'qualification_monotonic'); END;
CREATE TRIGGER qualification_no_delete BEFORE DELETE ON qualification_run
BEGIN SELECT RAISE(ABORT, 'qualification_no_delete'); END;
