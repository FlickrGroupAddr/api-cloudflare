import { ProvenNotDispatched } from "./dispatch_policy.ts";
import type { SqlStore } from "./admission.ts";
import type { AttemptContext, Reservation } from "./fail_polite.ts";
import { NOW_US_SQL } from "./installations.ts";

export interface FlickrRatePolicy { capacity: number; windowMs: number; }
export const DEFAULT_FLICKR_RATE_POLICY: FlickrRatePolicy = { capacity: 60, windowMs: 60_000 };

export async function reserveFlickrAttempt(
  db: SqlStore, context: AttemptContext, policy: FlickrRatePolicy = DEFAULT_FLICKR_RATE_POLICY,
): Promise<Reservation | null> {
  if (!Number.isSafeInteger(policy.capacity) || policy.capacity < 3 || policy.capacity > 3600 ||
      !Number.isSafeInteger(policy.windowMs) || policy.windowMs < 1000 || policy.windowMs > 3_600_000)
    throw new Error("invalid_flickr_rate_policy");
  const id = crypto.randomUUID(), tx = crypto.randomUUID(), window = crypto.randomUUID();
  const values = [id, context.attemptId, context.photoId, context.groupId,
    policy.capacity, policy.windowMs, tx, window];
  const sql = (text: string) => db.prepare(
    "WITH input AS(SELECT ?1 r,?2 a,?3 p,?4 g,?5 c,?6 w,?7 t,?8 n) " + text,
  ).bind(...values);
  try {
    await db.batch([
      sql(`INSERT INTO flickr_rate_window(singleton,window_id,capacity,window_ms,expires_at_us)
        VALUES(1,?8,?5,?6,${NOW_US_SQL}+?6*1000) ON CONFLICT(singleton) DO UPDATE SET
        window_id=excluded.window_id,capacity=excluded.capacity,window_ms=excluded.window_ms,
        expires_at_us=excluded.expires_at_us,reserved_slots=0
        WHERE flickr_rate_window.expires_at_us<=${NOW_US_SQL}`),
      sql(`INSERT INTO transaction_guards(transaction_id,approved) VALUES(?7,
        EXISTS(SELECT 1 FROM flickr_rate_window WHERE singleton=1 AND capacity=?5 AND window_ms=?6
          AND reserved_slots+3<=capacity AND expires_at_us>${NOW_US_SQL})
        AND EXISTS(SELECT 1 FROM submission_attempts a JOIN submission_intents i ON i.intent_id=a.intent_id
          JOIN group_partitions p ON p.partition_id=i.partition_id
          WHERE p.lease_id=a.lease_id AND p.lease_generation=a.lease_generation
          AND p.lease_expires_at_us>${NOW_US_SQL} AND p.invocation_deadline_at_us>${NOW_US_SQL} AND a.attempt_id=?2 AND i.photo_id=?3 AND i.group_id=?4 AND i.state='attempting'
          AND NOT EXISTS(SELECT 1 FROM attempt_resolutions WHERE attempt_id=a.attempt_id)))`),
      sql("UPDATE flickr_rate_window SET reserved_slots=reserved_slots+3 WHERE singleton=1"),
      sql(`INSERT INTO flickr_rate_reservations(reservation_id,attempt_id,window_id,expires_at_us)
        SELECT ?1,?2,window_id,expires_at_us FROM flickr_rate_window WHERE singleton=1`),
      sql("DELETE FROM transaction_guards WHERE transaction_id=?7"),
    ]);
  } catch { return null; } // Unknown allocation remains charged; never replay it.
  const used = new Set<string>();
  let released = false;
  return {
    id,
    async check(attempt) {
      if (released || attempt.attemptId !== context.attemptId || attempt.photoId !== context.photoId || attempt.groupId !== context.groupId) return false;
      const row = await db.prepare(`SELECT 1 AS valid FROM flickr_rate_reservations r
        JOIN flickr_rate_window w ON w.window_id=r.window_id
        JOIN submission_attempts a ON a.attempt_id=r.attempt_id
        JOIN submission_intents i ON i.intent_id=a.intent_id
        JOIN group_partitions p ON p.partition_id=i.partition_id
        WHERE p.lease_id=a.lease_id AND p.lease_generation=a.lease_generation
        AND p.lease_expires_at_us>${NOW_US_SQL} AND p.invocation_deadline_at_us>${NOW_US_SQL}
        AND NOT EXISTS(SELECT 1 FROM attempt_resolutions WHERE attempt_id=a.attempt_id) AND r.reservation_id=? AND r.attempt_id=? AND r.released=0 AND r.expires_at_us>${NOW_US_SQL}`)
        .bind(id, context.attemptId).first();
      return row !== null;
    },
    consume(operation) {
      if (released || used.has(operation) ||
          operation === "preflight" && !used.has("membership") ||
          operation === "add" && !used.has("preflight")) throw new Error("invalid_flickr_reservation");
      used.add(operation);
    },
    proveAddNotSent(proof) {
      if (!(proof instanceof ProvenNotDispatched) || released || !used.has("add"))
        throw new Error("invalid_zero_handoff_proof");
      used.delete("add");
    },
    async releaseUnused() {
      if (released) return;
      released = true;
      const release = crypto.randomUUID();
      try {
        await db.batch([
          db.prepare(`INSERT INTO transaction_guards(transaction_id,approved)
            SELECT ?,EXISTS(SELECT 1 FROM flickr_rate_reservations WHERE reservation_id=? AND released=0)`)
            .bind(release,id),
          db.prepare(`UPDATE flickr_rate_window SET reserved_slots=reserved_slots-?
            WHERE window_id=(SELECT window_id FROM flickr_rate_reservations WHERE reservation_id=? AND released=0)`)
            .bind(3-used.size,id),
          db.prepare("UPDATE flickr_rate_reservations SET released=1,consumed_slots=? WHERE reservation_id=? AND released=0")
            .bind(used.size,id),
          db.prepare("DELETE FROM transaction_guards WHERE transaction_id=?").bind(release),
        ]);
      } catch { /* Conservatively charged until window expiry; no repeated refund. */ }
    },
  };
}

/** API/lifecycle calls share the dispatcher's key-wide budget, one operation at a time. */
export function budgetedFlickrFetch(db:SqlStore,fetcher:(request:Request)=>Promise<Response>) {
  return async(request:Request):Promise<Response>=>{
    if(new URL(request.url).origin!=="https://www.flickr.com")return fetcher(request);
    const {capacity,windowMs}=DEFAULT_FLICKR_RATE_POLICY;
    const id=crypto.randomUUID(),window=crypto.randomUUID();
    try {
      await db.batch([
        db.prepare(`INSERT INTO flickr_rate_window(singleton,window_id,capacity,window_ms,expires_at_us)
          VALUES(1,?,?,?,${NOW_US_SQL}+?*1000) ON CONFLICT(singleton) DO UPDATE SET
          window_id=excluded.window_id,capacity=excluded.capacity,window_ms=excluded.window_ms,
          expires_at_us=excluded.expires_at_us,reserved_slots=0
          WHERE flickr_rate_window.expires_at_us<=${NOW_US_SQL}`).bind(window,capacity,windowMs,windowMs),
        db.prepare(`INSERT INTO transaction_guards(transaction_id,approved) VALUES(?,
          EXISTS(SELECT 1 FROM flickr_rate_window WHERE singleton=1 AND capacity=? AND window_ms=?
            AND reserved_slots+1<=capacity AND expires_at_us>${NOW_US_SQL}))`).bind(id,capacity,windowMs),
        db.prepare("UPDATE flickr_rate_window SET reserved_slots=reserved_slots+1 WHERE singleton=1"),
        db.prepare("DELETE FROM transaction_guards WHERE transaction_id=?").bind(id),
      ]);
    } catch {throw new Error("flickr_global_rate_unavailable");}
    // Once charged, an uncertain network outcome remains charged until window expiry.
    return fetcher(request);
  };
}
