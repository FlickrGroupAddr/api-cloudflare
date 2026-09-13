-- Metadata only; credential values remain one-time response data.
ALTER TABLE installations ADD COLUMN rotation_due_at_utc TEXT;
ALTER TABLE installations ADD COLUMN last_authenticated_at_utc TEXT;
UPDATE installations SET rotation_due_at_utc=strftime('%Y-%m-%dT%H:%M:%f',created_at_utc,'+1 year')||'000Z';
CREATE TABLE installation_lifecycle_events (
 event_id TEXT PRIMARY KEY,
 installation_id TEXT NOT NULL REFERENCES installations(installation_id) ON DELETE RESTRICT,
 version_id TEXT REFERENCES installation_credential_versions(version_id) ON DELETE RESTRICT,
 from_revision INTEGER NOT NULL,
 to_revision INTEGER NOT NULL,
 kind TEXT NOT NULL CHECK(kind IN ('created','rotation_created','rotation_completed','rotation_cancelled','rotation_expired','revoked')),
 created_at_utc TEXT NOT NULL DEFAULT(strftime('%Y-%m-%dT%H:%M:%f','now')||'000Z'),
 UNIQUE(installation_id,from_revision,kind)
) STRICT;
CREATE TRIGGER installation_lifecycle_no_update BEFORE UPDATE ON installation_lifecycle_events
 BEGIN SELECT RAISE(ABORT,'credential_history_immutable'); END;
CREATE TRIGGER installation_lifecycle_no_delete BEFORE DELETE ON installation_lifecycle_events
 BEGIN SELECT RAISE(ABORT,'credential_history_immutable'); END;
CREATE TRIGGER installation_lifecycle_no_replace BEFORE INSERT ON installation_lifecycle_events
 WHEN EXISTS(SELECT 1 FROM installation_lifecycle_events WHERE event_id=NEW.event_id)
 BEGIN SELECT RAISE(ABORT,'credential_history_immutable'); END;
