CREATE TABLE probe_control(id INTEGER PRIMARY KEY CHECK(id=1),initialized INTEGER NOT NULL,cron_enabled INTEGER NOT NULL DEFAULT 0,fail_group TEXT) STRICT;
CREATE TABLE probe_events(id TEXT PRIMARY KEY,kind TEXT NOT NULL,partition_id TEXT,instance_id TEXT,detail TEXT,created_us INTEGER NOT NULL DEFAULT(CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000)) STRICT;
CREATE TRIGGER probe_intent_failure BEFORE INSERT ON submission_intents WHEN NEW.group_id=(SELECT fail_group FROM probe_control WHERE id=1) BEGIN SELECT RAISE(ABORT,'injected_intent_failure'); END;

CREATE TABLE probe_fail_config(partition_id TEXT PRIMARY KEY,peer_origin TEXT NOT NULL,fault TEXT NOT NULL,response_code INTEGER NOT NULL,present INTEGER NOT NULL,before_age INTEGER NOT NULL,after_age INTEGER NOT NULL,rollback_result INTEGER NOT NULL);
CREATE TABLE probe_peer_operations(sequence INTEGER PRIMARY KEY AUTOINCREMENT,attempt_id TEXT NOT NULL,photo_id TEXT NOT NULL,group_id TEXT NOT NULL,method TEXT NOT NULL,marker_visible INTEGER NOT NULL);
CREATE TABLE probe_reservations(attempt_id TEXT PRIMARY KEY,slots INTEGER NOT NULL CHECK(slots=3));
