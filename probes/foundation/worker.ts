// Disposable proof wrapper. No proof route or fixture provisioning ships in src/worker.ts.
import api, { type Env as ApiEnv } from "../../src/worker.ts";
import { authenticate, credentialDigest, d1Lookup, NOW_US_SQL } from "../../src/installations.ts";
interface Env extends ApiEnv { PROOF_TOKEN: string; PROOF_MODE: string; PROOF_BUILD: string; PROOF_EXPIRES: string; }
const TABLES = ["fga_users","installations","installation_credential_versions","submission_blocks","audit_events"];
function tagged(response: Response, env: Env): Response {
  const headers=new Headers(response.headers); headers.set("X-FGA-Proof-Build",env.PROOF_BUILD);
  return new Response(response.body,{status:response.status,headers});
}
async function snapshot(db: D1Database): Promise<string> {
  const values=[];
  for (const table of TABLES) values.push((await db.prepare(`SELECT * FROM ${table} ORDER BY ${table==="submission_blocks"?"1,2":"1"}`).all()).results);
  return credentialDigest(JSON.stringify(values));
}
async function seed(db: D1Database, credentials: string[]): Promise<void> {
  if (credentials.length !== 7 || credentials.some(x=>typeof x!=="string")) throw new Error("fixture_shape");
  const hashes=await Promise.all(credentials.map(credentialDigest));
  const sameFixture=async(): Promise<boolean> => {
    const rows=(await db.prepare("SELECT version_id,credential_digest FROM installation_credential_versions ORDER BY version_id").all<{version_id:string,credential_digest:string}>()).results;
    return rows.length===7 && rows.every((row,n)=>row.version_id===`v${n}` && row.credential_digest===hashes[n]);
  };
  if ((await db.prepare("SELECT COUNT(*) AS n FROM installations").first<{n:number}>())?.n !== 0) {
    if(await sameFixture()) return;
    throw new Error("fixture_identity_conflict");
  }
  const statements=[db.prepare("INSERT INTO fga_users VALUES('fixture-owner')")];
  for (const [id,state,current,pending,revision] of [
    ["active","active","v0","v1",7], ["expired","active","v2","v3",2], ["revoked","revoked",null,null,3],
  ]) statements.push(db.prepare("INSERT INTO installations(installation_id,user_id,credential_class,state,revision,current_version_id,pending_version_id,label) VALUES(?,'fixture-owner','lrc_plugin',?,?,?,?,?)").bind(id,state,revision,current,pending,"fixture 'line\r\n\u263a\u0000tail"));
  const versions=[ ["active","current",1,null], ["active","pending_rotation",2,"future"],
    ["expired","current",1,null], ["expired","pending_rotation",2,"past"],
    ["active","replaced",3,null], ["revoked","revoked",1,null], ["revoked","expired_unactivated",2,null] ];
  for (let n=0;n<versions.length;n++) {
    const [parent,state,ordinal,expiry]=versions[n];
    const expression=expiry===null ? "NULL" : `${NOW_US_SQL}${expiry==="future"?"+900000000":"-1000000"}`;
    statements.push(db.prepare(`INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal,expires_at_us) VALUES(?,?,?,?,?,${expression})`).bind(`v${n}`,parent,hashes[n],state,ordinal));
  }
  statements.push(db.prepare("INSERT INTO submission_blocks(photo_id,group_id,first_reason,source_attempt_id) VALUES('photo','group','delivery_uncertain','fixture-attempt')"));
  statements.push(db.prepare("INSERT INTO audit_events(event_id,user_id,action,request_correlation_id,outcome,reason) VALUES(?,'fixture-owner','fixture.provision','fixture-request','succeeded','synthetic')").bind(crypto.randomUUID()));
  try { await db.batch(statements); }
  catch (error) { if(!await sameFixture()) throw error; }
  // Concurrent/repeated setup uses the same seven natural version IDs and
  // digests. One atomic batch wins; unique constraints roll back every loser.

}
const DENIED: [string,string][] = [
  ["installation.creation","UPDATE installations SET created_at_utc='changed'"],
  ["installation.revocation_terminal","UPDATE installations SET state='active',current_version_id='v5',revision=4 WHERE installation_id='revoked'"],
  ["version.creation","UPDATE installation_credential_versions SET created_at_utc='changed'"],
  ["version.expiry","UPDATE installation_credential_versions SET expires_at_us=expires_at_us+1 WHERE state='pending_rotation'"],
  ["block.update","UPDATE submission_blocks SET first_reason='flickr_code_6'"],
  ["block.delete","DELETE FROM submission_blocks"],
  ["block.replace","INSERT OR REPLACE INTO submission_blocks SELECT * FROM submission_blocks"],
  ["block.upsert","INSERT INTO submission_blocks SELECT * FROM submission_blocks WHERE 1 ON CONFLICT DO UPDATE SET first_reason='flickr_code_6'"],
  ["audit.update","UPDATE audit_events SET reason='changed'"],
  ["audit.delete","DELETE FROM audit_events"],
  ["audit.replace","INSERT OR REPLACE INTO audit_events SELECT * FROM audit_events"],
  ["audit.upsert","INSERT INTO audit_events SELECT * FROM audit_events WHERE 1 ON CONFLICT DO UPDATE SET reason='changed'"],
  ["parent.delete_restricted","DELETE FROM fga_users"],
  ["installation.delete","DELETE FROM installations"],
  ["installation.missing_current","UPDATE installations SET current_version_id='absent',revision=revision+1 WHERE installation_id='active'"],
  ["installation.identity","UPDATE installations SET credential_class='different'"],
  ["installation.revision","UPDATE installations SET revision=0"],
  ["version.delete","DELETE FROM installation_credential_versions"],
  ["version.digest","UPDATE installation_credential_versions SET credential_digest='broken'"],
  ["version.reverse_pointer","UPDATE installation_credential_versions SET state='replaced' WHERE version_id='v0'"],
  ["version.reactivation","UPDATE installation_credential_versions SET state='current' WHERE version_id='v4'"],
];
export default {
 async fetch(request: Request,env: Env): Promise<Response> {
  const path=new URL(request.url).pathname;
  if (path.startsWith("/__proof/")) {
   if (Date.now()>Number(env.PROOF_EXPIRES) || request.headers.get("Authorization")!==`Bearer ${env.PROOF_TOKEN}`) return new Response(null,{status:401});
   try {
    let result: unknown;
    if (path==="/__proof/status" && ["GET","POST"].includes(request.method)) {
      result={snapshot:await snapshot(env.DB), counts:await env.DB.prepare("SELECT (SELECT COUNT(*) FROM installations) installations,(SELECT COUNT(*) FROM submission_blocks) blocks,(SELECT COUNT(*) FROM audit_events) audits").first(),
        clock:await env.DB.prepare(`SELECT strftime('%Y-%m-%dT%H:%M:%f','now') || '000Z' AS utc,CAST(${NOW_US_SQL} AS TEXT) AS epoch_us`).first()};
    } else if (path==="/__proof/seed" && request.method==="POST") {
      const input=await request.json() as {credentials:string[]}; await seed(env.DB,input.credentials); result={seeded:true};
    } else if (path==="/__proof/guards" && request.method==="POST" && env.PROOF_MODE==="guards") {
      const before=await snapshot(env.DB), cases=[];
      for (const [id,sql] of DENIED) {
        let denied=false; try { await env.DB.prepare(sql).run(); } catch { denied=true; }
        cases.push({id,passed:denied && await snapshot(env.DB)===before});
      }
      let denied=false;
      try { await env.DB.batch([env.DB.prepare("INSERT INTO submission_blocks(photo_id,group_id,first_reason,source_attempt_id) VALUES('rollback','group','delivery_uncertain','fixture')"),env.DB.prepare("DELETE FROM audit_events")]); } catch { denied=true; }
      cases.push({id:"batch.failure_rollback",passed:denied && await snapshot(env.DB)===before});
      result={cases};
    } else if (path==="/__proof/ordinary" && request.method==="GET" && env.PROOF_MODE==="read") {
      // Test-only adapter exercises the shared pending-scope rule; this route is not production API.
      const headers=new Headers(request.headers); headers.set("Authorization",headers.get("X-Fixture-Credential")??""); headers.delete("X-Fixture-Credential");
      const result=await authenticate(new Request("https://fixture.invalid/",{headers}),d1Lookup(env.DB),false);
      if(result instanceof Response) return tagged(result,env);
      return Response.json({scopeAuthorized:true},{headers:{"Cache-Control":"no-store"}});
    } else return new Response(null,{status:404});
    return Response.json({build:env.PROOF_BUILD,result},{headers:{"Cache-Control":"no-store"}});
   } catch { return Response.json({build:env.PROOF_BUILD,error:"proof_failed"},{status:409,headers:{"Cache-Control":"no-store"}}); }
  }
  return tagged(await api.fetch(request,env),env);
 }
} satisfies ExportedHandler<Env>;
