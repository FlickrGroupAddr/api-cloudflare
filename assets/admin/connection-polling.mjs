// Poll only while the visible connection has unfinished lifecycle work.
export function createConnectionPoller({shouldPoll,load,apply,onError,schedule=setTimeout,cancel=clearTimeout,delay=15000}){
 let timer=null,running=false,enabled=false,epoch=0;
 const clear=()=>{if(timer!==null)cancel(timer);timer=null;};
 function sync(){enabled=true;clear();if(!running&&shouldPoll())timer=schedule(()=>void poll(),delay);}
 async function poll(){
  timer=null;if(!enabled||running||!shouldPoll())return;
  const generation=epoch;running=true;
  try{const value=await load();if(enabled&&generation===epoch&&shouldPoll())apply(value);}
  catch(error){if(enabled&&generation===epoch&&shouldPoll())onError(error);}
  finally{running=false;if(enabled)sync();}
 }
 return {sync,stop(){enabled=false;epoch++;clear();}};
}
