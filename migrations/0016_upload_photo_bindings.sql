-- Append-only successful upload proof, correlated to the existing common identity.
-- No Flickr metadata, signed envelope, credentials, album or group state is retained.
CREATE TABLE upload_photo_binding_events (
 authorization_id TEXT PRIMARY KEY NOT NULL REFERENCES upload_authorizations(authorization_id) ON DELETE RESTRICT,
 binding_id TEXT NOT NULL REFERENCES photo_bindings(binding_id) ON DELETE RESTRICT,
 link_revision INTEGER NOT NULL CHECK(link_revision BETWEEN 1 AND 9007199254740991),
 verification_revision INTEGER NOT NULL CHECK(verification_revision BETWEEN 1 AND 9007199254740991),
 observed_public INTEGER NOT NULL CHECK(observed_public IN (0,1)),
 verified_at_us INTEGER NOT NULL
) STRICT;
CREATE TRIGGER upload_photo_binding_event_consistent BEFORE INSERT ON upload_photo_binding_events
 WHEN NOT EXISTS(SELECT 1 FROM upload_authorizations a JOIN photo_bindings b
   ON b.photo_id=a.photo_id AND b.user_id=a.user_id
   WHERE a.authorization_id=NEW.authorization_id AND b.binding_id=NEW.binding_id
     AND b.link_revision=NEW.link_revision AND b.verification_revision=NEW.verification_revision
     AND b.verified_at_us=NEW.verified_at_us)
 BEGIN SELECT RAISE(ABORT,'upload_photo_binding_event_inconsistent'); END;
CREATE TRIGGER upload_photo_binding_event_no_update BEFORE UPDATE ON upload_photo_binding_events
 BEGIN SELECT RAISE(ABORT,'upload_photo_binding_event_immutable'); END;
CREATE TRIGGER upload_photo_binding_event_no_delete BEFORE DELETE ON upload_photo_binding_events
 BEGIN SELECT RAISE(ABORT,'upload_photo_binding_event_immutable'); END;
CREATE TRIGGER upload_photo_binding_event_no_replace BEFORE INSERT ON upload_photo_binding_events
 WHEN EXISTS(SELECT 1 FROM upload_photo_binding_events WHERE authorization_id=NEW.authorization_id)
 BEGIN SELECT RAISE(ABORT,'upload_photo_binding_event_immutable'); END;
