import assert from 'node:assert/strict';
import { sqliteDatabase, nativeDatabase, rows, retained, splitMigrations } from './album_create_repair_fixture.mjs';
import { materializationFixture, AUTH, SERVICE } from './album_materialization_sqlite.mjs';
import * as materialization from '../src/album_materialization_store.ts';

export { sqliteDatabase, nativeDatabase, rows, retained, splitMigrations, AUTH, SERVICE };
export const SET = 'removal-set';
export async function removalFixture(t, { db = sqliteDatabase(), materialized = true, later = true } = {}) {
  if (db.raw) t.after(() => db.raw.close());
  const f = await materializationFixture({ after() {} }, db);
  f.auth = AUTH;
  if (later) f.later = await f.associate('later-photo');
  if (materialized) {
    const claimed = await materialization.claimAlbumMaterialization(db, f.bindingId);
    assert(claimed);
    const marked = await materialization.markAlbumCreateDispatch(db, claimed, []);
    assert(marked);
    const result = { photosetId: SET, url: 'https://www.flickr.com/photos/owner/albums/' + SET,
      ownerNsid: 'owner', primaryPhotoId: 'primary-remote', contextIds: [SET] };
    assert(await materialization.recordAlbumCreateResult(db, marked, result));
    assert(await materialization.finishAlbumMaterialization(db, marked, result));
  }
  f.binding = () => db.prepare('SELECT * FROM album_bindings WHERE binding_id=?').bind(f.bindingId).first();
  f.obligation = (photo = 'later-photo') => db.prepare('SELECT * FROM album_photo_obligations WHERE album_binding_id=? AND photo_binding_id=?').bind(f.bindingId, photo).first();
  return f;
}
