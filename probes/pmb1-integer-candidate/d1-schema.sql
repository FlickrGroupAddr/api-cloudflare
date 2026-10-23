-- NEW isolated prospective fixture ONLY; never apply to existing state.
-- Scoped hosted foundation: installation reads and protected-history probes.
-- Database time is formatted to six digits but currently sampled at SQLite millisecond resolution.
CREATE TABLE fga_users (
 user_id TEXT PRIMARY KEY NOT NULL
) STRICT;
CREATE TABLE installations (
 installation_id TEXT PRIMARY KEY NOT NULL,
 user_id TEXT NOT NULL REFERENCES fga_users(user_id) ON DELETE RESTRICT,
 credential_class TEXT NOT NULL CHECK(credential_class='lrc_plugin'),
 label TEXT NOT NULL DEFAULT '',
 state TEXT NOT NULL CHECK(state IN ('active','revoked')),
 revision INTEGER NOT NULL CHECK(revision BETWEEN 1 AND 9007199254740991),
 current_version_id TEXT,
 pending_version_id TEXT,
 created_at_utc TEXT NOT NULL DEFAULT(strftime('%Y-%m-%dT%H:%M:%f','now') || '000Z'),
 revoked_at_utc TEXT,
 current_kind TEXT GENERATED ALWAYS AS ('current') VIRTUAL,
 pending_kind TEXT GENERATED ALWAYS AS ('pending_rotation') VIRTUAL,
 UNIQUE(installation_id,state),
 UNIQUE(installation_id,current_version_id),
 UNIQUE(installation_id,pending_version_id),
 CHECK((state='active' AND current_version_id IS NOT NULL) OR
       (state='revoked' AND current_version_id IS NULL AND pending_version_id IS NULL)),
 FOREIGN KEY(installation_id,current_version_id,current_kind)
   REFERENCES installation_credential_versions(installation_id,version_id,state)
   DEFERRABLE INITIALLY DEFERRED,
 FOREIGN KEY(installation_id,pending_version_id,pending_kind)
   REFERENCES installation_credential_versions(installation_id,version_id,state)
   DEFERRABLE INITIALLY DEFERRED
) STRICT;
CREATE TABLE installation_credential_versions (
 version_id TEXT PRIMARY KEY NOT NULL,
 installation_id TEXT NOT NULL REFERENCES installations(installation_id) ON DELETE RESTRICT
   DEFERRABLE INITIALLY DEFERRED,
 credential_digest TEXT NOT NULL UNIQUE CHECK(length(credential_digest)=64 AND credential_digest NOT GLOB '*[^0-9a-f]*'),
 state TEXT NOT NULL CHECK(state IN ('current','pending_rotation','replaced','revoked','expired_unactivated')),
 ordinal INTEGER NOT NULL CHECK(ordinal>0),
 expires_at_us INTEGER,
 created_at_utc TEXT NOT NULL DEFAULT(strftime('%Y-%m-%dT%H:%M:%f','now') || '000Z'),
 current_link TEXT GENERATED ALWAYS AS (CASE WHEN state='current' THEN version_id END) VIRTUAL,
 pending_link TEXT GENERATED ALWAYS AS (CASE WHEN state='pending_rotation' THEN version_id END) VIRTUAL,
 active_parent TEXT GENERATED ALWAYS AS (CASE WHEN state IN ('current','pending_rotation') THEN 'active' END) VIRTUAL,
 CHECK(state<>'current' OR expires_at_us IS NULL),
 CHECK(state<>'pending_rotation' OR expires_at_us IS NOT NULL),
 UNIQUE(installation_id,version_id,state),
 UNIQUE(installation_id,ordinal),
 FOREIGN KEY(installation_id,current_link) REFERENCES installations(installation_id,current_version_id)
   DEFERRABLE INITIALLY DEFERRED,
 FOREIGN KEY(installation_id,pending_link) REFERENCES installations(installation_id,pending_version_id)
   DEFERRABLE INITIALLY DEFERRED,
 FOREIGN KEY(installation_id,active_parent) REFERENCES installations(installation_id,state)
   DEFERRABLE INITIALLY DEFERRED
) STRICT;
CREATE UNIQUE INDEX one_current ON installation_credential_versions(installation_id) WHERE state='current';
CREATE UNIQUE INDEX one_pending ON installation_credential_versions(installation_id) WHERE state='pending_rotation';
CREATE TRIGGER installation_identity_immutable BEFORE UPDATE ON installations
 WHEN NEW.installation_id<>OLD.installation_id OR NEW.user_id<>OLD.user_id OR NEW.credential_class<>OLD.credential_class
 BEGIN SELECT RAISE(ABORT,'installation_identity_immutable'); END;
CREATE TRIGGER installation_revision_guard BEFORE UPDATE ON installations
 WHEN NEW.revision<OLD.revision OR
 ((NEW.state<>OLD.state OR NEW.current_version_id IS NOT OLD.current_version_id OR NEW.pending_version_id IS NOT OLD.pending_version_id)
  AND NEW.revision<>OLD.revision+1)
 BEGIN SELECT RAISE(ABORT,'installation_revision_guard'); END;
CREATE TRIGGER version_identity_immutable BEFORE UPDATE ON installation_credential_versions
 WHEN NEW.version_id<>OLD.version_id OR NEW.installation_id<>OLD.installation_id OR
      NEW.credential_digest<>OLD.credential_digest OR NEW.ordinal<>OLD.ordinal
 BEGIN SELECT RAISE(ABORT,'version_identity_immutable'); END;
CREATE TRIGGER version_state_transition BEFORE UPDATE OF state ON installation_credential_versions
 WHEN NEW.state<>OLD.state AND NOT (
  (OLD.state='current' AND NEW.state IN ('replaced','revoked')) OR
  (OLD.state='pending_rotation' AND NEW.state IN ('current','revoked','expired_unactivated')))
 BEGIN SELECT RAISE(ABORT,'version_state_transition'); END;
CREATE TRIGGER version_ordinal_guard BEFORE INSERT ON installation_credential_versions
 WHEN NEW.ordinal<=COALESCE((SELECT MAX(ordinal) FROM installation_credential_versions WHERE installation_id=NEW.installation_id),0)
 BEGIN SELECT RAISE(ABORT,'version_ordinal_guard'); END;
CREATE TABLE submission_blocks (
 photo_id TEXT NOT NULL, group_id TEXT NOT NULL,
 first_reason TEXT NOT NULL CHECK(first_reason IN ('flickr_code_6','flickr_code_7','delivery_uncertain')),
 source_attempt_id TEXT NOT NULL,
 created_at_utc TEXT NOT NULL DEFAULT(strftime('%Y-%m-%dT%H:%M:%f','now') || '000Z'),
 PRIMARY KEY(photo_id,group_id)
) STRICT;
CREATE TRIGGER block_no_update BEFORE UPDATE ON submission_blocks BEGIN SELECT RAISE(ABORT,'block_immutable'); END;
CREATE TRIGGER block_no_delete BEFORE DELETE ON submission_blocks BEGIN SELECT RAISE(ABORT,'block_immutable'); END;
CREATE TRIGGER block_no_replace BEFORE INSERT ON submission_blocks
 WHEN EXISTS(SELECT 1 FROM submission_blocks WHERE photo_id=NEW.photo_id AND group_id=NEW.group_id)
 BEGIN SELECT RAISE(ABORT,'block_immutable'); END;
CREATE TABLE audit_events (
 event_id TEXT PRIMARY KEY NOT NULL,
 user_id TEXT REFERENCES fga_users(user_id) ON DELETE RESTRICT,
 action TEXT NOT NULL,
 request_correlation_id TEXT NOT NULL,
 session_correlation_id TEXT,
 outcome TEXT NOT NULL CHECK(outcome IN ('succeeded','failed')),
 reason TEXT NOT NULL,
 target_id TEXT,
 created_at_utc TEXT NOT NULL DEFAULT(strftime('%Y-%m-%dT%H:%M:%f','now') || '000Z')
) STRICT;
CREATE TRIGGER audit_no_update BEFORE UPDATE ON audit_events BEGIN SELECT RAISE(ABORT,'audit_immutable'); END;
CREATE TRIGGER audit_no_delete BEFORE DELETE ON audit_events BEGIN SELECT RAISE(ABORT,'audit_immutable'); END;
CREATE TRIGGER audit_no_replace BEFORE INSERT ON audit_events
 WHEN EXISTS(SELECT 1 FROM audit_events WHERE event_id=NEW.event_id)
 BEGIN SELECT RAISE(ABORT,'audit_immutable'); END;

CREATE TRIGGER installation_no_delete BEFORE DELETE ON installations BEGIN SELECT RAISE(ABORT,'installation_history_retained'); END;
CREATE TRIGGER installation_no_replace BEFORE INSERT ON installations
 WHEN EXISTS(SELECT 1 FROM installations WHERE installation_id=NEW.installation_id)
 BEGIN SELECT RAISE(ABORT,'installation_history_retained'); END;
CREATE TRIGGER version_no_delete BEFORE DELETE ON installation_credential_versions BEGIN SELECT RAISE(ABORT,'version_history_retained'); END;
CREATE TRIGGER version_no_replace BEFORE INSERT ON installation_credential_versions
 WHEN EXISTS(SELECT 1 FROM installation_credential_versions WHERE version_id=NEW.version_id OR credential_digest=NEW.credential_digest)
 BEGIN SELECT RAISE(ABORT,'version_history_retained'); END;

CREATE TRIGGER installation_creation_immutable BEFORE UPDATE OF created_at_utc ON installations
 WHEN NEW.created_at_utc<>OLD.created_at_utc
 BEGIN SELECT RAISE(ABORT,'installation_creation_immutable'); END;
CREATE TRIGGER installation_revocation_terminal BEFORE UPDATE OF state ON installations
 WHEN OLD.state='revoked' AND NEW.state<>'revoked'
 BEGIN SELECT RAISE(ABORT,'installation_revocation_terminal'); END;
CREATE TRIGGER version_creation_immutable BEFORE UPDATE OF created_at_utc ON installation_credential_versions
 WHEN NEW.created_at_utc<>OLD.created_at_utc
 BEGIN SELECT RAISE(ABORT,'version_creation_immutable'); END;
CREATE TRIGGER version_expiry_immutable BEFORE UPDATE OF expires_at_us ON installation_credential_versions
 WHEN NEW.expires_at_us IS NOT OLD.expires_at_us AND NOT
 (OLD.state='pending_rotation' AND NEW.state='current' AND NEW.expires_at_us IS NULL)
 BEGIN SELECT RAISE(ABORT,'version_expiry_immutable'); END;

-- Upgrade an existing foundation without rewriting protected history.
ALTER TABLE audit_events ADD COLUMN source_component TEXT NOT NULL DEFAULT 'fga_api_backend';
CREATE INDEX audit_event_page ON audit_events(created_at_utc DESC,event_id DESC);
CREATE INDEX pending_credential_expiry ON installation_credential_versions(state,expires_at_us);

-- Native admission/scheduling candidate. All durable authority stays in this D1 database.
CREATE TABLE flickr_links (
 user_id TEXT PRIMARY KEY REFERENCES fga_users(user_id) ON DELETE RESTRICT,
 owner_nsid TEXT NOT NULL,
 link_revision INTEGER NOT NULL CHECK(link_revision>0),
 state TEXT NOT NULL CHECK(state IN ('linked','paused','disconnected'))
) STRICT;
CREATE TABLE photo_bindings (
 binding_id TEXT PRIMARY KEY NOT NULL,
 user_id TEXT NOT NULL REFERENCES fga_users(user_id) ON DELETE RESTRICT,
 photo_id TEXT NOT NULL UNIQUE,
 owner_nsid TEXT NOT NULL,
 link_revision INTEGER NOT NULL CHECK(link_revision>0),
 verification_revision INTEGER NOT NULL CHECK(verification_revision>0),
 source_kind TEXT NOT NULL CHECK(source_kind IN ('upload','existing_public')),
 verified_at_us INTEGER NOT NULL DEFAULT((CAST(strftime('%s','now') AS INTEGER)*1000000 + CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000)),
 last_admission_at_us INTEGER,
 UNIQUE(binding_id,user_id,photo_id)
) STRICT;
CREATE TRIGGER binding_identity_immutable BEFORE UPDATE ON photo_bindings
 WHEN NEW.binding_id<>OLD.binding_id OR NEW.user_id<>OLD.user_id OR
 NEW.photo_id<>OLD.photo_id OR NEW.owner_nsid<>OLD.owner_nsid OR NEW.source_kind<>OLD.source_kind
 BEGIN SELECT RAISE(ABORT,'binding_identity_immutable'); END;
CREATE TRIGGER binding_no_delete BEFORE DELETE ON photo_bindings
 BEGIN SELECT RAISE(ABORT,'binding_retained'); END;
CREATE TRIGGER binding_no_replace BEFORE INSERT ON photo_bindings
 WHEN EXISTS(SELECT 1 FROM photo_bindings WHERE binding_id=NEW.binding_id OR photo_id=NEW.photo_id)
 BEGIN SELECT RAISE(ABORT,'binding_retained'); END;
CREATE TABLE flickr_write_gates (
 scope TEXT NOT NULL CHECK(scope IN ('deployment','user')),
 scope_id TEXT NOT NULL,
 enabled INTEGER NOT NULL CHECK(enabled IN (0,1)),
 revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>0),
 PRIMARY KEY(scope,scope_id)
) STRICT;
CREATE TABLE group_partitions (
 partition_id TEXT PRIMARY KEY NOT NULL,
 user_id TEXT NOT NULL REFERENCES fga_users(user_id) ON DELETE RESTRICT,
 group_id TEXT NOT NULL,
 next_enqueue_ordinal INTEGER NOT NULL DEFAULT 1 CHECK(next_enqueue_ordinal>0),
 next_work_not_before_us INTEGER,
 wake_revision INTEGER NOT NULL DEFAULT 0 CHECK(wake_revision>=0),
 lease_id TEXT,
 lease_generation INTEGER NOT NULL DEFAULT 0 CHECK(lease_generation>=0),
 lease_expires_at_us INTEGER,
 lease_started_at_us INTEGER,
 invocation_deadline_at_us INTEGER,
 last_claim_at_us INTEGER,
 next_probe_not_before_us INTEGER,
 UNIQUE(user_id,group_id),
 UNIQUE(partition_id,user_id,group_id),
 CHECK((lease_id IS NULL AND lease_expires_at_us IS NULL AND lease_started_at_us IS NULL AND invocation_deadline_at_us IS NULL)
    OR (lease_id IS NOT NULL AND lease_expires_at_us IS NOT NULL AND lease_started_at_us IS NOT NULL AND invocation_deadline_at_us IS NOT NULL))
) STRICT;
CREATE INDEX due_partitions ON group_partitions(next_work_not_before_us,last_claim_at_us,partition_id);
CREATE TRIGGER partition_identity_immutable BEFORE UPDATE ON group_partitions
 WHEN NEW.partition_id<>OLD.partition_id OR NEW.user_id<>OLD.user_id OR NEW.group_id<>OLD.group_id
 BEGIN SELECT RAISE(ABORT,'partition_identity_immutable'); END;
CREATE TRIGGER partition_counters_monotonic BEFORE UPDATE ON group_partitions
 WHEN NEW.next_enqueue_ordinal<OLD.next_enqueue_ordinal OR NEW.wake_revision<OLD.wake_revision OR NEW.lease_generation<OLD.lease_generation
 BEGIN SELECT RAISE(ABORT,'partition_counter_regression'); END;
CREATE TABLE submission_intents (
 intent_id TEXT PRIMARY KEY NOT NULL,
 binding_id TEXT NOT NULL,
 user_id TEXT NOT NULL,
 photo_id TEXT NOT NULL,
 group_id TEXT NOT NULL,
 partition_id TEXT NOT NULL,
 enqueue_ordinal INTEGER NOT NULL CHECK(enqueue_ordinal>0),
 state TEXT NOT NULL CHECK(state IN ('queued','attempting','retrying','throttled','added','moderation_submitted','delivery_uncertain','needs_attention','cancelled')),
 active_fifo_member INTEGER GENERATED ALWAYS AS (state IN ('queued','attempting','retrying','throttled')) STORED,
 state_version INTEGER NOT NULL DEFAULT 1 CHECK(state_version>0),
 created_at_us INTEGER NOT NULL DEFAULT((CAST(strftime('%s','now') AS INTEGER)*1000000 + CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000)),
 created_request_id TEXT NOT NULL,
 next_attempt_not_before_us INTEGER,
 terminal_at_us INTEGER,
 safe_read_failure_count INTEGER NOT NULL DEFAULT 0 CHECK(safe_read_failure_count>=0),
 add_dispatch_count INTEGER NOT NULL DEFAULT 0 CHECK(add_dispatch_count>=0),
 UNIQUE(photo_id,group_id),
 UNIQUE(partition_id,enqueue_ordinal),
 FOREIGN KEY(binding_id,user_id,photo_id) REFERENCES photo_bindings(binding_id,user_id,photo_id) ON DELETE RESTRICT,
 FOREIGN KEY(partition_id,user_id,group_id) REFERENCES group_partitions(partition_id,user_id,group_id) ON DELETE RESTRICT,
 CHECK(state<>'retrying' OR next_attempt_not_before_us IS NOT NULL),
 CHECK((active_fifo_member=1 AND terminal_at_us IS NULL) OR (active_fifo_member=0 AND terminal_at_us IS NOT NULL AND next_attempt_not_before_us IS NULL))
) STRICT;
CREATE INDEX active_partition_head ON submission_intents(partition_id,active_fifo_member,enqueue_ordinal);
CREATE INDEX intent_user_history ON submission_intents(user_id,created_at_us DESC,intent_id DESC);
CREATE INDEX intent_binding_history ON submission_intents(binding_id,created_at_us DESC,intent_id DESC);
CREATE TRIGGER intent_identity_immutable BEFORE UPDATE ON submission_intents
 WHEN NEW.intent_id<>OLD.intent_id OR NEW.binding_id<>OLD.binding_id OR NEW.user_id<>OLD.user_id OR
 NEW.photo_id<>OLD.photo_id OR NEW.group_id<>OLD.group_id OR NEW.partition_id<>OLD.partition_id OR
 NEW.enqueue_ordinal<>OLD.enqueue_ordinal OR NEW.created_at_us<>OLD.created_at_us OR NEW.created_request_id<>OLD.created_request_id
 BEGIN SELECT RAISE(ABORT,'intent_identity_immutable'); END;
CREATE TRIGGER intent_terminal_retained BEFORE UPDATE ON submission_intents
 WHEN OLD.active_fifo_member=0 AND (NEW.state<>OLD.state OR NEW.active_fifo_member<>OLD.active_fifo_member)
 BEGIN SELECT RAISE(ABORT,'terminal_intent_retained'); END;
CREATE TRIGGER intent_no_delete BEFORE DELETE ON submission_intents
 BEGIN SELECT RAISE(ABORT,'intent_retained'); END;
CREATE TRIGGER intent_no_replace BEFORE INSERT ON submission_intents
 WHEN EXISTS(SELECT 1 FROM submission_intents WHERE intent_id=NEW.intent_id OR (photo_id=NEW.photo_id AND group_id=NEW.group_id))
 BEGIN SELECT RAISE(ABORT,'intent_retained'); END;
CREATE TRIGGER intent_no_blocked_insert BEFORE INSERT ON submission_intents
 WHEN EXISTS(SELECT 1 FROM submission_blocks WHERE photo_id=NEW.photo_id AND group_id=NEW.group_id)
 BEGIN SELECT RAISE(ABORT,'pair_permanently_blocked'); END;
CREATE TABLE submission_intent_events (
 event_id TEXT PRIMARY KEY NOT NULL,
 intent_id TEXT NOT NULL REFERENCES submission_intents(intent_id) ON DELETE RESTRICT,
 kind TEXT NOT NULL,
 correlation_id TEXT NOT NULL,
 created_at_us INTEGER NOT NULL DEFAULT((CAST(strftime('%s','now') AS INTEGER)*1000000 + CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000))
) STRICT;
CREATE TRIGGER intent_event_no_update BEFORE UPDATE ON submission_intent_events BEGIN SELECT RAISE(ABORT,'intent_event_immutable'); END;
CREATE TRIGGER intent_event_no_delete BEFORE DELETE ON submission_intent_events BEGIN SELECT RAISE(ABORT,'intent_event_immutable'); END;
CREATE TRIGGER intent_event_no_replace BEFORE INSERT ON submission_intent_events
 WHEN EXISTS(SELECT 1 FROM submission_intent_events WHERE event_id=NEW.event_id)
 BEGIN SELECT RAISE(ABORT,'intent_event_immutable'); END;
CREATE TRIGGER intent_allocate BEFORE INSERT ON submission_intents
 WHEN NEW.enqueue_ordinal<>(SELECT next_enqueue_ordinal FROM group_partitions WHERE partition_id=NEW.partition_id)
 BEGIN SELECT RAISE(ABORT,'ordinal_not_current_counter'); END;
CREATE TRIGGER intent_enqueued AFTER INSERT ON submission_intents
 BEGIN
 UPDATE group_partitions SET next_enqueue_ordinal=next_enqueue_ordinal+1,
   next_work_not_before_us=CASE WHEN NEW.active_fifo_member=1 AND (SELECT COUNT(*) FROM submission_intents WHERE partition_id=NEW.partition_id AND active_fifo_member=1)=1 THEN NEW.created_at_us ELSE next_work_not_before_us END,
   wake_revision=wake_revision+CASE WHEN NEW.active_fifo_member=1 AND (SELECT COUNT(*) FROM submission_intents WHERE partition_id=NEW.partition_id AND active_fifo_member=1)=1 THEN 1 ELSE 0 END
 WHERE partition_id=NEW.partition_id;
 INSERT INTO submission_intent_events(event_id,intent_id,kind,correlation_id,created_at_us)
 VALUES(lower(hex(randomblob(16))),NEW.intent_id,'admitted',NEW.created_request_id,NEW.created_at_us);
 END;
-- A batch-local assertion/clock row, inserted and deleted in the SAME transaction.
-- This is not a receipt, idempotency key, work queue, or retained request body.
CREATE TABLE transaction_guards (
 transaction_id TEXT PRIMARY KEY NOT NULL,
 approved INTEGER NOT NULL CHECK(approved=1),
 now_us INTEGER NOT NULL DEFAULT((CAST(strftime('%s','now') AS INTEGER)*1000000 + CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000))
) STRICT;
CREATE TABLE partition_lease_events (
 event_id TEXT PRIMARY KEY NOT NULL,
 partition_id TEXT NOT NULL REFERENCES group_partitions(partition_id) ON DELETE RESTRICT,
 lease_id TEXT NOT NULL,
 lease_generation INTEGER NOT NULL CHECK(lease_generation>0),
 kind TEXT NOT NULL CHECK(kind IN ('claim','renew','release','defer')),
 invocation_id TEXT NOT NULL,
 created_at_us INTEGER NOT NULL DEFAULT((CAST(strftime('%s','now') AS INTEGER)*1000000 + CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000))
) STRICT;
CREATE TRIGGER lease_event_no_update BEFORE UPDATE ON partition_lease_events BEGIN SELECT RAISE(ABORT,'lease_event_immutable'); END;
CREATE TRIGGER lease_event_no_delete BEFORE DELETE ON partition_lease_events BEGIN SELECT RAISE(ABORT,'lease_event_immutable'); END;
CREATE TRIGGER lease_event_no_replace BEFORE INSERT ON partition_lease_events
 WHEN EXISTS(SELECT 1 FROM partition_lease_events WHERE event_id=NEW.event_id)
 BEGIN SELECT RAISE(ABORT,'lease_event_immutable'); END;

-- Candidate fail-polite durable facts. D1 is the sole authority for every row.
CREATE TABLE submission_attempts (
 attempt_id TEXT PRIMARY KEY NOT NULL,
 intent_id TEXT NOT NULL REFERENCES submission_intents(intent_id) ON DELETE RESTRICT,
 ordinal INTEGER NOT NULL CHECK(ordinal>0),
 lease_id TEXT NOT NULL,
 lease_generation INTEGER NOT NULL CHECK(lease_generation>0),
 deployment_revision INTEGER NOT NULL,
 user_revision INTEGER NOT NULL,
 link_revision INTEGER NOT NULL,
 created_at_us INTEGER NOT NULL DEFAULT((CAST(strftime('%s','now') AS INTEGER)*1000000 + CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000)),
 UNIQUE(intent_id,ordinal)
) STRICT;
CREATE TABLE attempt_membership (
 attempt_id TEXT PRIMARY KEY REFERENCES submission_attempts(attempt_id) ON DELETE RESTRICT,
 target_absent INTEGER NOT NULL CHECK(target_absent IN (0,1)),
 observed_at_us INTEGER NOT NULL DEFAULT((CAST(strftime('%s','now') AS INTEGER)*1000000 + CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000))
) STRICT;
CREATE TABLE attempt_preflights (
 attempt_id TEXT PRIMARY KEY REFERENCES submission_attempts(attempt_id) ON DELETE RESTRICT,
 moderated INTEGER NOT NULL CHECK(moderated IN (0,1)),
 observed_at_us INTEGER NOT NULL DEFAULT((CAST(strftime('%s','now') AS INTEGER)*1000000 + CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000))
) STRICT;
CREATE TABLE attempt_dispatches (
 attempt_id TEXT PRIMARY KEY REFERENCES submission_attempts(attempt_id) ON DELETE RESTRICT,
 started_at_us INTEGER NOT NULL DEFAULT((CAST(strftime('%s','now') AS INTEGER)*1000000 + CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000))
) STRICT;
CREATE TABLE attempt_resolutions (
 attempt_id TEXT PRIMARY KEY REFERENCES submission_attempts(attempt_id) ON DELETE RESTRICT,
 outcome TEXT NOT NULL CHECK(outcome IN ('added','moderation_submitted','delivery_uncertain','retrying')),
 reason TEXT NOT NULL CHECK(reason IN ('pre_add_membership_observation','flickr_added','flickr_code_3','flickr_code_6','flickr_code_7','unknown_code','unresolved_dispatch','safe_read_unavailable','flickr_code_105','flickr_code_106','abandoned_before_dispatch','not_dispatched_preflight_expired')),
 completed_at_us INTEGER NOT NULL DEFAULT((CAST(strftime('%s','now') AS INTEGER)*1000000 + CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000))
) STRICT;
CREATE TRIGGER submission_attempts_no_update BEFORE UPDATE ON submission_attempts
 BEGIN SELECT RAISE(ABORT,'attempt_evidence_immutable'); END;
CREATE TRIGGER submission_attempts_no_delete BEFORE DELETE ON submission_attempts
 BEGIN SELECT RAISE(ABORT,'attempt_evidence_immutable'); END;
CREATE TRIGGER submission_attempts_no_replace BEFORE INSERT ON submission_attempts
 WHEN EXISTS(SELECT 1 FROM submission_attempts WHERE attempt_id=NEW.attempt_id)
 BEGIN SELECT RAISE(ABORT,'attempt_evidence_immutable'); END;
CREATE TRIGGER attempt_membership_no_update BEFORE UPDATE ON attempt_membership
 BEGIN SELECT RAISE(ABORT,'attempt_evidence_immutable'); END;
CREATE TRIGGER attempt_membership_no_delete BEFORE DELETE ON attempt_membership
 BEGIN SELECT RAISE(ABORT,'attempt_evidence_immutable'); END;
CREATE TRIGGER attempt_membership_no_replace BEFORE INSERT ON attempt_membership
 WHEN EXISTS(SELECT 1 FROM attempt_membership WHERE attempt_id=NEW.attempt_id)
 BEGIN SELECT RAISE(ABORT,'attempt_evidence_immutable'); END;
CREATE TRIGGER attempt_preflights_no_update BEFORE UPDATE ON attempt_preflights
 BEGIN SELECT RAISE(ABORT,'attempt_evidence_immutable'); END;
CREATE TRIGGER attempt_preflights_no_delete BEFORE DELETE ON attempt_preflights
 BEGIN SELECT RAISE(ABORT,'attempt_evidence_immutable'); END;
CREATE TRIGGER attempt_preflights_no_replace BEFORE INSERT ON attempt_preflights
 WHEN EXISTS(SELECT 1 FROM attempt_preflights WHERE attempt_id=NEW.attempt_id)
 BEGIN SELECT RAISE(ABORT,'attempt_evidence_immutable'); END;
CREATE TRIGGER attempt_dispatches_no_update BEFORE UPDATE ON attempt_dispatches
 BEGIN SELECT RAISE(ABORT,'attempt_evidence_immutable'); END;
CREATE TRIGGER attempt_dispatches_no_delete BEFORE DELETE ON attempt_dispatches
 BEGIN SELECT RAISE(ABORT,'attempt_evidence_immutable'); END;
CREATE TRIGGER attempt_dispatches_no_replace BEFORE INSERT ON attempt_dispatches
 WHEN EXISTS(SELECT 1 FROM attempt_dispatches WHERE attempt_id=NEW.attempt_id)
 BEGIN SELECT RAISE(ABORT,'attempt_evidence_immutable'); END;
CREATE TRIGGER attempt_resolutions_no_update BEFORE UPDATE ON attempt_resolutions
 BEGIN SELECT RAISE(ABORT,'attempt_evidence_immutable'); END;
CREATE TRIGGER attempt_resolutions_no_delete BEFORE DELETE ON attempt_resolutions
 BEGIN SELECT RAISE(ABORT,'attempt_evidence_immutable'); END;
CREATE TRIGGER attempt_resolutions_no_replace BEFORE INSERT ON attempt_resolutions
 WHEN EXISTS(SELECT 1 FROM attempt_resolutions WHERE attempt_id=NEW.attempt_id)
 BEGIN SELECT RAISE(ABORT,'attempt_evidence_immutable'); END;

-- Native consumer metadata only. Lifecycle management remains gated on its
-- authenticated integration and reviewed writer identity; no credential bytes.
CREATE TABLE flickr_native_credentials (
 user_id TEXT PRIMARY KEY REFERENCES flickr_links(user_id) ON DELETE RESTRICT,
 active_generation TEXT NOT NULL CHECK(length(active_generation) BETWEEN 1 AND 128),
 link_revision INTEGER NOT NULL CHECK(link_revision>0),
 verified_owner_nsid TEXT NOT NULL,
 verified_permission TEXT NOT NULL CHECK(verified_permission IN ('write','delete')),
 operation_id TEXT,
 UNIQUE(user_id,active_generation,link_revision)
) STRICT;
CREATE TABLE photo_binding_events (
 event_id TEXT PRIMARY KEY NOT NULL,
 binding_id TEXT NOT NULL REFERENCES photo_bindings(binding_id) ON DELETE RESTRICT,
 verification_revision INTEGER NOT NULL CHECK(verification_revision>0),
 kind TEXT NOT NULL CHECK(kind='existing_public_verified'),
 created_at_us INTEGER NOT NULL DEFAULT((CAST(strftime('%s','now') AS INTEGER)*1000000 + CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000))
) STRICT;
CREATE TRIGGER photo_binding_event_no_update BEFORE UPDATE ON photo_binding_events BEGIN SELECT RAISE(ABORT,'binding_event_immutable'); END;
CREATE TRIGGER photo_binding_event_no_delete BEFORE DELETE ON photo_binding_events BEGIN SELECT RAISE(ABORT,'binding_event_immutable'); END;
CREATE TRIGGER photo_binding_event_no_replace BEFORE INSERT ON photo_binding_events
 WHEN EXISTS(SELECT 1 FROM photo_binding_events WHERE event_id=NEW.event_id)
 BEGIN SELECT RAISE(ABORT,'binding_event_immutable'); END;

CREATE TRIGGER flickr_link_identity_immutable BEFORE UPDATE ON flickr_links
 WHEN NEW.user_id<>OLD.user_id OR NEW.owner_nsid<>OLD.owner_nsid OR NEW.link_revision<OLD.link_revision
 BEGIN SELECT RAISE(ABORT,'flickr_link_identity_immutable'); END;
CREATE TRIGGER flickr_link_no_delete BEFORE DELETE ON flickr_links
 BEGIN SELECT RAISE(ABORT,'flickr_link_retained'); END;
CREATE TRIGGER flickr_link_no_replace BEFORE INSERT ON flickr_links
 WHEN EXISTS(SELECT 1 FROM flickr_links WHERE user_id=NEW.user_id)
 BEGIN SELECT RAISE(ABORT,'flickr_link_retained'); END;

-- The existing coarse link state remains the dispatch authority.
CREATE TABLE flickr_connection_state (
 user_id TEXT PRIMARY KEY REFERENCES flickr_links(user_id) ON DELETE RESTRICT,
 state TEXT NOT NULL CHECK(state IN ('unlinked','linked','replacing','repair_required','relink_required','disconnecting','disconnected')),
 local_state TEXT NOT NULL CHECK(local_state IN ('absent','available','replacement_pending','retirement_pending','retired','unknown')),
 verified_permission TEXT CHECK(verified_permission IN ('write','delete')),
 verified_at_us INTEGER,
 external_removal INTEGER NOT NULL DEFAULT 0 CHECK(external_removal IN (0,1)),
 operation_id TEXT,
 CHECK((verified_permission IS NULL)=(verified_at_us IS NULL))
) STRICT;
-- Older consumer references have no historical verification timestamp. Require repair.
INSERT INTO flickr_connection_state(user_id,state,local_state)
 SELECT user_id,CASE WHEN state='disconnected' THEN 'disconnected' ELSE 'repair_required' END,
 CASE WHEN state='disconnected' THEN 'retired' ELSE 'unknown' END FROM flickr_links;
UPDATE flickr_links SET state='paused',link_revision=link_revision+1 WHERE state='linked';
UPDATE flickr_write_gates SET enabled=0,revision=revision+1 WHERE scope='user' AND enabled=1;
CREATE TABLE flickr_lifecycle_operations (
 operation_id TEXT PRIMARY KEY,
 user_id TEXT NOT NULL REFERENCES flickr_links(user_id) ON DELETE RESTRICT,
 kind TEXT NOT NULL CHECK(kind IN ('replace','retire')),
 phase TEXT NOT NULL CHECK(phase IN ('prepared','dispatched','repair_required','complete')),
 generation TEXT NOT NULL UNIQUE,
 retiring_generation TEXT,
 preserve_relink INTEGER NOT NULL DEFAULT 0 CHECK(preserve_relink IN (0,1)),
 expected_revision INTEGER NOT NULL CHECK(expected_revision BETWEEN 1 AND 9007199254740990),
 created_at_us INTEGER NOT NULL DEFAULT(CAST(strftime('%s','now') AS INTEGER)*1000000),
 completed_at_us INTEGER,
 UNIQUE(user_id,operation_id)
) STRICT;
CREATE UNIQUE INDEX one_open_flickr_operation ON flickr_lifecycle_operations(user_id) WHERE phase<>'complete';
CREATE TRIGGER lifecycle_identity BEFORE UPDATE ON flickr_lifecycle_operations
 WHEN NEW.operation_id<>OLD.operation_id OR NEW.user_id<>OLD.user_id OR NEW.kind<>OLD.kind OR NEW.generation<>OLD.generation OR NEW.retiring_generation IS NOT OLD.retiring_generation OR NEW.preserve_relink<>OLD.preserve_relink OR NEW.expected_revision<>OLD.expected_revision OR NEW.created_at_us<>OLD.created_at_us
 BEGIN SELECT RAISE(ABORT,'lifecycle_identity'); END;
CREATE TRIGGER lifecycle_phase BEFORE UPDATE ON flickr_lifecycle_operations
 WHEN NEW.phase<>OLD.phase AND NOT ((OLD.phase='prepared' AND NEW.phase='dispatched') OR (OLD.phase='dispatched' AND NEW.phase IN ('repair_required','complete')) OR (OLD.phase='repair_required' AND NEW.phase='complete'))
 BEGIN SELECT RAISE(ABORT,'lifecycle_phase'); END;
CREATE TRIGGER lifecycle_retain BEFORE DELETE ON flickr_lifecycle_operations BEGIN SELECT RAISE(ABORT,'lifecycle_retain'); END;
CREATE TRIGGER lifecycle_no_replace BEFORE INSERT ON flickr_lifecycle_operations WHEN EXISTS(SELECT 1 FROM flickr_lifecycle_operations WHERE operation_id=NEW.operation_id OR generation=NEW.generation) BEGIN SELECT RAISE(ABORT,'lifecycle_retain'); END;

CREATE TABLE admin_principals (
 user_id TEXT PRIMARY KEY REFERENCES fga_users(user_id) ON DELETE RESTRICT,
 google_issuer TEXT NOT NULL CHECK(google_issuer='https://accounts.google.com'),
 google_sub TEXT NOT NULL UNIQUE,
 session_set_revision INTEGER NOT NULL DEFAULT 1 CHECK(session_set_revision BETWEEN 1 AND 9007199254740991)
) STRICT;
CREATE TABLE admin_sessions (
 session_id TEXT PRIMARY KEY,
 token_digest TEXT NOT NULL UNIQUE CHECK(length(token_digest)=64),
 user_id TEXT NOT NULL REFERENCES admin_principals(user_id) ON DELETE RESTRICT,
 csrf_token TEXT NOT NULL CHECK(length(csrf_token)=43),
 created_at_us INTEGER NOT NULL,
 recent_authentication_at_us INTEGER NOT NULL,
 expires_at_us INTEGER NOT NULL,
 last_activity_at_us INTEGER NOT NULL,
 revoked_at_us INTEGER,
 revocation_reason TEXT,
 revision INTEGER NOT NULL DEFAULT 1 CHECK(revision BETWEEN 1 AND 9007199254740991),
 correlation_id TEXT NOT NULL,
 CHECK(expires_at_us=created_at_us+86400000000),
 CHECK(recent_authentication_at_us=created_at_us),
 CHECK((revoked_at_us IS NULL)=(revocation_reason IS NULL))
) STRICT;
CREATE TRIGGER session_identity BEFORE UPDATE ON admin_sessions WHEN NEW.session_id<>OLD.session_id OR NEW.token_digest<>OLD.token_digest OR NEW.user_id<>OLD.user_id OR NEW.csrf_token<>OLD.csrf_token OR NEW.created_at_us<>OLD.created_at_us OR NEW.expires_at_us<>OLD.expires_at_us OR NEW.recent_authentication_at_us<>OLD.recent_authentication_at_us OR NEW.correlation_id<>OLD.correlation_id OR NEW.revision<OLD.revision OR (OLD.revoked_at_us IS NOT NULL AND (NEW.revoked_at_us IS NOT OLD.revoked_at_us OR NEW.revocation_reason IS NOT OLD.revocation_reason)) BEGIN SELECT RAISE(ABORT,'session_identity'); END;
CREATE TABLE google_login_transactions (
 state_digest TEXT PRIMARY KEY CHECK(length(state_digest)=64),
 nonce_digest TEXT NOT NULL CHECK(length(nonce_digest)=64),
 purpose TEXT NOT NULL CHECK(purpose IN ('initial_login','reauthentication')),
 bound_session_id TEXT REFERENCES admin_sessions(session_id) ON DELETE RESTRICT,
 user_id TEXT REFERENCES fga_users(user_id) ON DELETE RESTRICT,
 created_at_us INTEGER NOT NULL,
 expires_at_us INTEGER NOT NULL,
 consumed_at_us INTEGER,
 CHECK(expires_at_us=created_at_us+300000000),
 CHECK((purpose='initial_login' AND bound_session_id IS NULL AND user_id IS NULL) OR (purpose='reauthentication' AND bound_session_id IS NOT NULL AND user_id IS NOT NULL))
) STRICT;
CREATE TABLE auth_cost_events (
 event_id TEXT PRIMARY KEY,
 source_key TEXT NOT NULL CHECK(length(source_key)=64),
 route TEXT NOT NULL CHECK(route IN ('login','start','callback')),
 created_at_us INTEGER NOT NULL,
 invalid_or_inflight INTEGER NOT NULL DEFAULT 1 CHECK(invalid_or_inflight IN (0,1))
) STRICT;
CREATE INDEX auth_cost_window ON auth_cost_events(created_at_us,source_key);
CREATE TABLE auth_source_buckets (
 source_key TEXT PRIMARY KEY CHECK(length(source_key)=64),
 tokens REAL NOT NULL CHECK(tokens>=0 AND tokens<=2),
 updated_at_us INTEGER NOT NULL
) STRICT;
CREATE TABLE google_jwks_cache (
 singleton INTEGER PRIMARY KEY CHECK(singleton=1),
 keys_json TEXT,
 expires_at_us INTEGER NOT NULL DEFAULT 0,
 refresh_after_us INTEGER NOT NULL DEFAULT 0,
 refresh_owner TEXT,
 refresh_until_us INTEGER NOT NULL DEFAULT 0
) STRICT;
INSERT INTO google_jwks_cache(singleton) VALUES(1);

CREATE TRIGGER principal_identity BEFORE UPDATE ON admin_principals WHEN NEW.user_id<>OLD.user_id OR NEW.google_sub<>OLD.google_sub OR NEW.google_issuer<>OLD.google_issuer OR NEW.session_set_revision<OLD.session_set_revision BEGIN SELECT RAISE(ABORT,'principal_identity'); END;
CREATE TRIGGER principal_no_replace BEFORE INSERT ON admin_principals WHEN EXISTS(SELECT 1 FROM admin_principals WHERE user_id=NEW.user_id OR google_sub=NEW.google_sub) BEGIN SELECT RAISE(ABORT,'principal_identity'); END;
CREATE TRIGGER session_no_replace BEFORE INSERT ON admin_sessions WHEN EXISTS(SELECT 1 FROM admin_sessions WHERE session_id=NEW.session_id OR token_digest=NEW.token_digest) BEGIN SELECT RAISE(ABORT,'session_identity'); END;
CREATE TRIGGER login_transaction_identity BEFORE UPDATE ON google_login_transactions WHEN NEW.state_digest<>OLD.state_digest OR NEW.nonce_digest<>OLD.nonce_digest OR NEW.purpose<>OLD.purpose OR NEW.bound_session_id IS NOT OLD.bound_session_id OR NEW.user_id IS NOT OLD.user_id OR NEW.created_at_us<>OLD.created_at_us OR NEW.expires_at_us<>OLD.expires_at_us OR (OLD.consumed_at_us IS NOT NULL AND NEW.consumed_at_us IS NOT OLD.consumed_at_us) BEGIN SELECT RAISE(ABORT,'login_transaction_identity'); END;
CREATE TRIGGER login_transaction_no_replace BEFORE INSERT ON google_login_transactions WHEN EXISTS(SELECT 1 FROM google_login_transactions WHERE state_digest=NEW.state_digest) BEGIN SELECT RAISE(ABORT,'login_transaction_identity'); END;

-- Five fixed native temporary-secret slots; no request/access token material is in SQL.
CREATE TABLE flickr_oauth_transactions (
 transaction_id TEXT PRIMARY KEY,
 user_id TEXT NOT NULL REFERENCES fga_users(user_id) ON DELETE RESTRICT,
 session_id TEXT NOT NULL,
 state_digest TEXT NOT NULL UNIQUE CHECK(length(state_digest)=64),
 request_token_digest TEXT,
 slot INTEGER NOT NULL CHECK(slot BETWEEN 0 AND 4),
 generation TEXT NOT NULL UNIQUE,
 expected_revision INTEGER NOT NULL,
 phase TEXT NOT NULL CHECK(phase IN ('initializing','ready','exchanging','consumed','repair_required','retiring','retired')),
 created_at_us INTEGER NOT NULL,
 expires_at_us INTEGER NOT NULL,
 operation_id TEXT,
 retirement_generation TEXT,
 CHECK(expires_at_us=created_at_us+300000000)
) STRICT;
CREATE UNIQUE INDEX one_flickr_oauth_slot_owner ON flickr_oauth_transactions(slot) WHERE phase<>'retired';
CREATE TRIGGER oauth_immutable BEFORE UPDATE ON flickr_oauth_transactions WHEN NEW.transaction_id<>OLD.transaction_id OR NEW.user_id<>OLD.user_id OR NEW.session_id<>OLD.session_id OR NEW.state_digest<>OLD.state_digest OR NEW.slot<>OLD.slot OR NEW.generation<>OLD.generation OR NEW.expected_revision<>OLD.expected_revision OR NEW.created_at_us<>OLD.created_at_us OR NEW.expires_at_us<>OLD.expires_at_us OR (OLD.request_token_digest IS NOT NULL AND NEW.request_token_digest IS NOT OLD.request_token_digest) OR (OLD.phase='retired' AND NEW.phase<>'retired') BEGIN SELECT RAISE(ABORT,'oauth_immutable'); END;

-- Production dispatcher reservations and expanded retained result classifications.
-- Rebuild only the resolution relation; retain every historical row verbatim.
CREATE TABLE attempt_resolutions_v2 (
 attempt_id TEXT PRIMARY KEY REFERENCES submission_attempts(attempt_id) ON DELETE RESTRICT,
 outcome TEXT NOT NULL CHECK(outcome IN ('added','moderation_submitted','delivery_uncertain','retrying','throttled','needs_attention')),
 reason TEXT NOT NULL CHECK(length(reason) BETWEEN 1 AND 96),
 completed_at_us INTEGER NOT NULL DEFAULT((CAST(strftime('%s','now') AS INTEGER)*1000000 + CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000)),
 flickr_code INTEGER,
 observed_age_us INTEGER,
 CHECK(observed_age_us IS NULL OR observed_age_us>=0)
) STRICT;
INSERT INTO attempt_resolutions_v2(attempt_id,outcome,reason,completed_at_us)
 SELECT attempt_id,outcome,reason,completed_at_us FROM attempt_resolutions;
DROP TABLE attempt_resolutions;
ALTER TABLE attempt_resolutions_v2 RENAME TO attempt_resolutions;
CREATE TRIGGER attempt_resolutions_no_update BEFORE UPDATE ON attempt_resolutions
 BEGIN SELECT RAISE(ABORT,'attempt_evidence_immutable'); END;
CREATE TRIGGER attempt_resolutions_no_delete BEFORE DELETE ON attempt_resolutions
 BEGIN SELECT RAISE(ABORT,'attempt_evidence_immutable'); END;
CREATE TRIGGER attempt_resolutions_no_replace BEFORE INSERT ON attempt_resolutions
 WHEN EXISTS(SELECT 1 FROM attempt_resolutions WHERE attempt_id=NEW.attempt_id)
 BEGIN SELECT RAISE(ABORT,'attempt_evidence_immutable'); END;
CREATE TABLE flickr_rate_window (
 singleton INTEGER PRIMARY KEY CHECK(singleton=1),
 window_id TEXT NOT NULL UNIQUE,
 capacity INTEGER NOT NULL CHECK(capacity BETWEEN 3 AND 3600),
 window_ms INTEGER NOT NULL CHECK(window_ms BETWEEN 1000 AND 3600000),
 expires_at_us INTEGER NOT NULL,
 reserved_slots INTEGER NOT NULL DEFAULT 0 CHECK(reserved_slots>=0 AND reserved_slots<=capacity)
) STRICT;
CREATE TABLE flickr_rate_reservations (
 reservation_id TEXT PRIMARY KEY,
 attempt_id TEXT NOT NULL UNIQUE REFERENCES submission_attempts(attempt_id) ON DELETE RESTRICT,
 window_id TEXT NOT NULL,
 expires_at_us INTEGER NOT NULL,
 released INTEGER NOT NULL DEFAULT 0 CHECK(released IN (0,1)),
 consumed_slots INTEGER CHECK(consumed_slots BETWEEN 0 AND 3)
) STRICT;
CREATE TRIGGER rate_reservation_identity BEFORE UPDATE ON flickr_rate_reservations
 WHEN NEW.reservation_id<>OLD.reservation_id OR NEW.attempt_id<>OLD.attempt_id OR
 NEW.window_id<>OLD.window_id OR NEW.expires_at_us<>OLD.expires_at_us OR
 (OLD.released=1 AND (NEW.released<>1 OR NEW.consumed_slots IS NOT OLD.consumed_slots))
 BEGIN SELECT RAISE(ABORT,'rate_reservation_identity'); END;
CREATE TRIGGER rate_reservation_no_replace BEFORE INSERT ON flickr_rate_reservations
 WHEN EXISTS(SELECT 1 FROM flickr_rate_reservations WHERE reservation_id=NEW.reservation_id OR attempt_id=NEW.attempt_id)
 BEGIN SELECT RAISE(ABORT,'rate_reservation_identity'); END;
CREATE TABLE flickr_write_gate_events (
 event_id TEXT PRIMARY KEY,
 scope TEXT NOT NULL CHECK(scope IN ('deployment','user')),
 scope_id TEXT NOT NULL,
 revision INTEGER NOT NULL,
 reason TEXT NOT NULL,
 flickr_code INTEGER,
 attempt_id TEXT REFERENCES submission_attempts(attempt_id) ON DELETE RESTRICT,
 created_at_us INTEGER NOT NULL DEFAULT((CAST(strftime('%s','now') AS INTEGER)*1000000 + CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000))
) STRICT;
CREATE TRIGGER write_gate_event_no_update BEFORE UPDATE ON flickr_write_gate_events
 BEGIN SELECT RAISE(ABORT,'gate_event_immutable'); END;
CREATE TRIGGER write_gate_event_no_delete BEFORE DELETE ON flickr_write_gate_events
 BEGIN SELECT RAISE(ABORT,'gate_event_immutable'); END;
CREATE TRIGGER write_gate_event_no_replace BEFORE INSERT ON flickr_write_gate_events
 WHEN EXISTS(SELECT 1 FROM flickr_write_gate_events WHERE event_id=NEW.event_id)
 BEGIN SELECT RAISE(ABORT,'gate_event_immutable'); END;

-- Preserve a generic transition record for lifecycle/administrative changes too.
-- Dispatcher-specific evidence is inserted before UPDATE in the same transaction.
CREATE TRIGGER write_gate_transition AFTER UPDATE ON flickr_write_gates
 WHEN NEW.revision<>OLD.revision OR NEW.enabled<>OLD.enabled
 BEGIN
 INSERT INTO flickr_write_gate_events(event_id,scope,scope_id,revision,reason)
 SELECT lower(hex(randomblob(16))),NEW.scope,NEW.scope_id,NEW.revision,
   CASE WHEN NEW.enabled=1 THEN 'gate_enabled' ELSE 'gate_paused' END
 WHERE NOT EXISTS(SELECT 1 FROM flickr_write_gate_events
   WHERE scope=NEW.scope AND scope_id=NEW.scope_id AND revision=NEW.revision);
 END;

-- Metadata only; credential values remain one-time response data.
ALTER TABLE installations ADD COLUMN rotation_due_at_utc TEXT;
ALTER TABLE installations ADD COLUMN last_authenticated_at_utc TEXT;
UPDATE installations SET rotation_due_at_utc=strftime('%Y-%m-%dT%H:%M:%f',created_at_utc,'+1 year')||'000Z';
CREATE TABLE installation_lifecycle_events (
 event_id TEXT PRIMARY KEY,
 installation_id TEXT NOT NULL REFERENCES installations(installation_id) ON DELETE RESTRICT,
 version_id TEXT REFERENCES installation_credential_versions(version_id) ON DELETE RESTRICT,
 from_revision INTEGER NOT NULL,
 to_revision INTEGER NOT NULL,
 kind TEXT NOT NULL CHECK(kind IN ('created','rotation_created','rotation_completed','rotation_cancelled','rotation_expired','revoked')),
 created_at_utc TEXT NOT NULL DEFAULT(strftime('%Y-%m-%dT%H:%M:%f','now')||'000Z'),
 UNIQUE(installation_id,from_revision,kind)
) STRICT;
CREATE TRIGGER installation_lifecycle_no_update BEFORE UPDATE ON installation_lifecycle_events
 BEGIN SELECT RAISE(ABORT,'credential_history_immutable'); END;
CREATE TRIGGER installation_lifecycle_no_delete BEFORE DELETE ON installation_lifecycle_events
 BEGIN SELECT RAISE(ABORT,'credential_history_immutable'); END;
CREATE TRIGGER installation_lifecycle_no_replace BEFORE INSERT ON installation_lifecycle_events
 WHEN EXISTS(SELECT 1 FROM installation_lifecycle_events WHERE event_id=NEW.event_id)
 BEGIN SELECT RAISE(ABORT,'credential_history_immutable'); END;

-- Status reads have no authority to schedule, retry, or change group intents.
ALTER TABLE submission_intents ADD COLUMN state_changed_at_us INTEGER;
UPDATE submission_intents SET state_changed_at_us=COALESCE(
 (SELECT MAX(created_at_us) FROM submission_intent_events e WHERE e.intent_id=submission_intents.intent_id),created_at_us);
CREATE TRIGGER intent_initial_status_clock AFTER INSERT ON submission_intents
 BEGIN UPDATE submission_intents SET state_changed_at_us=NEW.created_at_us WHERE intent_id=NEW.intent_id; END;
CREATE TRIGGER intent_status_clock AFTER UPDATE OF state_version ON submission_intents
 WHEN NEW.state_version<>OLD.state_version
 BEGIN UPDATE submission_intents SET state_changed_at_us=(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000) WHERE intent_id=NEW.intent_id; END;
CREATE INDEX status_owner_page ON submission_intents(user_id,created_at_us DESC,intent_id DESC);
CREATE INDEX status_binding_page ON submission_intents(user_id,binding_id,created_at_us DESC,intent_id DESC);
CREATE TABLE status_read_buckets (
 family TEXT NOT NULL CHECK(family IN ('installation','admin')),
 subject_id TEXT NOT NULL,
 tokens REAL NOT NULL CHECK(tokens>=0 AND tokens<=20),
 updated_at_us INTEGER NOT NULL,
 PRIMARY KEY(family,subject_id)
) STRICT;
CREATE TABLE status_read_events (
 event_id TEXT PRIMARY KEY,
 created_at_us INTEGER NOT NULL
) STRICT;
CREATE INDEX status_read_window ON status_read_events(created_at_us);
-- Initial gate observations provide a timestamp without exposing token state.
INSERT INTO flickr_write_gate_events(event_id,scope,scope_id,revision,reason)
 SELECT lower(hex(randomblob(16))),g.scope,g.scope_id,g.revision,'migration_snapshot'
 FROM flickr_write_gates g WHERE NOT EXISTS(SELECT 1 FROM flickr_write_gate_events e
 WHERE e.scope=g.scope AND e.scope_id=g.scope_id AND e.revision=g.revision);
CREATE TRIGGER write_gate_initial_observation AFTER INSERT ON flickr_write_gates
 BEGIN INSERT INTO flickr_write_gate_events(event_id,scope,scope_id,revision,reason)
 VALUES(lower(hex(randomblob(16))),NEW.scope,NEW.scope_id,NEW.revision,
 CASE WHEN NEW.enabled=1 THEN 'initially_enabled' ELSE 'initially_paused' END); END;

-- Only validated release tooling writes receipts; HTTP/runtime paths only read them.
ALTER TABLE flickr_write_gate_events ADD COLUMN artifact_sha2_256 TEXT;
CREATE TABLE deployment_conformance (
 artifact_sha2_256 TEXT PRIMARY KEY CHECK(length(artifact_sha2_256)=64 AND artifact_sha2_256 NOT GLOB '*[^0-9a-f]*'),
 contract_sha2_256 TEXT NOT NULL CHECK(length(contract_sha2_256)=64),
 evidence_sha2_256 TEXT NOT NULL CHECK(length(evidence_sha2_256)=64),
 verified_at_us INTEGER NOT NULL DEFAULT(CAST(strftime('%s','now') AS INTEGER)*1000000)
) STRICT;
CREATE TRIGGER deployment_conformance_no_update BEFORE UPDATE ON deployment_conformance
 BEGIN SELECT RAISE(ABORT,'release_evidence_immutable'); END;
CREATE TRIGGER deployment_conformance_no_delete BEFORE DELETE ON deployment_conformance
 BEGIN SELECT RAISE(ABORT,'release_evidence_immutable'); END;
CREATE TRIGGER deployment_conformance_no_replace BEFORE INSERT ON deployment_conformance
 WHEN EXISTS(SELECT 1 FROM deployment_conformance WHERE artifact_sha2_256=NEW.artifact_sha2_256)
 BEGIN SELECT RAISE(ABORT,'release_evidence_immutable'); END;

-- Disposable group cache and refresh authority; no submission history is touched.
CREATE TABLE group_snapshots (
 user_id TEXT PRIMARY KEY REFERENCES fga_users(user_id),
 revision INTEGER NOT NULL DEFAULT 0 CHECK(revision BETWEEN 0 AND 9007199254740991),
 refreshed_at_us INTEGER,
 link_revision INTEGER,
 generation TEXT
) STRICT;
CREATE TABLE group_snapshot_rows (
 user_id TEXT NOT NULL REFERENCES group_snapshots(user_id),
 group_id TEXT COLLATE BINARY NOT NULL,
 display_name TEXT NOT NULL,
 PRIMARY KEY(user_id,group_id)
) STRICT;
CREATE TABLE group_refresh (
 user_id TEXT PRIMARY KEY REFERENCES fga_users(user_id),
 job_id TEXT NOT NULL UNIQUE,
 installation_id TEXT NOT NULL REFERENCES installations(installation_id),
 version_id TEXT NOT NULL REFERENCES installation_credential_versions(version_id),
 link_revision INTEGER NOT NULL,
 generation TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('queued','running','succeeded','failed')),
 admitted_at_us INTEGER NOT NULL,
 deadline_at_us INTEGER NOT NULL,
 failed_at_us INTEGER
) STRICT;
CREATE INDEX group_refresh_due ON group_refresh(state,admitted_at_us);
CREATE TABLE group_refresh_rows (
 user_id TEXT NOT NULL REFERENCES fga_users(user_id),
 job_id TEXT NOT NULL,
 group_id TEXT COLLATE BINARY NOT NULL,
 display_name TEXT NOT NULL,
 PRIMARY KEY(user_id,job_id,group_id)
) STRICT;

-- One replaceable advisory observation per binding; no retained generations or cursors.
CREATE TABLE photo_membership_observations (
 binding_id TEXT PRIMARY KEY REFERENCES photo_bindings(binding_id),
 revision INTEGER NOT NULL CHECK(revision BETWEEN 1 AND 9007199254740991),
 link_revision INTEGER NOT NULL,
 generation TEXT NOT NULL,
 valid INTEGER NOT NULL DEFAULT 1 CHECK(valid IN (0,1)),
 observed_at_us INTEGER NOT NULL
) STRICT;
CREATE TABLE photo_membership_rows (
 binding_id TEXT NOT NULL REFERENCES photo_membership_observations(binding_id),
 group_id TEXT COLLATE BINARY NOT NULL,
 display_name TEXT NOT NULL,
 PRIMARY KEY(binding_id,group_id)
) STRICT;

-- Durable correlation only. Never store an OAuth envelope, URL, or upload metadata.
CREATE TABLE upload_authorizations (
 authorization_id TEXT PRIMARY KEY NOT NULL,
 installation_id TEXT NOT NULL REFERENCES installations(installation_id) ON DELETE RESTRICT,
 user_id TEXT NOT NULL REFERENCES fga_users(user_id) ON DELETE RESTRICT,
 issued_at_us INTEGER NOT NULL,
 photo_id TEXT,
 CHECK(length(authorization_id) BETWEEN 1 AND 128),
 CHECK(photo_id IS NULL OR length(photo_id) BETWEEN 1 AND 128)
) STRICT;
CREATE TRIGGER upload_authorization_initial_owner BEFORE INSERT ON upload_authorizations
 WHEN NEW.photo_id IS NOT NULL OR NOT EXISTS(SELECT 1 FROM installations i
   WHERE i.installation_id=NEW.installation_id AND i.user_id=NEW.user_id)
 BEGIN SELECT RAISE(ABORT,'upload_authorization_initial_owner'); END;
CREATE TRIGGER upload_authorization_identity BEFORE UPDATE ON upload_authorizations
 WHEN NEW.authorization_id<>OLD.authorization_id OR NEW.installation_id<>OLD.installation_id
   OR NEW.user_id<>OLD.user_id OR NEW.issued_at_us<>OLD.issued_at_us
   OR (OLD.photo_id IS NOT NULL AND NEW.photo_id IS NOT OLD.photo_id)
 BEGIN SELECT RAISE(ABORT,'upload_authorization_identity'); END;
CREATE TRIGGER upload_authorization_retain BEFORE DELETE ON upload_authorizations
 BEGIN SELECT RAISE(ABORT,'upload_authorization_retained'); END;
CREATE TRIGGER upload_authorization_no_replace BEFORE INSERT ON upload_authorizations
 WHEN EXISTS(SELECT 1 FROM upload_authorizations WHERE authorization_id=NEW.authorization_id)
 BEGIN SELECT RAISE(ABORT,'upload_authorization_retained'); END;

-- Append-only successful upload proof, correlated to the existing common identity.
-- No Flickr metadata, signed envelope, credentials, album or group state is retained.
CREATE TABLE upload_photo_binding_events (
 authorization_id TEXT PRIMARY KEY NOT NULL REFERENCES upload_authorizations(authorization_id) ON DELETE RESTRICT,
 binding_id TEXT NOT NULL REFERENCES photo_bindings(binding_id) ON DELETE RESTRICT,
 link_revision INTEGER NOT NULL CHECK(link_revision BETWEEN 1 AND 9007199254740991),
 verification_revision INTEGER NOT NULL CHECK(verification_revision BETWEEN 1 AND 9007199254740991),
 observed_public INTEGER NOT NULL CHECK(observed_public IN (0,1)),
 verified_at_us INTEGER NOT NULL
) STRICT;
CREATE TRIGGER upload_photo_binding_event_consistent BEFORE INSERT ON upload_photo_binding_events
 WHEN NOT EXISTS(SELECT 1 FROM upload_authorizations a JOIN photo_bindings b
   ON b.photo_id=a.photo_id AND b.user_id=a.user_id
   WHERE a.authorization_id=NEW.authorization_id AND b.binding_id=NEW.binding_id
     AND b.link_revision=NEW.link_revision AND b.verification_revision=NEW.verification_revision
     AND b.verified_at_us=NEW.verified_at_us)
 BEGIN SELECT RAISE(ABORT,'upload_photo_binding_event_inconsistent'); END;
CREATE TRIGGER upload_photo_binding_event_no_update BEFORE UPDATE ON upload_photo_binding_events
 BEGIN SELECT RAISE(ABORT,'upload_photo_binding_event_immutable'); END;
CREATE TRIGGER upload_photo_binding_event_no_delete BEFORE DELETE ON upload_photo_binding_events
 BEGIN SELECT RAISE(ABORT,'upload_photo_binding_event_immutable'); END;
CREATE TRIGGER upload_photo_binding_event_no_replace BEFORE INSERT ON upload_photo_binding_events
 WHEN EXISTS(SELECT 1 FROM upload_photo_binding_events WHERE authorization_id=NEW.authorization_id)
 BEGIN SELECT RAISE(ABORT,'upload_photo_binding_event_immutable'); END;

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

-- Immutable, retained identities. No album, provider side effect or idempotency key.
CREATE TABLE publish_service_identities (
 service_id TEXT PRIMARY KEY NOT NULL CHECK(length(service_id)=36 AND service_id=lower(service_id)
  AND service_id GLOB '????????-????-4???-[89ab]???-????????????'
  AND length(replace(service_id,'-',''))=32 AND replace(service_id,'-','') NOT GLOB '*[^0-9a-f]*'),
 user_id TEXT NOT NULL REFERENCES fga_users(user_id) ON DELETE RESTRICT,
 issuing_installation_id TEXT NOT NULL REFERENCES installations(installation_id) ON DELETE RESTRICT,
 link_revision INTEGER NOT NULL CHECK(link_revision BETWEEN 1 AND 9007199254740991),
 owner_nsid TEXT NOT NULL CHECK(length(owner_nsid) BETWEEN 1 AND 128),
 service_revision INTEGER NOT NULL DEFAULT 1 CHECK(service_revision=1)
) STRICT;
CREATE TRIGGER publish_service_no_update BEFORE UPDATE ON publish_service_identities
 BEGIN SELECT RAISE(ABORT,'publish_service_immutable'); END;
CREATE TRIGGER publish_service_no_delete BEFORE DELETE ON publish_service_identities
 BEGIN SELECT RAISE(ABORT,'publish_service_retained'); END;
CREATE TRIGGER publish_service_no_replace BEFORE INSERT ON publish_service_identities
 WHEN EXISTS(SELECT 1 FROM publish_service_identities WHERE service_id=NEW.service_id)
 BEGIN SELECT RAISE(ABORT,'publish_service_retained'); END;

-- Retain only proven issuance context. Legacy authorizations deliberately remain NULL.
ALTER TABLE upload_authorizations ADD COLUMN owner_nsid TEXT CHECK(owner_nsid IS NULL OR length(owner_nsid) BETWEEN 1 AND 128);
ALTER TABLE upload_authorizations ADD COLUMN link_revision INTEGER CHECK(link_revision IS NULL OR link_revision BETWEEN 1 AND 9007199254740991);
CREATE TRIGGER upload_authorization_candidate_initial BEFORE INSERT ON upload_authorizations
 WHEN (NEW.owner_nsid IS NULL)<>(NEW.link_revision IS NULL)
   OR (NEW.owner_nsid IS NOT NULL AND NOT EXISTS(SELECT 1 FROM flickr_links l
     WHERE l.user_id=NEW.user_id AND l.state='linked' AND l.owner_nsid=NEW.owner_nsid AND l.link_revision=NEW.link_revision))
 BEGIN SELECT RAISE(ABORT,'upload_authorization_candidate_initial'); END;
CREATE TRIGGER upload_authorization_candidate_identity BEFORE UPDATE ON upload_authorizations
 WHEN NEW.owner_nsid IS NOT OLD.owner_nsid OR NEW.link_revision IS NOT OLD.link_revision
 BEGIN SELECT RAISE(ABORT,'upload_authorization_candidate_identity'); END;

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

DROP TABLE auth_source_buckets;
DROP TABLE status_read_buckets;
-- fga-prospective-integer-quota-v1: synthetic source fixture ONLY.
-- Not an installable migration or a conversion of historical REAL balances.
-- Exact E/R/X transition authority, complete no-REAL guards and actual schema
-- qualification are separate. Ordinary rowid tables preserve hidden identities.
CREATE TABLE auth_source_buckets (
 source_key TEXT PRIMARY KEY CHECK(length(source_key)=64),
 credit_us INTEGER NOT NULL CHECK(typeof(credit_us)='integer' AND credit_us BETWEEN 0 AND 240000000),
 updated_at_us INTEGER NOT NULL CHECK(typeof(updated_at_us)='integer' AND updated_at_us BETWEEN 0 AND 9223372036854775807)
) STRICT;
CREATE TABLE status_read_buckets (
 family TEXT NOT NULL CHECK(family IN ('installation','admin')),
 subject_id TEXT NOT NULL,
 credit_us INTEGER NOT NULL CHECK(typeof(credit_us)='integer' AND credit_us BETWEEN 0 AND 100000000),
 updated_at_us INTEGER NOT NULL CHECK(typeof(updated_at_us)='integer' AND updated_at_us BETWEEN 0 AND 9223372036854775807),
 PRIMARY KEY(family,subject_id)
) STRICT;
-- ANY prevents affinity from laundering a REAL clock into INTEGER before CHECK.
CREATE TABLE quota_credit_clocks (
 batch_id TEXT PRIMARY KEY,
 now_us ANY NOT NULL CONSTRAINT quota_credit_invariant
  CHECK(typeof(now_us)='integer' AND now_us BETWEEN 0 AND 9223372036854775807)
) STRICT;
CREATE TABLE quota_credit_guards (
 batch_id TEXT NOT NULL REFERENCES quota_credit_clocks(batch_id),
 kind TEXT NOT NULL CHECK(kind IN ('auth','status')),
 invariant_ok INTEGER NOT NULL CONSTRAINT quota_credit_invariant CHECK(invariant_ok=1),
 admitted INTEGER NOT NULL CONSTRAINT quota_credit_exhausted CHECK(admitted=1),
 PRIMARY KEY(batch_id,kind)
) STRICT;

-- INERT CANDIDATE ONLY. Not an active migration or install command.
-- Execute with guards.sql in ONE qualified atomic bootstrap boundary.
CREATE TABLE maintenance_control (
  singleton_id INTEGER NOT NULL PRIMARY KEY
    CHECK (typeof(singleton_id) = 'integer' AND singleton_id = 1),
  generation INTEGER NOT NULL
    CHECK (typeof(generation) = 'integer'
           AND generation BETWEEN 1 AND 9223372036854775807),
  state TEXT NOT NULL
    CHECK (typeof(state) = 'text' AND state IN ('open', 'closed'))
);
INSERT INTO maintenance_control(singleton_id, generation, state)
VALUES (1, 1, 'closed');
CREATE TRIGGER maintenance_control_no_insert
BEFORE INSERT ON maintenance_control
BEGIN SELECT RAISE(ABORT, 'maintenance_control_insert_denied'); END;
CREATE TRIGGER maintenance_control_no_delete
BEFORE DELETE ON maintenance_control
BEGIN SELECT RAISE(ABORT, 'maintenance_control_delete_denied'); END;
CREATE TRIGGER maintenance_control_transition
BEFORE UPDATE ON maintenance_control
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND typeof(OLD.singleton_id) = 'integer' AND OLD.singleton_id = 1
    AND NEW.singleton_id = OLD.singleton_id
    AND typeof(NEW.singleton_id) = 'integer'
    AND typeof(OLD.generation) = 'integer'
    AND OLD.generation BETWEEN 1 AND 9223372036854775806
    AND typeof(NEW.generation) = 'integer'
    AND NEW.generation = OLD.generation + 1
    AND typeof(OLD.state) = 'text' AND typeof(NEW.state) = 'text'
    AND ((OLD.state = 'open' AND NEW.state = 'closed')
      OR (OLD.state = 'closed' AND NEW.state = 'open'))
  THEN 1 ELSE RAISE(ABORT, 'maintenance_control_transition_denied') END;
END;
