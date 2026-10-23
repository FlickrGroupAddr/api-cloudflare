-- NEW object fixture extracted by actual bootstrapPartitionMaintenance.
CREATE TABLE maintenance_control (
      singleton_id INTEGER NOT NULL PRIMARY KEY CHECK(typeof(singleton_id)='integer' AND singleton_id=1),
      generation INTEGER NOT NULL CHECK(typeof(generation)='integer' AND generation BETWEEN 1 AND 9223372036854775807),
      state TEXT NOT NULL CHECK(typeof(state)='text' AND state IN ('open','closed')));
CREATE TABLE pmb1_partition_binding (id INTEGER PRIMARY KEY CHECK(id=1), partition_id TEXT NOT NULL);
CREATE TABLE pmb1_partition_invocations (
      id TEXT PRIMARY KEY NOT NULL, generation TEXT NOT NULL, entry TEXT NOT NULL,
      partition_id TEXT, claim_id TEXT, lease TEXT, grant_binding TEXT, attempt_id TEXT, attempt_binding TEXT, due_token TEXT, dispatch INTEGER NOT NULL DEFAULT 0,
      state TEXT NOT NULL CHECK(state IN ('active','settled')), receipt TEXT);
CREATE TABLE pmb1_wake_executions (id TEXT NOT NULL PRIMARY KEY, generation TEXT NOT NULL,
        revision TEXT NOT NULL, value TEXT NOT NULL,
        state TEXT NOT NULL CHECK(state IN ('admitted','external_pending','settled','cancelled')));
CREATE TABLE pmb1_wake_results (id TEXT NOT NULL PRIMARY KEY, result TEXT NOT NULL);
CREATE TABLE pmb1_wake_work (id INTEGER NOT NULL PRIMARY KEY CHECK(id=1), revision TEXT NOT NULL,
        value TEXT NOT NULL, due INTEGER CHECK(due IS NULL OR (typeof(due)='integer' AND due>0)));
CREATE TRIGGER pmb1_control_no_delete BEFORE DELETE ON maintenance_control BEGIN SELECT RAISE(ABORT,'control_delete_denied'); END;

CREATE TRIGGER pmb1_control_transition BEFORE UPDATE ON maintenance_control BEGIN
        SELECT CASE WHEN (SELECT COUNT(*) FROM maintenance_control)=1
        AND typeof(OLD.singleton_id)='integer' AND OLD.singleton_id=1 AND NEW.singleton_id=OLD.singleton_id
        AND typeof(NEW.singleton_id)='integer' AND typeof(OLD.generation)='integer'
        AND OLD.generation BETWEEN 1 AND 9223372036854775806 AND typeof(NEW.generation)='integer'
        AND NEW.generation=OLD.generation+1 AND typeof(OLD.state)='text' AND typeof(NEW.state)='text'
        AND ((OLD.state='open' AND NEW.state='closed') OR (OLD.state='closed' AND NEW.state='open'))
        THEN 1 ELSE RAISE(ABORT,'control_transition_denied') END; END;
CREATE TRIGGER pmb1_partition_binding_delete BEFORE DELETE ON pmb1_partition_binding
        BEGIN SELECT CASE WHEN (SELECT COUNT(*) FROM maintenance_control)=1 AND EXISTS(
          SELECT 1 FROM maintenance_control WHERE singleton_id=1 AND typeof(singleton_id)='integer'
          AND typeof(generation)='integer' AND generation BETWEEN 1 AND 9223372036854775807 AND typeof(state)='text' AND state='open')
          THEN 1 ELSE RAISE(ABORT,'maintenance_closed') END; END;
CREATE TRIGGER pmb1_partition_binding_insert BEFORE INSERT ON pmb1_partition_binding
        BEGIN SELECT CASE WHEN (SELECT COUNT(*) FROM maintenance_control)=1 AND EXISTS(
          SELECT 1 FROM maintenance_control WHERE singleton_id=1 AND typeof(singleton_id)='integer'
          AND typeof(generation)='integer' AND generation BETWEEN 1 AND 9223372036854775807 AND typeof(state)='text' AND state='open')
          THEN 1 ELSE RAISE(ABORT,'maintenance_closed') END; END;
CREATE TRIGGER pmb1_partition_binding_update BEFORE UPDATE ON pmb1_partition_binding
        BEGIN SELECT CASE WHEN (SELECT COUNT(*) FROM maintenance_control)=1 AND EXISTS(
          SELECT 1 FROM maintenance_control WHERE singleton_id=1 AND typeof(singleton_id)='integer'
          AND typeof(generation)='integer' AND generation BETWEEN 1 AND 9223372036854775807 AND typeof(state)='text' AND state='open')
          THEN 1 ELSE RAISE(ABORT,'maintenance_closed') END; END;
CREATE TRIGGER pmb1_partition_invocations_delete BEFORE DELETE ON pmb1_partition_invocations
        BEGIN SELECT CASE WHEN (SELECT COUNT(*) FROM maintenance_control)=1 AND EXISTS(
          SELECT 1 FROM maintenance_control WHERE singleton_id=1 AND typeof(singleton_id)='integer'
          AND typeof(generation)='integer' AND generation BETWEEN 1 AND 9223372036854775807 AND typeof(state)='text' AND state='open')
          THEN 1 ELSE RAISE(ABORT,'maintenance_closed') END; END;
CREATE TRIGGER pmb1_partition_invocations_insert BEFORE INSERT ON pmb1_partition_invocations
        BEGIN SELECT CASE WHEN (SELECT COUNT(*) FROM maintenance_control)=1 AND EXISTS(
          SELECT 1 FROM maintenance_control WHERE singleton_id=1 AND typeof(singleton_id)='integer'
          AND typeof(generation)='integer' AND generation BETWEEN 1 AND 9223372036854775807 AND typeof(state)='text' AND state='open')
          THEN 1 ELSE RAISE(ABORT,'maintenance_closed') END; END;
CREATE TRIGGER pmb1_partition_invocations_update BEFORE UPDATE ON pmb1_partition_invocations
        BEGIN SELECT CASE WHEN (SELECT COUNT(*) FROM maintenance_control)=1 AND EXISTS(
          SELECT 1 FROM maintenance_control WHERE singleton_id=1 AND typeof(singleton_id)='integer'
          AND typeof(generation)='integer' AND generation BETWEEN 1 AND 9223372036854775807 AND typeof(state)='text' AND state='open')
          THEN 1 ELSE RAISE(ABORT,'maintenance_closed') END; END;
CREATE TRIGGER pmb1_wake_executions_delete BEFORE DELETE ON pmb1_wake_executions
          BEGIN SELECT CASE WHEN (SELECT COUNT(*) FROM maintenance_control)=1 AND EXISTS
 (SELECT 1 FROM maintenance_control WHERE typeof(singleton_id)='integer' AND singleton_id=1
 AND typeof(generation)='integer' AND generation BETWEEN 1 AND 9223372036854775807
 AND typeof(state)='text' AND state='open') THEN 1 ELSE RAISE(ABORT,'maintenance_closed') END; END;
CREATE TRIGGER pmb1_wake_executions_insert BEFORE INSERT ON pmb1_wake_executions
          BEGIN SELECT CASE WHEN (SELECT COUNT(*) FROM maintenance_control)=1 AND EXISTS
 (SELECT 1 FROM maintenance_control WHERE typeof(singleton_id)='integer' AND singleton_id=1
 AND typeof(generation)='integer' AND generation BETWEEN 1 AND 9223372036854775807
 AND typeof(state)='text' AND state='open') THEN 1 ELSE RAISE(ABORT,'maintenance_closed') END; END;
CREATE TRIGGER pmb1_wake_executions_update BEFORE UPDATE ON pmb1_wake_executions
          BEGIN SELECT CASE WHEN (SELECT COUNT(*) FROM maintenance_control)=1 AND EXISTS
 (SELECT 1 FROM maintenance_control WHERE typeof(singleton_id)='integer' AND singleton_id=1
 AND typeof(generation)='integer' AND generation BETWEEN 1 AND 9223372036854775807
 AND typeof(state)='text' AND state='open') THEN 1 ELSE RAISE(ABORT,'maintenance_closed') END; END;
CREATE TRIGGER pmb1_wake_results_delete BEFORE DELETE ON pmb1_wake_results
          BEGIN SELECT CASE WHEN (SELECT COUNT(*) FROM maintenance_control)=1 AND EXISTS
 (SELECT 1 FROM maintenance_control WHERE typeof(singleton_id)='integer' AND singleton_id=1
 AND typeof(generation)='integer' AND generation BETWEEN 1 AND 9223372036854775807
 AND typeof(state)='text' AND state='open') THEN 1 ELSE RAISE(ABORT,'maintenance_closed') END; END;
CREATE TRIGGER pmb1_wake_results_insert BEFORE INSERT ON pmb1_wake_results
          BEGIN SELECT CASE WHEN (SELECT COUNT(*) FROM maintenance_control)=1 AND EXISTS
 (SELECT 1 FROM maintenance_control WHERE typeof(singleton_id)='integer' AND singleton_id=1
 AND typeof(generation)='integer' AND generation BETWEEN 1 AND 9223372036854775807
 AND typeof(state)='text' AND state='open') THEN 1 ELSE RAISE(ABORT,'maintenance_closed') END; END;
CREATE TRIGGER pmb1_wake_results_update BEFORE UPDATE ON pmb1_wake_results
          BEGIN SELECT CASE WHEN (SELECT COUNT(*) FROM maintenance_control)=1 AND EXISTS
 (SELECT 1 FROM maintenance_control WHERE typeof(singleton_id)='integer' AND singleton_id=1
 AND typeof(generation)='integer' AND generation BETWEEN 1 AND 9223372036854775807
 AND typeof(state)='text' AND state='open') THEN 1 ELSE RAISE(ABORT,'maintenance_closed') END; END;
CREATE TRIGGER pmb1_wake_work_delete BEFORE DELETE ON pmb1_wake_work
          BEGIN SELECT CASE WHEN (SELECT COUNT(*) FROM maintenance_control)=1 AND EXISTS
 (SELECT 1 FROM maintenance_control WHERE typeof(singleton_id)='integer' AND singleton_id=1
 AND typeof(generation)='integer' AND generation BETWEEN 1 AND 9223372036854775807
 AND typeof(state)='text' AND state='open') THEN 1 ELSE RAISE(ABORT,'maintenance_closed') END; END;
CREATE TRIGGER pmb1_wake_work_insert BEFORE INSERT ON pmb1_wake_work
          BEGIN SELECT CASE WHEN (SELECT COUNT(*) FROM maintenance_control)=1 AND EXISTS
 (SELECT 1 FROM maintenance_control WHERE typeof(singleton_id)='integer' AND singleton_id=1
 AND typeof(generation)='integer' AND generation BETWEEN 1 AND 9223372036854775807
 AND typeof(state)='text' AND state='open') THEN 1 ELSE RAISE(ABORT,'maintenance_closed') END; END;
CREATE TRIGGER pmb1_wake_work_update BEFORE UPDATE ON pmb1_wake_work
          BEGIN SELECT CASE WHEN (SELECT COUNT(*) FROM maintenance_control)=1 AND EXISTS
 (SELECT 1 FROM maintenance_control WHERE typeof(singleton_id)='integer' AND singleton_id=1
 AND typeof(generation)='integer' AND generation BETWEEN 1 AND 9223372036854775807
 AND typeof(state)='text' AND state='open') THEN 1 ELSE RAISE(ABORT,'maintenance_closed') END; END;
INSERT INTO maintenance_control VALUES(1,1,'closed');
CREATE TRIGGER pmb1_control_no_insert BEFORE INSERT ON maintenance_control BEGIN SELECT RAISE(ABORT,'control_insert_denied'); END;
