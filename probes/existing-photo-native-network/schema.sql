CREATE TABLE network_probe_budget (
  run_id TEXT NOT NULL CHECK(length(run_id)=24 AND run_id NOT GLOB '*[^0-9a-f]*'),
  role TEXT NOT NULL CHECK(role IN ('source','receiver')),
  expires_at_unix INTEGER NOT NULL CHECK(expires_at_unix>0),
  requests INTEGER NOT NULL DEFAULT 0 CHECK(requests BETWEEN 0 AND 32),
  receiver_requests INTEGER NOT NULL DEFAULT 0 CHECK(receiver_requests BETWEEN 0 AND 32),
  authorization_seen INTEGER NOT NULL DEFAULT 0 CHECK(authorization_seen IN (0,1)),
  canary_seen INTEGER NOT NULL DEFAULT 0 CHECK(canary_seen IN (0,1)),
  PRIMARY KEY(run_id,role)
) STRICT;
