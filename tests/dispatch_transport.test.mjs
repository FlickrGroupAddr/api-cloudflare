import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createDispatchTransport, membershipPresent, moderationValue } from "../src/dispatch_transport.ts";
import { runPartition } from "../src/fail_polite.ts";
import { sqlStore } from "./sql_store.mjs";

const context = { attemptId: "attempt", photoId: "photo", groupId: "123@N00" };
const secrets = {
  FLICKR_APPLICATION: { get: async () => JSON.stringify({ schemaVersion: 1, consumerKey: "synthetic-key", consumerSecret: "synthetic-secret" }) },
  FLICKR_GRANT: { get: async () => JSON.stringify({ schemaVersion: 1, generation: "generation", token: "synthetic-token", tokenSecret: "synthetic-token-secret" }) },
};

function fixture(t) {
  const directory = mkdtempSync(join(tmpdir(), "fga-dispatch-"));
  const db = sqlStore(join(directory, "database.sqlite"));
  db.raw.exec(`INSERT INTO fga_users VALUES('user');
    INSERT INTO flickr_links VALUES('user','owner',1,'linked');
    INSERT INTO flickr_write_gates VALUES('deployment','*',1,1),('user','user',1,1);
    INSERT INTO photo_bindings(binding_id,user_id,photo_id,owner_nsid,link_revision,verification_revision,source_kind)
      VALUES('binding','user','photo','owner',1,1,'upload');
    INSERT INTO group_partitions(partition_id,user_id,group_id) VALUES('partition','user','123@N00');
    INSERT INTO submission_intents(intent_id,binding_id,user_id,photo_id,group_id,partition_id,enqueue_ordinal,state,created_request_id)
      VALUES('intent','binding','user','photo','123@N00','partition',1,'queued','request');`);
  t.after(() => { db.raw.close(); rmSync(directory, { recursive: true, force: true }); });
  return db;
}

function peer(db, events, result=6) {
  return async request => {
    assert.equal(new URL(request.url).origin, "https://www.flickr.com");
    assert.match(request.headers.get("Authorization"), /^OAuth /);
    assert.equal(request.redirect, "manual");
    const params = request.method === "POST" ? new URLSearchParams(await request.text()) : new URL(request.url).searchParams;
    const method = params.get("method"); events.push(method);
    if (method === "flickr.photos.getAllContexts") return Response.json({ stat: "ok", pool: [] });
    if (method === "flickr.groups.getInfo") return Response.json({ stat: "ok", group: { id: "123@N00", ispoolmoderated: "0" } });
    assert.equal(request.method, "POST");
    assert.equal(method, "flickr.groups.pools.add");
    assert.equal(params.get("photo_id"), "photo"); assert.equal(params.get("group_id"), "123@N00");
    assert.equal(db.raw.prepare("SELECT COUNT(*) n FROM attempt_dispatches").get().n, 1);
    return Response.json({ stat: "fail", code: result });
  };
}

function reservation(events) {
  const used = new Set();
  return { async check(){return true;}, consume(kind) { assert(!used.has(kind)); used.add(kind); events.push("consume:"+kind); },
    releaseUnused() { events.push("release:"+(3-used.size)); } };
}

test("signed transport validates the complete membership response and exact moderation identity", () => {
  assert.equal(membershipPresent({stat:"ok",pool:[]},context.groupId),false);
  assert.equal(membershipPresent({stat:"ok",pool:[{id:context.groupId,title:"A pool"}]},context.groupId),true);
  for(const pool of [undefined,null,{},"",[{}],[{id:context.groupId}],
    [{id:context.groupId,title:"ok"},{id:context.groupId,title:"duplicate"}],
    [{id:"bad id",title:"bad"}],[{id:"valid",title:9}],Array(257).fill({id:"id",title:"x"})])
    assert.throws(()=>membershipPresent({stat:"ok",pool},context.groupId));
  for(const moderation of [undefined,null,2,"false",{},[]])
    assert.throws(()=>moderationValue({stat:"ok",group:{id:context.groupId,ispoolmoderated:moderation}},context.groupId));
  assert.throws(()=>moderationValue({stat:"ok",group:{id:"another",ispoolmoderated:0}},context.groupId));
});

test("credential mismatch and a stale authority callback cause zero Flickr requests", async () => {
  let sent=0;
  await assert.rejects(createDispatchTransport(secrets,"different",async()=>{},async()=>{sent++;}));
  await assert.rejects(createDispatchTransport(secrets,"generation",async()=>{throw Error("stale");},async()=>{sent++;}));
  assert.equal(sent,0);
});

test("prepared signed dispatch follows membership/preflight/marker and permanently blocks code 6", async t => {
  const db=fixture(t), events=[];
  const transport=await createDispatchTransport(secrets,"generation",async()=>{
    assert.equal(db.raw.prepare("SELECT COUNT(*) n FROM attempt_dispatches").get().n,0);
  },peer(db,events));
  const result=await runPartition({db,transport,monotonicUs:()=>0,reserve:async()=>reservation(events)},"partition","hint");
  assert.equal(result,"moderation_submitted");
  assert.deepEqual(events.filter(x=>x.startsWith("flickr.")),["flickr.photos.getAllContexts","flickr.groups.getInfo","flickr.groups.pools.add"]);
  assert.equal(db.raw.prepare("SELECT first_reason FROM submission_blocks").get().first_reason,"flickr_code_6");
  assert.equal(await runPartition({db,transport,monotonicUs:()=>0,reserve:async()=>assert.fail()},"partition","sweep"),"no_claim");
  assert(!JSON.stringify(db.raw.prepare("SELECT * FROM attempt_resolutions").all()).includes("synthetic-token"));
});

test("prepared transport cannot be reused, change pair, or skip fresh reads",async()=>{
  const seen=[];
  const fetcher=async request=>{const method=new URL(request.url).searchParams.get("method");seen.push(request.method);return Response.json(method==="flickr.photos.getAllContexts"?{stat:"ok",pool:[]}:method==="flickr.groups.getInfo"?{stat:"ok",group:{id:context.groupId,ispoolmoderated:1}}:{stat:"ok"});};
  const transport=await createDispatchTransport(secrets,"generation",async()=>{},fetcher);
  await assert.rejects(transport.prepareAdd(context));
  await transport.membership(context);
  await assert.rejects(transport.preflight({...context,groupId:"different"}));
  await transport.preflight(context);
  const prepared=await transport.prepareAdd(context);
  assert.equal(await prepared.handoff(),"ok");
  assert.throws(()=>prepared.handoff()); prepared.dispose();
  await assert.rejects(transport.prepareAdd(context));
  assert.deepEqual(seen,["GET","GET","POST"]);
});

for(const stage of ["preparation","marker"]) test(`expired during ${stage}: no POST and retained safe non-handoff`,async t=>{
  const db=fixture(t),events=[];let now=0;
  const real=await createDispatchTransport(secrets,"generation",async()=>{},peer(db,events));
  const transport={...real,async prepareAdd(attempt){
    assert.equal(db.raw.prepare("SELECT COUNT(*) n FROM attempt_dispatches").get().n,0);
    const prepared=await real.prepareAdd(attempt); if(stage==="preparation")now=1_000_000;return prepared;
  }};
  const result=await runPartition({db,transport,monotonicUs:()=>now,reserve:async()=>reservation(events),
    fault:async point=>{if(stage==="marker"&&point==="marker_committed")now=1_000_000;}},"partition","hint");
  assert.equal(result,"expired");assert(!events.includes("flickr.groups.pools.add"));
  assert.equal(db.raw.prepare("SELECT COUNT(*) n FROM submission_blocks").get().n,0);
  assert.equal(db.raw.prepare("SELECT reason FROM attempt_resolutions").get().reason,"not_dispatched_preflight_expired");
  assert.equal(events.at(-1),"release:1");
});

test("failed marker transaction never hands a prepared request to the transport",async t=>{
  const db=fixture(t),events=[];
  const transport=await createDispatchTransport(secrets,"generation",async()=>{},peer(db,events));
  await assert.rejects(runPartition({db,transport,monotonicUs:()=>0,reserve:async()=>reservation(events),fault:async point=>{
    if(point==="preflight_committed")db.raw.exec("UPDATE flickr_write_gates SET enabled=0,revision=revision+1 WHERE scope='deployment'");
  }},"partition","hint"));
  assert(!events.includes("flickr.groups.pools.add"));assert.equal(db.raw.prepare("SELECT COUNT(*) n FROM attempt_dispatches").get().n,0);
});

test("lost POST response becomes uncertain with a permanent block and no replay",async t=>{
  const db=fixture(t),events=[];const get=peer(db,events);
  const transport=await createDispatchTransport(secrets,"generation",async()=>{},request=>{
    if(request.method==="POST"){events.push("POST");throw Error("lost response");}return get(request);
  });
  assert.equal(await runPartition({db,transport,monotonicUs:()=>0,reserve:async()=>reservation(events)},"partition","hint"),"uncertain");
  assert.equal(db.raw.prepare("SELECT first_reason FROM submission_blocks").get().first_reason,"delivery_uncertain");
  assert.equal(events.filter(x=>x==="POST").length,1);
});
