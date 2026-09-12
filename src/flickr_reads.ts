import OAuth from "oauth-1.0a";
import { NOW_US_SQL } from "./installations.ts";
import type { SqlStore, AdmissionAuth } from "./admission.ts";
export interface SecretReads { FLICKR_APPLICATION:Pick<SecretsStoreSecret,"get">;FLICKR_GRANT:Pick<SecretsStoreSecret,"get">; }
export interface GrantSnapshot {userId:string;ownerNsid:string;revision:string;generation:string;}
interface Pair {token:string;tokenSecret:string;}
interface Application {consumerKey:string;consumerSecret:string;}
export class FlickrReadError extends Error {}
const opaque=(x:unknown):x is string=>typeof x==="string"&&x.length>0&&x.length<=2048&&!/[\x00-\x20\x7f]/.test(x);
function object(raw:string,keys:string[]):Record<string,unknown> {
 if(typeof raw!=="string"||raw.length>8192)throw new FlickrReadError("credential_unavailable");
 let value:unknown;try{value=JSON.parse(raw);}catch{throw new FlickrReadError("credential_unavailable");}
 if(!value||typeof value!=="object"||Array.isArray(value)||Object.keys(value).sort().join()!==keys.sort().join())throw new FlickrReadError("credential_unavailable");
 return value as Record<string,unknown>;
}
export async function linkedGrant(db:SqlStore,auth:AdmissionAuth):Promise<GrantSnapshot|null> {
 return db.prepare(`SELECT i.user_id userId,l.owner_nsid ownerNsid,CAST(l.link_revision AS TEXT) revision,n.active_generation generation
 FROM installations i JOIN installation_credential_versions v ON v.version_id=i.current_version_id AND v.installation_id=i.installation_id
 JOIN flickr_links l ON l.user_id=i.user_id JOIN flickr_native_credentials n ON n.user_id=l.user_id
 WHERE i.installation_id=? AND i.credential_class='lrc_plugin' AND i.state='active' AND v.state='current' AND v.credential_digest=?
 AND l.state='linked' AND n.operation_id IS NULL AND n.link_revision=l.link_revision AND n.verified_owner_nsid=l.owner_nsid AND n.verified_permission IN ('write','delete')`).bind(auth.installationId,auth.credentialDigest).first<GrantSnapshot>();
}
export function sameGrant(a:GrantSnapshot,b:GrantSnapshot|null):boolean {return b!==null&&a.userId===b.userId&&a.ownerNsid===b.ownerNsid&&a.revision===b.revision&&a.generation===b.generation;}
async function secret(read:Pick<SecretsStoreSecret,"get">):Promise<string> {
 let timer:ReturnType<typeof setTimeout>|undefined;
 try {return await Promise.race([read.get(),new Promise<never>((_,reject)=>{timer=setTimeout(()=>reject(new FlickrReadError("credential_unavailable")),10_000);})]);}
 catch {throw new FlickrReadError("credential_unavailable");}
 finally {if(timer!==undefined)clearTimeout(timer);}
}
export async function withGrant<T>(db:SqlStore,auth:AdmissionAuth,secrets:SecretReads,snapshot:GrantSnapshot,operation:(pair:Pair,app:Application)=>Promise<T>):Promise<T> {
 const [grantRaw,appRaw]=await Promise.all([secret(secrets.FLICKR_GRANT),secret(secrets.FLICKR_APPLICATION)]);
 const grant=object(grantRaw,["schemaVersion","generation","token","tokenSecret"]),app=object(appRaw,["schemaVersion","consumerKey","consumerSecret"]);
 if(grant.schemaVersion!==1||grant.generation!==snapshot.generation||!opaque(grant.token)||!opaque(grant.tokenSecret)||app.schemaVersion!==1||!opaque(app.consumerKey)||!opaque(app.consumerSecret))throw new FlickrReadError("credential_unavailable");
 if(!sameGrant(snapshot,await linkedGrant(db,auth)))throw new FlickrReadError("flickr_link_changed");
 return operation({token:grant.token,tokenSecret:grant.tokenSecret},{consumerKey:app.consumerKey,consumerSecret:app.consumerSecret});
}
function hmac(base:string,key:string):string {
 const process=(globalThis as unknown as {process?:{getBuiltinModule:(name:string)=>{createHmac:(algorithm:string,key:string)=>{update:(data:string)=>{digest:(encoding:string)=>string}}}}}).process;
 if(!process?.getBuiltinModule)throw new FlickrReadError("crypto_unavailable");
 return process.getBuiltinModule("crypto").createHmac("sha1",key).update(base).digest("base64");
}
export function signedRead(method:"flickr.photos.getInfo"|"flickr.auth.oauth.checkToken",photoId:string|null,pair:Pair,app:Application):Request {
 const url=new URL("https://www.flickr.com/services/rest/");url.searchParams.set("method",method);url.searchParams.set("format","json");url.searchParams.set("nojsoncallback","1");if(photoId!==null)url.searchParams.set("photo_id",photoId);
 const oauth=new OAuth({consumer:{key:app.consumerKey,secret:app.consumerSecret},signature_method:"HMAC-SHA1",hash_function:hmac});
 // The library owns OAuth canonicalization; runtime CSPRNG replaces its default nonce generator.
 oauth.getNonce=()=>Array.from(crypto.getRandomValues(new Uint8Array(32)),b=>b.toString(16).padStart(2,"0")).join("");
 return new Request(url,{method:"GET",headers:{...oauth.toHeader(oauth.authorize({url:String(url),method:"GET"},{key:pair.token,secret:pair.tokenSecret})),Accept:"application/json"},redirect:"manual"});
}
export type FlickrFetch=(request:Request)=>Promise<Response>;
export async function readJson(request:Request,fetcher:FlickrFetch):Promise<Record<string,unknown>> {
 const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),10_000);
 try {
  const response=await fetcher(new Request(request,{signal:controller.signal}));
  if(!response.ok||!/^application\/json(?:;|$)/i.test(response.headers.get("Content-Type")??""))throw new FlickrReadError("upstream_unavailable");
  if(!response.body)throw new FlickrReadError("upstream_unavailable");
  const reader=response.body.getReader();let size=0;const chunks:Uint8Array[]=[];
  for(;;){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>262144){await reader.cancel();throw new FlickrReadError("upstream_unavailable");}chunks.push(value);}
  const bytes=new Uint8Array(size);let offset=0;for(const part of chunks){bytes.set(part,offset);offset+=part.length;}
  const value:unknown=JSON.parse(new TextDecoder("utf-8",{fatal:true,ignoreBOM:false}).decode(bytes));
  if(!value||typeof value!=="object"||Array.isArray(value))throw new FlickrReadError("upstream_unavailable");
  return value as Record<string,unknown>;
 }catch(error){if(error instanceof FlickrReadError)throw error;throw new FlickrReadError("upstream_unavailable");}
 finally {clearTimeout(timer);}
}
export async function verifyPhoto(db:SqlStore,auth:AdmissionAuth,secrets:SecretReads,snapshot:GrantSnapshot,photoId:string,fetcher:FlickrFetch):Promise<void> {
 const result=await withGrant(db,auth,secrets,snapshot,(pair,app)=>readJson(signedRead("flickr.photos.getInfo",photoId,pair,app),fetcher));
 if(result.stat==="fail"&&result.code===1)throw new FlickrReadError("invalid_existing_photo");
 if(result.stat!=="ok"||!result.photo||typeof result.photo!=="object"||Array.isArray(result.photo))throw new FlickrReadError("upstream_unavailable");
 const photo=result.photo as {id?:unknown;owner?:{nsid?:unknown};visibility?:{ispublic?:unknown};media?:unknown};
 if(typeof photo.id!=="string"||!photo.owner||typeof photo.owner.nsid!=="string"||!photo.visibility||![0,1,"0","1"].includes(photo.visibility.ispublic as string|number))throw new FlickrReadError("upstream_unavailable");
 if(photo.id!==photoId||(photo.media!==undefined&&photo.media!=="photo"))throw new FlickrReadError("invalid_existing_photo");
 if(photo.owner.nsid!==snapshot.ownerNsid)throw new FlickrReadError("photo_owner_mismatch");
 if(photo.visibility.ispublic!==1&&photo.visibility.ispublic!=="1")throw new FlickrReadError("existing_photo_not_public");
}
export async function commitBinding(db:SqlStore,auth:AdmissionAuth,snapshot:GrantSnapshot,photoId:string):Promise<{created:boolean;body:unknown}> {
 const bindingId=crypto.randomUUID(),tx=crypto.randomUUID();
 const current=`EXISTS(SELECT 1 FROM installations i JOIN installation_credential_versions v ON v.version_id=i.current_version_id AND v.installation_id=i.installation_id JOIN flickr_links l ON l.user_id=i.user_id JOIN flickr_native_credentials n ON n.user_id=l.user_id WHERE i.installation_id=?1 AND i.user_id=?3 AND i.state='active' AND i.credential_class='lrc_plugin' AND v.credential_digest=?2 AND v.state='current' AND l.state='linked' AND l.owner_nsid=?4 AND l.link_revision=CAST(?5 AS INTEGER) AND n.link_revision=l.link_revision AND n.active_generation=?6 AND n.operation_id IS NULL AND n.verified_owner_nsid=l.owner_nsid AND n.verified_permission IN ('write','delete'))`;
 const params=[auth.installationId,auth.credentialDigest,snapshot.userId,snapshot.ownerNsid,snapshot.revision,snapshot.generation,photoId,bindingId,tx];
 const sql=(value:string)=>db.prepare("WITH input AS(SELECT ?1 i,?2 d,?3 u,?4 o,?5 r,?6 g,?7 p,?8 b,?9 t) "+value).bind(...params);
 const results=await db.batch([
  sql(`INSERT INTO transaction_guards(transaction_id,approved) VALUES(?9,${current} AND NOT EXISTS(SELECT 1 FROM photo_bindings WHERE photo_id=?7 AND (user_id<>?3 OR owner_nsid<>?4 OR verification_revision>=9007199254740991)))`),
  sql(`INSERT INTO photo_bindings(binding_id,user_id,photo_id,owner_nsid,link_revision,verification_revision,source_kind) SELECT ?8,?3,?7,?4,CAST(?5 AS INTEGER),1,'existing_public' WHERE NOT EXISTS(SELECT 1 FROM photo_bindings WHERE photo_id=?7)`),
  sql(`UPDATE photo_bindings SET verification_revision=verification_revision+1,link_revision=CAST(?5 AS INTEGER),verified_at_us=${NOW_US_SQL} WHERE photo_id=?7 AND binding_id<>?8 AND verification_revision<9007199254740991`),
  sql(`INSERT INTO photo_binding_events(event_id,binding_id,verification_revision,kind) SELECT lower(hex(randomblob(16))),binding_id,verification_revision,'existing_public_verified' FROM photo_bindings WHERE photo_id=?7`),
  sql(`SELECT binding_id AS fgaPhotoBindingId,photo_id AS flickrPhotoId,source_kind,link_revision AS linkedFlickrRevision,verification_revision AS verificationRevision,strftime('%Y-%m-%dT%H:%M:',verified_at_us/1000000,'unixepoch')||printf('%09.6f',(verified_at_us%60000000)/1000000.0)||'Z' AS verifiedAt,binding_id=?8 AS created FROM photo_bindings WHERE photo_id=?7`),
  sql("DELETE FROM transaction_guards WHERE transaction_id=?9")
 ]);
 const row=results[4].results[0] as unknown as {fgaPhotoBindingId:string;flickrPhotoId:string;source_kind:string;linkedFlickrRevision:number;verificationRevision:number;verifiedAt:string;created:number};
 const {source_kind,created,...body}=row;
 return {created:created===1,body:{schemaVersion:1,...body,sourceKind:source_kind==="existing_public"?"existing_public_flickr_photo":"fga_direct_upload"}};
}

// For the authenticated lifecycle service; never exposed as a credential-input HTTP route.
export async function verifyCandidateCredential(grantRaw:string,appRaw:string,generation:string,ownerNsid:string,fetcher:FlickrFetch):Promise<{ownerNsid:string;permission:"write"|"delete"}> {
 const grant=object(grantRaw,["schemaVersion","generation","token","tokenSecret"]),app=object(appRaw,["schemaVersion","consumerKey","consumerSecret"]);
 if(grant.schemaVersion!==1||grant.generation!==generation||!opaque(grant.token)||!opaque(grant.tokenSecret)||app.schemaVersion!==1||!opaque(app.consumerKey)||!opaque(app.consumerSecret))throw new FlickrReadError("credential_unavailable");
 const response=await readJson(signedRead("flickr.auth.oauth.checkToken",null,{token:grant.token,tokenSecret:grant.tokenSecret},{consumerKey:app.consumerKey,consumerSecret:app.consumerSecret}),fetcher);
 const value=response.oauth as {token?:{_content?:unknown};perms?:{_content?:unknown};user?:{nsid?:unknown}}|undefined;
 if(response.stat!=="ok"||!value||value.token?._content!==grant.token||value.user?.nsid!==ownerNsid||!['write','delete'].includes(value.perms?._content as string))throw new FlickrReadError("grant_verification_failed");
 return {ownerNsid,permission:value.perms!._content as "write"|"delete"};
}
