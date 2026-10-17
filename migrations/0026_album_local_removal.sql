-- One-way local archival; every accepted remote obligation and history survives.
-- Receipt insertion owns the semantic transaction. No table rebuild or remote work.
CREATE TABLE album_local_removal_receipts (
 binding_id TEXT PRIMARY KEY NOT NULL REFERENCES album_bindings(binding_id) ON DELETE RESTRICT,
 expected_binding_revision INTEGER NOT NULL CHECK(expected_binding_revision BETWEEN 1 AND 9007199254740990),
 accepted_binding_revision INTEGER NOT NULL CHECK(accepted_binding_revision=expected_binding_revision+1),
 acknowledged_create_attempt_id TEXT REFERENCES album_materialization_attempts(attempt_id) ON DELETE RESTRICT,
 archived_at_us INTEGER NOT NULL DEFAULT (CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000),
 installation_id TEXT NOT NULL,credential_digest TEXT NOT NULL
) STRICT;
CREATE TABLE album_photo_local_removal_receipts (
 obligation_id TEXT PRIMARY KEY NOT NULL REFERENCES album_photo_obligations(obligation_id) ON DELETE RESTRICT,
 binding_id TEXT NOT NULL REFERENCES album_bindings(binding_id) ON DELETE RESTRICT,
 photo_binding_id TEXT NOT NULL REFERENCES photo_bindings(binding_id) ON DELETE RESTRICT,
 expected_binding_revision INTEGER NOT NULL CHECK(expected_binding_revision BETWEEN 1 AND 9007199254740990),
 expected_obligation_revision INTEGER NOT NULL CHECK(expected_obligation_revision BETWEEN 1 AND 9007199254740990),
 accepted_binding_revision INTEGER NOT NULL CHECK(accepted_binding_revision=expected_binding_revision+1),
 archived_obligation_revision INTEGER NOT NULL CHECK(archived_obligation_revision=expected_obligation_revision+1),
 source TEXT NOT NULL CHECK(source IN ('photo','album')),
 archived_at_us INTEGER NOT NULL DEFAULT (CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000),
 installation_id TEXT NOT NULL,credential_digest TEXT NOT NULL,
 UNIQUE(binding_id,photo_binding_id)
) STRICT;
CREATE TRIGGER album_local_removal_initial BEFORE INSERT ON album_local_removal_receipts
 WHEN NEW.archived_at_us<>(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000) OR NOT EXISTS(SELECT 1 FROM installations i JOIN installation_credential_versions v
 ON v.installation_id=i.installation_id AND v.version_id=i.current_version_id
 JOIN album_bindings b ON b.user_id=i.user_id
 JOIN publish_service_identities s ON s.service_id=b.service_id AND s.user_id=b.user_id
 WHERE b.binding_id=NEW.binding_id AND i.installation_id=NEW.installation_id
 AND i.state='active' AND i.credential_class='lrc_plugin' AND i.revision BETWEEN 1 AND 9007199254740991
 AND v.state='current' AND v.expires_at_us IS NULL AND v.credential_digest=NEW.credential_digest)
 OR NOT EXISTS(SELECT 1 FROM album_bindings b WHERE b.binding_id=NEW.binding_id
 AND b.state='materialization_pending' AND b.binding_revision=NEW.expected_binding_revision
 AND NEW.acknowledged_create_attempt_id IS (SELECT attempt_id FROM album_materialization_attempts a
 WHERE a.binding_id=b.binding_id AND a.state='create_outcome_unknown' AND b.materialization_state='create_outcome_unknown' AND b.flickr_photoset_id IS NULL ORDER BY epoch DESC LIMIT 1))
 OR EXISTS(SELECT 1 FROM album_photo_obligations o WHERE o.album_binding_id=NEW.binding_id
 AND o.local_relationship='active' AND o.obligation_revision=9007199254740991)
 BEGIN SELECT RAISE(ABORT,'album_local_removal_initial'); END;
CREATE TRIGGER album_photo_local_removal_initial BEFORE INSERT ON album_photo_local_removal_receipts
 WHEN NEW.archived_at_us<>(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000) OR NOT EXISTS(SELECT 1 FROM installations i JOIN installation_credential_versions v
 ON v.installation_id=i.installation_id AND v.version_id=i.current_version_id
 JOIN album_bindings b ON b.user_id=i.user_id
 JOIN publish_service_identities s ON s.service_id=b.service_id AND s.user_id=b.user_id
 WHERE b.binding_id=NEW.binding_id AND i.installation_id=NEW.installation_id
 AND i.state='active' AND i.credential_class='lrc_plugin' AND i.revision BETWEEN 1 AND 9007199254740991
 AND v.state='current' AND v.expires_at_us IS NULL AND v.credential_digest=NEW.credential_digest)
 OR NOT EXISTS(SELECT 1 FROM album_photo_obligations o JOIN album_bindings b ON b.binding_id=o.album_binding_id
 WHERE o.obligation_id=NEW.obligation_id AND o.album_binding_id=NEW.binding_id AND o.photo_binding_id=NEW.photo_binding_id
 AND o.local_relationship='active' AND o.obligation_revision=NEW.expected_obligation_revision
 AND ((NEW.source='photo' AND b.binding_revision=NEW.expected_binding_revision)
 OR (NEW.source='album' AND b.state='local_collection_removed_remote_preserved'
 AND b.binding_revision=NEW.accepted_binding_revision
 AND EXISTS(SELECT 1 FROM album_local_removal_receipts r WHERE r.binding_id=b.binding_id
 AND r.expected_binding_revision=NEW.expected_binding_revision AND r.accepted_binding_revision=NEW.accepted_binding_revision
 AND r.installation_id=NEW.installation_id AND r.credential_digest=NEW.credential_digest AND r.archived_at_us=NEW.archived_at_us))))
 BEGIN SELECT RAISE(ABORT,'album_photo_local_removal_initial'); END;
CREATE TRIGGER album_local_removal_receipts_no_update BEFORE UPDATE ON album_local_removal_receipts BEGIN SELECT RAISE(ABORT,'local_removal_receipt_retained'); END;
CREATE TRIGGER album_local_removal_receipts_no_delete BEFORE DELETE ON album_local_removal_receipts BEGIN SELECT RAISE(ABORT,'local_removal_receipt_retained'); END;
CREATE TRIGGER album_local_removal_receipts_no_replace BEFORE INSERT ON album_local_removal_receipts
 WHEN EXISTS(SELECT 1 FROM album_local_removal_receipts WHERE binding_id=NEW.binding_id)
 BEGIN SELECT RAISE(ABORT,'local_removal_receipt_retained'); END;
CREATE TRIGGER album_photo_local_removal_receipts_no_update BEFORE UPDATE ON album_photo_local_removal_receipts BEGIN SELECT RAISE(ABORT,'local_removal_receipt_retained'); END;
CREATE TRIGGER album_photo_local_removal_receipts_no_delete BEFORE DELETE ON album_photo_local_removal_receipts BEGIN SELECT RAISE(ABORT,'local_removal_receipt_retained'); END;
CREATE TRIGGER album_photo_local_removal_receipts_no_replace BEFORE INSERT ON album_photo_local_removal_receipts
 WHEN EXISTS(SELECT 1 FROM album_photo_local_removal_receipts WHERE obligation_id=NEW.obligation_id OR (binding_id=NEW.binding_id AND photo_binding_id=NEW.photo_binding_id))
 BEGIN SELECT RAISE(ABORT,'local_removal_receipt_retained'); END;
CREATE TRIGGER album_local_archive_authorized BEFORE UPDATE ON album_bindings
 WHEN NEW.state<>OLD.state AND NOT EXISTS(SELECT 1 FROM album_local_removal_receipts r
 WHERE r.binding_id=OLD.binding_id AND r.expected_binding_revision=OLD.binding_revision
 AND r.accepted_binding_revision=NEW.binding_revision)
 BEGIN SELECT RAISE(ABORT,'album_archive_receipt_required'); END;
DROP TRIGGER album_binding_revision;
CREATE TRIGGER album_binding_revision BEFORE UPDATE ON album_bindings
 WHEN NEW.binding_revision<>OLD.binding_revision+
   (NEW.title_revision<>OLD.title_revision OR NEW.flickr_photoset_id IS NOT OLD.flickr_photoset_id OR NEW.state<>OLD.state OR NEW.materialization_state<>OLD.materialization_state
    OR EXISTS(SELECT 1 FROM album_photo_obligations o WHERE o.album_binding_id=OLD.binding_id
      AND o.admission_binding_revision=OLD.binding_revision+1
      AND NOT EXISTS(SELECT 1 FROM album_binding_events e WHERE e.binding_id=OLD.binding_id AND e.binding_revision=o.admission_binding_revision))
    OR EXISTS(SELECT 1 FROM album_title_semantic_events e WHERE e.binding_id=OLD.binding_id
      AND e.binding_revision_after=OLD.binding_revision+1 AND e.binding_revision_before=OLD.binding_revision
      AND NOT EXISTS(SELECT 1 FROM album_binding_events h WHERE h.binding_id=OLD.binding_id AND h.binding_revision=e.binding_revision_after))
 OR EXISTS(SELECT 1 FROM album_attachment_semantic_events se WHERE se.binding_id=OLD.binding_id
 AND se.binding_revision_before=OLD.binding_revision AND se.binding_revision_after=NEW.binding_revision
 AND NOT EXISTS(SELECT 1 FROM album_binding_events e WHERE e.binding_id=OLD.binding_id AND e.binding_revision=NEW.binding_revision))
 OR EXISTS(SELECT 1 FROM album_photo_local_removal_receipts r WHERE r.binding_id=OLD.binding_id
 AND r.source='photo' AND r.expected_binding_revision=OLD.binding_revision AND r.accepted_binding_revision=NEW.binding_revision
 AND NOT EXISTS(SELECT 1 FROM album_binding_events e WHERE e.binding_id=OLD.binding_id AND e.binding_revision=NEW.binding_revision)))

 OR NEW.materialization_revision<>OLD.materialization_revision+(NEW.materialization_state<>OLD.materialization_state)
 OR (NEW.title_revision<>OLD.title_revision AND NOT (NEW.title_revision=OLD.title_revision+1
  AND EXISTS(SELECT 1 FROM album_title_receipts r WHERE r.binding_id=OLD.binding_id
   AND r.title_revision=NEW.title_revision AND r.expected_binding_revision=OLD.binding_revision
   AND r.accepted_binding_revision=NEW.binding_revision AND r.expected_title_revision=OLD.title_revision AND r.desired_title=NEW.desired_title)))
 OR (NEW.desired_title<>OLD.desired_title AND NEW.title_revision=OLD.title_revision)
 OR (OLD.state='local_collection_removed_remote_preserved' AND (NEW.state<>OLD.state OR NEW.desired_title<>OLD.desired_title OR NEW.title_revision<>OLD.title_revision))
 BEGIN SELECT RAISE(ABORT,'album_binding_revision'); END;
DROP TRIGGER album_obligation_no_update;
CREATE TRIGGER album_obligation_no_update BEFORE UPDATE ON album_photo_obligations
 WHEN NEW.obligation_id<>OLD.obligation_id OR NEW.album_binding_id<>OLD.album_binding_id
 OR NEW.photo_binding_id<>OLD.photo_binding_id OR NEW.photo_id<>OLD.photo_id
 OR NEW.admission_binding_revision<>OLD.admission_binding_revision
 OR NEW.obligation_revision<>OLD.obligation_revision+1
 OR NOT (
  (NEW.state=OLD.state AND OLD.local_relationship='active' AND NEW.local_relationship='archived'
   AND EXISTS(SELECT 1 FROM album_photo_local_removal_receipts r
 WHERE r.obligation_id=OLD.obligation_id AND r.binding_id=OLD.album_binding_id AND r.photo_binding_id=OLD.photo_binding_id
 AND r.expected_obligation_revision=OLD.obligation_revision AND r.archived_obligation_revision=NEW.obligation_revision
 AND EXISTS(SELECT 1 FROM album_bindings b WHERE b.binding_id=r.binding_id AND b.binding_revision=r.accepted_binding_revision)))
  OR (NEW.local_relationship=OLD.local_relationship AND NEW.state='membership_verified' AND OLD.state='waiting_for_album'
   AND (EXISTS(SELECT 1 FROM album_materialization_attempts a JOIN album_bindings b ON b.binding_id=a.binding_id
    WHERE b.first_obligation_id=OLD.obligation_id AND a.state='verified' AND a.photoset_id=b.flickr_photoset_id
    AND a.photo_id=OLD.photo_id AND a.photo_binding_id=OLD.photo_binding_id)
   OR EXISTS(SELECT 1 FROM album_create_repair_receipts r JOIN album_bindings b ON b.binding_id=r.binding_id
    WHERE b.first_obligation_id=OLD.obligation_id AND b.flickr_photoset_id=r.selected_photoset_id
    AND r.first_photo_id=OLD.photo_id AND r.first_photo_binding_id=OLD.photo_binding_id)))
 OR (NEW.local_relationship=OLD.local_relationship
 AND EXISTS(SELECT 1 FROM album_attachment_semantic_events se WHERE se.obligation_id=OLD.obligation_id
 AND se.obligation_revision_before=OLD.obligation_revision AND se.obligation_revision_after=NEW.obligation_revision
 AND NEW.state=CASE WHEN se.state='membership_verified' THEN 'membership_verified' ELSE OLD.state END)))

 BEGIN SELECT RAISE(ABORT,'album_obligation_immutable'); END;
DROP TRIGGER album_binding_archive_obligations;
CREATE TRIGGER album_binding_archive_obligations AFTER UPDATE ON album_bindings
 WHEN OLD.state<>NEW.state AND NEW.state='local_collection_removed_remote_preserved' BEGIN
 INSERT INTO album_photo_local_removal_receipts(obligation_id,binding_id,photo_binding_id,
 expected_binding_revision,expected_obligation_revision,accepted_binding_revision,archived_obligation_revision,
 source,archived_at_us,installation_id,credential_digest)
 SELECT o.obligation_id,NEW.binding_id,o.photo_binding_id,r.expected_binding_revision,o.obligation_revision,
 r.accepted_binding_revision,o.obligation_revision+1,'album',r.archived_at_us,r.installation_id,r.credential_digest
 FROM album_photo_obligations o JOIN album_local_removal_receipts r ON r.binding_id=o.album_binding_id
 WHERE o.album_binding_id=NEW.binding_id AND o.local_relationship='active';
END;
CREATE TRIGGER album_photo_local_removal_apply AFTER INSERT ON album_photo_local_removal_receipts BEGIN
 UPDATE album_bindings SET binding_revision=NEW.accepted_binding_revision
 WHERE binding_id=NEW.binding_id AND NEW.source='photo' AND binding_revision=NEW.expected_binding_revision;
 UPDATE album_photo_obligations SET local_relationship='archived',obligation_revision=NEW.archived_obligation_revision
 WHERE obligation_id=NEW.obligation_id;
END;
CREATE TRIGGER album_local_removal_apply AFTER INSERT ON album_local_removal_receipts BEGIN
 UPDATE album_bindings SET state='local_collection_removed_remote_preserved',binding_revision=NEW.accepted_binding_revision
 WHERE binding_id=NEW.binding_id;
END;
