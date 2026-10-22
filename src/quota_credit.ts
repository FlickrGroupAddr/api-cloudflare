import type { SqlStore } from './admission.ts';

// Prospective SOURCE ONLY under architecture ADR0065. No current writer imports
// this module. Callers must place these statements and ALL other budget checks,
// charges/events/cleanup in ONE D1 batch; never execute a fragment separately.
// This fixture is neither an actual migration nor a complete no-REAL profile.
export const INTEGER_QUOTA_SCHEMA_VERSION = 'fga-prospective-integer-quota-v1';
// Exact UTF-8/LF fixture bytes (also the canonical Git blob).
export const INTEGER_QUOTA_FIXTURE_SHA2_256 = 'ddcd31e0d3277559131e8b063f2dd5abbed8a304e33a8fcfdce352cac92b6c32';
export const AUTH_CREDIT_CAPACITY_US = 240_000_000;
export const AUTH_CREDIT_CHARGE_US = 120_000_000;
export const STATUS_CREDIT_CAPACITY_US = 100_000_000;
export const STATUS_CREDIT_CHARGE_US = 5_000_000;

// SQLite's database UTC clock has millisecond source resolution. Sample its
// components once; validate actual types and canonical text BEFORE the only CAST.
// Reject NUL explicitly: SQLite length/GLOB stop at NUL and can hide a suffix.
// 0..253402300799 seconds (through year 9999) and 0..999 milliseconds imply
// 0..253402300799999000 us, safely below signed64 MAX even before insertion.
// NULL/unsupported clocks refuse; no Worker wall clock or lossy outer CAST.
export const QUOTA_CLOCK_SQL = `WITH sampled AS MATERIALIZED (
 SELECT unixepoch('now') AS seconds, strftime('%f','now') AS fraction
) INSERT INTO quota_credit_clocks(batch_id,now_us)
 SELECT ?, CASE WHEN typeof(seconds)='integer' AND seconds BETWEEN 0 AND 253402300799
  AND typeof(fraction)='text' AND instr(fraction,char(0))=0 AND length(fraction)=6
  AND fraction GLOB '[0-5][0-9].[0-9][0-9][0-9]'
 THEN seconds*1000000+CAST(substr(fraction,4,3) AS INTEGER)*1000 ELSE NULL END
 FROM sampled`;

export function beginQuotaClock(db: SqlStore, batchId: string): D1PreparedStatement {
 return db.prepare(QUOTA_CLOCK_SQL).bind(batchId);
}

// Lazy CASE is essential: difference only follows t>s; addition only follows
// d<C-q. Thus nonnegative signed64 subtraction and the small addition stay
// INTEGER even at signed64 MAX. No division, floating literal or CAST is used.
function refill(capacity: number, clock: string): string {
 return `CASE WHEN ${clock}<=b.updated_at_us THEN b.credit_us
 WHEN ${clock}-b.updated_at_us>=${capacity}-b.credit_us THEN ${capacity}
 ELSE b.credit_us+(${clock}-b.updated_at_us) END`;
}
export const AUTH_CREDIT_REFILL_SQL = refill(AUTH_CREDIT_CAPACITY_US, 'c.now_us');
export const STATUS_CREDIT_REFILL_SQL = refill(STATUS_CREDIT_CAPACITY_US, 'c.now_us');

// An explicit invariant statement runs before any exhaustion check or formula.
// Missing clocks, corrupt balances/watermarks and unexpected guard/schema faults
// are unavailable, never a synthetic ordinary rate-limit refusal.
export function authenticationCreditStatements(db: SqlStore, batchId: string, sourceKey: string): D1PreparedStatement[] {
 return [
  db.prepare(`INSERT INTO quota_credit_guards(batch_id,kind,invariant_ok,admitted)
   SELECT ?1,'auth',CASE WHEN
    EXISTS(SELECT 1 FROM quota_credit_clocks c WHERE c.batch_id=?1
     AND typeof(c.now_us)='integer' AND c.now_us BETWEEN 0 AND 9223372036854775807)
    AND NOT EXISTS(SELECT 1 FROM auth_source_buckets b WHERE b.source_key=?2 AND
     (typeof(b.credit_us)<>'integer' OR b.credit_us NOT BETWEEN 0 AND 240000000
      OR typeof(b.updated_at_us)<>'integer' OR b.updated_at_us NOT BETWEEN 0 AND 9223372036854775807))
    THEN 1 ELSE 0 END,1`).bind(batchId, sourceKey),
  db.prepare(`UPDATE quota_credit_guards SET admitted=CASE WHEN
   NOT EXISTS(SELECT 1 FROM auth_source_buckets WHERE source_key=?2)
   OR EXISTS(SELECT 1 FROM auth_source_buckets b JOIN quota_credit_clocks c ON c.batch_id=?1
    WHERE b.source_key=?2 AND (${AUTH_CREDIT_REFILL_SQL})>=120000000)
   THEN 1 ELSE 0 END WHERE batch_id=?1 AND kind='auth'`).bind(batchId, sourceKey),
  db.prepare(`INSERT INTO auth_source_buckets AS b(source_key,credit_us,updated_at_us)
   SELECT ?2,120000000,c.now_us FROM quota_credit_clocks c WHERE c.batch_id=?1
   ON CONFLICT(source_key) DO UPDATE SET
    credit_us=(${refill(AUTH_CREDIT_CAPACITY_US, 'excluded.updated_at_us')})-120000000,
    updated_at_us=MAX(b.updated_at_us,excluded.updated_at_us)`).bind(batchId, sourceKey)
 ];
}

// These keys are the existing status family/subject namespaces. Their caller
// still owns independent deployment-window admission and all other limits.
export function statusCreditStatements(db: SqlStore, batchId: string, family: 'installation'|'admin', subjectId: string): D1PreparedStatement[] {
 return [
  db.prepare(`INSERT INTO quota_credit_guards(batch_id,kind,invariant_ok,admitted)
   SELECT ?1,'status',CASE WHEN
    EXISTS(SELECT 1 FROM quota_credit_clocks c WHERE c.batch_id=?1
     AND typeof(c.now_us)='integer' AND c.now_us BETWEEN 0 AND 9223372036854775807)
    AND NOT EXISTS(SELECT 1 FROM status_read_buckets b WHERE b.family=?2 AND b.subject_id=?3 AND
     (typeof(b.credit_us)<>'integer' OR b.credit_us NOT BETWEEN 0 AND 100000000
      OR typeof(b.updated_at_us)<>'integer' OR b.updated_at_us NOT BETWEEN 0 AND 9223372036854775807))
    THEN 1 ELSE 0 END,1`).bind(batchId, family, subjectId),
  db.prepare(`UPDATE quota_credit_guards SET admitted=CASE WHEN
   NOT EXISTS(SELECT 1 FROM status_read_buckets WHERE family=?2 AND subject_id=?3)
   OR EXISTS(SELECT 1 FROM status_read_buckets b JOIN quota_credit_clocks c ON c.batch_id=?1
    WHERE b.family=?2 AND b.subject_id=?3 AND (${STATUS_CREDIT_REFILL_SQL})>=5000000)
   THEN 1 ELSE 0 END WHERE batch_id=?1 AND kind='status'`).bind(batchId, family, subjectId),
  db.prepare(`INSERT INTO status_read_buckets AS b(family,subject_id,credit_us,updated_at_us)
   SELECT ?2,?3,95000000,c.now_us FROM quota_credit_clocks c WHERE c.batch_id=?1
   ON CONFLICT(family,subject_id) DO UPDATE SET
    credit_us=(${refill(STATUS_CREDIT_CAPACITY_US, 'excluded.updated_at_us')})-5000000,
    updated_at_us=MAX(b.updated_at_us,excluded.updated_at_us)`).bind(batchId, family, subjectId)
 ];
}

export function finishQuotaClock(db: SqlStore, batchId: string): D1PreparedStatement[] {
 return [db.prepare('DELETE FROM quota_credit_guards WHERE batch_id=?').bind(batchId),
  db.prepare('DELETE FROM quota_credit_clocks WHERE batch_id=?').bind(batchId)];
}

// Only our specifically named exhaustion CHECK is a rate refusal. All other
// errors, including unknown acknowledgement outcomes, remain unavailable.
// This is internal classification; route integration must retain generic,
// non-oracular no-store 429/503 envelopes and must never auto-retry or refund.
export function quotaCreditFailure(error: unknown): 'exhausted'|'unavailable' {
 return /(?:^|: )CHECK constraint failed: quota_credit_exhausted(?:$|: SQLITE_CONSTRAINT(?:_CHECK)?$)/.test(String(error))
  ? 'exhausted' : 'unavailable';
}
