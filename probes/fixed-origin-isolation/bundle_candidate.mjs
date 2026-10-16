// JavaScript is required here to call the pinned esbuild API on Worker source.
import { pathToFileURL } from 'node:url';
import { resolve } from 'node:path';
const [repository, candidate, outfile] = process.argv.slice(2);
if (process.version !== 'v24.22.0') throw Error('unexpected_node');
if (!repository || !candidate || !outfile || process.argv.length !== 5) throw Error('arguments');
const { build, version } = await import(pathToFileURL(resolve(repository, 'node_modules/esbuild/lib/main.js')));
if (version !== '0.28.1') throw Error('unexpected_bundler');
await build({ entryPoints: [resolve(candidate, 'src/worker.ts')], outfile,
  absWorkingDir: candidate, nodePaths: [resolve(repository, 'node_modules')],
  bundle: true, platform: 'node', format: 'esm', target: 'node24', minify: true,
  keepNames: true, sourcemap: false, logLevel: 'silent' });
