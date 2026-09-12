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
