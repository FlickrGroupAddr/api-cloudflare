-- MIT License; copyright 2026 Terry Ott.
-- NEW SEPARATE external D1 only. No automatic seed, replacement or reset.
CREATE TABLE pmb1_journal_control (
 id INTEGER PRIMARY KEY CHECK(id=1),
 schema_version TEXT NOT NULL CHECK(schema_version='pmb1-main-journal-v1'),
 database_id TEXT NOT NULL CHECK(length(database_id)=36 AND substr(database_id,9,1)='-' AND substr(database_id,14,1)='-' AND substr(database_id,19,1)='-' AND substr(database_id,24,1)='-' AND length(replace(database_id,'-',''))=32 AND replace(database_id,'-','') NOT GLOB '*[^0-9a-f]*'),
 candidate TEXT NOT NULL CHECK(length(candidate)=64 AND candidate NOT GLOB '*[^0-9a-f]*'),
 lifecycle TEXT NOT NULL CHECK(length(lifecycle) BETWEEN 1 AND 80 AND lifecycle NOT GLOB '*[^A-Za-z0-9_-]*'),
 generation TEXT NOT NULL CHECK(length(generation) BETWEEN 1 AND 19 AND generation NOT GLOB '*[^0-9]*' AND substr(generation,1,1) BETWEEN '1' AND '9' AND (length(generation)<19 OR generation<='9223372036854775807')),
 state TEXT NOT NULL CHECK(state IN ('open','stopped')),
 stop_evidence TEXT CHECK((state='open' AND stop_evidence IS NULL) OR (state='stopped' AND stop_evidence IS NOT NULL AND length(stop_evidence)=64 AND stop_evidence NOT GLOB '*[^0-9a-f]*')),
 revision INTEGER NOT NULL CHECK(revision>=0)
) STRICT, WITHOUT ROWID;
CREATE TABLE pmb1_journal_invocations (
 invocation TEXT PRIMARY KEY CHECK(length(invocation)=36 AND substr(invocation,9,1)='-' AND substr(invocation,14,1)='-' AND substr(invocation,19,1)='-' AND substr(invocation,24,1)='-' AND length(replace(invocation,'-',''))=32 AND replace(invocation,'-','') NOT GLOB '*[^0-9a-f]*'),
 candidate TEXT NOT NULL, lifecycle TEXT NOT NULL, generation TEXT NOT NULL,
 entry TEXT NOT NULL CHECK(entry IN ('fetch','scheduled')),
 returned TEXT CHECK(returned IN ('fulfilled','rejected'))
) STRICT, WITHOUT ROWID;
CREATE TABLE pmb1_journal_effects (
 effect TEXT PRIMARY KEY CHECK(length(effect)=36 AND substr(effect,9,1)='-' AND substr(effect,14,1)='-' AND substr(effect,19,1)='-' AND substr(effect,24,1)='-' AND length(replace(effect,'-',''))=32 AND replace(effect,'-','') NOT GLOB '*[^0-9a-f]*'),
 invocation TEXT NOT NULL REFERENCES pmb1_journal_invocations(invocation),
 kind TEXT NOT NULL CHECK(kind IN ('d1','provider','provider-body','provider-cancel','secret-read','wake','asset','repair-reader')),
 settled TEXT CHECK(settled IN ('fulfilled','rejected'))
) STRICT, WITHOUT ROWID;
CREATE INDEX pmb1_journal_effect_invocation ON pmb1_journal_effects(invocation,settled);
CREATE TRIGGER pmb1_control_insert BEFORE INSERT ON pmb1_journal_control WHEN EXISTS(SELECT 1 FROM pmb1_journal_control) OR NEW.state<>'open' OR NEW.stop_evidence IS NOT NULL OR NEW.revision<>0 BEGIN SELECT RAISE(ABORT,'pmb1_journal_guard'); END;
CREATE TRIGGER pmb1_control_delete BEFORE DELETE ON pmb1_journal_control BEGIN SELECT RAISE(ABORT,'pmb1_journal_guard'); END;
CREATE TRIGGER pmb1_control_update BEFORE UPDATE ON pmb1_journal_control WHEN NEW.id<>OLD.id OR NEW.schema_version<>OLD.schema_version OR NEW.database_id<>OLD.database_id OR NEW.candidate<>OLD.candidate OR NEW.lifecycle<>OLD.lifecycle OR NEW.generation<>OLD.generation OR NEW.revision<>OLD.revision+1 OR (OLD.state='stopped' AND (NEW.state<>'stopped' OR NEW.stop_evidence IS NOT OLD.stop_evidence)) OR (OLD.state=NEW.state AND NEW.stop_evidence IS NOT OLD.stop_evidence) BEGIN SELECT RAISE(ABORT,'pmb1_journal_guard'); END;
CREATE TRIGGER pmb1_invocation_insert BEFORE INSERT ON pmb1_journal_invocations WHEN EXISTS(SELECT 1 FROM pmb1_journal_invocations WHERE invocation=NEW.invocation) OR NEW.returned IS NOT NULL OR NOT EXISTS(SELECT 1 FROM pmb1_journal_control c WHERE c.id=1 AND c.state='open' AND c.candidate=NEW.candidate AND c.lifecycle=NEW.lifecycle AND c.generation=NEW.generation) BEGIN SELECT RAISE(ABORT,'pmb1_journal_guard'); END;
CREATE TRIGGER pmb1_invocation_update BEFORE UPDATE ON pmb1_journal_invocations WHEN NEW.invocation<>OLD.invocation OR NEW.candidate<>OLD.candidate OR NEW.lifecycle<>OLD.lifecycle OR NEW.generation<>OLD.generation OR NEW.entry<>OLD.entry OR OLD.returned IS NOT NULL OR NEW.returned IS NULL OR EXISTS(SELECT 1 FROM pmb1_journal_effects e WHERE e.invocation=OLD.invocation AND e.settled IS NULL) BEGIN SELECT RAISE(ABORT,'pmb1_journal_guard'); END;
CREATE TRIGGER pmb1_invocation_delete BEFORE DELETE ON pmb1_journal_invocations BEGIN SELECT RAISE(ABORT,'pmb1_journal_guard'); END;
CREATE TRIGGER pmb1_effect_insert BEFORE INSERT ON pmb1_journal_effects WHEN EXISTS(SELECT 1 FROM pmb1_journal_effects WHERE effect=NEW.effect) OR NEW.settled IS NOT NULL OR NOT EXISTS(SELECT 1 FROM pmb1_journal_invocations i JOIN pmb1_journal_control c ON c.candidate=i.candidate AND c.lifecycle=i.lifecycle AND c.generation=i.generation WHERE i.invocation=NEW.invocation AND i.returned IS NULL AND c.id=1) BEGIN SELECT RAISE(ABORT,'pmb1_journal_guard'); END;
CREATE TRIGGER pmb1_effect_update BEFORE UPDATE ON pmb1_journal_effects WHEN NEW.effect<>OLD.effect OR NEW.invocation<>OLD.invocation OR NEW.kind<>OLD.kind OR OLD.settled IS NOT NULL OR NEW.settled IS NULL OR NOT EXISTS(SELECT 1 FROM pmb1_journal_invocations i WHERE i.invocation=OLD.invocation AND i.returned IS NULL) BEGIN SELECT RAISE(ABORT,'pmb1_journal_guard'); END;
CREATE TRIGGER pmb1_effect_delete BEFORE DELETE ON pmb1_journal_effects BEGIN SELECT RAISE(ABORT,'pmb1_journal_guard'); END;
CREATE TRIGGER pmb1_invocation_revision_insert AFTER INSERT ON pmb1_journal_invocations BEGIN UPDATE pmb1_journal_control SET revision=revision+1 WHERE id=1; END;
CREATE TRIGGER pmb1_invocation_revision_update AFTER UPDATE ON pmb1_journal_invocations BEGIN UPDATE pmb1_journal_control SET revision=revision+1 WHERE id=1; END;
CREATE TRIGGER pmb1_effect_revision_insert AFTER INSERT ON pmb1_journal_effects BEGIN UPDATE pmb1_journal_control SET revision=revision+1 WHERE id=1; END;
CREATE TRIGGER pmb1_effect_revision_update AFTER UPDATE ON pmb1_journal_effects BEGIN UPDATE pmb1_journal_control SET revision=revision+1 WHERE id=1; END;
