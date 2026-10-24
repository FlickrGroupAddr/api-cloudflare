// MIT License; copyright 2026 Terry Ott.
// OPERATOR ONLY. Never import from an FGA Worker, route, schedule or native owner.
import { encoded, same, sha2_256, validateHeader } from './ledger.ts';
import { EvidenceUnavailable, type EvidenceHeader, type EvidencePublicationReview } from './types.ts';
import { preparePublication, publicationReadback, type PreparedPublication, type FixedStatement } from './publication-plan.ts';

export interface OperatorPublicationAuthority {
  schema: 'pmb1-qualified-native-d1-operator-publication-v1';
  databaseId: string; envelopeId: string; operationId: string;
  /** Exact independent semantic handoff, source/holder/custody/environment records.
   * This is trusted OPERATOR SOURCE input after the actual work; labels/digests
   * do not establish that meaning. No JSON/request/environment loader exists. */
  qualificationRecord: string; operatorEnvironmentRecord: string; bindingHolderRecord: string;
  credentialCustodyRecord: string; publisherSourceDigest: string;
  rootRecord: string; reviewRecord: string; retainedEnvelopeDigest: string;
  attemptLedgerRecord: string; attemptState: 'allocated-unused';
  fromMs: number; throughMs: number;
  allocation: { maxRequests: number; maxStatements: number; maxAcquiredBytes: number; maxAggregateBytes: number };
}
export interface OperatorPublicationResult {
  outcome: 'published' | 'unknown'; publicationAcknowledged: boolean;
  readback: 'exact' | 'unknown'; envelopeId: string;
}
const digest = (v: unknown): v is string => typeof v === 'string' && /^[a-f0-9]{64}$/.test(v);
const uuid = (v: unknown): v is string => typeof v === 'string' && /^[a-f0-9]{8}(-[a-f0-9]{4}){3}-[a-f0-9]{12}$/.test(v);
const fail = (why: string): never => { throw new EvidenceUnavailable(why); };
const spent = new WeakMap<object, Set<string>>();
const spentAuthorities = new WeakSet<object>();
function allocation(v: OperatorPublicationAuthority['allocation']): void {
  const keys = ['maxRequests','maxStatements','maxAcquiredBytes','maxAggregateBytes'];
  if (!v || Object.getPrototypeOf(v) !== Object.prototype || Reflect.ownKeys(v).length !== keys.length
    || keys.some(key => { const d=Object.getOwnPropertyDescriptor(v,key);
      return !d || !d.enumerable || !('value' in d) || !Number.isSafeInteger(d.value) || d.value<=0; })) fail('operator_allocation');
  if (v.maxRequests!==4 || v.maxStatements>23 || v.maxStatements<8 || v.maxAcquiredBytes>33554432
    || v.maxAggregateBytes>67108864) fail('operator_allocation');
}
function checkAuthority(v: OperatorPublicationAuthority, header: EvidenceHeader, now: number): void {
  if (!v || v.schema!=='pmb1-qualified-native-d1-operator-publication-v1' || !uuid(v.databaseId)
    || v.databaseId!==header.reference.databaseId || v.envelopeId!==header.reference.envelopeId || !uuid(v.operationId)
    || v.attemptState!=='allocated-unused' || !digest(v.qualificationRecord) || !digest(v.operatorEnvironmentRecord)
    || !digest(v.bindingHolderRecord) || !digest(v.credentialCustodyRecord) || !digest(v.attemptLedgerRecord)
    || v.attemptLedgerRecord!==header.provenance.operatorAttemptLedgerRecord
    || v.publisherSourceDigest!==header.provenance.publisherSourceDigest || !digest(v.publisherSourceDigest)
    || v.rootRecord!==header.provenance.rootRecord || v.reviewRecord!==header.provenance.reviewRecord
    || !digest(v.retainedEnvelopeDigest) || !Number.isSafeInteger(v.fromMs) || !Number.isSafeInteger(v.throughMs)
    || v.fromMs<0 || v.throughMs<=v.fromMs || v.throughMs-v.fromMs>600000
    || now<v.fromMs || now>=v.throughMs || now<header.fromMs || now>=header.throughMs) fail('operator_qualification_or_custody');
  allocation(v.allocation);
}
function anchors(provenance: EvidencePublicationReview) {
  const {rootRecord:_root,reviewRecord:_review,author:_author,reviewer:_reviewer,fromMs:_from,throughMs:_through,...rest}=provenance;
  return rest;
}
type Row=Record<string,unknown>;

/** Concrete native-D1 SDK execution, not an invented REST transaction transport.
 * The caller must be a separately qualified private operator environment already
 * holding the exact selected native D1 binding. This library selects/deploys no
 * such environment, resource or topology. Its absent authority defaults to NO-GO.
 * Genuine Root/non-author semantic authentication and durable external attempt
 * custody precede this call; a forged object/label cannot perform that work.
 */
export async function publishReviewedEvidence(db: D1Database, prepared: PreparedPublication,
  authority?: OperatorPublicationAuthority, now = Date.now): Promise<OperatorPublicationResult> {
  if (!authority) return fail('operator_publication_execution_disabled');
  if (!db || typeof db.withSession!=='function' || !prepared?.header) return fail('operator_native_binding_required');
  // Check original source objects before cloning; no accessor/missing-allocation
  // bypass. Retained caller SQL is never used for execution.
  checkAuthority(authority,prepared.header,now());
  validateHeader(prepared.header,prepared.header.binding,anchors(prepared.header.provenance),prepared.header.allocation,now());
  const grant=structuredClone(authority), header=structuredClone(prepared.header);
  const operation=grant.operationId+'/'+grant.envelopeId;
  const prior=spent.get(db)??new Set<string>();
  if (spentAuthorities.has(authority) || prior.has(operation) || prior.has('envelope/'+grant.envelopeId))
    return fail('operator_publication_no_replay');
  spentAuthorities.add(authority);prior.add(operation);prior.add('envelope/'+grant.envelopeId);spent.set(db,prior);
  let previous=-1,requests=0,statements=0;
  const time=()=>{const n=now();if(!Number.isSafeInteger(n)||n<previous)fail('operator_clock');
    previous=n;checkAuthority(grant,header,n);return n;};
  const fixed=await preparePublication({header,payloadText:prepared.payloadText,retainedEnvelopeDigest:grant.retainedEnvelopeDigest,
    retainedRootRecord:grant.rootRecord,retainedReviewRecord:grant.reviewRecord},header.binding,
    anchors(header.provenance),header.allocation,time());
  time();
  const readPlan=publicationReadback(fixed),readBound=header.payloadBytes*6+65536;
  const publicationBytes=encoded(fixed.statements).length;
  if (fixed.statements.length>18 || fixed.statements.length+5>grant.allocation.maxStatements
    || readBound>grant.allocation.maxAcquiredBytes
    || publicationBytes+readBound+header.payloadBytes*4>grant.allocation.maxAggregateBytes) return fail('operator_preacquisition_budget');
  const batch=async(plan:readonly FixedStatement[]):Promise<Row[][]>=>{
    time();if(++requests>grant.allocation.maxRequests||(statements+=plan.length)>grant.allocation.maxStatements)fail('operator_call_budget');
    const session=db.withSession('first-primary');
    const results=await session.batch(plan.map(s=>session.prepare(s.sql).bind(...s.args)));time();
    if(!Array.isArray(results)||results.length!==plan.length)fail('operator_ack_unknown');
    return results.map(result=>{if(!result||result.success!==true||!Array.isArray(result.results)
      ||result.results.some(row=>!row||typeof row!=='object'||Array.isArray(row)))fail('operator_ack_unknown');
      return (result.results as Row[]).map(row=>({...row}));});
  };
  let acknowledged=false;
  try {const ack=await batch(fixed.statements);if(ack.some(rows=>rows.length!==0))fail('operator_ack_unknown');acknowledged=true;}
  catch { /* A failed/lost/malformed mutation ACK is UNKNOWN, never replayed. */ }
  let exact=false;
  try {
    const [summary]=await batch([readPlan[0]!]);
    if(summary!.length!==1 || summary![0]!.header_json!==encoded(header)
      || summary![0]!.payload_bytes!==header.payloadBytes || summary![0]!.actual_bytes!==header.payloadBytes
      || summary![0]!.chunk_count!==header.chunkCount || summary![0]!.actual_chunks!==header.chunkCount
      || summary![0]!.revision!==1) fail('operator_readback_unknown');
    const [headers,chunks,events]=await batch(readPlan.slice(1));
    if(headers!.length!==1||headers![0]!.header_json!==encoded(header)||chunks!.length!==header.chunkCount
      || events!.length!==1)fail('operator_readback_unknown');
    let payload='';
    chunks!.forEach((row,index)=>{if(row.ordinal!==index||typeof row.payload!=='string'||row.payload.length<1
      ||row.payload.length>262144||!/^[\x20-\x7e]+$/.test(row.payload))fail('operator_readback_unknown');payload+=row.payload;});
    const event=events![0]!;
    if(payload!==fixed.payloadText||payload.length!==header.payloadBytes||await sha2_256(payload)!==header.payloadDigest
      || event.revision!==1||event.kind!=='publish'||event.capture_key!==''||event.attempt_id!==header.reference.attemptId
      ||event.outcome!==''||event.observed_ms!==fixed.statements[fixed.statements.length-1]!.args[2])fail('operator_readback_unknown');
    time();const [final]=await batch([readPlan[3]!]);
    if(!same(final,events))fail('operator_readback_unknown');exact=true;
  } catch { /* Bounded status failure conservatively retains UNKNOWN. */ }
  return Object.freeze({outcome:acknowledged&&exact?'published':'unknown',publicationAcknowledged:acknowledged,
    readback:exact?'exact':'unknown',envelopeId:header.reference.envelopeId});
}
