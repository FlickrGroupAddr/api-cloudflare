// MIT License; copyright 2026 Terry Ott.
// Exact ordinary closed restoration capability. Its implementation body is
// verified against the reviewed private helper; no authentication is replaced.
import { createWorker, type Env } from '../../src/worker.ts';
import { LOOKUP_SQL } from '../../src/installations.ts';
import { MainEntryUnavailable } from '../../src/main_entry_maintenance.ts';
export function closedRestorationCheck(request: Request, db: D1Database, readEnabled?: string): Promise<Response> {
  const unavailable = (): never => { throw new MainEntryUnavailable(); };
  const lookupOnly = {
    prepare(sql: string) {
      if (sql !== LOOKUP_SQL) return unavailable();
      return { bind(digest: string) {
        return { first: () => db.prepare(sql).bind(digest).first() };
      } };
    },
  } as D1Database;
  // Same ordinary worker code and feature gate as a deployed read. No success
  // body is fabricated, no authentication is skipped and no error is rewritten.
  return createWorker(async () => unavailable()).fetch(request,
    { DB: lookupOnly, FGA_READ_ENABLED: readEnabled } as Env);
}
