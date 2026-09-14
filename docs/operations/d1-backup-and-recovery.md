# D1 backup and recovery baseline

Status: Investigated and resolved; Terry accepted daily backup coverage as
sufficient on 2026-09-14. This does not amend the accepted restore/conformance
requirements.

## Provider recovery

Cloudflare D1 Time Travel is always on for the production storage backend and
supports recovery to a chosen minute. Its retention is 7 days on Workers Free
and 30 days on Workers Paid, with no additional history/restore charge. The
observed database generation is `production`, which supports Time Travel. The
owner confirmed upgrading the account to Workers Paid on 2026-09-14. The
project's documented Time Travel retention is therefore **30 days**. This records
the owner's confirmation and the provider's plan limit; it does not claim a
30-day-old bookmark was tested on this recently created database.

Source checked 2026-09-14:
[Cloudflare Time Travel and backups](https://developers.cloudflare.com/d1/reference/time-travel/).
Time Travel restores overwrite the database in place. Retain the returned undo
bookmark. The feature covers D1; it is not a backup of Worker configuration or
Secrets Store credentials. Scheduled exports can provide longer retention,
but no independent recurring export job has been configured for this project.

## Implemented and tested

`scripts/current_schema_archive.py` exports the exact current schema and rows
from a stopped source and verifies a restored database. The earlier hosted-to-local
SQLite check has now been supplemented by a disposable hosted D1-to-D1 restore
at the current 37-table migration head. All 12 checks passed and cleanup was
confirmed; see [the recorded evidence](../evidence/hosted-current-schema-restore-2026-09-14.json).

The drill retained all four permanent-block seed reasons and later session and
installation revocations, rejected the stale pre-revocation snapshot, checked
restored SQL guards, and kept write gates paused. D1 rejects the generic SQLite
`integrity_check`; the hosted checker explicitly selects D1's documented
`quick_check`, plus exact schema/row equality and foreign-key validation.
[Provider SQL surface](https://developers.cloudflare.com/d1/sql-api/sql-statements/#pragma-quick_check).

This proves restoration of a complete frozen recovery snapshot. It does not
merge missing facts from an unavailable newer source, verify live native-secret
generations, or constitute the complete production conformance pass. Private
archive payloads stay outside Git and logs; public evidence is sanitized.

## Accepted backup strategy

Terry stated on 2026-09-14: "Daily backups is perfectly fine" and directed that
the investigation be recorded as resolved. Daily recovery coverage is sufficient
for this private hobby project. D1's automatic Time Travel history meets that
frequency requirement with recovery points throughout the day; a separate daily
snapshot/export job is not required by this decision. Keep the manual export
utility for migration checkpoints and portable copies. No independent recurring
export job is being claimed as deployed.

The backup-frequency/strategy question is resolved. The remaining work below
is restore validation, not an outstanding owner decision about backup frequency.

## Remaining restore validation

The disposable hosted restore drill is complete. The release gate still requires
its integration with the complete production path and native-secret reconciliation.
Stop runtime writers before restoration and keep writes paused afterward. Verify schema,
rows, guards and integrity; reconcile newer permanent exact-pair suppression,
unresolved dispatches, revocations and live secret generations before resuming.
An older database must not resurrect a revoked credential or make the worker
repeat a Flickr submission. If the newer protection history cannot be recovered,
the accepted contract requires writes to remain paused rather than guessing.

Track that implementation and proof in #0018; see the
[release handoff](../research/2026-09-14-foundation-release-handoff.md).
The owner performed the Workers Paid upgrade. Codex did not perform a production
restore, scheduled export, or write-enable while documenting this decision.
