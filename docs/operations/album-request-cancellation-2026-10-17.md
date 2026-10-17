# Album request cancellation lifetime

Date: 2026-10-17. Source correction and regression evidence under #0154.
The dormant source remains subject to its hosted/native qualification gates.

## Measured failure and correction

On pinned Node 24.22.0, the backend aggregate exposed a candidate-discovery
request whose operation rejected at deadline while the injected request signal
remained un-aborted. Explicit garbage collection reproduced the failure with a
single temporary Request follower as well as a composed chain. Inspection of
the locally bundled runtime source showed that the Request owns its follower
AbortController and its upstream abort listener uses a weak reference to that
controller. Retaining the leaf signal alone could lose propagation.

The shared `readJson` helper now retains its input and outgoing Request objects
through response-body consumption or cancellation. Its optional internal
`FlickrFetchLifetime` context permits one innermost admission clone: at most
three distinct Requests per read. Duplicate retention is idempotent; a fourth
object or registration after release refuses. The per-read set clears in
`finally`; there is no global retention map or response-body wrapper.

Candidate discovery, title, attachment and materialization forward their already
composed Request and the lifetime context. Their redundant clones are removed.
Album rate admission retains its additional forwarded Request through that same
context, preserving its separate execution signal and all final authority,
fault, credit and window-expiry checks. Production deadlines, byte budgets,
strict decoding and no-retry rules remain unchanged.

Wrappers that allocate another Request in this read-backed composition must
register it before network handoff and forward the lifetime context. Direct
admission calls without a shared-reader context retain their existing
one-argument contract; these GC guarantees concern the tested `readJson`-backed
composition. This note does not qualify an arbitrary injected fetch wrapper,
the hosted runtime, native transport or provider cancellation.

## Verification and independent review

- Author: 66 affected checks passed; three forced-GC regressions repeated ten
  times passed 30/30. The original real 100 ms deadline test remains unchanged.
- GC cases cover input/execution cancellation before headers and during stalled
  bodies, propagated signal state, unread-body cleanup and no dependent reads.
- One fresh independent reviewer passed 16 reader/discovery checks plus private
  success/error/abort retention-release probes and the native compiler.
- A second fresh independent reviewer passed 55 admission/transport checks,
  including actual local D1 with no outbound traffic. Its isolated negative
  control removed only admission retention and reproduced the signal failure.
- Parent: 857 backend/Worker/local-D1/probe tests and 757 Python/Lua tests passed.
  Pinned native TypeScript 7.0.2, exact generated API checks, Ruff and Pyright
  passed. Staging privacy and whitespace checks accompany the commit.

Detailed private proof and frozen review receipts are retained in workspace
`work-batch-2026-10-17-archive`: `debug-0154.md`,
`review-0154-lifetime.md` and `0154-admission-independent-review.md`.
The correction reads no credentials, makes no provider/Flickr request and
performs no native action, deployment, feature activation or tool upgrade.
