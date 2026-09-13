const active=new Set(["queued","attempting","retrying","throttled"]);
const states=new Set([...active,"added","moderation_submitted","delivery_uncertain","needs_attention","cancelled"]);
const stamp=value=>typeof value==="string"&&/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$/.test(value)&&Number.isFinite(Date.parse(value));
const time=value=>new Date(value).toLocaleString(undefined,{timeZoneName:"short"});
export function statusPresentation(intent,observedAt){
 if(!intent||!states.has(intent.state)||!stamp(observedAt)||typeof intent.fgaSubmissionIntentId!=="string"||!Number.isSafeInteger(intent.stateRevision)||intent.stateRevision<1)throw Error("status_unavailable");
 const block=intent.permanentSubmissionBlock;
 if(intent.state==="moderation_submitted"&&block?.reasonCode!=="moderation_submission_recorded"||intent.state==="delivery_uncertain"&&block?.reasonCode!=="delivery_uncertain"||!['moderation_submitted','delivery_uncertain'].includes(intent.state)&&block!==null)throw Error("status_unavailable");
 if(block){
  if(!stamp(block.createdAt)||intent.queue!==null||intent.state==="delivery_uncertain"&&intent.attention?.fgaResubmissionAllowed!==false)throw Error("status_unavailable");
  return block.reasonCode==="moderation_submission_recorded"?{code:"moderation_submission_protected",text:"Flickr recorded a moderation submission for this photo and group. The final moderator decision is unknown. FGA components will not submit this exact pair again.",tone:"amber"}:{code:"delivery_uncertain_protected",text:"FGA records cannot prove whether Flickr received the add request. To avoid a duplicate request, FGA components will not submit this exact pair again. Inspect Flickr manually.",tone:"amber"};
 }
 if(active.has(intent.state)){
  const q=intent.queue;if(!q||!Number.isSafeInteger(q.activeAheadInPartition)||q.activeAheadInPartition<0||q.isPartitionHead!==(q.activeAheadInPartition===0)||!Array.isArray(q.holds)||new Set(q.holds).size!==q.holds.length||q.holds.some(x=>!["user_flickr_write_gate_paused","deployment_flickr_write_gate_paused"].includes(x)))throw Error("status_unavailable");
  if((!q.isPartitionHead||intent.state==="attempting")&&q.nextWorkNotBefore!==null)throw Error("status_unavailable");
  if(q.isPartitionHead&&intent.state!=="attempting"&&!stamp(q.nextWorkNotBefore))throw Error("status_unavailable");
  let text;
  if(q.holds.length)text="Flickr writes are paused for review. Queue order is preserved.";
  else if(intent.state==="attempting")text="Work has started for this group request.";
  else if(!q.isPartitionHead)text=`Waiting behind ${q.activeAheadInPartition} earlier request${q.activeAheadInPartition===1?"":"s"} for this Flickr group.`;
  else{
   if(!stamp(q.nextWorkNotBefore))throw Error("status_unavailable");
   if(q.nextWorkNotBefore>observedAt&&intent.state==="throttled")text="Flickr's group limit was reached. Eligible for another check after "+time(q.nextWorkNotBefore)+".";
   else if(q.nextWorkNotBefore>observedAt&&intent.state==="retrying")text="Eligible for a safe retry after "+time(q.nextWorkNotBefore)+".";
   else if(q.nextWorkNotBefore<=observedAt)text="Waiting for the next worker opportunity.";
   else throw Error("status_unavailable");
  }
  return {code:"existing_submission_intent",text,tone:"neutral"};
 }
 if(intent.queue!==null)throw Error("status_unavailable");
 if(intent.state==="added")return {code:"existing_submission_intent",text:"Flickr confirmed the photo was in this group when the request was processed.",tone:"green"};
 if(intent.state==="cancelled")return {code:"existing_submission_intent",text:"This retained request was cancelled. No Flickr removal is implied.",tone:"neutral"};
 const attention=intent.attention;
 if(!attention||attention.kind!=="needs_attention"||attention.fgaResubmissionAllowed!==false)throw Error("status_unavailable");
 const copy={correct_future_selection:"This request needs attention. Correct future selections or inspect Flickr manually; this intent will not retry automatically.",reauthorize_flickr:"This request stopped because Flickr authorization needs repair. Repairing the connection will not resubmit this intent.",repair_deployment:"This request stopped because the deployment needs repair. Repairing the deployment will not resubmit this intent."};
 if(!Object.hasOwn(copy,attention.operatorAction))throw Error("status_unavailable");
 return {code:"existing_submission_intent",text:copy[attention.operatorAction],tone:"amber"};
}
