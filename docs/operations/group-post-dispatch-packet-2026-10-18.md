# Fresh synthetic POST dispatch packet

Date: 2026-10-18. Ticket #0160. Status: offline source preparation only.
The new source-bound proposal requires independent review and a later #0161
exact action-time decision. No owner/native consent, provider/native execution,
transport measurement or production qualification is recorded here.

The original attempt `c01ba6d2c2754597aa311c9f`, base manifest and execution bridge
remain historical, closed and immutable. Its UI invocation count was zero and
its measured result was 0/23. A bridge callback was not a UI invocation. Its
30-second request expired during preparation; a later Node stop-write EPERM did
not cause that expiry. Do not reset/replay it or extend its deadline.

## Closed new proposal

The fresh proposed run is `88603c8c3262426397a5bb67`. Its only proposed resources
are `fga-post-src-88603c8c3262426397a5bb67`,
`fga-post-recv-88603c8c3262426397a5bb67`, and
`fga-post-db-88603c8c3262426397a5bb67`. Resource absence, exact returned identity,
creation journal and verified teardown remain required at execution.

The new integrity record is
`probes/group-post-characterization/dispatch-manifest.json`. It has a closed
source-path set: the original nine source files, unchanged original base
manifest, new Python coordinator, new supported Node controller, this preparer,
this packet and the [operator rehearsal](group-post-dispatch-rehearsal-2026-10-18.md).
The preparer rejects missing/extra/substituted paths and changed bytes, and
independently pins the original base manifest digest. Neither the sealed old
bridge nor its approval/configuration/path identity is imported as action input.
The new manifest cannot pin itself; the later independently retained approval
digest pins its exact bytes through `manifestSha256`. Rehashing modified source
is a new review proposal, never permission to execute.

The exact coordination root is
`C:/Users/TDO-XPS15-2024/Documents/ChatGPT/FGA/.coordination-runs/group-post-dispatch/88603c8c3262426397a5bb67/handshake`.
The private `config.json`, `approved-packet.json` and future `operator-token.txt`
are siblings under this run's `private/` directory. No old credential file is
replayed. The native fixture retains its supported fixed path interface at
`C:/Temp/FGA-group-post-v1`; all target/used/status/stop/temp markers must be
absent after separately authorized archival/cleanup. The immutable fixture
source, version, toolkit identifier and command remain governed by the unchanged
[base packet](group-post-characterization-2026-10-16.md).

## Offline preparation and later binding

Run `uv run --frozen python -m scripts.prepare_group_post_dispatch` to verify and
print only the non-secret proposal. `--prepare` creates a new run directory and
writes templates with empty account/subdomain and both consent flags false. It
refuses an existing run directory, creates no handshake root or credential file,
and reads no retained private source, token, native state or provider account.
An interrupted preparation is not reusable; preserve it for investigation.

The closed configuration fields are `schemaVersion`, `runId`,
`coordinationRoot`, `nativeRoot`, `tokenFile`, `accountId`, and `subdomain`.
The closed integrity/consent record fields are `schemaVersion`, `runId`,
`manifestSha256`, `configSha256`, `ownerConsent`, and `nativeConsent`.
Private identity/provenance verification and filling actual account/subdomain
remain the primary operator's later responsibility. The supplied approval hash
must match the exact bounded approval bytes. Both consent flags must be actual
JSON true values before the runtime validator accepts; they are integrity
bindings, never substitutes for applicable human authorization.

The new coordinator validates the exact approval/configuration/source closure
before its bounded provider-token read. Only its same live job owns remote
creation, observation and cleanup. The prewarmed supported Node controller
claims the correlated identity, rehearses durable writes, persists attempt
before input, performs one observed command action and acknowledges promptly.
Unknown input is terminal and latched; it never permits another click. See the
rehearsal for exact supported API actions and the readiness-before-lifetime
sequence. Commands supplied by files are never executed.

## Verification and limits

`uv run --frozen python -m unittest tests.test_prepare_group_post_dispatch`
checks ungranted templates, no overwrite, exact closure, source/pin substitution,
original-source repinning, identity/path/extra-field rejection, approval/config/
manifest digest binding and consent/duplicate-field rejection with synthetic
inputs only. Coordinator and controller tests own their protocol behavior.

Actual Node scratch preflight results are recorded by the primary operator in
the rehearsal; successful ordinary workspace file I/O would prove only that
specific scratch operation, not native execution, host ownership or full
protocol qualification. New source review, exact runtime approval, verified
private inputs, supported API observation and any native run remain separate
gates. This offline work cannot enable group additions or claim measurements.
