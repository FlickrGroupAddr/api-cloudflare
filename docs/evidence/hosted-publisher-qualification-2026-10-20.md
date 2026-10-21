# Hosted publisher bounded qualification evidence — 2026-10-20

The authorized synthetic hosted-publisher run completed all 28 phase checks across four scenarios at source `0c23c3697fd2163307e45de3f5327a038247c48f`. This establishes the bounded finite evidence described below; overall production qualification remains unproved.

- Scenarios: happy path, lost create response, lost attachment response and lost title response. Each completed seed, materialize, attach, title, finish, HTTP and remove checks.
- Main run: 192 provider calls / 132 mutations. Worker cleanup: 24 / 8. Residual database cleanup: 8 / 4. Combined: **224 / 144**, within the authorized **256 / 160** limits.
- Four Worker DELETE acknowledgements and four database DELETE acknowledgements were followed by exact-ID absence observations for every target.
- Token administration used ten separate calls: five for issuance and five for retirement. The individual child token was revoked; the parent was retained. Five DNS operations were separately accounted for.
- All three local callers reached terminal state after one invocation each. No replay occurred. No new unknown outcomes were recorded; uncertainty and evidence from earlier attempts remain preserved.

The audit mechanism was independently reviewed in source and executed by the primary operator. Review agents did not read raw private execution data. The selected source deliberately stores presence receipts for general readbacks. The positive progression conclusion therefore combines those receipts with the pinned source's comparison, binding and later client-progression gates. It does **not** reconstruct rich remote readback values, original response bytes or headers.

The canonical cleanup result code was 2 (`stopped_or_unknown`); the actual operating-system process exit was 1. Independently checked evidence established removal of all four Workers. It retained the four databases because canonical binding eligibility was unproved. A separately reviewed and authorized residual cleanup then supplied the four database DELETE acknowledgements and absence observations. The earlier pending cleanup result remains part of the evidence history.

These results do not establish production deployment, production scheduler qualification, feature-flag activation, native qualification, Flickr real-data qualification, a REAL-gate waiver, SQL query settlement or physical erasure. Historical failed attempts and unresolved conclusions are unchanged. The completed callers and retired child credential provide no authority to replay or extend this run.

