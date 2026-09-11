// Clock-independent policy. A caller must separately prove its clock is suitable.
export const PREFLIGHT_MAX_AGE_US = 1_000_000;
export function preflightIsFresh(receivedUs:number, nowUs:number):boolean {
 const age=nowUs-receivedUs;
 return Number.isSafeInteger(receivedUs) && Number.isSafeInteger(nowUs)
  && Number.isSafeInteger(age) && age>=0 && age<PREFLIGHT_MAX_AGE_US;
}
