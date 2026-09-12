import {scenarios,authorizationTarget} from "./model.mjs";
const $=id=>document.getElementById(id),select=$("scenario");
for(const [key,value] of Object.entries(scenarios)){const option=document.createElement("option");option.value=key;option.textContent=value.label;select.append(option);}
function render(){const value=scenarios[select.value];$("badge").textContent=value.badge;$("badge").className="badge "+value.tone;$("notice").className="notice "+value.tone;$("notice-title").textContent=value.title;$("notice-copy").textContent=value.copy;$("payload").textContent=value.payload;$("permission").textContent=value.permission;$("revision").textContent="7 · synthetic";$("external").textContent=value.external;$("user-gate").textContent=value.userGate;$("deployment-gate").textContent=value.deploymentGate;$("action-copy").textContent=value.action;$("connect").textContent=value.connect;$("connect").disabled=!value.canConnect;$("disconnect").disabled=!value.canDisconnect;$("resume").disabled=!value.canResume;$("feedback").textContent="";}
select.addEventListener("change",render);render();
$("connect").addEventListener("click",()=>{$("feedback").textContent=select.value==="repair_required"?"Preview: keep writes paused and reconcile the existing operation before another credential change.":"Preview: this would begin a protected authorization request, then navigate to the validated Flickr consent page. No navigation or account change occurred.";});
$("disconnect").addEventListener("click",()=>{$("feedback").textContent="Preview: disconnect would stop new operations first, then retire the credential payload. It cannot recall work already sent.";});
$("resume").addEventListener("click",()=>{$("feedback").textContent="Preview: this would request a separate, explicit resume. Replacing credentials never performs this action automatically.";});
$("test-handoff").addEventListener("click",async()=>{
 try{const options={method:"POST",headers:{"Content-Type":"application/json","X-CSRF-Token":"synthetic-review"},body:JSON.stringify({schemaVersion:1,expectedRevision:7}),redirect:"manual"};
 const legacy=await fetch("/preview/legacy-start",options);const proposed=await fetch("/preview/json-start",options);const body=await proposed.json();authorizationTarget(body.authorizationUrl);
 $("handoff-result").textContent=`Existing response: ${legacy.type}, status ${legacy.status}, Location ${legacy.headers.get("Location")??"not exposed"}.\nProposed response: ${proposed.status}; authorization target validated.\nNo Flickr navigation or production request occurred.`;
 }catch{$("handoff-result").textContent="Local browser check unavailable. No account action occurred.";}
});
