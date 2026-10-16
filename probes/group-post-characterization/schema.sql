CREATE TABLE post_budget (
 run_id TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('source','receiver')),
 expires_at INTEGER NOT NULL, requests INTEGER NOT NULL DEFAULT 0 CHECK(requests BETWEEN 0 AND 64),
 PRIMARY KEY(run_id,role)
);
CREATE TABLE post_observations (
 run_id TEXT NOT NULL, role TEXT NOT NULL, case_id TEXT NOT NULL,
 method TEXT NOT NULL CHECK(method IN ('GET','POST')), body_bytes INTEGER NOT NULL CHECK(body_bytes BETWEEN 0 AND 16384),
 body_matches INTEGER NOT NULL, authorization_present INTEGER NOT NULL,
 canary_matches INTEGER NOT NULL, content_type_matches INTEGER NOT NULL,
 PRIMARY KEY(run_id,role,case_id)
);
