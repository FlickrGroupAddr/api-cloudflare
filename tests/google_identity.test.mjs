import test from "node:test";
import assert from "node:assert/strict";
import {generateKeyPair,exportJWK,SignJWT} from "jose";
import {sqlStore} from "./sql_store.mjs";
import {validateGoogle,refreshGoogleKeys} from "../src/google_identity.ts";
import {digest,randomToken} from "../src/browser_sessions.ts";
import {nativeWriter} from "../src/native_writer.ts";
test("maintained Google verifier accepts only current signed audience issuer nonce and owner claims",async()=>{
 const db=sqlStore(),pair=await generateKeyPair("RS256"),jwk={...await exportJWK(pair.publicKey),kid:"test-key",alg:"RS256",use:"sig"};let calls=0;const fetcher=async req=>{calls++;assert.equal(req.url,"https://www.googleapis.com/oauth2/v3/certs");return Response.json({keys:[jwk]},{headers:{"Cache-Control":"public, max-age=3600"}});};
 await refreshGoogleKeys(db,fetcher);assert.equal(calls,1);const nonce=randomToken(),now=Math.floor(Date.now()/1000);
 const token=async(overrides={},header={})=>new SignJWT({iss:"https://accounts.google.com",aud:"client",sub:"subject",nonce,iat:now,exp:now+3600,...overrides}).setProtectedHeader({alg:"RS256",kid:"test-key",...header}).sign(pair.privateKey);
 assert.equal(await validateGoogle(db,await token(),"client",digest(nonce),fetcher),"subject");assert.equal(calls,1);
 for(const claims of [{iss:"https://evil.example"},{aud:"other"},{nonce:"wrong"},{exp:now-1},{nbf:now+30},{azp:"other"},{sub:null}])await assert.rejects(validateGoogle(db,await token(claims),"client",digest(nonce),fetcher),/invalid_google_assertion/);
 await assert.rejects(validateGoogle(db,await token({}, {jku:"https://evil.example"}),"client",digest(nonce),fetcher));assert.equal(calls,1);
 db.raw.exec("UPDATE google_jwks_cache SET expires_at_us=0");await assert.rejects(validateGoogle(db,await token(),"client",digest(nonce),fetcher));db.raw.close();
});
test("JWKS failure preserves prior cache and coalesces concurrent refresh",async()=>{const db=sqlStore();let release;const wait=new Promise(r=>release=r);let calls=0;const fetcher=async()=>{calls++;await wait;throw new Error("upstream unavailable");};const first=refreshGoogleKeys(db,fetcher,true);await new Promise(r=>setTimeout(r,0));await refreshGoogleKeys(db,fetcher,true);release();await first;assert.equal(calls,1);await refreshGoogleKeys(db,fetcher,true);assert.equal(calls,1);db.raw.close();});
test("native writer has one fixed target and no mutation retry",async()=>{let count=0;const writer=nativeWriter("a".repeat(32),"b".repeat(32),"c".repeat(32),{get:async()=>"synthetic-token"},async request=>{count++;assert.equal(request.method,"PATCH");assert.equal(request.redirect,"manual");assert.equal(new URL(request.url).host,"api.cloudflare.com");assert.deepEqual(await request.json(),{value:"retired",scopes:["workers"]});throw new Error("lost");});await assert.rejects(writer.replace("retired"),/writer_mutation_unconfirmed/);assert.equal(count,1);assert.throws(()=>nativeWriter("../../other","b".repeat(32),"c".repeat(32),{}));});
