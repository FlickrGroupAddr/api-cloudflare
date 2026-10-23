-- Trusted provisioning only, after schema.sql on a NEW SEPARATE external D1.
-- Bind actual database UUID, candidate digest, lifecycle, exact generation TEXT.
-- Never INSERT OR REPLACE; an existing lifecycle is not resettable.
INSERT INTO pmb1_journal_control(id,schema_version,database_id,candidate,lifecycle,generation,state,stop_evidence,revision)
VALUES(1,'pmb1-main-journal-v1',?1,?2,?3,?4,'open',NULL,0);
