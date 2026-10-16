# Group-selection eligibility and retained status read cores

This source-level implementation follows the accepted architecture
`plugin-service-contract.md`, `existing-public-photo-intake.md`,
`queue-status-api.md`, and `moderator-safety-ui-conformance.md`. It does not
qualify the Lightroom Classic host transport or activate submission writes.

`GroupSelectionEligibility.assemble(groups, membership, history, statusClient,
jsonNull)` consumes complete validated aggregates from group discovery, existing
photo membership, and `SubmissionStatusClient.history`. Unbound photos pass nil
for both membership and history. The writable snapshot must be fresh. Bound
inputs must identify the same exact binding and Flickr photo. A `ready` result
contains `rows`, `eligibleGroups`, and `eligibleGroupIds`; each row has
`flickrGroupId`, `displayName`, `code`, `copy`, `readOnly`, informational
membership presence, retained intent, and a closed action list. IDs are sorted
bytewise. The union includes historical and member groups absent from the
writable snapshot; their identity remains visible without inventing a current
display name. Block protection wins over membership, then retained intent, then
first-add eligibility. Every retained intent remains read-only.

`load(dependencies, binding, prior)` injects `loadGroups()`,
`loadMemberships(binding)`, `loadHistory(binding)`, `statusClient`, `jsonNull`, and
optional `cancelled()`. The injected loaders own authenticated complete reads;
they must never return partial pages as complete aggregates. No loader performs
a write or supplies user-editable authority. Failure returns `nil`, a closed
reason, and an unavailable wrapper holding `previous=prior` only as stale
diagnostic data. The caller disables the complete handoff and never reconstructs
eligible controls from that prior model.

`SubmissionStatusClient.history(dependencies, binding, prior)` injects
`request('GET', relativePath) -> bytes, responseHeaders`, a non-yielding JSON
`decode(bytes)`, the decoder's explicit `jsonNull` sentinel, and optional
`cancelled()`, and mandatory yielding `sleep(seconds)`. The decoder preserves JSON object/array identity using
`__jsontype`, as the bundled dkjson decoder does. Before decoding, the client
checks bounded strict JSON grammar, including duplicate decoded object keys,
trailing bytes and nesting. It validates the closed projection, calendar
timestamps, safe integers, exact binding/photo identities, unique intent/group
IDs, descending continuation order, complete summary counts, write-gate holds,
queue constraints, outcomes, attention actions, and authoritative block shape.
`validateIntent` and `presentation` expose the same validation and reviewed
read-only status copy for other pure controllers.

The current status API provides keyset continuations without a snapshot token.
The client therefore performs two complete traversals from page one and requires
equal semantic content, summary and revisions, ignoring only advancing
`observedAt`. A changed traversal returns unavailable instead of publishing a
mixture. This detects observed changes; it is not a server-transaction snapshot
or proof against changes after the reads. The backend remains the admission
authority. A prior intent cannot disappear, change identity, regress revision,
or change state without a revision; neither the observation time nor a shared
write-gate revision may regress against the prior matching binding. Equal gate
revisions must retain the same state, pause timestamp and reason. Independently changing queue advisories do
not require an intent revision. A known permanent block cannot change or vanish.
Bounds are 100 pages, 10,000 intents, and
2 MiB per body. Exceeding a bound fails the complete read.

No internal poll loop, retry, work scheduling or mutation exists. Bounded
pagination paces every GET after the first through five injected one-second
sleep calls, checking cancellation before and after each yield. This spans both
traversals and respects the status bucket's sustained one-read-per-five-seconds
allowance even for more than 20 pages. Starting the second traversal also honors
the first traversal's 15/60-second poll recommendation; a terminal-only read uses
five seconds for that consistency check. The sleep adapter must actually yield
for the requested duration; a no-op implementation is nonconforming. The owning visible
dialog coalesces the installation's collection reader, waits at least
`minimumRefreshAfterSeconds`, and stops on null recommendation or dialog close.
Successful cadence honors the server's 15/60-second recommendation and at least
five seconds per request across both traversals, preventing large histories
from exceeding the installation's sustained read allowance across refreshes. Failure wrappers
request at least 60 seconds and honor a valid integer `Retry-After`; transport or
503 failures require increasing backoff in the owner. A next refresh always
starts page one. Cancellation is checked before and after every request and
between aggregate loaders. The SDK task encloses yielding work in `LrTasks.pcall`
and maps exceptions to unavailable; raw Lua 5.1 `pcall` wraps only decoding.
Authentication, fixed HTTPS origin, redirect refusal, timeout, bounded SDK body
acquisition, credential revalidation, visible lifecycle, concurrent-request
generation fencing and stale rendering
remain obligations of the host adapter. Raw server text and exception messages
are never returned by these cores.

The Lua 5.1 fixture tests cover all retained states, block-first membership,
nonwritable historical pairs, strict malformed responses, 101-intent keyset
pagination, 1,201-intent/26-read bucket simulation, between-pass change,
observation/gate regression, stale failure, cancellation during paced waits and Retry-After.
They provide injected boundary evidence, not hosted/native qualification.
