-- Native consumer metadata only. Lifecycle management remains gated on its
-- authenticated integration and reviewed writer identity; no credential bytes.
CREATE TABLE flickr_native_credentials (
 user_id TEXT PRIMARY KEY REFERENCES flickr_links(user_id) ON DELETE RESTRICT,
 active_generation TEXT NOT NULL CHECK(length(active_generation) BETWEEN 1 AND 128),
 link_revision INTEGER NOT NULL CHECK(link_revision>0),
 verified_owner_nsid TEXT NOT NULL,
 verified_permission TEXT NOT NULL CHECK(verified_permission IN ('write','delete')),
 operation_id TEXT,
 UNIQUE(user_id,active_generation,link_revision)
) STRICT;
CREATE TABLE photo_binding_events (
 event_id TEXT PRIMARY KEY NOT NULL,
 binding_id TEXT NOT NULL REFERENCES photo_bindings(binding_id) ON DELETE RESTRICT,
 verification_revision INTEGER NOT NULL CHECK(verification_revision>0),
 kind TEXT NOT NULL CHECK(kind='existing_public_verified'),
 created_at_us INTEGER NOT NULL DEFAULT((CAST(strftime('%s','now') AS INTEGER)*1000000 + CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000))
) STRICT;
CREATE TRIGGER photo_binding_event_no_update BEFORE UPDATE ON photo_binding_events BEGIN SELECT RAISE(ABORT,'binding_event_immutable'); END;
CREATE TRIGGER photo_binding_event_no_delete BEFORE DELETE ON photo_binding_events BEGIN SELECT RAISE(ABORT,'binding_event_immutable'); END;
CREATE TRIGGER photo_binding_event_no_replace BEFORE INSERT ON photo_binding_events
 WHEN EXISTS(SELECT 1 FROM photo_binding_events WHERE event_id=NEW.event_id)
 BEGIN SELECT RAISE(ABORT,'binding_event_immutable'); END;

CREATE TRIGGER flickr_link_identity_immutable BEFORE UPDATE ON flickr_links
 WHEN NEW.user_id<>OLD.user_id OR NEW.owner_nsid<>OLD.owner_nsid OR NEW.link_revision<OLD.link_revision
 BEGIN SELECT RAISE(ABORT,'flickr_link_identity_immutable'); END;
CREATE TRIGGER flickr_link_no_delete BEFORE DELETE ON flickr_links
 BEGIN SELECT RAISE(ABORT,'flickr_link_retained'); END;
CREATE TRIGGER flickr_link_no_replace BEFORE INSERT ON flickr_links
 WHEN EXISTS(SELECT 1 FROM flickr_links WHERE user_id=NEW.user_id)
 BEGIN SELECT RAISE(ABORT,'flickr_link_retained'); END;
