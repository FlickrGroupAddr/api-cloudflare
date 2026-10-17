# Temporary fixed-origin composition operator packet

Date: 2026-10-17. Ticket #0149. Status: **offline preparation; NO-GO for
provider installation, native execution and promotion**. This packet orders
the available build, verification and lifecycle seams and identifies the exact
inputs still required. It does not certify an executable live attempt.

Accepted architecture [documentation authority](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/README.md)
and [ADR0061](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/decisions/0061-develop-bounded-hosted-thumbnails.md)
control. The thumbnail candidate, effective-path alternative and single-target
program amendment remain Proposed. Completion of #0147/#0148/#0151 accepts
neither amendment. The [authorization disposition](fixed-origin-authorization-disposition-2026-10-17.md),
#0037 unqualified transport result and #0043 negative provider-restoration
result remain unchanged. Generic execution approval cannot supply missing
engineering evidence or amend those boundaries.

## Inputs and artifact custody

Use the [existing execution packet](fixed-origin-execution-packet-2026-10-17.md)
for historical provenance, the [restoration protocol](fixed-origin-restoration-2026-10-17.md)
for exact retained-target semantics, and the [preservation contract](fixed-origin-preservation-2026-10-17.md)
for full-state comparison and cleanup receipts. They own those details; this
document supplies operator ordering.

Keep three artifacts distinct:

- The captured ordinary module and exact retained rollback target: module
  `worker.js`, SHA2-256
  `f1cef97fe6e1e62b5ff2b57f7e11516423974e756011750feb1aebe3abb13e6d`.
  Capture-index SHA2-256 is
  `ea43ba41d7bb5c6ae7fae569f77a8d126cfcfb7a0a550e5f92856c771b9f8202`.
  These historical pins do not establish current availability or configuration.
- The separately approved synthetic candidate at
  `b599ca828d2a645b686aca0354d6c8ee2c2a0250`; its archived bundle SHA2-256 is
  `c1edd7e5e721119030085c9c0705de5d2f3a32b9cffc6bbed56f363df3432e36`.
  Do not substitute the newer production checkout.
- The new temporary composition and receiver outputs: bind their actual
  final source/module/configuration digests in the reviewed private packet.
  A constructor or source inventory alone is not a provider upload receipt.

Only the primary operator may resolve retained provider/resource identities
from the independently verified private packet within separately authorized
scope. Do not open captures, credentials or configuration merely to run these
offline checks. Keep private journals, targets, acknowledgments and full-state
proof outside Git. Public evidence contains digests, closed classifications,
bounded counts and sanitized retrieval references.

## Build and verify offline

`probes/fixed-origin-composition/entrypoint.mjs` exports
`createTemporaryComposition(options)`. It requires the captured module's
`default.fetch` and the candidate module's `createWorker`, then delegates to the existing closed
composition. It has no default Worker export or environment reader. Its
constructor options are owned by
`probes/fixed-origin-lifecycle/composition.mjs`: captured/candidate modules,
isolated synthetic/quota database handles, exact receiver service handle, run,
synthetic capability, common start, inner expiry, clock and counters. Ordinary
requests retain their original Request/environment references. Synthetic
admission and receiver forwarding use only their explicit isolated seams.

The checked-in `scripts/prepare_temporary_composition.py` prepares a fresh
directory outside the repository containing `manifest.json` and `source/`
copies of its seven closed source paths. Its `prepare` command and `verify`
command are the exact source-packet interface:

```console
uv run --frozen python -m scripts.prepare_temporary_composition prepare --repository . --output <fresh-external-output>
uv run --frozen python -m scripts.prepare_temporary_composition verify --output <same-external-output>
```

Replace angle-bracket operands with local paths, without running a provider
command. The manifest deliberately records null retained-version identity,
receiver binding key and provider target, false configuration-delta verification
and `deployReady:false`. It does not contain captured module bytes, the archived
candidate/migration closure, an assembled Worker bundle or deployment config.
Preparation must not query secret presence or import a native target. Never repurpose
`probes/fixed-origin-isolation/bundle_candidate.mjs` as a rollback builder:
that helper bundles candidate TypeScript for the historical VM harness, while
rollback selects the retained original provider version.

With existing pinned dependencies and tools, run the source-safe offline checks
from the API repository. These checks need no retained fixture access:

```console
uv run --frozen python -m unittest tests.test_prepare_temporary_composition tests.test_temporary_composition_lifecycle
uv run --frozen python -m unittest tests.test_fixed_origin_schedule tests.test_synthetic_restoration_packet tests.test_fixed_origin_preservation tests.test_fixed_origin_lifecycle
node --test probes/fixed-origin-composition/entrypoint.test.mjs probes/fixed-origin-lifecycle/quota_receiver.test.mjs
uv run --frozen python scripts/fixed_origin_schedule.py
uv run --frozen python scripts/fixed_origin_schedule.py --profile proposed-shared-discovery
```

The separate retained-fixture suite is
`probes/fixed-origin-lifecycle/composition.test.mjs`. Run it only when the primary
operator has separately authorized access to an existing independently verified
private fixture and has explicitly supplied its directory through
`FGA_OFFLINE_FIXTURE`. It reads `captured.mjs`, `candidate.mjs`, the candidate
source manifest and migrations, verifies their pinned provenance and exercises
the actual modules with synthetic SQLite. It fails when that variable is absent.
It is outside the source-safe recipe above; do not find, open or recreate a
capture merely to satisfy it. After that specific fixture access is authorized:

```console
node --test probes/fixed-origin-lifecycle/composition.test.mjs
```

The two schedule commands intentionally exit 2 with `no-go`; that refusal is
the expected current result. Use the pinned Node24.22.0 and uv0.12.5 toolchain;
do not install or upgrade tooling in this packet. Run packet-specific builder,
integrity and lifecycle tests with the final committed inputs, then retain their
sanitized receipts and manifest digest. Independent review and parent integration
own the final verification claim; the commands above are a recipe, not a claim
they were all executed for this document.

## Configuration inventory and authority barriers

The known captured metadata describes 26 bindings: one assets, one D1, one
Durable Object namespace, fourteen plain-text and nine Secrets Store secret
bindings. It contains no captured `secret_text` binding. Counts do not identify
resources or prove continuity. No permitted identity-free source supplies a
complete baseline-to-temporary field diff or current effective edge.

Before any live packet can be reviewed, privately pin and compare the complete
baseline bindings/resources, runtime/capability settings, assets and class
lifecycle, secret-reference identities, whole-host attachment, routes/domains,
ruleset descendants, Page Rules and effective edge/settings inputs. Preserve
the production references and bytes, original ordinary dispatcher and paused
production intake/dispatch/thumbnail capabilities. Add only the reviewed
synthetic database, quota scope and receiver configuration. The old five
qualification binding labels are an intended interface, not observed baseline
bindings or proof that a service-binding target has been selected correctly.

The exact receiver entrypoint/configuration, provider identity mapping, full
configuration delta and safe provider-wide ownership of the fixed Actions
secret names require concrete evidence. An absence check followed by create
and a local lock cannot exclude another operator. Do not invent an identity,
replace an existing secret or call missing configuration fields inherited.

The remaining live gates are cumulative:

- Resolve the unsupported direct SDK allocation, provider-error and pre-follow
  credential boundary through accepted architecture or a supported method.
  [Finite received-byte measurements](../research/effective-path-method-2026-10-17.md)
  cannot establish effective-path protection.
- Adopt and implement an exact accepted finite native target/schedule, with
  source/state isolation, image rendering, navigation, stale-result, cancel and
  separate backend disconnect observations. Current source costs at least
  150 FGA admissions / 6 receiver admissions and 33 native invocations before
  other required work. The Proposed 96/6 arithmetic is not executable authority.
- Complete all five accepted route-conformance phases for the exact temporary
  and rollback artifacts/configurations. The existing routing-proof fixture
  and VM refusal cases cannot substitute for their development/public HTTPS
  matrices or same-artifact deployment binding.
- Independently establish provider restoration and changed-secret semantics
  for the captured binding types through separately scoped Case A/B packets.
  The [synthetic restoration model](synthetic-restoration-packet-2026-10-17.md)
  supplies neither provider behavior nor production restoration evidence.
- Supply fresh complete capture, exact retained-target availability, both
  paused production durable gate rows/revisions, bounded consistent full-data
  proof, background-writer quiescence/accounting and safe authenticated ordinary
  reads bound to the captured artifact. Row counts and environment flags cannot
  replace those proofs.
- Review the complete finite provider/ordinary/native operations and exact
  ownership/cleanup scope, then resolve only uncovered live authority. Isolated
  preview, synthetic restoration, production-domain installation and native
  loading/running are distinct scopes.

## One future finite attempt: apply, stop, restore and retire

`scripts/temporary_composition_lifecycle.py` supplies `build_plan`,
`SyntheticProvider`, `LifecycleJournal` and `rehearse` Python APIs, with no CLI
or live transport. Its closed receiver-only synthetic sequence has eleven
ordinary operations: baseline read; receiver create/read; temporary apply/read;
disable/read; retained restore/read; exact receiver delete/absence read. It
allows at most two read-only reconciliation observations after ambiguity, for
thirteen total operations. It uses a 600000-ms work window and 1200000-ms outer
window. Stop or inner expiry enters its bounded safety-cleanup branch; reaching
the outer deadline stops further model calls and leaves cleanup unconfirmed.
That terminal outcome cannot establish real restoration or remove a future
operator's recovery obligation. This is a finite orchestration rehearsal, not
the complete qualification resource ledger or proof of provider restore behavior. The older
`scripts/fixed_origin_lifecycle.py` CLI intentionally exits 2; its
`Lifecycle.attempt()` remains an offline seam.

The following larger operation contract describes what a future complete,
separately authorized main attempt must implement. It is not implemented by the
receiver-only rehearsal and is not a live command sequence. Favorable synthetic
outputs cannot supply its missing live adapter or permission.

1. **Prepare and pin.** Recheck the card is In Progress before resuming work.
   Complete every barrier above and independent review. Refresh the privately
   verified baseline; any drift requires recapture/review before mutation.
   Bind one fresh run, one attempt, exact source/artifact/configuration digests,
   closed resource inventory and common start to an exclusive private journal.
   Preserve an existing owner/crash marker for reconciliation; never assume
   it stale. Fix every operation/readback budget before starting.
2. **Create once.** Verify reviewed name/ownership conditions, commit each
   attempt latch before its operation and record only acknowledged exact
   identities. Provision only the owned synthetic resources. Initialize and
   inspect durable quota with 96 combined FGA admissions and 16 combined
   receiver/report admissions. Never retry an ambiguous create or reset a run.
3. **Install once.** Latch the exact temporary upload/deployment, then inspect
   artifact/configuration identity, ordinary delegation and both still-paused
   production durable gates. The inner window ends at common-start+600000 ms;
   the outer lifecycle ends at +1200000 ms. Recheck lifetime after awaits and
   before publication. The second ten minutes is cleanup reserve.
4. **Observe only the accepted closed schedule.** Consume its target once.
   Reserve redirect/report admissions separately. Unexpected navigation,
   missing observation, cancellation, expiry, quota refusal or ambiguous result
   stops new work and records partial/inconclusive evidence. No retry, second
   run, target reuse, borrowed cleanup time or silent omitted case is permitted.
   Native cooperative cancellation does not prove backend abort or remote
   cleanup. Connection-phase timeouts do not establish a hard total deadline.
5. **Stop admission first.** Durably disable this run's qualification admission
   and independently read back the exact run and disabled state. This admission
   revision may advance once; the two production gate revisions remain pinned.
   A failed/unknown stop retains `cleanup_unconfirmed`; expiry alone cannot
   acknowledge stop, restoration or deletion.
6. **Restore once.** Latch one nonforced retained-target deployment selecting
   the exact captured version at weight100, with `force=false`. Never rebuild
   rollback, select latest, force, rotate back a secret, repair data or choose
   another target. Independently compare version/module/full configuration,
   removed qualification bindings, effective edge, safe authenticated ordinary
   reads, complete production facts and unchanged paused gate rows/revisions.
   An acknowledgment without those observations is insufficient.
7. **Retire only after verified restoration.** Delete only acknowledged exact
   owned temporary secrets, receiver and synthetic D1 in reverse creation
   order, with one latch and independent absence receipt per identity. Never
   delete production resources or guess an identity. Separately remove only
   matching-run target/used-target, owned native cache and local ephemeral
   material; native/local receipts cannot acknowledge remote deletion.
8. **Close honestly.** Retain private journals, captures and pending latches.
   Unknown creation, restore, deletion or absence leaves `cleanup_unconfirmed`.
   Do not replay a mutation or auto-remove an owner marker on restart. Preserve
   exact surviving state for separately reviewed finite read-only reconciliation.
   Cleanup remains necessary after expiry; no clock proves it completed.

## Handoff state

This packet author performed source/authority review and documentation checks
only. No provider/account request, credential read/presence check, capture
access, native initialization/input/load/run, real-photo operation, deployment
or capability activation occurred. Final immutable packet pins and executed
test receipts are the parent integration/review seam.

Keep `deploymentAllowed`, `providerRestorationVerified`,
`changedSecretSemanticsVerified`, `productionStateVerified`, authenticated
ordinary-route verification, transport/native qualification, feasibility-change
and release assertions false. A complete offline packet can make the remaining
decision reviewable; it cannot turn missing live evidence into an accepted pass.
