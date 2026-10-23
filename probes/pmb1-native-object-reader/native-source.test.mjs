// Source/synthetic tests only. Literal expected facts are independent of storage.
import test from 'node:test';
import assert from 'node:assert/strict';
import { DatabaseSync } from 'node:sqlite';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { createNativeSource, acquireNativeFacts, NativeSourceRefused } from './native-source.ts';
import { captureSupportedBoundary, BOUNDARY, REVISION } from './object-kv-interface.ts';
import { PROFILE, canonical, schemaSQL, storageSQL, columnsSQL, ENCODING_SQL } from '../pmb1-no-real-object-reader/reader.ts';

const hash = value => createHash('sha256').update(value).digest('hex');
const pin = value => hash(Buffer.from(canonical(value)));
const fixture = JSON.parse(readFileSync(new URL('./expected-observable.json', import.meta.url)));
const sourceBytes = Object.fromEntries(['native-source.ts', 'native-owner.ts', 'native-control.ts', 'native.ts', 'object-kv-interface.ts'].map(name =>
  [name, new Uint8Array(readFileSync(new URL(name, import.meta.url)))]));
sourceBytes['reader.ts'] = new Uint8Array(readFileSync(new URL('../pmb1-no-real-object-reader/reader.ts', import.meta.url)));
sourceBytes['ADR0066.md'] = new Uint8Array(readFileSync('C:/Projects/FGA/architecture-design/docs/decisions/0066-scope-prospective-object-preservation-to-supported-state.md'));
const sourcePins = Object.fromEntries(Object.entries(sourceBytes).map(([name, bytes]) => [name, hash(bytes)]));
const id = { namespace: 'b'.repeat(32), id: 'c'.repeat(64) }, objectKey = canonical([id.namespace, id.id]);
const limits = { objects: 2, schema: 128, tables: 16, columns: 64, rows: 100, kv: 100, bytes: 4194304,
  calls: 1000, page: 2, milliseconds: 30000 };
function approvedReads() {
  const reads = [schemaSQL(limits.schema), storageSQL(limits.schema), ENCODING_SQL, columnsSQL('__cf_kv', limits.columns)];
  const quote = name => '"' + name.replaceAll('"', '""') + '"';
  // Counts are retained fixture literals, never inferred from observed storage.
  for (const [table, count] of Object.entries({ facts: 2, maintenance_control: 1 })) {
    const columns = fixture.application.columns[table].map(row => row.name);
    reads.push(columnsSQL(table, limits.columns));
    reads.push('SELECT ' + [...columns, 'rowid'].map(column => 'typeof(' + quote(column) + ')').join(',') + ' FROM main.' + quote(table) + ' LIMIT 0');
    reads.push('SELECT CAST(count(*) AS TEXT) AS row_count FROM main.' + quote(table));
    const expressions = ['CAST("rowid" AS TEXT) AS row_identity'];
    columns.forEach((column, i) => { const c = quote(column); expressions.push(`typeof(${c}) AS c${i}_type`, `CASE typeof(${c}) WHEN 'integer' THEN CAST(${c} AS TEXT) WHEN 'text' THEN hex(CAST(${c} AS BLOB)) WHEN 'blob' THEN hex(${c}) ELSE NULL END AS c${i}_value`); });
    for (let offset = 0; offset <= count;) {
      const n = Math.min(limits.page, count - offset);
      reads.push('SELECT ' + expressions.join(',') + ' FROM main.' + quote(table) + ' ORDER BY "rowid"' + ` LIMIT ${n === 0 ? 1 : limits.page} OFFSET ${offset}`);
      if (n === 0) break; offset += n;
    }
  }
  return reads;
}
function setup() {
  const db = new DatabaseSync(':memory:'); db.exec(fixture.appDDL); db.exec(fixture.automaticDDL);
  for (const guard of fixture.application.guards) db.exec(guard.sql);
  db.exec("INSERT INTO facts(rowid,value,payload,note) VALUES(-9223372036854775808,9223372036854775807,x'00ff','first'),(9223372036854775807,-9223372036854775808,x'80','second')");
  db.exec("INSERT INTO maintenance_control VALUES(1,9223372036854775807,'closed')");
  const kv = new Map([['binary', new Uint8Array([0, 255])], ['exact', 9223372036854775807n], ['pmb1:wake-admission-sequence', '0']]);
  let sqlCalls = 0, nativeCalls = 0, rawHidden = 0;
  const storage = { sql: { exec(sql) {
    sqlCalls++; if (/FROM main\."__cf_kv"/i.test(sql)) { rawHidden++; throw Error('hidden'); }
    const statement = db.prepare(sql);
    return { columnNames: statement.columns().map(c => c.name), one() { return { ...statement.get() }; },
      *[Symbol.iterator]() { for (const row of statement.iterate()) yield { ...row }; } };
  } }, async transaction(fn) { nativeCalls++; db.exec('BEGIN'); try {
    return await fn({ async getAlarm() { return null; }, async list(options) {
      return new Map([...kv].sort(([a], [b]) => Buffer.compare(Buffer.from(a), Buffer.from(b)))
        .filter(([key]) => !options.startAfter || Buffer.compare(Buffer.from(key), Buffer.from(options.startAfter)) > 0).slice(0, options.limit));
    } });
  } finally { db.exec('ROLLBACK'); } } };
  const now = Date.now(), closure = { interval: 'synthetic-closed', start: String(now - 1000), end: String(now + 30000),
    custody: 'independent-synthetic', writers: [{ id: 'application', epoch: 'synthetic-epoch', disposition: 'settled' }] };
  const binding = { generation: '9223372036854775807', state: 'closed', writerEpoch: 'synthetic-epoch', custody: closure.custody, interval: closure.interval };
  const manifest = { boundary: BOUNDARY, revision: REVISION, profile: PROFILE, object: id,
    automatic: { name: '__cf_kv', origin: 'provider-automatic-sqlite-kv', applicationDependsOnRaw: false },
    observable: fixture.observable, application: fixture.application, sourcePins };
  const request = { boundary: BOUNDARY, profile: PROFILE, expectedObjects: [{ ...id, manifest,
    manifestSha2_256: pin(manifest), alarmKeys: { invocation: 'pmb1:unused', sequence: 'pmb1:wake-admission-sequence' } }],
    closure, expectedWriterIds: ['application'], expectedSources: sourcePins, sourceBytes, fences: { [objectKey]: binding }, limits };
  const { sourceBytes: _sourceBytes, ...wireRequest } = request;
  const packet = { schema: 'pmb1-private-native-owner-packet-v1', approvedReads: approvedReads(), maximumEvents: 128,
    request: wireRequest, sourceHex: Object.fromEntries(Object.entries(sourceBytes).map(([name, value]) => [name, Buffer.from(value).toString('hex')])) };
  const population = { accountId: 'a'.repeat(32), accountNamespaces: [{ id: id.namespace, class: 'NativeCaptureOwner', name: 'synthetic', script: 'synthetic', use_sqlite: true },
    {id:'e'.repeat(32),class:'NativeCaptureControl',name:'external-control',script:'synthetic',use_sqlite:true}],
    objects: { [id.namespace]: [{ id: id.id, hasStoredData: true }] } };
  const census = { schema: 'pmb1-native-census-observation-v1', completeSnapshot: false, actualQualification: false, ...population, calls: 2, bytes: 1024 };
  const input = structuredClone({ control: {namespace:'e'.repeat(32),id:'f'.repeat(64),packetSha2_256:'2'.repeat(64)},request, expectedPopulation: population, expectedPopulationSha2_256: pin(population),
    inventoryProvenanceSha2_256: '1'.repeat(64), census, censusSha2_256: pin(census), packets: [{ packet, sha2_256: pin(packet) }] });
  let resolutions = 0, acquisitions = 0, carrierHook = x => x, reserved=false, completed=false;
  const control = {idFromString(value){assert.equal(value,input.control.id);return value;},get(){return {
    async reserve(controlHash,namespace,objectId,packetHash){assert.equal(reserved,false);reserved=true;
      return {controlSha2_256:controlHash,namespace,id:objectId,packetSha2_256:packetHash};},
    async complete(){assert.equal(reserved,true);assert.equal(completed,false);completed=true;},
  };}};
  const bindings = { [id.namespace]: { idFromString(value) { resolutions++; assert.equal(value, id.id); return value; },
    get() { return { async acquire(expected) { acquisitions++; assert.equal(expected, input.packets[0].sha2_256);
      const carrier = await acquireNativeFacts(storage, id.namespace, id.id, input.packets[0].packet, expected); return carrierHook(carrier); } }; } } };
  return { db, input, bindings, control, kv, storage, counts: () => ({ sqlCalls, nativeCalls, rawHidden, resolutions, acquisitions }),
    hook(fn) { carrierHook = fn; }, repin() { input.packets[0].sha2_256 = pin(input.packets[0].packet); }, close() { db.close(); } };
}
async function run(edit = () => {}) { const f = setup(); try { await edit(f); const source = await createNativeSource(f.input, f.bindings,f.control);
  return { result: await captureSupportedBoundary(source, f.input.request), counts: f.counts() }; } finally { f.close(); } }

test('complete factory composes reconciled population, native storage acquisition and unchanged successor with exact independently retained facts', async () => {
  const { result, counts } = await run();
  assert.equal(result.objects.length, 1); assert.equal(result.actualQualification, false);
  assert.deepEqual(result.objects[0].tables.facts.rows, [
    { identity: '-9223372036854775808', cells: [['integer', '9223372036854775807'], ['blob', '00ff'], ['text', 'first']] },
    { identity: '9223372036854775807', cells: [['integer', '-9223372036854775808'], ['blob', '80'], ['text', 'second']] },
  ]);
  assert.deepEqual(result.objects[0].kv, [['binary', ['uint8array', '00ff']], ['exact', ['bigint', '9223372036854775807']], ['pmb1:wake-admission-sequence', ['text', '0']]]);
  assert.deepEqual(result.objects[0].observable, { before: fixture.observable, after: fixture.observable });
  assert.equal(counts.acquisitions, 1); assert.equal(counts.nativeCalls, 1); assert.equal(counts.rawHidden, 0);
});
test('hasStoredData=false remains an included object and is never silently skipped',async()=>{
  const {result,counts}=await run(f=>{
    f.input.expectedPopulation.objects[id.namespace][0].hasStoredData=false;
    f.input.census.objects[id.namespace][0].hasStoredData=false;
    f.input.expectedPopulationSha2_256=pin(f.input.expectedPopulation);f.input.censusSha2_256=pin(f.input.census);
  });
  assert.equal(result.objects.length,1);assert.equal(counts.acquisitions,1);
});
test('independent inventory/source/manifest/packet mismatches refuse before native object resolution', async () => {
  const edits = [f => { f.input.inventoryProvenanceSha2_256 = ''; },
    f => { f.input.expectedPopulation.objects[id.namespace][0].hasStoredData = false; f.input.expectedPopulationSha2_256 = pin(f.input.expectedPopulation); },
    f => { f.input.request.sourceBytes['native-source.ts'][0] ^= 1; },
    f => { f.input.packets[0].packet.request.expectedObjects[0].manifest.object.id = 'd'.repeat(64); f.repin(); },
    f => { f.input.packets[0].sha2_256 = '0'.repeat(64); },
    f => { f.input.packets[0].packet.approvedReads = ['DELETE FROM facts']; f.repin(); }];
  for (const edit of edits) { const f = setup(); try { edit(f); await assert.rejects(createNativeSource(f.input, f.bindings,f.control));
    assert.equal(f.counts().resolutions, 0); assert.equal(f.counts().nativeCalls, 0); } finally { f.close(); } }
});
test('wrong owner object identity and missing/unknown state cannot bootstrap storage', async () => {
  const f = setup(); try {
    await assert.rejects(acquireNativeFacts(f.storage, id.namespace, 'd'.repeat(64), f.input.packets[0].packet, f.input.packets[0].sha2_256), /native_owner_identity/);
    assert.equal(f.counts().nativeCalls, 0); assert.equal(f.counts().sqlCalls, 0);
    f.db.exec('DROP TABLE facts');
    await assert.rejects(captureSupportedBoundary(await createNativeSource(f.input, f.bindings,f.control), f.input.request));
    assert.equal(f.db.prepare("SELECT count(*) n FROM sqlite_schema WHERE name='facts'").get().n, 0);
  } finally { f.close(); }
});
test('carrier substitution, query/order/truncation drift and unknown outcomes poison the attempt without replay', async () => {
  for (const hook of [x => ({ ...x, object: { ...id, id: 'd'.repeat(64) } }), x => ({ ...x, packetSha2_256: '0'.repeat(64) }),
    x => ({ ...x, events: x.events.slice(1) }), x => ({ ...x, events: x.events.slice(0, -1) }),
    x => { x.events[1].index = 9999; return x; }, () => { throw Error('unknown'); }]) {
    const f = setup(); try { f.hook(hook); const source = await createNativeSource(f.input, f.bindings,f.control);
      await assert.rejects(captureSupportedBoundary(source, f.input.request)); await assert.rejects(source.closure());
      await assert.rejects(source.readObject(id, async () => null)); assert.equal(f.counts().acquisitions, 1);
    } finally { f.close(); }
  }
});
test('terminal population page, closed session, duplicate object and caught bad session operation are enforced', async () => {
  const f = setup(); try {
    const source = await createNativeSource(f.input, f.bindings,f.control);
    await source.closure(); await source.listObjects(null, 2); await source.listObjects(objectKey, 2);
    let escaped;
    await assert.rejects(source.readObject(id, async session => { escaped = session; await assert.rejects(session.query('SELECT unplanned')); return null; }));
    await assert.rejects(escaped.getAlarm()); await assert.rejects(source.readObject(id, async () => null));
    assert.equal(f.counts().acquisitions, 1);
  } finally { f.close(); }
});
test('finite carrier allowance refuses before acquisition and full application drift remains fatal', async () => {
  const f = setup(); try { f.input.packets[0].packet.maximumEvents = 1; f.repin();
    await assert.rejects(captureSupportedBoundary(await createNativeSource(f.input, f.bindings,f.control), f.input.request));
    assert.ok(f.counts().sqlCalls < 20);
  } finally { f.close(); }
  await assert.rejects(run(f => { f.db.exec('CREATE TABLE unexpected(n INTEGER)'); }));
  await assert.rejects(run(f => { f.kv.set('pmb1:wake-admission-sequence', 'not-an-integer'); }));
});
