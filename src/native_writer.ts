import type {NativeWriter} from "./native_lifecycle.ts";
import type {FlickrFetch} from "./flickr_reads.ts";
// Private service configuration only. No request can choose account, store or slot.
export function nativeWriter(account:string,store:string,slot:string,token:Pick<SecretsStoreSecret,"get">,fetcher:FlickrFetch=request=>fetch(request)):NativeWriter {
 if(![account,store,slot].every(x=>/^[a-f0-9]{32}$/.test(x)))throw new Error("writer_configuration_unavailable");
 const target=`https://api.cloudflare.com/client/v4/accounts/${account}/secrets_store/stores/${store}/secrets/${slot}`;
 return {async replace(value:string){
  if(value.length>8192)throw new Error("writer_payload_invalid");
  const credential=await token.get();if(!credential||credential.length>2048||/[\x00-\x20\x7f]/.test(credential))throw new Error("writer_credential_unavailable");
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),10000);
  try {const response=await fetcher(new Request(target,{method:"PATCH",redirect:"manual",signal:controller.signal,headers:{Authorization:`Bearer ${credential}`,"Content-Type":"application/json"},body:JSON.stringify({value,scopes:["workers"]})}));
   // An HTTP success is only a dispatch acknowledgement. Native generation observation controls activation.
   if(!response.ok)throw new Error("writer_mutation_unconfirmed");if(response.body)await response.body.cancel();
  }catch{throw new Error("writer_mutation_unconfirmed");}finally{clearTimeout(timer);}
 }};
}
