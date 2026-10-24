// MIT License; copyright 2026 Terry Ott.
import { DurableObject } from 'cloudflare:workers';
import { NativeSourceRefused, type Carrier } from './source.ts';
import { qualifiedRuntimeAuthority } from './authority.ts';
import { acquireFreshNativeFacts } from './owner-core.ts';
import type { NativeAuthorityEnvironment, QualifiedRuntimeAuthority } from './authority.ts';
import type { EvidenceReference } from '../pmb1-runtime-evidence/types.ts';

export class FreshNativeCaptureOwner extends DurableObject<NativeAuthorityEnvironment> {
  protected runtimeAuthority(): QualifiedRuntimeAuthority | undefined { return qualifiedRuntimeAuthority(this.env); }
  async acquireFresh(reference: EvidenceReference, packetDigest: string): Promise<Carrier> {
    const authority = this.runtimeAuthority();
    if (!authority) throw new NativeSourceRefused('fresh_owner_unqualified');
    return acquireFreshNativeFacts(authority, this.ctx.storage, this.ctx.id.toString(), reference, packetDigest);
  }
}
