import test from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
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
test('shared JSON reader retains request cancellation across forced GC', { timeout: 20_000 }, async () => {
 if (typeof globalThis.gc !== 'function') {
  execFileSync(process.execPath, ['--expose-gc', '--test',
   '--test-name-pattern=^shared JSON reader retains request cancellation across forced GC$', fileURLToPath(import.meta.url)],
  { timeout: 15_000, stdio: 'pipe' });
  return;
 }
 for (const headersReceived of [false, true]) for (const useRequestSignal of [false, true]) {
  const root = new AbortController();
  let injectedSignal, entered, finish, cancelled = false;
  const started = new Promise(resolve => { entered = resolve; });
  const pending = new Promise(resolve => { finish = resolve; });
  const response = () => new Response(new ReadableStream({
   pull() { if (headersReceived) entered(); }, cancel() { cancelled = true; },
  }), { headers: { 'Content-Type': 'application/json' } });
  const rejected = assert.rejects(readJson(new Request('https://www.flickr.com/', useRequestSignal ? { signal: root.signal } : {}), request => {
   injectedSignal = request.signal;
   if (headersReceived) return Promise.resolve(response());
   entered(); return pending;
  }, undefined, useRequestSignal ? {} : { signal: root.signal }), /upstream_unavailable/);
  await started;
  for (let n = 0; n < 8; n++) {
   await new Promise(resolve => setImmediate(resolve));
   globalThis.gc();
  }
  root.abort();
  await rejected;
  assert.equal(injectedSignal.aborted, true, `request signal aborted with headersReceived=${headersReceived}`);
  if (!headersReceived) finish(response());
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(cancelled, true, `unconsumed body canceled with headersReceived=${headersReceived}`);
 }
});
test('shared reader lifetime bounds adapter ownership and refuses registration after release', async () => {
 let saved;
 const value = await readJson(new Request('https://www.flickr.com/'), async (request, lifetime) => {
  saved = lifetime;
  lifetime.retain(request);
  const inner = new Request(request);
  lifetime.retain(inner);
  lifetime.retain(inner);
  assert.throws(() => lifetime.retain(new Request(request)), /upstream_unavailable/);
  return Response.json({ stat: 'ok' });
 });
 assert.equal(value.stat, 'ok');
 assert.throws(() => saved.retain(new Request('https://www.flickr.com/')), /upstream_unavailable/);
});
