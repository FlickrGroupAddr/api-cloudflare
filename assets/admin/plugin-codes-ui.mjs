import {transferView,CLEAN_CLIPBOARD_TEXT} from "./plugin-code-transfer.mjs";
const $=id=>document.getElementById(id);
const confirmations=["ownerControlledWorkstation","privateBrowser","clipboardHistoryOff","clipboardSyncOff","noObserversOrRecording","pluginReady"];
export function initializePluginCodes({getSession,onTransfer}){
 let busy=false,selected=null,epoch=0,pageToken=null,wasVisible=false;
 const feedback=text=>$("codes-feedback").textContent=text;
 const transfer=transferView({
  render(value,copyAllowed){if(!value&&wasVisible)feedback("Transfer view erased. If activation was not finished, revoke or cancel the code. Use Erase transfer view to overwrite the clipboard.");wasVisible=!!value;$("plugin-code-value").textContent=value;$("transfer-panel").hidden=!value;if(value)$("transfer-panel").scrollIntoView({block:"center"});$("copy-plugin-code").disabled=!copyAllowed;onTransfer(!!value);controls();},
  writeClipboard:value=>navigator.clipboard.writeText(value),
 });
 const erase=()=>{epoch++;transfer.erase();};
 async function api(path,method="GET",body,etag,media="application/json"){
  const session=getSession();if(!session)throw Error("authentication_required");
  const response=await fetch(path,{method,credentials:"same-origin",cache:"no-store",redirect:"error",
   headers:{...(method==="GET"?{}:{"Content-Type":media,"X-CSRF-Token":session.csrfToken}),...(etag?{"If-Match":etag}:{})},
   ...(body===undefined?{}:{body:JSON.stringify(body)})});
  if(!response.ok){if(response.status===401)erase();throw Error(response.status===403?"recent_authentication_required":response.status===412?"record_changed":response.status===409?"rotation_conflict":"request_unconfirmed");}
  return {body:await response.json(),etag:response.headers.get("ETag")};
 }
 function controls(){
  if(!$("create-plugin-code"))return;
  const confirmed=confirmations.every(key=>$("confirm-"+key).checked);
  const fresh=getSession()&&Date.now()-Date.parse(getSession().recentAuthenticationAt)<300000;
  const thirdParty=Boolean(window.google)||Boolean(document.querySelector('script[src^="https://"]'));
  $("create-plugin-code").disabled=busy||transfer.active||!confirmed||!fresh||thirdParty||(!selected&&!$("installation-label").value);
  $("create-plugin-code").textContent=selected?"Create rotation candidate":"Create Plugin Code";
  $("installation-label").disabled=!!selected||busy||transfer.active;
  $("cancel-code-selection").disabled=busy||transfer.active;
  $("code-create-help").textContent=thirdParty?"Reload this page before creating a Plugin Code; the transfer view requires a fresh page without Google scripts.":!fresh?"Confirm your Google Account from the Flickr section, then return and review this action.":selected?"A candidate is restricted to installation verification until you explicitly complete rotation.":"The code appears once. Keep Lightroom Classic ready on this workstation.";
 }
 async function act(action,duringTransfer=false){if(busy)return;if(transfer.active&&!duringTransfer){feedback("Finish the current transfer before another operation.");return;}busy=true;controls();feedback("");try{await action();}catch(error){feedback(error.message==="recent_authentication_required"?"Confirm your Google Account, then review and submit the action again.":error.message==="record_changed"?"The record changed. Refresh it before choosing an action.":"The operation is unconfirmed. Refresh the records; a created code cannot be revealed again.");}finally{busy=false;controls();}}
 async function detail(id){return api("/api/v001/plugin-codes/"+encodeURIComponent(id));}
 async function load(reset=true){
  const page=await api("/api/v001/plugin-codes"+(!reset&&pageToken?"?page_token="+encodeURIComponent(pageToken):""));
  if(!page.body||page.body.schemaVersion!==1||!Array.isArray(page.body.pluginCodes))throw Error("invalid_metadata");
  if(reset)$("plugin-code-list").replaceChildren();
  pageToken=page.body.nextPageToken??null;$("more-plugin-codes").hidden=!pageToken;
  for(const row of page.body.pluginCodes){
   const card=document.createElement("article");card.className="card";
   const title=document.createElement("h3");title.textContent=row.installationLabel||"Unnamed installation";
   const state=document.createElement("p");state.textContent=row.state+" · created "+new Date(row.createdAt).toLocaleString();
   const note=document.createElement("p");note.textContent=row.pendingCandidate?"A rotation candidate exists; expires "+new Date(row.pendingCandidate.expiresAt).toLocaleString():"Next planned rotation: "+new Date(row.rotationDueAt).toLocaleDateString();card.append(title,state,note);
   if(row.state==="active"){
    const rotate=document.createElement("button");rotate.className="secondary";rotate.textContent="Prepare rotation";rotate.disabled=!!row.pendingCandidate;
    rotate.onclick=()=>act(async()=>{const current=await detail(row.pluginCodeId);selected={...current.body,etag:current.etag};$("installation-label").value=current.body.installationLabel;for(const key of confirmations)$("confirm-"+key).checked=false;$("create-code-card").scrollIntoView({block:"center"});});card.append(rotate);
    if(row.pendingCandidate){
     const verified=document.createElement("label"),check=document.createElement("input");check.type="checkbox";verified.append(check,document.createTextNode(" Lightroom showed this candidate as pending_rotation; the clipboard and transfer view are cleared."));card.append(verified);
     const complete=document.createElement("button");complete.className="primary";complete.textContent="Complete rotation";complete.disabled=true;
     check.onchange=()=>complete.disabled=!check.checked||transfer.active||busy;
     complete.onclick=()=>act(async()=>{if(!check.checked||transfer.active)throw Error("confirmation_required");const current=await detail(row.pluginCodeId);await api(`/api/v001/plugin-codes/${encodeURIComponent(row.pluginCodeId)}/rotation-candidates/${encodeURIComponent(row.pendingCandidate.versionId)}`,"PATCH",{schemaVersion:1,state:"current",pluginValidationConfirmed:true},current.etag);await load();feedback("Rotation completed. Finish local rotation in Lightroom Classic; the old code is invalid.");});
     const cancel=document.createElement("button");cancel.className="secondary";cancel.textContent="Cancel candidate";
     cancel.onclick=()=>act(async()=>{erase();const current=await detail(row.pluginCodeId);await api(`/api/v001/plugin-codes/${encodeURIComponent(row.pluginCodeId)}/rotation-candidates/${encodeURIComponent(row.pendingCandidate.versionId)}`,"PATCH",{schemaVersion:1,state:"revoked"},current.etag);await load();feedback("Candidate cancelled. The prior current code remains valid; discard the failed candidate in Lightroom Classic.");});card.append(complete,cancel);
    }
    const revoke=document.createElement("button");revoke.className="danger";revoke.textContent="Revoke installation";
    revoke.onclick=()=>act(async()=>{const current=await detail(row.pluginCodeId);selected={...current.body,etag:current.etag};$("revoke-code-name").textContent=current.body.installationLabel;$("revoke-code-dialog").showModal();});card.append(revoke);
   }
   $("plugin-code-list").append(card);
  }
 }
 $("create-plugin-code").onclick=()=>act(async()=>{
  if(transfer.active||window.google||document.querySelector('script[src^="https://"]'))throw Error("fresh_page_required");
  const transferConfirmations=Object.fromEntries(confirmations.map(key=>[key,$("confirm-"+key).checked]));
  if(Object.values(transferConfirmations).some(value=>!value))throw Error("confirmation_required");
  const currentEpoch=epoch,target=selected?.pluginCodeId;
  const result=target?await api(`/api/v001/plugin-codes/${encodeURIComponent(target)}/rotation-candidates`,"POST",{schemaVersion:1,transferConfirmations},selected.etag):await api("/api/v001/plugin-codes","POST",{schemaVersion:1,installationLabel:$("installation-label").value,transferConfirmations});
  let code=result.body.pluginCode;delete result.body.pluginCode;
  if(currentEpoch!==epoch||document.visibilityState!=="visible"||target&&result.body.pluginCodeId!==target){code="";throw Error("transfer_view_lost");}
  transfer.show(code);code="";selected=null;for(const key of confirmations)$("confirm-"+key).checked=false;
  feedback("Compare this code with Lightroom before storing it. Erase this view and clear the clipboard after verification.");
 });
 $("copy-plugin-code").onclick=()=>act(async()=>{const copied=await transfer.copy();feedback(copied?"Copied once. Paste into Lightroom Classic and compare both displays.":"Clipboard copy was not confirmed. Use the accepted manual transcription recovery while both trusted displays are visible.");},true);
 $("erase-plugin-code").onclick=()=>{epoch++;void transfer.finish().then(async cleared=>{feedback(cleared?"Transfer view erased and clipboard overwritten. Close the private window after completing the Lightroom step.":"Transfer view erased. Copy the displayed non-secret cleanup sentence manually; clipboard overwrite was not confirmed.");await act(()=>load());});};
 $("cleanup-sentence").textContent=CLEAN_CLIPBOARD_TEXT;
 $("cancel-code-selection").onclick=()=>{selected=null;controls();};
 $("refresh-plugin-codes").onclick=()=>act(()=>load());$("more-plugin-codes").onclick=()=>act(()=>load(false));
 $("cancel-code-revoke").onclick=()=>{$("revoke-code-dialog").close();selected=null;controls();};
 $("confirm-code-revoke").onclick=()=>act(async()=>{const target=selected;if(!target)throw Error("missing_selection");erase();await api("/api/v001/plugin-codes/"+encodeURIComponent(target.pluginCodeId),"PATCH",{state:"revoked"},target.etag,"application/merge-patch+json");$("revoke-code-dialog").close();selected=null;await load();feedback("Server access revoked. Clear both Plugin Code keys on the workstation; remote erasure is not confirmed.");});
 for(const key of confirmations)$("confirm-"+key).onchange=controls;$("installation-label").oninput=controls;
 window.addEventListener("pagehide",erase);document.addEventListener("visibilitychange",()=>{if(document.visibilityState==="hidden")erase();});
 return {open:()=>act(()=>load()),erase,controls,get active(){return transfer.active;}};
}
