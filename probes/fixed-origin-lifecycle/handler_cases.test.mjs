import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { createHash } from 'node:crypto';
import vm from 'node:vm';
import { loadOfflineModule } from '../fixed-origin-isolation/offline_modules.mjs';
import { createSyntheticStore } from '../fixed-origin-isolation/offline_sqlite.mjs';
import { FAULT_CASES, JPEG_BASE64, png as originalPng } from '../fixed-origin-isolation/fault_matrix.mjs';
import { png } from '../fixed-origin-isolation/edge_png.mjs';
import { collectResponse } from '../fixed-origin-isolation/collector.mjs';
import { HANDLER_CASES, HANDLER_PATHS, BROWSER_PATHS, HANDLER_JPEG_BASE64,
  createHandlerCaseProvider, handlerCaseIdentity, initializeHandlerCaseNamespaces } from './handler_cases.mjs';

assert.equal(process.version, 'v24.22.0');
const fixture = process.env.FGA_OFFLINE_FIXTURE;
assert.ok(fixture, 'pinned private fixture required');
const hash = file => createHash('sha256').update(readFileSync(file)).digest('hex');
assert.equal(hash(join(fixture, 'candidate.mjs')), 'c1edd7e5e721119030085c9c0705de5d2f3a32b9cffc6bbed56f363df3432e36');
const manifest = JSON.parse(readFileSync(join(fixture, 'manifest.json')));
assert.equal(manifest.candidateCommit, 'b599ca828d2a645b686aca0354d6c8ee2c2a0250');
for (const [file, digest] of Object.entries(manifest.candidateSourceFiles)) assert.equal(hash(join(fixture, 'candidate', file)), digest);
const origin = 'https://flickrgroupaddr.com';
const request = path => new Request(origin + path, { headers: { Authorization: 'Bearer must-be-stripped', Cookie: 'private', 'X-FGA-Qualification-Case': 'ignored' } });
const count = Object.fromEntries(['hostIo','globalFetch','dynamicImport','syntheticSql','synthetic','memoryFetch','application','grant','pages','images','stalls','stallCompleted','cancelled','responderFailures'].map(key => [key, 0]));
const candidate = await loadOfflineModule(join(fixture, 'candidate.mjs'), count);
const db = createSyntheticStore(join(fixture, 'candidate/migrations'), count);
await initializeHandlerCaseNamespaces(db);
const provider = createHandlerCaseProvider({ candidate, syntheticDb: db, counters: count });
const receipts = [];
db.raw.exec("INSERT INTO submission_blocks(photo_id,group_id,first_reason,source_attempt_id) VALUES('protected-photo','protected-group','delivery_uncertain','protected-attempt'); INSERT INTO audit_events(event_id,action,request_correlation_id,outcome,reason) VALUES('protected-event','synthetic-probe','protected-request','succeeded','preserve');");
const history = () => JSON.stringify({ blocks: db.raw.prepare('SELECT * FROM submission_blocks').all(), audit: db.raw.prepare('SELECT * FROM audit_events').all() });
const originalHistory = history();

test('Worker graph exposes no Node dependency, process, binary helper or ambient network', async () => {
  const context = vm.createContext({ Request, Response, Headers, URL, TextEncoder, Uint8Array, DataView, crypto, atob,
    ReadableStream, AbortController, setTimeout, clearTimeout });
  const modules = new Map();
  async function load(url) {
    if (modules.has(url.href)) return modules.get(url.href);
    assert.ok(url.href.startsWith(new URL('../', import.meta.url).href));
    const source = readFileSync(url, 'utf8');
    assert.doesNotMatch(source, /\bBuffer\b|\bprocess\b|node:|from ['"].*fault_matrix|\b(?:globalThis|self)\.fetch|\bawait fetch\s*\(/);
    // Method declarations are intentional; an unbound fetch is forbidden.
    const module = new vm.SourceTextModule(source, { context, identifier: url.href });
    modules.set(url.href, module);
    await module.link(specifier => load(new URL(specifier, url)));
    return module;
  }
  const module = await load(new URL('./handler_cases.mjs', import.meta.url));
  await module.evaluate();
  assert.equal(typeof module.namespace.createHandlerCaseProvider, 'function');
  assert.deepEqual(HANDLER_CASES, FAULT_CASES);
  assert.equal(HANDLER_JPEG_BASE64, JPEG_BASE64);
  for (const size of [undefined,262144,262145]) assert.deepEqual(Buffer.from(png(size)), originalPng(size));
});

for (const [scenario, expected] of Object.entries(HANDLER_CASES)) test(`same persistent SQLite, actual pinned handler: ${scenario}`, async () => {
  const before = { ...count }, started = performance.now();
  const response = await provider.fetch(request(HANDLER_PATHS[2]), scenario);
  const copy = response.clone(), receipt = await collectResponse(response);
  assert.equal(response.status, expected);
  assert.equal(count.responderFailures, 0, 'dependency assertion/mutation errors cannot count as fault passes');
  assert.equal(receipt.accepted, true);
  const elapsedMs = Math.round(performance.now() - started);
  if (expected === 200) {
    assert.deepEqual(Buffer.from(await copy.arrayBuffer()), scenario === 'jpeg' ? Buffer.from(JPEG_BASE64, 'base64') : originalPng(scenario === 'exact-limit' ? 262144 : undefined));
    assert.equal(response.headers.get('Cache-Control'), 'private, no-store');
    assert.equal(response.headers.get('X-Content-Type-Options'), 'nosniff');
  } else if (scenario === 'missing-auth') {
    assert.equal(receipt.observedBytes, 0);
    assert.equal(response.headers.get('WWW-Authenticate'), 'Bearer realm="fga-api"');
    await copy.arrayBuffer();
  } else {
    const body = await copy.text();
    assert.match(response.headers.get('Content-Type'), /^application\/json/);
    assert.equal(body.includes('UPSTREAM_REJECTED_BODY'), false);
    assert.equal(body.includes('Synthetic'), false);
    assert.ok(JSON.parse(body).error);
  }
  if (['missing-auth','bad-auth','bad-query'].includes(scenario)) {
    assert.equal(count.pages, before.pages); assert.equal(count.images, before.images);
  } else if (['foreign-identity','private-photo','foreign-destination'].includes(scenario)) {
    assert.equal(count.pages, before.pages + 1); assert.equal(count.images, before.images);
  } else { assert.equal(count.pages, before.pages + 1); assert.equal(count.images, before.images + 1); }
  if (scenario === 'stall') {
    assert.equal(count.stalls, 1); assert.equal(count.stallCompleted, 0); assert.equal(count.cancelled, 1);
    assert.ok(elapsedMs >= 14900 && elapsedMs < 16000);
  }
  assert.equal(history(), originalHistory);
  assert.equal(db.raw.prepare('SELECT COUNT(*) n FROM photo_bindings').get().n, 0);
  assert.equal(db.raw.prepare('SELECT COUNT(*) n FROM submission_intents').get().n, 0);
  receipts.push({ scenario, ...receipt, elapsedMs });
});

test('final authority namespaces retain mutations without contaminating later authenticated pages', async () => {
  assert.equal(db.raw.prepare("SELECT state FROM installations WHERE installation_id='qualification-final-installation-install'").get().state, 'revoked');
  assert.equal(db.raw.prepare("SELECT link_revision FROM flickr_links WHERE user_id='qualification-final-link-user'").get().link_revision, 2);
  assert.equal(db.raw.prepare("SELECT active_generation FROM flickr_native_credentials WHERE user_id='qualification-final-grant-user'").get().active_generation, 'changed');
  // No reset occurs on reconstruction, and no case's mutation changes another.
  const restarted = createHandlerCaseProvider({ candidate, syntheticDb: db, counters: count });
  assert.equal((await restarted.fetch(request(HANDLER_PATHS[2]), 'final-installation')).status, 401);
  for (const scenario of ['ok','png','jpeg']) assert.equal((await restarted.fetch(request(HANDLER_PATHS[2]), scenario)).status, 200);
  const current = await (await restarted.fetch(request(HANDLER_PATHS[0]), 'ok')).json();
  assert.equal(current.installationId, handlerCaseIdentity('ok').installationId);
  assert.equal(db.raw.prepare("SELECT COUNT(*) n FROM installations WHERE installation_id LIKE 'qualification-%'").get().n, 20);
  await assert.rejects(initializeHandlerCaseNamespaces(db));
  assert.equal(history(), originalHistory);
});

test('actual complete browser pages and exact photo selection preserve cardinality/navigation', async () => {
  const pages = [];
  for (const path of BROWSER_PATHS.slice(0,2)) {
    const response = await provider.fetch(request(path), 'ok'); assert.equal(response.status, 200);
    const page = await response.json(); pages.push(page);
    assert.equal(page.pageSize, 2); assert.equal(page.total, 3); assert.equal(page.pages, 2);
    assert.equal(page.linkedFlickrRevision, 1);
  }
  assert.deepEqual(pages.map(page => page.photos.map(photo => photo.flickrPhotoId)), [['photo1','photo2'],['photo3']]);
  for (const path of BROWSER_PATHS.slice(2)) {
    const response = await provider.fetch(request(path), 'ok'); assert.equal(response.status, 200);
    assert.deepEqual(Buffer.from(await response.arrayBuffer()), originalPng());
  }
});

test('closed paths, selectors and malformed controls refuse before candidate/dependency work', async () => {
  const before = { ...count };
  for (const [scenario,path] of [['unknown',HANDLER_PATHS[2]],['png',HANDLER_PATHS[2]+'&extra=1'],['png',HANDLER_PATHS[2]+'?'],['jpeg',BROWSER_PATHS[0]],['bad-query',HANDLER_PATHS[0]],['png','/api/v001/existing-public-photos?page=3&page_size=2']]) {
    assert.equal((await provider.fetch(request(path), scenario)).status, 404);
  }
  assert.equal((await provider.fetch(new Request('https://other.invalid'+HANDLER_PATHS[2]), 'png')).status, 404);
  assert.equal((await provider.fetch(new Request(origin+HANDLER_PATHS[2], {method:'POST',body:'x'}), 'png')).status, 404);
  const controller = new AbortController(); controller.abort();
  assert.equal((await provider.fetch(new Request(origin+HANDLER_PATHS[2], {signal:controller.signal}), 'png')).status, 404);
  assert.deepEqual(count, before);
});

test('bounded evidence preserves unresolved hosted/native qualification and denies ambient I/O', () => {
  assert.equal(receipts.length, 20);
  assert.equal(count.hostIo + count.globalFetch + count.dynamicImport + count.responderFailures, 0);
  console.log(JSON.stringify({kind:'offline_worker_safe_actual_handler_cases',cases:receipts,hostedQualified:false,nativeQualified:false,feasibilityVerdictChanged:false}));
  db.raw.close();
});
