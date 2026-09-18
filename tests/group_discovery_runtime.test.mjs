import test from 'node:test';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {mkdtemp,readFile,writeFile,rm} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {Miniflare} from 'miniflare';

test('compiled group API on native D1 admits one concurrent job and publishes ordered pages',async()=>{
 const directory=await mkdtemp(path.join(os.tmpdir(),'fga-groups-'));
 let mf;
 try{
  const config=path.join(directory,'wrangler.json');
  await writeFile(config,JSON.stringify({name:'group-proof',main:path.resolve('probes/groups/worker.ts'),compatibility_date:'2026-09-11',compatibility_flags:['nodejs_compat']}));
  execFileSync(process.execPath,['node_modules/wrangler/bin/wrangler.js','deploy','--dry-run','--config',config,'--outdir',path.join(directory,'bundle')],
   {env:{...process.env,WRANGLER_WRITE_LOGS:'false',WRANGLER_SEND_METRICS:'false',CI:'true'},stdio:'pipe'});
  const migrations=JSON.parse(execFileSync('uv',['run','--frozen','python','-c',"import json;from pathlib import Path;from scripts.coordination_probe import statements;print(json.dumps([statements(p.read_text(encoding='utf-8')) for p in sorted(Path('migrations').glob('*.sql'))]))"],{encoding:'utf8'}));
  mf=new Miniflare({modules:true,script:await readFile(path.join(directory,'bundle/worker.js'),'utf8'),compatibilityDate:'2026-07-30',compatibilityFlags:['nodejs_compat'],cf:false,telemetry:{enabled:false},d1Databases:['DB'],
   bindings:{PROOF_TOKEN:'synthetic-control',PROOF_EXPIRES:String(Date.now()+300000)},outboundService(){throw new Error('no_external_traffic');}});
  const db=await mf.getD1Database('DB');for(const sql of migrations)await db.batch(sql.map(s=>db.prepare(s)));
  const control=async action=>{const r=await mf.dispatchFetch('https://proof.test/probe/'+action,{headers:{Authorization:'Bearer synthetic-control'}});assert.equal(r.status,200);};
  await control('seed');
  const headers={Authorization:'Bearer '+'0000-'.repeat(12)+'0000'};
  const read=q=>mf.dispatchFetch('https://proof.test/api/v001/groups?'+q,{headers});
  const requests=await Promise.all(Array.from({length:5},()=>read('page_size=2')));
  assert(requests.every(r=>r.status===202));
  assert.equal((await db.prepare('SELECT COUNT(*) n FROM group_refresh').first()).n,1);
  await control('refresh');
  const response=await read('page_size=2');assert.equal(response.status,200);assert.equal(response.headers.get('Cache-Control'),'no-store');
  const first=await response.json();assert.equal(first.snapshotRevision,1);assert.deepEqual(first.groups.map(g=>g.flickrGroupId),['A','a']);
  const last=await (await read('page_size=2&snapshot_revision=1&after_group_id=a')).json();assert.deepEqual(last.groups.map(g=>g.flickrGroupId),['z']);assert.equal(last.nextAfterGroupId,null);
  assert.equal((await read('page_size=2&snapshot_revision=2&after_group_id=a')).status,409);
  assert.equal((await mf.dispatchFetch('https://proof.test/api/v001/group-submission-batches',{method:'POST',headers})).status,503);
  assert.equal((await db.prepare('SELECT COUNT(*) n FROM attempt_dispatches').first()).n,0);
 }finally{
  await mf?.dispose();
  assert.equal(path.dirname(path.resolve(directory)),path.resolve(os.tmpdir()));
  assert(path.basename(directory).startsWith('fga-groups-'));
  await rm(directory,{recursive:true,force:true});
 }
});
