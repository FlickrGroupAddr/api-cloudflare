// Supplemental hosted-runtime check imports the exact optimized production bytes.
// All provider responses are synthetic; this adapter never invokes global fetch.
import {consumePartition} from "./production.mjs";
export default {
 async fetch(request,env){
  if(request.headers.get("Authorization")!=="Bearer "+env.MATRIX_TOKEN||Date.now()>Number(env.MATRIX_EXPIRES))return new Response(null,{status:404});
  if(request.method==="GET")return Response.json({ready:true,compatibilityDate:"2026-09-11"});
  const input=await request.json(),calls=[];
  let markerAt=null,handoffAt=null;
  const provider=async request=>{
   const url=new URL(request.url);if(url.origin!=="https://www.flickr.com")throw new Error("unexpected_provider_origin");
   const params=new URLSearchParams(request.method==="POST"?await request.text():url.search);
   const method=params.get("method");calls.push(method);
   if(method==="flickr.photos.getAllContexts")return Response.json({stat:"ok",pool:[]});
   if(method==="flickr.groups.getInfo")return Response.json({stat:"ok",group:{id:params.get("group_id"),ispoolmoderated:"0"}});
   if(method==="flickr.groups.pools.add"){
    handoffAt=Date.now();
    const mark=await env.DB.prepare("SELECT 1 present FROM attempt_dispatches d JOIN submission_attempts a ON a.attempt_id=d.attempt_id JOIN submission_intents i ON i.intent_id=a.intent_id WHERE i.partition_id=?").bind(input.partitionId).first();
    if(!mark)throw new Error("marker_not_visible");
    return Response.json({stat:"fail",code:6});
   }
   throw new Error("unexpected_flickr_method");
  };
  const result=await consumePartition({...env,FGA_DISPATCH_ENABLED:"1"},input.partitionId,null,"hosted-runtime",provider,{
   fault:async point=>{
    if(point==="marker_committed"){
     markerAt=Date.now();
     if(input.delayAfterMarker){await new Promise(resolve=>setTimeout(resolve,1100));await env.DB.prepare("SELECT 1").first();}
    }
   },monotonicUs:()=>Date.now()*1000,
  });
  const state=await env.DB.prepare("SELECT state,add_dispatch_count FROM submission_intents WHERE partition_id=?").bind(input.partitionId).first();
  return Response.json({result,state,calls,markerAt,handoffAt,clockSource:"Date.now with native I/O refresh",compatibilityDate:"2026-09-11"});
 }
};
