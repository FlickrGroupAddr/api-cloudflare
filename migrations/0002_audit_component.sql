-- Upgrade an existing foundation without rewriting protected history.
ALTER TABLE audit_events ADD COLUMN source_component TEXT NOT NULL DEFAULT 'fga_api_backend';
CREATE INDEX audit_event_page ON audit_events(created_at_utc DESC,event_id DESC);
CREATE INDEX pending_credential_expiry ON installation_credential_versions(state,expires_at_us);
