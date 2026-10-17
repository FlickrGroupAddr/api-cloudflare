-- An owner-selected identity is retained separately from the ambiguous POST.
-- The original terminal attempt and its dispatch evidence are never rewritten.
CREATE TABLE album_create_repair_receipts (
 binding_id TEXT PRIMARY KEY NOT NULL REFERENCES album_bindings(binding_id) ON DELETE RESTRICT,
 attempt_id TEXT NOT NULL UNIQUE REFERENCES album_materialization_attempts(attempt_id) ON DELETE RESTRICT,
 expected_binding_revision INTEGER NOT NULL CHECK(expected_binding_revision BETWEEN 1 AND 9007199254740990),
 selected_photoset_id TEXT NOT NULL CHECK(length(selected_photoset_id) BETWEEN 1 AND 128 AND selected_photoset_id<>'0'
  AND substr(selected_photoset_id,1,1) GLOB '[A-Za-z0-9]' AND selected_photoset_id NOT GLOB '*[^A-Za-z0-9@._:-]*'),
 navigation_url TEXT NOT NULL CHECK(length(navigation_url) BETWEEN 1 AND 2048),
 owner_nsid TEXT NOT NULL,first_photo_binding_id TEXT NOT NULL,first_photo_id TEXT NOT NULL,
 link_revision INTEGER NOT NULL,grant_generation TEXT NOT NULL,
 deployment_gate_revision INTEGER NOT NULL,user_gate_revision INTEGER NOT NULL,
 lifecycle TEXT NOT NULL CHECK(lifecycle IN ('materialization_pending','local_collection_removed_remote_preserved')),
 authority_kind TEXT NOT NULL CHECK(authority_kind IN ('installation','admin')),
 authority_id TEXT NOT NULL,authority_digest TEXT NOT NULL CHECK(length(authority_digest)=64),
 owner_sub TEXT NOT NULL,principal_revision INTEGER NOT NULL CHECK(principal_revision BETWEEN 0 AND 9007199254740991),
 authority_revision INTEGER NOT NULL CHECK(authority_revision BETWEEN 1 AND 9007199254740991),
 context_observed_at_us INTEGER NOT NULL,deadline_at_us INTEGER NOT NULL,
 proof_context_ids TEXT NOT NULL,proof_observed_at_us INTEGER NOT NULL,
 request_correlation_id TEXT NOT NULL CHECK(length(request_correlation_id)=36),
 provenance TEXT NOT NULL DEFAULT 'owner_reconciled_ambiguous_album_create'
  CHECK(provenance='owner_reconciled_ambiguous_album_create'),
 created_at_us INTEGER NOT NULL DEFAULT(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000),
 CHECK(deadline_at_us=context_observed_at_us+10000000),
 CHECK(proof_observed_at_us BETWEEN context_observed_at_us AND created_at_us)
) STRICT;
CREATE TRIGGER album_create_repair_initial BEFORE INSERT ON album_create_repair_receipts
 WHEN NEW.created_at_us<>(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000)
 OR NEW.deadline_at_us<=NEW.created_at_us OR NEW.context_observed_at_us>NEW.created_at_us
 OR (NEW.authority_kind='installation' AND NOT EXISTS(SELECT 1 FROM installations i
  JOIN installation_credential_versions c ON c.installation_id=i.installation_id AND c.version_id=i.current_version_id
  JOIN album_bindings b ON b.user_id=i.user_id
  WHERE b.binding_id=NEW.binding_id AND i.installation_id=NEW.authority_id AND i.revision=NEW.authority_revision
  AND c.credential_digest=NEW.authority_digest AND i.state='active' AND i.credential_class='lrc_plugin'
  AND c.state='current' AND c.expires_at_us IS NULL AND NEW.lifecycle='materialization_pending'))
 OR (NEW.authority_kind='admin' AND NOT EXISTS(SELECT 1 FROM admin_sessions s JOIN admin_principals p ON p.user_id=s.user_id
  JOIN album_bindings b ON b.user_id=s.user_id WHERE b.binding_id=NEW.binding_id
  AND s.session_id=NEW.authority_id AND s.token_digest=NEW.authority_digest AND s.revision=NEW.authority_revision
  AND s.revoked_at_us IS NULL AND s.expires_at_us>NEW.created_at_us
  AND p.google_issuer='https://accounts.google.com' AND p.google_sub=NEW.owner_sub AND p.session_set_revision=NEW.principal_revision))
 OR NOT EXISTS(SELECT 1 FROM album_materialization_authority v JOIN album_bindings b ON b.binding_id=v.binding_id
  JOIN album_materialization_attempts a ON a.binding_id=b.binding_id AND a.attempt_id=NEW.attempt_id
  JOIN album_photo_obligations o ON o.obligation_id=b.first_obligation_id
  WHERE b.binding_id=NEW.binding_id AND b.binding_revision=NEW.expected_binding_revision
  AND b.state=NEW.lifecycle AND b.flickr_photoset_id IS NULL AND b.materialization_state='create_outcome_unknown'
  AND b.materialization_revision<9007199254740991 AND o.obligation_revision<9007199254740991 AND o.state='waiting_for_album'
  AND a.state='create_outcome_unknown' AND a.dispatch_count=1 AND a.completed_at_us IS NOT NULL
  AND a.pre_context_ids IS NOT NULL AND a.pre_context_observed_at_us IS NOT NULL
  AND a.user_id=b.user_id AND a.owner_nsid=NEW.owner_nsid AND a.photo_id=NEW.first_photo_id
  AND a.photo_binding_id=NEW.first_photo_binding_id AND v.owner_nsid=NEW.owner_nsid
  AND v.photo_id=NEW.first_photo_id AND v.photo_binding_id=NEW.first_photo_binding_id
  AND v.link_revision=NEW.link_revision AND a.link_revision=NEW.link_revision
  AND v.grant_generation=NEW.grant_generation AND a.grant_generation=NEW.grant_generation
  AND v.deployment_gate_revision=NEW.deployment_gate_revision AND a.deployment_gate_revision=NEW.deployment_gate_revision
  AND v.user_gate_revision=NEW.user_gate_revision AND a.user_gate_revision=NEW.user_gate_revision)
 OR EXISTS(SELECT 1 FROM album_bindings b WHERE b.owner_nsid=NEW.owner_nsid AND b.flickr_photoset_id=NEW.selected_photoset_id)
 OR NOT json_valid(NEW.proof_context_ids) OR json_type(NEW.proof_context_ids)<>'array'
 OR json_array_length(NEW.proof_context_ids)>1000 OR length(NEW.proof_context_ids)>1048576
 OR EXISTS(SELECT 1 FROM json_each(NEW.proof_context_ids) WHERE type<>'text' OR value='0' OR length(value) NOT BETWEEN 1 AND 128
  OR substr(value,1,1) NOT GLOB '[A-Za-z0-9]' OR value GLOB '*[^A-Za-z0-9@._:-]*')
 OR (SELECT COUNT(*) FROM json_each(NEW.proof_context_ids))<>(SELECT COUNT(DISTINCT value) FROM json_each(NEW.proof_context_ids))
 OR NOT EXISTS(SELECT 1 FROM json_each(NEW.proof_context_ids) WHERE value=NEW.selected_photoset_id)
 OR NEW.navigation_url GLOB '*[^!-~]*' OR instr(NEW.navigation_url,char(92))>0
 OR instr(NEW.navigation_url,'?')>0 OR instr(NEW.navigation_url,'#')>0
 OR NOT (NEW.navigation_url GLOB 'https://www.flickr.com/photos/*/sets/*' OR NEW.navigation_url GLOB 'https://www.flickr.com/photos/*/albums/*'
  OR NEW.navigation_url GLOB 'https://flickr.com/photos/*/sets/*' OR NEW.navigation_url GLOB 'https://flickr.com/photos/*/albums/*')
 OR substr(rtrim(NEW.navigation_url,'/'),-length(NEW.selected_photoset_id)-1)<>'/'||NEW.selected_photoset_id
 BEGIN SELECT RAISE(ABORT,'album_create_repair_fenced'); END;
CREATE TRIGGER album_create_repair_no_update BEFORE UPDATE ON album_create_repair_receipts
 BEGIN SELECT RAISE(ABORT,'album_create_repair_retained'); END;
CREATE TRIGGER album_create_repair_no_delete BEFORE DELETE ON album_create_repair_receipts
 BEGIN SELECT RAISE(ABORT,'album_create_repair_retained'); END;
CREATE TRIGGER album_create_repair_no_replace BEFORE INSERT ON album_create_repair_receipts
 WHEN EXISTS(SELECT 1 FROM album_create_repair_receipts WHERE binding_id=NEW.binding_id OR attempt_id=NEW.attempt_id)
 BEGIN SELECT RAISE(ABORT,'album_create_repair_retained'); END;

DROP TRIGGER album_materialization_binding_guard;
CREATE TRIGGER album_materialization_binding_guard BEFORE UPDATE ON album_bindings
 WHEN (NEW.materialization_state<>OLD.materialization_state OR NEW.flickr_photoset_id IS NOT OLD.flickr_photoset_id OR NEW.navigation_url IS NOT OLD.navigation_url)
 AND NOT EXISTS(SELECT 1 FROM album_materialization_attempts a WHERE a.binding_id=OLD.binding_id
 AND ((a.state='dispatched' AND OLD.materialization_state='pending' AND NEW.materialization_state='creating' AND NEW.flickr_photoset_id IS NULL AND NEW.navigation_url IS NULL)
 OR (a.state='verified' AND OLD.materialization_state='creating' AND NEW.materialization_state='materialized' AND NEW.flickr_photoset_id=a.photoset_id AND NEW.navigation_url=a.navigation_url)
 OR (a.state IN ('create_outcome_unknown','create_rejected') AND OLD.materialization_state='creating' AND NEW.materialization_state=a.state AND NEW.flickr_photoset_id IS NULL AND NEW.navigation_url IS NULL)))
 AND NOT EXISTS(SELECT 1 FROM album_create_repair_receipts r WHERE r.binding_id=OLD.binding_id
  AND r.expected_binding_revision=OLD.binding_revision AND NEW.binding_revision=OLD.binding_revision+1
  AND OLD.materialization_state='create_outcome_unknown' AND OLD.flickr_photoset_id IS NULL
  AND NEW.materialization_state='materialized' AND NEW.flickr_photoset_id=r.selected_photoset_id AND NEW.navigation_url=r.navigation_url)
 BEGIN SELECT RAISE(ABORT,'album_materialization_binding_guard'); END;

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
    AND r.first_photo_id=OLD.photo_id AND r.first_photo_binding_id=OLD.photo_binding_id))))
 BEGIN SELECT RAISE(ABORT,'album_obligation_immutable'); END;
CREATE TRIGGER album_create_repair_committed AFTER INSERT ON album_create_repair_receipts BEGIN
 UPDATE album_bindings SET flickr_photoset_id=NEW.selected_photoset_id,navigation_url=NEW.navigation_url,
  materialization_state='materialized',materialization_revision=materialization_revision+1,binding_revision=binding_revision+1
  WHERE binding_id=NEW.binding_id;
 UPDATE album_photo_obligations SET state='membership_verified',obligation_revision=obligation_revision+1
  WHERE obligation_id=(SELECT first_obligation_id FROM album_bindings WHERE binding_id=NEW.binding_id);
END;
CREATE TRIGGER album_create_repair_audited AFTER INSERT ON album_create_repair_receipts
 WHEN NEW.authority_kind='admin' BEGIN
 INSERT INTO audit_events(event_id,user_id,action,request_correlation_id,session_correlation_id,outcome,reason,target_id)
 SELECT lower(hex(randomblob(16))),s.user_id,'album_create_repair.resolved',NEW.request_correlation_id,
  s.correlation_id,'succeeded','owner_reconciled_ambiguous_album_create',NEW.binding_id
 FROM admin_sessions s WHERE s.session_id=NEW.authority_id;
END;
CREATE VIEW album_binding_remote_status AS
 SELECT binding_id,materialization_state FROM album_bindings;
-- Read projection only; retained queue/admission rows remain the work authority.
CREATE VIEW album_obligation_status AS
 SELECT o.obligation_id,o.album_binding_id,o.photo_binding_id,o.photo_id,o.obligation_revision,
 CASE WHEN o.state='waiting_for_album' AND b.flickr_photoset_id IS NOT NULL THEN 'attachment_pending' ELSE o.state END state,
 o.local_relationship,o.admission_binding_revision,
 CASE WHEN o.obligation_id=b.first_obligation_id THEN COALESCE(r.proof_observed_at_us,a.proof_observed_at_us) ELSE NULL END membership_observed_at_us
 FROM album_photo_obligations o JOIN album_bindings b ON b.binding_id=o.album_binding_id
 LEFT JOIN album_create_repair_receipts r ON r.binding_id=b.binding_id
 LEFT JOIN album_materialization_attempts a ON a.binding_id=b.binding_id AND a.state='verified';
