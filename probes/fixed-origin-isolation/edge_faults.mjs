// Offline qualification stimuli AFTER a compliant actual thumbnail handler response.
// JavaScript is required to compose the unchanged Worker Response boundary.
import { ORIGIN, PATHS } from './wrapper.mjs';
import { png } from './edge_png.mjs';

export const EDGE_REDIRECT_CODES = Object.freeze([301, 302, 303, 307, 308]);
export const EDGE_FAULT_CASES = Object.freeze([
  ...EDGE_REDIRECT_CODES.map(code => `edge-redirect-${code}`),
  'edge-wrong-media', 'edge-malformed-png', 'edge-truncated-png',
  'edge-declared-excess', 'edge-undeclared-excess',
]);
export const MAX_EDGE_STIMULUS_BYTES = 262145;

// Paths are specifications for a later isolated receiver, not registered endpoints.
export function edgeReceiverPath(run, code) {
  if (typeof run !== 'string' || !/^[a-f0-9]{32}$/.test(run) || !EDGE_REDIRECT_CODES.includes(code)) throw Error('invalid_edge_receiver');
  return `/api/v001/existing-public-photos/photo/thumbnail/qualification-receiver/${run}/${code}`;
}

// No requested URL, body, size, delay or headers are admitted. The caller must
// validate the closed external capability/lifetime selectors before invoking this.
export async function injectEdgeFault(response, options) {
  if (!options || Object.keys(options).sort().join(',') !== 'requestUrl,run,scenario') throw Error('invalid_edge_fault_scope');
  const { scenario, run, requestUrl } = options;
  if (!EDGE_FAULT_CASES.includes(scenario) || typeof run !== 'string' || !/^[a-f0-9]{32}$/.test(run)
      || requestUrl !== ORIGIN + PATHS[2]) throw Error('invalid_edge_fault_scope');
  if (response.status !== 200 || response.headers.get('Content-Type') !== 'image/png'
      || response.headers.get('Cache-Control') !== 'private, no-store'
      || response.headers.get('X-Content-Type-Options') !== 'nosniff') throw Error('edge_fault_requires_compliant_handler');
  // Consume the actual compliant response before replacing it. Bound the read,
  // including when an erroneous caller supplies a streaming response.
  const reader = response.body?.getReader();
  if (!reader) throw Error('edge_fault_requires_compliant_handler');
  const parts = [];
  let observed = 0;
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      observed += value.byteLength;
      if (observed > 262144) {
        await reader.cancel().catch(() => {});
        throw Error('edge_fault_requires_compliant_handler');
      }
      parts.push(value);
    }
  } finally { reader.releaseLock(); }
  const source = new Uint8Array(observed);
  let offset = 0;
  for (const part of parts) { source.set(part, offset); offset += part.length; }
  // The finite source is exactly the synthetic png case, not arbitrary bytes.
  const wrapperPng = Uint8Array.from(atob('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII='), c => c.charCodeAt(0));
  if (![png(), wrapperPng].some(expected => source.length === expected.length
      && source.every((byte, index) => byte === expected[index]))) throw Error('edge_fault_requires_compliant_handler');
  const base = { 'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff' };
  if (scenario.startsWith('edge-redirect-')) {
    const status = Number(scenario.slice('edge-redirect-'.length));
    return new Response(null, { status, headers: { ...base, Location: ORIGIN + edgeReceiverPath(run, status) } });
  }
  const bytes = scenario === 'edge-wrong-media' ? new TextEncoder().encode('<html>synthetic edge fault</html>')
    : scenario === 'edge-malformed-png' ? Uint8Array.from([137, 80, 78, 71, 13, 10, 26, 10, 0, 0, 0, 0])
    : scenario === 'edge-truncated-png' ? source.subarray(0, source.length - 12)
    : png(MAX_EDGE_STIMULUS_BYTES);
  const headers = { ...base, 'Content-Type': scenario === 'edge-wrong-media' ? 'text/html' : 'image/png' };
  if (scenario !== 'edge-undeclared-excess') headers['Content-Length'] = String(scenario === 'edge-truncated-png' ? source.length : bytes.length);
  return new Response(bytes, { status: 200, headers });
}
