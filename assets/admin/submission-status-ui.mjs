import {statusPresentation} from "./submission-status-model.mjs";
const $=id=>document.getElementById(id);
export function initializeSubmissionStatus({onUnauthorized}){
 let opened=false,busy=false,epoch=0,timer=null,nextPage=null,retryAt=0;
 const stopTimer=()=>{if(timer!==null)clearTimeout(timer);timer=null;};
 const clear=()=>{epoch++;stopTimer();$("status-rows").replaceChildren();$("status-summary").textContent="";nextPage=null;$("status-more").hidden=true;};
 async function load(more=false){
  if(!opened||busy)return;if(Date.now()<retryAt){stopTimer();timer=setTimeout(()=>void load(false),retryAt-Date.now());return;}
  busy=true;$("status-refresh").disabled=true;$("status-more").disabled=true;stopTimer();
  const generation=epoch,query=new URLSearchParams({view:$("status-view").value,page_size:"50"});
  if(more&&nextPage){query.set("before_created_at",nextPage.beforeCreatedAt);query.set("before_intent_id",nextPage.beforeIntentId);}
  try{
   const response=await fetch("/api/v001/admin/group-submission-intents?"+query,{credentials:"same-origin",cache:"no-store",redirect:"error",signal:AbortSignal.timeout(15000)});
   if(response.status===401){clear();onUnauthorized();return;}
   if(!response.ok){const wait=Number(response.headers.get("Retry-After"));retryAt=Date.now()+(Number.isSafeInteger(wait)&&wait>0?Math.min(wait,3600):15)*1000;throw Error("unavailable");}
   const body=await response.json();
   if(generation!==epoch||!opened)return;
   if(body.schemaVersion!==1||!Array.isArray(body.intents)||body.intents.length>50||!body.summary||body.view!==$("status-view").value||!["activeIntentCount","activePartitionCount","attentionIntentCount"].every(key=>Number.isSafeInteger(body.summary[key])&&body.summary[key]>=0)||![null,15,60].includes(body.recommendedPollAfterSeconds))throw Error("invalid_status");
   // Validate the complete page before replacing any visible row.
   const rows=body.intents.map(intent=>({intent,presentation:statusPresentation(intent,body.observedAt)}));
   if(!more)$("status-rows").replaceChildren();
   for(const {intent,presentation} of rows){const card=document.createElement("article");card.className="card";const title=document.createElement("h3");title.textContent=intent.groupDisplayName??"Flickr group "+intent.flickrGroupId;const text=document.createElement("p");text.textContent=presentation.text;const ids=document.createElement("p");ids.className="retained";ids.textContent="Photo "+intent.flickrPhotoId+" · observed "+new Date(body.observedAt).toLocaleString(undefined,{timeZoneName:"short"});card.append(title,text,ids);$("status-rows").append(card);}
   $("status-summary").textContent=`${body.summary.activeIntentCount} active request${body.summary.activeIntentCount===1?"":"s"} across ${body.summary.activePartitionCount} group${body.summary.activePartitionCount===1?"":"s"} · ${body.summary.attentionIntentCount} need${body.summary.attentionIntentCount===1?"s":""} attention`;
   $("status-feedback").textContent=rows.length?"Status is an observation. Due times are lower bounds, not completion promises.":"No matching requests in this view.";
   nextPage=body.nextPage;$("status-more").hidden=!nextPage;
   if(body.recommendedPollAfterSeconds!==null)timer=setTimeout(()=>void load(false),body.recommendedPollAfterSeconds*1000);
  }catch{if(generation===epoch&&opened){$("status-feedback").textContent="Status unavailable. Any previously displayed data may be stale; no queue action was performed.";timer=setTimeout(()=>void load(false),Math.max(15000,retryAt-Date.now()));}}
  finally{busy=false;$("status-refresh").disabled=false;$("status-more").disabled=false;if(opened&&generation!==epoch)void load(false);}
 }
 $("status-refresh").onclick=()=>void load(false);$("status-more").onclick=()=>void load(true);
 $("status-view").onchange=()=>{clear();void load(false);};
 window.addEventListener("pagehide",()=>{opened=false;clear();});
 return {open(){opened=true;void load(false);},close(){opened=false;epoch++;stopTimer();},clear};
}
