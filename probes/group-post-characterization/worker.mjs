// Synthetic disposable Worker. MIT, copyright 2026 Terry Ott. No outbound fetch.
export const VERSION='fga-group-post-v1';
export const LIMITS={requests:64,requestBytes:16384,responseBytes:2097153,delayMs:16000,lifetime:1200,cleanupMargin:240};
export const PROOF='{"schemaVersion":1,"flickrPhotoId":"SYNTHETIC-PHOTO","expectedLinkedFlickrRevision":1}';
export const batch=n=>JSON.stringify({schemaVersion:2,photoBinding:{fgaPhotoBindingId:'SYNTHETIC-BINDING',expectedVerificationRevision:1},flickrGroupIds:Array.from({length:n},(_,i)=>'SYNTHETIC-GROUP-'+String(i+1).padStart(2,'0'))});
export const CASES=['proof','batch-one','batch-sixty','status-400','status-401','status-409','status-429','status-503','oversize-success','oversize-error','timeout','cancel','lost-response',...[301,302,303,307,308].flatMap(s=>['same-'+s,'cross-'+s])];
export const expected=id=>id==='proof'?PROOF:batch(id==='batch-sixty'?60:1);
export const origins=e=>({source:`https://fga-post-src-${e.RUN_ID}.${e.SUBDOMAIN}.workers.dev`,receiver:`https://fga-post-recv-${e.RUN_ID}.${e.SUBDOMAIN}.workers.dev`});
function valid(e,t) {return ['source','receiver'].includes(e.ROLE)&&/^[a-f0-9]{24}$/.test(e.RUN_ID)&&e.RUN_ID!=='0'.repeat(24)&&/^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(e.SUBDOMAIN)&&/^SYNTHETIC-[a-f0-9]{32}$/.test(e.CANARY??'')&&/^[a-f0-9]{64}$/.test(e.ACCESS??'')&&/^[1-9][0-9]{9,10}$/.test(e.EXPIRES??'')&&+e.EXPIRES>t&&+e.EXPIRES-t<=LIMITS.lifetime;}
function reply(body,status=200,extra={}) {return new Response(typeof body==='string'?body:JSON.stringify(body),{status,headers:{'Content-Type':'application/json','Cache-Control':'no-store','X-FGA-Post-Probe':VERSION,'X-Content-Type-Options':'nosniff',...extra}});}
async function bounded(req) {
  const length=req.headers.get('Content-Length');
  if(length!==null&&(!/^\d+$/.test(length)||+length>LIMITS.requestBytes)) return null;
  if(!req.body) return new Uint8Array();
  const reader=req.body.getReader(),chunks=[];let size=0;
  try {while(true){const {done,value}=await reader.read();if(done)break;size+=value.byteLength;if(size>LIMITS.requestBytes){await reader.cancel();return null;}chunks.push(value);}} finally {reader.releaseLock();}
  const bytes=new Uint8Array(size);let offset=0;for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.byteLength;}return bytes;
}
export function createProbe({now=()=>Date.now()/1000,sleep=ms=>new Promise(r=>setTimeout(r,ms))}={}) {
  return {async fetch(req,e) { try {
    if(!valid(e,now()))return reply({error:'expired_or_unconfigured'},410);
    const u=new URL(req.url),o=origins(e),deny=()=>reply({error:'not_found'},404);
    if(u.origin!==o[e.ROLE]||u.search||u.hash)return deny();
    const report=u.pathname==='/v1/report',receive=u.pathname.startsWith('/v1/receive/'),id=u.pathname.split('/').at(-1);
    if(report){if(req.method!=='GET'||req.headers.has('Authorization')||req.headers.get('X-FGA-Post-Access')!==e.ACCESS)return deny();}
    else {
      if(!CASES.includes(id)||!['GET','POST'].includes(req.method))return deny();
      if(receive){if(u.pathname!=='/v1/receive/'+id||(e.ROLE==='receiver'?!id.startsWith('cross-'):!id.startsWith('same-')))return deny();}
      else if(e.ROLE!=='source'||u.pathname!=='/v1/cases/'+id||req.method!=='POST'||req.headers.get('X-FGA-Post-Access')!==e.ACCESS||req.headers.get('Authorization')!=='Bearer '+e.CANARY)return deny();
    }
    // Shared atomic admission precedes reading the body. No isolate-local cap.
    const charge=await e.DB.prepare('UPDATE post_budget SET requests=requests+1 WHERE run_id=? AND role=? AND expires_at=? AND expires_at>unixepoch() AND requests<64 RETURNING requests').bind(e.RUN_ID,e.ROLE,+e.EXPIRES).first();
    if(!charge)return reply({error:'budget_or_expiry'},429);
    if(report){const rows=await e.DB.prepare('SELECT role,case_id,method,body_bytes,body_matches,authorization_present,canary_matches,content_type_matches FROM post_observations WHERE run_id=? ORDER BY role,case_id').bind(e.RUN_ID).all();return reply({schemaVersion:1,runId:e.RUN_ID,observations:rows.results});}
    const bytes=await bounded(req);if(bytes===null)return reply({error:'request_oversize'},413);
    const bodyMatch=new TextDecoder().decode(bytes)===expected(id),auth=req.headers.has('Authorization'),canary=req.headers.get('Authorization')==='Bearer '+e.CANARY,media=req.headers.get('Content-Type')==='application/json';
    await e.DB.prepare('INSERT INTO post_observations(run_id,role,case_id,method,body_bytes,body_matches,authorization_present,canary_matches,content_type_matches) VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT DO NOTHING').bind(e.RUN_ID,e.ROLE,(receive?'receive-':'')+id,req.method,bytes.length,+bodyMatch,+auth,+canary,+media).run();
    if(!receive&&(!bodyMatch||!media))return reply({error:'synthetic_shape_mismatch'},400);
    if(!valid(e,now()))return reply({error:'expired'},410);
    if(receive)return reply({schemaVersion:1,received:true});
    if(id.startsWith('same-')||id.startsWith('cross-'))return reply('',+id.split('-')[1],{Location:o[id.startsWith('cross-')?'receiver':'source']+'/v1/receive/'+id});
    if(['timeout','cancel','lost-response'].includes(id))await sleep(LIMITS.delayMs);
    if(!valid(e,now()))return reply({error:'expired'},410);
    if(id.startsWith('oversize-'))return reply('x'.repeat(LIMITS.responseBytes),id==='oversize-error'?503:202);
    if(id.startsWith('status-'))return reply({schemaVersion:1,error:'synthetic_failure'},+id.slice(7),id==='status-429'?{'Retry-After':'2'}:id==='status-401'?{'WWW-Authenticate':'Bearer error="invalid_token"'}:{});
    return reply({schemaVersion:1,synthetic:true},id==='proof'?200:202);
  } catch {return reply({error:'observation_unavailable'},503);}
  }};
}
export default createProbe();
