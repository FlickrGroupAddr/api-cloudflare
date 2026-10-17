-- Revisioned title intent and retained, fenced editMeta reconciliation.
-- No table rebuild: populated admission/materialization/repair history survives.
CREATE VIEW album_title_link_authority AS
 SELECT b.binding_id,b.user_id,b.owner_nsid,b.link_revision,n.active_generation grant_generation
 FROM album_bindings b JOIN publish_service_identities s ON s.service_id=b.service_id AND s.user_id=b.user_id
 JOIN flickr_links l ON l.user_id=b.user_id JOIN flickr_native_credentials n ON n.user_id=b.user_id
 JOIN flickr_connection_state c ON c.user_id=b.user_id
 WHERE s.owner_nsid=b.owner_nsid AND s.link_revision=b.link_revision
 AND l.state='linked' AND l.owner_nsid=b.owner_nsid AND l.link_revision=b.link_revision
 AND n.link_revision=b.link_revision AND n.verified_owner_nsid=b.owner_nsid AND n.operation_id IS NULL
 AND length(n.active_generation) BETWEEN 1 AND 128 AND n.verified_permission IN ('write','delete')
 AND c.state='linked' AND c.local_state='available' AND c.operation_id IS NULL
 AND c.verified_permission IN ('write','delete') AND c.external_removal=0;
CREATE TABLE album_title_receipts (
 binding_id TEXT NOT NULL REFERENCES album_bindings(binding_id) ON DELETE RESTRICT,
 title_revision INTEGER NOT NULL CHECK(title_revision BETWEEN 2 AND 9007199254740991),
 expected_binding_revision INTEGER NOT NULL CHECK(expected_binding_revision BETWEEN 1 AND 9007199254740990),
 expected_title_revision INTEGER NOT NULL CHECK(expected_title_revision=title_revision-1),
 desired_title TEXT NOT NULL CHECK(length(desired_title) BETWEEN 1 AND 1000 AND instr(desired_title,char(0))=0),
 accepted_binding_revision INTEGER NOT NULL CHECK(accepted_binding_revision=expected_binding_revision+1),
 installation_id TEXT NOT NULL,credential_digest TEXT NOT NULL,
 accepted_at_us INTEGER NOT NULL DEFAULT(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000),
 PRIMARY KEY(binding_id,title_revision)
) STRICT;
CREATE TRIGGER album_title_receipt_initial BEFORE INSERT ON album_title_receipts
 WHEN NEW.accepted_at_us<>(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000)
 OR NOT EXISTS(SELECT 1 FROM album_bindings b JOIN album_title_link_authority a ON a.binding_id=b.binding_id
 JOIN installations i ON i.user_id=b.user_id JOIN installation_credential_versions v
 ON v.installation_id=i.installation_id AND v.version_id=i.current_version_id
 WHERE b.binding_id=NEW.binding_id AND b.binding_revision=NEW.expected_binding_revision
 AND b.title_revision=NEW.expected_title_revision AND b.state='materialization_pending'
 AND i.installation_id=NEW.installation_id AND i.state='active' AND i.credential_class='lrc_plugin'
 AND i.revision BETWEEN 1 AND 9007199254740991 AND v.state='current' AND v.expires_at_us IS NULL
 AND v.credential_digest=NEW.credential_digest)
 BEGIN SELECT RAISE(ABORT,'album_title_receipt_initial'); END;
CREATE TRIGGER album_title_receipt_no_update BEFORE UPDATE ON album_title_receipts BEGIN SELECT RAISE(ABORT,'album_title_receipt_retained'); END;
CREATE TRIGGER album_title_receipt_no_delete BEFORE DELETE ON album_title_receipts BEGIN SELECT RAISE(ABORT,'album_title_receipt_retained'); END;
CREATE TRIGGER album_title_receipt_no_replace BEFORE INSERT ON album_title_receipts
 WHEN EXISTS(SELECT 1 FROM album_title_receipts WHERE binding_id=NEW.binding_id AND title_revision=NEW.title_revision)
 BEGIN SELECT RAISE(ABORT,'album_title_receipt_retained'); END;
DROP TRIGGER album_binding_revision;
CREATE TRIGGER album_binding_revision BEFORE UPDATE ON album_bindings
 WHEN NEW.binding_revision<>OLD.binding_revision+
   (NEW.title_revision<>OLD.title_revision OR NEW.flickr_photoset_id IS NOT OLD.flickr_photoset_id OR NEW.state<>OLD.state OR NEW.materialization_state<>OLD.materialization_state
    OR EXISTS(SELECT 1 FROM album_photo_obligations o WHERE o.album_binding_id=OLD.binding_id
      AND o.admission_binding_revision=OLD.binding_revision+1
      AND NOT EXISTS(SELECT 1 FROM album_binding_events e WHERE e.binding_id=OLD.binding_id AND e.binding_revision=o.admission_binding_revision))
    OR EXISTS(SELECT 1 FROM album_title_semantic_events e WHERE e.binding_id=OLD.binding_id
      AND e.binding_revision_after=OLD.binding_revision+1 AND e.binding_revision_before=OLD.binding_revision
      AND NOT EXISTS(SELECT 1 FROM album_binding_events h WHERE h.binding_id=OLD.binding_id AND h.binding_revision=e.binding_revision_after)))
 OR NEW.materialization_revision<>OLD.materialization_revision+(NEW.materialization_state<>OLD.materialization_state)
 OR (NEW.title_revision<>OLD.title_revision AND NOT (NEW.title_revision=OLD.title_revision+1
  AND EXISTS(SELECT 1 FROM album_title_receipts r WHERE r.binding_id=OLD.binding_id
   AND r.title_revision=NEW.title_revision AND r.expected_binding_revision=OLD.binding_revision
   AND r.accepted_binding_revision=NEW.binding_revision AND r.expected_title_revision=OLD.title_revision AND r.desired_title=NEW.desired_title)))
 OR (NEW.desired_title<>OLD.desired_title AND NEW.title_revision=OLD.title_revision)
 OR (OLD.state='local_collection_removed_remote_preserved' AND (NEW.state<>OLD.state OR NEW.desired_title<>OLD.desired_title OR NEW.title_revision<>OLD.title_revision))
 BEGIN SELECT RAISE(ABORT,'album_binding_revision'); END;
CREATE TRIGGER album_title_receipt_apply AFTER INSERT ON album_title_receipts BEGIN
 UPDATE album_bindings SET desired_title=NEW.desired_title,title_revision=NEW.title_revision,binding_revision=NEW.accepted_binding_revision WHERE binding_id=NEW.binding_id;
END;

CREATE VIEW album_title_worker_authority AS
 SELECT v.*,b.binding_revision FROM album_materialization_authority v JOIN album_bindings b ON b.binding_id=v.binding_id
 WHERE v.flickr_photoset_id IS NOT NULL AND v.materialization_state='materialized';
CREATE TABLE album_title_attempts (
 attempt_id TEXT PRIMARY KEY NOT NULL CHECK(length(attempt_id)=36),
 binding_id TEXT NOT NULL REFERENCES album_bindings(binding_id) ON DELETE RESTRICT,
 lease_id TEXT NOT NULL UNIQUE CHECK(length(lease_id)=36),epoch INTEGER NOT NULL CHECK(epoch BETWEEN 1 AND 9007199254740991),
 user_id TEXT NOT NULL,owner_nsid TEXT NOT NULL,photoset_id TEXT NOT NULL,
 link_revision INTEGER NOT NULL,grant_generation TEXT NOT NULL,
 desired_title TEXT NOT NULL,title_revision INTEGER NOT NULL CHECK(title_revision BETWEEN 1 AND 9007199254740991),
 binding_revision INTEGER NOT NULL CHECK(binding_revision BETWEEN 1 AND 9007199254740990),
 lease_binding_revision INTEGER NOT NULL CHECK(lease_binding_revision BETWEEN 1 AND 9007199254740990),
 deployment_gate_revision INTEGER NOT NULL,user_gate_revision INTEGER NOT NULL,
 attempt_number INTEGER NOT NULL CHECK(attempt_number BETWEEN 1 AND 3),
 started_at_us INTEGER NOT NULL DEFAULT(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000),
 lease_expires_at_us INTEGER NOT NULL DEFAULT(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000+11000000),
 invocation_deadline_at_us INTEGER NOT NULL DEFAULT(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000+10000000),
 next_read_at_us INTEGER NOT NULL DEFAULT 0,
 state TEXT NOT NULL DEFAULT 'claimed' CHECK(state IN ('claimed','dispatched','result_received','synced','superseded','retry_pending','conflict','reconciliation_pending','needs_attention','local_removed')),
 dispatch_count INTEGER NOT NULL DEFAULT 0 CHECK(dispatch_count IN (0,1)),
 read_count INTEGER NOT NULL DEFAULT 0 CHECK(read_count BETWEEN 0 AND 5),
 pre_dispatch_title TEXT,dispatch_started_at_us INTEGER,result_class TEXT CHECK(result_class IN ('success','uncertain','rejected')),
 observed_title TEXT,observed_at_us INTEGER,completed_at_us INTEGER,satisfied_title_revision INTEGER,remote_missing INTEGER NOT NULL DEFAULT 0 CHECK(remote_missing IN (0,1)),
 UNIQUE(binding_id,epoch),UNIQUE(binding_id,title_revision,attempt_number),
 CHECK((dispatch_count=0 AND pre_dispatch_title IS NULL AND dispatch_started_at_us IS NULL AND result_class IS NULL)
 OR (dispatch_count=1 AND pre_dispatch_title IS NOT NULL AND dispatch_started_at_us IS NOT NULL)),
 CHECK((observed_title IS NULL)=(observed_at_us IS NULL)),
 CHECK((state IN ('synced','superseded','retry_pending','conflict','local_removed') AND completed_at_us IS NOT NULL)
  OR (state='needs_attention') OR (state IN ('claimed','dispatched','result_received','reconciliation_pending') AND completed_at_us IS NULL))
) STRICT;
CREATE UNIQUE INDEX album_title_one_open ON album_title_attempts(binding_id) WHERE completed_at_us IS NULL;
CREATE INDEX album_title_due ON album_title_attempts(next_read_at_us,lease_expires_at_us) WHERE completed_at_us IS NULL;
CREATE TABLE album_title_events (
 attempt_id TEXT NOT NULL REFERENCES album_title_attempts(attempt_id) ON DELETE RESTRICT,
 event_ordinal INTEGER NOT NULL,state TEXT NOT NULL,epoch INTEGER NOT NULL,dispatch_count INTEGER NOT NULL,read_count INTEGER NOT NULL,
 semantic_change INTEGER NOT NULL DEFAULT 0 CHECK(semantic_change IN (0,1)),
 created_at_us INTEGER NOT NULL DEFAULT(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000),
 PRIMARY KEY(attempt_id,event_ordinal)
) STRICT;
CREATE TABLE album_title_semantic_events (
 binding_id TEXT NOT NULL REFERENCES album_bindings(binding_id) ON DELETE RESTRICT,
 binding_revision_before INTEGER NOT NULL CHECK(binding_revision_before BETWEEN 1 AND 9007199254740990),
 binding_revision_after INTEGER NOT NULL CHECK(binding_revision_after=binding_revision_before+1),
 attempt_id TEXT NOT NULL,epoch INTEGER NOT NULL,event_ordinal INTEGER NOT NULL,
 PRIMARY KEY(binding_id,binding_revision_after),UNIQUE(attempt_id,event_ordinal),
 FOREIGN KEY(attempt_id,event_ordinal) REFERENCES album_title_events(attempt_id,event_ordinal) ON DELETE RESTRICT
) STRICT;
CREATE TRIGGER album_title_semantic_initial BEFORE INSERT ON album_title_semantic_events
 WHEN NOT EXISTS(SELECT 1 FROM album_bindings b JOIN album_title_attempts a ON a.binding_id=b.binding_id
 JOIN album_title_events e ON e.attempt_id=a.attempt_id AND e.epoch=a.epoch
 WHERE b.binding_id=NEW.binding_id AND b.binding_revision=NEW.binding_revision_before
 AND a.attempt_id=NEW.attempt_id AND a.epoch=NEW.epoch AND e.event_ordinal=NEW.event_ordinal AND e.semantic_change=1
 AND e.event_ordinal=(SELECT MAX(event_ordinal) FROM album_title_events WHERE attempt_id=a.attempt_id))
 BEGIN SELECT RAISE(ABORT,'album_title_semantic_inconsistent'); END;
CREATE TRIGGER album_title_semantic_no_update BEFORE UPDATE ON album_title_semantic_events BEGIN SELECT RAISE(ABORT,'album_title_semantic_retained'); END;
CREATE TRIGGER album_title_semantic_no_delete BEFORE DELETE ON album_title_semantic_events BEGIN SELECT RAISE(ABORT,'album_title_semantic_retained'); END;
CREATE TRIGGER album_title_semantic_no_replace BEFORE INSERT ON album_title_semantic_events
 WHEN EXISTS(SELECT 1 FROM album_title_semantic_events WHERE (binding_id=NEW.binding_id AND binding_revision_after=NEW.binding_revision_after) OR (attempt_id=NEW.attempt_id AND event_ordinal=NEW.event_ordinal))
 BEGIN SELECT RAISE(ABORT,'album_title_semantic_retained'); END;
CREATE TRIGGER album_title_attempt_initial BEFORE INSERT ON album_title_attempts
 WHEN NEW.state<>'claimed' OR NEW.dispatch_count<>0 OR NEW.read_count<>0 OR NEW.completed_at_us IS NOT NULL
 OR NEW.observed_title IS NOT NULL OR NEW.remote_missing<>0 OR NEW.next_read_at_us<>0
 OR NEW.satisfied_title_revision IS NOT NULL
 OR NEW.lease_binding_revision<>NEW.binding_revision
 OR NEW.started_at_us<>(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000)
 OR NEW.lease_expires_at_us<>NEW.started_at_us+11000000 OR NEW.invocation_deadline_at_us<>NEW.started_at_us+10000000
 OR NEW.epoch<>COALESCE((SELECT MAX(epoch)+1 FROM album_title_attempts WHERE binding_id=NEW.binding_id),1)
 OR NEW.attempt_number<>COALESCE((SELECT MAX(attempt_number)+1 FROM album_title_attempts WHERE binding_id=NEW.binding_id AND title_revision=NEW.title_revision),1)
 OR EXISTS(SELECT 1 FROM album_title_attempts WHERE binding_id=NEW.binding_id AND completed_at_us IS NULL)
 OR NOT EXISTS(SELECT 1 FROM album_title_worker_authority a WHERE a.binding_id=NEW.binding_id AND a.user_id=NEW.user_id
 AND a.owner_nsid=NEW.owner_nsid AND a.flickr_photoset_id=NEW.photoset_id AND a.link_revision=NEW.link_revision
 AND a.grant_generation=NEW.grant_generation AND a.deployment_gate_revision=NEW.deployment_gate_revision AND a.user_gate_revision=NEW.user_gate_revision
 AND a.desired_title=NEW.desired_title AND a.title_revision=NEW.title_revision AND a.binding_revision=NEW.binding_revision AND a.lifecycle_state='materialization_pending')
 OR NOT EXISTS(SELECT 1 FROM album_binding_remote_status s WHERE s.binding_id=NEW.binding_id AND s.materialization_state='materialized')
 OR EXISTS(SELECT 1 FROM album_title_attempts x WHERE x.binding_id=NEW.binding_id AND x.title_revision=NEW.title_revision
  AND (x.state<>'retry_pending' OR x.next_read_at_us>(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000)))
 BEGIN SELECT RAISE(ABORT,'album_title_attempt_initial'); END;
CREATE TRIGGER album_title_attempt_update BEFORE UPDATE ON album_title_attempts
 WHEN OLD.completed_at_us IS NOT NULL OR NEW.attempt_id<>OLD.attempt_id OR NEW.binding_id<>OLD.binding_id
 OR NEW.user_id<>OLD.user_id OR NEW.owner_nsid<>OLD.owner_nsid OR NEW.photoset_id<>OLD.photoset_id
 OR NEW.link_revision<>OLD.link_revision OR NEW.grant_generation<>OLD.grant_generation
 OR NEW.desired_title<>OLD.desired_title OR NEW.title_revision<>OLD.title_revision
 OR NEW.deployment_gate_revision<>OLD.deployment_gate_revision OR NEW.user_gate_revision<>OLD.user_gate_revision
 OR NEW.attempt_number<>OLD.attempt_number OR NEW.started_at_us<>OLD.started_at_us
 OR NEW.binding_revision<>OLD.binding_revision
 OR (NEW.lease_binding_revision<>OLD.lease_binding_revision AND NEW.lease_id=OLD.lease_id)
 OR NEW.dispatch_count<OLD.dispatch_count OR NEW.dispatch_count>OLD.dispatch_count+1
 OR NEW.read_count<OLD.read_count OR NEW.read_count>OLD.read_count+1
 OR NEW.remote_missing<OLD.remote_missing
 OR (NEW.lease_id=OLD.lease_id AND NEW.lease_expires_at_us>OLD.lease_expires_at_us)
 OR (NEW.state<>OLD.state AND NOT (
  (OLD.state='claimed' AND NEW.state IN ('dispatched','synced','superseded','reconciliation_pending','needs_attention','local_removed'))
  OR (OLD.state IN ('dispatched','result_received','reconciliation_pending') AND NEW.state IN ('result_received','synced','superseded','retry_pending','conflict','reconciliation_pending','needs_attention','local_removed','claimed'))
  OR (OLD.state='needs_attention' AND OLD.dispatch_count=0 AND NEW.state IN ('superseded','local_removed'))))
 OR (NEW.state='claimed' AND NEW.dispatch_count<>0)
 OR (NEW.state='dispatched' AND NEW.dispatch_count<>1)
 OR (NEW.state='result_received' AND (NEW.dispatch_count<>1 OR NEW.result_class IS NULL))
 OR (NEW.state='reconciliation_pending' AND NEW.read_count=0)
 OR ((NEW.observed_title IS NOT OLD.observed_title OR NEW.observed_at_us IS NOT OLD.observed_at_us)
  AND (NEW.read_count=0 OR NEW.observed_title IS NULL OR NEW.observed_at_us<>(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000)))
 OR (NEW.satisfied_title_revision IS NOT OLD.satisfied_title_revision AND (NEW.state<>'synced'
  OR NOT EXISTS(SELECT 1 FROM album_bindings b WHERE b.binding_id=OLD.binding_id AND b.title_revision=NEW.satisfied_title_revision AND b.desired_title=NEW.observed_title)))
 OR (OLD.dispatch_count=1 AND (NEW.pre_dispatch_title IS NOT OLD.pre_dispatch_title OR NEW.dispatch_started_at_us IS NOT OLD.dispatch_started_at_us))
 OR (OLD.result_class IS NOT NULL AND NEW.result_class IS NOT OLD.result_class)
 OR (NEW.completed_at_us IS NOT NULL AND NEW.completed_at_us<>(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000))
 OR ((NEW.lease_id<>OLD.lease_id OR NEW.epoch<>OLD.epoch OR NEW.invocation_deadline_at_us<>OLD.invocation_deadline_at_us)
  AND (OLD.lease_expires_at_us>(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000)
   OR NEW.epoch<>OLD.epoch+1 OR NEW.lease_id=OLD.lease_id
   OR NEW.invocation_deadline_at_us<>(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000+10000000)
   OR NEW.lease_expires_at_us<>NEW.invocation_deadline_at_us+1000000
   OR NOT EXISTS(SELECT 1 FROM album_bindings b WHERE b.binding_id=OLD.binding_id AND b.binding_revision=NEW.lease_binding_revision)
   OR NEW.state<>OLD.state OR NEW.read_count<>OLD.read_count OR NEW.dispatch_count<>OLD.dispatch_count))
 OR (NEW.dispatch_count=1 AND OLD.dispatch_count=0 AND (OLD.state<>'claimed' OR NEW.state<>'dispatched' OR OLD.read_count<1 OR OLD.read_count>=5
  OR NEW.pre_dispatch_title=OLD.desired_title OR NEW.dispatch_started_at_us<>(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000)
  OR NOT EXISTS(SELECT 1 FROM album_bindings b WHERE b.binding_id=OLD.binding_id AND b.title_revision=OLD.title_revision
   AND b.desired_title=OLD.desired_title AND b.state='materialization_pending')
  OR NOT EXISTS(SELECT 1 FROM album_binding_remote_status s WHERE s.binding_id=OLD.binding_id AND s.materialization_state='materialized')))
 OR (NEW.read_count>OLD.read_count AND (OLD.read_count>=5
  OR (NEW.state<>OLD.state AND NOT (OLD.dispatch_count=0 AND OLD.state='reconciliation_pending' AND NEW.state='claimed'))
  OR OLD.next_read_at_us>(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000)
  OR NEW.next_read_at_us<(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000)
   +CASE WHEN (OLD.dispatch_count=1 AND NEW.read_count<=2) OR (OLD.dispatch_count=0 AND NEW.read_count<2) THEN 5000000 ELSE 30000000 END))
 OR (NEW.state IN ('synced','conflict','retry_pending') AND (NEW.observed_title IS NULL OR NEW.observed_at_us<>(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000)))
 OR (NEW.state='synced' AND NOT EXISTS(SELECT 1 FROM album_bindings b WHERE b.binding_id=OLD.binding_id AND NEW.observed_title=b.desired_title))
 OR (NEW.state='conflict' AND (OLD.dispatch_count<>1 OR NEW.observed_title=OLD.desired_title OR NEW.observed_title=OLD.pre_dispatch_title
  OR EXISTS(SELECT 1 FROM album_bindings b WHERE b.binding_id=OLD.binding_id AND b.desired_title=NEW.observed_title)))
 OR (NEW.state='retry_pending' AND (OLD.dispatch_count<>1 OR NEW.observed_title<>OLD.pre_dispatch_title OR OLD.attempt_number>=3
  OR NOT EXISTS(SELECT 1 FROM album_bindings b WHERE b.binding_id=OLD.binding_id AND b.title_revision=OLD.title_revision AND b.state='materialization_pending')))
 OR (NEW.state='needs_attention' AND NEW.completed_at_us IS NOT NULL AND (OLD.dispatch_count<>1 OR OLD.attempt_number<>3
  OR NEW.observed_title IS NOT OLD.pre_dispatch_title OR NEW.observed_at_us<>NEW.completed_at_us))
 OR (NEW.state='superseded' AND NOT EXISTS(SELECT 1 FROM album_bindings b WHERE b.binding_id=OLD.binding_id AND b.title_revision>OLD.title_revision))
 OR (NEW.state IN ('superseded','local_removed') AND OLD.dispatch_count=1
  AND (NEW.observed_title IS NULL OR NEW.observed_at_us<>(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000)))
 OR (NEW.state='superseded' AND OLD.dispatch_count=1 AND NEW.observed_title<>OLD.desired_title AND NEW.observed_title<>OLD.pre_dispatch_title)
 OR (NEW.state='local_removed' AND NOT EXISTS(SELECT 1 FROM album_bindings b WHERE b.binding_id=OLD.binding_id AND b.state='local_collection_removed_remote_preserved'))
 OR (NEW.lease_id=OLD.lease_id AND NOT (OLD.dispatch_count=0 AND NEW.state IN ('superseded','local_removed'))
 AND NOT (NEW.state='needs_attention' AND OLD.read_count=5 AND OLD.lease_expires_at_us<=(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000))
 AND NOT EXISTS(SELECT 1 FROM album_bindings b WHERE b.binding_id=OLD.binding_id
 AND b.binding_revision=COALESCE((SELECT MAX(e.binding_revision_after) FROM album_title_semantic_events e WHERE e.attempt_id=OLD.attempt_id AND e.epoch=OLD.epoch),OLD.lease_binding_revision)))
 OR ((NEW.state NOT IN ('superseded','local_removed') OR OLD.dispatch_count=1)
 AND NOT (NEW.state='needs_attention' AND OLD.read_count=5 AND OLD.lease_expires_at_us<=(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000))
 AND NOT EXISTS(SELECT 1 FROM album_title_worker_authority a
 WHERE a.binding_id=OLD.binding_id AND a.user_id=OLD.user_id AND a.owner_nsid=OLD.owner_nsid AND a.flickr_photoset_id=OLD.photoset_id
 AND a.link_revision=OLD.link_revision AND a.grant_generation=OLD.grant_generation
 AND a.deployment_gate_revision=OLD.deployment_gate_revision AND a.user_gate_revision=OLD.user_gate_revision))
 OR (NEW.lease_id=OLD.lease_id AND (NEW.state NOT IN ('superseded','local_removed') OR OLD.dispatch_count=1)
  AND NOT (NEW.state='needs_attention' AND OLD.read_count=5 AND OLD.lease_expires_at_us<=(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000))
  AND (OLD.lease_expires_at_us<=(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000)
   OR OLD.invocation_deadline_at_us<=(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000)))
 BEGIN SELECT RAISE(ABORT,'album_title_attempt_fenced'); END;
CREATE TRIGGER album_title_attempt_no_delete BEFORE DELETE ON album_title_attempts BEGIN SELECT RAISE(ABORT,'album_title_attempt_retained'); END;
CREATE TRIGGER album_title_attempt_no_replace BEFORE INSERT ON album_title_attempts
 WHEN EXISTS(SELECT 1 FROM album_title_attempts WHERE attempt_id=NEW.attempt_id OR lease_id=NEW.lease_id OR (binding_id=NEW.binding_id AND epoch=NEW.epoch))
 BEGIN SELECT RAISE(ABORT,'album_title_attempt_retained'); END;
CREATE TRIGGER album_title_event_initial BEFORE INSERT ON album_title_events
 WHEN NEW.event_ordinal<>COALESCE((SELECT MAX(event_ordinal)+1 FROM album_title_events WHERE attempt_id=NEW.attempt_id),1)
 OR NOT EXISTS(SELECT 1 FROM album_title_attempts a WHERE a.attempt_id=NEW.attempt_id AND a.state=NEW.state
  AND a.epoch=NEW.epoch AND a.dispatch_count=NEW.dispatch_count AND a.read_count=NEW.read_count)
 BEGIN SELECT RAISE(ABORT,'album_title_event_inconsistent'); END;
CREATE TRIGGER album_title_event_no_update BEFORE UPDATE ON album_title_events BEGIN SELECT RAISE(ABORT,'album_title_event_retained'); END;
CREATE TRIGGER album_title_event_no_delete BEFORE DELETE ON album_title_events BEGIN SELECT RAISE(ABORT,'album_title_event_retained'); END;
CREATE TRIGGER album_title_event_no_replace BEFORE INSERT ON album_title_events
 WHEN EXISTS(SELECT 1 FROM album_title_events WHERE attempt_id=NEW.attempt_id AND event_ordinal=NEW.event_ordinal)
 BEGIN SELECT RAISE(ABORT,'album_title_event_retained'); END;
CREATE TRIGGER album_title_attempt_created AFTER INSERT ON album_title_attempts BEGIN
 INSERT INTO album_title_events(attempt_id,event_ordinal,state,epoch,dispatch_count,read_count) VALUES(NEW.attempt_id,1,NEW.state,NEW.epoch,NEW.dispatch_count,NEW.read_count);
END;
CREATE TRIGGER album_title_attempt_changed AFTER UPDATE ON album_title_attempts BEGIN
 INSERT INTO album_title_events(attempt_id,event_ordinal,state,epoch,dispatch_count,read_count,semantic_change)
 SELECT NEW.attempt_id,MAX(event_ordinal)+1,NEW.state,NEW.epoch,NEW.dispatch_count,NEW.read_count,
 (NOT (OLD.dispatch_count=0 AND NEW.state IN ('superseded','local_removed')) AND
  (NEW.dispatch_count<>OLD.dispatch_count OR NEW.observed_title IS NOT OLD.observed_title OR NEW.observed_at_us IS NOT OLD.observed_at_us
   OR NEW.remote_missing<>OLD.remote_missing OR (NEW.state='needs_attention')<>(OLD.state='needs_attention')
   OR (OLD.dispatch_count=1 AND (NEW.completed_at_us IS NULL)<>(OLD.completed_at_us IS NULL))))
 FROM album_title_events WHERE attempt_id=NEW.attempt_id;
 INSERT INTO album_title_semantic_events(binding_id,binding_revision_before,binding_revision_after,attempt_id,epoch,event_ordinal)
 SELECT NEW.binding_id,b.binding_revision,b.binding_revision+1,NEW.attempt_id,NEW.epoch,e.event_ordinal
 FROM album_bindings b JOIN album_title_events e ON e.attempt_id=NEW.attempt_id
 WHERE b.binding_id=NEW.binding_id AND e.event_ordinal=(SELECT MAX(event_ordinal) FROM album_title_events WHERE attempt_id=NEW.attempt_id) AND e.semantic_change=1;
 UPDATE album_bindings SET binding_revision=binding_revision+1 WHERE binding_id=NEW.binding_id
 AND EXISTS(SELECT 1 FROM album_title_semantic_events e WHERE e.attempt_id=NEW.attempt_id AND e.epoch=NEW.epoch
 AND e.binding_revision_before=album_bindings.binding_revision AND e.binding_revision_after=album_bindings.binding_revision+1
 AND e.event_ordinal=(SELECT MAX(event_ordinal) FROM album_title_events WHERE attempt_id=NEW.attempt_id));
END;
CREATE TRIGGER album_title_binding_changed AFTER UPDATE ON album_bindings BEGIN
 UPDATE album_title_attempts SET state=CASE WHEN NEW.state='local_collection_removed_remote_preserved' THEN 'local_removed' ELSE 'superseded' END,
 completed_at_us=(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000)
 WHERE binding_id=NEW.binding_id AND completed_at_us IS NULL AND dispatch_count=0
 AND (NEW.title_revision>title_revision OR NEW.state='local_collection_removed_remote_preserved');
END;
-- Expose missing evidence without changing or clearing immutable bound identity
-- or rewriting the preceding materialization state machine/history.
DROP VIEW album_binding_remote_status;
CREATE VIEW album_binding_remote_status AS
 SELECT b.binding_id,CASE WHEN EXISTS(SELECT 1 FROM album_title_attempts t
 WHERE t.binding_id=b.binding_id AND t.photoset_id=b.flickr_photoset_id AND t.owner_nsid=b.owner_nsid
 AND t.remote_missing=1) THEN 'remote_album_missing_needs_attention' ELSE b.materialization_state END materialization_state
 FROM album_bindings b;
