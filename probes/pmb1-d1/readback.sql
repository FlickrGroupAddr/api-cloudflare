-- Entire relation, no WHERE/LIMIT: do not hide extra/malformed authority rows.
SELECT typeof(singleton_id) AS singleton_type,
       CAST(singleton_id AS TEXT) AS singleton_text,
       typeof(rowid) AS rowid_type, CAST(rowid AS TEXT) AS rowid_text,
       typeof(generation) AS generation_type,
       CAST(generation AS TEXT) AS generation_text,
       typeof(state) AS state_type, state
FROM maintenance_control;
