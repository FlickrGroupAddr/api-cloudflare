-- Complete schema, including indexes/internal definitions. No exclusion list.
SELECT type, name, tbl_name, sql FROM sqlite_schema ORDER BY type, name;
