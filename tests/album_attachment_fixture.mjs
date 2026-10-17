import assert from 'node:assert/strict';
import { nativeDatabase, sqliteDatabase, retained, rows } from './album_create_repair_fixture.mjs';
import { materializationFixture, databaseClock, AUTH } from './album_materialization_sqlite.mjs';
import * as materialization from '../src/album_materialization_store.ts';
import { putAlbumLocalRemoval } from '../src/album_local_removal_store.ts';

export { nativeDatabase, sqliteDatabase, retained, rows, databaseClock };
export const SET = 'attachment-set';
export async function attachmentFixture(t, options = {}) {
  const db = options.db ?? (options.native ? await nativeDatabase(t) : sqliteDatabase());
  if (db.raw) t.after(() => db.raw.close());
  const f = await materializationFixture({ after() {} }, db);
  const associated = await f.associate('later-photo');
  if (options.materialize !== false) {
    const claim = await materialization.claimAlbumMaterialization(db, f.bindingId);
    assert(claim);
    const marked = await materialization.markAlbumCreateDispatch(db, claim, []);
    assert(marked);
    const result = { photosetId: SET, url: 'https://www.flickr.com/photos/owner/albums/' + SET };
    assert(await materialization.recordAlbumCreateResult(db, marked, result));
    assert(await materialization.finishAlbumMaterialization(db, marked,
      { ...result, ownerNsid: 'owner', primaryPhotoId: 'primary-remote', contextIds: [SET] }));
  }
  const obligationId = associated.obligation.fgaAlbumObligationId;
  return { ...f, obligationId,
    obligation: () => db.prepare('SELECT * FROM album_photo_obligations WHERE obligation_id=?').bind(obligationId).first(),
    attempts: () => rows(db, 'album_attachment_attempts'),
    events: () => rows(db, 'album_attachment_events'),
    archive: async () => {
      const binding = await db.prepare('SELECT binding_revision FROM album_bindings WHERE binding_id=?').bind(f.bindingId).first();
      const unknown = await db.prepare("SELECT attempt_id FROM album_materialization_attempts WHERE binding_id=? AND state='create_outcome_unknown' ORDER BY epoch DESC LIMIT 1").bind(f.bindingId).first();
      return putAlbumLocalRemoval(db, AUTH, f.bindingId, { schemaVersion: 1,
        expectedBindingRevision: binding.binding_revision, acknowledgedCreateAttemptId: unknown?.attempt_id ?? null });
    },
  };
}
