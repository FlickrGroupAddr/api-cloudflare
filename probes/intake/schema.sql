CREATE TABLE intake_probe_control(id INTEGER PRIMARY KEY,fault_stage INTEGER NOT NULL DEFAULT -1,lose_hint INTEGER NOT NULL DEFAULT 0,mode TEXT NOT NULL DEFAULT 'public',configured_limit TEXT NOT NULL DEFAULT '60',future_class INTEGER NOT NULL DEFAULT 0);
CREATE TABLE intake_probe_hints(sequence INTEGER PRIMARY KEY,partition_id TEXT NOT NULL,wake_revision TEXT NOT NULL);
CREATE TABLE intake_probe_calls(sequence INTEGER PRIMARY KEY,method TEXT NOT NULL,photo_id TEXT);
