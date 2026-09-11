CREATE TABLE clock_trials (
 id TEXT PRIMARY KEY, target TEXT NOT NULL, receipt_wall_ms REAL NOT NULL,
 receipt_perf_ms REAL NOT NULL, marker_us INTEGER,
 peer_post_wall_ms REAL, peer_post_count INTEGER NOT NULL DEFAULT 0
) STRICT;
