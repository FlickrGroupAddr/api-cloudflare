# Synthetic catalog outbox probe 0.0.2 build 6

Run **receipt preflight (no catalog access)** first after a receipt failure.
This command calls no catalog API: it allocates a separate run and exercises
the fixed receipt directory, ordinary Lua open/write/close and SDK move path.
It preserves the current catalog property and existing complete/incomplete run
files. A passed `preflight` receipt establishes only that this receipt path
worked on this invocation, never catalog persistence or a previous write result.
Do not repeat a catalog write merely because a previous receipt is missing.

Failure dialogs identify a fixed stage and Lua error type, plus the types and
truthiness of completed file write/close/move return values. `not_called` means
the call did not return a value to the probe; it may have thrown after starting.
The summary is captured before the best-effort failure receipt, so it remains
available when that receipt also fails. No raw error string, catalog path or
property value is included. A falsey write/close/move return remains a failure;
the diagnostics do not reinterpret nil as success. The SDK 15.3 local reference
documents `LrFileUtils.move` as returning Boolean true on success.

Build 6 uses the fixed Windows native root `C:\Temp` and documented
`LrPathUtils.child` for both final and temporary receipt names. This is a bounded
native-path trial after build 5 returned false from move despite truthy write
and close results. On 2026-10-15, the Windows Lightroom Classic 15.6 host's
build 6 preflight passed: write, close and move returned truthy; SDK source
visibility was `file`, the destination was absent, and move's second return was
nil. The command called no catalog API. This native-path revision repaired the
observed receipt move failure on this host; it does not establish a universal
Windows or SDK slash restriction. SDK 15.3
documents child path construction with native Windows examples, but the move
documentation does not explicitly require backslashes or forbid same-directory
rename. After close, the probe checks that SDK `exists` reports the temporary
source as `file` and the final destination as absent before calling move.
Dialogs report only fixed booleans for those checks and the second move return's
Lua type. All falsey move results use the fixed category `sdk_move_failed`;
the error reason is never converted to text or interpreted as a path diagnosis.

Use only a newly created empty `FGA-Outbox-Probe.lrcat` on the qualified host.
The exact leaf-name guard prevents accidental use in an ordinary catalog but
does not prove emptiness; the operator verifies the disposable catalog before
running. No photo, credential or network API is used. Reload the probe after
replacing its files so the host cannot retain an older required module.

The write command stores only a synthetic record under the catalog-wide private
property `syntheticOutboxProbeV2`. It checks synchronous private-gate execution,
exact readback and rollback after a deliberately thrown callback error. The
verify command matches that exact synthetic record and its run identity.

Monitor only complete JSON files matching:

`C:/Temp/FGA-Outbox-Probe-probe-<clock-number>-<counter>-<stage>.json`

Stages are `preflight`, `same_session`, `rollback`, `restart` and `failure`. All receipts have
`schemaVersion: 2`, `probe: "catalog_outbox"`, `probeVersion: "0.0.2.6"`, `runId`,
`stage`, `outcome`, `reasonCode`, UTC `writeTime`, sanitized `host` version/build
and `stageTerminal: true`. `terminal` means the whole command has stopped:
the passed `same_session` stage is intermediate and sets it false; rollback,
restart, refused and failed stages set it true. The clock-based identifier is non-secret local
correlation, never security entropy. The body is bounded to closed synthetic
values. Temporary `.tmp` files are incomplete evidence and must be ignored.
The fixed ASCII path uses documented SDK directory/move APIs and ordinary Lua
file write/close; no SDK documentation promises power-loss flush semantics.
`writeTime` uses documented `LrDate.timestampToComponents(currentTime(), 0)`
for numeric UTC components, formatted without locale-dependent date prose.
Valid fractional seconds are floored to second resolution without rounding into
the next minute; this is receipt wall-clock time, not monotonic ordering proof.
Host context uses documented `LrApplication.versionTable()` major/minor/revision
and `build_version`, with bounded closed validation. Invalid context is recorded
only as `contextValid:false`, and invalid time as null; neither can qualify an
exact-build timed host result. No raw version string is echoed. The probe
version is fixed in its bundle and checked against `Info.lua` by a regression.

Record the runId from both passed write-stage receipts. After independently
observing a normal host shutdown/reopen of this exact disposable catalog, the
restart receipt must match that same runId and probeVersion, with valid exact
host version/build context. A `restart` outcome of `matched`
means only the value matched. `restartIndependentlyVerified`, `crashQualified`
and `powerLossQualified` are always false in machine receipts because the probe
cannot independently observe those lifecycle facts. An old, missing, partial,
unmatched, failure or refused receipt cannot satisfy acceptance. Repeated verify
refuses to overwrite the previous run's verification evidence.
An existing restart `.tmp` also refuses verification with
`verification_receipt_incomplete`; inspect only complete JSON receipts.

A receipt failure means only the operation or receipt was unavailable;
it does not prove rollback, absent catalog writes or safe external replay. No
raw exception/path or catalog content is recorded. A wrong-catalog refusal does
not mutate catalog properties. Do not deliberately terminate a host with a real
catalog open. This pass does not qualify abrupt-stop, restore or power loss.

Injected Lua5.1 tests cover a preflight with a forbidden activeCatalog function,
preservation of prior property and incomplete receipt files, actual missing
APIs, falsey I/O return values, and error objects with hostile tostring behavior.
They also cover correlation, refusal, queued/aborted write gates,
rollback failure, malformed state, receipt I/O failure, repeated verify and run
separation. These tests do not replace host SDK persistence qualification.
