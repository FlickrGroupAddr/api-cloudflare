-- Admission only: no worker, remote dispatch, or lifecycle wire is enabled.
-- D1 executes a migration transaction. Defer the retained binding's circular
-- first-obligation FK while rebuilding the original receipt table in place.
PRAGMA defer_foreign_keys=ON;
DROP TRIGGER album_binding_created;
DROP TRIGGER album_binding_revision;
CREATE TABLE album_photo_obligations_next (
 obligation_id TEXT PRIMARY KEY NOT NULL CHECK(length(obligation_id)=36 AND obligation_id=lower(obligation_id)
  AND obligation_id GLOB '????????-????-4???-[89ab]???-????????????'
  AND length(replace(obligation_id,'-',''))=32 AND replace(obligation_id,'-','') NOT GLOB '*[^0-9a-f]*'),
 album_binding_id TEXT NOT NULL REFERENCES album_bindings(binding_id) ON DELETE RESTRICT,
 photo_binding_id TEXT NOT NULL REFERENCES photo_bindings(binding_id) ON DELETE RESTRICT,
 photo_id TEXT NOT NULL,
 obligation_revision INTEGER NOT NULL DEFAULT 1 CHECK(obligation_revision BETWEEN 1 AND 9007199254740991),
 state TEXT NOT NULL DEFAULT 'waiting_for_album' CHECK(state IN ('waiting_for_album','attachment_pending')),
 local_relationship TEXT NOT NULL DEFAULT 'active' CHECK(local_relationship IN ('active','archived')),
 admission_binding_revision INTEGER NOT NULL CHECK(admission_binding_revision BETWEEN 1 AND 9007199254740991),
 UNIQUE(album_binding_id,photo_binding_id),
 UNIQUE(album_binding_id,admission_binding_revision),
 UNIQUE(obligation_id,album_binding_id,photo_binding_id,photo_id)
) STRICT;
INSERT INTO album_photo_obligations_next
 (obligation_id,album_binding_id,photo_binding_id,photo_id,obligation_revision,state,local_relationship,admission_binding_revision)
 SELECT o.obligation_id,o.album_binding_id,o.photo_binding_id,o.photo_id,o.obligation_revision,
  CASE WHEN b.flickr_photoset_id IS NULL THEN 'waiting_for_album' ELSE 'attachment_pending' END,
  CASE WHEN b.state='local_collection_removed_remote_preserved' THEN 'archived' ELSE 'active' END,1
 FROM album_photo_obligations o JOIN album_bindings b ON b.binding_id=o.album_binding_id;
DROP TABLE album_photo_obligations;
ALTER TABLE album_photo_obligations_next RENAME TO album_photo_obligations;
-- Restored circular references are checked explicitly before clearing SQLite's
-- deferred DROP counter. Refuse the entire migration if any retained FK differs.
CREATE TABLE album_obligation_migration_guard(ok INTEGER NOT NULL CHECK(ok=1)) STRICT;
INSERT INTO album_obligation_migration_guard SELECT NOT EXISTS(SELECT 1 FROM pragma_foreign_key_check);
DROP TABLE album_obligation_migration_guard;
PRAGMA defer_foreign_keys=OFF;

CREATE TABLE album_obligation_events (
 obligation_id TEXT NOT NULL REFERENCES album_photo_obligations(obligation_id) ON DELETE RESTRICT,
 obligation_revision INTEGER NOT NULL CHECK(obligation_revision BETWEEN 1 AND 9007199254740991),
 kind TEXT NOT NULL CHECK(kind IN ('obligation_admitted','relationship_archived','receipt_migrated')),
 state TEXT NOT NULL CHECK(state IN ('waiting_for_album','attachment_pending')),
 local_relationship TEXT NOT NULL CHECK(local_relationship IN ('active','archived')),
 created_at_us INTEGER NOT NULL DEFAULT(CAST(strftime('%s','now') AS INTEGER)*1000000
  + CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000),
 PRIMARY KEY(obligation_id,obligation_revision)
) STRICT;
-- This event describes migration, not a new admission or invented earlier time.
INSERT INTO album_obligation_events(obligation_id,obligation_revision,kind,state,local_relationship)
 SELECT obligation_id,obligation_revision,'receipt_migrated',state,local_relationship FROM album_photo_obligations;

CREATE TRIGGER album_binding_revision BEFORE UPDATE ON album_bindings
 WHEN NEW.binding_revision<>OLD.binding_revision+
   (NEW.desired_title<>OLD.desired_title OR NEW.flickr_photoset_id IS NOT OLD.flickr_photoset_id OR NEW.state<>OLD.state
    OR EXISTS(SELECT 1 FROM album_photo_obligations o WHERE o.album_binding_id=OLD.binding_id
      AND o.admission_binding_revision=OLD.binding_revision+1
      AND NOT EXISTS(SELECT 1 FROM album_binding_events e WHERE e.binding_id=OLD.binding_id
       AND e.binding_revision=o.admission_binding_revision)))
  OR NEW.title_revision<>OLD.title_revision+(NEW.desired_title<>OLD.desired_title)
  OR (OLD.state='local_collection_removed_remote_preserved'
    AND (NEW.state<>OLD.state OR NEW.desired_title<>OLD.desired_title))
 BEGIN SELECT RAISE(ABORT,'album_binding_revision'); END;

CREATE TRIGGER album_obligation_initial BEFORE INSERT ON album_photo_obligations
 WHEN NEW.obligation_revision<>1 OR NEW.local_relationship<>'active'
  OR NOT EXISTS(SELECT 1 FROM album_bindings b
   JOIN publish_service_identities s ON s.service_id=b.service_id AND s.user_id=b.user_id
   JOIN photo_bindings p ON p.binding_id=NEW.photo_binding_id AND p.user_id=b.user_id
   WHERE b.binding_id=NEW.album_binding_id AND b.state='materialization_pending'
    AND s.owner_nsid=b.owner_nsid AND s.link_revision=b.link_revision
    AND p.photo_id=NEW.photo_id AND p.owner_nsid=b.owner_nsid AND p.link_revision=b.link_revision
    AND p.binding_id<>'0' AND p.photo_id<>'0' AND p.verification_revision BETWEEN 1 AND 9007199254740991
    AND p.verified_at_us BETWEEN 0 AND CAST(strftime('%s','now') AS INTEGER)*1000000
      + CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000
    AND (EXISTS(SELECT 1 FROM photo_binding_events e WHERE e.binding_id=p.binding_id
      AND e.verification_revision=p.verification_revision AND e.kind='existing_public_verified')
     OR EXISTS(SELECT 1 FROM upload_photo_binding_events e WHERE e.binding_id=p.binding_id
      AND e.verification_revision=p.verification_revision AND e.link_revision=p.link_revision
      AND e.verified_at_us=p.verified_at_us))
    AND NEW.state=CASE WHEN b.flickr_photoset_id IS NULL THEN 'waiting_for_album' ELSE 'attachment_pending' END
    AND ((b.binding_revision=1 AND b.first_obligation_id=NEW.obligation_id
      AND b.first_photo_binding_id=NEW.photo_binding_id AND b.first_photo_id=NEW.photo_id
      AND NEW.admission_binding_revision=1)
     OR (b.first_obligation_id<>NEW.obligation_id AND b.first_photo_binding_id<>NEW.photo_binding_id
      AND b.binding_revision<9007199254740991 AND NEW.admission_binding_revision=b.binding_revision+1)))
 BEGIN SELECT RAISE(ABORT,'album_obligation_initial'); END;
CREATE TRIGGER album_obligation_no_update BEFORE UPDATE ON album_photo_obligations
 WHEN NEW.obligation_id<>OLD.obligation_id OR NEW.album_binding_id<>OLD.album_binding_id
  OR NEW.photo_binding_id<>OLD.photo_binding_id OR NEW.photo_id<>OLD.photo_id
  OR NEW.admission_binding_revision<>OLD.admission_binding_revision OR NEW.state<>OLD.state
  OR OLD.local_relationship<>'active' OR NEW.local_relationship<>'archived'
  OR NEW.obligation_revision<>OLD.obligation_revision+1
  OR NOT EXISTS(SELECT 1 FROM album_bindings b WHERE b.binding_id=OLD.album_binding_id
   AND b.state='local_collection_removed_remote_preserved')
 BEGIN SELECT RAISE(ABORT,'album_obligation_immutable'); END;
CREATE TRIGGER album_obligation_no_delete BEFORE DELETE ON album_photo_obligations
 BEGIN SELECT RAISE(ABORT,'album_obligation_retained'); END;
CREATE TRIGGER album_obligation_no_replace BEFORE INSERT ON album_photo_obligations
 WHEN EXISTS(SELECT 1 FROM album_photo_obligations WHERE obligation_id=NEW.obligation_id
  OR (album_binding_id=NEW.album_binding_id AND photo_binding_id=NEW.photo_binding_id))
 BEGIN SELECT RAISE(ABORT,'album_obligation_retained'); END;
CREATE TRIGGER album_obligation_event_consistent BEFORE INSERT ON album_obligation_events
 WHEN NEW.kind='receipt_migrated' OR NOT EXISTS(SELECT 1 FROM album_photo_obligations o
  WHERE o.obligation_id=NEW.obligation_id AND o.obligation_revision=NEW.obligation_revision
   AND o.state=NEW.state AND o.local_relationship=NEW.local_relationship)
  OR (NEW.obligation_revision=1 AND NEW.kind<>'obligation_admitted')
  OR (NEW.obligation_revision>1 AND NEW.kind<>'relationship_archived')
 BEGIN SELECT RAISE(ABORT,'album_obligation_event_inconsistent'); END;
CREATE TRIGGER album_obligation_event_no_update BEFORE UPDATE ON album_obligation_events
 BEGIN SELECT RAISE(ABORT,'album_obligation_event_immutable'); END;
CREATE TRIGGER album_obligation_event_no_delete BEFORE DELETE ON album_obligation_events
 BEGIN SELECT RAISE(ABORT,'album_obligation_event_retained'); END;
CREATE TRIGGER album_obligation_event_no_replace BEFORE INSERT ON album_obligation_events
 WHEN EXISTS(SELECT 1 FROM album_obligation_events WHERE obligation_id=NEW.obligation_id
  AND obligation_revision=NEW.obligation_revision)
 BEGIN SELECT RAISE(ABORT,'album_obligation_event_retained'); END;
CREATE TRIGGER album_obligation_admitted AFTER INSERT ON album_photo_obligations
 BEGIN
  UPDATE album_bindings SET binding_revision=NEW.admission_binding_revision
   WHERE binding_id=NEW.album_binding_id AND binding_revision<NEW.admission_binding_revision;
  INSERT INTO album_obligation_events(obligation_id,obligation_revision,kind,state,local_relationship)
   VALUES(NEW.obligation_id,NEW.obligation_revision,'obligation_admitted',NEW.state,NEW.local_relationship);
 END;
CREATE TRIGGER album_obligation_archived AFTER UPDATE ON album_photo_obligations
 BEGIN
  INSERT INTO album_obligation_events(obligation_id,obligation_revision,kind,state,local_relationship)
   VALUES(NEW.obligation_id,NEW.obligation_revision,'relationship_archived',NEW.state,NEW.local_relationship);
 END;
CREATE TRIGGER album_binding_archive_obligations AFTER UPDATE ON album_bindings
 WHEN OLD.state<>NEW.state AND NEW.state='local_collection_removed_remote_preserved'
 BEGIN
  UPDATE album_photo_obligations SET local_relationship='archived',obligation_revision=obligation_revision+1
   WHERE album_binding_id=NEW.binding_id AND local_relationship='active';
 END;
CREATE TRIGGER album_binding_created AFTER INSERT ON album_bindings
 BEGIN
  INSERT INTO album_photo_obligations(obligation_id,album_binding_id,photo_binding_id,photo_id,admission_binding_revision)
   VALUES(NEW.first_obligation_id,NEW.binding_id,NEW.first_photo_binding_id,NEW.first_photo_id,1);
  INSERT INTO album_binding_events(binding_id,binding_revision,kind,title_revision,desired_title,flickr_photoset_id,state)
   VALUES(NEW.binding_id,NEW.binding_revision,'binding_created',NEW.title_revision,NEW.desired_title,NEW.flickr_photoset_id,NEW.state);
 END;
