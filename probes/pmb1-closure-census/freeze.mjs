import {createRequire,builtinModules} from 'node:module';
import {readFileSync,readdirSync,writeFileSync} from 'node:fs';
import {resolve,relative} from 'node:path';
import {createHash} from 'node:crypto';
const root=resolve(process.argv[2]);
const out=resolve(process.argv[3]);
const require=createRequire(resolve(root,'package.json'));
const {build}=require('esbuild');
const hash=v=>createHash('sha256').update(v).digest('hex');
const files=[];
function walk(dir){for(const item of readdirSync(resolve(root,dir),{withFileTypes:true})){const p=`${dir}/${item.name}`;if(item.isDirectory())walk(p);else files.push(p);}}
for(const dir of ['src','migrations','scripts','probes/pmb1-d1','probes/pmb1-object'])walk(dir);
for(const p of ['package.json','package-lock.json','tsconfig.json','wrangler.example.jsonc','docs/operations/prospective-maintenance-contract-decision-2026-10-18.md'])files.push(p);
const pins=files.filter(p=>!p.includes('__pycache__')&&(!p.startsWith('scripts/')||/\.(py|sql|mjs)$/.test(p))).sort().map(path=>({path,sha256:hash(readFileSync(resolve(root,path)))}));
const result=await build({absWorkingDir:root,entryPoints:['src/worker.ts'],bundle:true,minify:true,format:'esm',platform:'browser',target:'es2023',external:['node:*',...builtinModules],write:false,metafile:true,logLevel:'silent'});
const inputs=Object.keys(result.metafile.inputs).filter(p=>p.startsWith('src/')).sort();
const output=Object.values(result.metafile.outputs)[0];
const emitted=Object.entries(output.inputs).filter(([p,v])=>p.startsWith('src/')&&v.bytesInOutput>0).map(([p])=>p).sort();
const allSource=pins.map(p=>p.path).filter(p=>p.startsWith('src/'));
const dependencyPins=Object.keys(result.metafile.inputs).filter(p=>!p.startsWith('src/')).sort().map(path=>({path,sha256:hash(readFileSync(resolve(root,path)))}));
const manifest={version:1,scope:'PUBLIC SOURCE CANDIDATE ONLY; NOT DEPLOYED CENSUS',entry:'src/worker.ts',build:{tool:'esbuild',version:require('esbuild/package.json').version,options:'bundle,minify,esm,browser,es2023,external=node:*+node-builtins',sha256:hash(result.outputFiles[0].contents),bytes:result.outputFiles[0].contents.length,exports:output.exports},importGraph:inputs,emittedSource:emitted,notImported:allSource.filter(p=>!inputs.includes(p)),dependencyPins,pins};
const encoded=JSON.stringify(manifest,null,2)+'\n';
if(process.argv.includes('--check')){if(readFileSync(out,'utf8')!==encoded)throw Error('source/build pin drift');console.log('source/build pins match');}
else {writeFileSync(out,encoded);console.log('frozen public source/build manifest');}
