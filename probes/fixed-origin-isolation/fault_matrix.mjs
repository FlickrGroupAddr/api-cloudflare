// Offline-only finite response factory for the pinned actual candidate handlers.
// No endpoint, selector extension, network implementation or production environment.
import assert from 'node:assert/strict';
import { deflateSync } from 'node:zlib';
export const FAULT_CASES = Object.freeze({
  png: 200, jpeg: 200, 'exact-limit': 200, 'declared-excess': 503,
  'undeclared-excess': 503, 'upstream-error': 503, truncation: 503,
  'wrong-media': 503, 'wrong-signature': 503, redirect: 503, stall: 503,
  'missing-auth': 401, 'bad-auth': 401, 'bad-query': 400,
  'final-installation': 401, 'final-link': 409, 'final-grant': 409,
  'foreign-identity': 503, 'private-photo': 503, 'foreign-destination': 503,
});
function crc32(data) {
  let value = 0xffffffff;
  for (const byte of data) { value ^= byte; for (let n = 0; n < 8; n++) value = (value >>> 1) ^ ((value & 1) ? 0xedb88320 : 0); }
  return (value ^ 0xffffffff) >>> 0;
}
function chunk(type, bytes) {
  const kind = Buffer.from(type), result = Buffer.alloc(bytes.length + 12);
  result.writeUInt32BE(bytes.length); kind.copy(result, 4); bytes.copy(result, 8);
  result.writeUInt32BE(crc32(Buffer.concat([kind, bytes])), result.length - 4); return result;
}
// Real decodable 1x1 grayscale PNG. Optional ancillary padding preserves CRCs and decoding.
export function png(size) {
  const ihdr = Buffer.from([0,0,0,1,0,0,0,1,8,0,0,0,0]);
  const pieces = [Buffer.from([137,80,78,71,13,10,26,10]), chunk('IHDR', ihdr), chunk('IDAT', deflateSync(Buffer.from([0,128])))];
  const base = pieces.reduce((n, p) => n + p.length, 12);
  if (size !== undefined) { assert.ok(size >= base + 12); pieces.push(chunk('paDd', Buffer.alloc(size - base - 12))); }
  pieces.push(chunk('IEND', Buffer.alloc(0))); return Buffer.concat(pieces);
}
// Filled from the existing generated solid-color 2x2 JPEG fixture; no photo metadata.
export const JPEG_BASE64 = '/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAMCAgMCAgMDAwMEAwMEBQgFBQQEBQoHBwYIDAoMDAsKCwsNDhIQDQ4RDgsLEBYQERMUFRUVDA8XGBYUGBIUFRT/2wBDAQMEBAUEBQkFBQkUDQsNFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBT/wAARCAACAAIDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDwSiiiv2U/Lz//2Q==';
export const IMAGE_URL = 'https://live.staticflickr.com/1/photo_key_q.png';
export function createFaultFetch(scenario, db, counters) {
  if (!Object.hasOwn(FAULT_CASES, scenario)) throw Error('unknown_fault_case');
  return async request => {
    try {
    assert.equal(request.method, 'GET'); assert.equal(request.redirect, 'manual');
    const url = new URL(request.url);
    if (url.origin === 'https://www.flickr.com' && url.pathname === '/services/rest/') {
      assert.deepEqual(Object.fromEntries(url.searchParams), { method: 'flickr.people.getPhotos', user_id: 'synthetic-owner',
        privacy_filter: '1', content_types: '0', extras: 'date_upload,date_taken,media,url_q', page: '1', per_page: '1', format: 'json', nojsoncallback: '1' });
      assert.match(request.headers.get('Authorization'), /^OAuth /);
      counters.pages++;
      return Response.json({ stat: 'ok', photos: { page: 1, perpage: 1, pages: 1, total: 1, photo: [{
        id: scenario === 'foreign-identity' ? 'foreign' : 'photo', owner: 'synthetic-owner',
        ispublic: scenario === 'private-photo' ? '0' : '1', media: 'photo', title: 'Synthetic',
        dateupload: '1770000000', datetaken: '2026-02-01 14:30:00',
        url_q: scenario === 'foreign-destination' ? 'https://other.invalid/1/photo_key_q.png' : IMAGE_URL,
      }] } });
    }
    assert.equal(request.url, IMAGE_URL);
    for (const header of ['Authorization', 'Cookie', 'Referer']) assert.equal(request.headers.has(header), false);
    counters.images++;
    // Mutate only isolated SQLite after upstream selection, so the actual final fences decide.
    if (scenario === 'final-installation') db.raw.exec("BEGIN; UPDATE installation_credential_versions SET state='revoked'; UPDATE installations SET state='revoked',current_version_id=NULL,pending_version_id=NULL,revision=revision+1; COMMIT");
    if (scenario === 'final-link') db.raw.exec('UPDATE flickr_links SET link_revision=link_revision+1');
    if (scenario === 'final-grant') db.raw.exec("UPDATE flickr_native_credentials SET active_generation='changed'");
    if (scenario === 'redirect') return new Response('UPSTREAM_REJECTED_BODY', { status: 302, headers: { Location: 'https://other.invalid/' } });
    if (scenario === 'upstream-error') return new Response('UPSTREAM_REJECTED_BODY', { status: 502 });
    if (scenario === 'stall') {
      return new Response(new ReadableStream({ start(controller) {
        counters.stalls++;
        const timer = setTimeout(() => { counters.stallCompleted++; controller.enqueue(png()); controller.close(); }, 16000);
        this.timer = timer;
      }, cancel() { clearTimeout(this.timer); counters.cancelled++; } }), { headers: { 'Content-Type': 'image/png' } });
    }
    const bytes = scenario === 'jpeg' ? Buffer.from(JPEG_BASE64, 'base64')
      : scenario === 'exact-limit' ? png(262144)
      : ['declared-excess', 'undeclared-excess'].includes(scenario) ? png(262145)
      : scenario === 'wrong-signature' ? Buffer.alloc(70, 120) : png();
    const headers = { 'Content-Type': scenario === 'jpeg' ? 'image/jpeg' : scenario === 'wrong-media' ? 'text/html' : 'image/png' };
    if (scenario !== 'undeclared-excess') headers['Content-Length'] = String(bytes.length + (scenario === 'truncation' ? 1 : 0));
    return new Response(bytes, { headers });
    } catch (error) { counters.responderFailures++; throw error; }
  };
}
