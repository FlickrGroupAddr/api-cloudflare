// MIT License; copyright 2026 Terry Ott.
// Trusted SOURCE data boundary. Missing actual qualification is not a runtime
// request/env/JSON toggle and no label below supplies the required actual work.
import type { StableChannelQualification } from '../pmb1-runtime-evidence/types.ts';
export interface NativeAuthorityQualification {
  channel: StableChannelQualification;
  namespace: string;
  operation: string;
}
// No actual observations/qualification artifacts have been supplied. A later
// separately reviewed SOURCE data revision may retain their qualified anchors.
// It must not contain own final module/version or finite envelope/attempt facts.
export function sourceQualification(): NativeAuthorityQualification | undefined { return undefined; }
