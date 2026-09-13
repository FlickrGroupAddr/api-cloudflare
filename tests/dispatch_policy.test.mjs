import test from "node:test";
import assert from "node:assert/strict";
import {classifyAdd,retryDelayMs} from "../src/dispatch_policy.ts";

test("complete documented add classifications preserve permanent moderation and unknown blocks",()=>{
  const expected=new Map([["ok","added"],[1,"needs_attention"],[2,"needs_attention"],[3,"added"],
    [4,"needs_attention"],[5,"throttled"],[6,"moderation_submitted"],[7,"moderation_submitted"],
    [8,"needs_attention"],[10,"needs_attention"],[11,"needs_attention"],[116,"needs_attention"],
    [105,"retrying"],[106,"retrying"],[98,"needs_attention"],[99,"needs_attention"],[95,"needs_attention"],[96,"needs_attention"],
    [97,"needs_attention"],[100,"needs_attention"],[111,"needs_attention"],[112,"needs_attention"],[114,"needs_attention"],[115,"needs_attention"]]);
  for(const [code,outcome] of expected)assert.equal(classifyAdd(code).outcome,outcome,String(code));
  for(const code of [9,113,9001,-1])assert.deepEqual(classifyAdd(code),{outcome:"delivery_uncertain",reason:"unknown_code",pause:"deployment"});
  for(const code of [98,99])assert.equal(classifyAdd(code).pause,"user");
  for(const code of [95,96,97,100,111,112,114,115])assert.equal(classifyAdd(code).pause,"deployment");
});

test("retry delays are finite jittered exponential windows and reject invalid entropy",()=>{
  assert.equal(retryDelayMs(0,0),2500);assert.equal(retryDelayMs(1,0),5000);
  assert.equal(retryDelayMs(99,0),150000);assert.equal(retryDelayMs(99,.999999),299999);
  for(const jitter of [-1,1,NaN,Infinity])assert.throws(()=>retryDelayMs(0,jitter));
  for(const count of [-1,.1,NaN,Infinity])assert.throws(()=>retryDelayMs(count,0));
});
