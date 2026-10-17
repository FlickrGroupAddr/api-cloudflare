import test from 'node:test';
import assert from 'node:assert/strict';
import { parseAlbumAssociate, ALBUM_OBLIGATIONS_RELEASE_METADATA } from '../src/album_obligations.ts';

const body = (binding = '1', proof = '1') => `{"schemaVersion":1,"expectedBindingRevision":${binding},"expectedVerificationRevision":${proof}}`;

test('association revisions retain exact safe integers in decimal and exponent notation', () => {
  for (const [raw, expected] of [['1', 1], ['1.00', 1], ['10e-1', 1], ['9007199254740991', Number.MAX_SAFE_INTEGER]]) {
    assert.deepEqual(parseAlbumAssociate(body(raw, raw)), { schemaVersion: 1, expectedBindingRevision: expected, expectedVerificationRevision: expected });
  }
  for (const raw of ['0', '-1', '1.1', '9007199254740992', '9007199254740991.1', '9007199254740990.9', '1e309', '1e-4097', '01', '+1', 'NaN', 'Infinity']) {
    assert.throws(() => parseAlbumAssociate(body(raw)), undefined, raw);
    assert.throws(() => parseAlbumAssociate(body('1', raw)), undefined, raw);
  }
});

test('association rejects duplicate names before JSON parsing can collapse them', () => {
  for (const raw of [
    '{"schemaVersion":1,"schemaVersion":1,"expectedBindingRevision":1,"expectedVerificationRevision":1}',
    '{"schemaVersion":1,"expectedBindingRevision":1,"expectedBindingRevisio\\u006e":2,"expectedVerificationRevision":1}',
    '{"schemaVersion":1,"expectedBindingRevision":1,"expectedVerificationRevision":1,"expectedVerificationRevision":1}',
  ]) assert.throws(() => parseAlbumAssociate(raw));
});

test('association closed schema rejects null, unknown, structural and Unicode substitutions', () => {
  const valid = JSON.parse(body());
  for (const field of Object.keys(valid)) {
    const missing = { ...valid }; delete missing[field];
    assert.throws(() => parseAlbumAssociate(JSON.stringify(missing)));
    for (const replacement of [null, true, '1', [], {}, '\ud800', '１']) {
      assert.throws(() => parseAlbumAssociate(JSON.stringify({ ...valid, [field]: replacement })));
    }
  }
  for (const raw of ['null', '[]', body() + body(), '\ufeff' + body(), body().replace('schemaVersion', 'SchemaVersion'),
    JSON.stringify({ ...valid, ownerNsid: 'owner' }), JSON.stringify({ ...valid, schemaVersion: 2 }),
    body().replace('1,"expectedBinding', '1,\u00a0"expectedBinding')]) assert.throws(() => parseAlbumAssociate(raw));
  assert.equal(ALBUM_OBLIGATIONS_RELEASE_METADATA.defaultValue, '0');
  assert.equal(ALBUM_OBLIGATIONS_RELEASE_METADATA.hostQualified, false);
});
