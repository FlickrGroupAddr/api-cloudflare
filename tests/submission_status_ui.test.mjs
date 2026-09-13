import test from "node:test";
import assert from "node:assert/strict";
import {statusPresentation} from "../assets/admin/submission-status-model.mjs";
const at="2026-09-13T12:00:00.000000Z";
const active={fgaSubmissionIntentId:"id",stateRevision:1,state:"queued",permanentSubmissionBlock:null,queue:{isPartitionHead:true,activeAheadInPartition:0,nextWorkNotBefore:at,holds:[]},attention:null};
test("active copy follows state, FIFO, due time and holds rather than polling cadence",()=>{
 assert.equal(statusPresentation(active,at).text,"Waiting for the next worker opportunity.");
 assert.equal(statusPresentation({...active,recommendedPollAfterSeconds:999},at).text,statusPresentation(active,at).text);
 assert.match(statusPresentation({...active,queue:{...active.queue,isPartitionHead:false,activeAheadInPartition:2,nextWorkNotBefore:null}},at).text,/2 earlier requests/);
 assert.match(statusPresentation({...active,state:"attempting",queue:{...active.queue,nextWorkNotBefore:null}},at).text,/Work has started/);
 assert.match(statusPresentation({...active,queue:{...active.queue,holds:["deployment_flickr_write_gate_paused"]}},at).text,/paused for review/);
 assert.match(statusPresentation({...active,state:"retrying",queue:{...active.queue,nextWorkNotBefore:"2026-09-13T12:00:00.000001Z"}},at).text,/Eligible for a safe retry/);
});
test("permanent blocks keep protected copy through time and moderation changes",()=>{
 const row={...active,state:"moderation_submitted",queue:null,permanentSubmissionBlock:{reasonCode:"moderation_submission_recorded",createdAt:at}};
 const expected=statusPresentation(row,at);assert.match(expected.text,/final moderator decision is unknown/);
 assert.deepEqual(statusPresentation({...row,moderated:false,currentMembership:false},"2036-09-13T12:00:00.000000Z"),expected);
 assert.throws(()=>statusPresentation({...row,permanentSubmissionBlock:null},at));
 assert.throws(()=>statusPresentation({...active,permanentSubmissionBlock:row.permanentSubmissionBlock},at));
 assert.throws(()=>statusPresentation({...active,state:"unknown"},at));
});
