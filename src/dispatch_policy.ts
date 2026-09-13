export type DispatchOutcome = "added" | "moderation_submitted" | "delivery_uncertain" |
  "retrying" | "throttled" | "needs_attention";
export interface ResultPolicy { outcome: DispatchOutcome; reason: string; pause: "deployment" | "user" | null; }
export const THROTTLE_DELAY_MS = 86_400_000;

export function retryDelayMs(failures: number, jitter = crypto.getRandomValues(new Uint32Array(1))[0] / 2 ** 32): number {
  if (!Number.isSafeInteger(failures) || failures < 0 || !Number.isFinite(jitter) || jitter < 0 || jitter >= 1)
    throw new Error("invalid_retry_policy_input");
  const ceiling = Math.min(300_000, 5_000 * 2 ** Math.min(failures, 6));
  return Math.floor(ceiling / 2 + jitter * ceiling / 2);
}

export function classifyAdd(result: "ok" | number): ResultPolicy {
  if (result === "ok" || result === 3) return { outcome: "added", reason: result === "ok" ? "flickr_added" : "flickr_code_3", pause: null };
  if (result === 6 || result === 7) return { outcome: "moderation_submitted", reason: `flickr_code_${result}`, pause: null };
  if (result === 105 || result === 106) return { outcome: "retrying", reason: `flickr_code_${result}`, pause: null };
  if (result === 5) return { outcome: "throttled", reason: "flickr_code_5", pause: null };
  if ([1,2,4,8,10,11,116].includes(result as number)) return { outcome: "needs_attention", reason: `flickr_code_${result}`, pause: null };
  if ([98,99].includes(result as number)) return { outcome: "needs_attention", reason: `flickr_code_${result}`, pause: "user" };
  if ([95,96,97,100,111,112,114,115].includes(result as number)) return { outcome: "needs_attention", reason: `flickr_code_${result}`, pause: "deployment" };
  return { outcome: "delivery_uncertain", reason: "unknown_code", pause: "deployment" };
}

export class FlickrFailure extends Error { readonly code:number; constructor(code:number) { super("flickr_application_failure"); this.code=code; } }
