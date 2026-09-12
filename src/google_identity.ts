import {OAuth2Client} from "google-auth-library";
import {decodeProtectedHeader} from "jose";
import {createPublicKey} from "node:crypto";
import type {SqlStore} from "./admission.ts";
import {NOW_US_SQL as NOW} from "./installations.ts";
import {digest,BrowserAuthError} from "./browser_sessions.ts";
import {readJson,type FlickrFetch} from "./flickr_reads.ts";
const GOOGLE_KEYS="https://www.googleapis.com/oauth2/v3/certs";
interface KeyCache {keys_json:string|null;expires_at_us:number;refresh_after_us:number;refresh_owner:string|null;refresh_until_us:number;now:number;}
const cache=(db:SqlStore)=>db.prepare(`SELECT *,${NOW} now FROM google_jwks_cache WHERE singleton=1`).first<KeyCache>();
export async function refreshGoogleKeys(db:SqlStore,fetcher:FlickrFetch,force=false):Promise<void>{
 const owner=crypto.randomUUID();
 const won=await db.prepare(`UPDATE google_jwks_cache SET refresh_owner=?,refresh_until_us=${NOW}+15000000 WHERE singleton=1 AND refresh_until_us<=${NOW} AND (?=1 OR refresh_after_us<=${NOW}) RETURNING singleton`).bind(owner,force?1:0).first();
 if(!won)return;
 try {
  let freshness=0;
  const result=await readJson(new Request(GOOGLE_KEYS,{redirect:"manual",headers:{Accept:"application/json"}}),async request=>{
   const response=await fetcher(request);const maxAge=/(?:^|,)\s*max-age=(\d+)(?:,|$)/i.exec(response.headers.get("Cache-Control")??"");
   const age=Number(response.headers.get("Age")??"0");
   if(!maxAge||!Number.isFinite(age)||age<0)throw new Error("invalid_cache_authority");freshness=Math.min(Number(maxAge[1])-age,86400);if(freshness<=30)throw new Error("expired_cache_authority");return response;
  });
  if(!Array.isArray(result.keys)||result.keys.length<1||result.keys.length>10)throw new Error("invalid_keys");
  const certs:Record<string,string>={};
  for(const key of result.keys){if(!key||typeof key!=="object"||typeof key.kid!=="string"||!/^[A-Za-z0-9_-]{1,128}$/.test(key.kid)||key.kty!=="RSA"||key.alg!=="RS256"||key.use!=="sig"||typeof key.n!=="string"||typeof key.e!=="string"||certs[key.kid])throw new Error("invalid_keys");
   certs[key.kid]=createPublicKey({key,format:"jwk"}).export({type:"spki",format:"pem"}).toString();}
  const refresh=Math.max(1,Math.min(21600,freshness*0.8)*(0.9+crypto.getRandomValues(new Uint32Array(1))[0]/4294967296*0.1));
  await db.prepare(`UPDATE google_jwks_cache SET keys_json=?,expires_at_us=${NOW}+?,refresh_after_us=${NOW}+?,refresh_owner=NULL,refresh_until_us=0 WHERE singleton=1 AND refresh_owner=?`).bind(JSON.stringify(certs),Math.floor(freshness*1000000),Math.floor(refresh*1000000),owner).run();
 }catch{
  // Keep valid old keys; shared cooldown bounds repeated unknown-kid pressure.
  await db.prepare(`UPDATE google_jwks_cache SET refresh_after_us=${NOW}+60000000,refresh_until_us=${NOW}+60000000,refresh_owner=NULL WHERE singleton=1 AND refresh_owner=?`).bind(owner).run();
 }
}
export async function validateGoogle(db:SqlStore,credential:string,audience:string,nonceDigest:string,fetcher:FlickrFetch):Promise<string>{
 try {
  if(!audience||credential.length>16384)throw new Error();
  const header=decodeProtectedHeader(credential);if(header.alg!=="RS256"||typeof header.kid!=="string"||header.kid.length>128||header.jku||header.jwk||header.x5u||header.crit)throw new Error();
  let current=await cache(db),certs:Record<string,string>=current?.keys_json?JSON.parse(current.keys_json):{};
  if(!certs[header.kid]){
   await refreshGoogleKeys(db,fetcher,true);
   // Join only an already-in-flight bounded refresh; never initiate another attempt.
   for(let i=0;i<20;i++){current=await cache(db);if(!current?.refresh_owner)break;await new Promise(resolve=>setTimeout(resolve,100));}
   current=await cache(db);certs=current?.keys_json?JSON.parse(current.keys_json):{};
  }
  if(!current||current.expires_at_us<=current.now||!certs[header.kid])throw new Error();
  const ticket=await new OAuth2Client().verifySignedJwtWithCertsAsync(credential,certs,audience,["accounts.google.com","https://accounts.google.com"],86400);
  const payload=ticket.getPayload() as unknown as {sub?:unknown;nonce?:unknown;exp?:unknown;iat?:unknown;nbf?:unknown;azp?:unknown};
  if(!payload||typeof payload.sub!=="string"||payload.sub.length<1||payload.sub.length>255||typeof payload.nonce!=="string"||digest(payload.nonce)!==nonceDigest||typeof payload.exp!=="number"||payload.exp*1000000<=current.now||typeof payload.iat!=="number"||payload.iat*1000000>current.now+300000000||(payload.nbf!==undefined&&(typeof payload.nbf!=="number"||payload.nbf*1000000>current.now))||(payload.azp!==undefined&&payload.azp!==audience))throw new Error();
  return payload.sub;
 }catch{throw new BrowserAuthError("invalid_google_assertion");}
}
