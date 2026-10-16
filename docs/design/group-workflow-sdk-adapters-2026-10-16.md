# Disabled group workflow SDK adapters

Date: 2026-10-16. Ticket #0056. Implementation evidence, not native or production
qualification. Controlling identity, task, storage and clock allocation:
[remaining adapter map](group-workflow-adapter-map-2026-10-16.md).

`GroupWorkflowAdapterFactory.lua` is unregistered and keeps
`PRODUCTION_QUALIFIED=false`. Its `start(options, consumer, finished?)` enters
`LrFunctionContext.postAsyncTaskWithContext`, wraps yielding initialization and
the consumer in `LrTasks.pcall`, and owns a cancelable `LrProgressScope` attached
to that context. `new(context, options)` accepts only a currently owned context.
The consumer receives `(context, dependencies)` and must finish its work inside
that context. Retained dependencies become unavailable on return or cleanup.
`finished` receives the consumer result or the generic `unavailable` state;
the factory never returns SDK exception text.

The caller supplies `options.transport={capabilities, httpGet, httpPost,
batchPost}`. All four named transport capabilities (`thumbnailTransport`,
`readTransport`, `proofTransport`, `batchTransport`) must be explicitly true;
missing functions or capabilities refuse before credential reads or HTTP.
Those assertions are integration seams, not evidence of transport qualification.
The shared transport and later proof/POST qualification tickets own their
implementations and evidence. The factory does not enable a native network seam.
`options.expectedInstallationId`, when supplied, is checked against the strict
authenticated current-installation document. Preferences alone never provide
link identity.

The factory reads credentials from documented `LrPasswords.retrieve` with the
existing plug-in identifier, captures the active catalog object and canonical
current credential, refuses any candidate credential, calls the actual
`ConnectionCore.verifyStored`, then calls the actual `ExistingPhotoClient.discover`.
A validated authenticated page, including an empty page, supplies the linked
Flickr revision; installation revision never substitutes for it. The local
session accessor returns exactly the two identity fields. It performs no HTTP
and never exposes credentials. The exported secure credential reader is also
guarded; cancellation or context closure refuses before accessing SDK password
storage. The raw reader remains private to the factory's own fence checks.
Every HTTP boundary checks cancellation, catalog,
candidate and current credential before and after the call. A later discovery
link mismatch invalidates the session before rows can be exposed. Existing
client, workflow and store guards still validate exact selected binding,
membership and acknowledgement correlation. External remote changes remain
detectable only through the next authenticated response/backend checks.

`dependencies.cancel()` invalidates the invocation cooperatively. Progress
cancellation is checked around I/O, inside private write callbacks, and after
each sleep slice of at most 0.1 seconds. Context return marks cancellation before
SDK resource cleanup, which also clears the captured secret/session references.
Cancellation cannot abort or prove absence of an in-flight POST, erase a
prepared record, or justify replay. Dialog/cache cleanup remains attached to
the owning context by the existing workflow. Future visible status/recovery
consumers must invoke `cancel` on close and stay within this lifetime.

`newStore()` constructs the actual `ExistingPhotoGroupStore` with the captured
catalog, `_PLUGIN`, `LrTasks.pcall`, active catalog reader and verified session
reader. The workflow also receives those exact dependencies for its own existing
store construction. No photo, UUID, Album, published association or public
catalog metadata is created. The store retains its synchronous private gate,
exact readback and collision checks.

`newHandoffId()` increments the catalog-private decimal string
`groupHandoffSequenceV1` inside
`withPrivateWriteAccessDo(...,{timeout=5, asynchronous=false})`. It requires an
executed gate, an open/completed callback, current fences and exact readback
before exposing `sdk-handoff-v1-<sequence>`. Invalid/noncanonical/exhausted
sequences, late callbacks and uncertain writes fail closed. Allocation burns
numbers on subsequent failure; it never decrements or retries an uncertain
write. The identifiers are non-secret local correlation values, not random,
cryptographic or authorization tokens. The existing outbox remains the
authority that refuses retained-ID reuse. Catalog cloning/restoration is not a
new cross-catalog uniqueness or durability claim.

`now()` returns unmodified documented SDK wall seconds. The actual controller
refuses finite/backward/observed-age failures, including the 15-second boundary.
No monotonic API, CPU clock, wall-clock clamp or stronger elapsed-time guarantee
is invented. The FGA API backend's proof-age and current-revision enforcement
remains authoritative. Native observed behavior belongs to #0067.

Verification: 16 focused factory tests plus eight existing actual-core workflow
tests pass under Lua 5.1 through Lupa. The fixture substitutes only the SDK/HTTP
boundary and reuses actual connection/photo/workflow/store/controller code.
Cases cover missing capability, exact installation, authenticated empty page,
link change, candidate/current rotation, catalog switch, progress cancellation,
secure-reader refusal without password access after cancellation/context cleanup,
sliced sleep, context closure, sequence persistence/corruption/exhaustion,
private-gate nonexecution/late callback, failed readback, outbox ID collision and
observed clock failure. Adobe SDK15.3's Windows compiler syntax-checks both new
Lua files. Focused Ruff formatting/lint and Pyright pass. These synthetic tests
exercise mutations at potential yielding boundaries; they do not characterize
native scheduling, cancellation latency, real catalog durability or HTTP.
No host execution, real credential use, cloud call or registration was performed.
