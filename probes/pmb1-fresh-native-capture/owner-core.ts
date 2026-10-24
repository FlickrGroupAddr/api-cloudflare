// MIT License; copyright 2026 Terry Ott.
import { acquireNativeFacts, NativeSourceRefused, type Carrier } from './source.ts';
import { canonical } from '../pmb1-no-real-object-reader/reader.ts';
import type { QualifiedRuntimeAuthority } from './authority.ts';
import { validateRuntimePayload } from './payload.ts';
import type { EvidenceReference } from '../pmb1-runtime-evidence/types.ts';

const need = (value: unknown, reason: string): void => { if (!value) throw new NativeSourceRefused(reason); };
/** Native storage is never touched before the sole D1 authority consumes the
 * exact protected reservation. Identifiers cross RPC; no packet, SQL, callback,
 * storage handle, qualification flag or caller-supplied grant crosses it.
 */
export async function acquireFreshNativeFacts(authority: QualifiedRuntimeAuthority,
  storage: Pick<DurableObjectStorage, 'sql' | 'transaction'>, objectId: string,
  reference: EvidenceReference, packetDigest: string): Promise<Carrier> {
  need(reference.operation === authority.operation, 'fresh_owner_reference');
  const captureKey = authority.namespace + '/' + objectId;
  // consume returns the complete bounded protected envelope after atomic latch
  // and final primary validation. No separate truth read or mutation retry.
  const envelope = await authority.ledger.consume(reference, captureKey);
  const payload = await validateRuntimePayload(envelope);
  need(canonical(payload.native.control) === canonical(reference), 'fresh_owner_control');
  const entries = payload.native.packets.filter(e => e.sha2_256 === packetDigest
    && e.packet.request.expectedObjects[0]?.namespace === authority.namespace
    && e.packet.request.expectedObjects[0]?.id === objectId);
  need(entries.length === 1, 'fresh_owner_packet');
  need(Number(payload.native.request.closure.start) <= Date.now()
    && Date.now() + payload.native.request.limits.milliseconds < Number(payload.native.request.closure.end), 'fresh_owner_expired');
  return acquireNativeFacts(storage, authority.namespace, objectId, entries[0].packet, packetDigest);
}

