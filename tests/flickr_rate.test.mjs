import test from "node:test";
import assert from "node:assert/strict";
import {mkdtempSync,rmSync} from "node:fs";
import {tmpdir} from "node:os";
import {join} from "node:path";
import {sqlStore} from "./sql_store.mjs";
import {reserveFlickrAttempt} from "../src/flickr_rate.ts";

function setup(t){
  const directory=mkdtempSync(join(tmpdir(),"fga-rate-")),db=sqlStore(join(directory,"db.sqlite"));
  t.after(()=>{db.raw.close();rmSync(directory,{recursive:true,force:true});});
  db.raw.exec("INSERT INTO fga_users VALUES('user');INSERT INTO flickr_links VALUES('user','owner',1,'linked');INSERT INTO flickr_write_gates VALUES('deployment','*',1,1),('user','user',1,1);");
  const contexts=[];
  for(let i=0;i<3;i++){
    const id="id"+i,expires=Date.now()*1000+60_000_000;
    db.raw.prepare("INSERT INTO photo_bindings(binding_id,user_id,photo_id,owner_nsid,link_revision,verification_revision,source_kind) VALUES(?,'user',?,'owner',1,1,'upload')").run(id,id);
    db.raw.prepare("INSERT INTO group_partitions(partition_id,user_id,group_id,lease_id,lease_generation,lease_started_at_us,lease_expires_at_us,invocation_deadline_at_us) VALUES(?,'user',?,?,1,1,?,?)").run(id,id,id,expires,expires);
    db.raw.prepare("INSERT INTO submission_intents(intent_id,binding_id,user_id,photo_id,group_id,partition_id,enqueue_ordinal,state,created_request_id) VALUES(?,?,'user',?,?,?,1,'attempting',?)").run(id,id,id,id,id,id);
    db.raw.prepare("INSERT INTO submission_attempts(attempt_id,intent_id,ordinal,lease_id,lease_generation,deployment_revision,user_revision,link_revision) VALUES(?,?,1,?,1,1,1,1)").run(id,id,id);
    contexts.push({attemptId:id,photoId:id,groupId:id});
  }
  return {db,contexts};
}

test("reserve three slots atomically; refund only proven-unused capacity once",async t=>{
  const {db,contexts}=setup(t),policy={capacity:3,windowMs:60000};
  const reservation=await reserveFlickrAttempt(db,contexts[0],policy);assert(reservation);
  assert.equal(await reserveFlickrAttempt(db,contexts[1],policy),null);
  assert.equal(db.raw.prepare("SELECT reserved_slots FROM flickr_rate_window").get().reserved_slots,3);
  assert.equal(await reservation.check(contexts[0]),true);
  assert.equal(await reservation.check(contexts[1]),false);
  assert.throws(()=>reservation.consume("preflight"));reservation.consume("membership");
  await reservation.releaseUnused();await reservation.releaseUnused();
  assert.equal(db.raw.prepare("SELECT reserved_slots FROM flickr_rate_window").get().reserved_slots,1);
  assert.equal(db.raw.prepare("SELECT consumed_slots FROM flickr_rate_reservations").get().consumed_slots,1);
});

test("expired and stale-lease reservations cannot authorize operations or refund a new window",async t=>{
  const {db,contexts}=setup(t),policy={capacity:3,windowMs:60000};
  const old=await reserveFlickrAttempt(db,contexts[0],policy);assert(old);
  db.raw.exec("UPDATE group_partitions SET lease_generation=2 WHERE partition_id='id0'");
  assert.equal(await old.check(contexts[0]),false);
  db.raw.exec("UPDATE flickr_rate_window SET expires_at_us=0");
  const next=await reserveFlickrAttempt(db,contexts[1],policy);assert(next);
  assert.equal(await old.check(contexts[0]),false);
  await old.releaseUnused();
  assert.equal(db.raw.prepare("SELECT reserved_slots FROM flickr_rate_window").get().reserved_slots,3);
  assert.equal(await next.check(contexts[1]),true);
});

test("allocation transaction failure rolls back its window charge and reservation together",async t=>{
  const {db,contexts}=setup(t);db.fault=3;
  assert.equal(await reserveFlickrAttempt(db,contexts[0]),null);
  assert.equal(db.raw.prepare("SELECT COUNT(*) n FROM flickr_rate_reservations").get().n,0);
  assert.equal(db.raw.prepare("SELECT COUNT(*) n FROM flickr_rate_window").get().n,0);
});
