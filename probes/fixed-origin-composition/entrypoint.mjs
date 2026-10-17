// Offline constructor only: deliberately no default Worker export or env reader.
// The caller supplies independently verified captured/candidate modules and isolated
// synthetic resources. This source cannot select a provider target or open a gate.
import { createQualificationComposition } from '../fixed-origin-lifecycle/composition.mjs';

export function createTemporaryComposition(options) {
  if (!options || typeof options.captured?.default?.fetch !== 'function'
      || typeof options.candidate?.createWorker !== 'function') {
    throw Error('module_interface_required');
  }
  // Do not wrap, clone, reconstruct or replace the ordinary request/environment.
  // The existing composition delegates these exact references to captured.fetch.
  return createQualificationComposition(options);
}
