// MIT License; copyright 2026 Terry Ott.
// Unregistered source probe, NOT a deployable alarm adapter.
import type { VerifyDisposition } from "../pmb1-object/candidate.ts";

export const NATIVE_ALARM_NO_GO = "native_alarm_identity_and_disposition_unproven";

// Accept the real optional native information shape, including zero arguments.
// It contains no application AlarmDispatch. Never read the latest marker to
// manufacture the identity of the event that woke this handler.
export class Pmb1NativeAlarmRefusal {
  async alarm(_alarmInfo?: AlarmInvocationInfo): Promise<void> {
    throw new Error(NATIVE_ALARM_NO_GO);
  }
}

// Callable as #0186's verifier, but never supplies synthetic success, repairs
// state or authorizes reopening. Even an empty exposed alarm is insufficient.
export const refuseNativeAlarmDisposition: VerifyDisposition = async _generation => {
  throw new Error(NATIVE_ALARM_NO_GO);
};
