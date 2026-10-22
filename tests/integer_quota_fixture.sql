-- fga-prospective-integer-quota-v1: synthetic source fixture ONLY.
-- Not an installable migration or a conversion of historical REAL balances.
-- Exact E/R/X transition authority, complete no-REAL guards and actual schema
-- qualification are separate. Ordinary rowid tables preserve hidden identities.
CREATE TABLE auth_source_buckets (
 source_key TEXT PRIMARY KEY CHECK(length(source_key)=64),
 credit_us INTEGER NOT NULL CHECK(typeof(credit_us)='integer' AND credit_us BETWEEN 0 AND 240000000),
 updated_at_us INTEGER NOT NULL CHECK(typeof(updated_at_us)='integer' AND updated_at_us BETWEEN 0 AND 9223372036854775807)
) STRICT;
CREATE TABLE status_read_buckets (
 family TEXT NOT NULL CHECK(family IN ('installation','admin')),
 subject_id TEXT NOT NULL,
 credit_us INTEGER NOT NULL CHECK(typeof(credit_us)='integer' AND credit_us BETWEEN 0 AND 100000000),
 updated_at_us INTEGER NOT NULL CHECK(typeof(updated_at_us)='integer' AND updated_at_us BETWEEN 0 AND 9223372036854775807),
 PRIMARY KEY(family,subject_id)
) STRICT;
-- ANY prevents affinity from laundering a REAL clock into INTEGER before CHECK.
CREATE TABLE quota_credit_clocks (
 batch_id TEXT PRIMARY KEY,
 now_us ANY NOT NULL CONSTRAINT quota_credit_invariant
  CHECK(typeof(now_us)='integer' AND now_us BETWEEN 0 AND 9223372036854775807)
) STRICT;
CREATE TABLE quota_credit_guards (
 batch_id TEXT NOT NULL REFERENCES quota_credit_clocks(batch_id),
 kind TEXT NOT NULL CHECK(kind IN ('auth','status')),
 invariant_ok INTEGER NOT NULL CONSTRAINT quota_credit_invariant CHECK(invariant_ok=1),
 admitted INTEGER NOT NULL CONSTRAINT quota_credit_exhausted CHECK(admitted=1),
 PRIMARY KEY(batch_id,kind)
) STRICT;
