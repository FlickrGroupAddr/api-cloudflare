-- Dormant first-photo create coordination. No runtime entry point is enabled.
-- Rebuild only CHECK domains; preserve every admission and historical timestamp.
-- D1 forbids TEMP tables. Fixed migration-only scratch tables are created and
-- dropped in this same atomic migration batch; failures roll back all copies.
PRAGMA defer_foreign_keys=ON;
DROP TRIGGER album_obligation_initial;
DROP TRIGGER album_obligation_no_update;
DROP TRIGGER album_obligation_no_delete;
DROP TRIGGER album_obligation_no_replace;
DROP TRIGGER album_obligation_event_consistent;
DROP TRIGGER album_obligation_event_no_update;
DROP TRIGGER album_obligation_event_no_delete;
DROP TRIGGER album_obligation_event_no_replace;
DROP TRIGGER album_obligation_admitted;
DROP TRIGGER album_obligation_archived;
DROP TRIGGER album_binding_created;
DROP TRIGGER album_binding_revision;
DROP TRIGGER album_binding_archive_obligations;
CREATE TABLE retained_album_obligations AS SELECT * FROM album_photo_obligations;
CREATE TABLE retained_album_obligation_events AS SELECT * FROM album_obligation_events;
DROP TABLE album_obligation_events;
DROP TABLE album_photo_obligations;
CREATE TABLE album_photo_obligations (
 obligation_id TEXT PRIMARY KEY NOT NULL CHECK(length(obligation_id)=36 AND obligation_id=lower(obligation_id)
  AND obligation_id GLOB '????????-????-4???-[89ab]???-????????????'
  AND length(replace(obligation_id,'-',''))=32 AND replace(obligation_id,'-','') NOT GLOB '*[^0-9a-f]*'),
 album_binding_id TEXT NOT NULL REFERENCES album_bindings(binding_id) ON DELETE RESTRICT,
 photo_binding_id TEXT NOT NULL REFERENCES photo_bindings(binding_id) ON DELETE RESTRICT,
 photo_id TEXT NOT NULL,
 obligation_revision INTEGER NOT NULL DEFAULT 1 CHECK(obligation_revision BETWEEN 1 AND 9007199254740991),
 state TEXT NOT NULL DEFAULT 'waiting_for_album' CHECK(state IN ('waiting_for_album','attachment_pending','membership_verified')),
 local_relationship TEXT NOT NULL DEFAULT 'active' CHECK(local_relationship IN ('active','archived')),
 admission_binding_revision INTEGER NOT NULL CHECK(admission_binding_revision BETWEEN 1 AND 9007199254740991),
 UNIQUE(album_binding_id,photo_binding_id),
 UNIQUE(album_binding_id,admission_binding_revision),
 UNIQUE(obligation_id,album_binding_id,photo_binding_id,photo_id)
) STRICT;
CREATE TABLE album_obligation_events (
 obligation_id TEXT NOT NULL REFERENCES album_photo_obligations(obligation_id) ON DELETE RESTRICT,
 obligation_revision INTEGER NOT NULL CHECK(obligation_revision BETWEEN 1 AND 9007199254740991),
 kind TEXT NOT NULL CHECK(kind IN ('obligation_admitted','relationship_archived','receipt_migrated','membership_verified')),
 state TEXT NOT NULL CHECK(state IN ('waiting_for_album','attachment_pending','membership_verified')),
 local_relationship TEXT NOT NULL CHECK(local_relationship IN ('active','archived')),
 created_at_us INTEGER NOT NULL DEFAULT(CAST(strftime('%s','now') AS INTEGER)*1000000
  + CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000),
 PRIMARY KEY(obligation_id,obligation_revision)
) STRICT;
INSERT INTO album_photo_obligations SELECT * FROM retained_album_obligations;
INSERT INTO album_obligation_events SELECT * FROM retained_album_obligation_events;
DROP TABLE retained_album_obligations;
DROP TABLE retained_album_obligation_events;
CREATE TABLE album_materialization_migration_guard(ok INTEGER NOT NULL CHECK(ok=1)) STRICT;
INSERT INTO album_materialization_migration_guard SELECT NOT EXISTS(SELECT 1 FROM pragma_foreign_key_check);
DROP TABLE album_materialization_migration_guard;
PRAGMA defer_foreign_keys=OFF;
ALTER TABLE album_bindings ADD COLUMN materialization_state TEXT NOT NULL DEFAULT 'pending'
 CHECK(materialization_state IN ('pending','creating','materialized','create_outcome_unknown','create_rejected'));
ALTER TABLE album_bindings ADD COLUMN materialization_revision INTEGER NOT NULL DEFAULT 1 CHECK(materialization_revision BETWEEN 1 AND 9007199254740991);
ALTER TABLE album_bindings ADD COLUMN navigation_url TEXT;
-- Existing remote identities are facts, not newly invented worker results.
UPDATE album_bindings SET materialization_state='materialized' WHERE flickr_photoset_id IS NOT NULL;
CREATE TRIGGER album_binding_revision BEFORE UPDATE ON album_bindings
 WHEN NEW.binding_revision<>OLD.binding_revision+
   (NEW.desired_title<>OLD.desired_title OR NEW.flickr_photoset_id IS NOT OLD.flickr_photoset_id OR NEW.state<>OLD.state OR NEW.materialization_state<>OLD.materialization_state
    OR EXISTS(SELECT 1 FROM album_photo_obligations o WHERE o.album_binding_id=OLD.binding_id
      AND o.admission_binding_revision=OLD.binding_revision+1
      AND NOT EXISTS(SELECT 1 FROM album_binding_events e WHERE e.binding_id=OLD.binding_id
       AND e.binding_revision=o.admission_binding_revision)))
  OR NEW.materialization_revision<>OLD.materialization_revision+(NEW.materialization_state<>OLD.materialization_state)
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
  OR NEW.admission_binding_revision<>OLD.admission_binding_revision
  OR NEW.obligation_revision<>OLD.obligation_revision+1
  OR NOT (
   (NEW.state=OLD.state AND OLD.local_relationship='active' AND NEW.local_relationship='archived'
    AND EXISTS(SELECT 1 FROM album_bindings b WHERE b.binding_id=OLD.album_binding_id
     AND b.state='local_collection_removed_remote_preserved'))
   OR (NEW.local_relationship=OLD.local_relationship AND NEW.state='membership_verified' AND OLD.state='waiting_for_album'
    AND EXISTS(SELECT 1 FROM album_materialization_attempts a JOIN album_bindings b ON b.binding_id=a.binding_id
     WHERE b.first_obligation_id=OLD.obligation_id AND a.state='verified' AND a.photoset_id=b.flickr_photoset_id
      AND a.photo_id=OLD.photo_id AND a.photo_binding_id=OLD.photo_binding_id)))
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
  OR (NEW.obligation_revision>1 AND NEW.kind NOT IN ('membership_verified','relationship_archived'))
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
   VALUES(NEW.obligation_id,NEW.obligation_revision,CASE WHEN NEW.state='membership_verified' AND OLD.state<>NEW.state THEN 'membership_verified' ELSE 'relationship_archived' END,NEW.state,NEW.local_relationship);
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
CREATE VIEW album_materialization_authority AS
 SELECT b.binding_id,b.user_id,b.owner_nsid,b.first_photo_binding_id photo_binding_id,b.first_photo_id photo_id,
 b.link_revision,b.desired_title,b.title_revision,b.state lifecycle_state,b.materialization_state,b.flickr_photoset_id,
 n.active_generation grant_generation,d.revision deployment_gate_revision,g.revision user_gate_revision
 FROM album_bindings b JOIN publish_service_identities s ON s.service_id=b.service_id AND s.user_id=b.user_id
 JOIN photo_bindings p ON p.binding_id=b.first_photo_binding_id AND p.user_id=b.user_id AND p.photo_id=b.first_photo_id
 JOIN flickr_links l ON l.user_id=b.user_id JOIN flickr_native_credentials n ON n.user_id=b.user_id
 JOIN flickr_connection_state c ON c.user_id=b.user_id
 JOIN flickr_write_gates d ON d.scope='deployment' AND d.scope_id='*'
 JOIN flickr_write_gates g ON g.scope='user' AND g.scope_id=b.user_id
 WHERE s.link_revision=b.link_revision AND s.owner_nsid=b.owner_nsid
 AND l.state='linked' AND l.link_revision=b.link_revision AND l.owner_nsid=b.owner_nsid
 AND n.link_revision=b.link_revision AND n.verified_owner_nsid=b.owner_nsid AND n.operation_id IS NULL
 AND n.verified_permission IN ('write','delete') AND c.state='linked' AND c.local_state='available'
 AND c.operation_id IS NULL AND c.verified_permission IN ('write','delete') AND c.external_removal=0
 AND d.enabled=1 AND g.enabled=1 AND d.revision BETWEEN 1 AND 9007199254740991 AND g.revision BETWEEN 1 AND 9007199254740991
 AND p.link_revision=b.link_revision AND p.owner_nsid=b.owner_nsid AND p.binding_id<>'0' AND p.photo_id<>'0'
 AND p.verification_revision BETWEEN 1 AND 9007199254740991
 AND p.verified_at_us BETWEEN 0 AND (CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000)
 AND (EXISTS(SELECT 1 FROM photo_binding_events e WHERE e.binding_id=p.binding_id AND e.verification_revision=p.verification_revision AND e.kind='existing_public_verified')
 OR EXISTS(SELECT 1 FROM upload_photo_binding_events e WHERE e.binding_id=p.binding_id AND e.verification_revision=p.verification_revision AND e.link_revision=p.link_revision AND e.verified_at_us=p.verified_at_us));

CREATE TABLE album_materialization_attempts (
 attempt_id TEXT PRIMARY KEY NOT NULL CHECK(length(attempt_id)=36),
 binding_id TEXT NOT NULL REFERENCES album_bindings(binding_id) ON DELETE RESTRICT,
 lease_id TEXT NOT NULL UNIQUE CHECK(length(lease_id)=36),
 epoch INTEGER NOT NULL CHECK(epoch BETWEEN 1 AND 9007199254740991),
 user_id TEXT NOT NULL,owner_nsid TEXT NOT NULL,photo_binding_id TEXT NOT NULL,photo_id TEXT NOT NULL,
 link_revision INTEGER NOT NULL,grant_generation TEXT NOT NULL,
 desired_title TEXT NOT NULL,title_revision INTEGER NOT NULL,
 deployment_gate_revision INTEGER NOT NULL,user_gate_revision INTEGER NOT NULL,
 started_at_us INTEGER NOT NULL DEFAULT(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000),
 invocation_deadline_at_us INTEGER NOT NULL DEFAULT(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000+45000000),
 lease_expires_at_us INTEGER NOT NULL DEFAULT(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000+60000000),
 state TEXT NOT NULL DEFAULT 'claimed' CHECK(state IN ('claimed','dispatched','result_received','verified','create_outcome_unknown','create_rejected','abandoned_before_dispatch')),
 dispatch_count INTEGER NOT NULL DEFAULT 0 CHECK(dispatch_count IN (0,1)),
 dispatch_started_at_us INTEGER,pre_context_ids TEXT,pre_context_observed_at_us INTEGER,
 received_photoset_id TEXT,received_navigation_url TEXT,received_at_us INTEGER,
 completed_at_us INTEGER,photoset_id TEXT,navigation_url TEXT,proof_context_ids TEXT,
 proof_owner_nsid TEXT,proof_photo_id TEXT,proof_observed_at_us INTEGER,flickr_code INTEGER,
 UNIQUE(binding_id,epoch),
 CHECK((dispatch_count=0 AND dispatch_started_at_us IS NULL AND pre_context_ids IS NULL AND pre_context_observed_at_us IS NULL)
 OR (dispatch_count=1 AND dispatch_started_at_us IS NOT NULL AND pre_context_ids IS NOT NULL AND pre_context_observed_at_us IS NOT NULL)),
 CHECK((state IN ('claimed','dispatched','result_received') AND completed_at_us IS NULL) OR (state NOT IN ('claimed','dispatched','result_received') AND completed_at_us IS NOT NULL)),
 CHECK((state IN ('claimed','abandoned_before_dispatch') AND dispatch_count=0) OR (state NOT IN ('claimed','abandoned_before_dispatch') AND dispatch_count=1)),
 CHECK(state<>'verified' OR (photoset_id IS NOT NULL AND navigation_url IS NOT NULL AND proof_context_ids IS NOT NULL
 AND proof_owner_nsid IS NOT NULL AND proof_photo_id IS NOT NULL AND proof_observed_at_us IS NOT NULL)),
 CHECK(state='verified' OR (photoset_id IS NULL AND navigation_url IS NULL AND proof_context_ids IS NULL AND proof_owner_nsid IS NULL AND proof_photo_id IS NULL AND proof_observed_at_us IS NULL)),
 CHECK(state='create_rejected' OR flickr_code IS NULL),
 CHECK(state<>'create_rejected' OR (flickr_code IS NOT NULL AND flickr_code IN (1,2,3,95,96,97,98,99,100))),
 CHECK((received_photoset_id IS NULL AND received_navigation_url IS NULL AND received_at_us IS NULL) OR
 (received_photoset_id IS NOT NULL AND received_navigation_url IS NOT NULL AND received_at_us IS NOT NULL)),
 CHECK(state NOT IN ('result_received','verified') OR received_photoset_id IS NOT NULL)
) STRICT;
CREATE UNIQUE INDEX album_one_active_materialization ON album_materialization_attempts(binding_id) WHERE completed_at_us IS NULL;
CREATE UNIQUE INDEX album_one_create_dispatch ON album_materialization_attempts(binding_id) WHERE dispatch_count=1;
CREATE INDEX album_materialization_due ON album_materialization_attempts(lease_expires_at_us,binding_id) WHERE completed_at_us IS NULL;
CREATE TABLE album_materialization_events (
 attempt_id TEXT NOT NULL REFERENCES album_materialization_attempts(attempt_id) ON DELETE RESTRICT,
 event_ordinal INTEGER NOT NULL,state TEXT NOT NULL,epoch INTEGER NOT NULL,dispatch_count INTEGER NOT NULL,
 dispatch_started_at_us INTEGER,created_at_us INTEGER NOT NULL DEFAULT(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000),
 PRIMARY KEY(attempt_id,event_ordinal),UNIQUE(attempt_id,state)
) STRICT;
CREATE TRIGGER album_materialization_initial BEFORE INSERT ON album_materialization_attempts
 WHEN NEW.state<>'claimed' OR NEW.dispatch_count<>0 OR NEW.completed_at_us IS NOT NULL
 OR NEW.epoch<>COALESCE((SELECT MAX(epoch)+1 FROM album_materialization_attempts WHERE binding_id=NEW.binding_id),1)
 OR NEW.started_at_us<>(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000)
 OR NEW.lease_expires_at_us<>NEW.started_at_us+60000000 OR NEW.invocation_deadline_at_us<>NEW.started_at_us+45000000
 OR NEW.received_photoset_id IS NOT NULL OR NEW.received_navigation_url IS NOT NULL OR NEW.received_at_us IS NOT NULL
 OR EXISTS(SELECT 1 FROM album_materialization_attempts WHERE binding_id=NEW.binding_id AND (completed_at_us IS NULL OR dispatch_count=1))
 OR NOT EXISTS(SELECT 1 FROM album_materialization_authority v WHERE v.binding_id=NEW.binding_id
 AND v.user_id=NEW.user_id AND v.owner_nsid=NEW.owner_nsid AND v.photo_binding_id=NEW.photo_binding_id AND v.photo_id=NEW.photo_id
 AND v.link_revision=NEW.link_revision AND v.grant_generation=NEW.grant_generation
 AND v.desired_title=NEW.desired_title AND v.title_revision=NEW.title_revision
 AND v.deployment_gate_revision=NEW.deployment_gate_revision AND v.user_gate_revision=NEW.user_gate_revision
 AND v.materialization_state='pending' AND v.flickr_photoset_id IS NULL)
 BEGIN SELECT RAISE(ABORT,'album_materialization_initial'); END;
CREATE TRIGGER album_materialization_update BEFORE UPDATE ON album_materialization_attempts
 WHEN OLD.completed_at_us IS NOT NULL
 OR NEW.attempt_id<>OLD.attempt_id OR NEW.binding_id<>OLD.binding_id OR NEW.lease_id<>OLD.lease_id OR NEW.epoch<>OLD.epoch
 OR NEW.started_at_us<>OLD.started_at_us OR NEW.lease_expires_at_us<>OLD.lease_expires_at_us OR NEW.invocation_deadline_at_us<>OLD.invocation_deadline_at_us
 OR NEW.user_id<>OLD.user_id OR NEW.owner_nsid<>OLD.owner_nsid OR NEW.photo_binding_id<>OLD.photo_binding_id OR NEW.photo_id<>OLD.photo_id
 OR NEW.link_revision<>OLD.link_revision OR NEW.grant_generation<>OLD.grant_generation
 OR NEW.desired_title<>OLD.desired_title OR NEW.title_revision<>OLD.title_revision
 OR NEW.deployment_gate_revision<>OLD.deployment_gate_revision OR NEW.user_gate_revision<>OLD.user_gate_revision
 OR EXISTS(SELECT 1 FROM album_materialization_attempts x WHERE x.binding_id=OLD.binding_id AND x.epoch>OLD.epoch)
 OR NOT ((OLD.state='claimed' AND NEW.state IN ('dispatched','abandoned_before_dispatch'))
 OR (OLD.state='dispatched' AND NEW.state IN ('result_received','create_outcome_unknown','create_rejected'))
 OR (OLD.state='result_received' AND NEW.state IN ('verified','create_outcome_unknown')))
 OR (OLD.received_photoset_id IS NOT NULL AND (NEW.received_photoset_id IS NOT OLD.received_photoset_id
 OR NEW.received_navigation_url IS NOT OLD.received_navigation_url OR NEW.received_at_us IS NOT OLD.received_at_us))
 OR (OLD.received_photoset_id IS NULL AND NEW.state<>'result_received' AND (NEW.received_photoset_id IS NOT NULL OR NEW.received_navigation_url IS NOT NULL OR NEW.received_at_us IS NOT NULL))
 OR (OLD.dispatch_count=1 AND (NEW.dispatch_count<>1 OR NEW.dispatch_started_at_us IS NOT OLD.dispatch_started_at_us
 OR NEW.pre_context_ids IS NOT OLD.pre_context_ids OR NEW.pre_context_observed_at_us IS NOT OLD.pre_context_observed_at_us))
 OR (NEW.completed_at_us IS NOT NULL AND NEW.completed_at_us<>(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000))
 OR (NEW.state NOT IN ('abandoned_before_dispatch','create_outcome_unknown') AND (
 OLD.lease_expires_at_us<=(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000)
 OR OLD.invocation_deadline_at_us-(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000)<=CASE WHEN NEW.state='dispatched' THEN 15000000 ELSE 5000000 END
 OR OLD.lease_expires_at_us-(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000)<=CASE WHEN NEW.state='dispatched' THEN 15000000 ELSE 5000000 END
 OR NOT EXISTS(SELECT 1 FROM album_materialization_authority v WHERE v.binding_id=OLD.binding_id
 AND v.user_id=OLD.user_id AND v.owner_nsid=OLD.owner_nsid AND v.photo_binding_id=OLD.photo_binding_id AND v.photo_id=OLD.photo_id
 AND v.link_revision=OLD.link_revision AND v.grant_generation=OLD.grant_generation
 AND v.deployment_gate_revision=OLD.deployment_gate_revision AND v.user_gate_revision=OLD.user_gate_revision
 AND v.flickr_photoset_id IS NULL)))
 OR (NEW.state='dispatched' AND (NEW.dispatch_started_at_us<>(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000)
 OR NEW.pre_context_observed_at_us<>NEW.dispatch_started_at_us OR NEW.dispatch_count<>1
 OR NOT EXISTS(SELECT 1 FROM album_bindings b WHERE b.binding_id=OLD.binding_id AND b.desired_title=OLD.desired_title AND b.title_revision=OLD.title_revision)))
 OR (NEW.state='result_received' AND (NEW.received_at_us<>(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000)
 OR length(NEW.received_photoset_id) NOT BETWEEN 1 AND 128 OR NEW.received_photoset_id='0'
 OR substr(NEW.received_photoset_id,1,1) NOT GLOB '[A-Za-z0-9]' OR NEW.received_photoset_id GLOB '*[^A-Za-z0-9@._:-]*'
 OR length(NEW.received_navigation_url) NOT BETWEEN 1 AND 2048
 OR NEW.received_navigation_url GLOB '*[^!-~]*' OR instr(NEW.received_navigation_url,char(92))>0
 OR instr(NEW.received_navigation_url,'?')>0 OR instr(NEW.received_navigation_url,'#')>0
 OR NOT (NEW.received_navigation_url GLOB 'https://www.flickr.com/photos/*/sets/*'
 OR NEW.received_navigation_url GLOB 'https://www.flickr.com/photos/*/albums/*'
 OR NEW.received_navigation_url GLOB 'https://flickr.com/photos/*/sets/*'
 OR NEW.received_navigation_url GLOB 'https://flickr.com/photos/*/albums/*')))
 OR (NEW.state='verified' AND (NEW.photoset_id IS NOT OLD.received_photoset_id OR NEW.navigation_url IS NOT OLD.received_navigation_url OR NEW.proof_owner_nsid<>OLD.owner_nsid OR NEW.proof_photo_id<>OLD.photo_id
 OR NEW.proof_observed_at_us<>NEW.completed_at_us OR NEW.photoset_id='0' OR length(NEW.photoset_id) NOT BETWEEN 1 AND 128
 OR substr(NEW.photoset_id,1,1) NOT GLOB '[A-Za-z0-9]' OR NEW.photoset_id GLOB '*[^A-Za-z0-9@._:-]*'
 OR length(NEW.navigation_url) NOT BETWEEN 1 AND 2048 OR NEW.navigation_url NOT GLOB 'https://*'
 OR NOT EXISTS(SELECT 1 FROM json_each(NEW.proof_context_ids) WHERE value=NEW.photoset_id)))
 BEGIN SELECT RAISE(ABORT,'album_materialization_fenced'); END;
-- Exact complete context sets are admitted once, never permissively filtered.
CREATE TRIGGER album_materialization_contexts BEFORE UPDATE ON album_materialization_attempts
 WHEN (NEW.pre_context_ids IS NOT NULL AND (NOT json_valid(NEW.pre_context_ids) OR json_type(NEW.pre_context_ids)<>'array'
 OR json_array_length(NEW.pre_context_ids)>1000 OR length(NEW.pre_context_ids)>1048576
 OR EXISTS(SELECT 1 FROM json_each(NEW.pre_context_ids) WHERE type<>'text' OR value='0' OR length(value) NOT BETWEEN 1 AND 128
 OR substr(value,1,1) NOT GLOB '[A-Za-z0-9]' OR value GLOB '*[^A-Za-z0-9@._:-]*')
 OR (SELECT COUNT(*) FROM json_each(NEW.pre_context_ids))<>(SELECT COUNT(DISTINCT value) FROM json_each(NEW.pre_context_ids))))
 OR (NEW.proof_context_ids IS NOT NULL AND (NOT json_valid(NEW.proof_context_ids) OR json_type(NEW.proof_context_ids)<>'array'
 OR json_array_length(NEW.proof_context_ids)>1000 OR length(NEW.proof_context_ids)>1048576
 OR EXISTS(SELECT 1 FROM json_each(NEW.proof_context_ids) WHERE type<>'text' OR value='0' OR length(value) NOT BETWEEN 1 AND 128
 OR substr(value,1,1) NOT GLOB '[A-Za-z0-9]' OR value GLOB '*[^A-Za-z0-9@._:-]*')
 OR (SELECT COUNT(*) FROM json_each(NEW.proof_context_ids))<>(SELECT COUNT(DISTINCT value) FROM json_each(NEW.proof_context_ids))))
 BEGIN SELECT RAISE(ABORT,'album_materialization_contexts'); END;
CREATE TRIGGER album_materialization_no_delete BEFORE DELETE ON album_materialization_attempts BEGIN SELECT RAISE(ABORT,'album_materialization_retained'); END;
CREATE TRIGGER album_materialization_no_replace BEFORE INSERT ON album_materialization_attempts
 WHEN EXISTS(SELECT 1 FROM album_materialization_attempts WHERE attempt_id=NEW.attempt_id OR lease_id=NEW.lease_id OR (binding_id=NEW.binding_id AND epoch=NEW.epoch))
 BEGIN SELECT RAISE(ABORT,'album_materialization_retained'); END;
CREATE TRIGGER album_materialization_event_consistent BEFORE INSERT ON album_materialization_events
 WHEN NEW.event_ordinal<>COALESCE((SELECT MAX(event_ordinal)+1 FROM album_materialization_events WHERE attempt_id=NEW.attempt_id),1)
 OR NOT EXISTS(SELECT 1 FROM album_materialization_attempts a WHERE a.attempt_id=NEW.attempt_id AND a.state=NEW.state AND a.epoch=NEW.epoch
 AND a.dispatch_count=NEW.dispatch_count AND a.dispatch_started_at_us IS NEW.dispatch_started_at_us)
 BEGIN SELECT RAISE(ABORT,'album_materialization_event_inconsistent'); END;
CREATE TRIGGER album_materialization_event_no_update BEFORE UPDATE ON album_materialization_events BEGIN SELECT RAISE(ABORT,'album_materialization_event_retained'); END;
CREATE TRIGGER album_materialization_event_no_delete BEFORE DELETE ON album_materialization_events BEGIN SELECT RAISE(ABORT,'album_materialization_event_retained'); END;
CREATE TRIGGER album_materialization_event_no_replace BEFORE INSERT ON album_materialization_events
 WHEN EXISTS(SELECT 1 FROM album_materialization_events WHERE attempt_id=NEW.attempt_id AND event_ordinal=NEW.event_ordinal)
 BEGIN SELECT RAISE(ABORT,'album_materialization_event_retained'); END;
CREATE TRIGGER album_materialization_created AFTER INSERT ON album_materialization_attempts BEGIN
 INSERT INTO album_materialization_events(attempt_id,event_ordinal,state,epoch,dispatch_count,dispatch_started_at_us)
 VALUES(NEW.attempt_id,1,NEW.state,NEW.epoch,NEW.dispatch_count,NEW.dispatch_started_at_us);
END;
CREATE TRIGGER album_materialization_changed AFTER UPDATE ON album_materialization_attempts BEGIN
 INSERT INTO album_materialization_events(attempt_id,event_ordinal,state,epoch,dispatch_count,dispatch_started_at_us)
 SELECT NEW.attempt_id,MAX(event_ordinal)+1,NEW.state,NEW.epoch,NEW.dispatch_count,NEW.dispatch_started_at_us FROM album_materialization_events WHERE attempt_id=NEW.attempt_id;
 UPDATE album_bindings SET materialization_state=CASE NEW.state WHEN 'dispatched' THEN 'creating' WHEN 'verified' THEN 'materialized' ELSE NEW.state END,
 materialization_revision=materialization_revision+1,binding_revision=binding_revision+1,
 flickr_photoset_id=CASE WHEN NEW.state='verified' THEN NEW.photoset_id ELSE flickr_photoset_id END,
 navigation_url=CASE WHEN NEW.state='verified' THEN NEW.navigation_url ELSE navigation_url END
 WHERE binding_id=NEW.binding_id AND NEW.state NOT IN ('abandoned_before_dispatch','result_received');
 UPDATE album_photo_obligations SET state='membership_verified',obligation_revision=obligation_revision+1
 WHERE obligation_id=(SELECT first_obligation_id FROM album_bindings WHERE binding_id=NEW.binding_id) AND NEW.state='verified';
END;
CREATE TRIGGER album_materialization_binding_guard BEFORE UPDATE ON album_bindings
 WHEN (NEW.materialization_state<>OLD.materialization_state OR NEW.flickr_photoset_id IS NOT OLD.flickr_photoset_id OR NEW.navigation_url IS NOT OLD.navigation_url)
 AND NOT EXISTS(SELECT 1 FROM album_materialization_attempts a WHERE a.binding_id=OLD.binding_id
 AND ((a.state='dispatched' AND OLD.materialization_state='pending' AND NEW.materialization_state='creating' AND NEW.flickr_photoset_id IS NULL AND NEW.navigation_url IS NULL)
 OR (a.state='verified' AND OLD.materialization_state='creating' AND NEW.materialization_state='materialized' AND NEW.flickr_photoset_id=a.photoset_id AND NEW.navigation_url=a.navigation_url)
 OR (a.state IN ('create_outcome_unknown','create_rejected') AND OLD.materialization_state='creating' AND NEW.materialization_state=a.state AND NEW.flickr_photoset_id IS NULL AND NEW.navigation_url IS NULL)))
 BEGIN SELECT RAISE(ABORT,'album_materialization_binding_guard'); END;
CREATE TRIGGER album_materialization_binding_initial BEFORE INSERT ON album_bindings
 WHEN NEW.materialization_state<>'pending' OR NEW.materialization_revision<>1 OR NEW.navigation_url IS NOT NULL
 BEGIN SELECT RAISE(ABORT,'album_materialization_binding_initial'); END;
