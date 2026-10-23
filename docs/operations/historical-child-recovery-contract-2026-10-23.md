# Historical-child recovery contract

Date: 2026-10-23. **Accepted for source implementation and independent review.**
Implementation, current facts, actual packet readiness and execution remain pending.

Terry explicitly accepted the independently reviewed source proposal in decision
`call_85ff42c39e6343dcbd60e8d1d7ee6c32`, answering
“Accept source contract (Recommended)”. The exact retained proposal has SHA2-256
`accd414ded834a584ef31550001b206f9be9944ae6ba7d747d77d381e5a3a0ba`. Its private acceptance and review references
are retained with implementation-board card 0161. This record accepts the scoped
contract; it is not an approval or witness file for an executable attempt.

## Two accepted changes

1. Retain the original terminal attestation, bytes and timestamp as immutable
   historical closure evidence. Supplement them with a genuine current recovery
   witness and independent judgment inside one new finite recovery interval.
   Do not retimestamp or overwrite the old terminal to make it appear current.
2. Permit one distinct exclusive recovery-only metadata namespace bound to the
   exact original acknowledged child, historical run and evidence/source pins.
   Preserve the old retirement packet and unchanged original single-use
   `issuer:retire` latch. A new namespace cannot bypass an existing, partial,
   unknown or completed latch, create another child or restart the stopped run.

This supplements the original terminal-freshness/fixed-namespace rules only
through a separate reviewed recovery implementation. The original helper,
controller, frozen source and evidence remain unchanged and cannot be presented
as implementing the new protocol. The [command-boundary procedure](post-preparation-command-boundary-2026-10-22.md)
still governs the unchanged original path.

## Required implementation and later factual gates

- Implement a separate inert controller with a closed record/role schema. Keep
  historical terminal evidence, genuine current witness, authority applicability
  and independent judgment distinct. No default affirmative facts, current times,
  automatic PASS, prepare-time bearer reads, execution, retries or hidden dispatch.
- Complete exact role/link/alias/ACL/sidecar and source/import inventory before
  protected reads/imports. Keep historical snapshot and review pins. Any permitted
  inspection uses only exact approved roles; no discovery, listing, ACL repair or
  broad runtime inventory. This source acceptance permits no actual inspection.
- Require genuine current identity/custody, full source/import closure, consumer
  AND cleanup-caller termination, permanent no-readmission and preservation of
  original unknown resources. Flags, elapsed time, old exit evidence alone or
  process disappearance do not prove those current facts. Enforce current latch
  refusal before credential access or provider dispatch; also retain the original
  producer's atomic single-use reservation. Producer reuse alone does not supply
  this earlier recovery gate.
- Provider expiry/revocation stays UNKNOWN until actual supported observation.
  Any later bounded operation validates the active parent and the exact expired
  child with unchanged historical security fields. Active, disabled, missing,
  unknown or mismatched child results refuse. No fallback credential, status
  normalization, listing, second deletion or retry after an unknown outcome.
- Current witness observation, genuine authority applicability and dispatch must
  all fit the same fixed `[start,end)` interval, positive and at most 600 seconds.
  Preserve original timestamps. End is no later than the unchanged parent and
  retention cutoff, 2026-10-26T12:00:00Z. Actual parent validity/expiry needs its own
  supported evidence; that ceiling neither proves validity nor grants renewal.
- Retain the proposed maximum of five management calls: four exact GETs and one
  exact-child DELETE, each at most 20 seconds, with unchanged producer source and
  total-byte limits. Freeze exact constants from pinned source before use. This
  acceptance allocates no executable request budget and permits no unattended
  action, resource operation or native input.
- Before credential access, require source freeze/review and independent actual
  packet review binding historical/current evidence, exact identities, authority,
  source/final bytes, current interval and unused original latch. Keep that work
  and dispatch within the interval without manufacturing freshness or clocks.
- Preserve actual results, unknowns and spent claims/journals. Independent final
  review reconciles calls, wire bytes and the original latch. A deletion receipt
  proves neither resource cleanup, physical erasure nor POST qualification. No
  child bearer is needed; the parent retains only its already accepted lifetime.
- Synthetic tests must cover immutable history, missing/stale/current witnesses
  and authority, interval boundaries, deadline, existing targets, aliases and
  sidecars, source drift, used/unknown latch, child identity/status mismatch,
  partial writes, no retry and no prepare-time dispatch. Local tests are not
  current host/provider facts or positive qualification.

## Acceptance and remaining work

The source proposal passed fresh independent High review before Terry's decision.
Acceptance now permits the separate source implementation and independent review;
it supplies no current facts, actual packet, credential access, deletion or POST
run. Do not retrofit affirmative consent into an old packet or revive a spent run.

A fresh synthetic POST successor still needs its own new unspent identity,
complete reviewed command/source graph, genuine current native/account/grant/
history/authority records and existing finite run/cleanup/no-replay boundaries.
Positive measured method-specific evidence and independent review remain required
before dependent transport work. The historical child disposition remains unknown
and must not be hidden by a new attempt. No such implementation or action occurred
while recording this acceptance.
