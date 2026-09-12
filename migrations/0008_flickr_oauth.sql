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
