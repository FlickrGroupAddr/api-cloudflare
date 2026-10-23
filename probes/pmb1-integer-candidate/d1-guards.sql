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

CREATE TRIGGER "pmb1_quota_credit_clocks_insert" BEFORE INSERT ON "quota_credit_clocks"
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

CREATE TRIGGER "pmb1_quota_credit_clocks_update" BEFORE UPDATE ON "quota_credit_clocks"
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

CREATE TRIGGER "pmb1_quota_credit_clocks_delete" BEFORE DELETE ON "quota_credit_clocks"
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

CREATE TRIGGER "pmb1_quota_credit_guards_insert" BEFORE INSERT ON "quota_credit_guards"
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

CREATE TRIGGER "pmb1_quota_credit_guards_update" BEFORE UPDATE ON "quota_credit_guards"
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

CREATE TRIGGER "pmb1_quota_credit_guards_delete" BEFORE DELETE ON "quota_credit_guards"
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
CREATE TRIGGER "pmb1_no_real_d399b411cd8be3ac311936a340f448b98d0e4a2442488a710f64e3b742df9e23_insert" AFTER INSERT ON "admin_principals" WHEN typeof(NEW."user_id")='real' OR typeof(NEW."google_issuer")='real' OR typeof(NEW."google_sub")='real' OR typeof(NEW."session_set_revision")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_d399b411cd8be3ac311936a340f448b98d0e4a2442488a710f64e3b742df9e23_update" AFTER UPDATE ON "admin_principals" WHEN typeof(NEW."user_id")='real' OR typeof(NEW."google_issuer")='real' OR typeof(NEW."google_sub")='real' OR typeof(NEW."session_set_revision")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_4dd68131569bd6919b54a4030c21d037437781c2aaace942bf6bff75f0aa4fa0_insert" AFTER INSERT ON "admin_sessions" WHEN typeof(NEW."session_id")='real' OR typeof(NEW."token_digest")='real' OR typeof(NEW."user_id")='real' OR typeof(NEW."csrf_token")='real' OR typeof(NEW."created_at_us")='real' OR typeof(NEW."recent_authentication_at_us")='real' OR typeof(NEW."expires_at_us")='real' OR typeof(NEW."last_activity_at_us")='real' OR typeof(NEW."revoked_at_us")='real' OR typeof(NEW."revocation_reason")='real' OR typeof(NEW."revision")='real' OR typeof(NEW."correlation_id")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_4dd68131569bd6919b54a4030c21d037437781c2aaace942bf6bff75f0aa4fa0_update" AFTER UPDATE ON "admin_sessions" WHEN typeof(NEW."session_id")='real' OR typeof(NEW."token_digest")='real' OR typeof(NEW."user_id")='real' OR typeof(NEW."csrf_token")='real' OR typeof(NEW."created_at_us")='real' OR typeof(NEW."recent_authentication_at_us")='real' OR typeof(NEW."expires_at_us")='real' OR typeof(NEW."last_activity_at_us")='real' OR typeof(NEW."revoked_at_us")='real' OR typeof(NEW."revocation_reason")='real' OR typeof(NEW."revision")='real' OR typeof(NEW."correlation_id")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_5c00849972ddc6425288f0e6be9b0fbad795e28d3896e4355f4cf98fbb827409_insert" AFTER INSERT ON "album_attachment_attempts" WHEN typeof(NEW."attempt_id")='real' OR typeof(NEW."obligation_id")='real' OR typeof(NEW."binding_id")='real' OR typeof(NEW."lease_id")='real' OR typeof(NEW."epoch")='real' OR typeof(NEW."user_id")='real' OR typeof(NEW."owner_nsid")='real' OR typeof(NEW."photo_binding_id")='real' OR typeof(NEW."photo_id")='real' OR typeof(NEW."photoset_id")='real' OR typeof(NEW."primary_photo_id")='real' OR typeof(NEW."link_revision")='real' OR typeof(NEW."grant_generation")='real' OR typeof(NEW."binding_revision")='real' OR typeof(NEW."obligation_revision")='real' OR typeof(NEW."verification_revision")='real' OR typeof(NEW."deployment_gate_revision")='real' OR typeof(NEW."user_gate_revision")='real' OR typeof(NEW."reconciliation_only")='real' OR typeof(NEW."started_at_us")='real' OR typeof(NEW."invocation_deadline_at_us")='real' OR typeof(NEW."lease_expires_at_us")='real' OR typeof(NEW."state")='real' OR typeof(NEW."dispatch_count")='real' OR typeof(NEW."dispatch_started_at_us")='real' OR typeof(NEW."pre_context_ids")='real' OR typeof(NEW."pre_observed_at_us")='real' OR typeof(NEW."received_result")='real' OR typeof(NEW."received_at_us")='real' OR typeof(NEW."completed_at_us")='real' OR typeof(NEW."retry_after_us")='real' OR typeof(NEW."proof_context_ids")='real' OR typeof(NEW."proof_owner_nsid")='real' OR typeof(NEW."proof_photo_id")='real' OR typeof(NEW."proof_observed_at_us")='real' OR typeof(NEW."attention_reason")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_5c00849972ddc6425288f0e6be9b0fbad795e28d3896e4355f4cf98fbb827409_update" AFTER UPDATE ON "album_attachment_attempts" WHEN typeof(NEW."attempt_id")='real' OR typeof(NEW."obligation_id")='real' OR typeof(NEW."binding_id")='real' OR typeof(NEW."lease_id")='real' OR typeof(NEW."epoch")='real' OR typeof(NEW."user_id")='real' OR typeof(NEW."owner_nsid")='real' OR typeof(NEW."photo_binding_id")='real' OR typeof(NEW."photo_id")='real' OR typeof(NEW."photoset_id")='real' OR typeof(NEW."primary_photo_id")='real' OR typeof(NEW."link_revision")='real' OR typeof(NEW."grant_generation")='real' OR typeof(NEW."binding_revision")='real' OR typeof(NEW."obligation_revision")='real' OR typeof(NEW."verification_revision")='real' OR typeof(NEW."deployment_gate_revision")='real' OR typeof(NEW."user_gate_revision")='real' OR typeof(NEW."reconciliation_only")='real' OR typeof(NEW."started_at_us")='real' OR typeof(NEW."invocation_deadline_at_us")='real' OR typeof(NEW."lease_expires_at_us")='real' OR typeof(NEW."state")='real' OR typeof(NEW."dispatch_count")='real' OR typeof(NEW."dispatch_started_at_us")='real' OR typeof(NEW."pre_context_ids")='real' OR typeof(NEW."pre_observed_at_us")='real' OR typeof(NEW."received_result")='real' OR typeof(NEW."received_at_us")='real' OR typeof(NEW."completed_at_us")='real' OR typeof(NEW."retry_after_us")='real' OR typeof(NEW."proof_context_ids")='real' OR typeof(NEW."proof_owner_nsid")='real' OR typeof(NEW."proof_photo_id")='real' OR typeof(NEW."proof_observed_at_us")='real' OR typeof(NEW."attention_reason")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_37ee882fbddeff3c94680456157b3259acb8a64e8b1a4ed6179566a51d4222a5_insert" AFTER INSERT ON "album_attachment_events" WHEN typeof(NEW."attempt_id")='real' OR typeof(NEW."event_ordinal")='real' OR typeof(NEW."state")='real' OR typeof(NEW."epoch")='real' OR typeof(NEW."dispatch_count")='real' OR typeof(NEW."dispatch_started_at_us")='real' OR typeof(NEW."created_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_37ee882fbddeff3c94680456157b3259acb8a64e8b1a4ed6179566a51d4222a5_update" AFTER UPDATE ON "album_attachment_events" WHEN typeof(NEW."attempt_id")='real' OR typeof(NEW."event_ordinal")='real' OR typeof(NEW."state")='real' OR typeof(NEW."epoch")='real' OR typeof(NEW."dispatch_count")='real' OR typeof(NEW."dispatch_started_at_us")='real' OR typeof(NEW."created_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_ea7a4c2c8f3bae26503b1b0daa7a55d59b088ade34cc6c931ee6c72603050b93_insert" AFTER INSERT ON "album_attachment_semantic_events" WHEN typeof(NEW."attempt_id")='real' OR typeof(NEW."event_ordinal")='real' OR typeof(NEW."obligation_id")='real' OR typeof(NEW."binding_id")='real' OR typeof(NEW."binding_revision_before")='real' OR typeof(NEW."binding_revision_after")='real' OR typeof(NEW."obligation_revision_before")='real' OR typeof(NEW."obligation_revision_after")='real' OR typeof(NEW."state")='real' OR typeof(NEW."membership_observed_at_us")='real' OR typeof(NEW."created_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_ea7a4c2c8f3bae26503b1b0daa7a55d59b088ade34cc6c931ee6c72603050b93_update" AFTER UPDATE ON "album_attachment_semantic_events" WHEN typeof(NEW."attempt_id")='real' OR typeof(NEW."event_ordinal")='real' OR typeof(NEW."obligation_id")='real' OR typeof(NEW."binding_id")='real' OR typeof(NEW."binding_revision_before")='real' OR typeof(NEW."binding_revision_after")='real' OR typeof(NEW."obligation_revision_before")='real' OR typeof(NEW."obligation_revision_after")='real' OR typeof(NEW."state")='real' OR typeof(NEW."membership_observed_at_us")='real' OR typeof(NEW."created_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_c17e933031f88a250b13bc4f6c576c01ab3e6316c4ffee5b8711f35a38e99b22_insert" AFTER INSERT ON "album_binding_events" WHEN typeof(NEW."binding_id")='real' OR typeof(NEW."binding_revision")='real' OR typeof(NEW."kind")='real' OR typeof(NEW."title_revision")='real' OR typeof(NEW."desired_title")='real' OR typeof(NEW."flickr_photoset_id")='real' OR typeof(NEW."state")='real' OR typeof(NEW."created_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_c17e933031f88a250b13bc4f6c576c01ab3e6316c4ffee5b8711f35a38e99b22_update" AFTER UPDATE ON "album_binding_events" WHEN typeof(NEW."binding_id")='real' OR typeof(NEW."binding_revision")='real' OR typeof(NEW."kind")='real' OR typeof(NEW."title_revision")='real' OR typeof(NEW."desired_title")='real' OR typeof(NEW."flickr_photoset_id")='real' OR typeof(NEW."state")='real' OR typeof(NEW."created_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_e8c80aaedd60a3b832935706e547061b344130792b93ecf09c941d6c6a996ce0_insert" AFTER INSERT ON "album_bindings" WHEN typeof(NEW."binding_id")='real' OR typeof(NEW."user_id")='real' OR typeof(NEW."service_id")='real' OR typeof(NEW."local_collection_id")='real' OR typeof(NEW."link_revision")='real' OR typeof(NEW."owner_nsid")='real' OR typeof(NEW."first_photo_binding_id")='real' OR typeof(NEW."first_photo_id")='real' OR typeof(NEW."first_obligation_id")='real' OR typeof(NEW."desired_title")='real' OR typeof(NEW."title_revision")='real' OR typeof(NEW."binding_revision")='real' OR typeof(NEW."flickr_photoset_id")='real' OR typeof(NEW."state")='real' OR typeof(NEW."materialization_state")='real' OR typeof(NEW."materialization_revision")='real' OR typeof(NEW."navigation_url")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_e8c80aaedd60a3b832935706e547061b344130792b93ecf09c941d6c6a996ce0_update" AFTER UPDATE ON "album_bindings" WHEN typeof(NEW."binding_id")='real' OR typeof(NEW."user_id")='real' OR typeof(NEW."service_id")='real' OR typeof(NEW."local_collection_id")='real' OR typeof(NEW."link_revision")='real' OR typeof(NEW."owner_nsid")='real' OR typeof(NEW."first_photo_binding_id")='real' OR typeof(NEW."first_photo_id")='real' OR typeof(NEW."first_obligation_id")='real' OR typeof(NEW."desired_title")='real' OR typeof(NEW."title_revision")='real' OR typeof(NEW."binding_revision")='real' OR typeof(NEW."flickr_photoset_id")='real' OR typeof(NEW."state")='real' OR typeof(NEW."materialization_state")='real' OR typeof(NEW."materialization_revision")='real' OR typeof(NEW."navigation_url")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_1ad881faca5dcbdb0e74ff01350411e6dda20c9f9e6cc5fa12b48e1db1beca56_insert" AFTER INSERT ON "album_create_repair_receipts" WHEN typeof(NEW."binding_id")='real' OR typeof(NEW."attempt_id")='real' OR typeof(NEW."expected_binding_revision")='real' OR typeof(NEW."selected_photoset_id")='real' OR typeof(NEW."navigation_url")='real' OR typeof(NEW."owner_nsid")='real' OR typeof(NEW."first_photo_binding_id")='real' OR typeof(NEW."first_photo_id")='real' OR typeof(NEW."link_revision")='real' OR typeof(NEW."grant_generation")='real' OR typeof(NEW."deployment_gate_revision")='real' OR typeof(NEW."user_gate_revision")='real' OR typeof(NEW."lifecycle")='real' OR typeof(NEW."authority_kind")='real' OR typeof(NEW."authority_id")='real' OR typeof(NEW."authority_digest")='real' OR typeof(NEW."owner_sub")='real' OR typeof(NEW."principal_revision")='real' OR typeof(NEW."authority_revision")='real' OR typeof(NEW."context_observed_at_us")='real' OR typeof(NEW."deadline_at_us")='real' OR typeof(NEW."proof_context_ids")='real' OR typeof(NEW."proof_observed_at_us")='real' OR typeof(NEW."request_correlation_id")='real' OR typeof(NEW."provenance")='real' OR typeof(NEW."created_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_1ad881faca5dcbdb0e74ff01350411e6dda20c9f9e6cc5fa12b48e1db1beca56_update" AFTER UPDATE ON "album_create_repair_receipts" WHEN typeof(NEW."binding_id")='real' OR typeof(NEW."attempt_id")='real' OR typeof(NEW."expected_binding_revision")='real' OR typeof(NEW."selected_photoset_id")='real' OR typeof(NEW."navigation_url")='real' OR typeof(NEW."owner_nsid")='real' OR typeof(NEW."first_photo_binding_id")='real' OR typeof(NEW."first_photo_id")='real' OR typeof(NEW."link_revision")='real' OR typeof(NEW."grant_generation")='real' OR typeof(NEW."deployment_gate_revision")='real' OR typeof(NEW."user_gate_revision")='real' OR typeof(NEW."lifecycle")='real' OR typeof(NEW."authority_kind")='real' OR typeof(NEW."authority_id")='real' OR typeof(NEW."authority_digest")='real' OR typeof(NEW."owner_sub")='real' OR typeof(NEW."principal_revision")='real' OR typeof(NEW."authority_revision")='real' OR typeof(NEW."context_observed_at_us")='real' OR typeof(NEW."deadline_at_us")='real' OR typeof(NEW."proof_context_ids")='real' OR typeof(NEW."proof_observed_at_us")='real' OR typeof(NEW."request_correlation_id")='real' OR typeof(NEW."provenance")='real' OR typeof(NEW."created_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_a1ddb052bc3a2877c4d476ee24a0becacdf4559be5923e978fcf143ea3888446_insert" AFTER INSERT ON "album_local_removal_receipts" WHEN typeof(NEW."binding_id")='real' OR typeof(NEW."expected_binding_revision")='real' OR typeof(NEW."accepted_binding_revision")='real' OR typeof(NEW."acknowledged_create_attempt_id")='real' OR typeof(NEW."archived_at_us")='real' OR typeof(NEW."installation_id")='real' OR typeof(NEW."credential_digest")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_a1ddb052bc3a2877c4d476ee24a0becacdf4559be5923e978fcf143ea3888446_update" AFTER UPDATE ON "album_local_removal_receipts" WHEN typeof(NEW."binding_id")='real' OR typeof(NEW."expected_binding_revision")='real' OR typeof(NEW."accepted_binding_revision")='real' OR typeof(NEW."acknowledged_create_attempt_id")='real' OR typeof(NEW."archived_at_us")='real' OR typeof(NEW."installation_id")='real' OR typeof(NEW."credential_digest")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_aa8a0ea368e35ebb0dac6c86b61d1831c0416172b9032657df31524f8dee7f8b_insert" AFTER INSERT ON "album_materialization_attempts" WHEN typeof(NEW."attempt_id")='real' OR typeof(NEW."binding_id")='real' OR typeof(NEW."lease_id")='real' OR typeof(NEW."epoch")='real' OR typeof(NEW."user_id")='real' OR typeof(NEW."owner_nsid")='real' OR typeof(NEW."photo_binding_id")='real' OR typeof(NEW."photo_id")='real' OR typeof(NEW."link_revision")='real' OR typeof(NEW."grant_generation")='real' OR typeof(NEW."desired_title")='real' OR typeof(NEW."title_revision")='real' OR typeof(NEW."deployment_gate_revision")='real' OR typeof(NEW."user_gate_revision")='real' OR typeof(NEW."started_at_us")='real' OR typeof(NEW."invocation_deadline_at_us")='real' OR typeof(NEW."lease_expires_at_us")='real' OR typeof(NEW."state")='real' OR typeof(NEW."dispatch_count")='real' OR typeof(NEW."dispatch_started_at_us")='real' OR typeof(NEW."pre_context_ids")='real' OR typeof(NEW."pre_context_observed_at_us")='real' OR typeof(NEW."received_photoset_id")='real' OR typeof(NEW."received_navigation_url")='real' OR typeof(NEW."received_at_us")='real' OR typeof(NEW."completed_at_us")='real' OR typeof(NEW."photoset_id")='real' OR typeof(NEW."navigation_url")='real' OR typeof(NEW."proof_context_ids")='real' OR typeof(NEW."proof_owner_nsid")='real' OR typeof(NEW."proof_photo_id")='real' OR typeof(NEW."proof_observed_at_us")='real' OR typeof(NEW."flickr_code")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_aa8a0ea368e35ebb0dac6c86b61d1831c0416172b9032657df31524f8dee7f8b_update" AFTER UPDATE ON "album_materialization_attempts" WHEN typeof(NEW."attempt_id")='real' OR typeof(NEW."binding_id")='real' OR typeof(NEW."lease_id")='real' OR typeof(NEW."epoch")='real' OR typeof(NEW."user_id")='real' OR typeof(NEW."owner_nsid")='real' OR typeof(NEW."photo_binding_id")='real' OR typeof(NEW."photo_id")='real' OR typeof(NEW."link_revision")='real' OR typeof(NEW."grant_generation")='real' OR typeof(NEW."desired_title")='real' OR typeof(NEW."title_revision")='real' OR typeof(NEW."deployment_gate_revision")='real' OR typeof(NEW."user_gate_revision")='real' OR typeof(NEW."started_at_us")='real' OR typeof(NEW."invocation_deadline_at_us")='real' OR typeof(NEW."lease_expires_at_us")='real' OR typeof(NEW."state")='real' OR typeof(NEW."dispatch_count")='real' OR typeof(NEW."dispatch_started_at_us")='real' OR typeof(NEW."pre_context_ids")='real' OR typeof(NEW."pre_context_observed_at_us")='real' OR typeof(NEW."received_photoset_id")='real' OR typeof(NEW."received_navigation_url")='real' OR typeof(NEW."received_at_us")='real' OR typeof(NEW."completed_at_us")='real' OR typeof(NEW."photoset_id")='real' OR typeof(NEW."navigation_url")='real' OR typeof(NEW."proof_context_ids")='real' OR typeof(NEW."proof_owner_nsid")='real' OR typeof(NEW."proof_photo_id")='real' OR typeof(NEW."proof_observed_at_us")='real' OR typeof(NEW."flickr_code")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_3539e851a6a31d05864e253a9f27de4d1aeab848def8bb199f0e1d58188f10f2_insert" AFTER INSERT ON "album_materialization_events" WHEN typeof(NEW."attempt_id")='real' OR typeof(NEW."event_ordinal")='real' OR typeof(NEW."state")='real' OR typeof(NEW."epoch")='real' OR typeof(NEW."dispatch_count")='real' OR typeof(NEW."dispatch_started_at_us")='real' OR typeof(NEW."created_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_3539e851a6a31d05864e253a9f27de4d1aeab848def8bb199f0e1d58188f10f2_update" AFTER UPDATE ON "album_materialization_events" WHEN typeof(NEW."attempt_id")='real' OR typeof(NEW."event_ordinal")='real' OR typeof(NEW."state")='real' OR typeof(NEW."epoch")='real' OR typeof(NEW."dispatch_count")='real' OR typeof(NEW."dispatch_started_at_us")='real' OR typeof(NEW."created_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_407daaa034f0d7f7bfd38803407183996d3d51b1e7b6d42908bf111c499fd8cd_insert" AFTER INSERT ON "album_obligation_events" WHEN typeof(NEW."obligation_id")='real' OR typeof(NEW."obligation_revision")='real' OR typeof(NEW."kind")='real' OR typeof(NEW."state")='real' OR typeof(NEW."local_relationship")='real' OR typeof(NEW."created_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_407daaa034f0d7f7bfd38803407183996d3d51b1e7b6d42908bf111c499fd8cd_update" AFTER UPDATE ON "album_obligation_events" WHEN typeof(NEW."obligation_id")='real' OR typeof(NEW."obligation_revision")='real' OR typeof(NEW."kind")='real' OR typeof(NEW."state")='real' OR typeof(NEW."local_relationship")='real' OR typeof(NEW."created_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_32c2aa5e4413b3bc0f1493678649b1213f77162fb4e0f3a62fdfc2a6486193e8_insert" AFTER INSERT ON "album_photo_local_removal_receipts" WHEN typeof(NEW."obligation_id")='real' OR typeof(NEW."binding_id")='real' OR typeof(NEW."photo_binding_id")='real' OR typeof(NEW."expected_binding_revision")='real' OR typeof(NEW."expected_obligation_revision")='real' OR typeof(NEW."accepted_binding_revision")='real' OR typeof(NEW."archived_obligation_revision")='real' OR typeof(NEW."source")='real' OR typeof(NEW."archived_at_us")='real' OR typeof(NEW."installation_id")='real' OR typeof(NEW."credential_digest")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_32c2aa5e4413b3bc0f1493678649b1213f77162fb4e0f3a62fdfc2a6486193e8_update" AFTER UPDATE ON "album_photo_local_removal_receipts" WHEN typeof(NEW."obligation_id")='real' OR typeof(NEW."binding_id")='real' OR typeof(NEW."photo_binding_id")='real' OR typeof(NEW."expected_binding_revision")='real' OR typeof(NEW."expected_obligation_revision")='real' OR typeof(NEW."accepted_binding_revision")='real' OR typeof(NEW."archived_obligation_revision")='real' OR typeof(NEW."source")='real' OR typeof(NEW."archived_at_us")='real' OR typeof(NEW."installation_id")='real' OR typeof(NEW."credential_digest")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_02ae843bb3d178342113c450354e6f18c594509d1eb8dccbce2c90f085860f67_insert" AFTER INSERT ON "album_photo_obligations" WHEN typeof(NEW."obligation_id")='real' OR typeof(NEW."album_binding_id")='real' OR typeof(NEW."photo_binding_id")='real' OR typeof(NEW."photo_id")='real' OR typeof(NEW."obligation_revision")='real' OR typeof(NEW."state")='real' OR typeof(NEW."local_relationship")='real' OR typeof(NEW."admission_binding_revision")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_02ae843bb3d178342113c450354e6f18c594509d1eb8dccbce2c90f085860f67_update" AFTER UPDATE ON "album_photo_obligations" WHEN typeof(NEW."obligation_id")='real' OR typeof(NEW."album_binding_id")='real' OR typeof(NEW."photo_binding_id")='real' OR typeof(NEW."photo_id")='real' OR typeof(NEW."obligation_revision")='real' OR typeof(NEW."state")='real' OR typeof(NEW."local_relationship")='real' OR typeof(NEW."admission_binding_revision")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_3b9442caf5d6e0cfd04ae2e39dd00285e2f22dfb403f3f331b71dc1addab21d6_insert" AFTER INSERT ON "album_title_attempts" WHEN typeof(NEW."attempt_id")='real' OR typeof(NEW."binding_id")='real' OR typeof(NEW."lease_id")='real' OR typeof(NEW."epoch")='real' OR typeof(NEW."user_id")='real' OR typeof(NEW."owner_nsid")='real' OR typeof(NEW."photoset_id")='real' OR typeof(NEW."link_revision")='real' OR typeof(NEW."grant_generation")='real' OR typeof(NEW."desired_title")='real' OR typeof(NEW."title_revision")='real' OR typeof(NEW."binding_revision")='real' OR typeof(NEW."lease_binding_revision")='real' OR typeof(NEW."deployment_gate_revision")='real' OR typeof(NEW."user_gate_revision")='real' OR typeof(NEW."attempt_number")='real' OR typeof(NEW."started_at_us")='real' OR typeof(NEW."lease_expires_at_us")='real' OR typeof(NEW."invocation_deadline_at_us")='real' OR typeof(NEW."next_read_at_us")='real' OR typeof(NEW."state")='real' OR typeof(NEW."dispatch_count")='real' OR typeof(NEW."read_count")='real' OR typeof(NEW."pre_dispatch_title")='real' OR typeof(NEW."dispatch_started_at_us")='real' OR typeof(NEW."result_class")='real' OR typeof(NEW."observed_title")='real' OR typeof(NEW."observed_at_us")='real' OR typeof(NEW."completed_at_us")='real' OR typeof(NEW."satisfied_title_revision")='real' OR typeof(NEW."remote_missing")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_3b9442caf5d6e0cfd04ae2e39dd00285e2f22dfb403f3f331b71dc1addab21d6_update" AFTER UPDATE ON "album_title_attempts" WHEN typeof(NEW."attempt_id")='real' OR typeof(NEW."binding_id")='real' OR typeof(NEW."lease_id")='real' OR typeof(NEW."epoch")='real' OR typeof(NEW."user_id")='real' OR typeof(NEW."owner_nsid")='real' OR typeof(NEW."photoset_id")='real' OR typeof(NEW."link_revision")='real' OR typeof(NEW."grant_generation")='real' OR typeof(NEW."desired_title")='real' OR typeof(NEW."title_revision")='real' OR typeof(NEW."binding_revision")='real' OR typeof(NEW."lease_binding_revision")='real' OR typeof(NEW."deployment_gate_revision")='real' OR typeof(NEW."user_gate_revision")='real' OR typeof(NEW."attempt_number")='real' OR typeof(NEW."started_at_us")='real' OR typeof(NEW."lease_expires_at_us")='real' OR typeof(NEW."invocation_deadline_at_us")='real' OR typeof(NEW."next_read_at_us")='real' OR typeof(NEW."state")='real' OR typeof(NEW."dispatch_count")='real' OR typeof(NEW."read_count")='real' OR typeof(NEW."pre_dispatch_title")='real' OR typeof(NEW."dispatch_started_at_us")='real' OR typeof(NEW."result_class")='real' OR typeof(NEW."observed_title")='real' OR typeof(NEW."observed_at_us")='real' OR typeof(NEW."completed_at_us")='real' OR typeof(NEW."satisfied_title_revision")='real' OR typeof(NEW."remote_missing")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_b32939189392c5b459ea9746f3b1b36b08d8d682d1e9eec3b75ffa417a676509_insert" AFTER INSERT ON "album_title_events" WHEN typeof(NEW."attempt_id")='real' OR typeof(NEW."event_ordinal")='real' OR typeof(NEW."state")='real' OR typeof(NEW."epoch")='real' OR typeof(NEW."dispatch_count")='real' OR typeof(NEW."read_count")='real' OR typeof(NEW."semantic_change")='real' OR typeof(NEW."created_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_b32939189392c5b459ea9746f3b1b36b08d8d682d1e9eec3b75ffa417a676509_update" AFTER UPDATE ON "album_title_events" WHEN typeof(NEW."attempt_id")='real' OR typeof(NEW."event_ordinal")='real' OR typeof(NEW."state")='real' OR typeof(NEW."epoch")='real' OR typeof(NEW."dispatch_count")='real' OR typeof(NEW."read_count")='real' OR typeof(NEW."semantic_change")='real' OR typeof(NEW."created_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_bdb47aec0d41307e59a4b3b06083eac620994de283800c76f02275247b4ede96_insert" AFTER INSERT ON "album_title_receipts" WHEN typeof(NEW."binding_id")='real' OR typeof(NEW."title_revision")='real' OR typeof(NEW."expected_binding_revision")='real' OR typeof(NEW."expected_title_revision")='real' OR typeof(NEW."desired_title")='real' OR typeof(NEW."accepted_binding_revision")='real' OR typeof(NEW."installation_id")='real' OR typeof(NEW."credential_digest")='real' OR typeof(NEW."accepted_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_bdb47aec0d41307e59a4b3b06083eac620994de283800c76f02275247b4ede96_update" AFTER UPDATE ON "album_title_receipts" WHEN typeof(NEW."binding_id")='real' OR typeof(NEW."title_revision")='real' OR typeof(NEW."expected_binding_revision")='real' OR typeof(NEW."expected_title_revision")='real' OR typeof(NEW."desired_title")='real' OR typeof(NEW."accepted_binding_revision")='real' OR typeof(NEW."installation_id")='real' OR typeof(NEW."credential_digest")='real' OR typeof(NEW."accepted_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_285a359146e56f984de0ada7e6c8aedeccc9c3cc2165607d16385883b76c612a_insert" AFTER INSERT ON "album_title_semantic_events" WHEN typeof(NEW."binding_id")='real' OR typeof(NEW."binding_revision_before")='real' OR typeof(NEW."binding_revision_after")='real' OR typeof(NEW."attempt_id")='real' OR typeof(NEW."epoch")='real' OR typeof(NEW."event_ordinal")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_285a359146e56f984de0ada7e6c8aedeccc9c3cc2165607d16385883b76c612a_update" AFTER UPDATE ON "album_title_semantic_events" WHEN typeof(NEW."binding_id")='real' OR typeof(NEW."binding_revision_before")='real' OR typeof(NEW."binding_revision_after")='real' OR typeof(NEW."attempt_id")='real' OR typeof(NEW."epoch")='real' OR typeof(NEW."event_ordinal")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_c1e6d07d96996180fed0bbd4535899cd535212fb2becc95006cf757708a19739_insert" AFTER INSERT ON "attempt_dispatches" WHEN typeof(NEW."attempt_id")='real' OR typeof(NEW."started_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_c1e6d07d96996180fed0bbd4535899cd535212fb2becc95006cf757708a19739_update" AFTER UPDATE ON "attempt_dispatches" WHEN typeof(NEW."attempt_id")='real' OR typeof(NEW."started_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_91d03c1ae092bc0da9fa47cb5e67dd6117c8716ed43ba96649a51aca0fb2d2d8_insert" AFTER INSERT ON "attempt_membership" WHEN typeof(NEW."attempt_id")='real' OR typeof(NEW."target_absent")='real' OR typeof(NEW."observed_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_91d03c1ae092bc0da9fa47cb5e67dd6117c8716ed43ba96649a51aca0fb2d2d8_update" AFTER UPDATE ON "attempt_membership" WHEN typeof(NEW."attempt_id")='real' OR typeof(NEW."target_absent")='real' OR typeof(NEW."observed_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_6b5f54996cb756b588f5dcc5e354b251b2f28c5345e94a8c1277ced8f5b78a2f_insert" AFTER INSERT ON "attempt_preflights" WHEN typeof(NEW."attempt_id")='real' OR typeof(NEW."moderated")='real' OR typeof(NEW."observed_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_6b5f54996cb756b588f5dcc5e354b251b2f28c5345e94a8c1277ced8f5b78a2f_update" AFTER UPDATE ON "attempt_preflights" WHEN typeof(NEW."attempt_id")='real' OR typeof(NEW."moderated")='real' OR typeof(NEW."observed_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_53d355bddfd1f451c8d778b8ec8b5967e6b2d739c3b98d721011c411ea207c59_insert" AFTER INSERT ON "attempt_resolutions" WHEN typeof(NEW."attempt_id")='real' OR typeof(NEW."outcome")='real' OR typeof(NEW."reason")='real' OR typeof(NEW."completed_at_us")='real' OR typeof(NEW."flickr_code")='real' OR typeof(NEW."observed_age_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_53d355bddfd1f451c8d778b8ec8b5967e6b2d739c3b98d721011c411ea207c59_update" AFTER UPDATE ON "attempt_resolutions" WHEN typeof(NEW."attempt_id")='real' OR typeof(NEW."outcome")='real' OR typeof(NEW."reason")='real' OR typeof(NEW."completed_at_us")='real' OR typeof(NEW."flickr_code")='real' OR typeof(NEW."observed_age_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_14cca081ca09d1ec9f604d58abf95d1d70bd30d21156dff68d1ea96e9b91f645_insert" AFTER INSERT ON "audit_events" WHEN typeof(NEW."event_id")='real' OR typeof(NEW."user_id")='real' OR typeof(NEW."action")='real' OR typeof(NEW."request_correlation_id")='real' OR typeof(NEW."session_correlation_id")='real' OR typeof(NEW."outcome")='real' OR typeof(NEW."reason")='real' OR typeof(NEW."target_id")='real' OR typeof(NEW."created_at_utc")='real' OR typeof(NEW."source_component")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_14cca081ca09d1ec9f604d58abf95d1d70bd30d21156dff68d1ea96e9b91f645_update" AFTER UPDATE ON "audit_events" WHEN typeof(NEW."event_id")='real' OR typeof(NEW."user_id")='real' OR typeof(NEW."action")='real' OR typeof(NEW."request_correlation_id")='real' OR typeof(NEW."session_correlation_id")='real' OR typeof(NEW."outcome")='real' OR typeof(NEW."reason")='real' OR typeof(NEW."target_id")='real' OR typeof(NEW."created_at_utc")='real' OR typeof(NEW."source_component")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_0427e27da46b4591575084c5235e9fa400217e38d160f3b38bbe193620dca6c5_insert" AFTER INSERT ON "auth_cost_events" WHEN typeof(NEW."event_id")='real' OR typeof(NEW."source_key")='real' OR typeof(NEW."route")='real' OR typeof(NEW."created_at_us")='real' OR typeof(NEW."invalid_or_inflight")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_0427e27da46b4591575084c5235e9fa400217e38d160f3b38bbe193620dca6c5_update" AFTER UPDATE ON "auth_cost_events" WHEN typeof(NEW."event_id")='real' OR typeof(NEW."source_key")='real' OR typeof(NEW."route")='real' OR typeof(NEW."created_at_us")='real' OR typeof(NEW."invalid_or_inflight")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_35dd784868c1d0acd9546bc05cb0cd348840705c868d4ad362afb65dcabd1101_insert" AFTER INSERT ON "auth_source_buckets" WHEN typeof(NEW."source_key")='real' OR typeof(NEW."credit_us")='real' OR typeof(NEW."updated_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_35dd784868c1d0acd9546bc05cb0cd348840705c868d4ad362afb65dcabd1101_update" AFTER UPDATE ON "auth_source_buckets" WHEN typeof(NEW."source_key")='real' OR typeof(NEW."credit_us")='real' OR typeof(NEW."updated_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_85b81c8453dd2d947e3f0cbbea74b910312570c1dca7716aca58ebaedf4ef7bb_insert" AFTER INSERT ON "deployment_conformance" WHEN typeof(NEW."artifact_sha2_256")='real' OR typeof(NEW."contract_sha2_256")='real' OR typeof(NEW."evidence_sha2_256")='real' OR typeof(NEW."verified_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_85b81c8453dd2d947e3f0cbbea74b910312570c1dca7716aca58ebaedf4ef7bb_update" AFTER UPDATE ON "deployment_conformance" WHEN typeof(NEW."artifact_sha2_256")='real' OR typeof(NEW."contract_sha2_256")='real' OR typeof(NEW."evidence_sha2_256")='real' OR typeof(NEW."verified_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_c37eb993967dd8e3fefb3ea132a0d788374b210367edc5aeed63997d83229514_insert" AFTER INSERT ON "fga_users" WHEN typeof(NEW."user_id")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_c37eb993967dd8e3fefb3ea132a0d788374b210367edc5aeed63997d83229514_update" AFTER UPDATE ON "fga_users" WHEN typeof(NEW."user_id")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_53f750331dba5c305819db6bb6fc40cbed5de5cec7231fb9af6bf3994195edaf_insert" AFTER INSERT ON "flickr_connection_state" WHEN typeof(NEW."user_id")='real' OR typeof(NEW."state")='real' OR typeof(NEW."local_state")='real' OR typeof(NEW."verified_permission")='real' OR typeof(NEW."verified_at_us")='real' OR typeof(NEW."external_removal")='real' OR typeof(NEW."operation_id")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_53f750331dba5c305819db6bb6fc40cbed5de5cec7231fb9af6bf3994195edaf_update" AFTER UPDATE ON "flickr_connection_state" WHEN typeof(NEW."user_id")='real' OR typeof(NEW."state")='real' OR typeof(NEW."local_state")='real' OR typeof(NEW."verified_permission")='real' OR typeof(NEW."verified_at_us")='real' OR typeof(NEW."external_removal")='real' OR typeof(NEW."operation_id")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_38a61ccda096f2c36b6c2ba420946867cbe6aae555c2d3fc88099099394c6050_insert" AFTER INSERT ON "flickr_lifecycle_operations" WHEN typeof(NEW."operation_id")='real' OR typeof(NEW."user_id")='real' OR typeof(NEW."kind")='real' OR typeof(NEW."phase")='real' OR typeof(NEW."generation")='real' OR typeof(NEW."retiring_generation")='real' OR typeof(NEW."preserve_relink")='real' OR typeof(NEW."expected_revision")='real' OR typeof(NEW."created_at_us")='real' OR typeof(NEW."completed_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_38a61ccda096f2c36b6c2ba420946867cbe6aae555c2d3fc88099099394c6050_update" AFTER UPDATE ON "flickr_lifecycle_operations" WHEN typeof(NEW."operation_id")='real' OR typeof(NEW."user_id")='real' OR typeof(NEW."kind")='real' OR typeof(NEW."phase")='real' OR typeof(NEW."generation")='real' OR typeof(NEW."retiring_generation")='real' OR typeof(NEW."preserve_relink")='real' OR typeof(NEW."expected_revision")='real' OR typeof(NEW."created_at_us")='real' OR typeof(NEW."completed_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_543201599f50ceb3f2d68804122a06a7c132e11192c89074ff9f3d31ba7df1bb_insert" AFTER INSERT ON "flickr_links" WHEN typeof(NEW."user_id")='real' OR typeof(NEW."owner_nsid")='real' OR typeof(NEW."link_revision")='real' OR typeof(NEW."state")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_543201599f50ceb3f2d68804122a06a7c132e11192c89074ff9f3d31ba7df1bb_update" AFTER UPDATE ON "flickr_links" WHEN typeof(NEW."user_id")='real' OR typeof(NEW."owner_nsid")='real' OR typeof(NEW."link_revision")='real' OR typeof(NEW."state")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_8ec237d10f1a16a046d98cfb7cef08415eabc50b4b935ee15ef75bae3acecaa6_insert" AFTER INSERT ON "flickr_native_credentials" WHEN typeof(NEW."user_id")='real' OR typeof(NEW."active_generation")='real' OR typeof(NEW."link_revision")='real' OR typeof(NEW."verified_owner_nsid")='real' OR typeof(NEW."verified_permission")='real' OR typeof(NEW."operation_id")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_8ec237d10f1a16a046d98cfb7cef08415eabc50b4b935ee15ef75bae3acecaa6_update" AFTER UPDATE ON "flickr_native_credentials" WHEN typeof(NEW."user_id")='real' OR typeof(NEW."active_generation")='real' OR typeof(NEW."link_revision")='real' OR typeof(NEW."verified_owner_nsid")='real' OR typeof(NEW."verified_permission")='real' OR typeof(NEW."operation_id")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_37b34418c5d014b87eec00e905bf16cb0cc98be85d561fc6fc981f9e411d04f4_insert" AFTER INSERT ON "flickr_oauth_transactions" WHEN typeof(NEW."transaction_id")='real' OR typeof(NEW."user_id")='real' OR typeof(NEW."session_id")='real' OR typeof(NEW."state_digest")='real' OR typeof(NEW."request_token_digest")='real' OR typeof(NEW."slot")='real' OR typeof(NEW."generation")='real' OR typeof(NEW."expected_revision")='real' OR typeof(NEW."phase")='real' OR typeof(NEW."created_at_us")='real' OR typeof(NEW."expires_at_us")='real' OR typeof(NEW."operation_id")='real' OR typeof(NEW."retirement_generation")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_37b34418c5d014b87eec00e905bf16cb0cc98be85d561fc6fc981f9e411d04f4_update" AFTER UPDATE ON "flickr_oauth_transactions" WHEN typeof(NEW."transaction_id")='real' OR typeof(NEW."user_id")='real' OR typeof(NEW."session_id")='real' OR typeof(NEW."state_digest")='real' OR typeof(NEW."request_token_digest")='real' OR typeof(NEW."slot")='real' OR typeof(NEW."generation")='real' OR typeof(NEW."expected_revision")='real' OR typeof(NEW."phase")='real' OR typeof(NEW."created_at_us")='real' OR typeof(NEW."expires_at_us")='real' OR typeof(NEW."operation_id")='real' OR typeof(NEW."retirement_generation")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_c5a2a1fbc762ba7bedf732f0aeb0bc665f3d0b2822d6df7b7fd8530d647ccfe4_insert" AFTER INSERT ON "flickr_rate_reservations" WHEN typeof(NEW."reservation_id")='real' OR typeof(NEW."attempt_id")='real' OR typeof(NEW."window_id")='real' OR typeof(NEW."expires_at_us")='real' OR typeof(NEW."released")='real' OR typeof(NEW."consumed_slots")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_c5a2a1fbc762ba7bedf732f0aeb0bc665f3d0b2822d6df7b7fd8530d647ccfe4_update" AFTER UPDATE ON "flickr_rate_reservations" WHEN typeof(NEW."reservation_id")='real' OR typeof(NEW."attempt_id")='real' OR typeof(NEW."window_id")='real' OR typeof(NEW."expires_at_us")='real' OR typeof(NEW."released")='real' OR typeof(NEW."consumed_slots")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_bc7500ae59761f00811b862bec1dbb6eaddbd61dd383e6cc07883307c5f70e75_insert" AFTER INSERT ON "flickr_rate_window" WHEN typeof(NEW."singleton")='real' OR typeof(NEW."window_id")='real' OR typeof(NEW."capacity")='real' OR typeof(NEW."window_ms")='real' OR typeof(NEW."expires_at_us")='real' OR typeof(NEW."reserved_slots")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_bc7500ae59761f00811b862bec1dbb6eaddbd61dd383e6cc07883307c5f70e75_update" AFTER UPDATE ON "flickr_rate_window" WHEN typeof(NEW."singleton")='real' OR typeof(NEW."window_id")='real' OR typeof(NEW."capacity")='real' OR typeof(NEW."window_ms")='real' OR typeof(NEW."expires_at_us")='real' OR typeof(NEW."reserved_slots")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_dee0c5d0463d8f022a4963ce928f8fd44dd75ecaeed0002f2038fd919806f07e_insert" AFTER INSERT ON "flickr_write_gate_events" WHEN typeof(NEW."event_id")='real' OR typeof(NEW."scope")='real' OR typeof(NEW."scope_id")='real' OR typeof(NEW."revision")='real' OR typeof(NEW."reason")='real' OR typeof(NEW."flickr_code")='real' OR typeof(NEW."attempt_id")='real' OR typeof(NEW."created_at_us")='real' OR typeof(NEW."artifact_sha2_256")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_dee0c5d0463d8f022a4963ce928f8fd44dd75ecaeed0002f2038fd919806f07e_update" AFTER UPDATE ON "flickr_write_gate_events" WHEN typeof(NEW."event_id")='real' OR typeof(NEW."scope")='real' OR typeof(NEW."scope_id")='real' OR typeof(NEW."revision")='real' OR typeof(NEW."reason")='real' OR typeof(NEW."flickr_code")='real' OR typeof(NEW."attempt_id")='real' OR typeof(NEW."created_at_us")='real' OR typeof(NEW."artifact_sha2_256")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_d91c1d78ecbe226b326cd5df47f7e4d741f887984695f0d6ad5db6293db4427e_insert" AFTER INSERT ON "flickr_write_gates" WHEN typeof(NEW."scope")='real' OR typeof(NEW."scope_id")='real' OR typeof(NEW."enabled")='real' OR typeof(NEW."revision")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_d91c1d78ecbe226b326cd5df47f7e4d741f887984695f0d6ad5db6293db4427e_update" AFTER UPDATE ON "flickr_write_gates" WHEN typeof(NEW."scope")='real' OR typeof(NEW."scope_id")='real' OR typeof(NEW."enabled")='real' OR typeof(NEW."revision")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_d7d7fcc462ddd12f1b0da08157f448e382af37486e668c7d0a64a69753d613d9_insert" AFTER INSERT ON "google_jwks_cache" WHEN typeof(NEW."singleton")='real' OR typeof(NEW."keys_json")='real' OR typeof(NEW."expires_at_us")='real' OR typeof(NEW."refresh_after_us")='real' OR typeof(NEW."refresh_owner")='real' OR typeof(NEW."refresh_until_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_d7d7fcc462ddd12f1b0da08157f448e382af37486e668c7d0a64a69753d613d9_update" AFTER UPDATE ON "google_jwks_cache" WHEN typeof(NEW."singleton")='real' OR typeof(NEW."keys_json")='real' OR typeof(NEW."expires_at_us")='real' OR typeof(NEW."refresh_after_us")='real' OR typeof(NEW."refresh_owner")='real' OR typeof(NEW."refresh_until_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_5a5397d06042eb90da7e648d782460a061209839d206898b12c7717cc2f7dc5c_insert" AFTER INSERT ON "google_login_transactions" WHEN typeof(NEW."state_digest")='real' OR typeof(NEW."nonce_digest")='real' OR typeof(NEW."purpose")='real' OR typeof(NEW."bound_session_id")='real' OR typeof(NEW."user_id")='real' OR typeof(NEW."created_at_us")='real' OR typeof(NEW."expires_at_us")='real' OR typeof(NEW."consumed_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_5a5397d06042eb90da7e648d782460a061209839d206898b12c7717cc2f7dc5c_update" AFTER UPDATE ON "google_login_transactions" WHEN typeof(NEW."state_digest")='real' OR typeof(NEW."nonce_digest")='real' OR typeof(NEW."purpose")='real' OR typeof(NEW."bound_session_id")='real' OR typeof(NEW."user_id")='real' OR typeof(NEW."created_at_us")='real' OR typeof(NEW."expires_at_us")='real' OR typeof(NEW."consumed_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_6048967b8db4735cd43fd93cb277a9fd5ac71d3ed1fe4e85ca007670770a1e34_insert" AFTER INSERT ON "group_partitions" WHEN typeof(NEW."partition_id")='real' OR typeof(NEW."user_id")='real' OR typeof(NEW."group_id")='real' OR typeof(NEW."next_enqueue_ordinal")='real' OR typeof(NEW."next_work_not_before_us")='real' OR typeof(NEW."wake_revision")='real' OR typeof(NEW."lease_id")='real' OR typeof(NEW."lease_generation")='real' OR typeof(NEW."lease_expires_at_us")='real' OR typeof(NEW."lease_started_at_us")='real' OR typeof(NEW."invocation_deadline_at_us")='real' OR typeof(NEW."last_claim_at_us")='real' OR typeof(NEW."next_probe_not_before_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_6048967b8db4735cd43fd93cb277a9fd5ac71d3ed1fe4e85ca007670770a1e34_update" AFTER UPDATE ON "group_partitions" WHEN typeof(NEW."partition_id")='real' OR typeof(NEW."user_id")='real' OR typeof(NEW."group_id")='real' OR typeof(NEW."next_enqueue_ordinal")='real' OR typeof(NEW."next_work_not_before_us")='real' OR typeof(NEW."wake_revision")='real' OR typeof(NEW."lease_id")='real' OR typeof(NEW."lease_generation")='real' OR typeof(NEW."lease_expires_at_us")='real' OR typeof(NEW."lease_started_at_us")='real' OR typeof(NEW."invocation_deadline_at_us")='real' OR typeof(NEW."last_claim_at_us")='real' OR typeof(NEW."next_probe_not_before_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_acaf0280fb706019a277d89411f1fa7a4ee0685056b4b7a255b9d58185fc6214_insert" AFTER INSERT ON "group_refresh" WHEN typeof(NEW."user_id")='real' OR typeof(NEW."job_id")='real' OR typeof(NEW."installation_id")='real' OR typeof(NEW."version_id")='real' OR typeof(NEW."link_revision")='real' OR typeof(NEW."generation")='real' OR typeof(NEW."state")='real' OR typeof(NEW."admitted_at_us")='real' OR typeof(NEW."deadline_at_us")='real' OR typeof(NEW."failed_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_acaf0280fb706019a277d89411f1fa7a4ee0685056b4b7a255b9d58185fc6214_update" AFTER UPDATE ON "group_refresh" WHEN typeof(NEW."user_id")='real' OR typeof(NEW."job_id")='real' OR typeof(NEW."installation_id")='real' OR typeof(NEW."version_id")='real' OR typeof(NEW."link_revision")='real' OR typeof(NEW."generation")='real' OR typeof(NEW."state")='real' OR typeof(NEW."admitted_at_us")='real' OR typeof(NEW."deadline_at_us")='real' OR typeof(NEW."failed_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_6e76e882f0f654e9cce81bf7434ec8ca8ad45eafc8346828f99f3d4975af1e05_insert" AFTER INSERT ON "group_refresh_rows" WHEN typeof(NEW."user_id")='real' OR typeof(NEW."job_id")='real' OR typeof(NEW."group_id")='real' OR typeof(NEW."display_name")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_6e76e882f0f654e9cce81bf7434ec8ca8ad45eafc8346828f99f3d4975af1e05_update" AFTER UPDATE ON "group_refresh_rows" WHEN typeof(NEW."user_id")='real' OR typeof(NEW."job_id")='real' OR typeof(NEW."group_id")='real' OR typeof(NEW."display_name")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_e6f5557b8e0efbf0ac913f0dff6fa162d1d6f358c6663323cd5356ffc845478a_insert" AFTER INSERT ON "group_snapshot_rows" WHEN typeof(NEW."user_id")='real' OR typeof(NEW."group_id")='real' OR typeof(NEW."display_name")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_e6f5557b8e0efbf0ac913f0dff6fa162d1d6f358c6663323cd5356ffc845478a_update" AFTER UPDATE ON "group_snapshot_rows" WHEN typeof(NEW."user_id")='real' OR typeof(NEW."group_id")='real' OR typeof(NEW."display_name")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_98693af67986275fd0297e7a0fd0f1a88c7b9a001ac8aa3eac6d06332d115a9e_insert" AFTER INSERT ON "group_snapshots" WHEN typeof(NEW."user_id")='real' OR typeof(NEW."revision")='real' OR typeof(NEW."refreshed_at_us")='real' OR typeof(NEW."link_revision")='real' OR typeof(NEW."generation")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_98693af67986275fd0297e7a0fd0f1a88c7b9a001ac8aa3eac6d06332d115a9e_update" AFTER UPDATE ON "group_snapshots" WHEN typeof(NEW."user_id")='real' OR typeof(NEW."revision")='real' OR typeof(NEW."refreshed_at_us")='real' OR typeof(NEW."link_revision")='real' OR typeof(NEW."generation")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_f5ed9083eced14217aa0621941898bd8a35d0709c6b9be911b2474acb73b4fb8_insert" AFTER INSERT ON "installation_credential_versions" WHEN typeof(NEW."version_id")='real' OR typeof(NEW."installation_id")='real' OR typeof(NEW."credential_digest")='real' OR typeof(NEW."state")='real' OR typeof(NEW."ordinal")='real' OR typeof(NEW."expires_at_us")='real' OR typeof(NEW."created_at_utc")='real' OR typeof(NEW."current_link")='real' OR typeof(NEW."pending_link")='real' OR typeof(NEW."active_parent")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_f5ed9083eced14217aa0621941898bd8a35d0709c6b9be911b2474acb73b4fb8_update" AFTER UPDATE ON "installation_credential_versions" WHEN typeof(NEW."version_id")='real' OR typeof(NEW."installation_id")='real' OR typeof(NEW."credential_digest")='real' OR typeof(NEW."state")='real' OR typeof(NEW."ordinal")='real' OR typeof(NEW."expires_at_us")='real' OR typeof(NEW."created_at_utc")='real' OR typeof(NEW."current_link")='real' OR typeof(NEW."pending_link")='real' OR typeof(NEW."active_parent")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_31c6554f69f2e9e221ae051d79ecf627dc92552f00d7c5aefd5b69539761941f_insert" AFTER INSERT ON "installation_lifecycle_events" WHEN typeof(NEW."event_id")='real' OR typeof(NEW."installation_id")='real' OR typeof(NEW."version_id")='real' OR typeof(NEW."from_revision")='real' OR typeof(NEW."to_revision")='real' OR typeof(NEW."kind")='real' OR typeof(NEW."created_at_utc")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_31c6554f69f2e9e221ae051d79ecf627dc92552f00d7c5aefd5b69539761941f_update" AFTER UPDATE ON "installation_lifecycle_events" WHEN typeof(NEW."event_id")='real' OR typeof(NEW."installation_id")='real' OR typeof(NEW."version_id")='real' OR typeof(NEW."from_revision")='real' OR typeof(NEW."to_revision")='real' OR typeof(NEW."kind")='real' OR typeof(NEW."created_at_utc")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_c050ab2cac577214238155708b82fc4e27dfba98770b445590882dd4a6ae65f6_insert" AFTER INSERT ON "installations" WHEN typeof(NEW."installation_id")='real' OR typeof(NEW."user_id")='real' OR typeof(NEW."credential_class")='real' OR typeof(NEW."label")='real' OR typeof(NEW."state")='real' OR typeof(NEW."revision")='real' OR typeof(NEW."current_version_id")='real' OR typeof(NEW."pending_version_id")='real' OR typeof(NEW."created_at_utc")='real' OR typeof(NEW."revoked_at_utc")='real' OR typeof(NEW."current_kind")='real' OR typeof(NEW."pending_kind")='real' OR typeof(NEW."rotation_due_at_utc")='real' OR typeof(NEW."last_authenticated_at_utc")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_c050ab2cac577214238155708b82fc4e27dfba98770b445590882dd4a6ae65f6_update" AFTER UPDATE ON "installations" WHEN typeof(NEW."installation_id")='real' OR typeof(NEW."user_id")='real' OR typeof(NEW."credential_class")='real' OR typeof(NEW."label")='real' OR typeof(NEW."state")='real' OR typeof(NEW."revision")='real' OR typeof(NEW."current_version_id")='real' OR typeof(NEW."pending_version_id")='real' OR typeof(NEW."created_at_utc")='real' OR typeof(NEW."revoked_at_utc")='real' OR typeof(NEW."current_kind")='real' OR typeof(NEW."pending_kind")='real' OR typeof(NEW."rotation_due_at_utc")='real' OR typeof(NEW."last_authenticated_at_utc")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_ce00d527a17b4a13a31331cd468482b2cc253090aee61c52d831cc1fa446446d_insert" AFTER INSERT ON "maintenance_control" WHEN typeof(NEW."singleton_id")='real' OR typeof(NEW."generation")='real' OR typeof(NEW."state")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_ce00d527a17b4a13a31331cd468482b2cc253090aee61c52d831cc1fa446446d_update" AFTER UPDATE ON "maintenance_control" WHEN typeof(NEW."singleton_id")='real' OR typeof(NEW."generation")='real' OR typeof(NEW."state")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_0c7cd48097169737ff5d0eb8efa8cc5f8618d99cf626ba09f3a24827e29c6187_insert" AFTER INSERT ON "partition_lease_events" WHEN typeof(NEW."event_id")='real' OR typeof(NEW."partition_id")='real' OR typeof(NEW."lease_id")='real' OR typeof(NEW."lease_generation")='real' OR typeof(NEW."kind")='real' OR typeof(NEW."invocation_id")='real' OR typeof(NEW."created_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_0c7cd48097169737ff5d0eb8efa8cc5f8618d99cf626ba09f3a24827e29c6187_update" AFTER UPDATE ON "partition_lease_events" WHEN typeof(NEW."event_id")='real' OR typeof(NEW."partition_id")='real' OR typeof(NEW."lease_id")='real' OR typeof(NEW."lease_generation")='real' OR typeof(NEW."kind")='real' OR typeof(NEW."invocation_id")='real' OR typeof(NEW."created_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_6c74d07136bd00ad126003c88c6661578481794cfb02dec16ee31fbdfb220036_insert" AFTER INSERT ON "photo_binding_events" WHEN typeof(NEW."event_id")='real' OR typeof(NEW."binding_id")='real' OR typeof(NEW."verification_revision")='real' OR typeof(NEW."kind")='real' OR typeof(NEW."created_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_6c74d07136bd00ad126003c88c6661578481794cfb02dec16ee31fbdfb220036_update" AFTER UPDATE ON "photo_binding_events" WHEN typeof(NEW."event_id")='real' OR typeof(NEW."binding_id")='real' OR typeof(NEW."verification_revision")='real' OR typeof(NEW."kind")='real' OR typeof(NEW."created_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_049c8681085f20e777281c06fcccc58a027c22d4934fd7ea0f42d9736a8c7bbd_insert" AFTER INSERT ON "photo_bindings" WHEN typeof(NEW."binding_id")='real' OR typeof(NEW."user_id")='real' OR typeof(NEW."photo_id")='real' OR typeof(NEW."owner_nsid")='real' OR typeof(NEW."link_revision")='real' OR typeof(NEW."verification_revision")='real' OR typeof(NEW."source_kind")='real' OR typeof(NEW."verified_at_us")='real' OR typeof(NEW."last_admission_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_049c8681085f20e777281c06fcccc58a027c22d4934fd7ea0f42d9736a8c7bbd_update" AFTER UPDATE ON "photo_bindings" WHEN typeof(NEW."binding_id")='real' OR typeof(NEW."user_id")='real' OR typeof(NEW."photo_id")='real' OR typeof(NEW."owner_nsid")='real' OR typeof(NEW."link_revision")='real' OR typeof(NEW."verification_revision")='real' OR typeof(NEW."source_kind")='real' OR typeof(NEW."verified_at_us")='real' OR typeof(NEW."last_admission_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_9b9469489fb2390b88a3214aea52e41f72c2bdb19a286702c08fd9f430cd6323_insert" AFTER INSERT ON "photo_membership_observations" WHEN typeof(NEW."binding_id")='real' OR typeof(NEW."revision")='real' OR typeof(NEW."link_revision")='real' OR typeof(NEW."generation")='real' OR typeof(NEW."valid")='real' OR typeof(NEW."observed_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_9b9469489fb2390b88a3214aea52e41f72c2bdb19a286702c08fd9f430cd6323_update" AFTER UPDATE ON "photo_membership_observations" WHEN typeof(NEW."binding_id")='real' OR typeof(NEW."revision")='real' OR typeof(NEW."link_revision")='real' OR typeof(NEW."generation")='real' OR typeof(NEW."valid")='real' OR typeof(NEW."observed_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_caa9f77e5c93ae282759ad5aa6b18f47560efe65834e001397b843b57b41108a_insert" AFTER INSERT ON "photo_membership_rows" WHEN typeof(NEW."binding_id")='real' OR typeof(NEW."group_id")='real' OR typeof(NEW."display_name")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_caa9f77e5c93ae282759ad5aa6b18f47560efe65834e001397b843b57b41108a_update" AFTER UPDATE ON "photo_membership_rows" WHEN typeof(NEW."binding_id")='real' OR typeof(NEW."group_id")='real' OR typeof(NEW."display_name")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_914191bfe46486a39244e6233cd2af4b83218cc7c9737f8edb6ce81a214844fa_insert" AFTER INSERT ON "publish_service_identities" WHEN typeof(NEW."service_id")='real' OR typeof(NEW."user_id")='real' OR typeof(NEW."issuing_installation_id")='real' OR typeof(NEW."link_revision")='real' OR typeof(NEW."owner_nsid")='real' OR typeof(NEW."service_revision")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_914191bfe46486a39244e6233cd2af4b83218cc7c9737f8edb6ce81a214844fa_update" AFTER UPDATE ON "publish_service_identities" WHEN typeof(NEW."service_id")='real' OR typeof(NEW."user_id")='real' OR typeof(NEW."issuing_installation_id")='real' OR typeof(NEW."link_revision")='real' OR typeof(NEW."owner_nsid")='real' OR typeof(NEW."service_revision")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_09344163eab0c87411bedc356b9bed8707e54506cf91e036dbba4b17c6d2175c_insert" AFTER INSERT ON "quota_credit_clocks" WHEN typeof(NEW."batch_id")='real' OR typeof(NEW."now_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_09344163eab0c87411bedc356b9bed8707e54506cf91e036dbba4b17c6d2175c_update" AFTER UPDATE ON "quota_credit_clocks" WHEN typeof(NEW."batch_id")='real' OR typeof(NEW."now_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_71c59928ab4abb1ba5d37e9be4960e064a5afa750260fb0bf2b2ee41ccd0e4a0_insert" AFTER INSERT ON "quota_credit_guards" WHEN typeof(NEW."batch_id")='real' OR typeof(NEW."kind")='real' OR typeof(NEW."invariant_ok")='real' OR typeof(NEW."admitted")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_71c59928ab4abb1ba5d37e9be4960e064a5afa750260fb0bf2b2ee41ccd0e4a0_update" AFTER UPDATE ON "quota_credit_guards" WHEN typeof(NEW."batch_id")='real' OR typeof(NEW."kind")='real' OR typeof(NEW."invariant_ok")='real' OR typeof(NEW."admitted")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_48004daf348aa93dfbb3c9e1836636d8037686439f39490352e7e43995ee480b_insert" AFTER INSERT ON "status_read_buckets" WHEN typeof(NEW."family")='real' OR typeof(NEW."subject_id")='real' OR typeof(NEW."credit_us")='real' OR typeof(NEW."updated_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_48004daf348aa93dfbb3c9e1836636d8037686439f39490352e7e43995ee480b_update" AFTER UPDATE ON "status_read_buckets" WHEN typeof(NEW."family")='real' OR typeof(NEW."subject_id")='real' OR typeof(NEW."credit_us")='real' OR typeof(NEW."updated_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_f0f500d3e02446e6635e6a86726b82a10e1669024bfd2fd080e2b8c129304a3b_insert" AFTER INSERT ON "status_read_events" WHEN typeof(NEW."event_id")='real' OR typeof(NEW."created_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_f0f500d3e02446e6635e6a86726b82a10e1669024bfd2fd080e2b8c129304a3b_update" AFTER UPDATE ON "status_read_events" WHEN typeof(NEW."event_id")='real' OR typeof(NEW."created_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_3d5c1ac14bb578aa548b1b838a3ffb5b4b0b5698ce99987a2d4b79f81178ca96_insert" AFTER INSERT ON "submission_attempts" WHEN typeof(NEW."attempt_id")='real' OR typeof(NEW."intent_id")='real' OR typeof(NEW."ordinal")='real' OR typeof(NEW."lease_id")='real' OR typeof(NEW."lease_generation")='real' OR typeof(NEW."deployment_revision")='real' OR typeof(NEW."user_revision")='real' OR typeof(NEW."link_revision")='real' OR typeof(NEW."created_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_3d5c1ac14bb578aa548b1b838a3ffb5b4b0b5698ce99987a2d4b79f81178ca96_update" AFTER UPDATE ON "submission_attempts" WHEN typeof(NEW."attempt_id")='real' OR typeof(NEW."intent_id")='real' OR typeof(NEW."ordinal")='real' OR typeof(NEW."lease_id")='real' OR typeof(NEW."lease_generation")='real' OR typeof(NEW."deployment_revision")='real' OR typeof(NEW."user_revision")='real' OR typeof(NEW."link_revision")='real' OR typeof(NEW."created_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_d530385b6a50ec0bf12f48092153d494fea06d2138b3808778198937986b7b36_insert" AFTER INSERT ON "submission_blocks" WHEN typeof(NEW."photo_id")='real' OR typeof(NEW."group_id")='real' OR typeof(NEW."first_reason")='real' OR typeof(NEW."source_attempt_id")='real' OR typeof(NEW."created_at_utc")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_d530385b6a50ec0bf12f48092153d494fea06d2138b3808778198937986b7b36_update" AFTER UPDATE ON "submission_blocks" WHEN typeof(NEW."photo_id")='real' OR typeof(NEW."group_id")='real' OR typeof(NEW."first_reason")='real' OR typeof(NEW."source_attempt_id")='real' OR typeof(NEW."created_at_utc")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_8107ef052abdc9ee7edc4f9eb28d1316b39f7bb959ab47c8fd9075e7c43df4bc_insert" AFTER INSERT ON "submission_intent_events" WHEN typeof(NEW."event_id")='real' OR typeof(NEW."intent_id")='real' OR typeof(NEW."kind")='real' OR typeof(NEW."correlation_id")='real' OR typeof(NEW."created_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_8107ef052abdc9ee7edc4f9eb28d1316b39f7bb959ab47c8fd9075e7c43df4bc_update" AFTER UPDATE ON "submission_intent_events" WHEN typeof(NEW."event_id")='real' OR typeof(NEW."intent_id")='real' OR typeof(NEW."kind")='real' OR typeof(NEW."correlation_id")='real' OR typeof(NEW."created_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_37a6b6a4a343b923b4e3cb7c9efba9b01cf304ce077608382f547a7aec59c3c6_insert" AFTER INSERT ON "submission_intents" WHEN typeof(NEW."intent_id")='real' OR typeof(NEW."binding_id")='real' OR typeof(NEW."user_id")='real' OR typeof(NEW."photo_id")='real' OR typeof(NEW."group_id")='real' OR typeof(NEW."partition_id")='real' OR typeof(NEW."enqueue_ordinal")='real' OR typeof(NEW."state")='real' OR typeof(NEW."active_fifo_member")='real' OR typeof(NEW."state_version")='real' OR typeof(NEW."created_at_us")='real' OR typeof(NEW."created_request_id")='real' OR typeof(NEW."next_attempt_not_before_us")='real' OR typeof(NEW."terminal_at_us")='real' OR typeof(NEW."safe_read_failure_count")='real' OR typeof(NEW."add_dispatch_count")='real' OR typeof(NEW."state_changed_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_37a6b6a4a343b923b4e3cb7c9efba9b01cf304ce077608382f547a7aec59c3c6_update" AFTER UPDATE ON "submission_intents" WHEN typeof(NEW."intent_id")='real' OR typeof(NEW."binding_id")='real' OR typeof(NEW."user_id")='real' OR typeof(NEW."photo_id")='real' OR typeof(NEW."group_id")='real' OR typeof(NEW."partition_id")='real' OR typeof(NEW."enqueue_ordinal")='real' OR typeof(NEW."state")='real' OR typeof(NEW."active_fifo_member")='real' OR typeof(NEW."state_version")='real' OR typeof(NEW."created_at_us")='real' OR typeof(NEW."created_request_id")='real' OR typeof(NEW."next_attempt_not_before_us")='real' OR typeof(NEW."terminal_at_us")='real' OR typeof(NEW."safe_read_failure_count")='real' OR typeof(NEW."add_dispatch_count")='real' OR typeof(NEW."state_changed_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_e45fca55c6cf06206f252741cb8ae78783ab1d55459b5a8e0de82417d993507f_insert" AFTER INSERT ON "transaction_guards" WHEN typeof(NEW."transaction_id")='real' OR typeof(NEW."approved")='real' OR typeof(NEW."now_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_e45fca55c6cf06206f252741cb8ae78783ab1d55459b5a8e0de82417d993507f_update" AFTER UPDATE ON "transaction_guards" WHEN typeof(NEW."transaction_id")='real' OR typeof(NEW."approved")='real' OR typeof(NEW."now_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_e7c0c056d5cd90710723c0d3f4e16ab948c76795faa222f3906ff0ce9dd21853_insert" AFTER INSERT ON "upload_ambiguity_resolution_events" WHEN typeof(NEW."authorization_id")='real' OR typeof(NEW."provenance")='real' OR typeof(NEW."binding_origin")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_e7c0c056d5cd90710723c0d3f4e16ab948c76795faa222f3906ff0ce9dd21853_update" AFTER UPDATE ON "upload_ambiguity_resolution_events" WHEN typeof(NEW."authorization_id")='real' OR typeof(NEW."provenance")='real' OR typeof(NEW."binding_origin")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_0a6bbcc05f1dbeb13e8a5d50539c37ee6601fc0b7d4d9c3fb67ee975189b66fd_insert" AFTER INSERT ON "upload_authorizations" WHEN typeof(NEW."authorization_id")='real' OR typeof(NEW."installation_id")='real' OR typeof(NEW."user_id")='real' OR typeof(NEW."issued_at_us")='real' OR typeof(NEW."photo_id")='real' OR typeof(NEW."owner_nsid")='real' OR typeof(NEW."link_revision")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_0a6bbcc05f1dbeb13e8a5d50539c37ee6601fc0b7d4d9c3fb67ee975189b66fd_update" AFTER UPDATE ON "upload_authorizations" WHEN typeof(NEW."authorization_id")='real' OR typeof(NEW."installation_id")='real' OR typeof(NEW."user_id")='real' OR typeof(NEW."issued_at_us")='real' OR typeof(NEW."photo_id")='real' OR typeof(NEW."owner_nsid")='real' OR typeof(NEW."link_revision")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_5b5c01f72aa37e62477c283cb4501caa2586248a01f7e1da22e0003946a6c8f4_insert" AFTER INSERT ON "upload_photo_binding_events" WHEN typeof(NEW."authorization_id")='real' OR typeof(NEW."binding_id")='real' OR typeof(NEW."link_revision")='real' OR typeof(NEW."verification_revision")='real' OR typeof(NEW."observed_public")='real' OR typeof(NEW."verified_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
CREATE TRIGGER "pmb1_no_real_5b5c01f72aa37e62477c283cb4501caa2586248a01f7e1da22e0003946a6c8f4_update" AFTER UPDATE ON "upload_photo_binding_events" WHEN typeof(NEW."authorization_id")='real' OR typeof(NEW."binding_id")='real' OR typeof(NEW."link_revision")='real' OR typeof(NEW."verification_revision")='real' OR typeof(NEW."observed_public")='real' OR typeof(NEW."verified_at_us")='real' OR typeof(NEW."rowid")='real' BEGIN SELECT RAISE(ABORT,'pmb1_no_real'); END;
