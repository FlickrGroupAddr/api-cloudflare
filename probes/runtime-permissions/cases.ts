// Synthetic fixtures only. This is a capability probe, not a production schema.
export type Family = "blocks" | "audit";
export type Row = Record<string, string | number | null>;
export interface ProbeCase {
  id: string;
  family: Family;
  kind: "control" | "guard" | "capability";
  table: string;
  setup: string[];
  steps: string[];
}
export const ACTIONS = [
  "read", "insert", "update", "delete", "replace", "upsert", "cascade",
  "check_enforced", "foreign_key_enforced", "drop_update_guard", "drop_delete_guard", "drop_table", "rename_table", "disable_check",
] as const;

function fixture(family: Family, action: typeof ACTIONS[number]): ProbeCase {
  const table = `probe_${family}_${action}`;
  const parent = `${table}_parent`;
  const setup = [
    `CREATE TABLE ${parent} (id TEXT PRIMARY KEY)`,
    `INSERT INTO ${parent} VALUES ('parent')`,
    `CREATE TABLE ${table} (
      record_id TEXT PRIMARY KEY,
      parent_id TEXT NOT NULL REFERENCES ${parent}(id) ON DELETE CASCADE,
      evidence TEXT NOT NULL,
      check_value INTEGER NOT NULL CHECK(check_value = 1)
    ) STRICT`,
    `INSERT INTO ${table} VALUES ('seed', 'parent', 'original', 1)`,
    `CREATE TRIGGER ${table}_no_delete BEFORE DELETE ON ${table}
      BEGIN SELECT RAISE(ABORT, 'FGA_PROBE_GUARD'); END`,
    `CREATE TRIGGER ${table}_no_replace BEFORE INSERT ON ${table}
      WHEN EXISTS(SELECT 1 FROM ${table} WHERE record_id = NEW.record_id)
      BEGIN SELECT RAISE(ABORT, 'FGA_PROBE_GUARD'); END`,
  ];
  // The check-toggle case isolates CHECK enforcement from the update trigger.
  if (action !== "disable_check" && action !== "check_enforced") setup.push(
    `CREATE TRIGGER ${table}_no_update BEFORE UPDATE ON ${table}
      BEGIN SELECT RAISE(ABORT, 'FGA_PROBE_GUARD'); END`,
  );
  const statements: Record<typeof ACTIONS[number], string[]> = {
    read: [],
    insert: [`INSERT INTO ${table} VALUES ('added', 'parent', 'new', 1)`],
    update: [`UPDATE ${table} SET evidence = 'rewritten' WHERE record_id = 'seed'`],
    delete: [`DELETE FROM ${table} WHERE record_id = 'seed'`],
    replace: [`INSERT OR REPLACE INTO ${table} VALUES ('seed', 'parent', 'rewritten', 1)`],
    upsert: [`INSERT INTO ${table} VALUES ('seed', 'parent', 'rewritten', 1)
      ON CONFLICT(record_id) DO UPDATE SET evidence = excluded.evidence`],
    cascade: [`DELETE FROM ${parent} WHERE id = 'parent'`],
    foreign_key_enforced: [`INSERT INTO ${table} VALUES ('orphan', 'missing', 'invalid', 1)`],
    check_enforced: [`UPDATE ${table} SET check_value = 2 WHERE record_id = 'seed'`],
    drop_update_guard: [
      `DROP TRIGGER ${table}_no_update`,
      `UPDATE ${table} SET evidence = 'rewritten' WHERE record_id = 'seed'`,
    ],
    drop_delete_guard: [
      `DROP TRIGGER ${table}_no_delete`,
      `DELETE FROM ${table} WHERE record_id = 'seed'`,
    ],
    drop_table: [`DROP TABLE ${table}`],
    rename_table: [`ALTER TABLE ${table} RENAME TO ${table}_renamed`],
    disable_check: [
      "PRAGMA ignore_check_constraints = ON",
      `UPDATE ${table} SET check_value = 2 WHERE record_id = 'seed'`,
      "PRAGMA ignore_check_constraints = OFF",
    ],
  };
  return {
    id: `${family}.${action}`, family, table, setup, steps: statements[action],
    kind: action === "read" || action === "insert" ? "control"
      : ["update", "delete", "replace", "upsert", "cascade", "check_enforced", "foreign_key_enforced"].includes(action) ? "guard"
      : "capability",
  };
}

export const CASES: ProbeCase[] = (["blocks", "audit"] as const)
  .flatMap((family) => ACTIONS.map((action) => fixture(family, action)));

export const D1_PHASE_SIZE = 4;
export const PHASE_COUNT = Math.ceil(CASES.length / D1_PHASE_SIZE) + 1;

export function metadataSetup(runId: string): string[] {
  if (!/^rp-[a-f0-9]{24}$/.test(runId)) throw new Error("invalid_probe_run_id");
  return [
    `CREATE TABLE probe_meta (run_id TEXT PRIMARY KEY, executed INTEGER NOT NULL CHECK(executed BETWEEN 0 AND ${PHASE_COUNT})) STRICT`,
    `INSERT INTO probe_meta VALUES ('${runId}', 0)`,
  ];
}

export function allSetup(runId: string): string[] {
  return [...metadataSetup(runId), ...CASES.flatMap((test) => test.setup)];
}
