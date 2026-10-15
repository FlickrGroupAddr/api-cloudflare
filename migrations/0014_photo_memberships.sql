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
