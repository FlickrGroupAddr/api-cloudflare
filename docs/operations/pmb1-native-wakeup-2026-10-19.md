# PMB-1 native alarm wake-up source successor

Date: 2026-10-19. Ticket #0205. Status: **Positive unregistered source candidate;
twenty synthetic cases and scoped native TypeScript pass. Independent High
review is required before downstream consumption. Actual qualification is false.**

The [candidate](../../probes/pmb1-native-wakeup/candidate.ts) implements the
conventional successor identified by [#0194](pmb1-native-alarm-2026-10-19.md).
Its zero-argument `alarm(): Promise<void>` satisfies the pinned native handler
interface. A notification prompts fresh local admission of current due durable
work. No callback argument, retry flag/count, scheduled timestamp, exposed alarm
time or constructor cache identifies an application arm. The accepted
[PMB-1 contract](prospective-maintenance-contract-decision-2026-10-18.md#future-artifact-durable-objects-and-other-writers)
and complete typed equality remain controlling.

## Fixed admission and completion

- `alarm()` synchronously reads the exact control generation before its first
  await. Inside one `storage.transaction`, it rechecks that same open generation
  and admission flag, reads the current durable work revision/value/due time,
  checks due time against the trusted application clock, allocates an exact
  durable admission sequence, snapshots that revision/value into an execution,
  marks the work no longer due, and explicitly deletes the exposed alarm.
  SQL, KV and explicit alarm effects commit or roll back together.
- The execution identity, generation, revision and value are immutable. Local
  completion and new external dispatch recheck the stored execution and current
  work revision transactionally. Replacement after admission fences that old
  callback; it cannot read a new marker and acquire new authority. A notification
  delayed before admission may instead admit the current due replacement under
  the generation captured at its entry. Crossing close/reopen while waiting
  refuses, even when new work is due. Equal-time replacement is ordinary new
  durable revision selection, with no claim of causal delivery identity.
- Native completion is a fixed synthetic local result. `admitCurrentDue()` exposes
  the same bounded admission for a future trusted dispatcher bridge; no caller
  supplies SQL, keys or an arbitrary transactional callback. This is a standalone
  successor schema, not an adapter that fabricates #0186's `AlarmDispatch`.
  The reviewed #0186 and negative #0194 source remain unchanged.
- `beginExternal()` durably marks a valid current admitted execution before a
  later caller could dispatch. This class sends no external request. Confirmed
  success/failure result storage belongs to that exact execution, remains
  mandatory during drain and after work replacement, and does not overwrite the
  replacement. A result failure rolls back; an unknown outcome has no cancel,
  timeout, settlement or replay shortcut and blocks close across restart.
- A failed local completion retains its durable admission. A later native retry
  cannot silently acquire fresh authority for that already admitted revision.
  Trusted completion using the exact original admission, or cancellation of
  undispatched work, must settle it. Superseded admitted work likewise remains
  visible to drain until explicitly cancelled; no implicit cleanup hides it.

## Closure and scope

Explicit isolated bootstrap creates the typed closed `(1,1,'closed')` control,
the successor's work/executions/results tables, unrestricted INSERT/UPDATE/DELETE
guards on all three, and monotonic KV revision/admission counters. Unexpected
schema, KV or exposed alarms refuse bootstrap. Construction and restart write
nothing. All ordinary SQL/KV/explicit-alarm operations check exact valid open
control inside the supported transaction boundary. Counters use canonical decimal
text and bigint arithmetic, never JavaScript-number generation ownership.

Drain first turns admission off. New scheduling, wake admissions and external
dispatch refuse; admitted local work and mandatory confirmed external results
may settle while still open. Close refuses any unresolved execution, due work
or exposed alarm. Closed SQL guards remain active. Fixed adjacent-generation
close/reopen transitions require exactly one affected row. Reopen requires the
separately qualified exact-generation independent disposition verifier, rechecks
empty drain/alarm inside the transaction and never occurs automatically.
Test verifier answers are fixture inputs, not independent disposition evidence.

There is no Worker entry point, binding, registration, migration or production
import. Integration into the actual PartitionWorker remains #0197; retained
artifact assembly remains #0199. This source provides positive native-shape
admission viability for those source tasks, subject to independent review.
It supplies no actual native scheduling, atomicity, input/output-gate or clock
qualification. The in-memory SQLite/KV/alarm adapter serializes transactions
and injects faults; it does not emulate Cloudflare scheduling.

Automatic provider delivery/removal/retry metadata and closed-interval stability,
complete independent SQL/KV/alarm/internal-state observation, object/version
census, effective writer embargo and independent reopen disposition remain
unqualified. No provider cancellation or global drain receipt is invented.
Unknown, unreadable or unsupported state still refuses the all-store candidate.
Source success cannot pass #0182 or authorize materialization/capture/reopening.

## Verification

Pinned Node **24.22.0**, native TypeScript **7.0.2** and workers-types
**5.20261015.1** are unchanged. [Source pins](../../probes/pmb1-native-wakeup/source-pins.json)
bind the immutable prior candidate/refusal, reused synthetic storage adapter and
installed native declarations. The new class statically implements the native
alarm member; the suite calls its actual zero-argument method and also supplies
hostile/repeated optional event fields that it ignores.

Commands from the API repository with pinned Node on PATH:

```text
node --test probes/pmb1-native-wakeup/candidate.test.mjs
node node_modules/typescript/bin/tsc -p probes/pmb1-native-wakeup/tsconfig.json --noEmit
```

Twenty cases pass: due/not-yet-due, duplicate retry, equal-time replacement,
restart, exposed-null alarm, before-admission generation/replacement races,
after-admission revision races, concurrent once-only admission, local drain,
mandatory external-result rollback/restart, unknown outcomes, admission stop,
SQL/KV/alarm/commit faults, token mutation, counters beyond safe integers,
corruption/exhaustion, all ordinary SQL event guards and refused reopening.
The scoped compiler extends canonical strict options; root `npm run check`
does not include this probe. No tooling or shared manifest changed.

No private record, credential, provider/account/DNS call, real native callback,
deployment, schema installation, capture, cleanup or reopening occurred.
