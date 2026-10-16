// Node VM is necessary to execute both unchanged JavaScript Worker bundles.
// Only pure host helpers are linked; filesystem/network/process are never exposed.
import { readFileSync } from 'node:fs';
import * as cryptoModule from 'node:crypto';
import * as util from 'node:util';
import stream from 'node:stream';
import events from 'node:events';
import buffer from 'node:buffer';
import assert from 'node:assert';
import url from 'node:url';
import path from 'node:path';
import querystring from 'node:querystring';
import vm from 'node:vm';

export async function loadOfflineModule(filename, counters) {
  const denyIo = new Proxy(function () { counters.hostIo++; throw Error('offline_io_denied'); }, {
    get(_, key) { if (key === 'then') return undefined; return denyIo; },
    apply() { counters.hostIo++; throw Error('offline_io_denied'); },
    construct() { counters.hostIo++; throw Error('offline_io_denied'); },
  });
  const inertProcess = Object.freeze({ env: Object.freeze({}), platform: 'offline', version: 'v24.22.0',
    cwd: () => '/offline', argv: Object.freeze([]),
    versions: Object.freeze({ node: '24.22.0' }), stdout: Object.freeze({ isTTY: false }), stderr: Object.freeze({ isTTY: false }),
    getBuiltinModule(name) { if (name === 'crypto') return cryptoModule; return denyIo; } });
  const pureDefaults = { util, stream, events, buffer, assert, url, path, querystring, process: inertProcess,
    crypto: cryptoModule };
  const context = vm.createContext({ Request, Response, Headers, URL, URLSearchParams, TextEncoder, TextDecoder,
    ReadableStream, AbortController, AbortSignal, setTimeout, clearTimeout, performance, atob, btoa,
    process: inertProcess, Buffer: buffer.Buffer, crypto: cryptoModule.webcrypto,
    require(name) { const key = name.replace(/^node:/, '');
      return Object.hasOwn(pureDefaults, key) ? pureDefaults[key] : denyIo; },
    fetch() { counters.globalFetch++; throw Error('offline_fetch_denied'); },
    console: Object.freeze({ log() {}, warn() {}, error() {} }) },
    { codeGeneration: { strings: false, wasm: false } });
  const source = readFileSync(filename, 'utf8');
  const module = new vm.SourceTextModule(source, { context, identifier: 'offline-worker',
    importModuleDynamically() { counters.dynamicImport++; throw Error('offline_import_denied'); } });
  try { await module.link(specifier => {
    const name = specifier.replace(/^node:/, '');
    const pure = Object.hasOwn(pureDefaults, name) ? pureDefaults[name] : undefined;
    const exports = pure ? { ...pure, default: pure }
      : specifier === 'node:crypto' || specifier === 'crypto'
        ? { ...cryptoModule, default: cryptoModule }
        : { default: pureDefaults[specifier] ?? denyIo };
    // Denied builtins may be named imports. Link their names to throwing values
    // without handing any real filesystem/network/process implementation across.
    for (const match of source.matchAll(/import\s*[^;]*?\{([^}]+)\}\s*from\s*["']([^"']+)["']/g)) {
      if (match[2] !== specifier) continue;
      for (const part of match[1].split(',')) {
        const exported = part.trim().split(/\s+as\s+/)[0];
        if (!(exported in exports)) exports[exported] = denyIo;
      }
    }
    return new vm.SyntheticModule(Object.keys(exports), function () {
      for (const [name, value] of Object.entries(exports)) this.setExport(name, value);
    }, { context });
  }); } catch (error) { throw Error('offline_module_link_refused: ' + error.message); }
  try { await module.evaluate({ timeout: 5000 }); }
  catch (error) { throw Error('offline_module_evaluation_refused: ' + error.message); }
  return module.namespace;
}
