// MIT License; copyright 2026 Terry Ott. No actual records or qualification.
import test from 'node:test';
import assert from 'node:assert/strict';
import { setupTrustedFixture } from './trusted_inputs_fixture.mjs';
import { AssembledTrustedInputs, assertAssembledTrustedInputs } from './trusted_inputs.ts';
import { createNativeSource } from '../pmb1-native-object-reader/native-source.ts';
import { captureSupportedBoundary } from '../pmb1-native-object-reader/object-kv-interface.ts';
import { assertNoOutbound } from '../pmb1-native-disposition/fixture.mjs';

test('source-local reviewed inputs assemble concrete coverage and full native source without acquisition', async () => {
  const f = setupTrustedFixture(); try {
    const trusted = await f.assemble(); assertAssembledTrustedInputs(trusted, f.config);
    assert.equal(trusted.coverage.records().observed.reviewer, 'independent-reviewer');
    assert.deepEqual(f.native.counts(), { sqlCalls: 0, acquisitions: 0, reservations: 0, completions: 0 });
    const source = trusted.source(), native = await createNativeSource(source, f.native.bindings, f.native.control);
    const captured = await captureSupportedBoundary(native, source.request);
    assert.equal(captured.objects.length, 1); assert.equal(captured.actualQualification, false);
    assert.equal(f.native.counts().acquisitions, 1);
  } finally { f.close(); }
});

test('retained inputs and delivered copies cannot mutate trusted construction', async () => {
  const f = setupTrustedFixture(); try {
    const trusted = await f.assemble(), before = trusted.source();
    f.expected.binding.candidate = 'f'.repeat(64);
    f.authenticated.reviewer = 'substituted'; f.native.input.control.id = '0'.repeat(64);
    const delivered = trusted.source(); delivered.request.sourceBytes['native.ts'][0] ^= 1;
    delivered.request.expectedObjects[0].id = '0'.repeat(64);
    assert.deepEqual(trusted.source(), before); assertAssembledTrustedInputs(trusted, f.config);
    assert.equal(trusted.coverage.records().observed.reviewer, 'independent-reviewer');
    assert.throws(() => { trusted.coverage = undefined; });
  } finally { f.close(); }
});

test('plain objects, prototype spoofs, structured copies and substituted exact configuration refuse', async () => {
  const f = setupTrustedFixture(); try {
    const trusted = await f.assemble();
    for (const forged of [{ coverage: trusted.coverage, source: trusted.source },
      Object.create(AssembledTrustedInputs.prototype), structuredClone(trusted), new Proxy(trusted, {})])
      assert.throws(() => assertAssembledTrustedInputs(forged, f.config));
    assert.throws(() => new AssembledTrustedInputs(Symbol('forged'), trusted.coverage, trusted.source()));
    for (const change of [c => { c.binding.candidate = '1'.repeat(64); },
      c => { c.binding.lifecycle = 'other'; }, c => { c.binding.generation = '2'; },
      c => { c.domainDatabaseId = c.journalDatabaseId; }]) {
      const config = structuredClone(f.config); change(config);
      assert.throws(() => assertAssembledTrustedInputs(trusted, config));
    }
  } finally { f.close(); }
});

test('coverage/source population, all object writers, private control exclusion and custody reconcile', async () => {
  for (const change of [f => { f.expected.resources = f.expected.resources.filter(r => r.kind !== 'object');
      f.authenticated.custody = f.authenticated.custody.filter(c => !c.resource.includes('/')); },
    f => { f.native.input.request.expectedWriterIds = ['unreviewed-writer']; },
    f => { f.expected.resources.push({ id: f.native.input.control.namespace + '/' + f.native.input.control.id, kind: 'object' }); },
    f => { f.authenticated.custody[0].fromMs += 1; },
    f => { f.native.input.expectedPopulation.objects[f.native.id.namespace][0].hasStoredData = false; },
    f => { f.native.input.request.sourceBytes['native-owner.ts'][0] ^= 1; },
    f => { f.native.input.packets[0].packet.approvedReads[0] = 'SELECT substituted'; }]) {
    const f = setupTrustedFixture(); try {
      change(f); await assert.rejects(f.assemble()); assert.equal(f.native.counts().acquisitions, 0);
    } finally { f.close(); }
  }
});

test('absolute stale/future custody and restart reconstruction retain refusal without native calls', async () => {
  const f = setupTrustedFixture(), clock = Date.now;
  try {
    const trusted = await f.assemble();
    Date.now = () => Number(f.native.input.request.closure.end);
    assert.throws(() => assertAssembledTrustedInputs(trusted, f.config));
    assert.throws(() => trusted.source());
    await assert.rejects(f.assemble());
    Date.now = () => Number(f.native.input.request.closure.start) - 1;
    await assert.rejects(f.assemble());
    assert.equal(f.native.counts().acquisitions, 0);
  } finally { Date.now = clock; f.close(); }
});

test('assembled source is still a single attempt and never retries unknown acquisition', async () => {
  const f = setupTrustedFixture(); try {
    const trusted = await f.assemble(), input = trusted.source();
    let calls = 0;
    const bindings = { [f.native.id.namespace]: { idFromString: id => id, get: () => ({
      acquire: async () => { calls++; throw Error('unknown_native_result'); } }) } };
    const source = await createNativeSource(input, bindings, f.native.control);
    await assert.rejects(captureSupportedBoundary(source, input.request));
    await assert.rejects(captureSupportedBoundary(source, input.request));
    assert.equal(calls, 1);
  } finally { f.close(); }
});

test.after(() => assertNoOutbound());
