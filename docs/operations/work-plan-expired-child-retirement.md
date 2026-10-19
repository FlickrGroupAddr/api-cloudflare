# Retire one acknowledged expired execution child

An expired execution child supplies no authority for a later run or cleanup.
The accepted bootstrap parent may separately delete that exact acknowledged
child while the parent itself remains active within its original finite lifetime.
This procedure changes neither credential's expiry, grants a new child profile,
nor revives an earlier execution window or spent attempt.

Use explicit `operation: revoke_expired` only with a fresh independently reviewed
packet. The ordinary `issue` and active `revoke` modes retain their existing
current-lifetime requirements. The execution child keeps the existing exact
account-scoped D1/Workers profile; retirement uses only the parent's token
management capability.

## Required evidence

- The primary establishes that every actual credential consumer and cleanup
  caller process has terminated before protected preparation and invocation.
  A plan, scheduled window or command-line flag does not establish this fact.
- Preserve genuine original issuance commit, all nineteen historical source
  digests/Git blobs, reviewed acknowledgement and sanitized response evidence,
  exact child/parent identity, and the original six-intent issuance journal.
- Bind the current amended runtime to its own genuine reviewed commit and full
  current source closure. Historical and amended issuer source are separate
  provenance; do not assert byte equality or substitute an old HEAD.
- The new `issuance` reference additionally carries the unchanged original
  `child_details` and `historical_validation_at` from the original issuance
  packet's window end. These historical records remain active-at-issuance facts,
  never rewritten to claim a new observation or live grant.
- Keep exclusive new packet, claim, journal and evidence sinks; current accepted
  parent custody/fingerprint, exact account/child and original cleanup/retention
  bounds; a fresh window of at most 600 seconds; fresh independent source and
  protected-packet review; and the accepted owner authority for the exact action.

## Finite management protocol

Only the parent bearer is loaded. No child bearer is read or used. The recipe
remains four GETs and one exact-child DELETE, maximum five management requests:

1. Verify the active current parent.
2. Read the bounded permission catalog; this is never a list of tokens.
3. Match the exact parent policy, identity, conditions and accepted lifetime.
4. Reserve the original append-only `issuer:retire` latch, then read only the
   acknowledged child's details. Require current status `expired`, the exact
   known expiry at or before the current clock, and unchanged ID, name, issuance
   time, not-before time, expiry, policies and conditions. Parent validation
   remains strictly active and must outlive the fresh retirement window.
5. Delete only that acknowledged child ID. Require the provider's successful
   exact-ID acknowledgement before recording retirement complete.

Cloudflare documents token status values including `active`, `disabled` and
`expired`; this procedure deliberately accepts only `expired` for the expired
child path. That schema is not evidence of the actual child's current state.
[Cloudflare token details API](https://developers.cloudflare.com/api/resources/user/subresources/tokens/methods/get/)

Unknown, active or disabled child status, changed identity/policy/lifetime,
expired or changed parent, unknown response, missing ownership or a spent latch
refuses. Any uncertain deletion consumes the attempt without retry, token
listing, discovery, reissuance or bypass through a new packet. The parent is
retained for separately approved work. Successful child retirement establishes
no resource cleanup, positive qualification or cascade from parent revocation.

## Observed October 19 retirement

One independently reviewed invocation of runtime commit
`71c5878be6ed8d37758b0c15e1e586f9cf493994` completed within its fresh action
window after explicit owner approval of the exact expired-child deletion.
The provider acknowledged deletion of the original acknowledged execution child.

- All five management requests completed; no unknown intent was recorded.
- The original six issuance intents remained unchanged. One completed retirement
  latch was appended, and the consumed action cannot be replayed.
- No child bearer was read. The bootstrap parent remains retained under its
  existing finite policy; its observed active status preceded child deletion.
- No database, Worker, SQL, native or qualification operation occurred in this
  retirement. Six previously acknowledged synthetic databases remained retained
  at this checkpoint. Their old unknown outcomes were not resolved by revocation.

The immutable approval, source/packet review, actual-result review and protected
journals remain in the private operator evidence store. No credential or provider
identity is reproduced here. This records exact-child deletion acknowledgement;
it does not claim cascade, physical erasure, database cleanup, or qualification.