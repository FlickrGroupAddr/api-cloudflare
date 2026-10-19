# PMB-1 native alarm compatibility refusal

Date: 2026-10-19. Ticket #0194. Status: **Source-only NO-GO; independent High
review passed for this negative handoff. Native support and actual qualification remain false.**

The evaluated native interface does not supply the complete `AlarmDispatch`
required by the unchanged [#0186 object candidate](pmb1-object-source-2026-10-19.md).
No supported adapter and disposition proof was established for that candidate.
The [refusal probe](../../probes/pmb1-native-alarm/refusal.ts) accepts the optional
native callback shape, including zero arguments, and throws before any application
read or mutation. Its disposition verifier always refuses. It is unregistered,
has no storage capability, binding or Worker entry point, and is **not deployable
as a solution**: throwing may itself induce native retries and metadata changes.

This is a precise negative compatibility finding for the evaluated candidate and
interfaces, not a claim that every possible native scheduling design is impossible.
The [accepted PMB-1 contract](prospective-maintenance-contract-decision-2026-10-18.md#future-artifact-durable-objects-and-other-writers)
still controls. Neither this source result nor a Completed ticket can qualify
#0182, permit retained-artifact assembly, waive equality, omit alarms/metadata,
or authorize an alternate architecture.

## Verified interface and source pins

Public primary documentation was read on 2026-10-19. These are documentation
observations, not observations of any account or runtime:

- The [native handler reference](https://developers.cloudflare.com/durable-objects/api/base/#alarm)
  describes an optional information argument with retry count and retry flag;
  it supplies no application invocation or per-arm generation.
- The [alarms reference](https://developers.cloudflare.com/durable-objects/api/alarms/)
  describes one scheduled alarm per object, replacement by `setAlarm`,
  at-least-once execution, bounded failure retries, and one active handler per
  instance. Its retry statement applies to the latest `setAlarm`. It does not
  supply an application delivery identity or global disposition receipt.
- The [SQLite alarm methods](https://developers.cloudflare.com/durable-objects/api/sqlite-storage-api/#alarms)
  expose a scheduled time, which can be null during execution. Replacement and
  deletion do not cancel a running handler. The
  [alarm deletion reference](https://developers.cloudflare.com/durable-objects/api/alarms/#deletealarm)
  describes retry prevention inside a callback as best effort.

There is a material documentation/type difference: pinned
`@cloudflare/workers-types` **5.20261015.1**, `index.d.ts:584`, also declares
`scheduledTime`. The current handler prose lists two fields. The probe uses the
installed complete `AlarmInvocationInfo` type and tests that full pinned shape.
Even assuming the timestamp is delivered, equal-time replacement gives two arms
the same timestamp; retry fields also repeat across events. No native field is
the candidate's durable `alarmGeneration`. Missing optional information cannot
be repaired from the current marker.

[source-pins.json](../../probes/pmb1-native-alarm/source-pins.json) pins SHA2-256
digests of the unchanged #0186 candidate and installed native declarations,
the package version, observation date and primary URLs. Tests verify those local
pins and explicitly check all three declaration fields. The URLs are dated
observations, not immutable content digests or a claim of hosted compatibility.
No tooling, package lock, source candidate or Completed #0186 record changed.

## Identity and disposition boundary

An equal-time replacement increments #0186's exact durable per-arm generation.
The original frozen token is refused by `alarmCallback(original)`. In the
negative-control test, an old handler starts and yields before reading its
marker, a replacement commits, and the old handler reads the replacement token.
Calling `alarmCallback` with that invented identity consumes replacement work.
This is an injected application scheduling counterexample, **not evidence that
Cloudflare delivers an old retry after replacement**. In particular, the test
does not contradict the documented latest-set retry rule.

Capturing the token before yielding protects that invocation, but does not prove
which arm caused a zero-argument callback that has not read anything yet.
A mutex that merely serializes `alarm()` does not bind native delivery to an arm;
ordinary writers may replace the marker. A constructor cache also loses its
identity on restart and cannot supply durable independent disposition.

The conventional stricter option was considered: forbid replacement/rearm until
the previous callback finishes. It would require every alarm writer to use that
restriction, plus a supported terminal callback/queued-delivery disposition
boundary before releasing it. The unchanged candidate permits replacement,
including equal-time replacement; its transaction finishing is not native
handler completion. A local marker, `getAlarm() == null`, in-memory lock,
elapsed retry window or an application return value supplies no independent
global disposition receipt. Restart also discards an in-memory completion lock.
The documentation reviewed does not establish the required full boundary for
this integration. Permanently refusing future arms avoids reuse by ceasing to
support candidate behavior. None of these is silently adopted as a replacement
architecture or proof of support. A future conventional mechanism can be
re-evaluated against the unchanged contract when its actual guarantees and
complete writer integration are concrete.

Explicit deletion may remove the candidate marker and let its **source-local**
drain finish after admitted work settles. It cannot attest that a provider
callback was canceled. The refusal verifier therefore cannot authorize even the
exact next reopen generation. A fake successful verifier would recreate the
unproven assumption. There is no cancellation of an unknown external result,
automatic reopen, timeout unlock, generation reset, or mutation replay.

## Synthetic checks and actual gaps

The suite imports the unchanged #0186 class and uses an isolated in-memory SQLite
adapter with serialized SQL/KV/explicit-alarm transactions. It exercises:

- Zero-argument/native-info refusal, including supplied fake application identity.
- Equal-time replacement and independently injected first/retry deliveries;
  restart does not consume replacement work or erase the outstanding marker.
- An already-started callback before replacement, both the unsafe latest-marker
  negative control and rejection when a real frozen old token is available.
- Null exposed alarm while delivery is injected as running, deletion, close,
  stale callback refusal and refused reopening after restart.
- External-pending restart, failed mandatory result storage with rollback,
  continued close refusal, confirmed settlement during drain, and exact closure.
- Exact-generation reopen refusal and unchanged closed application state.
- An illustrative independent metadata fault showing that application-state
  equality alone cannot imply provider metadata equality. This fault is not a
  provider model, complete reader, or actual metadata observation.

Commands from the API repository with pinned Node **24.22.0** on PATH:

```text
node --test probes/pmb1-native-alarm/refusal.test.mjs
node node_modules/typescript/bin/tsc -p probes/pmb1-native-alarm/tsconfig.json --noEmit
git diff --check -- probes/pmb1-native-alarm docs/operations/pmb1-native-alarm-2026-10-19.md
```

The scoped compiler extends canonical strict options; root `npm run check` does
not include this probe. All **nine** synthetic cases and native TypeScript
**7.0.2** scoped compilation passed under pinned Node **24.22.0**. Local checks
do not establish runtime scheduling,
input/output gates, automatic alarm removal/retry metadata, a complete independent
reader, object/version census, effective embargo or closed-interval stability.
Full typed equality remains mandatory. Any unknown, unreadable or unfenced
state refuses the all-store candidate. Positive native compatibility and the
separate actual qualification obligations remain required before assembly.

No private evidence, credential, account/provider/DNS call, real callback,
native action, registration, deployment, schema installation, capture, cleanup
or reopening occurred. Public documentation retrieval and synthetic inputs were
the only external information used.

## Independent review and follow-up

Independent High review passed this narrow negative compatibility result. Nine
tests, scoped native TypeScript and extra refusal/rollback/drain/restart checks
pass; the parent reproduced the installed suite and scoped compiler gate.
This does not establish a positive native adapter or a PMB-1 impossibility.

Follow-up #0205 implements the conventional wake-up interpretation: a native
notification may trigger fresh transactional admission of currently due work,
with generation/revision captured before yielding. Already admitted callbacks
must never refresh old authority. No native per-arm causal identity is invented.
That ordinary source direction needs no new policy gate; automatic metadata,
complete observation and independent reopen disposition still need qualification.
