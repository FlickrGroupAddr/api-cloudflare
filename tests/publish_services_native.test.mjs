import test from 'node:test';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {Miniflare} from 'miniflare';
import {publishServiceRequest} from '../src/publish_services.ts';

test('actual local D1 batches issue distinct retained IDs and fence pause/credential mutation',async t=>{
 const mf=new Miniflare({modules:true,script:'export default {fetch(){return new Response("local proof")}}',
  compatibilityDate:'2026-07-30',cf:false,telemetry:{enabled:false},d1Databases:['DB'],
  outboundService(){throw new Error('No live network')}});
 t.after(()=>mf.dispose());const db=await mf.getD1Database('DB');
 const migrations=JSON.parse(execFileSync('uv',['tool','run','--from','uv==0.12.5','uv','run','--frozen','python','-c',
  "import json;from pathlib import Path;from scripts.coordination_probe import statements;print(json.dumps([statements(p.read_text(encoding='utf-8')) for p in sorted(Path('migrations').glob('*.sql'))]))"],{encoding:'utf8'}));
 for(const sql of migrations) await db.batch(sql.map(s=>db.prepare(s)));
 const auth={installationId:'install',credentialDigest:'d'.repeat(64)};
 await db.batch([
  "INSERT INTO fga_users VALUES('user')",
  "INSERT INTO installations(installation_id,user_id,credential_class,state,revision,current_version_id) VALUES('install','user','lrc_plugin','active',1,'version')",
  `INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal) VALUES('version','install','${auth.credentialDigest}','current',1)`,
  "INSERT INTO flickr_links VALUES('user','owner',1,'linked')",
  "INSERT INTO flickr_native_credentials VALUES('user','gen',1,'owner','write',NULL)",
  "INSERT INTO flickr_connection_state(user_id,state,local_state,verified_permission,verified_at_us) VALUES('user','linked','available','write',1)",
 ].map(s=>db.prepare(s)));
 const env={DB:db,FGA_PUBLISH_SERVICE_ENABLED:'1'};
 const call=()=>publishServiceRequest(env,auth,new Request('https://example.test/api/v001/publish-services',{
  method:'POST',headers:{'Content-Type':'application/json'},body:'{"schemaVersion":1}'}));
 const results=await Promise.all([call(),call()]);assert.deepEqual(results.map(x=>x.status),[201,201]);
 const identities=await Promise.all(results.map(x=>x.json()));assert.notEqual(identities[0].fgaPublishServiceId,identities[1].fgaPublishServiceId);
 for(const sql of ['DELETE FROM publish_service_identities','UPDATE publish_service_identities SET service_revision=1',
  'INSERT OR REPLACE INTO publish_service_identities SELECT * FROM publish_service_identities']) await assert.rejects(db.prepare(sql).run());
 const original=db.batch.bind(db);let inject=true;
 const wrapped={prepare:db.prepare.bind(db),batch:async statements=>{
  if(inject){inject=false;await db.prepare("UPDATE flickr_connection_state SET state='replacing',operation_id='transition'").run()}
  return original(statements);
 }};
 assert.equal((await publishServiceRequest({...env,DB:wrapped},auth,new Request('https://example.test/api/v001/publish-services',{
  method:'POST',headers:{'Content-Type':'application/json'},body:'{"schemaVersion":1}'}))).status,409);
 assert.equal((await db.prepare('SELECT count(*) n FROM publish_service_identities').first()).n,2);
 const id=identities[0].fgaPublishServiceId;
 const read=await publishServiceRequest(env,auth,new Request('https://example.test/api/v001/publish-services/'+id),id);
 assert.equal((await read.json()).linkStatus,'link_unavailable');
 await db.prepare("CREATE TRIGGER synthetic_identity_failure BEFORE INSERT ON publish_service_identities BEGIN SELECT RAISE(ABORT,'synthetic'); END").run();
 await db.prepare("UPDATE flickr_connection_state SET state='linked',operation_id=NULL").run();
 assert.equal((await call()).status,503);assert.equal((await db.prepare('SELECT count(*) n FROM publish_service_identities').first()).n,2);
});
