// MIT License; copyright 2026 Terry Ott.
import { DurableObject } from 'cloudflare:workers';
import { acquireNativeFacts, NativeSourceRefused, type OwnerPacket, type Carrier } from './native-source.ts';
import type { NativeCaptureControl, ControlReference, Reservation } from './native-control.ts';

interface Env {
  // Reviewed configuration for the EXISTING owning namespace, not a new reader
  // namespace or credential. No configuration is read from an HTTP request.
  PMB1_READ_NAMESPACE: string;
  PMB1_READ_PACKETS: string;
  PMB1_CAPTURE_CONTROL_REF: string;
  PMB1_CAPTURE_CONTROL: DurableObjectNamespace<NativeCaptureControl>;
}

/** Prospective replacement composition for an existing owning class export.
 * Its constructor neither initializes missing state nor performs storage I/O.
 * There is no fetch handler, mutation method or diagnostic HTTP route.
 * Deployment/binding changes, actual custody and managed qualification are later
 * separately gated work. Never deploy this into a separate reader namespace.
 */
export class NativeCaptureOwner extends DurableObject<Env> {
  #spent = false;
  async acquire(packetSha2_256: string, reservation: Reservation): Promise<Carrier> {
    if (this.#spent) throw new NativeSourceRefused('native_owner_once_only');
    this.#spent = true; // Failure/unknown outcome spends this owner lifetime too.
    const raw = this.env.PMB1_READ_PACKETS;
    if (typeof raw !== 'string' || raw.length > 4 * 1024 * 1024
      || new TextEncoder().encode(raw).byteLength > 4 * 1024 * 1024
      || !/^[a-f0-9]{32}$/.test(this.env.PMB1_READ_NAMESPACE)
      || !/^[a-f0-9]{64}$/.test(packetSha2_256)) throw new NativeSourceRefused('native_owner_configuration');
    let packets: { packet: OwnerPacket; sha2_256: string }[];
    try { packets = JSON.parse(raw); } catch { throw new NativeSourceRefused('native_owner_configuration'); }
    if (!Array.isArray(packets) || packets.length > 128) throw new NativeSourceRefused('native_owner_configuration');
    const selected = packets.filter(entry => entry?.sha2_256 === packetSha2_256);
    if (selected.length !== 1) throw new NativeSourceRefused('native_owner_packet');
    const controlRaw = this.env.PMB1_CAPTURE_CONTROL_REF;
    if (typeof controlRaw !== 'string' || controlRaw.length > 1024) throw new NativeSourceRefused('native_owner_control');
    const control: ControlReference = JSON.parse(controlRaw);
    if (!/^[a-f0-9]{32}$/.test(control.namespace) || control.namespace === this.env.PMB1_READ_NAMESPACE
      || !/^[a-f0-9]{64}$/.test(control.id) || !/^[a-f0-9]{64}$/.test(control.packetSha2_256)
      || reservation?.controlSha2_256 !== control.packetSha2_256
      || reservation.namespace !== this.env.PMB1_READ_NAMESPACE || reservation.id !== this.ctx.id.toString()
      || reservation.packetSha2_256 !== packetSha2_256) throw new NativeSourceRefused('native_owner_control');
    const controller = this.env.PMB1_CAPTURE_CONTROL.get(this.env.PMB1_CAPTURE_CONTROL.idFromString(control.id));
    await controller.consume(reservation);
    return acquireNativeFacts(this.ctx.storage, this.env.PMB1_READ_NAMESPACE,
      this.ctx.id.toString(), selected[0].packet, packetSha2_256);
  }
}
