// Synthetic native API model, not an emulator or managed-runtime assertion.
import assert from 'node:assert/strict';
import test from 'node:test';
import { DatabaseSync } from 'node:sqlite';
import { readLocal, NativeReadRefused } from './native.ts';

const bounds = { calls: 100, rows: 100, bytes: 4 * 1024 * 1024, milliseconds: 1000, kvAcquisitionBytes: 2 * 1024 * 1024 };
const custody = { generation: '9223372036854775807', writerEpoch: 'synthetic-epoch', custody: 'synthetic-custody', interval: 'synthetic-interval' };
const exact = 'SELECT CAST(rowid AS TEXT) identity,CAST(value AS TEXT) value,hex(payload) payload FROM facts ORDER BY rowid';
function fixture() {
  const db = new DatabaseSync(':memory:');
  db.exec(`CREATE TABLE maintenance_control(singleton_id INTEGER PRIMARY KEY,generation INTEGER,state TEXT);
    INSERT INTO maintenance_control VALUES(1,9223372036854775807,'closed');
    CREATE TABLE facts(value INTEGER,payload BLOB);
    INSERT INTO facts(rowid,value,payload) VALUES(-9223372036854775808,9223372036854775807,x'00ff'),(9223372036854775807,-9223372036854775808,x'80');`);
  const kv = new Map([['a', { data: new Uint8Array([0, 255]), exact: 9223372036854775807n }]]);
  let kvCalls = 0, alarm = null;
  const calls = [];
  const storage = {
    sql: { exec(sql) {
      calls.push(sql);
      if (/__cf_kv/i.test(sql)) throw new Error('synthetic native private table');
      const statement = db.prepare(sql);
      return {
        columnNames: statement.columns().map(c => c.name),
        one() { const rows = statement.all(); assert.equal(rows.length, 1); return { ...rows[0] }; },
        *[Symbol.iterator]() { for (const row of statement.iterate()) yield { ...row }; },
      };
    } },
    async transaction(fn) {
      db.exec('BEGIN');
      try { return await fn({
        async list(options) {
          kvCalls++;
          assert.equal(options.limit, 1);
          return new Map([...kv].filter(([key]) => !options.startAfter || key > options.startAfter).slice(0, options.limit));
        },
        async getAlarm() { return alarm; },
      }); } finally { db.exec('ROLLBACK'); }
    },
  };
  return { db, storage, calls, kv, kvCalls: () => kvCalls, setAlarm: x => { alarm = x; }, close: () => db.close() };
}
async function withFixture(run) { const f = fixture(); try { return await run(f); } finally { f.close(); } }
const refuses = (p, reason) => assert.rejects(p, e => e instanceof NativeReadRefused && e.message === reason);

test('exact signed64/rowids/binary and actual local fence match independent literal oracle', () => withFixture(async f => {
  const out = await readLocal(f.storage, [exact], custody, bounds, async session => ({ rows: await session.query(exact), fence: await session.fence() }));
  // Separately retained literals; neither native SQL projections nor decoder
  // create the expected signed64 identities or source values.
  assert.deepEqual(out.rows, [
    { identity: '-9223372036854775808', value: '9223372036854775807', payload: '00FF' },
    { identity: '9223372036854775807', value: '-9223372036854775808', payload: '80' },
  ]);
  assert.equal(out.fence.generation, custody.generation);
  assert.equal(out.fence.state, 'closed');
  assert.equal(out.fence.custody, custody.custody);
}));

test('typed native KV retained without JSON coercion; one bounded item only', () => withFixture(async f => {
  const out = await readLocal(f.storage, [], custody, bounds, s => s.listKV(null, 256));
  assert.deepEqual(out, { entries: [['a', { data: new Uint8Array([0, 255]), exact: 9223372036854775807n }]], next: 'a' });
  assert.equal(f.kvCalls(), 1);
}));

test('reserve insufficient for unknown next KV item refuses before acquisition', () => withFixture(async f => {
  await refuses(readLocal(f.storage, [], custody, { ...bounds, bytes: 1024 }, s => s.listKV(null, 2)), 'native_acquisition_byte_bound');
  assert.equal(f.kvCalls(), 0);
}));

test('large SQL response refuses before original cursor materialization', () => withFixture(async f => {
  const sql = 'SELECT hex(zeroblob(10000)) value';
  await refuses(readLocal(f.storage, [sql], custody, { ...bounds, bytes: 100 }, s => s.query(sql)), 'native_response_bound');
  assert.ok(!f.calls.includes(sql));
}));

test('native hidden SQL table refuses without a substitute or SQL attempt', () => withFixture(async f => {
  const sql = 'SELECT CAST(count(*) AS TEXT) n FROM main."__cf_kv"';
  await refuses(readLocal(f.storage, [sql], custody, bounds, s => s.query(sql)), 'native_internal_sql_unavailable');
  assert.equal(f.calls.length, 0);
}));

test('unlisted SQL and lossy Number projections refuse', () => withFixture(async f => {
  await refuses(readLocal(f.storage, [exact], custody, bounds, s => s.query('DELETE FROM facts')), 'unapproved_native_sql');
  const sql = 'SELECT value FROM facts';
  await refuses(readLocal(f.storage, [sql], custody, bounds, s => s.query(sql)), 'native_read_unknown');
  // node:sqlite refuses the lossy native Number projection itself. An adapter
  // returning it as Number is separately refused by native_lossy_number.
  const original = f.storage.sql.exec;
  f.storage.sql.exec = sql => sql === 'SELECT 9007199254740993 value'
    ? [{ value: Number(9007199254740993n) }] : original(sql);
  const unsafe = 'SELECT 9007199254740993 value';
  await refuses(readLocal(f.storage, [unsafe], custody, bounds, s => s.query(unsafe)), 'native_lossy_number');
}));

test('local fence detects open state and duplicate control population', () => withFixture(async f => {
  f.db.exec("UPDATE maintenance_control SET state='open'");
  await refuses(readLocal(f.storage, [], custody, bounds, s => s.fence()), 'native_fence_drift');
  f.db.exec("UPDATE maintenance_control SET state='closed'; INSERT INTO maintenance_control VALUES(2,1,'closed')");
  await refuses(readLocal(f.storage, [], custody, bounds, s => s.fence()), 'native_fence_population');
}));

test('expired callback cannot keep using read session and native transaction cannot rerun consumer', () => withFixture(async f => {
  let saved;
  await readLocal(f.storage, [exact], custody, bounds, async session => { saved = session; });
  await refuses(saved.query(exact), 'native_session_expired');
  const transact = f.storage.transaction;
  f.storage.transaction = async fn => { await transact(fn); return transact(fn); };
  let count = 0;
  await refuses(readLocal(f.storage, [], custody, bounds, async () => { count++; }), 'native_transaction_reentered');
  assert.equal(count, 1);
}));

test('hung transaction/unknown outcome stops once and retained session expires', async () => {
  let calls = 0;
  const storage = { sql: {}, transaction: () => { calls++; return new Promise(() => {}); } };
  await refuses(readLocal(storage, [], custody, { ...bounds, milliseconds: 10 }, async () => {}), 'native_elapsed_bound');
  assert.equal(calls, 1);
});

test('null native alarm reports scheduled state only, without adding marker identity', () => withFixture(async f => {
  assert.equal(await readLocal(f.storage, [], custody, bounds, s => s.getAlarm()), null);
  f.setAlarm(1700000000000);
  assert.equal(await readLocal(f.storage, [], custody, bounds, s => s.getAlarm()), 1700000000000);
}));

test('delayed native transaction cannot invoke consumer after timeout', async () => {
  let enter;
  const storage = { sql: {}, transaction(fn) {
    return new Promise((resolve, reject) => { enter = () => fn({}).then(resolve, reject); });
  } };
  let consumerCalls = 0;
  await refuses(readLocal(storage, [], custody, { ...bounds, milliseconds: 5 }, async () => { consumerCalls++; }), 'native_elapsed_bound');
  await enter();
  assert.equal(consumerCalls, 0);
});

test('completed small KV reads replace in-flight reserve with retained facts and admit terminal page', () => withFixture(async f => {
  const out = await readLocal(f.storage, [], custody, bounds, async session => {
    const first = await session.listKV(null, 2), terminal = await session.listKV(first.next, 2);
    return { first, terminal };
  });
  assert.equal(out.first.entries.length, 1); assert.deepEqual(out.terminal, { entries: [], next: null });
  assert.equal(f.kvCalls(), 2);
}));

test('large retained typed binary prevents the next worst-case acquisition before dispatch', () => withFixture(async f => {
  f.kv.set('a', new Uint8Array(1500000));
  await refuses(readLocal(f.storage, [], custody, bounds, async session => {
    const first = await session.listKV(null, 1); return session.listKV(first.next, 1);
  }), 'native_acquisition_byte_bound');
  assert.equal(f.kvCalls(), 1);
}));

test('unsupported native KV representation poisons the session even if consumer catches refusal', () => withFixture(async f => {
  f.kv.set('a', new Date(0));
  await refuses(readLocal(f.storage, [], custody, bounds, async session => {
    try { await session.listKV(null, 1); } catch {}
    return 'cannot suppress failed acquisition';
  }), 'native_kv_value');
  let getterCalls = 0;
  const accessor = {};
  Object.defineProperty(accessor, 'private', { enumerable: true, configurable: true, get() { getterCalls++; return 'must not run'; } });
  f.kv.set('a', accessor);
  await refuses(readLocal(f.storage, [], custody, bounds, session => session.listKV(null, 1)), 'native_kv_value');
  assert.equal(getterCalls, 0);
}));

test('binary own and backing-buffer accessors refuse without invocation and poison the session', () => withFixture(async f => {
  for (const [value, property] of [
    [new Uint8Array([1]), 'byteLength'], [new Uint8Array([1]), 'buffer'],
    [new Uint8Array([1]), 'byteOffset'], [new Uint8Array([1]), 'length'],
    [new ArrayBuffer(1), 'byteLength'], [new ArrayBuffer(1), 'resizable'],
  ]) {
    let getterCalls = 0;
    Object.defineProperty(value, property, { configurable: true, get() { getterCalls++; return 1; } });
    f.kv.set('a', value);
    await refuses(readLocal(f.storage, [], custody, bounds, async session => {
      try { await session.listKV(null, 1); } catch {}
      return 'cannot suppress unsupported binary';
    }), 'native_kv_value');
    assert.equal(getterCalls, 0, property);
  }
  for (const property of ['resizable', 'byteLength']) {
    const backing = new ArrayBuffer(1);
    let getterCalls = 0;
    Object.defineProperty(backing, property, { configurable: true, get() { getterCalls++; return false; } });
    f.kv.set('a', new Uint8Array(backing));
    await refuses(readLocal(f.storage, [], custody, bounds, async session => {
      try { await session.listKV(null, 1); } catch {}
      return 'cannot suppress unsupported backing buffer';
    }), 'native_kv_value');
    assert.equal(getterCalls, 0, property);
  }
}));

test('ordinary Uint8Array and ArrayBuffer exact values remain admitted', () => withFixture(async f => {
  for (const value of [new Uint8Array([0, 255, 128]), new Uint8Array([0, 255, 128]).buffer]) {
    f.kv.set('a', value);
    const page = await readLocal(f.storage, [], custody, bounds, session => session.listKV(null, 1));
    assert.equal(page.entries[0][1], value);
    const actual = value instanceof ArrayBuffer ? new Uint8Array(page.entries[0][1]) : page.entries[0][1];
    assert.deepEqual(actual, new Uint8Array([0, 255, 128]));
  }
}));
