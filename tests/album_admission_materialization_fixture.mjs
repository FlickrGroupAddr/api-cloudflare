import assert from 'node:assert/strict';
import { claimAlbumMaterialization, markAlbumCreateDispatch, recordAlbumCreateResult, finishAlbumMaterialization } from '../src/album_materialization_store.ts';

/** Synthetic proof enters through the production store; current SQL guards stay active. */
export async function materializeAdmissionAlbum(db, bindingId, photosetId) {
  await db.batch([
    db.prepare("INSERT INTO flickr_write_gates(scope,scope_id,enabled,revision) VALUES('deployment','*',1,1) ON CONFLICT(scope,scope_id) DO NOTHING"),
    db.prepare("INSERT INTO flickr_write_gates(scope,scope_id,enabled,revision) SELECT 'user',user_id,1,1 FROM album_bindings WHERE binding_id=? ON CONFLICT(scope,scope_id) DO NOTHING").bind(bindingId),
    db.prepare("UPDATE flickr_write_gates SET enabled=1,revision=revision+1 WHERE enabled=0 AND ((scope='deployment' AND scope_id='*') OR (scope='user' AND scope_id=(SELECT user_id FROM album_bindings WHERE binding_id=?)))").bind(bindingId),
  ]);
  const claim = await claimAlbumMaterialization(db, bindingId);
  assert(claim, 'admitted album must yield a fenced materialization claim');
  const dispatched = await markAlbumCreateDispatch(db, claim, []);
  assert(dispatched, 'synthetic pre-context proof must commit the dispatch marker');
  const url = `https://www.flickr.com/photos/${claim.ownerNsid}/albums/${photosetId}/`;
  assert.equal(await recordAlbumCreateResult(db, dispatched, { photosetId, url }), true);
  assert.equal(await finishAlbumMaterialization(db, dispatched, {
    photosetId, url,
    ownerNsid: claim.ownerNsid, primaryPhotoId: claim.photoId, contextIds: [photosetId],
  }), true);
}
