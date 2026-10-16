-- Append-only photographer assertion, additional to the exact-photo ownership proof.
-- No byte identity is inferred. Existing common binding source is retained.
CREATE TABLE upload_ambiguity_resolution_events (
 authorization_id TEXT PRIMARY KEY NOT NULL REFERENCES upload_photo_binding_events(authorization_id) ON DELETE RESTRICT,
 provenance TEXT NOT NULL CHECK(provenance='photographer_reconciled_ambiguous_upload'),
 binding_origin INTEGER NOT NULL CHECK(binding_origin IN (0,1))
) STRICT;
CREATE TRIGGER upload_ambiguity_resolution_consistent BEFORE INSERT ON upload_ambiguity_resolution_events
 WHEN NOT EXISTS(SELECT 1 FROM upload_photo_binding_events e JOIN photo_bindings b ON b.binding_id=e.binding_id
   WHERE e.authorization_id=NEW.authorization_id
     AND (NEW.binding_origin=0 OR (b.source_kind='upload' AND e.verification_revision=1)))
 BEGIN SELECT RAISE(ABORT,'upload_ambiguity_resolution_inconsistent'); END;
CREATE TRIGGER upload_ambiguity_resolution_no_update BEFORE UPDATE ON upload_ambiguity_resolution_events
 BEGIN SELECT RAISE(ABORT,'upload_ambiguity_resolution_immutable'); END;
CREATE TRIGGER upload_ambiguity_resolution_no_delete BEFORE DELETE ON upload_ambiguity_resolution_events
 BEGIN SELECT RAISE(ABORT,'upload_ambiguity_resolution_immutable'); END;
CREATE TRIGGER upload_ambiguity_resolution_no_replace BEFORE INSERT ON upload_ambiguity_resolution_events
 WHEN EXISTS(SELECT 1 FROM upload_ambiguity_resolution_events WHERE authorization_id=NEW.authorization_id)
 BEGIN SELECT RAISE(ABORT,'upload_ambiguity_resolution_immutable'); END;
