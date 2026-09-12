import test from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import {relayCallback,acceptCallback,findAuthorizationUrl} from "../scripts/cloudflare_login_bridge.mjs";
test("stale callbacks cannot terminate or reach the current Wrangler login",async()=>{
 let forwarded=0;const backend=http.createServer((req,res)=>{forwarded++;res.writeHead(307,{Location:"https://dash.cloudflare.com/oauth2/consent-granted"});res.end();});await new Promise(resolve=>backend.listen(0,"127.0.0.1",resolve));
 const flow={phase:"waiting",url:"https://dash.cloudflare.com/oauth2/auth?state=current-state",port:backend.address().port,claimed:false};const front=http.createServer((req,res)=>relayCallback(req,res,flow));await new Promise(resolve=>front.listen(0,"127.0.0.1",resolve));const origin="http://127.0.0.1:"+front.address().port;
 try{
  for(const query of ["state=old-state&code=old","code=missing-state","state=current-state&state=other&code=bad"]){const response=await fetch(origin+"/oauth/callback?"+query,{redirect:"manual"});assert.equal(response.status,410);await response.text();}
  assert.equal(forwarded,0);assert.equal(flow.phase,"waiting");assert.equal(flow.claimed,false);
  const success=await fetch(origin+"/oauth/callback?state=current-state&code=synthetic",{redirect:"manual"});assert.equal(success.status,303);assert.equal(success.headers.get("location"),"/result");assert.equal(forwarded,1);
  const duplicate=await fetch(origin+"/oauth/callback?state=current-state&code=synthetic",{redirect:"manual"});assert.equal(duplicate.status,303);assert.equal(forwarded,1);
  assert.equal(acceptCallback({...flow,phase:"expired"},new URL(origin+"/oauth/callback?state=current-state")),false);
 }finally{await new Promise(resolve=>front.close(resolve));await new Promise(resolve=>backend.close(resolve));}
});

test("authorization handoff parses only the official fixed callback URL",()=>{const url="https://dash.cloudflare.com/oauth2/auth?state=fresh&redirect_uri=http%3A%2F%2Flocalhost%3A8976%2Foauth%2Fcallback";assert.equal(findAuthorizationUrl("Visit this link to authenticate: "+url+"\n"),url);assert.equal(findAuthorizationUrl("Visit this link to authenticate: "+url.replace("dash.cloudflare.com","evil.example")),null);});
