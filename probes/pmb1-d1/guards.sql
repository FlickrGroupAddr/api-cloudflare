-- INERT CANDIDATE ONLY. Enumerated public-source fixture tables.

CREATE TRIGGER "pmb1_admin_principals_insert" BEFORE INSERT ON "admin_principals"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_admin_principals_update" BEFORE UPDATE ON "admin_principals"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_admin_principals_delete" BEFORE DELETE ON "admin_principals"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_admin_sessions_insert" BEFORE INSERT ON "admin_sessions"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_admin_sessions_update" BEFORE UPDATE ON "admin_sessions"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_admin_sessions_delete" BEFORE DELETE ON "admin_sessions"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_album_attachment_attempts_insert" BEFORE INSERT ON "album_attachment_attempts"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_album_attachment_attempts_update" BEFORE UPDATE ON "album_attachment_attempts"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_album_attachment_attempts_delete" BEFORE DELETE ON "album_attachment_attempts"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_album_attachment_events_insert" BEFORE INSERT ON "album_attachment_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_album_attachment_events_update" BEFORE UPDATE ON "album_attachment_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_album_attachment_events_delete" BEFORE DELETE ON "album_attachment_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_album_attachment_semantic_events_insert" BEFORE INSERT ON "album_attachment_semantic_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_album_attachment_semantic_events_update" BEFORE UPDATE ON "album_attachment_semantic_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_album_attachment_semantic_events_delete" BEFORE DELETE ON "album_attachment_semantic_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_album_binding_events_insert" BEFORE INSERT ON "album_binding_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_album_binding_events_update" BEFORE UPDATE ON "album_binding_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_album_binding_events_delete" BEFORE DELETE ON "album_binding_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_album_bindings_insert" BEFORE INSERT ON "album_bindings"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_album_bindings_update" BEFORE UPDATE ON "album_bindings"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_album_bindings_delete" BEFORE DELETE ON "album_bindings"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_album_create_repair_receipts_insert" BEFORE INSERT ON "album_create_repair_receipts"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_album_create_repair_receipts_update" BEFORE UPDATE ON "album_create_repair_receipts"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_album_create_repair_receipts_delete" BEFORE DELETE ON "album_create_repair_receipts"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_album_local_removal_receipts_insert" BEFORE INSERT ON "album_local_removal_receipts"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_album_local_removal_receipts_update" BEFORE UPDATE ON "album_local_removal_receipts"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_album_local_removal_receipts_delete" BEFORE DELETE ON "album_local_removal_receipts"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_album_materialization_attempts_insert" BEFORE INSERT ON "album_materialization_attempts"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_album_materialization_attempts_update" BEFORE UPDATE ON "album_materialization_attempts"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_album_materialization_attempts_delete" BEFORE DELETE ON "album_materialization_attempts"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_album_materialization_events_insert" BEFORE INSERT ON "album_materialization_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_album_materialization_events_update" BEFORE UPDATE ON "album_materialization_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_album_materialization_events_delete" BEFORE DELETE ON "album_materialization_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_album_obligation_events_insert" BEFORE INSERT ON "album_obligation_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_album_obligation_events_update" BEFORE UPDATE ON "album_obligation_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_album_obligation_events_delete" BEFORE DELETE ON "album_obligation_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_album_photo_local_removal_receipts_insert" BEFORE INSERT ON "album_photo_local_removal_receipts"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_album_photo_local_removal_receipts_update" BEFORE UPDATE ON "album_photo_local_removal_receipts"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_album_photo_local_removal_receipts_delete" BEFORE DELETE ON "album_photo_local_removal_receipts"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_album_photo_obligations_insert" BEFORE INSERT ON "album_photo_obligations"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_album_photo_obligations_update" BEFORE UPDATE ON "album_photo_obligations"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_album_photo_obligations_delete" BEFORE DELETE ON "album_photo_obligations"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_album_title_attempts_insert" BEFORE INSERT ON "album_title_attempts"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_album_title_attempts_update" BEFORE UPDATE ON "album_title_attempts"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_album_title_attempts_delete" BEFORE DELETE ON "album_title_attempts"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_album_title_events_insert" BEFORE INSERT ON "album_title_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_album_title_events_update" BEFORE UPDATE ON "album_title_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_album_title_events_delete" BEFORE DELETE ON "album_title_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_album_title_receipts_insert" BEFORE INSERT ON "album_title_receipts"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_album_title_receipts_update" BEFORE UPDATE ON "album_title_receipts"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_album_title_receipts_delete" BEFORE DELETE ON "album_title_receipts"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_album_title_semantic_events_insert" BEFORE INSERT ON "album_title_semantic_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_album_title_semantic_events_update" BEFORE UPDATE ON "album_title_semantic_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_album_title_semantic_events_delete" BEFORE DELETE ON "album_title_semantic_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_attempt_dispatches_insert" BEFORE INSERT ON "attempt_dispatches"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_attempt_dispatches_update" BEFORE UPDATE ON "attempt_dispatches"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_attempt_dispatches_delete" BEFORE DELETE ON "attempt_dispatches"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_attempt_membership_insert" BEFORE INSERT ON "attempt_membership"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_attempt_membership_update" BEFORE UPDATE ON "attempt_membership"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_attempt_membership_delete" BEFORE DELETE ON "attempt_membership"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_attempt_preflights_insert" BEFORE INSERT ON "attempt_preflights"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_attempt_preflights_update" BEFORE UPDATE ON "attempt_preflights"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_attempt_preflights_delete" BEFORE DELETE ON "attempt_preflights"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_attempt_resolutions_insert" BEFORE INSERT ON "attempt_resolutions"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_attempt_resolutions_update" BEFORE UPDATE ON "attempt_resolutions"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_attempt_resolutions_delete" BEFORE DELETE ON "attempt_resolutions"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_audit_events_insert" BEFORE INSERT ON "audit_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_audit_events_update" BEFORE UPDATE ON "audit_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_audit_events_delete" BEFORE DELETE ON "audit_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_auth_cost_events_insert" BEFORE INSERT ON "auth_cost_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_auth_cost_events_update" BEFORE UPDATE ON "auth_cost_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_auth_cost_events_delete" BEFORE DELETE ON "auth_cost_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_auth_source_buckets_insert" BEFORE INSERT ON "auth_source_buckets"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_auth_source_buckets_update" BEFORE UPDATE ON "auth_source_buckets"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_auth_source_buckets_delete" BEFORE DELETE ON "auth_source_buckets"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_deployment_conformance_insert" BEFORE INSERT ON "deployment_conformance"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_deployment_conformance_update" BEFORE UPDATE ON "deployment_conformance"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_deployment_conformance_delete" BEFORE DELETE ON "deployment_conformance"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_fga_users_insert" BEFORE INSERT ON "fga_users"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_fga_users_update" BEFORE UPDATE ON "fga_users"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_fga_users_delete" BEFORE DELETE ON "fga_users"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_flickr_connection_state_insert" BEFORE INSERT ON "flickr_connection_state"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_flickr_connection_state_update" BEFORE UPDATE ON "flickr_connection_state"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_flickr_connection_state_delete" BEFORE DELETE ON "flickr_connection_state"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_flickr_lifecycle_operations_insert" BEFORE INSERT ON "flickr_lifecycle_operations"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_flickr_lifecycle_operations_update" BEFORE UPDATE ON "flickr_lifecycle_operations"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_flickr_lifecycle_operations_delete" BEFORE DELETE ON "flickr_lifecycle_operations"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_flickr_links_insert" BEFORE INSERT ON "flickr_links"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_flickr_links_update" BEFORE UPDATE ON "flickr_links"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_flickr_links_delete" BEFORE DELETE ON "flickr_links"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_flickr_native_credentials_insert" BEFORE INSERT ON "flickr_native_credentials"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_flickr_native_credentials_update" BEFORE UPDATE ON "flickr_native_credentials"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_flickr_native_credentials_delete" BEFORE DELETE ON "flickr_native_credentials"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_flickr_oauth_transactions_insert" BEFORE INSERT ON "flickr_oauth_transactions"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_flickr_oauth_transactions_update" BEFORE UPDATE ON "flickr_oauth_transactions"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_flickr_oauth_transactions_delete" BEFORE DELETE ON "flickr_oauth_transactions"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_flickr_rate_reservations_insert" BEFORE INSERT ON "flickr_rate_reservations"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_flickr_rate_reservations_update" BEFORE UPDATE ON "flickr_rate_reservations"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_flickr_rate_reservations_delete" BEFORE DELETE ON "flickr_rate_reservations"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_flickr_rate_window_insert" BEFORE INSERT ON "flickr_rate_window"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_flickr_rate_window_update" BEFORE UPDATE ON "flickr_rate_window"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_flickr_rate_window_delete" BEFORE DELETE ON "flickr_rate_window"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_flickr_write_gate_events_insert" BEFORE INSERT ON "flickr_write_gate_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_flickr_write_gate_events_update" BEFORE UPDATE ON "flickr_write_gate_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_flickr_write_gate_events_delete" BEFORE DELETE ON "flickr_write_gate_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_flickr_write_gates_insert" BEFORE INSERT ON "flickr_write_gates"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_flickr_write_gates_update" BEFORE UPDATE ON "flickr_write_gates"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_flickr_write_gates_delete" BEFORE DELETE ON "flickr_write_gates"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_google_jwks_cache_insert" BEFORE INSERT ON "google_jwks_cache"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_google_jwks_cache_update" BEFORE UPDATE ON "google_jwks_cache"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_google_jwks_cache_delete" BEFORE DELETE ON "google_jwks_cache"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_google_login_transactions_insert" BEFORE INSERT ON "google_login_transactions"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_google_login_transactions_update" BEFORE UPDATE ON "google_login_transactions"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_google_login_transactions_delete" BEFORE DELETE ON "google_login_transactions"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_group_partitions_insert" BEFORE INSERT ON "group_partitions"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_group_partitions_update" BEFORE UPDATE ON "group_partitions"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_group_partitions_delete" BEFORE DELETE ON "group_partitions"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_group_refresh_insert" BEFORE INSERT ON "group_refresh"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_group_refresh_update" BEFORE UPDATE ON "group_refresh"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_group_refresh_delete" BEFORE DELETE ON "group_refresh"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_group_refresh_rows_insert" BEFORE INSERT ON "group_refresh_rows"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_group_refresh_rows_update" BEFORE UPDATE ON "group_refresh_rows"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_group_refresh_rows_delete" BEFORE DELETE ON "group_refresh_rows"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_group_snapshot_rows_insert" BEFORE INSERT ON "group_snapshot_rows"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_group_snapshot_rows_update" BEFORE UPDATE ON "group_snapshot_rows"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_group_snapshot_rows_delete" BEFORE DELETE ON "group_snapshot_rows"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_group_snapshots_insert" BEFORE INSERT ON "group_snapshots"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_group_snapshots_update" BEFORE UPDATE ON "group_snapshots"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_group_snapshots_delete" BEFORE DELETE ON "group_snapshots"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_installation_credential_versions_insert" BEFORE INSERT ON "installation_credential_versions"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_installation_credential_versions_update" BEFORE UPDATE ON "installation_credential_versions"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_installation_credential_versions_delete" BEFORE DELETE ON "installation_credential_versions"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_installation_lifecycle_events_insert" BEFORE INSERT ON "installation_lifecycle_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_installation_lifecycle_events_update" BEFORE UPDATE ON "installation_lifecycle_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_installation_lifecycle_events_delete" BEFORE DELETE ON "installation_lifecycle_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_installations_insert" BEFORE INSERT ON "installations"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_installations_update" BEFORE UPDATE ON "installations"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_installations_delete" BEFORE DELETE ON "installations"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_partition_lease_events_insert" BEFORE INSERT ON "partition_lease_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_partition_lease_events_update" BEFORE UPDATE ON "partition_lease_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_partition_lease_events_delete" BEFORE DELETE ON "partition_lease_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_photo_binding_events_insert" BEFORE INSERT ON "photo_binding_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_photo_binding_events_update" BEFORE UPDATE ON "photo_binding_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_photo_binding_events_delete" BEFORE DELETE ON "photo_binding_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_photo_bindings_insert" BEFORE INSERT ON "photo_bindings"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_photo_bindings_update" BEFORE UPDATE ON "photo_bindings"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_photo_bindings_delete" BEFORE DELETE ON "photo_bindings"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_photo_membership_observations_insert" BEFORE INSERT ON "photo_membership_observations"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_photo_membership_observations_update" BEFORE UPDATE ON "photo_membership_observations"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_photo_membership_observations_delete" BEFORE DELETE ON "photo_membership_observations"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_photo_membership_rows_insert" BEFORE INSERT ON "photo_membership_rows"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_photo_membership_rows_update" BEFORE UPDATE ON "photo_membership_rows"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_photo_membership_rows_delete" BEFORE DELETE ON "photo_membership_rows"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_publish_service_identities_insert" BEFORE INSERT ON "publish_service_identities"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_publish_service_identities_update" BEFORE UPDATE ON "publish_service_identities"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_publish_service_identities_delete" BEFORE DELETE ON "publish_service_identities"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_status_read_buckets_insert" BEFORE INSERT ON "status_read_buckets"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_status_read_buckets_update" BEFORE UPDATE ON "status_read_buckets"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_status_read_buckets_delete" BEFORE DELETE ON "status_read_buckets"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_status_read_events_insert" BEFORE INSERT ON "status_read_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_status_read_events_update" BEFORE UPDATE ON "status_read_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_status_read_events_delete" BEFORE DELETE ON "status_read_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_submission_attempts_insert" BEFORE INSERT ON "submission_attempts"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_submission_attempts_update" BEFORE UPDATE ON "submission_attempts"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_submission_attempts_delete" BEFORE DELETE ON "submission_attempts"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_submission_blocks_insert" BEFORE INSERT ON "submission_blocks"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_submission_blocks_update" BEFORE UPDATE ON "submission_blocks"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_submission_blocks_delete" BEFORE DELETE ON "submission_blocks"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_submission_intent_events_insert" BEFORE INSERT ON "submission_intent_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_submission_intent_events_update" BEFORE UPDATE ON "submission_intent_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_submission_intent_events_delete" BEFORE DELETE ON "submission_intent_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_submission_intents_insert" BEFORE INSERT ON "submission_intents"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_submission_intents_update" BEFORE UPDATE ON "submission_intents"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_submission_intents_delete" BEFORE DELETE ON "submission_intents"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_transaction_guards_insert" BEFORE INSERT ON "transaction_guards"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_transaction_guards_update" BEFORE UPDATE ON "transaction_guards"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_transaction_guards_delete" BEFORE DELETE ON "transaction_guards"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_upload_ambiguity_resolution_events_insert" BEFORE INSERT ON "upload_ambiguity_resolution_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_upload_ambiguity_resolution_events_update" BEFORE UPDATE ON "upload_ambiguity_resolution_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_upload_ambiguity_resolution_events_delete" BEFORE DELETE ON "upload_ambiguity_resolution_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_upload_authorizations_insert" BEFORE INSERT ON "upload_authorizations"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_upload_authorizations_update" BEFORE UPDATE ON "upload_authorizations"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_upload_authorizations_delete" BEFORE DELETE ON "upload_authorizations"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_upload_photo_binding_events_insert" BEFORE INSERT ON "upload_photo_binding_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_upload_photo_binding_events_update" BEFORE UPDATE ON "upload_photo_binding_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;

CREATE TRIGGER "pmb1_upload_photo_binding_events_delete" BEFORE DELETE ON "upload_photo_binding_events"
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND EXISTS (
      SELECT 1 FROM maintenance_control
      WHERE typeof(singleton_id) = 'integer' AND singleton_id = 1
        AND typeof(generation) = 'integer'
        AND generation BETWEEN 1 AND 9223372036854775807
        AND typeof(state) = 'text' AND state = 'open'
    )
  THEN 1 ELSE RAISE(ABORT, 'maintenance_closed') END;
END;
