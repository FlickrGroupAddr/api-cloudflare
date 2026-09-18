// Isolated synthetic fixture; never exported by the production Worker.
import {createWorker,type Env} from '../../src/worker.ts';
import {refreshGroups} from '../../src/group_discovery.ts';
import {credentialDigest} from '../../src/installations.ts';
interface ProbeEnv { DB:D1Database; PROOF_TOKEN:string; PROOF_EXPIRES:string; }
const secrets = {
 FLICKR_APPLICATION:{get:async()=>JSON.stringify({schemaVersion:1,consumerKey:'app',consumerSecret:'secret'})},
 FLICKR_GRANT:{get:async()=>JSON.stringify({schemaVersion:1,generation:'gen',token:'token',tokenSecret:'token-secret'})},
};
export default {
 async fetch(request:Request,env:ProbeEnv):Promise<Response>{
  if(!Number.isFinite(Number(env.PROOF_EXPIRES))||Date.now()>Number(env.PROOF_EXPIRES))return new Response(null,{status:410});
  const url=new URL(request.url);
  if(url.pathname.startsWith('/probe/')){
   if(request.headers.get('Authorization')!=='Bearer '+env.PROOF_TOKEN)return new Response(null,{status:401});
   if(url.pathname==='/probe/seed'){
    const digest=await credentialDigest('0000-'.repeat(12)+'0000');
    await env.DB.batch([
     env.DB.prepare("INSERT INTO fga_users VALUES('user')"),
     env.DB.prepare("INSERT INTO installations(installation_id,user_id,credential_class,state,revision,current_version_id) VALUES('install','user','lrc_plugin','active',1,'version')"),
     env.DB.prepare("INSERT INTO installation_credential_versions(version_id,installation_id,credential_digest,state,ordinal) VALUES('version','install',?,'current',1)").bind(digest),
     env.DB.prepare("INSERT INTO flickr_links VALUES('user','owner',1,'linked')"),
     env.DB.prepare("INSERT INTO flickr_native_credentials(user_id,active_generation,link_revision,verified_owner_nsid,verified_permission) VALUES('user','gen',1,'owner','write')"),
    ]);
    return Response.json({seeded:true});
   }
   if(url.pathname==='/probe/refresh'){
    await refreshGroups(env.DB,secrets,async request=>{
     const u=new URL(request.url);
     if(u.searchParams.get('method')!=='flickr.groups.pools.getGroups'||!request.headers.has('Authorization'))throw new Error('wrong_fixture_call');
     return Response.json({stat:'ok',groups:{page:1,pages:1,per_page:400,total:3,
      group:[{nsid:'z',name:'Last'},{nsid:'A',name:'First'},{nsid:'a',name:'Second'}]}});
    });
    return Response.json({ran:true});
   }
   return new Response(null,{status:404});
  }
  return createWorker(async()=>{throw new Error('unexpected_egress');}).fetch(request,
   {DB:env.DB,...secrets,FGA_READ_ENABLED:'1',FGA_GROUPS_ENABLED:'1',FGA_INTAKE_ENABLED:'0',FGA_DISPATCH_ENABLED:'0'} as Env);
 }
} satisfies ExportedHandler<ProbeEnv>;
