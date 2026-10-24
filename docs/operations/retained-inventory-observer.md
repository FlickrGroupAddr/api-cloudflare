# Retained inventory observer

`scripts.retained_inventory_observer` prepares a held historical observation of
two retained inventory records. Importing the module performs no I/O. Its CLI
prints `DISABLED` and `NO_GO`; it exposes no execution switch.

## Execution contract

The trusted Primary supplies an independently reviewed exact binding and a
backend that reuses mature privacy and stable-reader helpers. The backend owns
filesystem and native ACL operations; this module adds no native framework.
Tests use invented records and a memory adapter and grant no actual access.

Before any metadata observation, `run(execute=True, ...)` requires a genuine
externally authenticated admission callback for the held scope fingerprint and
chosen whole-second UTC interval, at most 30 seconds. JSON, source acceptance,
a digest or a boolean cannot authenticate the owner. The Primary must consume
admission outside the observer before returning success from that callback and
preserve the spent decision across new objects and process restarts. This
observer's local spent flag alone cannot provide durable replay protection.

The only content sequence is:

1. One index read, at most 65,536 bytes, matching its independently held
   SHA2-256 digest. Validate 15 distinct `/files` names and 1,083,133 aggregate
   declared bytes; select exactly one `restoration-inputs.json` row.
2. Only after those checks, one restoration-record read, at most 262,144 bytes,
   matching the selected row's exact byte length and `sha256` field.

The aggregate returned/validated ceiling is 327,680 bytes. The selected digest
never authorizes following another row, endpoint locator, module or payload.
Duplicate JSON keys, malformed selected metadata, identity drift, privacy
failure and digest mismatch stop the attempt. No retry or repair path exists.

The binding must pin the existing stable reader. The reviewed reader requests
`read(maximum)`, so no extra refusal-sentinel byte is authorized. If a helper
raises after a possible read, the report conservatively retains that record's
entire maximum as unknown possible read extent. Zero returned bytes does not
prove zero observation. Callback counters distinguish attempted and completed
operations; they do not claim to count each underlying native API call.

## Timing and privacy limits

Monotonic and UTC wall clocks fence observer callbacks and reject nonfinite,
expired or regressing times. Fences are cooperative. Synchronous filesystem or
ACL calls can block beyond the interval; this module cannot preempt them and
does not install a per-native-call watchdog. A late return discards the held
observation. Any actual access proposal must disclose this limitation and the
precise helper, ancestor checks and allowed metadata operations.

Results retain original bytes and values in held memory with suppressed object
representations. Safe reports and projections use closed status/boolean fields
and counts; they contain no raw provider messages, identities or record values.
The observer creates no files or directories and makes no provider, credential,
network, restoration or deployment call.

## Historical meaning and provenance

A successful shape/digest observation supplies historical metadata for later
semantic review. It establishes neither current provider identity/configuration
nor current custody, active permissions, creator authenticity, referenced
payload integrity or positive qualification. `currentFactQualification` stays
`NO_GO`, including on success.

The scoped decoder uses selected field meanings from
[`fixed_origin_restore.py`](../../scripts/fixed_origin_restore.py) and the
restoration writer in
[`existing_photo_inventory.py`](../../scripts/existing_photo_inventory.py).
It does not invent a closed top-level integrity-index schema. No public
integrity-index writer was located during preparation. The existing restoration
consumer's index pin differs from the separately held historical selector pin;
source inspection alone has not explained that provenance discrepancy. An exact
private binding must preserve its independently authorized pin, disclose this
gap for a Primary decision and stop on mismatch. Trying a different digest,
format, path or root requires a separate decision; it is not an observer
fallback.
