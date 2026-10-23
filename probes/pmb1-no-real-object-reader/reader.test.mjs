// Synthetic source tests only; no managed storage, namespace or actual closure.
import assert from "node:assert/strict";
import test from "node:test";
import { DatabaseSync } from "node:sqlite";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { PROFILE, capture, canonical, buildGuardManifest, sha2_256, Refused } from "./reader.ts";
import { bootstrap, Pmb1ObjectCandidate } from "../pmb1-object/candidate.ts";

const fixture = JSON.parse(readFileSync(new URL("./synthetic-fixture.json", import.meta.url), "utf8"));
const source = new Uint8Array(readFileSync(new URL("./reader.ts", import.meta.url)));
const hash = bytes => createHash("sha256").update(bytes).digest("hex");
const scalarOrder = (a, b) => Buffer.compare(Buffer.from(a), Buffer.from(b));
const idKey = id => canonical([id.namespace, id.id]);
const clone = structuredClone;
const defaultLimits = { objects: 8, schema: 128, tables: 16, columns: 64, rows: 200, kv: 100, bytes: 1024 * 1024, calls: 1000, page: 2, milliseconds: 30000 };
const closure = { interval: "synthetic-common", start: "100", end: "900", custody: "synthetic-only",
  writers: [{ id: "application", epoch: "writer-4", disposition: "settled" }, { id: "operator", epoch: "operator-7", disposition: "retired" }] };
function query(db, sql) { return db.prepare(sql).all().map(row => ({ ...row })); }
function makeDB() {
  const db = new DatabaseSync(":memory:"); db.exec(fixture.ddl);
  for (const guard of fixture.manifest.guards) db.exec(guard.sql);
  db.exec(`INSERT INTO payload(_rowid_,rowid,value,note) VALUES
    (-9223372036854775808,'shadow',-9223372036854775808,'\uFEFFzero'),
    (-1,'shadow',9007199254740991,'nul' || char(0) || 'é'),
    (0,'shadow',9007199254740992,'😀'),
    (1,'shadow',9007199254740993,'duplicate'),
    (9223372036854775807,'shadow',9223372036854775807,'duplicate');
    INSERT INTO composite VALUES(-9223372036854775808,'z',x'00FF'),(7,'A',NULL),(7,'b',x'');
    INSERT INTO "__cf_kv" VALUES('sql-bookkeeping',-17);
    INSERT INTO bookkeeping VALUES(9223372036854775807);`);
  return db;
}
async function setup() {
  const ids = [{ namespace: "synthetic-namespace", id: "object-a" }, { namespace: "synthetic-namespace", id: "object-b" }];
  const stores = ids.map((id, i) => ({ id, db: makeDB(), alarm: i === 0 ? 1700000000000 : null,
    kv: new Map([
      ["__cf_kv:exposed", new Uint8Array([0, 255, 128])], ["pmb1:alarm-sequence", "9007199254740993"],
      ["structured", { nested: [null, false, 1.5, "text", { byte: new Uint8Array([0, 255]) }] }],
      ["bigint", -9223372036854775808n], ["boolean", false], ["buffer", new Uint8Array([7, 0]).buffer],
      ["minus-zero", -0], ["number", 1.5], ["text", "\uFEFFnul\0é😀"],
    ]), fenceReads: 0 }));
  stores[0].kv.set("pmb1:alarm-invocation", { id: "dispatch-7", generation: "19", alarmGeneration: "9007199254740993" });
  const fences = Object.fromEntries(ids.map(id => [idKey(id), { generation: "19", state: "closed", writerEpoch: "writer-4", custody: closure.custody, interval: closure.interval }]));
  const request = { profile: PROFILE, expectedObjects: ids.map(id => ({ ...id,
    guardManifest: clone(fixture.manifest), guardManifestSha256: fixture.manifestSha256,
    alarmKeys: { invocation: "pmb1:alarm-invocation", sequence: "pmb1:alarm-sequence" } })),
    closure: clone(closure), expectedWriterIds: ["application", "operator"],
    expectedSources: { "reader.ts": hash(source) }, sourceBytes: { "reader.ts": source.slice() }, fences, limits: clone(defaultLimits) };
  const hooks = { query: null, kv: null, alarm: null, fence: null, objects: null, closure: null };
  function page(entries, after, limit, key) {
    const rest = entries.filter(e => after === null || scalarOrder(key(e), after) > 0).slice(0, limit);
    return { entries: rest, next: rest.length ? key(rest.at(-1)) : null };
  }
  const adapter = {
    closure: async () => hooks.closure ? hooks.closure(clone(closure)) : clone(closure),
    listObjects: async (after, limit) => {
      const p = page(clone(ids), after, limit, idKey); return hooks.objects ? hooks.objects(p, after) : p;
    },
    readObject: async (id, read) => {
      const s = stores.find(s => s.id.id === id.id); s.db.exec("BEGIN");
      try { return await read({
        query: async sql => { const r = query(s.db, sql); return hooks.query ? hooks.query(r, sql, s) : r; },
        listKV: async (after, limit) => {
          const p = page([...s.kv].sort((a, b) => scalarOrder(a[0], b[0])), after, limit, e => e[0]);
          return hooks.kv ? hooks.kv(p, after, s) : p;
        },
        getAlarm: async () => hooks.alarm ? hooks.alarm(s.alarm, s) : s.alarm,
        fence: async () => { const f = { ...fences[idKey(id)], observedAt: String(++s.fenceReads === 1 ? 200 : 800) }; return hooks.fence ? hooks.fence(f, s) : f; },
      }); } finally { s.db.exec("ROLLBACK"); }
    },
  };
  return { adapter, request, stores, hooks, close: () => stores.forEach(s => s.db.close()) };
}
async function run(mutator = () => {}) {
  const f = await setup(); try { await mutator(f); return await capture(f.adapter, f.request); } finally { f.close(); }
}
async function refuses(mutator, category) { await assert.rejects(run(mutator), e => e instanceof Refused && (!category || e.message === category)); }

// Independent direct SQLite-binding reference. No reader decoder/query builder.
// BigInts are actual binding results, not decimal text re-encoded by the candidate.
function referenceTables(db) {
  const result = {};
  for (const { name } of db.prepare("SELECT name FROM sqlite_schema WHERE type='table' ORDER BY name").all()) {
    const q = s => '"' + s.replaceAll('"', '""') + '"';
    const columns = db.prepare(`PRAGMA table_xinfo(${q(name)})`).all().map(r => r.name);
    const without = db.prepare("SELECT wr FROM pragma_table_list WHERE name=?").get(name).wr === 1;
    const pk = db.prepare(`PRAGMA table_xinfo(${q(name)})`).all().filter(r => r.pk).sort((a, b) => a.pk - b.pk).map(r => r.name);
    const rowid = ["oid", "_rowid_", "rowid"].find(a => !columns.map(c => c.toLowerCase()).includes(a));
    const expressions = [...(without ? [] : [q(rowid) + " AS independent_identity"]), ...columns.flatMap((c, i) => [`typeof(${q(c)}) AS t${i}`, `${q(c)} AS v${i}`])];
    const sql = `SELECT ${expressions.join(",")} FROM ${q(name)} ORDER BY ` + (without ? pk.map(k => q(k) + " COLLATE BINARY").join(",") : q(rowid));
    const statement = db.prepare(sql); statement.setReadBigInts(true);
    const rows = statement.all().map(r => {
      const cells = columns.map((_, i) => {
        const t = r[`t${i}`], v = r[`v${i}`];
        assert.notEqual(t, "real");
        return [t, t === "integer" ? v.toString() : t === "blob" ? Buffer.from(v).toString("hex") : v];
      });
      return { identity: without ? pk.map(k => cells[columns.indexOf(k)]) : r.independent_identity.toString(), cells };
    });
    result[name] = { columns, rows };
  }
  return result;
}
test("canonical manifest exactly matches completed Python guard implementation, including Unicode", async () => {
  const m = fixture.manifest;
  assert.equal(hash(Buffer.from(canonical(m))), fixture.manifestSha256);
  assert.deepEqual(await buildGuardManifest({ schema: m.baseSchema, tableList: m.tableList, columns: m.columns }, defaultLimits), m);
});
test("guard builder preserves completed Python casefold refusal policy in its conservative domain", async t => {
  const base = () => ({ schema: clone(fixture.manifest.baseSchema), tableList: clone(fixture.manifest.tableList), columns: clone(fixture.manifest.columns) });
  await t.test("ASCII table names distinct only by case refuse", async () => {
    const b = base(), row = clone(b.schema.find(r => r.type === "table" && r.name === "payload"));
    row.name = row.tbl_name = "PAYLOAD"; row.sql = row.sql.replace("payload", "PAYLOAD"); b.schema.push(row);
    b.schema.sort((a,b) => scalarOrder(a.type,b.type) || scalarOrder(a.name,b.name) || scalarOrder(a.tbl_name,b.tbl_name));
    b.tableList.push({ ...b.tableList.find(r => r.name === "payload"), name: "PAYLOAD" });
    b.tableList.sort((a,b) => scalarOrder(a.name,b.name)); b.columns.PAYLOAD = clone(b.columns.payload);
    await assert.rejects(buildGuardManifest(b, defaultLimits), e => e instanceof Refused && e.message === "duplicate_casefold_table");
  });
  await t.test("Unicode casefold spelling in base-trigger literal refuses", async () => {
    const b = base(); b.schema.find(r => r.type === "trigger").sql = "CREATE TRIGGER payload_history AFTER INSERT ON payload BEGIN SELECT 'raiſe ignore'; END";
    await assert.rejects(buildGuardManifest(b, defaultLimits), e => e instanceof Refused && e.message === "unsupported_base_trigger");
  });
});
test("complete two-object SQL/KV/alarm capture matches independent direct typed oracle", async () => {
  const f = await setup();
  try {
    const expected = f.stores.map(s => referenceTables(s.db));
    const observed = await capture(f.adapter, f.request);
    assert.equal(observed.actualQualification, false); assert.equal(observed.objects.length, 2);
    observed.objects.forEach((o, i) => {
      assert.deepEqual(o.tables, expected[i]);
      assert.deepEqual(o.census, { schema: fixture.manifest.schema, tableList: fixture.manifest.tableList, columns: fixture.manifest.columns });
      const expectedNested = [["null", null], ["boolean", false], ["number-binary64", "3ff8000000000000"], ["text", "text"], ["object", [["byte", ["uint8array", "00ff"]]]]];
      const expectedKV = [
        ["__cf_kv:exposed", ["uint8array", "00ff80"]], ["bigint", ["bigint", "-9223372036854775808"]],
        ["boolean", ["boolean", false]], ["buffer", ["arraybuffer", "0700"]],
        ["minus-zero", ["number-binary64", "8000000000000000"]], ["number", ["number-binary64", "3ff8000000000000"]],
        ...(i === 0 ? [["pmb1:alarm-invocation", ["object", [["id", ["text", "dispatch-7"]], ["generation", ["text", "19"]], ["alarmGeneration", ["text", "9007199254740993"]]]]]] : []),
        ["pmb1:alarm-sequence", ["text", "9007199254740993"]],
        ["structured", ["object", [["nested", ["array", expectedNested]]]]],
        ["text", ["text", "\uFEFFnul\0é😀"]],
      ];
      assert.deepEqual(o.kv, expectedKV);
    });
    assert.equal(observed.objects[0].tables.payload.rows.at(-1).identity, "9223372036854775807");
    assert.deepEqual(observed.objects[0].alarm, { timeMs: "1700000000000", generation: "19", sequence: "9007199254740993", dispatch: { id: "dispatch-7", generation: "19", alarmGeneration: "9007199254740993" } });
    assert.equal(observed.objects[1].alarm.timeMs, null);
    const kv = new Map(observed.objects[0].kv);
    assert.deepEqual(kv.get("__cf_kv:exposed"), ["uint8array", "00ff80"]);
    assert.deepEqual(kv.get("minus-zero"), ["number-binary64", "8000000000000000"]);
    assert.deepEqual(kv.get("number"), ["number-binary64", "3ff8000000000000"]);
    assert.deepEqual(kv.get("bigint"), ["bigint", "-9223372036854775808"]);
    assert.deepEqual(kv.get("text"), ["text", "\uFEFFnul\0é😀"]);
    assert.deepEqual(kv.get("buffer"), ["arraybuffer", "0700"]);
    assert.deepEqual(kv.get("structured"), ["object", [["nested", ["array", [["null", null], ["boolean", false], ["number-binary64", "3ff8000000000000"], ["text", "text"], ["object", [["byte", ["uint8array", "00ff"]]]]]]]]]);
    assert.equal(observed.objects[0].tables.payload.rows[0].cells[3][1], "\uFEFFzero😀");
  } finally { f.close(); }
});
test("existing unregistered candidate produces the captured structured alarm marker without a new writer protocol", async () => {
  const f = await setup(), s = f.stores[0]; s.db.close(); s.db = new DatabaseSync(":memory:"); s.kv.clear(); s.alarm = null;
  const storage = {
    sql: { exec: (sql, ...bindings) => {
      if (sql.includes("CREATE TABLE")) { s.db.exec(sql); return { toArray: () => [] }; }
      const rows = queryWithBindings(sql, bindings); return { toArray: () => rows };
    } },
    transaction: async fn => {
      s.db.exec("BEGIN"); const kv = clone(s.kv), alarm = s.alarm;
      try {
        const value = await fn({ list: async () => clone(s.kv), get: async key => clone(s.kv.get(key)),
          put: async (key, value) => { s.kv.set(key, clone(value)); }, delete: async key => s.kv.delete(key),
          getAlarm: async () => s.alarm, setAlarm: async time => { s.alarm = time; }, deleteAlarm: async () => { s.alarm = null; } });
        s.db.exec("COMMIT"); return value;
      } catch (error) { s.db.exec("ROLLBACK"); s.kv = kv; s.alarm = alarm; throw error; }
    },
  };
  function queryWithBindings(sql, bindings) { return s.db.prepare(sql).all(...bindings).map(row => ({ ...row })); }
  try {
    await bootstrap(storage);
    const candidate = new Pmb1ObjectCandidate(storage, async generation => ({ generation, preCloseExecutionsDisposed: true,
      temporaryExecutionsDisposed: true, oldVersionsFenced: true, queuedAndAlarmCallbacksDisposed: true }));
    await candidate.reopen("1"); const admitted = await candidate.admit("existing-invocation", "2");
    const dispatch = await candidate.write(admitted, "work", 1700000000000);
    const base = { schema: query(s.db, "SELECT type,name,tbl_name,sql FROM main.sqlite_schema ORDER BY type,name,tbl_name"),
      tableList: query(s.db, 'SELECT schema,name,type,ncol,wr,"strict" FROM pragma_table_list WHERE schema=\'main\' ORDER BY name'), columns: {} };
    for (const row of base.schema.filter(r => r.type === "table")) base.columns[row.name] = query(s.db, `PRAGMA table_xinfo('${row.name}')`);
    const manifest = await buildGuardManifest(base, defaultLimits);
    for (const g of manifest.guards) s.db.exec(g.sql);
    f.request.expectedObjects[0].guardManifest = manifest;
    f.request.expectedObjects[0].guardManifestSha256 = await sha2_256(Buffer.from(canonical(manifest)));
    f.request.fences[idKey(s.id)].generation = "2";
    const observed = await capture(f.adapter, f.request);
    assert.deepEqual(observed.objects[0].alarm.dispatch, dispatch);
    const typed = new Map(observed.objects[0].kv).get("pmb1:alarm-invocation");
    assert.deepEqual(typed, ["object", [["id", ["text", "existing-invocation"]], ["generation", ["text", "2"]], ["alarmGeneration", ["text", "1"]]]]);
    assert.equal(new Map(observed.objects[0].kv).get("pmb1:admission")[1], true);
    // The fence is supplied synthetic evidence. This test intentionally proves
    // source shape fit only: the real candidate cannot close with a pending alarm.
    assert.equal(observed.actualQualification, false);
  } finally { f.close(); }
});
test("independent population, terminal and duplicate/order enforcement", async t => {
  await t.test("omitted object", () => refuses(f => { f.hooks.objects = p => ({ ...p, entries: p.entries.filter(id => id.id !== "object-b"), next: p.entries.length ? idKey(p.entries[0]) : null }); }));
  await t.test("unknown object", () => refuses(f => { f.request.expectedObjects.pop(); delete f.request.fences[idKey({ namespace: "synthetic-namespace", id: "object-b" })]; }, "incomplete_object_population"));
  await t.test("duplicate object", () => refuses(f => { f.hooks.objects = p => p.entries.length ? { entries: [p.entries[0], p.entries[0]], next: idKey(p.entries[0]) } : p; }, "object_order"));
  await t.test("missing terminal", () => refuses(f => { f.hooks.objects = p => p.entries.length ? p : { entries: [], next: "bogus" }; }, "invalid_terminal_page"));
  await t.test("expected population order", () => refuses(f => { f.request.expectedObjects.reverse(); }, "object_population_order"));
});
test("full observed SQL census and fixed guards cannot be replaced by hash claims", async t => {
  await t.test("guard missing", () => refuses(f => { f.stores[0].db.exec('DROP TRIGGER "' + fixture.manifest.guards[0].name + '"'); }, "schema_or_guard_drift"));
  await t.test("forged guard plus matching incoming hash", () => refuses(f => { const o = f.request.expectedObjects[0]; o.guardManifest.guards[0].sql += " -- altered"; o.guardManifestSha256 = hash(Buffer.from(canonical(o.guardManifest))); }, "fixed_guard_definition"));
  await t.test("unexpected SQL table", () => refuses(f => { f.stores[0].db.exec("CREATE TABLE surprise(value)"); }, "schema_or_guard_drift"));
  await t.test("inaccessible __cf_kv is complete refusal", () => refuses(f => { f.hooks.query = (r, sql) => { if (sql.includes('FROM main."__cf_kv"')) throw Error("private"); return r; }; }, "source_read_failed"));
  await t.test("extra columns", () => refuses(f => { f.stores[0].db.exec("ALTER TABLE bookkeeping ADD COLUMN extra"); }, "schema_or_guard_drift"));
  await t.test("bookkeeping unsupported, never skipped", () => refuses(async f => {
    const m = f.request.expectedObjects[0].guardManifest;
    m.baseSchema.push({ type: "table", name: "sqlite_sequence", tbl_name: "sqlite_sequence", sql: "CREATE TABLE sqlite_sequence(name,seq)" });
    m.baseSchema.sort((a,b) => scalarOrder(a.type,b.type) || scalarOrder(a.name,b.name));
    m.tableList.push({ schema: "main", name: "sqlite_sequence", type: "table", ncol: 2, wr: 0, strict: 0 });
    m.tableList.sort((a,b) => scalarOrder(a.name,b.name));
    m.columns.sqlite_sequence = ["name", "seq"].map((name,cid) => ({ cid, name, type: "", notnull: 0, dflt_value: null, pk: 0, hidden: 0 }));
    f.request.expectedObjects[0].guardManifestSha256 = hash(Buffer.from(canonical(m)));
  }, "unguardable_table"));
});
test("actual REAL is rejected after guards bypassed then restored, in unrelated cells", async () => {
  await refuses(f => {
    const gs = fixture.manifest.guards.filter(g => g.table === "__cf_kv");
    for (const g of gs) f.stores[0].db.exec(`DROP TRIGGER "${g.name}"`);
    f.stores[0].db.exec('INSERT INTO "__cf_kv" VALUES(\'unexpected-real\',1.0)');
    for (const g of gs) f.stores[0].db.exec(g.sql);
  }, "actual_real_refused");
});
test("exact signed64 transport independently rejects malformed numeric/tag/encoding authority", async t => {
  for (const [label, mutate, category] of [
    ["Number integer", r => { r.c1_value = 7; }, "invalid_integer_wire"],
    ["positive overflow", r => { r.c1_value = "9223372036854775808"; }, "integer_range"],
    ["negative overflow", r => { r.c1_value = "-9223372036854775809"; }, "integer_range"],
    ["leading zero", r => { r.c1_value = "01"; }, "invalid_integer_wire"],
    ["negative zero", r => { r.c1_value = "-0"; }, "invalid_integer_wire"],
    ["decimal", r => { r.c1_value = "1.0"; }, "invalid_integer_wire"],
    ["exponent", r => { r.c1_value = "1e0"; }, "invalid_integer_wire"],
    ["trailing newline decimal", r => { r.c1_value = "1\n"; }, "invalid_integer_wire"],
    ["unknown tag", r => { r.c1_type = "unknown"; }, "invalid_typed_wire"],
    ["REAL tag", r => { r.c1_type = "real"; }, "actual_real_refused"],
    ["bad UTF8", r => { r.c2_value = "FF"; }, "invalid_utf8"],
    ["lowercase hex", r => { r.c2_value = "c3a9"; }, "invalid_typed_wire"],
    ["numeric rowid", r => { r.row_identity = 1; }, "invalid_integer_wire"],
  ]) await t.test(label, () => refuses(f => { f.hooks.query = (rows, sql) => { if (sql.includes('FROM main."payload" ORDER BY') && rows.length) mutate(rows[0]); return rows; }; }, category));
});
test("row identities, duplicates, counts and generated-column pages retain full coverage", async t => {
  await t.test("duplicate rowid", () => refuses(f => { f.hooks.query = (r, sql) => { if (sql.includes('FROM main."payload" ORDER BY') && r.length > 1) r[1].row_identity = r[0].row_identity; return r; }; }, "row_identity_order"));
  await t.test("rowid ordering", () => refuses(f => { f.hooks.query = (r, sql) => sql.includes('FROM main."payload" ORDER BY') ? r.reverse() : r; }, "row_identity_order"));
  await t.test("duplicate composite key", () => refuses(f => { f.hooks.query = (r, sql) => { if (sql.includes('FROM main."composite" ORDER BY') && r.length > 1) { r[1].c0_value = r[0].c0_value; r[1].c1_value = r[0].c1_value; } return r; }; }, "key_identity_order"));
  await t.test("NULL composite key", () => refuses(f => { f.hooks.query = (r, sql) => { if (sql.includes('FROM main."composite" ORDER BY') && r.length) { r[0].c0_type = "null"; r[0].c0_value = null; } return r; }; }, "null_primary_key"));
  await t.test("omitted generated cell", () => refuses(f => { f.hooks.query = (r, sql) => { if (sql.includes('FROM main."payload" ORDER BY') && r.length) delete r[0].c3_value; return r; }; }, "invalid_shape"));
  await t.test("false count", () => refuses(f => { f.hooks.query = (r, sql) => sql.startsWith("SELECT CAST(count(*)") ? [{ row_count: "0" }] : r; }, "incomplete_table_page"));
  await t.test("numeric count", () => refuses(f => { f.hooks.query = (r, sql) => sql.startsWith("SELECT CAST(count(*)") ? [{ row_count: 1 }] : r; }, "invalid_integer_wire"));
});
test("KV exact types/identity and alarm state/order are included with whole-capture refusal", async t => {
  await t.test("omitted alarm ordering key", () => refuses(f => { f.stores[0].kv.delete("pmb1:alarm-sequence"); }, "missing_alarm_order"));
  await t.test("omitted exposed alarm", () => refuses(f => { f.hooks.alarm = () => undefined; }, "unsupported_alarm"));
  await t.test("scheduled alarm silently absent conflicts with dispatch", () => refuses(f => { f.hooks.alarm = () => null; }, "alarm_order_identity"));
  await t.test("alarm drift", () => refuses(f => { let n = 0; f.hooks.alarm = a => ++n === 1 ? a : a + 1; }, "alarm_drift"));
  await t.test("dispatch omitted", () => refuses(f => { f.stores[0].kv.set("pmb1:alarm-invocation", null); }, "alarm_order_identity"));
  await t.test("generation drift", () => refuses(f => { f.stores[0].kv.get("pmb1:alarm-invocation").generation = "20"; }, "alarm_order_identity"));
  await t.test("sequence malformed", () => refuses(f => { f.stores[0].kv.set("pmb1:alarm-sequence", "01"); }, "invalid_integer_wire"));
  await t.test("duplicate KV", () => refuses(f => { f.hooks.kv = p => p.entries.length ? { entries: [p.entries[0],p.entries[0]], next: p.entries[0][0] } : p; }, "kv_order"));
  await t.test("KV order", () => refuses(f => { f.hooks.kv = p => ({ ...p, entries: p.entries.reverse() }); }, "kv_order"));
  for (const [label, value] of [["Date", new Date()], ["undefined", undefined], ["NaN", NaN], ["infinity", Infinity], ["oversized bigint", 1n << 64n], ["surrogate", "\ud800"]])
    await t.test(label, () => refuses(f => { f.stores[0].kv.set("unsupported", value); }));
  for (const [label, make] of [
    ["cycle", () => { const v = {}; v.self = v; return v; }],
    ["shared object reference", () => { const v = {}; return [v,v]; }],
    ["shared byte view reference", () => { const v = new Uint8Array([0]); return [v,v]; }],
    ["getter", () => Object.defineProperty({}, "value", { enumerable: true, get() { throw Error("must not invoke"); } })],
    ["array getter", () => Object.defineProperty([1], "0", { enumerable: true, configurable: true, get() { throw Error("must not invoke"); } })],
    ["symbol", () => ({ [Symbol("hidden")]: 1 })],
    ["sparse array", () => new Array(3)],
    ["descriptor", () => Object.freeze({ value: "frozen" })],
    ["partial byte view", () => new Uint8Array(new ArrayBuffer(8), 2, 2)],
    ["depth", () => { let v = "leaf"; for (let i = 0; i < 18; i++) v = [v]; return v; }],
  ]) await t.test(label, () => refuses(f => { f.stores[0].kv.set("unsupported", make()); }));
  await t.test("ordinary omitted KV changes independently expected complete state", async () => {
    const baseline = await run(), changed = await run(f => { f.stores[0].kv.delete("__cf_kv:exposed"); });
    assert.notDeepEqual(changed.objects[0].kv, baseline.objects[0].kv);
  });
  await t.test("alarm time changes complete state", async () => {
    const baseline = await run(), changed = await run(f => { f.stores[0].alarm++; });
    assert.notDeepEqual(changed.objects[0].alarm, baseline.objects[0].alarm);
  });
  await t.test("property insertion order remains exact", async () => {
    const baseline = await run(), changed = await run(f => { f.stores[0].kv.set("pmb1:alarm-invocation", { generation: "19", id: "dispatch-7", alarmGeneration: "9007199254740993" }); });
    assert.notDeepEqual(changed.objects[0].kv, baseline.objects[0].kv);
  });
});
test("finite aggregate object/SQL/KV/byte/call limits refuse", async t => {
  for (const [key, value] of [["objects", 1], ["schema", 30], ["tables", 7], ["columns", 15], ["rows", 20], ["kv", 15], ["bytes", 1000], ["calls", 15]])
    await t.test(key, () => refuses(f => { f.request.limits[key] = value; }));
  await t.test("elapsed read timeout", () => refuses(f => { f.request.limits.milliseconds = 20; f.hooks.query = () => new Promise(() => {}); }, "elapsed_bound"));
  await t.test("deadline includes final artifact encoding after the last adapter call", async () => {
    const original = Object.getOwnPropertyDescriptor(performance, "now"), clock = performance.now.bind(performance);
    let finalClosure = false, afterFinalCalls = 0;
    Object.defineProperty(performance, "now", { configurable: true, value: () => finalClosure && ++afterFinalCalls >= 2 ? clock() + 600001 : clock() });
    try {
      await refuses(f => { let closures = 0; f.hooks.closure = c => { if (++closures === 2) finalClosure = true; return c; }; }, "elapsed_bound");
      assert.equal(afterFinalCalls, 2);
    } finally { if (original) Object.defineProperty(performance, "now", original); else delete performance.now; }
  });
  await t.test("structured KV aggregate nodes", () => refuses(f => { f.stores[0].kv.set("wide", Array.from({ length: 3201 }, () => null)); }, "aggregate_kv_node_bound"));
});
test("source binding, writer/custody/fence/common interval and adapter faults fail closed", async t => {
  await t.test("source bytes mismatch", () => refuses(f => { f.request.sourceBytes["reader.ts"][0] ^= 1; }, "source_binding"));
  await t.test("wrong profile", () => refuses(f => { f.request.profile = "old-profile"; }, "explicit_profile_required"));
  await t.test("writer omitted", () => refuses(f => { f.request.expectedWriterIds.push("unknown-writer"); }, "writer_population"));
  await t.test("unsettled writer", () => refuses(f => { f.request.closure.writers[0].disposition = "running"; }, "writer_unsettled"));
  await t.test("custody mismatch", () => refuses(f => { f.hooks.fence = v => ({ ...v, custody: "other" }); }, "fence_or_interval_drift"));
  await t.test("generation drift", () => refuses(f => { f.hooks.fence = v => ({ ...v, generation: "20" }); }, "fence_or_interval_drift"));
  await t.test("common interval violated", () => refuses(f => { f.hooks.fence = v => ({ ...v, observedAt: "901" }); }, "fence_or_interval_drift"));
  await t.test("observation order", () => refuses(f => { f.hooks.fence = v => ({ ...v, observedAt: v.observedAt === "200" ? "800" : "200" }); }, "observation_order"));
  await t.test("closure drift", () => refuses(f => { let n = 0; f.hooks.closure = c => ++n === 1 ? c : { ...c, interval: "changed" }; }, "closure_drift"));
  await t.test("SQL fault sanitized", () => refuses(f => { f.hooks.query = () => { throw Error("secret state"); }; }, "source_read_failed"));
  await t.test("encoding witness", () => refuses(f => { f.hooks.query = (r, sql) => sql.includes("AS encoding_probe") ? [{ encoding_probe: "4100" }] : r; }, "unsupported_database_encoding"));
  await t.test("metadata changes on recheck", () => refuses(f => { let n = 0; f.hooks.query = (r, sql) => sql.includes("FROM main.sqlite_schema") && ++n === 2 ? r.slice(1) : r; }, "census_drift"));
  await t.test("read callback skipped", () => refuses(f => { f.adapter.readObject = async () => ({}); }, "invalid_read_session_result"));
});
