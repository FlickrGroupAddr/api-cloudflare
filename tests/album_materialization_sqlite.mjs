import { readFileSync } from 'node:fs';
import { sqlStore } from './sql_store.mjs';
import { legacyAlbumStore, migrateAlbumObligations } from './album_migration_fixture.mjs';
import { ensureAlbumBinding } from '../src/album_binding_store.ts';
import { associateAlbumPhoto } from '../src/album_obligation_store.ts';

export const SERVICE = '11111111-1111-4111-8111-111111111111';
export const AUTH = { installationId: 'install', credentialDigest: 'a'.repeat(64) };

export function through0021() {
  const db = legacyAlbumStore();
  migrateAlbumObligations(db);
  return db;
}
export function migrateMaterialization(db) {
  db.raw.exec('BEGIN');
  try {
    db.raw.exec(readFileSync('migrations/0022_album_materialization.sql', 'utf8'));
    db.raw.exec('COMMIT');
  } catch (error) {
    db.raw.exec('ROLLBACK');
    throw error;
  }
}
/** Only database setup: all album admission uses production stores. */
export async function materializationFixture(t, db = sqlStore()) {
  t.after(() => db.raw.close());
  await db.batch([
    db.prepare("INSERT INTO fga_users VALUES('user')"),
    db.prepare("INSERT INTO installations(installation_id,user_id,credential_class,state,revision,current_version_id) VALUES('install','user','lrc_plugin','active',1,'version')"),
    db.prepare("INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal) VALUES('version','install',?,'current',1)").bind(AUTH.credentialDigest),
    db.prepare("INSERT INTO flickr_links VALUES('user','owner',1,'linked')"),
    db.prepare("INSERT INTO flickr_native_credentials VALUES('user','gen',1,'owner','write',NULL)"),
    db.prepare("INSERT INTO flickr_connection_state(user_id,state,local_state,verified_permission,verified_at_us) VALUES('user','linked','available','write',1)"),
    db.prepare("INSERT INTO flickr_write_gates VALUES('deployment','*',1,1),('user','user',1,1)"),
    db.prepare("INSERT INTO publish_service_identities(service_id,user_id,issuing_installation_id,link_revision,owner_nsid) VALUES(?,'user','install',1,'owner')").bind(SERVICE),
    db.prepare("INSERT INTO photo_bindings(binding_id,user_id,photo_id,owner_nsid,link_revision,verification_revision,source_kind,verified_at_us) VALUES('primary-photo','user','primary-remote','owner',1,1,'existing_public',1),('later-photo','user','later-remote','owner',1,1,'existing_public',1),('third-photo','user','third-remote','owner',1,1,'existing_public',1)"),
    db.prepare("INSERT INTO photo_binding_events(event_id,binding_id,verification_revision,kind) VALUES('primary-proof','primary-photo',1,'existing_public_verified'),('later-proof','later-photo',1,'existing_public_verified'),('third-proof','third-photo',1,'existing_public_verified')"),
  ]);
  const ensure = (photo = 'primary-photo', local = 'Album:007') => ensureAlbumBinding(db, AUTH, SERVICE, local, {
    schemaVersion: 1, desiredTitle: 'Synthetic album', candidate: { fgaPhotoBindingId: photo, expectedVerificationRevision: 1 },
  });
  const first = await ensure(), bindingId = first.binding.fgaAlbumBindingId;
  return { db, first, bindingId, ensure, associate: (photo = 'later-photo', revision = 1) =>
    associateAlbumPhoto(db, AUTH, bindingId, photo, { schemaVersion: 1, expectedBindingRevision: revision, expectedVerificationRevision: 1 }) };
}
export const rows = (db, table) => db.raw.prepare('SELECT * FROM ' + table + ' ORDER BY rowid').all();
export const retainedState = db => Object.fromEntries([
  'album_bindings', 'album_photo_obligations', 'album_binding_events', 'album_obligation_events',
  'album_materialization_attempts', 'album_materialization_events', 'transaction_guards',
].map(table => [table, rows(db, table)]));

/** Move the authoritative SQLite clock without editing guarded lease evidence. */
export function databaseClock(db) {
  let nowUs = db.raw.prepare("SELECT CAST(strftime('%s','now') AS INTEGER)*1000000 + CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000 now_us").get().now_us;
  db.raw.function('strftime', (format, when) => {
    if (when !== 'now') throw new Error('unexpected_test_clock_input');
    if (format === '%s') return String(Math.floor(nowUs / 1000000));
    if (format === '%f') return String(Math.floor(nowUs / 1000000) % 60).padStart(2, '0') + '.' + String(Math.floor(nowUs / 1000) % 1000).padStart(3, '0');
    throw new Error('unexpected_test_clock_format');
  });
  return { set: value => { nowUs = value; } };
}
