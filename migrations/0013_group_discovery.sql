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
