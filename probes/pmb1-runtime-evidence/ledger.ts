// MIT License; copyright 2026 Terry Ott.
import { canonical } from '../pmb1-no-real-object-reader/reader.ts';
import { EvidenceUnavailable, type EvidenceReference, type EvidenceBinding, type QualifiedEvidenceProvenance,
  type EvidenceReadAllocation, type EvidenceHeader, type RuntimeEvidencePacket, type TerminalOutcome,
  type EvidenceExecutionAnchors, type NativeExecutionSelector, type StableChannelQualification } from './types.ts';
export * from './types.ts';

const fail = (reason: string): never => { throw new EvidenceUnavailable(reason); };
const text = (v: unknown, n = 256): v is string => typeof v === 'string' && /^[\x20-\x7e]+$/.test(v) && v.length <= n;
const digest = (v: unknown): v is string => typeof v === 'string' && /^[a-f0-9]{64}$/.test(v);
const uuid = (v: unknown): v is string => typeof v === 'string' && /^[a-f0-9]{8}(-[a-f0-9]{4}){3}-[a-f0-9]{12}$/.test(v);
const positive = (v: unknown): v is number => Number.isSafeInteger(v) && Number(v) > 0;
export const encoded = (value: unknown): string => canonical(value).replace(/[\u007f-\uffff]/g,
  c => '\\u' + c.charCodeAt(0).toString(16).padStart(4, '0'));
export const same = (a: unknown, b: unknown): boolean => encoded(a) === encoded(b);
export async function sha2_256(value: string): Promise<string> {
  return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(value))),
    b => b.toString(16).padStart(2, '0')).join('');
}
function freeze<T>(value: T): T {
  if (value && typeof value === 'object') { for (const v of Object.values(value)) freeze(v); Object.freeze(value); }
  return value;
}
export function validateReference(v: EvidenceReference): void {
  if (!v || !uuid(v.databaseId) || !uuid(v.envelopeId) || !uuid(v.attemptId) || !text(v.operation, 80)) fail('evidence_reference');
}
export function executionAnchors(v: EvidenceExecutionAnchors | EvidenceBinding): EvidenceExecutionAnchors {
  const { lifecycle: _lifecycle, generation: _generation, ...anchors } = v as EvidenceBinding;
  return anchors;
}
function validateAnchors(v: EvidenceExecutionAnchors): void {
  if (!v || v.contract !== 'pmb1-runtime-evidence-v1' || !uuid(v.databaseId) || !text(v.profile, 80)
    || !text(v.boundary, 80) || !text(v.schema, 80)
    || !digest(v.sourceContext) || !digest(v.moduleDigest) || !digest(v.configurationDigest)
    || !digest(v.resourceInventoryDigest) || !digest(v.nativeSourceDigest) || !digest(v.ownerSourceDigest)
    || !text(v.immutableVersion, 128) || !text(v.controlReference)) fail('evidence_binding');
}
function validateBinding(v: EvidenceBinding): void {
  validateAnchors(v);
  if (!text(v.lifecycle,80) || !/^[1-9][0-9]{0,18}$/.test(v.generation) || BigInt(v.generation)>9223372036854775807n)
    fail('evidence_journal_binding');
}
function validateProvenance(v: QualifiedEvidenceProvenance, binding: EvidenceExecutionAnchors): void {
  if (!v || !same(executionAnchors(v.binding), executionAnchors(binding)) || !digest(v.publisherSourceDigest) || !digest(v.holderInventoryDigest)
    || !digest(v.writerInventoryDigest)
    || !digest(v.executionAttributionRecord) || !digest(v.historyContinuityRecord) || !digest(v.operatorAttemptLedgerRecord)) fail('evidence_provenance');
  if (!digest(v.provenancePathDigest) || !digest(v.holderPolicyDigest) || !digest(v.nativeGetterQualificationRecord)) fail('evidence_provenance_path');
}
export function validateAllocation(v: EvidenceReadAllocation): void {
  const fields = ['maxPayloadBytes','maxAcquiredBytes','maxDecodedBytes','maxNativeBytes','maxAggregateBytes',
    'maxRequests','maxStatements','maxTotalRequests','maxTotalStatements'];
  if (!v || typeof v !== 'object' || Object.getPrototypeOf(v) !== Object.prototype) fail('evidence_allocation');
  const keys = Reflect.ownKeys(v);
  if (keys.length !== fields.length || fields.some(field => {
    const descriptor = Object.getOwnPropertyDescriptor(v, field);
    return !descriptor || !descriptor.enumerable || !('value' in descriptor) || !positive(descriptor.value);
  }) || keys.some(key => typeof key !== 'string' || !fields.includes(key as string))) fail('evidence_allocation');
  if (v.maxPayloadBytes > 4194304
    || v.maxAcquiredBytes > 33554432 || v.maxDecodedBytes > 16777216 || v.maxNativeBytes > 16777216
    || v.maxAggregateBytes > 67108864
    || v.maxRequests > 8 || v.maxRequests < 8 || v.maxStatements > 32 || v.maxStatements < 8
    || v.maxTotalRequests > 68 || v.maxTotalStatements > 136) fail('evidence_allocation');
}
/** Conservative protocol charge: escaped D1 serialization, two retained text
 * copies, decoded source representation and separately allocated native facts.
 * This is a finite transport/materialization charge, not a JS heap-size proof.
 */
export function requiredCharge(payloadBytes: number, captures: number, nativeBytes: number): {
  acquired: number; decoded: number; aggregate: number; requests: number; statements: number;
} {
  const acquired = payloadBytes * 6 + 65536, decoded = payloadBytes * 4;
  return { acquired, decoded, aggregate: (acquired + decoded) * (captures + 1) + (captures===0?0:nativeBytes),
    requests: captures===0?5:4 + captures * 4, statements: 8 + captures * 8 };
}
export function validateHeader(header: EvidenceHeader, binding: EvidenceExecutionAnchors,
  provenance: QualifiedEvidenceProvenance, allocation: EvidenceReadAllocation, now: number): void {
  validateAnchors(binding); validateProvenance(provenance, binding); validateAllocation(allocation);
  if (!header) fail('evidence_header');
  validateAllocation(header.allocation);
  validateBinding(header.binding);
  validateReference(header.reference);
  const review = header.provenance;
  if (!review) fail('evidence_review');
  const { rootRecord, reviewRecord, reviewer, author, fromMs, throughMs, ...anchors } = review;
  validateProvenance(anchors, binding);
  if (!digest(rootRecord) || !digest(reviewRecord) || !text(reviewer, 128) || !text(author, 128)
    || reviewer === author || !Number.isSafeInteger(fromMs) || !Number.isSafeInteger(throughMs)
    || fromMs < 0 || throughMs <= fromMs || throughMs - fromMs > 600000) fail('evidence_review');
  if (!same(executionAnchors(header.binding), executionAnchors(binding)) || !same(anchors, provenance) || !same(header.allocation, allocation)
    || header.reference.databaseId !== binding.databaseId || !Number.isSafeInteger(header.fromMs)
    || !Number.isSafeInteger(header.throughMs) || header.fromMs < fromMs || header.throughMs > throughMs
    || header.fromMs > now || now >= header.throughMs || header.throughMs <= header.fromMs
    || header.throughMs - header.fromMs > 600000 || !digest(header.payloadDigest)
    || !positive(header.payloadBytes) || header.payloadBytes > allocation.maxPayloadBytes
    || !positive(header.chunkCount) || header.chunkCount > 16 || header.chunkCount !== Math.ceil(header.payloadBytes / 262144)
    || !['raw-capture','evidence-use'].includes(header.mode)
    || !Array.isArray(header.captureKeys) || header.captureKeys.length > 16
    || (header.mode==='raw-capture' ? header.captureKeys.length<1 : header.captureKeys.length!==0
      || !['main-assess','partition-reconcile'].includes(header.reference.operation))
    || header.captureKeys.some(k => !text(k)) || new Set(header.captureKeys).size !== header.captureKeys.length
    || !Array.isArray(header.captureAttempts) || header.captureAttempts.length !== header.captureKeys.length
    || header.captureAttempts.some((c, i) => !c || c.captureKey !== header.captureKeys[i] || !uuid(c.attemptId)
      || c.attemptId === header.reference.attemptId)
    || new Set(header.captureAttempts.map(c => c.attemptId)).size !== header.captureAttempts.length
    || encoded(header).length > 16384 || encoded(binding).length > 4096) fail('evidence_header');
  const charge = requiredCharge(header.payloadBytes, header.captureKeys.length, allocation.maxNativeBytes);
  // Shared source reservation/final checks count against EVERY raw attempt:
  // source6 + owner6 + terminal1 + final1 =14 actual statements, reserve15.
  // The distinct evidence-only operation reserves its actual8. A larger total
  // population allocation cannot lend statements to an underallocated attempt.
  const perAttemptStatements=header.mode==='raw-capture'?15:8;
  if (allocation.maxStatements<perAttemptStatements
    || charge.acquired > allocation.maxAcquiredBytes || charge.decoded > allocation.maxDecodedBytes
    || charge.aggregate > allocation.maxAggregateBytes || charge.requests > allocation.maxTotalRequests
    || charge.statements > allocation.maxTotalStatements) fail('evidence_preacquisition_budget');
}

const CURRENT = `EXISTS(SELECT 1 FROM pmb1_journal_control j WHERE j.id=1 AND j.schema_version='pmb1-main-journal-v1'
  AND j.database_id=json_extract(e.binding_json,'$.databaseId') AND j.candidate=json_extract(e.binding_json,'$.sourceContext')
  AND j.lifecycle=json_extract(e.binding_json,'$.lifecycle') AND j.generation=json_extract(e.binding_json,'$.generation')
  AND j.state='stopped' AND j.stop_evidence IS NOT NULL)`;
const MATCH = `e.envelope_id=? AND json_remove(e.binding_json,'$.lifecycle','$.generation')=? AND ${CURRENT}`;
const NATIVE_MATCH = `e.envelope_id=? AND json_extract(e.binding_json,'$.databaseId')=?
  AND json_extract(e.binding_json,'$.sourceContext')=? AND json_extract(e.binding_json,'$.immutableVersion')=?
  AND json_extract(e.binding_json,'$.schema')=? AND ${CURRENT}`;
const ACTIVE = `EXISTS(SELECT 1 FROM pmb1_evidence_events v WHERE v.envelope_id=e.envelope_id AND v.kind='publish')
  AND NOT EXISTS(SELECT 1 FROM pmb1_evidence_events v WHERE v.envelope_id=e.envelope_id AND v.kind='retire')`;
export const EVIDENCE_SQL = Object.freeze({
  preflight: `SELECT e.header_json,e.payload_bytes,e.chunk_count,COUNT(c.ordinal) AS actual_chunks,
    COALESCE(SUM(length(CAST(c.payload AS BLOB))),0) AS actual_bytes,
    COALESCE((SELECT MAX(revision) FROM pmb1_evidence_events v WHERE v.envelope_id=e.envelope_id),0) AS revision
    FROM pmb1_evidence_envelopes e LEFT JOIN pmb1_evidence_chunks c ON c.envelope_id=e.envelope_id
    WHERE ${MATCH} AND ${ACTIVE} GROUP BY e.envelope_id LIMIT 1`,
  select: `SELECT e.header_json,e.payload_bytes,e.chunk_count,COUNT(c.ordinal) AS actual_chunks,
    COALESCE(SUM(length(CAST(c.payload AS BLOB))),0) AS actual_bytes,
    COALESCE((SELECT MAX(revision) FROM pmb1_evidence_events v WHERE v.envelope_id=e.envelope_id),0) AS revision
    FROM pmb1_evidence_envelopes e LEFT JOIN pmb1_evidence_chunks c ON c.envelope_id=e.envelope_id
    WHERE json_remove(e.binding_json,'$.lifecycle','$.generation')=? AND ${CURRENT}
      AND json_extract(e.header_json,'$.reference.operation')=? AND ${ACTIVE}
    GROUP BY e.envelope_id LIMIT 2`,
  header: `SELECT e.header_json FROM pmb1_evidence_envelopes e WHERE ${MATCH} AND ${ACTIVE} LIMIT 1`,
  chunks: `SELECT c.ordinal,c.payload FROM pmb1_evidence_chunks c JOIN pmb1_evidence_envelopes e USING(envelope_id)
    WHERE ${MATCH} AND ${ACTIVE} AND e.payload_bytes<=? AND e.chunk_count<=? ORDER BY c.ordinal LIMIT 16`,
  events: `SELECT v.revision,v.kind,v.capture_key,v.attempt_id,v.outcome,v.observed_ms FROM pmb1_evidence_events v
    JOIN pmb1_evidence_envelopes e USING(envelope_id) WHERE ${MATCH} ORDER BY v.revision LIMIT 35`,
  append: `INSERT INTO pmb1_evidence_events(envelope_id,revision,kind,capture_key,attempt_id,outcome,observed_ms)
    SELECT e.envelope_id,?+1,?,?,?,?,? FROM pmb1_evidence_envelopes e WHERE ${MATCH} AND ${ACTIVE}
      AND ?=(SELECT MAX(revision) FROM pmb1_evidence_events v WHERE v.envelope_id=e.envelope_id)
    RETURNING revision,kind,capture_key,attempt_id,outcome,observed_ms`,
  terminal: `INSERT INTO pmb1_evidence_events(envelope_id,revision,kind,capture_key,attempt_id,outcome,observed_ms)
    SELECT e.envelope_id,1+(SELECT MAX(revision) FROM pmb1_evidence_events v WHERE v.envelope_id=e.envelope_id),
      'terminal',?,?,?,? FROM pmb1_evidence_envelopes e WHERE ${MATCH}
    RETURNING revision,kind,capture_key,attempt_id,outcome,observed_ms`,
});
const NATIVE_SQL = Object.freeze(Object.fromEntries(Object.entries(EVIDENCE_SQL).map(([key, sql]) => [key,
  key === 'select' ? sql.replace("json_remove(e.binding_json,'$.lifecycle','$.generation')=?",
    "json_extract(e.binding_json,'$.databaseId')=? AND json_extract(e.binding_json,'$.sourceContext')=? AND json_extract(e.binding_json,'$.immutableVersion')=? AND json_extract(e.binding_json,'$.schema')=?")
    : sql.replace(MATCH, NATIVE_MATCH)]))) as unknown as typeof EVIDENCE_SQL;

type Row = Record<string, unknown>;
type Event = { revision: number; kind: string; capture_key: string; attempt_id: string; outcome: string; observed_ms: number };
/** Fixed bounded reader/use ledger. NO schema, publisher, approval, renewal,
 * arbitrary SQL or credential method. Every request starts a fresh primary
 * session. A rejected/lost/malformed mutation ACK is UNKNOWN and never retried.
 */
export class RuntimeEvidenceLedger {
  readonly #db: D1Database; readonly #binding?: EvidenceExecutionAnchors; readonly #provenance?: QualifiedEvidenceProvenance;
  readonly #selector?: NativeExecutionSelector; readonly #qualification?: StableChannelQualification;
  readonly #allocation: EvidenceReadAllocation; readonly #now: () => number;
  #selectedAllocation?: EvidenceReadAllocation;
  readonly #attemptCharges = new Map<string,{requests:number;statements:number}>();
  #ownerCaptureKey = '';
  readonly #packets = new WeakSet<object>(); readonly #spent = new Set<string>();
  readonly #reservedPackets = new WeakSet<object>(); readonly #pendingMutation = new Set<string>();
  #role: 'source' | 'owner' | undefined;
  #finalStarted = false;
  readonly #terminalOutcomes = new Map<string, TerminalOutcome>();
  #requests = 0; #statements = 0; #previousTime = -1;
  constructor(db: D1Database, expected: EvidenceExecutionAnchors | NativeExecutionSelector,
    provenance: QualifiedEvidenceProvenance | StableChannelQualification,
    allocation: EvidenceReadAllocation, now = Date.now) {
    validateAllocation(allocation);
    if ('contract' in expected) {
      validateAnchors(expected); validateProvenance(provenance as QualifiedEvidenceProvenance, expected);
      this.#binding = freeze(structuredClone(executionAnchors(expected)));
      this.#provenance = freeze(structuredClone(provenance as QualifiedEvidenceProvenance));
    } else {
      const q = provenance as StableChannelQualification;
      if (!expected || !uuid(expected.databaseId) || !digest(expected.sourceContext) || !text(expected.immutableVersion,128)
        || !q || q.databaseId !== expected.databaseId || !text(q.schema,80)
        || !digest(q.publisherSourceDigest) || !digest(q.provenancePathDigest) || !digest(q.holderPolicyDigest)
        || !digest(q.nativeGetterQualificationRecord)) fail('evidence_native_qualification');
      this.#selector = freeze(structuredClone(expected)); this.#qualification = freeze(structuredClone(q));
    }
    if (!db || typeof db.withSession !== 'function') fail('evidence_database');
    this.#db = db;
    this.#allocation = freeze(structuredClone(allocation)); this.#now = now; this.time();
  }
  static fromNativeExecution(db: D1Database, selector: NativeExecutionSelector, qualification: StableChannelQualification,
    protocolCeilings: EvidenceReadAllocation, now = Date.now): RuntimeEvidenceLedger {
    return new RuntimeEvidenceLedger(db, selector, qualification, protocolCeilings, now);
  }
  private sql(key: keyof typeof EVIDENCE_SQL): string { return (this.#selector ? NATIVE_SQL : EVIDENCE_SQL)[key]; }
  private validate(header: EvidenceHeader): void {
    if (!this.#selector) {
      validateHeader(header, this.#binding!, this.#provenance!, this.#allocation, this.time()); return;
    }
    const observed = this.#selector, q = this.#qualification!;
    if (!header?.provenance || !header.binding || !header.allocation) fail('evidence_header');
    const { rootRecord: _root, reviewRecord: _review, reviewer: _reviewer, author: _author,
      fromMs: _from, throughMs: _through, ...authenticatedAnchors } = header.provenance;
    // The prequalified protected publisher supplies the EXPECTED full immutable
    // version -> retained module/configuration/resource mapping. Only independently
    // observed native version/context select it; a row cannot vouch for that getter.
    validateHeader(header, header.binding, authenticatedAnchors, header.allocation, this.time());
    if (header.binding.databaseId !== observed.databaseId || header.binding.sourceContext !== observed.sourceContext
      || header.binding.immutableVersion !== observed.immutableVersion || header.binding.schema !== q.schema
      || header.binding.profile !== 'pmb1-private-application-no-real-v1'
      || header.binding.boundary !== 'pmb1-private-object-kv-interface-v1'
      || header.provenance.publisherSourceDigest !== q.publisherSourceDigest
      || header.provenance.provenancePathDigest !== q.provenancePathDigest
      || header.provenance.holderPolicyDigest !== q.holderPolicyDigest
      || header.provenance.nativeGetterQualificationRecord !== q.nativeGetterQualificationRecord
      || Object.entries(header.allocation).some(([key, value]) => value > this.#allocation[key as keyof EvidenceReadAllocation]))
      fail('evidence_native_selector_or_provenance');
  }
  private time(): number {
    const now = this.#now();
    if (!Number.isSafeInteger(now) || now < 0 || now < this.#previousTime) fail('evidence_clock_or_expiry');
    this.#previousTime = now; return now;
  }
  private reference(ref: EvidenceReference): void {
    validateReference(ref); if (ref.databaseId !== (this.#selector?.databaseId ?? this.#binding!.databaseId)) fail('evidence_database_binding');
  }
  private selectorArgs(): string[] {
    return this.#selector ? [this.#selector.databaseId,this.#selector.sourceContext,this.#selector.immutableVersion,this.#qualification!.schema]
      : [encoded(this.#binding)];
  }
  private args(ref: EvidenceReference): string[] { return [ref.envelopeId, ...this.selectorArgs()]; }
  private rows(result: D1Result): Row[] {
    if (!result || result.success !== true || !Array.isArray(result.results)
      || result.results.some(row => !row || typeof row !== 'object' || Array.isArray(row))) fail('evidence_ack_unknown');
    return (result.results as Row[]).map(row => ({ ...row }));
  }
  private async batch(queries: readonly { sql: string; args: (number | string)[] }[], captureScope?:string): Promise<Row[][]> {
    this.time();
    const allocated = this.#selectedAllocation ?? this.#allocation;
    // Source and owner run in separate isolates. Charge the fixed OTHER role's
    // complete cost conservatively in each local exact-attempt counter, then
    // charge every actual shared/key-specific request here. The envelope total
    // cannot lend capacity to any individually underallocated raw attempt.
    const charges = captureScope===undefined ? [...this.#attemptCharges.values()]
      : [this.#attemptCharges.get(captureScope) ?? fail('evidence_attempt_scope')];
    for(const charge of charges){
      if(charge.requests+1>allocated.maxRequests||charge.statements+queries.length>allocated.maxStatements)
        fail('evidence_per_attempt_budget');
    }
    for(const charge of charges){charge.requests++;charge.statements+=queries.length;}
    if (++this.#requests > allocated.maxTotalRequests
      || (this.#statements += queries.length) > allocated.maxTotalStatements) fail('evidence_request_budget');
    const session = this.#db.withSession('first-primary');
    let results: D1Result[];
    try { results = await session.batch(queries.map(q => session.prepare(q.sql).bind(...q.args))); }
    catch { fail('evidence_ack_unknown'); }
    this.time();
    if (!Array.isArray(results!) || results!.length !== queries.length) fail('evidence_ack_unknown');
    return results!.map(result => this.rows(result));
  }
  private decodeHeader(raw: unknown, ref: EvidenceReference): EvidenceHeader {
    if (typeof raw !== 'string' || raw.length > 16384 || !/^[\x20-\x7e]+$/.test(raw)) fail('evidence_header_size');
    let header: EvidenceHeader; try { header = JSON.parse(raw as string) as EvidenceHeader; } catch { fail('evidence_header_json'); }
    this.validate(header!);
    if (encoded(header!) !== raw || !same(header!.reference, ref)) fail('evidence_reference_binding');
    return header!;
  }
  private events(rows: Row[], header: EvidenceHeader, retired = false): Event[] {
    if (rows.length < 1 || rows.length > (header.mode==='evidence-use'?4:3 + 2 * header.captureKeys.length)) fail('evidence_history');
    const kinds = new Set<string>(), consumed = new Set<string>(); let reserved = false;
    rows.forEach((row, index) => {
      const event = row as unknown as Event;
      const capture = header.captureAttempts.find(c => c.captureKey === event.capture_key);
      const native = event.kind === 'native-consumed' || (event.kind === 'terminal' && header.mode==='raw-capture');
      const key = event.kind + '/' + event.capture_key;
      if (event.revision !== index + 1 || !['publish','use-reserved','native-consumed','terminal','retire'].includes(event.kind)
        || kinds.has(key) || !Number.isSafeInteger(event.observed_ms) || event.observed_ms < 0
        || (native ? !capture || event.attempt_id !== capture.attemptId : event.capture_key !== '' || event.attempt_id !== header.reference.attemptId)
        || (event.kind === 'terminal' ? !['complete','refused','unknown'].includes(event.outcome) : event.outcome !== '')
        || (index === 0 ? event.kind !== 'publish' : event.kind === 'publish')
        || (event.kind === 'native-consumed' && !reserved)
        || (event.kind === 'native-consumed' && header.mode!=='raw-capture')
        || (event.kind === 'terminal' && (header.mode==='raw-capture'?!consumed.has(event.capture_key):!reserved))
        || (event.kind === 'retire' && !retired)) fail('evidence_history');
      kinds.add(key); if (event.kind === 'use-reserved') reserved = true;
      if (event.kind === 'native-consumed') consumed.add(event.capture_key);
    });
    return rows as unknown as Event[];
  }
  private async preflight(ref: EvidenceReference | string): Promise<{ header: EvidenceHeader; revision: number }> {
    if (typeof ref !== 'string') this.reference(ref); else if (!text(ref, 80)) fail('evidence_operation');
    const [rows] = await this.batch([typeof ref === 'string'
      ? { sql: this.sql('select'), args: [...this.selectorArgs(), ref] }
      : { sql: this.sql('preflight'), args: this.args(ref) }]);
    if (rows.length !== 1) fail('evidence_missing_or_retired');
    const row = rows[0]!;
    let selected = ref;
    if (typeof ref === 'string') {
      if (typeof row.header_json !== 'string' || row.header_json.length > 16384) fail('evidence_header_size');
      try { selected = (JSON.parse(row.header_json as string) as EvidenceHeader).reference; } catch { fail('evidence_header_json'); }
      this.reference(selected as EvidenceReference);
      if ((selected as EvidenceReference).operation !== ref) fail('evidence_operation');
    }
    const header = this.decodeHeader(row.header_json, selected as EvidenceReference);
    if (this.#selectedAllocation && !same(this.#selectedAllocation,header.allocation)) fail('evidence_allocation_changed');
    this.#selectedAllocation = header.allocation;
    if(this.#attemptCharges.size===0){
      // Preflight was one bounded request/statement before the protected header
      // was available. Account it now, BEFORE any complete payload acquisition.
      if(header.mode==='evidence-use') this.#attemptCharges.set('',{requests:1,statements:1});
      else if(this.#role==='source') for(const key of header.captureKeys)
        this.#attemptCharges.set(key,{requests:4,statements:7}); // held owner3/6 + preflight1/1
      else {
        if(!header.captureKeys.includes(this.#ownerCaptureKey))fail('evidence_attempt_scope');
        this.#attemptCharges.set(this.#ownerCaptureKey,{requests:6,statements:9}); // held source/terminal/final5/8 + preflight1/1
      }
      if([...this.#attemptCharges.values()].some(c=>c.requests>header.allocation.maxRequests
        ||c.statements>header.allocation.maxStatements))fail('evidence_per_attempt_budget');
    }
    if (row.payload_bytes !== header.payloadBytes || row.actual_bytes !== header.payloadBytes
      || row.chunk_count !== header.chunkCount || row.actual_chunks !== header.chunkCount
      || !positive(row.revision) || Number(row.revision) > 35) fail('evidence_incomplete');
    return { header, revision: Number(row.revision) };
  }
  private async load(selection: EvidenceReference | string, kind: 'use-reserved' | 'native-consumed', captureKey = ''): Promise<RuntimeEvidencePacket> {
    selection = structuredClone(selection);
    // One complete source materialization OR one exact owner materialization per
    // instance. Set synchronously before the first await; concurrent calls,
    // alternate envelopes/keys and failed acquisitions cannot borrow another role.
    if (this.#role) fail('evidence_role_already_spent');
    this.#role = kind === 'use-reserved' ? 'source' : 'owner';
    this.#ownerCaptureKey=captureKey;
    const phase = kind + '/' + (typeof selection === 'string' ? selection : selection.envelopeId) + '/' + captureKey;
    if (kind && this.#pendingMutation.size) fail('evidence_unknown_or_concurrent_mutation');
    if (this.#spent.has(phase)) fail('evidence_no_replay'); this.#spent.add(phase);
    const before = await this.preflight(selection), ref = before.header.reference,
      queries: { sql: string; args: (string | number)[] }[] = [];
    if (kind) {
      const capture = before.header.captureAttempts.find(c => c.captureKey === captureKey);
      if (kind === 'native-consumed' && (before.header.mode!=='raw-capture'||!capture)) fail('evidence_capture_binding');
      queries.push({ sql: this.sql('append'), args: [before.revision, kind, captureKey,
        capture?.attemptId ?? ref.attemptId, '', this.time(), ...this.args(ref), before.revision] });
      this.#pendingMutation.add(phase);
    }
    queries.push({ sql: this.sql('header'), args: this.args(ref) },
      { sql: this.sql('chunks'), args: [...this.args(ref), before.header.payloadBytes, before.header.chunkCount] },
      { sql: this.sql('events'), args: this.args(ref) });
    const result = await this.batch(queries);
    if (kind) {
      const mutation = result.shift()!;
      if (mutation.length !== 1 || mutation[0]!.revision !== before.revision + 1) fail('evidence_claim_unknown');
    }
    if (result[0]!.length !== 1 || result[0]![0]!.header_json !== encoded(before.header)) fail('evidence_header_changed');
    const chunks = result[1]!;
    if (chunks.length !== before.header.chunkCount) fail('evidence_chunks');
    let payload = '';
    for (let i = 0; i < chunks.length; ++i) {
      const row = chunks[i]!, part = row.payload;
      if (row.ordinal !== i || typeof part !== 'string' || part.length < 1 || part.length > 262144
        || !/^[\x20-\x7e]+$/.test(part) || (i < chunks.length - 1 && part.length !== 262144)) fail('evidence_chunks');
      payload += part;
    }
    const events = this.events(result[2]!, before.header), revision = events.length;
    if (payload.length !== before.header.payloadBytes || await sha2_256(payload) !== before.header.payloadDigest) fail('evidence_payload_digest');
    this.time();
    let decoded: unknown; try { decoded = JSON.parse(payload); } catch { fail('evidence_payload_json'); }
    if (encoded(decoded) !== payload) fail('evidence_payload_noncanonical');
    const [finalRows] = await this.batch([{ sql: this.sql('events'), args: this.args(ref) }]);
    const final = this.events(finalRows!, before.header);
    if (!same(final, events)) fail('evidence_revision_changed');
    this.validate(before.header);
    const packet = freeze({ reference: ref, header: before.header, payload: decoded, revision });
    this.#packets.add(packet);
    if (kind) { this.#terminalHeaders.set(ref.envelopeId, packet); this.#pendingMutation.delete(phase); }
    if (kind === 'use-reserved') this.#reservedPackets.add(packet);
    return packet;
  }
  /** Full payload reconciliation has no separate accepted finite allocation in
   * this source revision. Refuse before I/O, including after restart. Exact
   * operator status/readback plans remain separately allocated and disabled. */
  async read(_ref: EvidenceReference): Promise<never> { return fail('evidence_standalone_read_not_allocated'); }
  reserve(ref: EvidenceReference): Promise<RuntimeEvidencePacket> { return this.load(ref, 'use-reserved'); }
  reserveSelected(operation: string): Promise<RuntimeEvidencePacket> { return this.load(operation, 'use-reserved'); }
  consume(ref: EvidenceReference, captureKey: string): Promise<RuntimeEvidencePacket> {
    if (!text(captureKey)) fail('evidence_capture_binding'); return this.load(ref, 'native-consumed', captureKey);
  }
  async complete(ref: EvidenceReference, captureKey: string, outcome: TerminalOutcome): Promise<void> {
    if (this.#role !== 'source' || this.#finalStarted) fail('evidence_source_role_required');
    this.reference(ref); if (!text(captureKey) || !['complete','refused','unknown'].includes(outcome)) fail('evidence_terminal');
    const phase = 'terminal/' + ref.envelopeId + '/' + captureKey;
    if (this.#pendingMutation.size) fail('evidence_unknown_or_concurrent_mutation');
    if (this.#spent.has(phase)) fail('evidence_no_replay'); this.#spent.add(phase);
    // A terminal cannot manufacture first use. Require this source instance's
    // exact successful reservation/header; SQL requires the owning native
    // adapter's separately committed exact-key consumption in the same ledger.
    const packet = this.#terminalHeaders.get(ref.envelopeId);
    if (!packet || !same(packet.reference, ref)) fail('evidence_unconsumed');
    const capture = packet!.header.captureAttempts.find(c => c.captureKey === captureKey);
    if (!capture) fail('evidence_capture_binding');
    if (outcome === 'complete') this.validate(packet!.header);
    this.#pendingMutation.add(phase);
    const [rows] = await this.batch([{ sql: this.sql('terminal'),
      args: [captureKey, capture!.attemptId, outcome, this.time(), ...this.args(ref)] }],captureKey);
    if (rows!.length !== 1 || rows![0]!.kind !== 'terminal' || rows![0]!.capture_key !== captureKey
      || rows![0]!.attempt_id !== capture!.attemptId || rows![0]!.outcome !== outcome) fail('evidence_terminal_unknown');
    if (outcome === 'complete') this.validate(packet!.header);
    this.#pendingMutation.delete(phase);
    this.#terminalOutcomes.set(captureKey,outcome);
  }
  readonly #terminalHeaders = new Map<string, RuntimeEvidencePacket>();
  async revalidate(packet: RuntimeEvidencePacket): Promise<void> {
    if (this.#role !== 'source' || this.#finalStarted || !packet || !this.#packets.has(packet) || !this.#reservedPackets.has(packet)
      || packet.header.mode!=='raw-capture' || this.#pendingMutation.size) fail('evidence_packet_not_reserved_or_unknown');
    this.#finalStarted = true;
    if (packet.header.captureKeys.some(key => this.#terminalOutcomes.get(key) !== 'complete')) fail('evidence_incomplete_terminal');
    this.validate(packet.header);
    const [rows] = await this.batch([{ sql: this.sql('events'), args: this.args(packet.reference) }]);
    const events = this.events(rows!, packet.header);
    if (events.length < packet.revision || !events.some(e => e.kind === 'use-reserved')
      || packet.header.captureKeys.some(key => !events.some(e => e.kind === 'terminal' && e.capture_key === key && e.outcome === 'complete')))
      fail('evidence_incomplete_terminal');
    this.validate(packet.header);
  }
  /** Separate explicitly published non-acquisition attempt. No native-consumed
   * event or raw capture allocation is borrowed. Append its own generic terminal
   * and validate current primary history/time/source AFTER the protected await. */
  async finishEvidenceUse(packet: RuntimeEvidencePacket): Promise<void> {
    if (this.#role!=='source'||this.#finalStarted||!packet||!this.#packets.has(packet)
      ||!this.#reservedPackets.has(packet)||packet.header.mode!=='evidence-use'||this.#pendingMutation.size)
      fail('evidence_use_not_reserved_or_unknown');
    this.#finalStarted=true;this.validate(packet.header);
    const phase='evidence-use-terminal/'+packet.reference.envelopeId;
    this.#pendingMutation.add(phase);
    const observedMs=this.time();
    const [terminal]=await this.batch([{sql:this.sql('terminal'),
      args:['',packet.reference.attemptId,'complete',observedMs,...this.args(packet.reference)]}]);
    if(terminal!.length!==1||terminal![0]!.kind!=='terminal'||terminal![0]!.capture_key!==''
      ||terminal![0]!.attempt_id!==packet.reference.attemptId||terminal![0]!.outcome!=='complete'
      ||terminal![0]!.revision!==packet.revision+1||terminal![0]!.observed_ms!==observedMs) fail('evidence_use_terminal_unknown');
    this.validate(packet.header);
    const [rows]=await this.batch([{sql:this.sql('events'),args:this.args(packet.reference)}]);
    const events=this.events(rows!,packet.header);
    if(events.length!==3||events[1]!.kind!=='use-reserved'||events[2]!.kind!=='terminal'
      ||events[2]!.capture_key!==''||events[2]!.outcome!=='complete') fail('evidence_use_terminal_unknown');
    this.validate(packet.header);this.#pendingMutation.delete(phase);
  }
}
