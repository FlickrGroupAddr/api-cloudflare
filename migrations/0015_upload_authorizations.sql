-- Durable correlation only. Never store an OAuth envelope, URL, or upload metadata.
CREATE TABLE upload_authorizations (
 authorization_id TEXT PRIMARY KEY NOT NULL,
 installation_id TEXT NOT NULL REFERENCES installations(installation_id) ON DELETE RESTRICT,
 user_id TEXT NOT NULL REFERENCES fga_users(user_id) ON DELETE RESTRICT,
 issued_at_us INTEGER NOT NULL,
 photo_id TEXT,
 CHECK(length(authorization_id) BETWEEN 1 AND 128),
 CHECK(photo_id IS NULL OR length(photo_id) BETWEEN 1 AND 128)
) STRICT;
CREATE TRIGGER upload_authorization_initial_owner BEFORE INSERT ON upload_authorizations
 WHEN NEW.photo_id IS NOT NULL OR NOT EXISTS(SELECT 1 FROM installations i
   WHERE i.installation_id=NEW.installation_id AND i.user_id=NEW.user_id)
 BEGIN SELECT RAISE(ABORT,'upload_authorization_initial_owner'); END;
CREATE TRIGGER upload_authorization_identity BEFORE UPDATE ON upload_authorizations
 WHEN NEW.authorization_id<>OLD.authorization_id OR NEW.installation_id<>OLD.installation_id
   OR NEW.user_id<>OLD.user_id OR NEW.issued_at_us<>OLD.issued_at_us
   OR (OLD.photo_id IS NOT NULL AND NEW.photo_id IS NOT OLD.photo_id)
 BEGIN SELECT RAISE(ABORT,'upload_authorization_identity'); END;
CREATE TRIGGER upload_authorization_retain BEFORE DELETE ON upload_authorizations
 BEGIN SELECT RAISE(ABORT,'upload_authorization_retained'); END;
CREATE TRIGGER upload_authorization_no_replace BEFORE INSERT ON upload_authorizations
 WHEN EXISTS(SELECT 1 FROM upload_authorizations WHERE authorization_id=NEW.authorization_id)
 BEGIN SELECT RAISE(ABORT,'upload_authorization_retained'); END;
