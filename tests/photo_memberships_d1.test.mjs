import test from 'node:test';
import assert from 'node:assert/strict';
import { Miniflare } from 'miniflare';
import { sqlStore } from './sql_store.mjs';
import { photoMembershipsRequest } from '../src/photo_memberships.ts';
import { budgetedFlickrFetch } from '../src/flickr_rate.ts';

// Exercises exact handler SQL against native local D1. This does not qualify hosted clocks or Flickr compatibility.
test('native D1 atomically publishes complete memberships and honors the shared provider budget', async () => {
  let outbound = 0;
  const mf = new Miniflare({ modules: true, script: 'export default {fetch(){return new Response(null,{status:404})}}',
    compatibilityDate: '2026-07-30', compatibilityFlags: ['nodejs_compat'], cf: false, telemetry: { enabled: false },
    d1Databases: ['DB'], outboundService() { outbound++; throw new Error('no_external_traffic'); } });
  const source = sqlStore();
  try {
    const db = await mf.getD1Database('DB');
    // Final schema comes from executing every repository migration in the existing SQLite fixture.
    // All native D1 transaction/JSON/ordering operations below use the production handler unchanged.
    const schema = source.raw.prepare("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY CASE type WHEN 'table' THEN 1 WHEN 'index' THEN 2 ELSE 3 END,rowid").all();
    await db.batch(schema.map(row => db.prepare(row.sql)));
    const digest = 'd'.repeat(64);
    await db.batch([
      db.prepare("INSERT INTO fga_users VALUES('user')"),
      db.prepare("INSERT INTO installations(installation_id,user_id,credential_class,state,revision,current_version_id) VALUES('install','user','lrc_plugin','active',1,'version')"),
      db.prepare("INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal) VALUES('version','install',?,'current',1)").bind(digest),
      db.prepare("INSERT INTO flickr_links VALUES('user','owner',1,'linked')"),
      db.prepare("INSERT INTO flickr_native_credentials(user_id,active_generation,link_revision,verified_owner_nsid,verified_permission) VALUES('user','gen',1,'owner','write')"),
      db.prepare("INSERT INTO photo_bindings(binding_id,user_id,photo_id,owner_nsid,link_revision,verification_revision,source_kind) VALUES('binding','user','photo','owner',1,1,'existing_public')"),
    ]);
    const secrets = { FLICKR_APPLICATION: { get: async () => JSON.stringify({ schemaVersion: 1, consumerKey: 'app', consumerSecret: 'secret' }) },
      FLICKR_GRANT: { get: async () => JSON.stringify({ schemaVersion: 1, generation: 'gen', token: 'token', tokenSecret: 'token-secret' }) } };
    let calls = 0, malformed = false;
    const fetcher = budgetedFlickrFetch(db, async () => { calls++; return Response.json(malformed ? { stat: 'ok' } :
      { stat: 'ok', pool: [{ id: 'z', title: 'Last' }, { id: 'a', title: 'Middle' }, { id: 'A', title: 'First' }] }); });
    const read = q => photoMembershipsRequest(db, { installationId: 'install', credentialDigest: digest }, 'binding', new URL('https://fixture.test/?' + q), secrets, fetcher);
    const firstResponse = await read('page_size=2'); assert.equal(firstResponse.status, 200);
    const first = await firstResponse.json(); assert.deepEqual(first.groups.map(g => g.flickrGroupId), ['A', 'a']); assert.equal(first.nextAfterGroupId, 'a');
    const next = await read('page_size=2&observation_revision=1&after_group_id=a');
    assert.deepEqual((await next.json()).groups.map(g => g.flickrGroupId), ['z']); assert.equal(calls, 1);
    malformed = true; assert.equal((await read('page_size=2')).status, 503);
    assert.equal((await db.prepare('SELECT revision FROM photo_membership_observations').first()).revision, 1);
    assert.equal((await db.prepare('SELECT COUNT(*) n FROM photo_membership_rows').first()).n, 3);
    assert.equal((await read('page_size=2&observation_revision=1&after_group_id=a')).status, 409);
    assert.equal((await db.prepare('SELECT reserved_slots FROM flickr_rate_window').first()).reserved_slots, 2);
    malformed = false; await read('page_size=2');
    assert.equal((await read('page_size=2&observation_revision=1&after_group_id=a')).status, 409);
    await db.prepare('UPDATE flickr_rate_window SET reserved_slots=capacity').run();
    assert.equal((await read('page_size=2')).status, 503); assert.equal(calls, 3);
    assert.equal((await db.prepare('SELECT revision FROM photo_membership_observations').first()).revision, 2);
    assert.equal((await db.prepare('SELECT COUNT(*) n FROM attempt_dispatches').first()).n, 0);
    assert.equal((await db.prepare('SELECT COUNT(*) n FROM transaction_guards').first()).n, 0);
    assert.equal((await db.prepare('PRAGMA foreign_key_check').all()).results.length, 0);
    assert.equal(outbound, 0);
  } finally { source.raw.close(); await mf.dispose(); }
});
