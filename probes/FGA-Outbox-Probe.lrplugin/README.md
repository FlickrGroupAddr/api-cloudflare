# Synthetic catalog outbox probe 0.0.2 build 4

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

Stages are `same_session`, `rollback`, `restart` and `failure`. All receipts have
`schemaVersion: 2`, `probe: "catalog_outbox"`, `probeVersion: "0.0.2.4"`, `runId`,
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

A generic receipt failure means only the operation or receipt was unavailable;
it does not prove rollback, absent catalog writes or safe external replay. No
raw exception/path or catalog content is recorded. A wrong-catalog refusal does
not mutate catalog properties. Do not deliberately terminate a host with a real
catalog open. This pass does not qualify abrupt-stop, restore or power loss.

Injected Lua5.1 tests cover correlation, refusal, queued/aborted write gates,
rollback failure, malformed state, receipt I/O failure, repeated verify and run
separation. These tests do not replace host SDK persistence qualification.
