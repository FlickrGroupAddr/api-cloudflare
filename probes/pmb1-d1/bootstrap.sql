-- INERT CANDIDATE ONLY. Not an active migration or install command.
-- Execute with guards.sql in ONE qualified atomic bootstrap boundary.
CREATE TABLE maintenance_control (
  singleton_id INTEGER NOT NULL PRIMARY KEY
    CHECK (typeof(singleton_id) = 'integer' AND singleton_id = 1),
  generation INTEGER NOT NULL
    CHECK (typeof(generation) = 'integer'
           AND generation BETWEEN 1 AND 9223372036854775807),
  state TEXT NOT NULL
    CHECK (typeof(state) = 'text' AND state IN ('open', 'closed'))
);
INSERT INTO maintenance_control(singleton_id, generation, state)
VALUES (1, 1, 'closed');
CREATE TRIGGER maintenance_control_no_insert
BEFORE INSERT ON maintenance_control
BEGIN SELECT RAISE(ABORT, 'maintenance_control_insert_denied'); END;
CREATE TRIGGER maintenance_control_no_delete
BEFORE DELETE ON maintenance_control
BEGIN SELECT RAISE(ABORT, 'maintenance_control_delete_denied'); END;
CREATE TRIGGER maintenance_control_transition
BEFORE UPDATE ON maintenance_control
BEGIN
  SELECT CASE WHEN
    (SELECT COUNT(*) FROM maintenance_control) = 1
    AND typeof(OLD.singleton_id) = 'integer' AND OLD.singleton_id = 1
    AND NEW.singleton_id = OLD.singleton_id
    AND typeof(NEW.singleton_id) = 'integer'
    AND typeof(OLD.generation) = 'integer'
    AND OLD.generation BETWEEN 1 AND 9223372036854775806
    AND typeof(NEW.generation) = 'integer'
    AND NEW.generation = OLD.generation + 1
    AND typeof(OLD.state) = 'text' AND typeof(NEW.state) = 'text'
    AND ((OLD.state = 'open' AND NEW.state = 'closed')
      OR (OLD.state = 'closed' AND NEW.state = 'open'))
  THEN 1 ELSE RAISE(ABORT, 'maintenance_control_transition_denied') END;
END;
