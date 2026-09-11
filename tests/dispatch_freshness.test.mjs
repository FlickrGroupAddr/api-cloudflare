import test from "node:test";
import assert from "node:assert/strict";
import { preflightIsFresh } from "../src/dispatch_freshness.ts";
test("preflight policy has a strict microsecond deadline and rejects clock anomalies",()=>{
 for(const [received,now,wanted] of [[0,0,true],[100,1_000_099,true],[100,1_000_100,false],[100,1_000_101,false],[100,99,false],[NaN,100,false],[0,Infinity,false],[0,0.5,false],[Number.MAX_SAFE_INTEGER+1,Number.MAX_SAFE_INTEGER+1,false]]) assert.equal(preflightIsFresh(received,now),wanted);
});
