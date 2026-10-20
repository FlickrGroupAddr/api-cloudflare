# #0222 indexed menu ID format adaptation

Source adaptation for the #0218 no-cloud rehearsal, 2026-10-20.

The read-only #0218 preflight found that the supported Sky accessibility tree
appends ` ID: <positive integer>` to the exact fixture menu label. The earlier
parser refused that line with `observed_command_mismatch`; no fixture invocation
or rehearsal claim resulted. This note records new #0222 source work and leaves
the Completed #0216 proposal and evidence unchanged.

The Node controller now accepts an optional, exact ` ID: ` suffix followed by
one canonical decimal positive safe integer on its existing exact label variants.
The suffix cannot contain leading zeros, signs, whitespace, unknown annotations,
disabled state, additional IDs, or values above JavaScript's safe integer range.
It is generated tree metadata, not a replacement for the observed click index
and not evidence that the native menu item is enabled or actionable.

The parser still requires one command-text occurrence across the whole tree and
one safe, unique index. All prior label/index syntax remains supported. The
controller's owner/request/deadline checks, durable intent, single input latch,
immediate refresh, acknowledgement, and no-replay semantics are unchanged. There
is no coordinate or keyboard fallback. Node remains necessary for the supported
Computer Use Node REPL integration; this change adds no runtime or dependency.

Synthetic source tests cover the old formats, the closed suffix grammar, maximum
safe ID, malformed and oversized IDs, disabled/unknown annotations, duplicates,
and index safety. They preserve the existing controller lifecycle checks and
make no claim of native invocation, fixture entry, or qualification. Fresh
independent source review and a separately reviewed #0218 packet bound to the
new source are required before the primary consumes this adaptation.
