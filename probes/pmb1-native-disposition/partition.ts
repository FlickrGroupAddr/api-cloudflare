// MIT License; copyright 2026 Terry Ott.
import type { MainEntryBinding } from '../../src/main_entry_maintenance.ts';
import type { PartitionCapture, VerifyPartitionReconciliation } from '../../src/partition_maintenance.ts';
import type { VerifyDisposition } from '../pmb1-object/candidate.ts';
import { createNativeSource, type NativeSourceInput } from '../pmb1-native-object-reader/native-source.ts';
import type { NativeCaptureOwner } from '../pmb1-native-object-reader/native-owner.ts';
import type { NativeCaptureControl } from '../pmb1-native-object-reader/native-control.ts';
import { captureSupportedBoundary, type BoundaryCapture } from '../pmb1-native-object-reader/object-kv-interface.ts';
import { D1DomainReader, validateDomain, domainText as text, domainInteger as integer, type DomainFacts } from './domain.ts';
import { ReviewedCoverage, freezeEvidence } from './coverage.ts';
import { DispositionUnavailable, type ObservationBounds } from './observer.ts';

const fail = (reason: string): never => { throw new DispositionUnavailable(reason); };
const gen = (g: unknown): g is string => typeof g === 'string' && /^[1-9][0-9]{0,18}$/.test(g) && BigInt(g) <= 9223372036854775807n;
const hash = async (v: unknown) => Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(JSON.stringify(v)))), b => b.toString(16).padStart(2, '0')).join('');
type Storage = Pick<DurableObjectStorage, 'sql' | 'transaction'>;
export interface PartitionConfiguration {
  binding: MainEntryBinding; journalDatabaseId: string; domainDatabaseId: string;
  namespace: string; id: string; deadlineMs: number; bounds: ObservationBounds;
  source: NativeSourceInput;
}
interface Row extends Record<string, unknown> {
  id: string; generation: string; entry: string; partition_id: string | null;
  claim_id: string | null; lease: string | null; grant_binding: string | null;
  attempt_id: string | null; attempt_binding: string | null; due_token: string | null; dispatch: number;
  state: string; receipt: string | null;
}

/** Validate complete native application SQL/KV/alarm capture from the existing
 * #0245 adapter. Its accepted raw __cf_kv boundary remains explicitly unobserved.
 * Local receipt rows alone never authorize an old callback or pending D1 call.
 */
export function validatePartitionCapture(capture: BoundaryCapture, generation: string, namespace: string, id: string): void {
  if (capture.boundary !== 'pmb1-private-object-kv-interface-v1' || !gen(generation)) fail('partition_boundary');
  const object = capture.objects.find(o => o.namespace === namespace && o.id === id);
  if (!object || object.before.generation !== generation || object.after.generation !== generation
    || object.before.state !== 'closed' || object.after.state !== 'closed' || object.alarm.timeMs !== null
    || object.alarm.dispatch !== null) fail('partition_closed_observation');
  // All included objects from the independently retained population are covered,
  // not just the target selected for this verifier invocation.
  for (const other of capture.objects) {
    if (other.before.state !== 'closed' || other.after.state !== 'closed'
      || other.alarm.timeMs !== null || other.alarm.dispatch !== null) fail('partition_other_object_pending');
    const rows = (name: string): Record<string, unknown>[] => {
      const table = other.tables[name]; if (!table) return fail('partition_table_missing');
      return table.rows.map(row => Object.fromEntries(table.columns.map((column, i) => [column,
        row.cells[i][0] === 'null' ? null : row.cells[i][1]])));
    };
    for (const row of rows('pmb1_partition_invocations')) if (row.state !== 'settled' || typeof row.receipt !== 'string') fail('partition_invocation_pending');
    for (const row of rows('pmb1_wake_executions')) if (!['settled', 'cancelled'].includes(String(row.state))) fail('partition_wake_pending');
    if (rows('pmb1_wake_work').length) fail('partition_scheduled_work');
    const kv = new Map(other.kv), admission = kv.get('pmb1:admission');
    if (!admission || admission[0] !== 'boolean' || admission[1] !== false) fail('partition_admission_not_stopped');
    if (kv.has('pmb1:wake-value')) fail('partition_scheduled_value');
  }
}

/** Concrete native factory + bounded local read + complete D1 reader. No verifier
 * callback, HTTP control, store mutation, result replay or native process API.
 * Authenticated old-execution custody is an external positive factual gate;
 * constructors do not create it and no phase/timeout/current generation implies it.
 */
export class NativePartitionDisposition {
  private readonly config: Readonly<PartitionConfiguration> | undefined;
  private readonly storage: Storage | undefined;
  private readonly domain: D1DomainReader | undefined;
  private readonly coverage: ReviewedCoverage | undefined;
  private readonly bindings: Record<string, DurableObjectNamespace<NativeCaptureOwner>> | undefined;
  private readonly control: DurableObjectNamespace<NativeCaptureControl> | undefined;
  private spent = false;
  private evidenceRecord: unknown;
  constructor(config?: PartitionConfiguration, storage?: Storage, domain?: D1DomainReader,
    coverage?: ReviewedCoverage, bindings?: Record<string, DurableObjectNamespace<NativeCaptureOwner>>,
    control?: DurableObjectNamespace<NativeCaptureControl>) {
    this.config = config ? Object.freeze(structuredClone(config)) : undefined;
    this.storage = storage; this.domain = domain; this.coverage = coverage;
    this.bindings = bindings ? Object.freeze({ ...bindings }) : undefined; this.control = control;
  }
  private gate(): PartitionConfiguration {
    const c = this.config;
    if (!c || !this.domain || !this.coverage || !this.storage || !this.bindings || !this.control) return fail('partition_capabilities_unobserved');
    if (!Number.isFinite(c.deadlineMs) || performance.now() >= c.deadlineMs) fail('partition_deadline');
    if (!/^[a-f0-9]{32}$/.test(c.namespace) || !/^[a-f0-9]{64}$/.test(c.id)
      || this.domain.databaseId !== c.domainDatabaseId
      || !this.coverage.records().expected.resources.some(r => r.kind === 'object' && r.id === c.namespace + '/' + c.id)
      || !c.source.request.expectedObjects.some(o => o.namespace === c.namespace && o.id === c.id)) fail('partition_target_binding');
    this.coverage.check(c.binding, c.journalDatabaseId, c.domainDatabaseId); return c;
  }
  readonly verify: VerifyDisposition = async generation => {
    if (!gen(generation)) fail('partition_generation');
    const c = this.gate();
    if (this.spent) fail('partition_native_read_spent'); this.spent = true;
    const source = await createNativeSource(c.source, this.bindings!, this.control!);
    this.gate();
    if (c.source.request.limits.milliseconds > c.deadlineMs - performance.now()) fail('partition_native_window');
    const captured = await captureSupportedBoundary(source, c.source.request); this.gate();
    validatePartitionCapture(captured, generation, c.namespace, c.id);
    const domain = await this.domain!.capture(c.deadlineMs); validateDomain(domain); this.gate();
    for (const object of captured.objects) {
      const table = object.tables.pmb1_partition_invocations;
      if (!table) fail('partition_table_missing');
      for (const row of table.rows) {
        const value = Object.fromEntries(table.columns.map((column, i) => [column,
          row.cells[i][0] === 'null' ? null : column === 'dispatch' ? Number(row.cells[i][1]) : row.cells[i][1]]));
        this.validateOriginal(value as Row, domain);
        this.validateReceipt(value as Row, domain);
      }
    }
    const record = freezeEvidence({ generation, captured, domain, coverage: this.coverage!.records() });
    if (new TextEncoder().encode(JSON.stringify(record)).byteLength > c.bounds.bytes) fail('partition_evidence_bound');
    this.evidenceRecord = record;
    return { generation, preCloseExecutionsDisposed: true, temporaryExecutionsDisposed: true,
      oldVersionsFenced: true, queuedAndAlarmCallbacksDisposed: true };
  };
  readonly reconcile: VerifyPartitionReconciliation = async capture => {
    if (!capture || !/^[a-f0-9-]{36}$/.test(capture.id) || !gen(capture.generation)
      || !['fetch', 'alarm'].includes(capture.entry)) fail('partition_capture');
    const token = Object.freeze({ ...capture }), c = this.gate();
    // No same-writer acknowledgment, empty local tracker or elapsed timeout may
    // enter here. Exact retained native retirement + terminal operation custody
    // is authenticated independently before constructing ReviewedCoverage.
    const retired = this.coverage!.retired(token);
    const row = await this.readInvocation(token, c); this.gate();
    const domain = await this.domain!.capture(c.deadlineMs); validateDomain(domain);
    this.validateOriginal(row, domain); this.gate();
    // A completed local record must retain its genuine original domain receipt.
    // Active pre-receipt recovery still relies on the exact original tuple and
    // settled independent domain facts; finish will create its first receipt.
    if (row.state === 'settled') this.validateReceipt(row, domain);
    else if (row.receipt !== null) fail('partition_receipt_state');
    const after = await this.readInvocation(token, c);
    if (JSON.stringify(row) !== JSON.stringify(after)) fail('partition_invocation_drift');
    const record = freezeEvidence({ token, row, retired, domain, coverage: this.coverage!.records() });
    if (new TextEncoder().encode(JSON.stringify(record)).byteLength > c.bounds.bytes) fail('partition_evidence_bound');
    const evidence = await hash(record); this.gate(); this.evidenceRecord = record;
    return { id: token.id, generation: token.generation, oldExecutionStopped: true, pendingD1Settled: true, evidence };
  };
  private async readInvocation(token: PartitionCapture, c: PartitionConfiguration): Promise<Readonly<Row>> {
    let entered = false, active = true, timer: ReturnType<typeof setTimeout> | undefined;
    try {
      return await Promise.race([this.storage!.transaction(async () => {
        if (entered) fail('partition_transaction_reentered'); entered = true; if (!active) fail('partition_deadline'); this.gate();
        const controls = this.storage!.sql.exec("SELECT CAST(generation AS TEXT) generation,state FROM maintenance_control LIMIT 2").toArray();
        if (controls.length !== 1 || controls[0].generation !== token.generation || controls[0].state !== 'open') fail('partition_generation_drift');
        // Keep arbitrary lease/receipt JSON behind a native aggregate byte
        // preflight. No unbounded SELECT * is materialized before this check.
        const columns = ['id', 'generation', 'entry', 'partition_id', 'claim_id', 'lease', 'grant_binding', 'attempt_id', 'attempt_binding', 'due_token', 'dispatch', 'state', 'receipt'];
        const columnRows = this.storage!.sql.exec("SELECT name FROM pragma_table_xinfo('pmb1_partition_invocations') ORDER BY cid LIMIT 14").toArray();
        if (JSON.stringify(columnRows.map(r => r.name)) !== JSON.stringify(columns)) fail('partition_local_schema');
        const cost = columns.map(column => `coalesce(length(CAST(${column} AS BLOB)),0)`).join('+');
        const p = this.storage!.sql.exec(`SELECT CAST(count(*) AS TEXT) n,
          CAST(coalesce(sum(4096+6*(${cost})),0) AS TEXT) b FROM pmb1_partition_invocations WHERE id=?`, token.id).toArray();
        if (p.length !== 1 || p[0].n !== '1' || typeof p[0].b !== 'string' || !/^[0-9]+$/.test(p[0].b)
          || BigInt(p[0].b) > BigInt(c.bounds.bytes)) fail('partition_local_acquisition_bound');
        const rows = this.storage!.sql.exec('SELECT ' + columns.join(',') + ' FROM pmb1_partition_invocations WHERE id=? LIMIT 2', token.id).toArray();
        const row = rows[0] as unknown as Row;
        if (rows.length !== 1 || row.id !== token.id || row.generation !== token.generation || row.entry !== token.entry
          || !['active', 'settled'].includes(row.state) || ![0, 1].includes(row.dispatch)) fail('partition_original_binding');
        if (!active) fail('partition_deadline'); this.gate(); return Object.freeze(structuredClone(row));
      }), new Promise<never>((_, reject) => { timer = setTimeout(() => {
        active = false; reject(new DispositionUnavailable('partition_deadline'));
      }, c.deadlineMs - performance.now()); })]);
    } catch (error) { if (error instanceof DispositionUnavailable) throw error; return fail('partition_local_read_unknown'); }
    finally { active = false; if (timer !== undefined) clearTimeout(timer); }
  }
  private validateOriginal(row: Row, domain: DomainFacts) {
    const all = domain.tables;
    if (row.lease === null) {
      if (row.attempt_id !== null || row.attempt_binding !== null || row.dispatch !== 0
        || (row.claim_id !== null && all.partition_lease_events.some(r => text(r.invocation_id) === row.claim_id && text(r.kind) === 'claim'))) fail('partition_claim_unbound');
      return;
    }
    let lease: Record<string, unknown>, binding: Record<string, unknown>, grant: Record<string, unknown> | null;
    try { lease = JSON.parse(row.lease); binding = JSON.parse(row.attempt_binding!); grant = row.grant_binding ? JSON.parse(row.grant_binding) : null; }
    catch { return fail('partition_original_json'); }
    const attempt = all.submission_attempts.find(r => text(r.attempt_id) === row.attempt_id);
    const resolution = all.attempt_resolutions.find(r => text(r.attempt_id) === row.attempt_id);
    const intent = all.submission_intents.find(r => text(r.intent_id) === lease.headId);
    if (!attempt || !resolution || !intent || typeof binding.generation !== 'string' || !gen(binding.generation)
      || binding.intentId !== lease.headId || lease.partitionId !== row.partition_id || lease.invocationId !== row.claim_id
      || lease.leaseId !== binding.leaseId || lease.generation !== binding.generation
      || text(attempt.intent_id) !== lease.headId || text(attempt.attempt_id) !== binding.attemptId
      || text(attempt.lease_id) !== binding.leaseId || integer(attempt.lease_generation) !== String(binding.generation)
      || text(intent.partition_id) !== row.partition_id || text(intent.state) !== text(resolution.outcome)) fail('partition_domain_original_unsettled');
    if (row.dispatch !== Number(all.attempt_dispatches.some(r => text(r.attempt_id) === row.attempt_id))) fail('partition_dispatch_mismatch');
    if (['98', '99'].includes(integer(resolution!.flickr_code) ?? '')) {
      const user = text(intent!.user_id), connection = all.flickr_connection_state.find(r => text(r.user_id) === user);
      const native = all.flickr_native_credentials.find(r => text(r.user_id) === user), link = all.flickr_links.find(r => text(r.user_id) === user);
      const retired = all.flickr_lifecycle_operations.some(r => text(r.user_id) === user && text(r.kind) === 'retire'
        && text(r.phase) === 'complete' && text(r.retiring_generation) === grant?.generation && integer(r.expected_revision) === String(grant?.revision));
      const superseded = !!native && !!link && (text(native.active_generation) !== grant?.generation || integer(link.link_revision) !== String(grant?.revision));
      if (!grant || (!superseded && !(retired && connection && text(connection.state) === 'relink_required'))) fail('partition_grant_result_unsettled');
    }
  }
  private validateReceipt(row: Row, domain: DomainFacts) {
    let receipt: Record<string, unknown>;
    try { receipt = JSON.parse(row.receipt!); } catch { return fail('partition_receipt_unknown'); }
    if (!receipt || typeof receipt !== 'object' || Array.isArray(receipt)
      || typeof receipt.result !== 'string' || receipt.result.length < 1 || receipt.result.length > 128) fail('partition_receipt_unknown');
    if (row.lease === null) {
      if (receipt.attempt !== null || Object.keys(receipt).sort().join() !== 'attempt,result') fail('partition_receipt_unknown'); return;
    }
    const binding = JSON.parse(row.attempt_binding!) as Record<string, unknown>;
    const resolution = domain.tables.attempt_resolutions.find(r => text(r.attempt_id) === row.attempt_id);
    const intent = domain.tables.submission_intents.find(r => text(r.intent_id) === binding.intentId);
    if (!resolution || receipt.attemptId !== row.attempt_id || receipt.intentId !== binding.intentId
      || receipt.leaseId !== binding.leaseId || receipt.generation !== binding.generation
      || receipt.outcome !== text(resolution.outcome) || receipt.intentState !== text(resolution.outcome)
      || receipt.pendingReservations !== 0) fail('partition_receipt_mismatch');
    if (!intent) fail('partition_receipt_mismatch');
    const code = integer(resolution!.flickr_code);
    if (code !== null && (BigInt(code) < BigInt(Number.MIN_SAFE_INTEGER) || BigInt(code) > BigInt(Number.MAX_SAFE_INTEGER))) fail('partition_receipt_code_inexact');
    const marked = Number(domain.tables.attempt_dispatches.some(r => text(r.attempt_id) === row.attempt_id));
    const blocked = domain.tables.submission_blocks.filter(r => text(r.photo_id) === text(intent!.photo_id) && text(r.group_id) === text(intent!.group_id)).length;
    const pendingReservations = domain.tables.flickr_rate_reservations.filter(r => text(r.attempt_id) === row.attempt_id && integer(r.released) === '0').length;
    let grant: Record<string, unknown> | null;
    try { grant = row.grant_binding ? JSON.parse(row.grant_binding) : null; } catch { return fail('partition_original_json'); }
    let grantRetired = 0, grantSuperseded = 0;
    if (grant !== null) {
      if (!grant || typeof grant.generation !== 'string' || !grant.generation.length || !gen(grant.revision)) fail('partition_original_json');
      const user = text(intent!.user_id), connection = domain.tables.flickr_connection_state.find(r => text(r.user_id) === user);
      const native = domain.tables.flickr_native_credentials.find(r => text(r.user_id) === user), link = domain.tables.flickr_links.find(r => text(r.user_id) === user);
      const operationId = connection ? text(connection.operation_id) : null;
      const operation = operationId === null ? undefined : domain.tables.flickr_lifecycle_operations.find(r => text(r.operation_id) === operationId);
      // Match the original finish SELECT, including SQL NULL join behavior.
      // Later ownership changes refuse instead of rewriting historical facts.
      grantRetired = Number(!!connection && !!native && !!link && !!operation && operationId !== null
        && text(connection.state) === 'relink_required' && text(link.state) === 'paused'
        && text(native.operation_id) === operationId && text(operation.kind) === 'retire'
        && text(operation.retiring_generation) === grant.generation && integer(operation.expected_revision) === grant.revision);
      grantSuperseded = Number(!!native && !!link && (text(native.active_generation) !== grant.generation || integer(link.link_revision) !== grant.revision));
    }
    const expected = { attemptId: row.attempt_id, intentId: binding.intentId, leaseId: binding.leaseId, generation: binding.generation,
      outcome: text(resolution!.outcome), reason: text(resolution!.reason), code: code === null ? null : Number(code),
      intentState: text(intent!.state), marked, blocked, pendingReservations, grantRetired, grantSuperseded };
    if (Object.keys(receipt).sort().join() !== [...Object.keys(expected), 'result'].sort().join()
      || Object.entries(expected).some(([key, value]) => receipt[key] !== value)
      || row.dispatch !== marked) fail('partition_receipt_mismatch');
  }
  retainedEvidence() { return this.evidenceRecord; }
}
