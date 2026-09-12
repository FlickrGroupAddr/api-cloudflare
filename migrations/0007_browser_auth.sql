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
