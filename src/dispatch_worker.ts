import type { SqlStore, WakeHint } from "./admission.ts";
import { runPartition } from "./fail_polite.ts";
import type { Transport } from "./fail_polite.ts";
import { createDispatchTransport } from "./dispatch_transport.ts";
import { reserveFlickrAttempt, DEFAULT_FLICKR_RATE_POLICY } from "./flickr_rate.ts";
import { sameGrant, type GrantSnapshot, type SecretReads, type FlickrFetch } from "./flickr_reads.ts";
import { NOW_US_SQL } from "./installations.ts";
import { scheduleView } from "./scheduling.ts";

export interface DispatchEnv extends SecretReads {
  DB: D1Database;
  FGA_DISPATCH_ENABLED?: string;
  FGA_ARTIFACT_SHA2_256?: string;
}

export async function workerGrant(db: SqlStore, userId: string): Promise<GrantSnapshot | null> {
  return db.prepare(`SELECT l.user_id userId,l.owner_nsid ownerNsid,
    CAST(l.link_revision AS TEXT) revision,n.active_generation generation
    FROM flickr_links l JOIN flickr_native_credentials n ON n.user_id=l.user_id
    JOIN flickr_connection_state c ON c.user_id=l.user_id
    WHERE l.user_id=? AND l.state='linked' AND c.state='linked' AND c.operation_id IS NULL
      AND n.operation_id IS NULL AND n.link_revision=l.link_revision
      AND n.verified_owner_nsid=l.owner_nsid AND n.verified_permission IN ('write','delete')`)
    .bind(userId).first<GrantSnapshot>();
}

async function rejectWorkerGrant(db: SqlStore, snapshot: GrantSnapshot): Promise<void> {
  const tx=crypto.randomUUID(),operation=crypto.randomUUID(),generation=crypto.randomUUID();
  try {
    await db.batch([
      db.prepare(`INSERT INTO transaction_guards(transaction_id,approved) SELECT ?,EXISTS(
        SELECT 1 FROM flickr_links l JOIN flickr_native_credentials n ON n.user_id=l.user_id
        JOIN flickr_connection_state c ON c.user_id=l.user_id
        WHERE l.user_id=? AND l.state='linked' AND l.link_revision=CAST(? AS INTEGER)
        AND n.active_generation=? AND n.operation_id IS NULL AND c.operation_id IS NULL)`)
        .bind(tx,snapshot.userId,snapshot.revision,snapshot.generation),
      db.prepare(`INSERT INTO flickr_lifecycle_operations(operation_id,user_id,kind,phase,generation,retiring_generation,preserve_relink,expected_revision)
        VALUES(?,?,'retire','prepared',?,?,1,CAST(? AS INTEGER))`)
        .bind(operation,snapshot.userId,generation,snapshot.generation,snapshot.revision),
      db.prepare("UPDATE flickr_links SET state='paused',link_revision=link_revision+1 WHERE user_id=?").bind(snapshot.userId),
      db.prepare("UPDATE flickr_connection_state SET state='relink_required',local_state='retirement_pending',operation_id=?,external_removal=0 WHERE user_id=?")
        .bind(operation,snapshot.userId),
      db.prepare("UPDATE flickr_native_credentials SET operation_id=? WHERE user_id=?").bind(operation,snapshot.userId),
      db.prepare("UPDATE flickr_write_gates SET enabled=0,revision=revision+1 WHERE scope='user' AND scope_id=? AND enabled=1").bind(snapshot.userId),
      db.prepare(`INSERT INTO audit_events(event_id,user_id,action,request_correlation_id,outcome,reason,target_id,source_component)
        VALUES(?,?,'flickr.grant_rejected',?,'succeeded','definitive_flickr_rejection',?,'fga_group_submission_worker')`)
        .bind(crypto.randomUUID(),snapshot.userId,operation,operation),
      db.prepare("DELETE FROM transaction_guards WHERE transaction_id=?").bind(tx),
    ]);
  } catch { /* A stale result cannot retire a successor; the already-paused gate remains safe. */ }
}

export async function consumePartition(
  env: DispatchEnv, partitionId: string, revision: string | null, source: string,
  fetcher: FlickrFetch = request => fetch(request),
): Promise<string> {
  if(env.FGA_DISPATCH_ENABLED!=="1")return "disabled";
  const owner=await env.DB.prepare("SELECT user_id userId FROM group_partitions WHERE partition_id=?")
    .bind(partitionId).first<{userId:string}>();
  if(!owner)return "no_partition";
  const snapshot=await workerGrant(env.DB,owner.userId);
  let selected:Promise<Transport>|undefined;
  const current=async()=>{
    if(!snapshot||!sameGrant(snapshot,await workerGrant(env.DB,owner.userId)))throw new Error("flickr_authority_changed");
  };
  const transport=()=>selected??=(async()=>{
    await current();
    return createDispatchTransport(env,snapshot!.generation,current,fetcher);
  })();
  return runPartition({db:env.DB,monotonicUs:()=>Date.now()*1000,artifactSha2_256:env.FGA_ARTIFACT_SHA2_256,
    transport:{
      membership:async context=>(await transport()).membership(context),
      preflight:async context=>(await transport()).preflight(context),
      prepareAdd:async context=>(await transport()).prepareAdd(context),
    },
    reserve:context=>reserveFlickrAttempt(env.DB,context,DEFAULT_FLICKR_RATE_POLICY),
    async rateRetryDelayMs(){
      const row=await env.DB.prepare(`SELECT CAST(MAX(1000,MIN(3600000,(expires_at_us-${NOW_US_SQL})/1000+1)) AS INTEGER) delay
        FROM flickr_rate_window WHERE singleton=1`).first<{delay:number}>();
      return row?.delay??1000;
    },
    async beforePreflight(lease){
      return (await env.DB.prepare(`SELECT 1 valid FROM group_partitions WHERE partition_id=?
        AND lease_id=? AND lease_generation=CAST(? AS INTEGER)
        AND lease_expires_at_us-${NOW_US_SQL}>30000000
        AND invocation_deadline_at_us-${NOW_US_SQL}>30000000`)
        .bind(partitionId,lease.leaseId,lease.generation).first())!==null;
    },
    async onFlickrCode(code){if(snapshot&&(code===98||code===99))await rejectWorkerGrant(env.DB,snapshot);},
  },partitionId,source,revision);
}

/** Durable Object storage holds an advisory wake, never queue or lease authority. */
export class PartitionWorker {
  private ctx:DurableObjectState;
  private env:DispatchEnv;
  constructor(ctx:DurableObjectState,env:DispatchEnv){this.ctx=ctx;this.env=env;}

  private async arm(partitionId:string,allowImmediate:boolean):Promise<void>{
    if(this.env.FGA_DISPATCH_ENABLED!=="1")return;
    const view=await scheduleView(this.env.DB,partitionId);
    if(!view?.wakeAfterUs||!view.headId)return;
    // Even paused scopes need to resolve abandoned marked attempts after expiry.
    const recovering=await this.env.DB.prepare("SELECT 1 FROM submission_intents WHERE intent_id=? AND state='attempting'").bind(view.headId).first();
    if(view.gatesEnabled!==1&&!recovering)return;
    const delta=BigInt(view.wakeAfterUs)-BigInt(view.nowUs);
    if(delta<=0n&&!allowImmediate)return; // A refused due claim waits for the durable sweep.
    const desired=Date.now()+Math.min(86_400_000,Math.max(50,Number(delta/1000n)));
    await this.ctx.storage.transaction(async tx=>{
      const old=await tx.getAlarm();if(old===null||desired<old)await tx.setAlarm(desired);
    });
  }

  private async consume(partitionId:string,revision:string|null,source:string):Promise<void>{
    const before=await scheduleView(this.env.DB,partitionId);
    try{await consumePartition(this.env,partitionId,revision,source);}
    finally{
      const after=await scheduleView(this.env.DB,partitionId);
      await this.arm(partitionId,!!before?.headId&&after?.headId!==before.headId);
    }
  }

  async fetch(request:Request):Promise<Response>{
    if(request.method!=="POST"||new URL(request.url).pathname!=="/wake")return new Response(null,{status:404});
    if(this.env.FGA_DISPATCH_ENABLED!=="1")return new Response(null,{status:503});
    let input:WakeHint&{source:string};
    try{
      const text=await request.text();if(text.length>1024)throw new Error();
      input=JSON.parse(text);
      if(!input||Object.keys(input).sort().join()!=="partitionId,source,wakeRevision"||
        typeof input.partitionId!=="string"||!/^[A-Za-z0-9][A-Za-z0-9@._:-]{0,127}$/.test(input.partitionId)||
        typeof input.wakeRevision!=="string"||!/^(0|[1-9][0-9]{0,18})$/.test(input.wakeRevision)||
        !["admission","sweep"].includes(input.source))throw new Error();
    }catch{return new Response(null,{status:400});}
    const bound=await this.ctx.storage.transaction(async tx=>{
      const old=await tx.get<string>("partitionId");if(old!==undefined&&old!==input.partitionId)return false;
      if(old===undefined)await tx.put("partitionId",input.partitionId);return true;
    });
    if(!bound)return new Response(null,{status:409});
    this.ctx.waitUntil(this.consume(input.partitionId,input.wakeRevision,input.source==="admission"?"hint":"sweep"));
    return new Response(null,{status:204});
  }

  async alarm():Promise<void>{
    if(this.env.FGA_DISPATCH_ENABLED!=="1")return;
    const partitionId=await this.ctx.storage.get<string>("partitionId");
    if(partitionId)await this.consume(partitionId,null,"alarm");
  }
}
