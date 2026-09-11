// Synthetic native-store proof. No Flickr transport or real credential input.
export interface State {
  revision: number;
  state: "linked" | "paused" | "disconnecting" | "disconnected";
  generation: string | null;
  pending_generation: string | null;
  retiring_generation: string | null;
  operation: string | null;
  writes_paused: number;
}
export class Refusal extends Error {
  constructor(code: string) { super(code); }
}
export function bundle(generation: string): string {
  return JSON.stringify({ fixture: "fga-native-synthetic-only", generation,
    token: `synthetic-token-${generation}`, tokenSecret: `synthetic-secret-${generation}` });
}
export function parseBundle(raw: string, generations: readonly string[]): string {
  if (typeof raw !== "string" || raw.length > 2048) throw new Refusal("invalid_bundle");
  let value: Record<string, unknown>;
  try { value = JSON.parse(raw); } catch { throw new Refusal("invalid_bundle"); }
  if (!value || typeof value !== "object" || Array.isArray(value) ||
      Object.keys(value).sort().join() !== "fixture,generation,token,tokenSecret" ||
      typeof value.generation !== "string" || !generations.includes(value.generation) ||
      value.fixture !== "fga-native-synthetic-only" ||
      value.token !== `synthetic-token-${value.generation}` ||
      value.tokenSecret !== `synthetic-secret-${value.generation}`) {
    throw new Refusal("invalid_bundle");
  }
  return value.generation;
}
export async function observe(secret: Pick<SecretsStoreSecret, "get">,
  generations: readonly string[]): Promise<{ outcome: string; generation?: string }> {
  try {
    // No application caching. Timeout also bounds a binding that never settles.
    let timer: ReturnType<typeof setTimeout> | undefined;
    try {
      const raw = await Promise.race([secret.get(), new Promise<never>((_, reject) => {
        timer = setTimeout(() => reject(new Refusal("unavailable")), 10_000);
      })]);
      for (const generation of generations) {
        if (raw === JSON.stringify({ fixture: "fga-native-retired", generation })) {
          return { outcome: "retired", generation };
        }
      }
      return { outcome: "present", generation: parseBundle(raw, generations) };
    } finally { if (timer !== undefined) clearTimeout(timer); }
  } catch (error) {
    return { outcome: error instanceof Refusal ? error.message : "unavailable" };
  }
}
export async function resolve(readState: () => Promise<State>,
  secret: Pick<SecretsStoreSecret, "get">, generations: readonly string[]) {
  const before = await readState();
  if (before.state !== "linked") return { outcome: "stopped" };
  const value = await observe(secret, generations);
  if (value.outcome !== "present") return value;
  const after = await readState();
  if (after.state !== "linked" || after.revision !== before.revision ||
      after.generation !== before.generation) return { outcome: "state_changed" };
  if (value.generation !== after.generation) return { outcome: "generation_mismatch" };
  // Values never leave operation-local scope, and no Flickr call is made.
  return { outcome: "usable", generation: after.generation };
}
export class Authority {
  readonly db: D1Database;
  readonly runId: string;
  constructor(db: D1Database, runId: string) { this.db = db; this.runId = runId; }
  async state(): Promise<State> {
    const row = await this.db.prepare(`SELECT revision,state,generation,pending_generation,
      retiring_generation,operation,writes_paused FROM link WHERE id=1 AND run_id=?`).bind(this.runId).first<State>();
    if (!row || !["linked", "paused", "disconnecting", "disconnected"].includes(row.state) ||
        !Number.isSafeInteger(row.revision) || row.writes_paused !== 1) throw new Refusal("invalid_state");
    return row;
  }
  async change(sql: string, values: (string | number | null)[], failAudit = false, attempt?: D1PreparedStatement) {
    const mutation = this.db.prepare(sql + " RETURNING revision").bind(...values);
    if (failAudit) {
      // Deliberate atomicity fault: the entire batch, including the trigger event, must roll back.
      try {
        await this.db.batch([mutation,
          this.db.prepare("INSERT INTO events VALUES(-1,'fault',0)")]);
      } catch (error) {
        if (error instanceof Error && error.message.includes("CHECK constraint failed") &&
            error.message.includes("valid=1")) throw new Refusal("injected_audit_failure");
        throw error;
      }
      throw new Refusal("fault_did_not_fail");
    }
    const reply = attempt
      ? (await this.db.batch<{ revision: number }>([attempt, mutation]))[1]
      : await mutation.all<{ revision: number }>();
    if (reply.results.length !== 1) throw new Refusal("conflict");
    return this.state();
  }
  async begin(kind: "replace" | "delete", expected: number, operation: string, generation: string) {
    return this.change(`UPDATE link SET revision=revision+1,state=?,
      generation=CASE WHEN ?='delete' THEN NULL ELSE generation END,
      retiring_generation=CASE WHEN ?='delete' THEN generation ELSE NULL END,
      pending_generation=?,operation=? WHERE id=1 AND run_id=? AND revision=?
      AND operation IS NULL AND state IN ('linked','disconnected')
      AND (?='replace' OR state='linked')
      AND (?='delete' OR generation IS NULL OR generation<>?)`,
      [kind === "replace" ? "paused" : "disconnecting", kind, kind,
        kind === "replace" ? generation : null, operation, this.runId, expected, kind, kind, generation],
      false, this.db.prepare("INSERT OR IGNORE INTO attempts VALUES(?,?,?)").bind(operation, expected, kind));
  }
  async check(kind: "replace" | "delete", expected: number, operation: string, generation: string) {
    const row = await this.state();
    if (row.revision !== expected || row.operation !== operation ||
        row.state !== (kind === "replace" ? "paused" : "disconnecting") ||
        (kind === "replace" && row.pending_generation !== generation) ||
        (kind === "delete" && row.retiring_generation !== generation)) throw new Refusal("conflict");
    return row;
  }
  async activate(expected: number, operation: string, generation: string, failAudit = false) {
    return this.change(`UPDATE link SET revision=revision+1,state='linked',generation=?,
      pending_generation=NULL,operation=NULL WHERE id=1 AND run_id=? AND revision=?
      AND state='paused' AND operation=? AND pending_generation=?`,
      [generation, this.runId, expected, operation, generation], failAudit);
  }
  async confirmRetirement(expected: number, operation: string, generation: string) {
    // Only the authenticated proof controller calls this after repeated native retirement observations.
    // A production lifecycle service must obtain that evidence itself, never trust browser input.
    return this.change(`UPDATE link SET revision=revision+1,state='disconnected',operation=NULL,retiring_generation=NULL
      WHERE id=1 AND run_id=? AND revision=? AND state='disconnecting' AND operation=? AND retiring_generation=?`,
      [this.runId, expected, operation, generation]);
  }
}
