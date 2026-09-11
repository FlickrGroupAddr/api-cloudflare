-- Scoped hosted foundation: installation reads and protected-history probes.
-- Database time is formatted to six digits but currently sampled at SQLite millisecond resolution.
CREATE TABLE fga_users (
 user_id TEXT PRIMARY KEY NOT NULL
) STRICT;
CREATE TABLE installations (
 installation_id TEXT PRIMARY KEY NOT NULL,
 user_id TEXT NOT NULL REFERENCES fga_users(user_id) ON DELETE RESTRICT,
 credential_class TEXT NOT NULL CHECK(credential_class='lrc_plugin'),
 label TEXT NOT NULL DEFAULT '',
 state TEXT NOT NULL CHECK(state IN ('active','revoked')),
 revision INTEGER NOT NULL CHECK(revision BETWEEN 1 AND 9007199254740991),
 current_version_id TEXT,
 pending_version_id TEXT,
 created_at_utc TEXT NOT NULL DEFAULT(strftime('%Y-%m-%dT%H:%M:%f','now') || '000Z'),
 revoked_at_utc TEXT,
 current_kind TEXT GENERATED ALWAYS AS ('current') VIRTUAL,
 pending_kind TEXT GENERATED ALWAYS AS ('pending_rotation') VIRTUAL,
 UNIQUE(installation_id,state),
 UNIQUE(installation_id,current_version_id),
 UNIQUE(installation_id,pending_version_id),
 CHECK((state='active' AND current_version_id IS NOT NULL) OR
       (state='revoked' AND current_version_id IS NULL AND pending_version_id IS NULL)),
 FOREIGN KEY(installation_id,current_version_id,current_kind)
   REFERENCES installation_credential_versions(installation_id,version_id,state)
   DEFERRABLE INITIALLY DEFERRED,
 FOREIGN KEY(installation_id,pending_version_id,pending_kind)
   REFERENCES installation_credential_versions(installation_id,version_id,state)
   DEFERRABLE INITIALLY DEFERRED
) STRICT;
CREATE TABLE installation_credential_versions (
 version_id TEXT PRIMARY KEY NOT NULL,
 installation_id TEXT NOT NULL REFERENCES installations(installation_id) ON DELETE RESTRICT
   DEFERRABLE INITIALLY DEFERRED,
 credential_digest TEXT NOT NULL UNIQUE CHECK(length(credential_digest)=64 AND credential_digest NOT GLOB '*[^0-9a-f]*'),
 state TEXT NOT NULL CHECK(state IN ('current','pending_rotation','replaced','revoked','expired_unactivated')),
 ordinal INTEGER NOT NULL CHECK(ordinal>0),
 expires_at_us INTEGER,
 created_at_utc TEXT NOT NULL DEFAULT(strftime('%Y-%m-%dT%H:%M:%f','now') || '000Z'),
 current_link TEXT GENERATED ALWAYS AS (CASE WHEN state='current' THEN version_id END) VIRTUAL,
 pending_link TEXT GENERATED ALWAYS AS (CASE WHEN state='pending_rotation' THEN version_id END) VIRTUAL,
 active_parent TEXT GENERATED ALWAYS AS (CASE WHEN state IN ('current','pending_rotation') THEN 'active' END) VIRTUAL,
 CHECK(state<>'current' OR expires_at_us IS NULL),
 CHECK(state<>'pending_rotation' OR expires_at_us IS NOT NULL),
 UNIQUE(installation_id,version_id,state),
 UNIQUE(installation_id,ordinal),
 FOREIGN KEY(installation_id,current_link) REFERENCES installations(installation_id,current_version_id)
   DEFERRABLE INITIALLY DEFERRED,
 FOREIGN KEY(installation_id,pending_link) REFERENCES installations(installation_id,pending_version_id)
   DEFERRABLE INITIALLY DEFERRED,
 FOREIGN KEY(installation_id,active_parent) REFERENCES installations(installation_id,state)
   DEFERRABLE INITIALLY DEFERRED
) STRICT;
CREATE UNIQUE INDEX one_current ON installation_credential_versions(installation_id) WHERE state='current';
CREATE UNIQUE INDEX one_pending ON installation_credential_versions(installation_id) WHERE state='pending_rotation';
CREATE TRIGGER installation_identity_immutable BEFORE UPDATE ON installations
 WHEN NEW.installation_id<>OLD.installation_id OR NEW.user_id<>OLD.user_id OR NEW.credential_class<>OLD.credential_class
 BEGIN SELECT RAISE(ABORT,'installation_identity_immutable'); END;
CREATE TRIGGER installation_revision_guard BEFORE UPDATE ON installations
 WHEN NEW.revision<OLD.revision OR
 ((NEW.state<>OLD.state OR NEW.current_version_id IS NOT OLD.current_version_id OR NEW.pending_version_id IS NOT OLD.pending_version_id)
  AND NEW.revision<>OLD.revision+1)
 BEGIN SELECT RAISE(ABORT,'installation_revision_guard'); END;
CREATE TRIGGER version_identity_immutable BEFORE UPDATE ON installation_credential_versions
 WHEN NEW.version_id<>OLD.version_id OR NEW.installation_id<>OLD.installation_id OR
      NEW.credential_digest<>OLD.credential_digest OR NEW.ordinal<>OLD.ordinal
 BEGIN SELECT RAISE(ABORT,'version_identity_immutable'); END;
CREATE TRIGGER version_state_transition BEFORE UPDATE OF state ON installation_credential_versions
 WHEN NEW.state<>OLD.state AND NOT (
  (OLD.state='current' AND NEW.state IN ('replaced','revoked')) OR
  (OLD.state='pending_rotation' AND NEW.state IN ('current','revoked','expired_unactivated')))
 BEGIN SELECT RAISE(ABORT,'version_state_transition'); END;
CREATE TRIGGER version_ordinal_guard BEFORE INSERT ON installation_credential_versions
 WHEN NEW.ordinal<=COALESCE((SELECT MAX(ordinal) FROM installation_credential_versions WHERE installation_id=NEW.installation_id),0)
 BEGIN SELECT RAISE(ABORT,'version_ordinal_guard'); END;
CREATE TABLE submission_blocks (
 photo_id TEXT NOT NULL, group_id TEXT NOT NULL,
 first_reason TEXT NOT NULL CHECK(first_reason IN ('flickr_code_6','flickr_code_7','delivery_uncertain')),
 source_attempt_id TEXT NOT NULL,
 created_at_utc TEXT NOT NULL DEFAULT(strftime('%Y-%m-%dT%H:%M:%f','now') || '000Z'),
 PRIMARY KEY(photo_id,group_id)
) STRICT;
CREATE TRIGGER block_no_update BEFORE UPDATE ON submission_blocks BEGIN SELECT RAISE(ABORT,'block_immutable'); END;
CREATE TRIGGER block_no_delete BEFORE DELETE ON submission_blocks BEGIN SELECT RAISE(ABORT,'block_immutable'); END;
CREATE TRIGGER block_no_replace BEFORE INSERT ON submission_blocks
 WHEN EXISTS(SELECT 1 FROM submission_blocks WHERE photo_id=NEW.photo_id AND group_id=NEW.group_id)
 BEGIN SELECT RAISE(ABORT,'block_immutable'); END;
CREATE TABLE audit_events (
 event_id TEXT PRIMARY KEY NOT NULL,
 user_id TEXT REFERENCES fga_users(user_id) ON DELETE RESTRICT,
 action TEXT NOT NULL,
 request_correlation_id TEXT NOT NULL,
 session_correlation_id TEXT,
 outcome TEXT NOT NULL CHECK(outcome IN ('succeeded','failed')),
 reason TEXT NOT NULL,
 target_id TEXT,
 created_at_utc TEXT NOT NULL DEFAULT(strftime('%Y-%m-%dT%H:%M:%f','now') || '000Z')
) STRICT;
CREATE TRIGGER audit_no_update BEFORE UPDATE ON audit_events BEGIN SELECT RAISE(ABORT,'audit_immutable'); END;
CREATE TRIGGER audit_no_delete BEFORE DELETE ON audit_events BEGIN SELECT RAISE(ABORT,'audit_immutable'); END;
CREATE TRIGGER audit_no_replace BEFORE INSERT ON audit_events
 WHEN EXISTS(SELECT 1 FROM audit_events WHERE event_id=NEW.event_id)
 BEGIN SELECT RAISE(ABORT,'audit_immutable'); END;

CREATE TRIGGER installation_no_delete BEFORE DELETE ON installations BEGIN SELECT RAISE(ABORT,'installation_history_retained'); END;
CREATE TRIGGER installation_no_replace BEFORE INSERT ON installations
 WHEN EXISTS(SELECT 1 FROM installations WHERE installation_id=NEW.installation_id)
 BEGIN SELECT RAISE(ABORT,'installation_history_retained'); END;
CREATE TRIGGER version_no_delete BEFORE DELETE ON installation_credential_versions BEGIN SELECT RAISE(ABORT,'version_history_retained'); END;
CREATE TRIGGER version_no_replace BEFORE INSERT ON installation_credential_versions
 WHEN EXISTS(SELECT 1 FROM installation_credential_versions WHERE version_id=NEW.version_id OR credential_digest=NEW.credential_digest)
 BEGIN SELECT RAISE(ABORT,'version_history_retained'); END;

CREATE TRIGGER installation_creation_immutable BEFORE UPDATE OF created_at_utc ON installations
 WHEN NEW.created_at_utc<>OLD.created_at_utc
 BEGIN SELECT RAISE(ABORT,'installation_creation_immutable'); END;
CREATE TRIGGER installation_revocation_terminal BEFORE UPDATE OF state ON installations
 WHEN OLD.state='revoked' AND NEW.state<>'revoked'
 BEGIN SELECT RAISE(ABORT,'installation_revocation_terminal'); END;
CREATE TRIGGER version_creation_immutable BEFORE UPDATE OF created_at_utc ON installation_credential_versions
 WHEN NEW.created_at_utc<>OLD.created_at_utc
 BEGIN SELECT RAISE(ABORT,'version_creation_immutable'); END;
CREATE TRIGGER version_expiry_immutable BEFORE UPDATE OF expires_at_us ON installation_credential_versions
 WHEN NEW.expires_at_us IS NOT OLD.expires_at_us AND NOT
 (OLD.state='pending_rotation' AND NEW.state='current' AND NEW.expires_at_us IS NULL)
 BEGIN SELECT RAISE(ABORT,'version_expiry_immutable'); END;
