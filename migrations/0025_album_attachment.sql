PRAGMA defer_foreign_keys=ON;
DROP TRIGGER album_obligation_event_consistent;
DROP TRIGGER album_obligation_event_no_update;
DROP TRIGGER album_obligation_event_no_delete;
DROP TRIGGER album_obligation_event_no_replace;
CREATE TABLE retained_attachment_obligation_events AS SELECT * FROM album_obligation_events;
DROP TABLE album_obligation_events;
CREATE TABLE album_obligation_events (
 obligation_id TEXT NOT NULL REFERENCES album_photo_obligations(obligation_id) ON DELETE RESTRICT,
 obligation_revision INTEGER NOT NULL CHECK(obligation_revision BETWEEN 1 AND 9007199254740991),
 kind TEXT NOT NULL CHECK(kind IN ('obligation_admitted','relationship_archived','receipt_migrated','membership_verified','attachment_state_changed')),
 state TEXT NOT NULL CHECK(state IN ('waiting_for_album','attachment_pending','membership_verified','attachment_state_changed')),
 local_relationship TEXT NOT NULL CHECK(local_relationship IN ('active','archived')),
 created_at_us INTEGER NOT NULL DEFAULT(CAST(strftime('%s','now') AS INTEGER)*1000000
  + CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000),
 PRIMARY KEY(obligation_id,obligation_revision)
) STRICT;
INSERT INTO album_obligation_events SELECT * FROM retained_attachment_obligation_events;
DROP TABLE retained_attachment_obligation_events;
CREATE TABLE attachment_migration_guard(ok INTEGER NOT NULL CHECK(ok=1)) STRICT;
INSERT INTO attachment_migration_guard SELECT NOT EXISTS(SELECT 1 FROM pragma_foreign_key_check);
DROP TABLE attachment_migration_guard;
PRAGMA defer_foreign_keys=OFF;
CREATE TRIGGER album_obligation_event_consistent BEFORE INSERT ON album_obligation_events
 WHEN NEW.kind='receipt_migrated' OR NOT EXISTS(SELECT 1 FROM album_photo_obligations o
  WHERE o.obligation_id=NEW.obligation_id AND o.obligation_revision=NEW.obligation_revision
   AND o.state=NEW.state AND o.local_relationship=NEW.local_relationship)
  OR (NEW.obligation_revision=1 AND NEW.kind<>'obligation_admitted')
  OR (NEW.obligation_revision>1 AND NEW.kind NOT IN ('membership_verified','relationship_archived','attachment_state_changed'))
  OR (NEW.kind='attachment_state_changed' AND NOT EXISTS(SELECT 1 FROM album_attachment_semantic_events se WHERE se.obligation_id=NEW.obligation_id AND se.obligation_revision_after=NEW.obligation_revision))
 BEGIN SELECT RAISE(ABORT,'album_obligation_event_inconsistent'); END;
CREATE TRIGGER album_obligation_event_no_update BEFORE UPDATE ON album_obligation_events
 BEGIN SELECT RAISE(ABORT,'album_obligation_event_immutable'); END;
CREATE TRIGGER album_obligation_event_no_delete BEFORE DELETE ON album_obligation_events
 BEGIN SELECT RAISE(ABORT,'album_obligation_event_retained'); END;
CREATE TRIGGER album_obligation_event_no_replace BEFORE INSERT ON album_obligation_events
 WHEN EXISTS(SELECT 1 FROM album_obligation_events WHERE obligation_id=NEW.obligation_id
  AND obligation_revision=NEW.obligation_revision)
 BEGIN SELECT RAISE(ABORT,'album_obligation_event_retained'); END;
-- Dormant fresh read/add/read attachment coordination. Retain all earlier guards.
CREATE VIEW album_attachment_authority AS
 SELECT o.obligation_id,o.obligation_revision,b.binding_id,b.binding_revision,b.user_id,b.owner_nsid,
 o.photo_binding_id,o.photo_id,p.verification_revision,b.flickr_photoset_id photoset_id,b.first_photo_id primary_photo_id,
 b.link_revision,n.active_generation grant_generation,d.revision deployment_gate_revision,g.revision user_gate_revision
 FROM album_photo_obligations o JOIN album_bindings b ON b.binding_id=o.album_binding_id
 JOIN publish_service_identities s ON s.service_id=b.service_id AND s.user_id=b.user_id
 JOIN photo_bindings p ON p.binding_id=o.photo_binding_id AND p.user_id=b.user_id AND p.photo_id=o.photo_id
 JOIN flickr_links l ON l.user_id=b.user_id JOIN flickr_native_credentials n ON n.user_id=b.user_id
 JOIN flickr_connection_state c ON c.user_id=b.user_id
 JOIN flickr_write_gates d ON d.scope='deployment' AND d.scope_id='*'
 JOIN flickr_write_gates g ON g.scope='user' AND g.scope_id=b.user_id
 WHERE (((((b.materialization_state='materialized' AND b.flickr_photoset_id IS NOT NULL) AND (NOT EXISTS(SELECT 1 FROM album_title_attempts t WHERE t.binding_id=b.binding_id
 AND t.photoset_id=b.flickr_photoset_id AND t.owner_nsid=b.owner_nsid AND t.remote_missing=1) AND NOT EXISTS(SELECT 1 FROM album_attachment_attempts bad WHERE bad.binding_id=b.binding_id
 AND bad.photoset_id=b.flickr_photoset_id AND bad.owner_nsid=b.owner_nsid
 AND bad.state='album_attachment_needs_attention' AND bad.attention_reason IN ('wrong_owner','binding_conflict','missing_album')))) AND (((o.local_relationship='active' OR NOT EXISTS(SELECT 1 FROM album_obligation_events fulfilled
 WHERE fulfilled.obligation_id=o.obligation_id AND fulfilled.state='membership_verified')
 OR ((SELECT se.state FROM album_attachment_semantic_events se WHERE se.obligation_id=o.obligation_id ORDER BY se.obligation_revision_after DESC LIMIT 1)='membership_reconciliation_pending'
 AND EXISTS(SELECT 1 FROM album_attachment_attempts marked WHERE marked.obligation_id=o.obligation_id AND marked.dispatch_count=1
 AND marked.epoch>COALESCE((SELECT MAX(done.epoch) FROM album_attachment_attempts done WHERE done.obligation_id=o.obligation_id AND done.state='membership_verified'),0)))) AND o.obligation_revision<9007199254740991) AND (b.binding_revision<9007199254740991 AND EXISTS(SELECT 1 FROM album_obligation_events e WHERE e.obligation_id=o.obligation_id
 AND e.obligation_revision=o.obligation_revision AND e.state=o.state AND e.local_relationship=o.local_relationship)))) AND (((s.link_revision=b.link_revision AND s.owner_nsid=b.owner_nsid) AND (l.state='linked' AND l.link_revision=b.link_revision)) AND ((l.owner_nsid=b.owner_nsid AND n.link_revision=b.link_revision) AND (n.verified_owner_nsid=b.owner_nsid AND (n.operation_id IS NULL AND length(n.active_generation) BETWEEN 1 AND 128))))) AND ((((n.verified_permission IN ('write','delete') AND c.state='linked') AND (c.local_state='available' AND c.operation_id IS NULL)) AND ((c.verified_permission IN ('write','delete') AND c.external_removal=0) AND (d.enabled=1 AND g.enabled=1))) AND (((d.revision BETWEEN 1 AND 9007199254740991 AND g.revision BETWEEN 1 AND 9007199254740991) AND (p.link_revision=b.link_revision AND p.owner_nsid=b.owner_nsid)) AND ((p.binding_id<>'0' AND p.photo_id<>'0') AND (p.verification_revision BETWEEN 1 AND 9007199254740991 AND (p.verified_at_us BETWEEN 0 AND (CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000) AND (EXISTS(SELECT 1 FROM photo_binding_events e WHERE e.binding_id=p.binding_id AND e.verification_revision=p.verification_revision AND e.kind='existing_public_verified')
 OR EXISTS(SELECT 1 FROM upload_photo_binding_events e WHERE e.binding_id=p.binding_id AND e.verification_revision=p.verification_revision AND e.link_revision=p.link_revision AND e.verified_at_us=p.verified_at_us))))))));
CREATE TABLE album_attachment_attempts (
 attempt_id TEXT PRIMARY KEY NOT NULL CHECK(length(attempt_id)=36),
 obligation_id TEXT NOT NULL REFERENCES album_photo_obligations(obligation_id) ON DELETE RESTRICT,
 binding_id TEXT NOT NULL REFERENCES album_bindings(binding_id) ON DELETE RESTRICT,
 lease_id TEXT NOT NULL UNIQUE CHECK(length(lease_id)=36),epoch INTEGER NOT NULL CHECK(epoch BETWEEN 1 AND 9007199254740991),
 user_id TEXT NOT NULL,owner_nsid TEXT NOT NULL,photo_binding_id TEXT NOT NULL,photo_id TEXT NOT NULL,
 photoset_id TEXT NOT NULL,primary_photo_id TEXT NOT NULL,link_revision INTEGER NOT NULL,grant_generation TEXT NOT NULL,
 binding_revision INTEGER NOT NULL,obligation_revision INTEGER NOT NULL,verification_revision INTEGER NOT NULL,
 deployment_gate_revision INTEGER NOT NULL,user_gate_revision INTEGER NOT NULL,
 reconciliation_only INTEGER NOT NULL CHECK(reconciliation_only IN (0,1)),
 started_at_us INTEGER NOT NULL DEFAULT (CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000),
 invocation_deadline_at_us INTEGER NOT NULL DEFAULT ((CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000)+45000000),
 lease_expires_at_us INTEGER NOT NULL DEFAULT ((CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000)+60000000),
 state TEXT NOT NULL DEFAULT 'claimed' CHECK(state IN ('claimed','dispatched','result_received','membership_verified','membership_reconciliation_pending','retry_scheduled','album_attachment_needs_attention','abandoned_before_dispatch')),
 dispatch_count INTEGER NOT NULL DEFAULT 0 CHECK(dispatch_count IN (0,1)),
 dispatch_started_at_us INTEGER,pre_context_ids TEXT,pre_observed_at_us INTEGER,
 received_result TEXT CHECK(received_result IN ('added','already_present','uncertain')),received_at_us INTEGER,
 completed_at_us INTEGER,retry_after_us INTEGER NOT NULL DEFAULT 0,
 proof_context_ids TEXT,proof_owner_nsid TEXT,proof_photo_id TEXT,proof_observed_at_us INTEGER,
 attention_reason TEXT CHECK(attention_reason IN ('wrong_owner','missing_album','missing_photo','binding_conflict','retry_exhausted','archived_drift_unresolved')),
 UNIQUE(obligation_id,epoch),
 CHECK((dispatch_count=0 AND dispatch_started_at_us IS NULL AND pre_context_ids IS NULL AND pre_observed_at_us IS NULL)
 OR (dispatch_count=1 AND dispatch_started_at_us IS NOT NULL AND pre_context_ids IS NOT NULL AND pre_observed_at_us IS NOT NULL)),
 CHECK((state IN ('claimed','dispatched','result_received') AND completed_at_us IS NULL) OR (state NOT IN ('claimed','dispatched','result_received') AND completed_at_us IS NOT NULL)),
 CHECK(state<>'claimed' OR dispatch_count=0),CHECK(state NOT IN ('dispatched','result_received') OR dispatch_count=1),
 CHECK((received_result IS NULL AND received_at_us IS NULL) OR (received_result IS NOT NULL AND received_at_us IS NOT NULL AND dispatch_count=1)),
 CHECK(state<>'result_received' OR (received_result IS NOT NULL AND received_result IN ('added','already_present'))),
 CHECK(completed_at_us IS NULL OR dispatch_count=0 OR received_result IS NOT NULL),
 CHECK(reconciliation_only=0 OR dispatch_count=0),
 CHECK(state<>'abandoned_before_dispatch' OR (dispatch_count=0 AND reconciliation_only=0)),
 CHECK(state<>'membership_reconciliation_pending' OR dispatch_count=1 OR reconciliation_only=1),
 CHECK(((state IN ('membership_verified','retry_scheduled') OR attention_reason IN ('retry_exhausted','archived_drift_unresolved')) AND proof_context_ids IS NOT NULL AND proof_owner_nsid IS NOT NULL AND proof_photo_id IS NOT NULL AND proof_observed_at_us IS NOT NULL)
 OR (state NOT IN ('membership_verified','retry_scheduled') AND attention_reason IS NOT 'retry_exhausted' AND attention_reason IS NOT 'archived_drift_unresolved' AND proof_context_ids IS NULL AND proof_owner_nsid IS NULL AND proof_photo_id IS NULL AND proof_observed_at_us IS NULL)),
 CHECK((state='album_attachment_needs_attention' AND attention_reason IS NOT NULL) OR (state<>'album_attachment_needs_attention' AND attention_reason IS NULL)),
 CHECK((state IN ('claimed','dispatched','result_received','membership_verified','album_attachment_needs_attention') AND retry_after_us=0)
 OR (state NOT IN ('claimed','dispatched','result_received','membership_verified','album_attachment_needs_attention') AND retry_after_us>completed_at_us))
) STRICT;
CREATE UNIQUE INDEX album_attachment_one_active ON album_attachment_attempts(obligation_id) WHERE completed_at_us IS NULL;
CREATE INDEX album_attachment_due ON album_attachment_attempts(retry_after_us,obligation_id);
CREATE TABLE album_attachment_events (
 attempt_id TEXT NOT NULL REFERENCES album_attachment_attempts(attempt_id) ON DELETE RESTRICT,
 event_ordinal INTEGER NOT NULL,state TEXT NOT NULL,epoch INTEGER NOT NULL,dispatch_count INTEGER NOT NULL,
 dispatch_started_at_us INTEGER,created_at_us INTEGER NOT NULL DEFAULT (CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000),
 PRIMARY KEY(attempt_id,event_ordinal),UNIQUE(attempt_id,state)
) STRICT;
CREATE VIEW album_attachment_membership_evidence AS
 SELECT a.obligation_id,a.proof_observed_at_us membership_observed_at_us FROM album_attachment_attempts a
 WHERE a.state='membership_verified' AND a.epoch=(SELECT MAX(done.epoch) FROM album_attachment_attempts done
 WHERE done.obligation_id=a.obligation_id AND done.state='membership_verified');
CREATE TRIGGER album_attachment_initial BEFORE INSERT ON album_attachment_attempts
 WHEN NEW.state<>'claimed' OR NEW.dispatch_count<>0 OR NEW.completed_at_us IS NOT NULL OR NEW.retry_after_us<>0
 OR NEW.proof_context_ids IS NOT NULL OR NEW.proof_owner_nsid IS NOT NULL OR NEW.proof_photo_id IS NOT NULL OR NEW.proof_observed_at_us IS NOT NULL
 OR NEW.attention_reason IS NOT NULL OR NEW.started_at_us<>(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000)
 OR NEW.received_result IS NOT NULL OR NEW.received_at_us IS NOT NULL
 OR NEW.invocation_deadline_at_us<>NEW.started_at_us+45000000 OR NEW.lease_expires_at_us<>NEW.started_at_us+60000000
 OR NEW.epoch<>COALESCE((SELECT MAX(epoch)+1 FROM album_attachment_attempts WHERE obligation_id=NEW.obligation_id),1)
 OR NEW.reconciliation_only<>COALESCE((SELECT state='membership_reconciliation_pending' FROM album_attachment_attempts WHERE obligation_id=NEW.obligation_id ORDER BY epoch DESC LIMIT 1),0)
 OR EXISTS(SELECT 1 FROM album_attachment_attempts WHERE obligation_id=NEW.obligation_id AND (completed_at_us IS NULL OR state='album_attachment_needs_attention'))
 OR COALESCE((SELECT retry_after_us FROM album_attachment_attempts WHERE obligation_id=NEW.obligation_id ORDER BY epoch DESC LIMIT 1),0)>(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000)
 OR NOT EXISTS(SELECT 1 FROM album_attachment_authority v WHERE (((v.obligation_id=NEW.obligation_id AND (v.binding_id=NEW.binding_id AND v.user_id=NEW.user_id)) AND ((v.owner_nsid=NEW.owner_nsid AND v.photo_binding_id=NEW.photo_binding_id) AND (v.photo_id=NEW.photo_id AND v.photoset_id=NEW.photoset_id))) AND (((v.primary_photo_id=NEW.primary_photo_id AND v.link_revision=NEW.link_revision) AND (v.grant_generation=NEW.grant_generation AND v.binding_revision=NEW.binding_revision)) AND ((v.obligation_revision=NEW.obligation_revision AND v.verification_revision=NEW.verification_revision) AND (v.deployment_gate_revision=NEW.deployment_gate_revision AND v.user_gate_revision=NEW.user_gate_revision)))))
 BEGIN SELECT RAISE(ABORT,'album_attachment_initial'); END;
CREATE TRIGGER album_attachment_update BEFORE UPDATE ON album_attachment_attempts
 WHEN OLD.completed_at_us IS NOT NULL
 OR NEW.attempt_id<>OLD.attempt_id OR NEW.lease_id<>OLD.lease_id OR NEW.epoch<>OLD.epoch OR NEW.reconciliation_only<>OLD.reconciliation_only OR NEW.started_at_us<>OLD.started_at_us OR NEW.invocation_deadline_at_us<>OLD.invocation_deadline_at_us OR NEW.lease_expires_at_us<>OLD.lease_expires_at_us OR NEW.obligation_id<>OLD.obligation_id OR NEW.binding_id<>OLD.binding_id OR NEW.user_id<>OLD.user_id OR NEW.owner_nsid<>OLD.owner_nsid OR NEW.photo_binding_id<>OLD.photo_binding_id OR NEW.photo_id<>OLD.photo_id OR NEW.photoset_id<>OLD.photoset_id OR NEW.primary_photo_id<>OLD.primary_photo_id OR NEW.link_revision<>OLD.link_revision OR NEW.grant_generation<>OLD.grant_generation OR NEW.binding_revision<>OLD.binding_revision OR NEW.obligation_revision<>OLD.obligation_revision OR NEW.verification_revision<>OLD.verification_revision OR NEW.deployment_gate_revision<>OLD.deployment_gate_revision OR NEW.user_gate_revision<>OLD.user_gate_revision
 OR EXISTS(SELECT 1 FROM album_attachment_attempts newer WHERE newer.obligation_id=OLD.obligation_id AND newer.epoch>OLD.epoch)
 OR NOT ((OLD.state='claimed' AND NEW.state IN ('dispatched','membership_verified','retry_scheduled','album_attachment_needs_attention','abandoned_before_dispatch','membership_reconciliation_pending'))
 OR (OLD.state='dispatched' AND NEW.state IN ('result_received','membership_verified','retry_scheduled','album_attachment_needs_attention','membership_reconciliation_pending'))
 OR (OLD.state='result_received' AND NEW.state IN ('membership_verified','retry_scheduled','album_attachment_needs_attention','membership_reconciliation_pending')))
 OR (OLD.dispatch_count=1 AND (NEW.dispatch_count<>1 OR NEW.dispatch_started_at_us IS NOT OLD.dispatch_started_at_us OR NEW.pre_context_ids IS NOT OLD.pre_context_ids OR NEW.pre_observed_at_us IS NOT OLD.pre_observed_at_us))
 OR (OLD.received_result IS NOT NULL AND (NEW.received_result IS NOT OLD.received_result OR NEW.received_at_us IS NOT OLD.received_at_us))
 OR (OLD.received_result IS NULL AND NEW.state<>'result_received' AND (NEW.received_result IS NOT NULL OR NEW.received_at_us IS NOT NULL)
 AND NOT (NEW.state IN ('membership_reconciliation_pending','membership_verified','retry_scheduled','album_attachment_needs_attention') AND OLD.dispatch_count=1 AND NEW.received_result='uncertain' AND NEW.received_at_us=(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000)))
 OR (NEW.state='membership_reconciliation_pending' AND OLD.dispatch_count=1 AND NEW.received_result IS NULL)
 OR (NEW.state='result_received' AND NEW.received_at_us<>(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000))
 OR (NEW.completed_at_us IS NOT NULL AND NEW.completed_at_us<>(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000))
 OR (NEW.state NOT IN ('abandoned_before_dispatch','membership_reconciliation_pending') AND
 (OLD.lease_expires_at_us-(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000)<=CASE WHEN NEW.state='dispatched' THEN 15000000 ELSE 5000000 END
 OR OLD.invocation_deadline_at_us-(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000)<=CASE WHEN NEW.state='dispatched' THEN 15000000 ELSE 5000000 END
 OR NOT EXISTS(SELECT 1 FROM album_attachment_authority v WHERE (((v.obligation_id=OLD.obligation_id AND (v.binding_id=OLD.binding_id AND v.user_id=OLD.user_id)) AND ((v.owner_nsid=OLD.owner_nsid AND v.photo_binding_id=OLD.photo_binding_id) AND (v.photo_id=OLD.photo_id AND v.photoset_id=OLD.photoset_id))) AND (((v.primary_photo_id=OLD.primary_photo_id AND v.link_revision=OLD.link_revision) AND (v.grant_generation=OLD.grant_generation AND v.binding_revision=OLD.binding_revision+(SELECT COUNT(*) FROM album_attachment_semantic_events se WHERE se.attempt_id=OLD.attempt_id))) AND ((v.obligation_revision=OLD.obligation_revision+(SELECT COUNT(*) FROM album_attachment_semantic_events se WHERE se.attempt_id=OLD.attempt_id) AND v.verification_revision=OLD.verification_revision) AND (v.deployment_gate_revision=OLD.deployment_gate_revision AND v.user_gate_revision=OLD.user_gate_revision)))))))
 OR (NEW.state='dispatched' AND (NEW.dispatch_count<>1 OR NEW.reconciliation_only<>0 OR NEW.dispatch_started_at_us<>(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000) OR NEW.pre_observed_at_us<>(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000)
 OR EXISTS(SELECT 1 FROM json_each(NEW.pre_context_ids) WHERE value=NEW.photoset_id) OR (SELECT COUNT(*) FROM album_attachment_attempts history WHERE history.obligation_id=OLD.obligation_id AND history.dispatch_count=1 AND history.epoch>COALESCE((SELECT MAX(done.epoch) FROM album_attachment_attempts done WHERE done.obligation_id=history.obligation_id AND done.state='membership_verified'),0))>=8))
 OR (OLD.dispatch_count=0 AND NEW.state<>'dispatched' AND NEW.dispatch_count<>0)
 OR ((NEW.state IN ('membership_verified','retry_scheduled') OR NEW.attention_reason IN ('retry_exhausted','archived_drift_unresolved')) AND (NEW.proof_owner_nsid<>OLD.owner_nsid OR NEW.proof_photo_id<>OLD.photo_id
 OR NEW.proof_observed_at_us<>(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000) OR (NEW.state='membership_verified')<>EXISTS(SELECT 1 FROM json_each(NEW.proof_context_ids) WHERE value=NEW.photoset_id)))
 OR (NEW.state='retry_scheduled' AND (SELECT COUNT(*) FROM album_attachment_attempts history WHERE history.obligation_id=OLD.obligation_id AND history.dispatch_count=1 AND history.epoch>COALESCE((SELECT MAX(done.epoch) FROM album_attachment_attempts done WHERE done.obligation_id=history.obligation_id AND done.state='membership_verified'),0))>=8)
 OR (NEW.attention_reason='retry_exhausted' AND (SELECT COUNT(*) FROM album_attachment_attempts history WHERE history.obligation_id=OLD.obligation_id AND history.dispatch_count=1 AND history.epoch>COALESCE((SELECT MAX(done.epoch) FROM album_attachment_attempts done WHERE done.obligation_id=history.obligation_id AND done.state='membership_verified'),0))<8)
 OR (NEW.state='retry_scheduled' AND EXISTS(SELECT 1 FROM album_photo_obligations o WHERE o.obligation_id=OLD.obligation_id AND o.local_relationship='archived'
 AND EXISTS(SELECT 1 FROM album_obligation_events e WHERE e.obligation_id=o.obligation_id AND e.state='membership_verified')))
 OR (NEW.attention_reason='archived_drift_unresolved' AND (OLD.reconciliation_only<>1 OR NOT EXISTS(SELECT 1 FROM album_photo_obligations o
 WHERE o.obligation_id=OLD.obligation_id AND o.local_relationship='archived' AND EXISTS(SELECT 1 FROM album_obligation_events e WHERE e.obligation_id=o.obligation_id AND e.state='membership_verified'))))
 OR (NEW.state IN ('retry_scheduled','membership_reconciliation_pending','abandoned_before_dispatch')
 AND NEW.retry_after_us<>(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000)+MIN(60000000,1000000*(1 << MIN(OLD.epoch-1,6))))
 BEGIN SELECT RAISE(ABORT,'album_attachment_fenced'); END;
CREATE TRIGGER album_attachment_pre_context_ids BEFORE UPDATE ON album_attachment_attempts
 WHEN NEW.pre_context_ids IS NOT NULL AND (NOT json_valid(NEW.pre_context_ids) OR json_type(NEW.pre_context_ids)<>'array'
 OR json_array_length(NEW.pre_context_ids)>1000 OR length(NEW.pre_context_ids)>1048576
 OR EXISTS(SELECT 1 FROM json_each(NEW.pre_context_ids) WHERE type<>'text' OR value='0' OR length(value) NOT BETWEEN 1 AND 128
 OR substr(value,1,1) NOT GLOB '[A-Za-z0-9]' OR value GLOB '*[^A-Za-z0-9@._:-]*')
 OR (SELECT COUNT(*) FROM json_each(NEW.pre_context_ids))<>(SELECT COUNT(DISTINCT value) FROM json_each(NEW.pre_context_ids)))
 BEGIN SELECT RAISE(ABORT,'album_attachment_contexts'); END;
CREATE TRIGGER album_attachment_proof_context_ids BEFORE UPDATE ON album_attachment_attempts
 WHEN NEW.proof_context_ids IS NOT NULL AND (NOT json_valid(NEW.proof_context_ids) OR json_type(NEW.proof_context_ids)<>'array'
 OR json_array_length(NEW.proof_context_ids)>1000 OR length(NEW.proof_context_ids)>1048576
 OR EXISTS(SELECT 1 FROM json_each(NEW.proof_context_ids) WHERE type<>'text' OR value='0' OR length(value) NOT BETWEEN 1 AND 128
 OR substr(value,1,1) NOT GLOB '[A-Za-z0-9]' OR value GLOB '*[^A-Za-z0-9@._:-]*')
 OR (SELECT COUNT(*) FROM json_each(NEW.proof_context_ids))<>(SELECT COUNT(DISTINCT value) FROM json_each(NEW.proof_context_ids)))
 BEGIN SELECT RAISE(ABORT,'album_attachment_contexts'); END;
CREATE TRIGGER album_attachment_no_delete BEFORE DELETE ON album_attachment_attempts BEGIN SELECT RAISE(ABORT,'album_attachment_retained'); END;
CREATE TRIGGER album_attachment_no_replace BEFORE INSERT ON album_attachment_attempts
 WHEN EXISTS(SELECT 1 FROM album_attachment_attempts WHERE attempt_id=NEW.attempt_id OR lease_id=NEW.lease_id OR (obligation_id=NEW.obligation_id AND epoch=NEW.epoch))
 BEGIN SELECT RAISE(ABORT,'album_attachment_retained'); END;
CREATE TRIGGER album_attachment_event_consistent BEFORE INSERT ON album_attachment_events
 WHEN NEW.event_ordinal<>COALESCE((SELECT MAX(event_ordinal)+1 FROM album_attachment_events WHERE attempt_id=NEW.attempt_id),1)
 OR NOT EXISTS(SELECT 1 FROM album_attachment_attempts a WHERE a.attempt_id=NEW.attempt_id AND a.state=NEW.state
 AND a.epoch=NEW.epoch AND a.dispatch_count=NEW.dispatch_count AND a.dispatch_started_at_us IS NEW.dispatch_started_at_us)
 BEGIN SELECT RAISE(ABORT,'album_attachment_event_inconsistent'); END;
CREATE TRIGGER album_attachment_event_no_update BEFORE UPDATE ON album_attachment_events BEGIN SELECT RAISE(ABORT,'album_attachment_event_retained'); END;
CREATE TRIGGER album_attachment_event_no_delete BEFORE DELETE ON album_attachment_events BEGIN SELECT RAISE(ABORT,'album_attachment_event_retained'); END;
CREATE TRIGGER album_attachment_event_no_replace BEFORE INSERT ON album_attachment_events
 WHEN EXISTS(SELECT 1 FROM album_attachment_events WHERE attempt_id=NEW.attempt_id AND event_ordinal=NEW.event_ordinal)
 BEGIN SELECT RAISE(ABORT,'album_attachment_event_retained'); END;
CREATE TRIGGER album_attachment_created AFTER INSERT ON album_attachment_attempts BEGIN
 INSERT INTO album_attachment_events(attempt_id,event_ordinal,state,epoch,dispatch_count,dispatch_started_at_us)
 VALUES(NEW.attempt_id,1,NEW.state,NEW.epoch,NEW.dispatch_count,NEW.dispatch_started_at_us);
END;
CREATE TRIGGER album_attachment_changed AFTER UPDATE ON album_attachment_attempts BEGIN
 INSERT INTO album_attachment_events(attempt_id,event_ordinal,state,epoch,dispatch_count,dispatch_started_at_us)
 SELECT NEW.attempt_id,MAX(event_ordinal)+1,NEW.state,NEW.epoch,NEW.dispatch_count,NEW.dispatch_started_at_us FROM album_attachment_events WHERE attempt_id=NEW.attempt_id;
 UPDATE album_photo_obligations SET state='membership_verified',obligation_revision=obligation_revision+1
 WHERE obligation_id=NEW.obligation_id AND state<>'membership_verified' AND NEW.state='membership_verified';
END;
DROP TRIGGER album_obligation_no_update;
CREATE TRIGGER album_obligation_no_update BEFORE UPDATE ON album_photo_obligations
 WHEN NEW.obligation_id<>OLD.obligation_id OR NEW.album_binding_id<>OLD.album_binding_id
 OR NEW.photo_binding_id<>OLD.photo_binding_id OR NEW.photo_id<>OLD.photo_id
 OR NEW.admission_binding_revision<>OLD.admission_binding_revision
 OR NEW.obligation_revision<>OLD.obligation_revision+1
 OR NOT (
  (NEW.state=OLD.state AND OLD.local_relationship='active' AND NEW.local_relationship='archived'
   AND EXISTS(SELECT 1 FROM album_bindings b WHERE b.binding_id=OLD.album_binding_id AND b.state='local_collection_removed_remote_preserved'))
  OR (NEW.local_relationship=OLD.local_relationship AND NEW.state='membership_verified' AND OLD.state='waiting_for_album'
   AND (EXISTS(SELECT 1 FROM album_materialization_attempts a JOIN album_bindings b ON b.binding_id=a.binding_id
    WHERE b.first_obligation_id=OLD.obligation_id AND a.state='verified' AND a.photoset_id=b.flickr_photoset_id
    AND a.photo_id=OLD.photo_id AND a.photo_binding_id=OLD.photo_binding_id)
   OR EXISTS(SELECT 1 FROM album_create_repair_receipts r JOIN album_bindings b ON b.binding_id=r.binding_id
    WHERE b.first_obligation_id=OLD.obligation_id AND b.flickr_photoset_id=r.selected_photoset_id
    AND r.first_photo_id=OLD.photo_id AND r.first_photo_binding_id=OLD.photo_binding_id)))
 OR (NEW.local_relationship=OLD.local_relationship AND NEW.state='membership_verified' AND OLD.state IN ('waiting_for_album','attachment_pending')
 AND EXISTS(SELECT 1 FROM album_attachment_attempts a JOIN album_bindings b ON b.binding_id=a.binding_id
 WHERE a.obligation_id=OLD.obligation_id AND a.state='membership_verified' AND a.photoset_id=b.flickr_photoset_id
 AND a.photo_id=OLD.photo_id AND a.photo_binding_id=OLD.photo_binding_id
 AND a.obligation_revision=OLD.obligation_revision AND a.proof_observed_at_us=a.completed_at_us)))
 BEGIN SELECT RAISE(ABORT,'album_obligation_immutable'); END;

CREATE TABLE album_attachment_semantic_events (
 attempt_id TEXT NOT NULL REFERENCES album_attachment_attempts(attempt_id) ON DELETE RESTRICT,
 event_ordinal INTEGER NOT NULL,obligation_id TEXT NOT NULL REFERENCES album_photo_obligations(obligation_id) ON DELETE RESTRICT,
 binding_id TEXT NOT NULL REFERENCES album_bindings(binding_id) ON DELETE RESTRICT,
 binding_revision_before INTEGER NOT NULL,binding_revision_after INTEGER NOT NULL,
 obligation_revision_before INTEGER NOT NULL,obligation_revision_after INTEGER NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('attachment_pending','membership_verified','membership_reconciliation_pending','album_attachment_needs_attention')),
 membership_observed_at_us INTEGER,
 created_at_us INTEGER NOT NULL DEFAULT (CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000),
 PRIMARY KEY(attempt_id,event_ordinal),UNIQUE(binding_id,binding_revision_after),UNIQUE(obligation_id,obligation_revision_after),
 CHECK(binding_revision_before BETWEEN 1 AND 9007199254740990 AND binding_revision_after=binding_revision_before+1),
 CHECK(obligation_revision_before BETWEEN 1 AND 9007199254740990 AND obligation_revision_after=obligation_revision_before+1)
) STRICT;
CREATE TRIGGER album_attachment_semantic_initial BEFORE INSERT ON album_attachment_semantic_events
 WHEN NEW.created_at_us<>(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000) OR NOT EXISTS(SELECT 1 FROM album_attachment_attempts a
 JOIN album_bindings b ON b.binding_id=a.binding_id JOIN album_photo_obligations o ON o.obligation_id=a.obligation_id
 WHERE a.attempt_id=NEW.attempt_id AND a.obligation_id=NEW.obligation_id AND a.binding_id=NEW.binding_id
 AND NOT EXISTS(SELECT 1 FROM album_attachment_attempts newer WHERE newer.obligation_id=a.obligation_id AND newer.epoch>a.epoch)
 AND b.binding_revision=NEW.binding_revision_before AND o.obligation_revision=NEW.obligation_revision_before
 AND ((b.binding_revision=a.binding_revision+(SELECT COUNT(*) FROM album_attachment_semantic_events se WHERE se.attempt_id=a.attempt_id)
 AND o.obligation_revision=a.obligation_revision+(SELECT COUNT(*) FROM album_attachment_semantic_events se WHERE se.attempt_id=a.attempt_id))
 OR a.state='membership_reconciliation_pending')
 AND NEW.event_ordinal=(SELECT MAX(event_ordinal) FROM album_attachment_events e WHERE e.attempt_id=a.attempt_id)
 AND NEW.state=CASE a.state WHEN 'dispatched' THEN 'attachment_pending' WHEN 'retry_scheduled' THEN 'attachment_pending' ELSE a.state END
 AND a.state IN ('dispatched','retry_scheduled','membership_verified','membership_reconciliation_pending','album_attachment_needs_attention')
 AND NEW.membership_observed_at_us IS CASE WHEN a.state='membership_verified' THEN a.proof_observed_at_us ELSE COALESCE((SELECT se.membership_observed_at_us FROM album_attachment_semantic_events se WHERE se.obligation_id=o.obligation_id ORDER BY se.obligation_revision_after DESC LIMIT 1),CASE WHEN b.first_obligation_id=o.obligation_id THEN COALESCE((SELECT r.proof_observed_at_us FROM album_create_repair_receipts r WHERE r.binding_id=b.binding_id),(SELECT a.proof_observed_at_us FROM album_materialization_attempts a WHERE a.binding_id=b.binding_id AND a.state='verified')) ELSE NULL END) END
 AND (COALESCE((SELECT se.state FROM album_attachment_semantic_events se WHERE se.obligation_id=o.obligation_id ORDER BY se.obligation_revision_after DESC LIMIT 1),CASE WHEN o.state='waiting_for_album' AND b.flickr_photoset_id IS NOT NULL THEN 'attachment_pending' ELSE o.state END)<>NEW.state OR a.state IN ('membership_verified','retry_scheduled')))
 BEGIN SELECT RAISE(ABORT,'album_attachment_semantic_initial'); END;
CREATE TRIGGER album_attachment_semantic_no_update BEFORE UPDATE ON album_attachment_semantic_events BEGIN SELECT RAISE(ABORT,'album_attachment_semantic_retained'); END;
CREATE TRIGGER album_attachment_semantic_no_delete BEFORE DELETE ON album_attachment_semantic_events BEGIN SELECT RAISE(ABORT,'album_attachment_semantic_retained'); END;
CREATE TRIGGER album_attachment_semantic_no_replace BEFORE INSERT ON album_attachment_semantic_events
 WHEN EXISTS(SELECT 1 FROM album_attachment_semantic_events WHERE (attempt_id=NEW.attempt_id AND event_ordinal=NEW.event_ordinal)
 OR (binding_id=NEW.binding_id AND binding_revision_after=NEW.binding_revision_after)
 OR (obligation_id=NEW.obligation_id AND obligation_revision_after=NEW.obligation_revision_after))
 BEGIN SELECT RAISE(ABORT,'album_attachment_semantic_retained'); END;
CREATE TRIGGER album_attachment_semantic_apply AFTER INSERT ON album_attachment_semantic_events BEGIN
 UPDATE album_photo_obligations SET obligation_revision=NEW.obligation_revision_after,
 state=CASE WHEN NEW.state='membership_verified' THEN 'membership_verified' ELSE state END WHERE obligation_id=NEW.obligation_id;
 UPDATE album_bindings SET binding_revision=NEW.binding_revision_after WHERE binding_id=NEW.binding_id;
END;
DROP TRIGGER album_attachment_changed;
CREATE TRIGGER album_attachment_changed AFTER UPDATE ON album_attachment_attempts BEGIN
 INSERT INTO album_attachment_events(attempt_id,event_ordinal,state,epoch,dispatch_count,dispatch_started_at_us)
 SELECT NEW.attempt_id,MAX(event_ordinal)+1,NEW.state,NEW.epoch,NEW.dispatch_count,NEW.dispatch_started_at_us FROM album_attachment_events WHERE attempt_id=NEW.attempt_id;
 INSERT INTO album_attachment_semantic_events(attempt_id,event_ordinal,obligation_id,binding_id,
 binding_revision_before,binding_revision_after,obligation_revision_before,obligation_revision_after,state,membership_observed_at_us)
 SELECT NEW.attempt_id,(SELECT MAX(event_ordinal) FROM album_attachment_events WHERE attempt_id=NEW.attempt_id),
 o.obligation_id,b.binding_id,b.binding_revision,b.binding_revision+1,o.obligation_revision,o.obligation_revision+1,
 CASE NEW.state WHEN 'dispatched' THEN 'attachment_pending' WHEN 'retry_scheduled' THEN 'attachment_pending' ELSE NEW.state END,
 CASE WHEN NEW.state='membership_verified' THEN NEW.proof_observed_at_us ELSE COALESCE((SELECT se.membership_observed_at_us FROM album_attachment_semantic_events se WHERE se.obligation_id=o.obligation_id ORDER BY se.obligation_revision_after DESC LIMIT 1),CASE WHEN b.first_obligation_id=o.obligation_id THEN COALESCE((SELECT r.proof_observed_at_us FROM album_create_repair_receipts r WHERE r.binding_id=b.binding_id),(SELECT a.proof_observed_at_us FROM album_materialization_attempts a WHERE a.binding_id=b.binding_id AND a.state='verified')) ELSE NULL END) END
 FROM album_photo_obligations o JOIN album_bindings b ON b.binding_id=o.album_binding_id
 WHERE o.obligation_id=NEW.obligation_id AND NEW.state IN ('dispatched','retry_scheduled','membership_verified','membership_reconciliation_pending','album_attachment_needs_attention')
 AND (COALESCE((SELECT se.state FROM album_attachment_semantic_events se WHERE se.obligation_id=o.obligation_id ORDER BY se.obligation_revision_after DESC LIMIT 1),CASE WHEN o.state='waiting_for_album' AND b.flickr_photoset_id IS NOT NULL THEN 'attachment_pending' ELSE o.state END)<>CASE NEW.state WHEN 'dispatched' THEN 'attachment_pending' WHEN 'retry_scheduled' THEN 'attachment_pending' ELSE NEW.state END
 OR NEW.state IN ('membership_verified','retry_scheduled'));
END;
DROP TRIGGER album_obligation_no_update;
CREATE TRIGGER album_obligation_no_update BEFORE UPDATE ON album_photo_obligations
 WHEN NEW.obligation_id<>OLD.obligation_id OR NEW.album_binding_id<>OLD.album_binding_id
 OR NEW.photo_binding_id<>OLD.photo_binding_id OR NEW.photo_id<>OLD.photo_id
 OR NEW.admission_binding_revision<>OLD.admission_binding_revision
 OR NEW.obligation_revision<>OLD.obligation_revision+1
 OR NOT (
  (NEW.state=OLD.state AND OLD.local_relationship='active' AND NEW.local_relationship='archived'
   AND EXISTS(SELECT 1 FROM album_bindings b WHERE b.binding_id=OLD.album_binding_id AND b.state='local_collection_removed_remote_preserved'))
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
 AND NOT EXISTS(SELECT 1 FROM album_binding_events e WHERE e.binding_id=OLD.binding_id AND e.binding_revision=NEW.binding_revision)))

 OR NEW.materialization_revision<>OLD.materialization_revision+(NEW.materialization_state<>OLD.materialization_state)
 OR (NEW.title_revision<>OLD.title_revision AND NOT (NEW.title_revision=OLD.title_revision+1
  AND EXISTS(SELECT 1 FROM album_title_receipts r WHERE r.binding_id=OLD.binding_id
   AND r.title_revision=NEW.title_revision AND r.expected_binding_revision=OLD.binding_revision
   AND r.accepted_binding_revision=NEW.binding_revision AND r.expected_title_revision=OLD.title_revision AND r.desired_title=NEW.desired_title)))
 OR (NEW.desired_title<>OLD.desired_title AND NEW.title_revision=OLD.title_revision)
 OR (OLD.state='local_collection_removed_remote_preserved' AND (NEW.state<>OLD.state OR NEW.desired_title<>OLD.desired_title OR NEW.title_revision<>OLD.title_revision))
 BEGIN SELECT RAISE(ABORT,'album_binding_revision'); END;

DROP TRIGGER album_obligation_archived;
CREATE TRIGGER album_obligation_archived AFTER UPDATE ON album_photo_obligations BEGIN
 INSERT INTO album_obligation_events(obligation_id,obligation_revision,kind,state,local_relationship)
 VALUES(NEW.obligation_id,NEW.obligation_revision,
 CASE WHEN NEW.local_relationship<>OLD.local_relationship THEN 'relationship_archived'
 WHEN NEW.state='membership_verified' AND OLD.state<>NEW.state THEN 'membership_verified' ELSE 'attachment_state_changed' END,
 NEW.state,NEW.local_relationship);
END;

-- Effective read state follows latest retained attachment work, while immutable
-- admission receipts retain their original fulfilled evidence.
DROP VIEW album_obligation_status;
CREATE VIEW album_obligation_status AS
 SELECT o.obligation_id,o.album_binding_id,o.photo_binding_id,o.photo_id,o.obligation_revision,
 COALESCE(latest.state,CASE WHEN o.state='waiting_for_album' AND b.flickr_photoset_id IS NOT NULL THEN 'attachment_pending' ELSE o.state END) state,
 o.local_relationship,o.admission_binding_revision,
 COALESCE(e.membership_observed_at_us,CASE WHEN o.obligation_id=b.first_obligation_id THEN COALESCE(r.proof_observed_at_us,a.proof_observed_at_us) ELSE NULL END) membership_observed_at_us
 FROM album_photo_obligations o JOIN album_bindings b ON b.binding_id=o.album_binding_id
 LEFT JOIN album_create_repair_receipts r ON r.binding_id=b.binding_id
 LEFT JOIN album_materialization_attempts a ON a.binding_id=b.binding_id AND a.state='verified'
 LEFT JOIN album_attachment_membership_evidence e ON e.obligation_id=o.obligation_id
 LEFT JOIN album_attachment_semantic_events latest ON latest.obligation_id=o.obligation_id
 AND latest.obligation_revision_after=(SELECT MAX(x.obligation_revision_after) FROM album_attachment_semantic_events x WHERE x.obligation_id=o.obligation_id);
DROP VIEW album_binding_remote_status;
CREATE VIEW album_binding_remote_status AS
 SELECT b.binding_id,CASE
 WHEN EXISTS(SELECT 1 FROM album_attachment_attempts bad WHERE bad.binding_id=b.binding_id
 AND bad.photoset_id=b.flickr_photoset_id AND bad.owner_nsid=b.owner_nsid
 AND bad.state='album_attachment_needs_attention' AND bad.attention_reason IN ('wrong_owner','binding_conflict')) THEN 'album_identity_conflict'
 WHEN EXISTS(SELECT 1 FROM album_attachment_attempts bad WHERE bad.binding_id=b.binding_id
 AND bad.photoset_id=b.flickr_photoset_id AND bad.owner_nsid=b.owner_nsid
 AND bad.state='album_attachment_needs_attention' AND bad.attention_reason='missing_album')
 OR EXISTS(SELECT 1 FROM album_title_attempts t WHERE t.binding_id=b.binding_id
 AND t.photoset_id=b.flickr_photoset_id AND t.owner_nsid=b.owner_nsid AND t.remote_missing=1) THEN 'remote_album_missing_needs_attention'
 ELSE b.materialization_state END materialization_state FROM album_bindings b;
