-- Admission only. These retained rows do not authorize a Flickr dispatch.
CREATE TABLE album_bindings (
 binding_id TEXT PRIMARY KEY NOT NULL CHECK(length(binding_id)=36 AND binding_id=lower(binding_id)
  AND binding_id GLOB '????????-????-4???-[89ab]???-????????????'
  AND length(replace(binding_id,'-',''))=32 AND replace(binding_id,'-','') NOT GLOB '*[^0-9a-f]*'),
 user_id TEXT NOT NULL REFERENCES fga_users(user_id) ON DELETE RESTRICT,
 service_id TEXT NOT NULL REFERENCES publish_service_identities(service_id) ON DELETE RESTRICT,
 local_collection_id TEXT NOT NULL CHECK(length(local_collection_id) BETWEEN 1 AND 128
  AND substr(local_collection_id,1,1) GLOB '[A-Za-z0-9]' AND local_collection_id NOT GLOB '*[^A-Za-z0-9@._:-]*'),
 link_revision INTEGER NOT NULL CHECK(link_revision BETWEEN 1 AND 9007199254740991),
 owner_nsid TEXT NOT NULL CHECK(length(owner_nsid) BETWEEN 1 AND 128),
 first_photo_binding_id TEXT NOT NULL,
 first_photo_id TEXT NOT NULL CHECK(first_photo_id<>'0'),
 first_obligation_id TEXT NOT NULL UNIQUE,
 desired_title TEXT NOT NULL CHECK(length(desired_title) BETWEEN 1 AND 1000 AND instr(desired_title,char(0))=0),
 title_revision INTEGER NOT NULL DEFAULT 1 CHECK(title_revision BETWEEN 1 AND 9007199254740991),
 binding_revision INTEGER NOT NULL DEFAULT 1 CHECK(binding_revision BETWEEN 1 AND 9007199254740991),
 flickr_photoset_id TEXT CHECK(flickr_photoset_id IS NULL OR (length(flickr_photoset_id) BETWEEN 1 AND 128
  AND substr(flickr_photoset_id,1,1) GLOB '[A-Za-z0-9]' AND flickr_photoset_id NOT GLOB '*[^A-Za-z0-9@._:-]*')),
 state TEXT NOT NULL DEFAULT 'materialization_pending'
  CHECK(state IN ('materialization_pending','local_collection_removed_remote_preserved')),
 UNIQUE(user_id,service_id,local_collection_id),
 UNIQUE(owner_nsid,flickr_photoset_id),
 UNIQUE(binding_id,user_id),
 FOREIGN KEY(first_photo_binding_id,user_id,first_photo_id)
  REFERENCES photo_bindings(binding_id,user_id,photo_id) ON DELETE RESTRICT,
 FOREIGN KEY(first_obligation_id,binding_id,first_photo_binding_id,first_photo_id)
  REFERENCES album_photo_obligations(obligation_id,album_binding_id,photo_binding_id,photo_id)
  DEFERRABLE INITIALLY DEFERRED
) STRICT;

-- Only the primary receipt is admitted in this migration. General association
-- admission and obligation transitions belong to #0110 and later worker work.
CREATE TABLE album_photo_obligations (
 obligation_id TEXT PRIMARY KEY NOT NULL CHECK(length(obligation_id)=36 AND obligation_id=lower(obligation_id)
  AND obligation_id GLOB '????????-????-4???-[89ab]???-????????????'
  AND length(replace(obligation_id,'-',''))=32 AND replace(obligation_id,'-','') NOT GLOB '*[^0-9a-f]*'),
 album_binding_id TEXT NOT NULL REFERENCES album_bindings(binding_id) ON DELETE RESTRICT,
 photo_binding_id TEXT NOT NULL REFERENCES photo_bindings(binding_id) ON DELETE RESTRICT,
 photo_id TEXT NOT NULL,
 obligation_revision INTEGER NOT NULL DEFAULT 1 CHECK(obligation_revision=1),
 state TEXT NOT NULL DEFAULT 'materialization_pending' CHECK(state='materialization_pending'),
 UNIQUE(album_binding_id,photo_binding_id),
 UNIQUE(obligation_id,album_binding_id,photo_binding_id,photo_id)
) STRICT;

CREATE TABLE album_binding_events (
 binding_id TEXT NOT NULL REFERENCES album_bindings(binding_id) ON DELETE RESTRICT,
 binding_revision INTEGER NOT NULL CHECK(binding_revision BETWEEN 1 AND 9007199254740991),
 kind TEXT NOT NULL CHECK(kind IN ('binding_created','binding_changed')),
 title_revision INTEGER NOT NULL,
 desired_title TEXT NOT NULL,
 flickr_photoset_id TEXT,
 state TEXT NOT NULL,
 created_at_us INTEGER NOT NULL DEFAULT(CAST(strftime('%s','now') AS INTEGER)*1000000
  + CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000),
 PRIMARY KEY(binding_id,binding_revision)
) STRICT;

CREATE TRIGGER album_binding_initial BEFORE INSERT ON album_bindings
 WHEN NEW.binding_revision<>1 OR NEW.title_revision<>1 OR NEW.flickr_photoset_id IS NOT NULL
  OR NEW.state<>'materialization_pending'
  OR NOT EXISTS(SELECT 1 FROM publish_service_identities s JOIN photo_bindings p ON p.user_id=s.user_id
   WHERE s.service_id=NEW.service_id AND s.user_id=NEW.user_id AND s.owner_nsid=NEW.owner_nsid
    AND s.link_revision=NEW.link_revision AND p.binding_id=NEW.first_photo_binding_id
    AND p.photo_id=NEW.first_photo_id AND p.owner_nsid=s.owner_nsid AND p.link_revision=s.link_revision
    AND p.photo_id<>'0' AND p.binding_id<>'0' AND p.verification_revision BETWEEN 1 AND 9007199254740991
    AND p.verified_at_us>=0 AND p.verified_at_us<=CAST(strftime('%s','now') AS INTEGER)*1000000
      + CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000
    AND (EXISTS(SELECT 1 FROM photo_binding_events e WHERE e.binding_id=p.binding_id
      AND e.verification_revision=p.verification_revision AND e.kind='existing_public_verified')
     OR EXISTS(SELECT 1 FROM upload_photo_binding_events e WHERE e.binding_id=p.binding_id
      AND e.verification_revision=p.verification_revision AND e.link_revision=p.link_revision
      AND e.verified_at_us=p.verified_at_us)))
 BEGIN SELECT RAISE(ABORT,'album_binding_initial'); END;
CREATE TRIGGER album_binding_identity BEFORE UPDATE ON album_bindings
 WHEN NEW.binding_id<>OLD.binding_id OR NEW.user_id<>OLD.user_id OR NEW.service_id<>OLD.service_id
  OR NEW.local_collection_id<>OLD.local_collection_id OR NEW.link_revision<>OLD.link_revision
  OR NEW.owner_nsid<>OLD.owner_nsid OR NEW.first_photo_binding_id<>OLD.first_photo_binding_id
  OR NEW.first_photo_id<>OLD.first_photo_id OR NEW.first_obligation_id<>OLD.first_obligation_id
  OR (OLD.flickr_photoset_id IS NOT NULL AND NEW.flickr_photoset_id IS NOT OLD.flickr_photoset_id)
 BEGIN SELECT RAISE(ABORT,'album_binding_identity'); END;
CREATE TRIGGER album_binding_revision BEFORE UPDATE ON album_bindings
 WHEN NEW.binding_revision<>OLD.binding_revision+
   (NEW.desired_title<>OLD.desired_title OR NEW.flickr_photoset_id IS NOT OLD.flickr_photoset_id OR NEW.state<>OLD.state)
  OR NEW.title_revision<>OLD.title_revision+(NEW.desired_title<>OLD.desired_title)
  OR (OLD.state='local_collection_removed_remote_preserved'
    AND (NEW.state<>OLD.state OR NEW.desired_title<>OLD.desired_title))
 BEGIN SELECT RAISE(ABORT,'album_binding_revision'); END;
CREATE TRIGGER album_binding_no_delete BEFORE DELETE ON album_bindings
 BEGIN SELECT RAISE(ABORT,'album_binding_retained'); END;
CREATE TRIGGER album_binding_no_replace BEFORE INSERT ON album_bindings
 WHEN EXISTS(SELECT 1 FROM album_bindings WHERE binding_id=NEW.binding_id
   OR (user_id=NEW.user_id AND service_id=NEW.service_id AND local_collection_id=NEW.local_collection_id)
   OR (owner_nsid=NEW.owner_nsid AND flickr_photoset_id=NEW.flickr_photoset_id))
 BEGIN SELECT RAISE(ABORT,'album_binding_retained'); END;

CREATE TRIGGER album_obligation_initial BEFORE INSERT ON album_photo_obligations
 WHEN NOT EXISTS(SELECT 1 FROM album_bindings b WHERE b.binding_id=NEW.album_binding_id
  AND b.first_obligation_id=NEW.obligation_id AND b.first_photo_binding_id=NEW.photo_binding_id
  AND b.first_photo_id=NEW.photo_id AND b.state='materialization_pending')
 BEGIN SELECT RAISE(ABORT,'album_obligation_initial'); END;
CREATE TRIGGER album_obligation_no_update BEFORE UPDATE ON album_photo_obligations
 BEGIN SELECT RAISE(ABORT,'album_obligation_immutable'); END;
CREATE TRIGGER album_obligation_no_delete BEFORE DELETE ON album_photo_obligations
 BEGIN SELECT RAISE(ABORT,'album_obligation_retained'); END;
CREATE TRIGGER album_obligation_no_replace BEFORE INSERT ON album_photo_obligations
 WHEN EXISTS(SELECT 1 FROM album_photo_obligations WHERE obligation_id=NEW.obligation_id
  OR (album_binding_id=NEW.album_binding_id AND photo_binding_id=NEW.photo_binding_id))
 BEGIN SELECT RAISE(ABORT,'album_obligation_retained'); END;

CREATE TRIGGER album_event_consistent BEFORE INSERT ON album_binding_events
 WHEN NOT EXISTS(SELECT 1 FROM album_bindings b WHERE b.binding_id=NEW.binding_id
  AND b.binding_revision=NEW.binding_revision AND b.title_revision=NEW.title_revision
  AND b.desired_title=NEW.desired_title AND b.flickr_photoset_id IS NEW.flickr_photoset_id AND b.state=NEW.state)
  OR (NEW.binding_revision=1 AND NEW.kind<>'binding_created')
  OR (NEW.binding_revision>1 AND NEW.kind<>'binding_changed')
 BEGIN SELECT RAISE(ABORT,'album_event_inconsistent'); END;
CREATE TRIGGER album_event_no_update BEFORE UPDATE ON album_binding_events
 BEGIN SELECT RAISE(ABORT,'album_event_immutable'); END;
CREATE TRIGGER album_event_no_delete BEFORE DELETE ON album_binding_events
 BEGIN SELECT RAISE(ABORT,'album_event_retained'); END;
CREATE TRIGGER album_event_no_replace BEFORE INSERT ON album_binding_events
 WHEN EXISTS(SELECT 1 FROM album_binding_events WHERE binding_id=NEW.binding_id AND binding_revision=NEW.binding_revision)
 BEGIN SELECT RAISE(ABORT,'album_event_retained'); END;

-- Both dependent facts are part of the binding INSERT, including on failure.
CREATE TRIGGER album_binding_created AFTER INSERT ON album_bindings
 BEGIN
  INSERT INTO album_photo_obligations(obligation_id,album_binding_id,photo_binding_id,photo_id)
   VALUES(NEW.first_obligation_id,NEW.binding_id,NEW.first_photo_binding_id,NEW.first_photo_id);
  INSERT INTO album_binding_events(binding_id,binding_revision,kind,title_revision,desired_title,flickr_photoset_id,state)
   VALUES(NEW.binding_id,NEW.binding_revision,'binding_created',NEW.title_revision,NEW.desired_title,NEW.flickr_photoset_id,NEW.state);
 END;
CREATE TRIGGER album_binding_changed AFTER UPDATE ON album_bindings
 WHEN NEW.binding_revision<>OLD.binding_revision
 BEGIN
  INSERT INTO album_binding_events(binding_id,binding_revision,kind,title_revision,desired_title,flickr_photoset_id,state)
   VALUES(NEW.binding_id,NEW.binding_revision,'binding_changed',NEW.title_revision,NEW.desired_title,NEW.flickr_photoset_id,NEW.state);
 END;
