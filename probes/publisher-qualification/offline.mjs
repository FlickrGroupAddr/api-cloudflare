// Finite local refusal diagnostic, not a full publisher or deployable Worker.
import { createWorker } from '../../src/worker.ts';
import { ROUTES } from '../../src/registry.ts';
import { consumeAlbumMaterialization } from '../../src/album_materialization_worker.ts';
import { consumeAlbumAttachment } from '../../src/album_attachment_worker.ts';
import { consumeAlbumTitle } from '../../src/album_title_worker.ts';
import { pathToFileURL } from 'node:url';

export async function runOfflineDiagnostic() {
  let providerCalls = 0, databaseCalls = 0;
  const db = new Proxy({}, { get() { databaseCalls++; throw Error('database_forbidden'); } });
  const upstream = async () => { providerCalls++; throw Error('network_forbidden'); };
  const originalFetch = globalThis.fetch;
  globalThis.fetch = upstream;
  const worker = createWorker(upstream);
  const routes = ROUTES.filter(route => /^(upload_|album_|publish_service_)/.test(route.handler));
  const results = [];
  const timer = setTimeout(() => { throw Error('offline_diagnostic_expired'); }, 30_000);
  try {
    for (const flags of [{}, Object.fromEntries([
      'FGA_UPLOAD_AUTHORIZATION_ENABLED', 'FGA_UPLOAD_PHOTO_BINDING_ENABLED',
      'FGA_UPLOAD_AMBIGUITY_RESOLUTION_ENABLED', 'FGA_UPLOAD_CANDIDATES_ENABLED',
      'FGA_PUBLISH_SERVICE_ENABLED', 'FGA_ALBUM_BINDINGS_ENABLED', 'FGA_ALBUM_OBLIGATIONS_ENABLED',
      'FGA_ALBUM_CREATE_REPAIR_ENABLED', 'FGA_ALBUM_TITLE_ENABLED', 'FGA_ALBUM_LOCAL_REMOVAL_ENABLED',
      'FGA_ALBUM_MATERIALIZATION_ENABLED', 'FGA_ALBUM_ATTACHMENT_ENABLED', 'FGA_ALBUM_TITLE_SYNC_ENABLED',
    ].map(name => [name, '0']))]) {
      for (const route of routes) {
        if (results.length >= 64) throw Error('offline_request_bound');
        const path = route.pathPattern.replace(/\{[^}]+\}/g, '00000000-0000-4000-8000-000000000001');
        const response = await worker.fetch(new Request(`https://publisher.invalid${path}`, {
          method: route.method, ...(route.method === 'POST' ? {body: '{}', headers: {'Content-Type': 'application/json'}} : {}),
        }), { DB: db, ...flags });
        if (response.status !== 503) throw Error('default_off_refusal_failed');
        results.push({ route: route.id, status: response.status });
      }
      await worker.scheduled({}, { DB: db, ...flags });
      for (const consume of [consumeAlbumMaterialization, consumeAlbumAttachment, consumeAlbumTitle]) {
        if (await consume({ DB: db, ...flags }, 'synthetic', upstream) !== 'disabled') {
          throw Error('consumer_default_off_failed');
        }
      }
    }
    if (providerCalls !== 0 || databaseCalls !== 0) throw Error('offline_boundary_failed');
    return { schemaVersion: 1, status: 'NO-GO', diagnostic: 'passed',
      fullPublisherExecutable: false, hostedQualification: 'not_executed',
      requests: results.length, defaultOffConsumers: 6, providerCalls, databaseCalls };
  } finally {
    clearTimeout(timer);
    globalThis.fetch = originalFetch;
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  console.log(JSON.stringify(await runOfflineDiagnostic()));
}
