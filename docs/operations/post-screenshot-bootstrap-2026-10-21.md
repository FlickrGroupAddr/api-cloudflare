# Same-process POST admission bootstrap — 2026-10-21

The screenshot successor's protected native witness must name the actual Python
PID that invokes `apply()`. The bootstrap supplies a bounded metadata rendezvous
before that invocation. Its default CLI is offline. Source preparation and fake
tests establish no current host, grant, route or action readiness.

The primary pins `scripts/post_screenshot_bootstrap.py` through the final source
manifest and independently reviewed private runtime cells before the one attached
launch. Explicit invocation is `python -B scripts/post_screenshot_bootstrap.py
--run --run-id <fresh-run> --manifest-sha2-256 <external-reviewed-manifest-pin>
--parent-token-file <canonical-protected-parent-path>`
from the selected source checkout with its exact reviewed environment. Use the
module's `run(run_id, manifest_sha2_256, parent_token_file)` only from an equally pinned caller;
neither interface accepts callbacks, executable text or paths from a release.

Before launch the primary creates and qualifies the exact run's
`private/bootstrap` directory through the established protected-directory rules.
The helper creates no directories, repairs no permissions and refuses any existing
`bootstrap.json`, `release.json`, `bootstrap-closed.json` or `bootstrap-stop.json`.
After checking the public source closure it publishes an exclusive durable
`bootstrap.json` with schema version, fresh run, actual PID string, fresh nonce,
manifest and helper byte digests, and an absolute cutoff. Protected root and
receipt checks apply. No approval/config application read, credential read,
provider request or native action occurs before release. The declared parent path
is an explicit metadata-only CLI/caller binding, never taken from an unread config.
Both parent and fixed child credential paths must already be distinct canonical
protected regular files, with distinct filesystem identities. Neither may lie in
the reserved bootstrap subtree. Their bytes are never read by this helper.

Before any manifest/helper/source hashing, the helper metadata-checks the entire
declared public source inventory and excludes both credential paths and file
identities. It rechecks credential identities and excludes every existing
bootstrap marker before any release bytes. This prevents role aliasing through
a declared path, reparse target or hard link. Changed metadata refuses rather
than reading a credential as JSON or public source.

The original wall and monotonic cutoff is at most600 seconds. Repeated metadata
observations or primary commentary do not extend it. The primary observes in
chunks of at most30 or60 seconds and independently proves the exact PID-scoped
Python process, command arguments and helper source bytes. An unknown start is
spent: preserve the original attachment and evidence, never launch a replacement.

The primary binds that PID in the exact protected native witness, finishes the
current config/approval and fresh independent packet review, then exclusively
publishes the exact five-field `release.json`:

```json
{"schemaVersion":1,"runId":"<fresh-run>","owner":"<actual-pid>","nonce":"<bootstrap-nonce>","approvalSha2_256":"<final-approved-packet-digest>"}
```

This is the primary's explicit one-shot release under recorded owner authority;
the receipt itself grants none. The protected reader validates the release's
metadata before content. The release is read exactly once through the protected
same-byte reader with a4096-byte maximum, then parsed with the existing strict
duplicate-free JSON parser. Exact types, identity, nonce, schema, helper/manifest
bytes, unchanged clocks and absence of the stop marker are checked before one
fixed `apply(runRoot/private/approved-packet.json, released_digest)` in the SAME
process. Before that call the helper metadata-excludes approval/config from both
credential identities, validates the pinned final packet and requires its
parentTokenFile to equal the declared canonical parent path. All this I/O precedes
the final stop/wall/monotonic guard; slow validation cannot renew the600s release
budget. Neither release paths, commands nor callbacks are accepted. The caller
retains its original source, action-window, grant and custody checks at apply.
The bootstrap wait does not renew any action deadline. NativeFiles prewarm30 and
owner960 begin only at the later actual admission/claim; request30 and challenge10
also remain unchanged. Prepare the owner-check/prewarm cells before release and
advance immediately when the actual claim appears.

Any stop marker, timeout, clock reversal, source mismatch, malformed release,
unknown read or apply failure ends the bootstrap without replay. Before release,
the primary can publish the exact `bootstrap-stop.json` once; mere presence stops
without parsing executable content. After release, the original caller/controller
stop and same-owner cleanup procedures govern in-flight work. A bootstrap marker
cannot cancel or establish the result of an already-dispatched operation.

The helper retains all metadata and attempts an exclusive durable
`bootstrap-closed.json` recording its own identity/source pin, released approval
pin, apply-started/returned and a fixed sanitized outcome. Closed is not an OS
exit, provider-cleanup confirmation or native-task completion. A failed closure
is unknown and retains the spent claim. Closure I/O never replaces an original
release/apply exception: that original exception is preserved with a fixed
closure-unconfirmed note. If no earlier failure exists, closure failure is an
explicit failure itself. The primary must separately observe the
original attached exit, matching closed native owner, independent native task
termination and same-owner cleanup/revocation disposition before kernel handback.
There is no deletion, restart, native initialization or alternate cleanup owner
in this helper. Private actual identifiers and receipts remain outside Git.
