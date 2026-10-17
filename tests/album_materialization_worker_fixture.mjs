import assert from 'node:assert/strict';
import { sqlStore } from './sql_store.mjs';
import { ensureAlbumBinding } from '../src/album_binding_store.ts';
import { consumeAlbumMaterialization } from '../src/album_materialization_worker.ts';
import { createSyntheticAlbumMaterializationTransport } from '../src/album_materialization_transport.ts';

export const SERVICE = '11111111-1111-4111-8111-111111111111';
export const SET = 'synthetic-set';
export const PHOTO = 'synthetic-first';
export const OWNER = 'synthetic-owner';
export const URL = `https://www.flickr.com/photos/${OWNER}/albums/${SET}/`;
export const contexts = (ids = []) => ({ stat: 'ok', set: ids.map(id => ({ id, title: 'Synthetic album' })), pool: [] });
export const created = () => ({ stat: 'ok', photoset: { id: SET, url: URL } });
export const info = (owner = OWNER, primary = PHOTO) => ({ stat: 'ok', photoset: { id: SET, owner, primary, title: { _content: 'Synthetic album' } } });

export async function materializationFixture(t) {
  const db = sqlStore();
  t.after(() => db.raw.close());
  const auth = { installationId: 'install', credentialDigest: 'a'.repeat(64) };
  await db.batch([
    db.prepare("INSERT INTO fga_users VALUES('user')"),
    db.prepare("INSERT INTO installations(installation_id,user_id,credential_class,state,revision,current_version_id) VALUES('install','user','lrc_plugin','active',1,'version')"),
    db.prepare("INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal) VALUES('version','install',?,'current',1)").bind(auth.credentialDigest),
    db.prepare("INSERT INTO flickr_links VALUES('user',?,1,'linked')").bind(OWNER),
    db.prepare("INSERT INTO flickr_native_credentials VALUES('user','synthetic-generation',1,?,'write',NULL)").bind(OWNER),
    db.prepare("INSERT INTO flickr_connection_state(user_id,state,local_state,verified_permission,verified_at_us) VALUES('user','linked','available','write',1)"),
    db.prepare("INSERT INTO flickr_write_gates VALUES('deployment','*',1,1),('user','user',1,1)"),
    db.prepare("INSERT INTO publish_service_identities(service_id,user_id,issuing_installation_id,link_revision,owner_nsid) VALUES(?,'user','install',1,?)").bind(SERVICE, OWNER),
    db.prepare("INSERT INTO photo_bindings(binding_id,user_id,photo_id,owner_nsid,link_revision,verification_revision,source_kind,verified_at_us) VALUES('first-photo','user',?,?,1,1,'existing_public',1),('competing-photo','user','synthetic-later',?,1,1,'existing_public',1)").bind(PHOTO, OWNER, OWNER),
    db.prepare("INSERT INTO photo_binding_events(event_id,binding_id,verification_revision,kind) VALUES('proof-first','first-photo',1,'existing_public_verified'),('proof-other','competing-photo',1,'existing_public_verified')"),
  ]);
  const ensure = photo => ensureAlbumBinding(db, auth, SERVICE, 'SyntheticAlbum', { schemaVersion: 1, desiredTitle: 'Synthetic album', candidate: { fgaPhotoBindingId: photo, expectedVerificationRevision: 1 } });
  const admitted = await ensure('first-photo');
  const binding = admitted.binding.fgaAlbumBindingId;
  const env = { DB: db, FGA_ALBUM_MATERIALIZATION_ENABLED: '1' };
  const f = { db, auth, env, binding, admitted, ensure, calls: [], hooks: {}, responses: {},
    album: () => db.raw.prepare('SELECT * FROM album_bindings WHERE binding_id=?').get(binding),
    obligation: () => db.raw.prepare('SELECT * FROM album_photo_obligations WHERE obligation_id=?').get(admitted.obligation.fgaAlbumObligationId),
  };
  f.factory = (identity, assertCurrent) => createSyntheticAlbumMaterializationTransport(identity, {
    assertCurrent, deadlineMs: f.deadlineMs,
    sign(method, data, post) {
      const url = new globalThis.URL('https://www.flickr.com/services/rest/');
      url.searchParams.set('method', method);
      for (const [key, value] of Object.entries(data)) url.searchParams.set(key, String(value));
      url.searchParams.set('format', 'json');
      url.searchParams.set('nojsoncallback', '1');
      const body = post ? url.searchParams.toString() : undefined;
      if (post) url.search = '';
      return new Request(url, { method: post ? 'POST' : 'GET', redirect: 'manual', ...(post ? { body, headers: { 'Content-Type': 'application/x-www-form-urlencoded' } } : {}) });
    },
    async fetcher(request) {
      const url = new globalThis.URL(request.url);
      const params = request.method === 'POST' ? new URLSearchParams(await request.clone().text()) : url.searchParams;
      const method = params.get('method');
      f.calls.push({ method, request, params });
      const count = f.calls.filter(call => call.method === method).length;
      await f.hooks[method]?.(request, count);
      let body = typeof f.responses[method] === 'function' ? await f.responses[method](request, count) : f.responses[method];
      body ??= method === 'flickr.photos.getAllContexts' ? contexts(count === 1 ? [] : [SET]) : method === 'flickr.photosets.create' ? created() : method === 'flickr.photosets.getInfo' ? info() : assert.fail('Unexpected Flickr method');
      return body instanceof Response ? body : Response.json(body);
    },
  });
  f.run = hooks => consumeAlbumMaterialization(env, binding, f.factory, hooks);
  return f;
}
