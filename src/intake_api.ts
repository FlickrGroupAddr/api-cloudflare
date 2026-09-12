import { admit, AdmissionError, MAX_GROUP_IDS, type AdmissionAuth, type WakeHint } from "./admission.ts";
import { errorResponse } from "./installations.ts";
import { commitBinding,FlickrReadError,linkedGrant,sameGrant,verifyPhoto,type FlickrFetch,type SecretReads } from "./flickr_reads.ts";
export const MAX_JSON_BYTES=16_384;
export interface IntakeEnv extends SecretReads { DB:D1Database; FGA_INTAKE_ENABLED?:string; FGA_MAX_GROUP_IDS_PER_BATCH?:string; COORD?:DurableObjectNamespace; }
export function configured(env:Pick<IntakeEnv,"FGA_INTAKE_ENABLED"|"FGA_MAX_GROUP_IDS_PER_BATCH">):boolean {
 return env.FGA_INTAKE_ENABLED==="1" && (env.FGA_MAX_GROUP_IDS_PER_BATCH===undefined||env.FGA_MAX_GROUP_IDS_PER_BATCH===String(MAX_GROUP_IDS));
}
export async function jsonBody(request:Request):Promise<unknown|Response> {
 if(!/^application\/json(?:\s*;\s*charset=utf-8)?$/i.test(request.headers.get("Content-Type")??"")||
  (request.headers.has("Content-Encoding")&&request.headers.get("Content-Encoding")!=="identity"))return errorResponse(415,"unsupported_media_type","Use JSON request content.");
 const declared=request.headers.get("Content-Length");
 if(declared!==null&&(!/^\d+$/.test(declared)||Number(declared)>MAX_JSON_BYTES))return errorResponse(413,"request_too_large","Request is too large.");
 if(!request.body)return errorResponse(400,"invalid_request","JSON request content is required.");
 const reader=request.body.getReader();const parts:Uint8Array[]=[];let size=0;
 try {
  for(;;){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>MAX_JSON_BYTES){await reader.cancel();return errorResponse(413,"request_too_large","Request is too large.");}parts.push(value);}
  const data=new Uint8Array(size);let offset=0;for(const part of parts){data.set(part,offset);offset+=part.length;}
  return JSON.parse(new TextDecoder("utf-8",{fatal:true,ignoreBOM:false}).decode(data));
 }catch{return errorResponse(400,"invalid_request","Invalid JSON request.");}
}
function json(body:unknown,status:number):Response {return Response.json(body,{status,headers:{"Cache-Control":"no-store","X-Content-Type-Options":"nosniff","Referrer-Policy":"no-referrer"}});}
export async function publishNativeHint(env:Pick<IntakeEnv,"COORD">,hint:WakeHint):Promise<void> {
 if(!env.COORD)throw new Error("wake_delivery_unavailable");
 const response=await env.COORD.get(env.COORD.idFromName(hint.partitionId)).fetch("https://internal.invalid/wake",{method:"POST",body:JSON.stringify({...hint,source:"admission"})});
 if(!response.ok)throw new Error("wake_delivery_unconfirmed");
}
async function rejectionCode(env:IntakeEnv,auth:AdmissionAuth,value:unknown):Promise<string> {
 const input=value as {photoBinding:{fgaPhotoBindingId:string;expectedVerificationRevision:number};flickrGroupIds:string[]};
 const row=await env.DB.prepare(`SELECT b.source_kind,CAST(b.verified_at_us AS TEXT) verified_us,CAST((CAST(strftime('%s','now') AS INTEGER)*1000000+CAST(substr(strftime('%f','now'),4,3) AS INTEGER)*1000) AS TEXT) now_us,
 b.verification_revision,b.link_revision,l.link_revision current_link_revision,l.state,
 EXISTS(SELECT 1 FROM json_each(?) g WHERE NOT EXISTS(SELECT 1 FROM submission_intents i WHERE i.photo_id=b.photo_id AND i.group_id=g.value)) missing
 FROM photo_bindings b JOIN installations i ON i.user_id=b.user_id JOIN flickr_links l ON l.user_id=b.user_id WHERE b.binding_id=? AND i.installation_id=?`).bind(JSON.stringify(input.flickrGroupIds),input.photoBinding.fgaPhotoBindingId,auth.installationId).first<{source_kind:string;verified_us:string;now_us:string;verification_revision:number;link_revision:number;current_link_revision:number;state:string;missing:number}>();
 if(row&&(row.link_revision!==row.current_link_revision||!["linked","paused"].includes(row.state)))return "flickr_link_changed";
 if(row&&row.verification_revision===input.photoBinding.expectedVerificationRevision&&row.source_kind==="existing_public"&&row.missing===1&&BigInt(row.now_us)-BigInt(row.verified_us)>15_000_000n)return "existing_photo_reverification_required";
 return "admission_rejected";
}
export async function batchRequest(env:IntakeEnv,auth:AdmissionAuth,value:unknown,publish:(hint:WakeHint)=>Promise<void>):Promise<Response> {
 try {
  const result=await admit(env.DB,auth,value,publish);
  return json({schemaVersion:2,fgaPhotoBindingId:result.bindingId,flickrPhotoId:result.photoId,
   submissions:result.items.map(item=>({fgaSubmissionIntentId:item.intentId,flickrGroupId:item.groupId,state:item.state,created:item.created,
    permanentSubmissionBlock:item.blockReason===null?null:{reasonCode:item.blockReason,createdAt:item.blockCreatedAt}}))},202);
 }catch(error){
  if(error instanceof AdmissionError && error.message==="invalid_request")return errorResponse(400,"invalid_request","Invalid group selection.");
  if(error instanceof AdmissionError && error.message==="admission_rejected"){
   try {return errorResponse(409,await rejectionCode(env,auth,value),"The binding or selection must be checked again.");}catch{}
  }
  return errorResponse(503,"admission_unavailable","Admission is unavailable.");
 }
}
export async function bindingRequest(env:IntakeEnv,auth:AdmissionAuth,value:unknown,fetcher:FlickrFetch):Promise<Response> {
 if(!value||typeof value!=="object"||Array.isArray(value)||Object.keys(value).sort().join()!=="expectedLinkedFlickrRevision,flickrPhotoId,schemaVersion")return errorResponse(400,"invalid_request","Invalid photo proof request.");
 const input=value as {schemaVersion:unknown;flickrPhotoId:unknown;expectedLinkedFlickrRevision:unknown};
 if(input.schemaVersion!==1||typeof input.flickrPhotoId!=="string"||!/^[A-Za-z0-9][A-Za-z0-9@._:-]{0,127}$/.test(input.flickrPhotoId)||!Number.isSafeInteger(input.expectedLinkedFlickrRevision)||(input.expectedLinkedFlickrRevision as number)<1)return errorResponse(400,"invalid_request","Invalid photo proof request.");
 let before;
 try {
  before=await linkedGrant(env.DB,auth);
  if(!before||before.revision!==String(input.expectedLinkedFlickrRevision))return errorResponse(409,"flickr_link_changed","The Flickr connection changed.");
  await verifyPhoto(env.DB,auth,env,before,input.flickrPhotoId,fetcher);
  const result=await commitBinding(env.DB,auth,before,input.flickrPhotoId);
  return json(result.body,result.created?201:200);
 }catch(error){
  if(error instanceof FlickrReadError){
   const statuses:Record<string,number>={flickr_link_changed:409,photo_owner_mismatch:403,existing_photo_not_public:422,invalid_existing_photo:422};
   if(statuses[error.message])return errorResponse(statuses[error.message],error.message,"The photo or connection could not be verified.");
  }
  if(before){try{if(!sameGrant(before,await linkedGrant(env.DB,auth)))return errorResponse(409,"flickr_link_changed","The Flickr connection changed.");}catch{}}
  return errorResponse(503,"existing_photo_verification_unavailable","Photo verification is unavailable.");
 }
}
