# Album attachment worker source — 2026-10-17

Ticket 0112 implements the accepted album read/add/read path in
`src/album_attachment_worker.ts`. It is dormant unless
`FGA_ALBUM_ATTACHMENT_ENABLED` equals `1` and an internal caller supplies a
transport factory. There is no default provider factory, credential reader,
scheduler registration or public worker route.

- A database claim supplies all album, photo, owner and revision authority.
  Pending materialization and fulfilled archived relationships are not add work.
- Complete fresh presence finishes membership without adding. Complete absence
  permits one prepared add only after a committed marker and current-fence check.
- Success, code 3 and uncertain results all require another complete fresh read.
  An unavailable read preserves reconciliation; absence records bounded retry.
  Documented add results are recorded before that read; a failed result commit
  preserves uncertain dispatch rather than asserting membership.
- Recovery claims are read-only. Their fresh absence schedules a later attempt
  instead of sending another add in the same invocation. The store permits at
  most eight adds per unresolved membership episode. Fresh absence at exhaustion
  records attention with the absence proof; fresh presence can still complete.
  Due times and exponential backoff belong to the attachment store.
  Unavailable reads retain pending state with backoff; finite invocation time and
  one pre/post read bound each pass without inventing remote absence evidence.
- Wrong owner, missing album/photo and binding conflict become attention states.
  No path removes membership, replaces album identity or repeats an image upload.
- If an already fulfilled relationship is archived while a marked drift attempt
  remains unresolved, recovery may read only. Fresh presence verifies; fresh
  absence records `archived_drift_unresolved` attention with proof. It never
  restores that archived membership. Unavailable reads retain pending/backoff.

The invocation has a 45-second monotonic budget, reserves 15 seconds for a
provider operation plus commit and 5 seconds for completion transactions, and
bounds each awaited operation by the remaining invocation lifetime. The
synthetic transport additionally owns its operation timeout and cancellation.
Internal transport composition must use the shared rate-budgeted Flickr fetch
wrapper. This source-only seam does not constitute a production factory or
hosted rate/restore qualification.

The canonical authority is `album-scoped-publish-contract.md`,
`album-write-reconciliation.md` and `album-lifecycle-contract.md` in the sibling
architecture repository. Independent test/review and aggregate validation are
recorded in the batch handoff; this note does not claim hosted qualification.
