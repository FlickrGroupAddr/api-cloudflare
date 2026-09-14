// Wrangler/Miniflare require Node; Python owns provisioning and cleanup.
import {readFile} from "node:fs/promises";
import {Miniflare} from "miniflare";
import {maybeStartOrUpdateRemoteProxySession} from "wrangler";
const path=process.argv[2], config=JSON.parse(await readFile(path,"utf8"));
if(!/^fga-restore-[a-f0-9]{24}$/.test(config.name)||
 config.d1_databases?.length!==1||config.d1_databases[0].database_name!==config.name+"-remote-binding"||
 config.d1_databases[0].remote!==true)throw new Error("disposable_database_config_required");
let session, mf;
try {
 session=await maybeStartOrUpdateRemoteProxySession({path});
 if(!session)throw new Error("remote_session_missing");
 await session.session.ready;
 mf=new Miniflare({modules:true,script:"export default {fetch(){return new Response('test')}}",
  compatibilityDate:"2026-07-30",cf:false,telemetry:{enabled:false},
  d1Databases:{DB:{id:config.d1_databases[0].database_id,
   remoteProxyConnectionString:session.session.remoteProxyConnectionString}}});
 const db=await mf.getD1Database("DB");
 await db.batch([db.prepare("CREATE TABLE remote_binding_marker(value INTEGER NOT NULL) STRICT"),
                 db.prepare("INSERT INTO remote_binding_marker VALUES(42)")]);
 const row=await db.prepare("SELECT value FROM remote_binding_marker").first();
 if(row?.value!==42)throw new Error("remote_binding_query_mismatch");
 console.log(JSON.stringify({remoteBindingRoundTrip:true}));
} finally {
 await mf?.dispose();
 await session?.session.dispose();
}
