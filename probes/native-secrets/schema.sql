CREATE TABLE link (
 id INTEGER PRIMARY KEY CHECK(id=1), run_id TEXT NOT NULL,
 revision INTEGER NOT NULL DEFAULT 0,
 state TEXT NOT NULL CHECK(state IN ('linked','paused','disconnecting','disconnected')),
 generation TEXT, pending_generation TEXT, retiring_generation TEXT, operation TEXT,
 writes_paused INTEGER NOT NULL DEFAULT 1 CHECK(writes_paused=1),
 CHECK((state='linked' AND generation IS NOT NULL AND operation IS NULL AND pending_generation IS NULL AND retiring_generation IS NULL)
    OR (state='paused' AND operation IS NOT NULL AND pending_generation IS NOT NULL AND retiring_generation IS NULL)
    OR (state='disconnecting' AND generation IS NULL AND operation IS NOT NULL AND pending_generation IS NULL AND retiring_generation IS NOT NULL)
    OR (state='disconnected' AND generation IS NULL AND operation IS NULL AND pending_generation IS NULL AND retiring_generation IS NULL))
);
CREATE TABLE events (revision INTEGER PRIMARY KEY, state TEXT NOT NULL, valid INTEGER NOT NULL CHECK(valid=1));
CREATE TRIGGER revision_guard BEFORE UPDATE ON link
 WHEN NEW.revision != OLD.revision+1 BEGIN SELECT RAISE(ABORT,'revision_guard'); END;
CREATE TRIGGER transition_event AFTER UPDATE ON link
 BEGIN INSERT INTO events VALUES(NEW.revision, NEW.state, 1); END;
CREATE TRIGGER event_no_update BEFORE UPDATE ON events
 BEGIN SELECT RAISE(ABORT,'event_guard'); END;
CREATE TRIGGER event_no_delete BEFORE DELETE ON events
 BEGIN SELECT RAISE(ABORT,'event_guard'); END;
CREATE TABLE attempts (
 operation TEXT NOT NULL, expected INTEGER NOT NULL, kind TEXT NOT NULL,
 PRIMARY KEY(operation,expected)
);
