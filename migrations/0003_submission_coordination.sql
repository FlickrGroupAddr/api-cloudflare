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
