import type {SqlStore} from "./admission.ts";
import {NOW_US_SQL as NOW} from "./installations.ts";
import {digest,randomToken,ADMIN_ORIGIN,type AdminSession} from "./browser_sessions.ts";
import {applicationEnvelope,oauthResponse,signedOAuthEndpoint,verifyCandidateCredential,type FlickrFetch,type SecretReads} from "./flickr_reads.ts";
import {beginLifecycle,dispatchLifecycle,reconcileLifecycle,type NativeWriter} from "./native_lifecycle.ts";
export interface OAuthSlots {read(index:number):Promise<string>;writer(index:number):NativeWriter;}
interface Transaction {transaction_id:string;user_id:string;session_id:string;generation:string;slot:number;expected_revision:number;phase:string;expires_at_us:number;request_token_digest:string|null;operation_id:string|null;retirement_generation:string|null;}
export class FlickrOAuthError extends Error {}
const evidence=(db:SqlStore,user:string,action:string,id:string)=>db.prepare("INSERT INTO audit_events(event_id,user_id,action,request_correlation_id,outcome,reason,target_id) VALUES(?,?,?,?,'succeeded','guarded_oauth_transition',?)").bind(crypto.randomUUID(),user,action,id,id);
export async function observeStagedSlot(read:()=>Promise<string>,expected:{schemaVersion:1;generation:string;transactionId:string;token:string;tokenSecret:string},pause:()=>Promise<void>=()=>new Promise(resolve=>setTimeout(resolve,2000))):Promise<void>{
 for(let attempt=0;attempt<16;attempt++){
  try{const observed=JSON.parse(await read());if(Object.keys(observed).sort().join()==="generation,schemaVersion,token,tokenSecret,transactionId"&&observed.schemaVersion===1&&observed.generation===expected.generation&&observed.transactionId===expected.transactionId&&observed.token===expected.token&&observed.tokenSecret===expected.tokenSecret)return;}catch{}
  if(attempt<15)await pause();
 }
 throw new FlickrOAuthError("native_staging_unconfirmed");
}
export async function startFlickrOAuth(db:SqlStore,session:AdminSession,revision:number,secrets:SecretReads,slots:OAuthSlots,fetcher:FlickrFetch):Promise<unknown>{
 if(!Number.isSafeInteger(revision)||revision<1)throw new FlickrOAuthError("stale_connection");
 const app=applicationEnvelope(await secrets.FLICKR_APPLICATION.get()),id=crypto.randomUUID(),state=randomToken(),generation=crypto.randomUUID();
 const tx=crypto.randomUUID();let row:Transaction;
 try{const rows=await db.batch([
 db.prepare(`INSERT INTO transaction_guards(transaction_id,approved) SELECT ?,EXISTS(SELECT 1 FROM admin_sessions s JOIN flickr_links l ON l.user_id=s.user_id JOIN flickr_connection_state c ON c.user_id=l.user_id WHERE s.session_id=? AND s.user_id=? AND s.revoked_at_us IS NULL AND s.expires_at_us>${NOW} AND l.link_revision=? AND c.operation_id IS NULL AND c.state NOT IN ('replacing','repair_required','disconnecting')) AND (SELECT COUNT(*) FROM flickr_oauth_transactions WHERE expires_at_us>${NOW} AND phase NOT IN ('consumed','retiring','retired'))<5`).bind(tx,session.sessionId,session.userId,revision),
 db.prepare(`INSERT INTO flickr_oauth_transactions(transaction_id,user_id,session_id,state_digest,slot,generation,expected_revision,phase,created_at_us,expires_at_us) SELECT ?,?,?,?,(SELECT value FROM json_each('[0,1,2,3,4]') WHERE NOT EXISTS(SELECT 1 FROM flickr_oauth_transactions t WHERE t.slot=value AND t.phase<>'retired') ORDER BY value LIMIT 1),?,?,'initializing',${NOW},${NOW}+300000000 RETURNING *`).bind(id,session.userId,session.sessionId,digest(state),generation,revision),
 evidence(db,session.userId,"flickr.authorization_started",id),db.prepare("DELETE FROM transaction_guards WHERE transaction_id=?").bind(tx)]);row=rows[1].results[0] as unknown as Transaction;}catch{throw new FlickrOAuthError("oauth_start_unavailable");}
 try{
  const pair=await oauthResponse(signedOAuthEndpoint("request_token",app,null,ADMIN_ORIGIN+"/admin/flickr-oauth/callback?state="+state),fetcher);
  await slots.writer(row.slot).replace(JSON.stringify({schemaVersion:1,generation,transactionId:id,...pair}));
  await observeStagedSlot(()=>slots.read(row.slot),{schemaVersion:1,generation,transactionId:id,...pair});
  const updated=await db.prepare(`UPDATE flickr_oauth_transactions SET phase='ready',request_token_digest=? WHERE transaction_id=? AND phase='initializing' AND expires_at_us>${NOW} RETURNING transaction_id`).bind(digest(pair.token),id).first();if(!updated)throw new Error();
  return {schemaVersion:1,authorizationTransactionId:id,authorizationUrl:"https://www.flickr.com/services/oauth/authorize?oauth_token="+encodeURIComponent(pair.token),expiresAt:new Date(row.expires_at_us/1000).toISOString().replace("Z","000Z")};
 }catch{await db.prepare("UPDATE flickr_oauth_transactions SET phase='repair_required' WHERE transaction_id=? AND phase='initializing'").bind(id).run();throw new FlickrOAuthError("oauth_start_unavailable");}
}
export async function completeFlickrOAuth(db:SqlStore,state:string,token:string,verifier:string,secrets:SecretReads,slots:OAuthSlots,grantWriter:NativeWriter,fetcher:FlickrFetch,ownerSub?:string):Promise<boolean>{
 if(!/^[A-Za-z0-9_-]{43}$/.test(state)||!token||token.length>2048||!verifier||verifier.length>2048)return false;
 const row=await db.prepare(`SELECT t.* FROM flickr_oauth_transactions t JOIN admin_sessions s ON s.session_id=t.session_id JOIN flickr_links l ON l.user_id=t.user_id WHERE t.state_digest=? AND t.request_token_digest=? AND t.phase='ready' AND t.expires_at_us>${NOW} AND s.revoked_at_us IS NULL AND s.expires_at_us>${NOW} AND l.link_revision=t.expected_revision`).bind(digest(state),digest(token)).first<Transaction>();if(!row)return false;
 let temporary:{token:string;tokenSecret:string;generation:string;transactionId:string;schemaVersion:number};
 try{temporary=JSON.parse(await slots.read(row.slot));if(Object.keys(temporary).sort().join()!=="generation,schemaVersion,token,tokenSecret,transactionId"||temporary.schemaVersion!==1||temporary.generation!==row.generation||temporary.transactionId!==row.transaction_id||temporary.token!==token||typeof temporary.tokenSecret!=="string")return false;}catch{return false;}
 // Exactly one callback may attempt the access-token exchange, including after response loss.
 const claimed=await db.prepare(`UPDATE flickr_oauth_transactions SET phase='exchanging' WHERE transaction_id=? AND phase='ready' AND expires_at_us>${NOW} AND EXISTS(SELECT 1 FROM admin_sessions s JOIN admin_principals p ON p.user_id=s.user_id WHERE s.session_id=flickr_oauth_transactions.session_id AND s.revoked_at_us IS NULL AND s.expires_at_us>${NOW} AND (? IS NULL OR p.google_sub=?)) RETURNING transaction_id`).bind(row.transaction_id,ownerSub??null,ownerSub??null).first();if(!claimed)return false;
 try{
  const appRaw=await secrets.FLICKR_APPLICATION.get(),app=applicationEnvelope(appRaw);
  const pair=await oauthResponse(signedOAuthEndpoint("access_token",app,temporary,verifier),fetcher);
  const owner=await db.prepare("SELECT owner_nsid owner FROM flickr_links WHERE user_id=?").bind(row.user_id).first<{owner:string}>();if(!owner)throw new Error();
  // A wrong owner/permission cannot pause or replace the previous active grant.
  await verifyCandidateCredential(JSON.stringify({schemaVersion:1,generation:row.generation,...pair}),appRaw,row.generation,owner.owner,fetcher);
  const op=await beginLifecycle(db,row.user_id,row.expected_revision,"replace",ownerSub?{sessionId:row.session_id,googleSub:ownerSub}:undefined);
  await db.prepare("UPDATE flickr_oauth_transactions SET operation_id=? WHERE transaction_id=? AND phase='exchanging'").bind(op.operationId,row.transaction_id).run();
  await dispatchLifecycle(db,op.operationId,grantWriter,pair);
  const activated=await reconcileLifecycle(db,op.operationId,secrets,fetcher);
  await db.prepare("UPDATE flickr_oauth_transactions SET phase='consumed' WHERE transaction_id=? AND phase='exchanging'").bind(row.transaction_id).run();
  return activated;
 }catch{await db.prepare("UPDATE flickr_oauth_transactions SET phase='repair_required' WHERE transaction_id=? AND phase='exchanging'").bind(row.transaction_id).run();return false;}
}
// Retire only known settled temporary writes. Unknown initializing writes remain owned for repair.
export async function retireOAuthSlot(db:SqlStore,id:string,slots:OAuthSlots):Promise<boolean>{
 const row=await db.prepare(`SELECT * FROM flickr_oauth_transactions WHERE transaction_id=? AND (phase='consumed' OR (phase='ready' AND expires_at_us<=${NOW}))`).bind(id).first<Transaction>();if(!row)return false;
 const generation=crypto.randomUUID();const claimed=await db.prepare("UPDATE flickr_oauth_transactions SET phase='retiring',retirement_generation=? WHERE transaction_id=? AND phase=? RETURNING transaction_id").bind(generation,id,row.phase).first();if(!claimed)return false;
 try{await slots.writer(row.slot).replace(JSON.stringify({schemaVersion:1,generation,retired:true}));}catch{/* Observe the matching retirement; never retry an unknown mutation. */}
 return observeOAuthRetirement(db,id,slots);
}
export async function observeOAuthRetirement(db:SqlStore,id:string,slots:OAuthSlots):Promise<boolean>{const row=await db.prepare("SELECT * FROM flickr_oauth_transactions WHERE transaction_id=? AND phase='retiring'").bind(id).first<Transaction>();if(!row)return false;
 try{const value=JSON.parse(await slots.read(row.slot));if(Object.keys(value).sort().join()!=="generation,retired,schemaVersion"||value.schemaVersion!==1||value.retired!==true||value.generation!==row.retirement_generation)return false;
 const tx=crypto.randomUUID();await db.batch([db.prepare("INSERT INTO transaction_guards(transaction_id,approved) SELECT ?,EXISTS(SELECT 1 FROM flickr_oauth_transactions WHERE transaction_id=? AND phase='retiring' AND retirement_generation=?)").bind(tx,id,row.retirement_generation),db.prepare("UPDATE flickr_oauth_transactions SET phase='retired' WHERE transaction_id=?").bind(id),evidence(db,row.user_id,"flickr.oauth_payload_retired",id),db.prepare("DELETE FROM transaction_guards WHERE transaction_id=?").bind(tx)]);return true;}catch{return false;}}
