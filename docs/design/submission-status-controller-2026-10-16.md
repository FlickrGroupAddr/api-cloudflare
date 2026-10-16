# Disabled retained-status controller

Ticket #0062, 2026-10-16. This is an implementation note, not native qualification
or registration authority. The accepted [queue status contract](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/queue-status-api.md)
and existing `SubmissionStatusClient` own validation and presentation.

`SubmissionStatusController.new(deps,binding)` requires the existing status client,
installation ID, a table-valued verified `context` token, a non-yielding
`currentContext()` reader, `now()`, yield-safe `protect(fn)`, and the client's
request/decode/jsonNull/sleep seams. `protect` has `LrTasks.pcall` semantics. It
must protect yielding I/O; raw Lua 5.1 pcall is used only in the synthetic tests.
The verified token identifies the entire catalog/credential/installation/link
session and must change whenever any of those facts changes. Supply the same
token to all consumers of that session. The composition owns creating and
invalidating the token before releasing its resources.

`open()` makes a consumer visible; `tick()` performs at most one complete history
read; `refresh()` requests a read without overriding admission; `close()` stops
further reads. The composition calls tick in its existing SDK task and observes
cancellation around its sliced sleeps. Each session/installation has one shared
in-flight owner and five-second inter-collection floor, with one cache per exact
binding/photo identity. Multiple consumers never issue per-intent requests.
Different binding histories serialize through that installation owner; the
current client requires a binding filter, so this controller does not invent an
unfiltered protocol or rewrite its validated traversal.

Each refresh calls the existing client's complete two-pass `history` from page
one. Only complete results replace the shared last good data. Failure retains
those data with a visible stale label and an allowlisted error; raw exception or
HTTP text never enters the model. A visible consumer polls at the client's
minimum interval (including its 15/60-second recommendation and pagination
floor). A null recommendation stops automatic reads. Manual refresh respects
the shared floor and failure delay. Failures use bounded 60–960-second
exponential backoff, increased to the client's Retry-After minimum when larger.
The failure counter and read deadline belong to the shared installation owner;
every binding and manual refresh honors that deadline. A complete successful
history resets the shared failure counter, restoring the five-second shared
floor while each binding retains its own recommendation or failure deadline.
Close/reopen generations and context checks fence late results and each client's
internal cancellation checks stop dependent pages. An in-flight native request
may finish; close does not claim to abort it. Nonfinite/backward clock samples
refuse further reads for that session. This observed clock guard is not a
hard monotonic-clock guarantee.

`SubmissionStatusView.model` uses the existing reviewed presentation for every
retained intent, including permanent pair protection. It does not consume
membership observations as authority to weaken that protection. The unregistered
`show(controller,context,task)` candidate uses SDK property bindings, one task
owned by the supplied context (`task.start`), and sliced `task.sleep`. Its only
buttons are Close and Refresh status. Cleanup closes the controller. The view
does not add retries, mutate gates or submissions, or render percentages or an
ETA. Exact retained intent/group IDs remain visible; historical group names are
not represented as current Flickr authority.

Focused verification executes the real controller and real two-pass client in
Lua 5.1, covering shared read admission, visible lifetime, recommendation/null
behavior, Retry-After/backoff, stale prior data, errors, context and generation
fences, all durable states and read-only protected-pair presentation. SDK host
task/dialog behavior remains an integration qualification obligation under
#0066/#0067; no `Info.lua`, accepted copy, production registration, cloud or
native action is changed here.
