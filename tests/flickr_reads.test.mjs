import test from "node:test";
import assert from "node:assert/strict";
import {verifyCandidateCredential, readJson} from "../src/flickr_reads.ts";
import {authorizationTarget} from "../prototypes/native-flickr-admin/model.mjs";
const grant=JSON.stringify({schemaVersion:1,generation:"g",token:"t",tokenSecret:"s"});
const app=JSON.stringify({schemaVersion:1,consumerKey:"k",consumerSecret:"a"});
const result=(permission="write",owner="owner",token="t")=>({stat:"ok",oauth:{token:{_content:token},perms:{_content:permission},user:{nsid:owner}}});
test("candidate validator verifies reflected token, configured owner and write authority",async()=>{
 for(const permission of ["write","delete"]){let calls=0;const verified=await verifyCandidateCredential(grant,app,"g","owner",async request=>{calls++;const url=new URL(request.url);assert.equal(url.origin,"https://www.flickr.com");assert.equal(url.searchParams.get("method"),"flickr.auth.oauth.checkToken");assert.equal(request.method,"GET");assert.equal(request.redirect,"manual");assert.match(request.headers.get("Authorization"),/oauth_nonce="[a-f0-9]{64}"/);return Response.json(result(permission));});assert.deepEqual(verified,{ownerNsid:"owner",permission});assert.equal(calls,1);}
 for(const body of [result("read"),result("write","other"),result("write","owner","other"),{stat:"fail"},{}])await assert.rejects(verifyCandidateCredential(grant,app,"g","owner",async()=>Response.json(body)),/grant_verification_failed/);
 let calls=0;await assert.rejects(verifyCandidateCredential(grant,app,"other","owner",async()=>{calls++;return Response.json(result());}),/credential_unavailable/);assert.equal(calls,0);
});
test("provider parser bounds bytes and rejects HTML, redirects and invalid UTF8",async()=>{
 for(const response of [new Response("x".repeat(262145),{headers:{"Content-Type":"application/json"}}),new Response("<html>"),new Response(null,{status:302,headers:{Location:"https://example.com"}}),new Response(new Uint8Array([255]),{headers:{"Content-Type":"application/json"}}),Response.json([])])await assert.rejects(readJson(new Request("https://www.flickr.com/"),async()=>response),/upstream_unavailable/);
});
test("browser authorization target is strictly constrained",()=>{
 const good="https://www.flickr.com/services/oauth/authorize?oauth_token=synthetic";assert.equal(authorizationTarget(good),good);
 for(const value of ["http://www.flickr.com/services/oauth/authorize?oauth_token=x",good+"&oauth_token=y",good+"&next=x",good+"#fragment",good.replace("www.flickr.com","evil.example"),good.replace("www.flickr.com","user@www.flickr.com"),good.replace("synthetic",""),good+" "])assert.throws(()=>authorizationTarget(value));
});
