// MIT License; copyright 2026 Terry Ott.
// Unregistered PMB-1 source bridge. No HTTP control, bootstrap or reopen route.
import { Pmb1NativeWakeup, bootstrap } from '../probes/pmb1-native-wakeup/candidate.ts';
import type { Admission } from '../probes/pmb1-native-wakeup/candidate.ts';
import type { VerifyDisposition } from '../probes/pmb1-object/candidate.ts';
import type { SqlStore } from './admission.ts';
import type { Lease } from './scheduling.ts';
import type { PartitionLifetime } from './fail_polite.ts';

type Storage = Pick<DurableObjectStorage, 'sql' | 'transaction'>;
export interface PartitionCapture { readonly id: string; readonly generation: string; readonly entry: 'fetch' | 'alarm' }
export type VerifyPartitionReconciliation = (capture: Readonly<PartitionCapture>) => Promise<{
  id:string; generation:string; oldExecutionStopped:true; pendingD1Settled:true; evidence:string
} | null>;
interface Row { id: string; generation: string; entry: string; partition_id: string | null; claim_id:string|null; lease: string | null; grant_binding:string|null;
  attempt_id: string | null; attempt_binding: string | null; due_token: string | null; dispatch: number; state: string; receipt: string | null }
const fail = (reason = 'partition_maintenance_fenced'): never => { throw new Error(reason); };
const validGeneration = (s: unknown): s is string => typeof s === 'string' && /^[1-9][0-9]{0,18}$/.test(s) && BigInt(s) <= 9223372036854775807n;
const BRIDGE_SCHEMA = [
  `CREATE TABLE pmb1_partition_invocations (
      id TEXT PRIMARY KEY NOT NULL, generation TEXT NOT NULL, entry TEXT NOT NULL,
      partition_id TEXT, claim_id TEXT, lease TEXT, grant_binding TEXT, attempt_id TEXT, attempt_binding TEXT, due_token TEXT, dispatch INTEGER NOT NULL DEFAULT 0,
      state TEXT NOT NULL CHECK(state IN ('active','settled')), receipt TEXT)`,
  `CREATE TABLE pmb1_partition_binding (id INTEGER PRIMARY KEY CHECK(id=1), partition_id TEXT NOT NULL)`,
  ...['pmb1_partition_invocations','pmb1_partition_binding'].flatMap(table=>['INSERT','UPDATE','DELETE'].map(event=>
    `CREATE TRIGGER ${table}_${event.toLowerCase()} BEFORE ${event} ON ${table}
        BEGIN SELECT CASE WHEN (SELECT COUNT(*) FROM maintenance_control)=1 AND EXISTS(
          SELECT 1 FROM maintenance_control WHERE singleton_id=1 AND typeof(singleton_id)='integer'
          AND typeof(generation)='integer' AND generation BETWEEN 1 AND 9223372036854775807 AND typeof(state)='text' AND state='open')
          THEN 1 ELSE RAISE(ABORT,'maintenance_closed') END; END`)),
];

/** Explicit isolated-only setup; never called by construction, fetch or alarm. */
export async function bootstrapPartitionMaintenance(storage: Storage): Promise<void> {
  await bootstrap(storage);
  await storage.transaction(async () => {
    for(const sql of BRIDGE_SCHEMA)storage.sql.exec(sql);
  });
}

/** Local admission is distinct from the D1 lease/attempt/dispatch/result authority.
 * A returned handler is settled only after a fixed exact-attempt D1 receipt,
 * mandatory grant effects and rate release are confirmed. A failed/unknown call
 * leaves its durable invocation active, including after restart. No result replay.
 */
export class PartitionMaintenance {
  private storage: Storage;
  private wake: Pmb1NativeWakeup;
  private verifyReconciliation: VerifyPartitionReconciliation;
  constructor(storage: Storage, verify: VerifyDisposition, clock: () => number = Date.now,
    verifyReconciliation: VerifyPartitionReconciliation = async () => null) {
    this.storage = storage; this.wake = new Pmb1NativeWakeup(storage, verify, clock);
    this.verifyReconciliation=verifyReconciliation;
    this.installed();
  }
  private installed():void {
    for(const sql of BRIDGE_SCHEMA){
      const match=/^CREATE (TABLE|TRIGGER) ([a-z0-9_]+)/.exec(sql)!;
      const rows=this.storage.sql.exec('SELECT sql FROM sqlite_master WHERE name=? AND type=?',match[2],match[1].toLowerCase()).toArray();
      if(rows.length!==1||rows[0].sql!==sql)fail('partition_schema_unconfirmed');
    }
  }
  private generation(): string {
    const rows = this.storage.sql.exec(`SELECT singleton_id,typeof(singleton_id) kt,
      CAST(generation AS TEXT) generation,typeof(generation) gt,state,typeof(state) st FROM maintenance_control`).toArray();
    const r = rows[0];
    if (rows.length !== 1 || r.singleton_id !== 1 || r.kt !== 'integer' || r.gt !== 'integer'
      || r.st !== 'text' || r.state !== 'open' || !validGeneration(r.generation)) fail();
    return r.generation as string;
  }
  /** Synchronous and immutable. Call as the first handler action before any await. */
  capture(entry: PartitionCapture['entry']): PartitionCapture {
    return Object.freeze({ id: crypto.randomUUID(), generation: this.generation(), entry });
  }
  private exact(c: PartitionCapture): Row {
    if (this.generation() !== c.generation) fail();
    const rows = this.storage.sql.exec('SELECT * FROM pmb1_partition_invocations WHERE id=?', c.id).toArray();
    const r = rows[0] as unknown as Row;
    if (rows.length !== 1 || r.generation !== c.generation || r.entry !== c.entry || r.state !== 'active') fail();
    return r;
  }
  async admit(input: PartitionCapture): Promise<PartitionCapture> {
    const c = Object.freeze({ id: input.id, generation: input.generation, entry: input.entry });
    if (!validGeneration(c.generation) || !/^[a-f0-9-]{36}$/.test(c.id) || !['fetch','alarm'].includes(c.entry)) fail();
    await this.storage.transaction(async tx => {
      if (this.generation() !== c.generation || await tx.get('pmb1:admission') !== true) fail();
      this.storage.sql.exec('INSERT INTO pmb1_partition_invocations(id,generation,entry,state) VALUES(?,?,?,?)', c.id,c.generation,c.entry,'active');
    });
    return c;
  }
  async checkNew(c: PartitionCapture): Promise<void> {
    await this.storage.transaction(async tx => { this.exact(c); if (await tx.get('pmb1:admission') !== true) fail(); });
  }
  async bind(c: PartitionCapture, partitionId: string): Promise<boolean> {
    return this.storage.transaction(async tx => {
      this.exact(c); if (await tx.get('pmb1:admission') !== true) fail();
      const old = this.storage.sql.exec('SELECT partition_id FROM pmb1_partition_binding WHERE id=1').toArray();
      if (old.length && old[0].partition_id !== partitionId) return false;
      if (!old.length) this.storage.sql.exec('INSERT INTO pmb1_partition_binding VALUES(1,?)', partitionId);
      this.storage.sql.exec('UPDATE pmb1_partition_invocations SET partition_id=? WHERE id=?', partitionId,c.id); return true;
    });
  }
  async partition(c: PartitionCapture): Promise<string | null> {
    return this.storage.transaction(async () => { this.exact(c);
      return this.storage.sql.exec('SELECT partition_id FROM pmb1_partition_binding WHERE id=1').toArray()[0]?.partition_id as string ?? null; });
  }
  lifetime(c: PartitionCapture, db: SqlStore): PartitionLifetime {
    return {
      checkNew: () => this.checkNew(c),
      authority: snapshot => this.storage.transaction(async()=>{
        const r=this.exact(c);if(r.claim_id!==null||r.grant_binding!==null)fail();
        this.storage.sql.exec('UPDATE pmb1_partition_invocations SET grant_binding=? WHERE id=?',JSON.stringify(snapshot),c.id);
      }),
      claiming: (partitionId,invocationId) => this.storage.transaction(async tx=>{
        const r=this.exact(c);if(await tx.get('pmb1:admission')!==true||r.partition_id!==partitionId||r.claim_id!==null)fail();
        this.storage.sql.exec('UPDATE pmb1_partition_invocations SET claim_id=? WHERE id=?',invocationId,c.id);
      }),
      claimed: lease => this.storage.transaction(async () => {
        const r = this.exact(c); if (r.lease !== null || r.partition_id !== lease.partitionId || r.claim_id!==lease.invocationId) fail();
        this.storage.sql.exec('UPDATE pmb1_partition_invocations SET lease=? WHERE id=?', JSON.stringify(lease),c.id);
      }),
      attempted: async (lease, attemptId) => {
        const bound = await db.prepare(`SELECT attempt_id attemptId,intent_id intentId,lease_id leaseId,
          CAST(lease_generation AS TEXT) generation FROM submission_attempts WHERE attempt_id=?`).bind(attemptId)
          .first<Record<string,unknown>>();
        if (!bound || bound.intentId !== lease.headId) fail();
        await this.storage.transaction(async () => {
          const r = this.exact(c); if (r.lease !== JSON.stringify(lease) || r.attempt_id !== null) fail();
          this.storage.sql.exec('UPDATE pmb1_partition_invocations SET attempt_id=?,attempt_binding=? WHERE id=?',attemptId,JSON.stringify(bound),c.id);
        });
      },
      dispatching: (lease, attemptId) => this.storage.transaction(async tx => {
        const r = this.exact(c);
        if (await tx.get('pmb1:admission') !== true || r.lease !== JSON.stringify(lease) || r.attempt_id !== attemptId || r.dispatch) fail();
        this.storage.sql.exec('UPDATE pmb1_partition_invocations SET dispatch=1 WHERE id=?',c.id);
      }),
    };
  }
  async arm(c: PartitionCapture, partitionId: string, due: number): Promise<void> {
    await this.checkNew(c);
    await this.wake.schedule(c.generation, partitionId, due);
  }
  /** Native events provide no causal identity; select current due work only. */
  async due(c: PartitionCapture): Promise<Admission | null> {
    await this.checkNew(c);
    const t = await this.wake.admitCurrentDue();
    if (t && t.generation !== c.generation) fail();
    return t;
  }
  async markDue(c: PartitionCapture, t: Admission): Promise<void> {
    await this.checkNew(c); if (t.generation !== c.generation) fail();
    await this.storage.transaction(async () => { this.exact(c);
      this.storage.sql.exec('UPDATE pmb1_partition_invocations SET due_token=? WHERE id=?',JSON.stringify(t),c.id); });
    await this.wake.beginExternal(t);
  }
  async settleDue(c: PartitionCapture, t: Admission): Promise<void> {
    // This binary ledger acknowledgment follows the domain receipt; it is not it.
    const r = this.storage.sql.exec('SELECT * FROM pmb1_partition_invocations WHERE id=?',c.id).toArray()[0];
    if (!r || r.state !== 'settled' || r.generation !== c.generation || !r.receipt || r.due_token !== JSON.stringify(t)) fail();
    await this.wake.settleExternal(t,'confirmed_success');
  }
  /** Only exact durable D1 facts can dispose a bound attempt. Called after all
   * callbacks/finally blocks returned, or by an explicit restart reconciliation.
   * No dispatch, domain resolution, reservation release or grant mutation replay.
   */
  async finish(c: PartitionCapture, db: SqlStore, result: string): Promise<void> {
    const row = this.exact(c);
    let receipt: unknown = { result, attempt: null };
    if(row.lease===null && row.claim_id!==null){
      const claimed=await db.prepare("SELECT event_id FROM partition_lease_events WHERE invocation_id=? AND kind='claim'").bind(row.claim_id).first();
      if(claimed)fail('partition_claim_unbound');
    }
    if (row.lease !== null) {
      const lease = JSON.parse(row.lease) as Lease;
      if (!row.attempt_id || !row.attempt_binding) fail('partition_attempt_unbound');
      const binding = JSON.parse(row.attempt_binding!) as Record<string,unknown>;
      const grant=row.grant_binding?JSON.parse(row.grant_binding) as {generation:string;revision:string}|null:null;
      const actual = await db.prepare(`SELECT a.attempt_id attemptId,a.intent_id intentId,a.lease_id leaseId,
        CAST(a.lease_generation AS TEXT) generation,r.outcome,r.reason,r.flickr_code code,
        i.state intentState,EXISTS(SELECT 1 FROM attempt_dispatches d WHERE d.attempt_id=a.attempt_id) marked,
        (SELECT COUNT(*) FROM submission_blocks b WHERE b.photo_id=i.photo_id AND b.group_id=i.group_id) blocked,
        (SELECT COUNT(*) FROM flickr_rate_reservations q WHERE q.attempt_id=a.attempt_id AND q.released=0) pendingReservations,
        EXISTS(SELECT 1 FROM flickr_connection_state cs JOIN flickr_native_credentials nc ON nc.user_id=cs.user_id
          JOIN flickr_links fl ON fl.user_id=cs.user_id JOIN flickr_lifecycle_operations op ON op.operation_id=cs.operation_id
          WHERE cs.user_id=i.user_id AND cs.state='relink_required' AND fl.state='paused'
          AND nc.operation_id=cs.operation_id AND op.kind='retire'
          AND op.retiring_generation=? AND op.expected_revision=CAST(? AS INTEGER)) grantRetired,
        EXISTS(SELECT 1 FROM flickr_links fl JOIN flickr_native_credentials nc ON nc.user_id=fl.user_id
          WHERE fl.user_id=i.user_id AND (nc.active_generation<>? OR fl.link_revision<>CAST(? AS INTEGER))) grantSuperseded
        FROM submission_attempts a JOIN submission_intents i ON i.intent_id=a.intent_id
        JOIN attempt_resolutions r ON r.attempt_id=a.attempt_id WHERE a.attempt_id=?`)
        .bind(grant?.generation??null,grant?.revision??null,grant?.generation??null,grant?.revision??null,row.attempt_id).first<Record<string,unknown>>();
      if (!actual || actual.intentId !== lease.headId || actual.attemptId !== binding.attemptId
        || actual.leaseId !== binding.leaseId || actual.generation !== binding.generation
        || actual.pendingReservations !== 0 || actual.intentState !== actual.outcome
        || (['moderation_submitted','delivery_uncertain'].includes(String(actual.outcome)) && actual.blocked !== 1)
        || ([98,99].includes(Number(actual.code)) && (!grant || (actual.grantRetired !== 1 && actual.grantSuperseded!==1)))) fail('partition_domain_unsettled');
      receipt = { result, ...actual };
    }
    await this.storage.transaction(async () => { this.exact(c);
      this.storage.sql.exec("UPDATE pmb1_partition_invocations SET state='settled',receipt=? WHERE id=?",JSON.stringify(receipt),c.id); });
  }
  /** Exact retained token only. Never substitutes current generation/lease. */
  async reconcile(input: PartitionCapture, db: SqlStore): Promise<void> {
    const c=Object.freeze({...input}),proof=await this.verifyReconciliation(c);
    if(!proof||proof.id!==c.id||proof.generation!==c.generation||proof.oldExecutionStopped!==true||proof.pendingD1Settled!==true
      || !/^[a-f0-9]{64}$/.test(proof.evidence)) fail('partition_reconciliation_unconfirmed');
    if(this.generation()!==c.generation)fail();
    const r=this.storage.sql.exec('SELECT * FROM pmb1_partition_invocations WHERE id=?',c.id).toArray()[0] as unknown as Row;
    if(!r||r.generation!==c.generation||r.entry!==c.entry)fail();
    if(r.state==='active')await this.finish(c,db,'reconciled');
    else if(r.state!=='settled'||!r.receipt)fail();
    if(r.due_token){
      const t=JSON.parse(r.due_token) as Admission;
      const state=this.storage.sql.exec('SELECT state FROM pmb1_wake_executions WHERE id=?',t.id).toArray()[0]?.state;
      if(state==='external_pending')await this.settleDue(c,t);
      else if(state==='admitted')await this.wake.cancel(t);
      else if(state!=='settled')fail();
    }
  }
  async stop(expected: string): Promise<void> { await this.wake.suspendAdmission(expected); }
  async close(expected: string): Promise<void> {
    await this.storage.transaction(async tx => {
      if(this.generation()!==expected||await tx.get('pmb1:admission')!==false)fail('partition_admission_not_stopped');
      if (this.storage.sql.exec("SELECT id FROM pmb1_partition_invocations WHERE state='active'").toArray().length
        ||this.storage.sql.exec("SELECT id FROM pmb1_wake_executions WHERE state NOT IN ('settled','cancelled')").toArray().length) fail('partition_drain_incomplete');
    });
    await this.wake.deleteScheduled(expected); await this.wake.close(expected);
  }
  async reopen(expected: string): Promise<void> { this.installed();await this.wake.reopen(expected); }
}
