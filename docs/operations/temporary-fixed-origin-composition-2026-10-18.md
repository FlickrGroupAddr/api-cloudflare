# Temporary fixed-origin composition: assembled offline packet

Date: 2026-10-18. Ticket #0149. Status: **offline implementation; NO-GO for
provider installation, native execution and promotion**.

This packet describes the private assembly and exact configuration-delta
procedure added after the [2026-10-17 source-only packet](temporary-fixed-origin-composition-2026-10-17.md).
Source assembly and synthetic lifecycle evidence do not qualify a live attempt.
The accepted architecture [documentation authority](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/README.md)
and [ADR0061](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/decisions/0061-develop-bounded-hosted-thumbnails.md)
control. The thumbnail candidate and finite target-program amendment remain
Proposed.

## Authority and artifact custody

Terry selected the strict helper investigation in #0156. The
[owner-direction record](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/project-log/2026-10-17-effective-path-helper-direction.md)
accepts that investigation, with the direct SDK selector/thumbnail path disabled.
The [helper feasibility design](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/proposals/windows-network-helper-feasibility-2026-10-17.md)
remains Proposed: helper credential ownership, backend authorization,
provisioning ceremony, implementation, adoption and qualification are separate
unaccepted work. No weaker observed-boundary contract is adopted here.

Keep these artifacts distinct:

- **Ordinary module and retained rollback.** The captured `worker.js` has
  SHA2-256 `f1cef97fe6e1e62b5ff2b57f7e11516423974e756011750feb1aebe3abb13e6d`;
  the capture-index SHA2-256 is
  `ea43ba41d7bb5c6ae7fae569f77a8d126cfcfb7a0a550e5f92856c771b9f8202`.
  Historical pins do not establish current provider state or retained-target
  availability. Preserve the original bytes and receipts. Rollback selects the
  exact original retained provider version at weight100 with `force=false`;
  never rebuild it or substitute a newer version.
- **Archived synthetic candidate.** Use commit
  `b599ca828d2a645b686aca0354d6c8ee2c2a0250` and archived bundle SHA2-256
  `c1edd7e5e721119030085c9c0705de5d2f3a32b9cffc6bbed56f363df3432e36`.
  This is an archived candidate, not the current checkout. Its exact source
  and migration closure remain separate from the ordinary module.
- **New private assembly.** Retain its actual module, receiver, configuration,
  delta and manifest bytes outside Git. Bind their actual final digests in the
  private review packet. Neither a constructor inventory nor a synthetic
  lifecycle receipt is an upload, deployment or restoration receipt.

The primary operator alone supplies separately authorized, independently
verified original-code inputs. Do not discover a fixture, open raw captures,
read credentials/configuration or query account state to make assembly pass.
Do not add a hidden source pin, invent a provider identity or fill a missing
configuration field by assumption. A missing required input is a refusal.
Public evidence may contain digests, bounded counts, closed classifications and
sanitized retrieval references; private targets, journals and full-state proofs
stay outside Git.

## Assemble and verify offline

The older `scripts.prepare_temporary_composition` prepare/verify commands still
produce a source-only closure. They do not assemble the private Worker.
`scripts/build_temporary_composition.py` supplies the separate assembly CLI:

```console
uv run --frozen python -m scripts.build_temporary_composition build --repository . --fixture <exact-authorized-fixture> --baseline <verified-baseline-json> --additions <reviewed-additions-json> --scope <reviewed-scope-json> --output <fresh-private-output> --node <pinned-node-executable>
uv run --frozen python -m scripts.build_temporary_composition verify --output <same-private-output> --manifest-sha256 <independently-retained-manifest-pin>
```

Run from the API repository only after the primary operator explicitly supplies
those inputs. Fixture and output must be outside the repository beneath a
`private-evidence` parent; output must be fresh. Replace placeholders with the
supplied exact paths, never by discovery. Use existing Node24.22.0 and
esbuild0.28.1, with uv0.12.5 and the frozen Python environment; do not install or
upgrade dependencies. No command above contacts a provider or selects a live
target.

The schemas are owned by `validate_baseline` / `build_delta` in
`scripts/temporary_composition_delta.py` and `validate_scope` in the builder.
Supply all eleven explicit configuration sections, exact target/retained version,
sole retained-version weight100 and production-state evidence. Supply the reviewed run, temporary-version identity,
four binding names, three isolated resource identities and receiver relation.
Scope binds the same run and exact 600000-ms inner lifetime. These fields are
inputs to offline validation, not observed provider facts. Do not put a bearer
or secret value into the configuration/reference envelope.

The builder verifies original-module, archived-candidate and candidate-source/
migration provenance, then bundles the actual temporary entrypoint with the
supplied exact scope. Ordinary requests delegate the original Request,
environment and context to the captured dispatcher; captured named exports and
other default handlers are retained. The qualification path uses the explicit
isolated database/quota/receiver/capability bindings. It does not replace ordinary
production configuration with a synthetic environment.

The private output inventory is:

- `worker.mjs`: assembled temporary Worker.
- `configuration-delta.json`: exact complete supplied baseline, temporary
  projection, allowed additions, comparison digests and retained restore request.
- `temporary-configuration.json` and `restore.json`: exact projections from that
  delta. The former is the full temporary envelope, not a Wrangler config file.
- `manifest.json` and `source/`: final output digests, exact captured/candidate
  bytes and pinned candidate source/migrations, composition closure, entrypoint
  and scope.

The allowed delta appends two isolated D1 resources, one receiver Worker
reference and their D1/D1/service bindings plus one synthetic-capability
plain-text binding. Baseline binding names and resource identities cannot be
reused; all other supplied baseline fields remain identical. This creates no
Actions secret and adopts no helper credential. The assembled flag describes
local output existence; all deployment/live-qualification assertions remain
false. Retain the final manifest SHA2-256 separately and use that pin when
verifying; copying a changed packet's own digest is not independent integrity.

An output referencing a receiver does not establish that receiver's deployment,
identity, behavior or current availability. The builder must refuse missing or
inconsistent inputs; a successful offline projection cannot certify the
completeness or freshness of the supplied provider capture.

The source-safe synthetic test recipe is:

```console
uv run --frozen python -m unittest tests.test_build_temporary_composition tests.test_temporary_composition_delta tests.test_temporary_composition_lifecycle
uv run --frozen python -m unittest tests.test_prepare_temporary_composition tests.test_fixed_origin_schedule tests.test_synthetic_restoration_packet tests.test_fixed_origin_preservation tests.test_fixed_origin_lifecycle
node --test probes/fixed-origin-composition/entrypoint.test.mjs probes/fixed-origin-lifecycle/quota_receiver.test.mjs
uv run --frozen python scripts/fixed_origin_schedule.py
uv run --frozen python scripts/fixed_origin_schedule.py --profile proposed-shared-discovery
```

Both schedule commands intentionally exit 2 with `no-go`; their refusal remains
the expected result. The actual retained-fixture composition suite
`probes/fixed-origin-lifecycle/composition.test.mjs` is separate: run only after
the primary operator authorizes the exact existing verified fixture and supplies
`FGA_OFFLINE_FIXTURE`. Never recreate/open a capture to satisfy a test. The
recipe above records required scope, not an assertion that this document's
author executed those checks or assembled a private artifact.

## Configuration preservation

The [restoration protocol](fixed-origin-restoration-2026-10-17.md) and
[preservation contract](fixed-origin-preservation-2026-10-17.md) retain ownership
of full-state comparison and cleanup requirements. The historical metadata
inventory contains 26 bindings: one assets, one D1, one Durable Object namespace,
fourteen plain-text and nine Secrets Store secret references, with no captured
`secret_text` binding. Counts alone prove no resource identity or continuity.

Preserve the complete supplied baseline configuration, ordinary dispatcher and
Request/environment references. Preserve all production binding/resource
references, runtime/capability settings, assets/class lifecycle, secret-reference
identities, host attachment, routes/domains, ruleset descendants, Page Rules and
effective edge inputs. Both production durable gate rows and their revisions
remain paused and pinned. Add only the explicit reviewed isolated synthetic
resources and receiver configuration; an exact baseline-to-temporary delta must
account for every change. Never call absent fields inherited.

The build input/delta is offline configuration evidence. It does not refresh
the captured baseline, prove effective provider settings, establish safe
provider-wide ownership of fixed Actions-secret names, or qualify changed-secret
restoration semantics. An absence check plus create or local lock cannot exclude
another operator. Those live/custody gates remain separate.

## Complete-delta lifecycle rehearsal

`scripts/temporary_composition_lifecycle.py` now also exports
`build_composition_plan(delta, start_ms)`, `SyntheticCompositionProvider`,
`LifecycleJournal` and `rehearse_composition`. These Python APIs have no CLI,
provider transport or caller-injected live adapter. The older eleven-operation
receiver-only `build_plan` / `rehearse` seam remains separately labeled.

The complete-delta plan fixes 23 ordinary operations: independent full-baseline
read; three exact resource create/read pairs; synthetic initialization/read;
temporary version upload/read; temporary deployment/read; admission disable/read;
retained original restore/read; and three reverse-order delete/absence pairs.
At most two read-only reconciliation observations after ambiguity bring the
operation cap to 25. A journal commits the single-use plan and each dispatch
latch before the operation; pending latches survive close/reopen, and replay is
refused. The local exclusive marker is not a provider concurrency guarantee.

Every transition compares the supplied complete configuration/production-state
envelope and exact owned-resource/admission state. Stop or inner expiry prevents
new work and enters bounded safety cleanup; outer expiry stops further model
calls and leaves cleanup unconfirmed. Unknown/malformed/exception outcomes latch
uncertainty and permit only the two bounded reads, without clearing the mutation
latch or replaying it. The 600000-ms inner window and 1200000-ms outer window
are unchanged; synthetic ticks are not real network deadlines.

The rehearsal stops admission before selecting the immutable original retained
version; it never uploads or rebuilds rollback. After full restored-state proof,
it retires only the acknowledged three owned resources in reverse creation
order. A temporary uploaded version is retained metadata and is explicitly
reported as `retainedTemporaryVersion`; successful owned-resource cleanup does
not claim that version was deleted. Exact retained version/artifact and cleanup
receipt semantics still need real provider evidence.

A `confirmed_offline` result proves the closed synthetic transition sequence
only. Configuration, production-state, ownership, module/version drift, ambiguous
operations and expiry retain their negative or unconfirmed dispositions. The
complete-delta rehearsal supplies useful backend/lifecycle evidence while all
live/client, preservation and authority gates below remain closed.

## Remaining live and client gates

The [authorization disposition](fixed-origin-authorization-disposition-2026-10-17.md),
#0037 unqualified transport and #0043 negative provider-restoration result remain
unchanged. Before a live packet can be reviewed, complete all of the following:

- Establish supported pre-follow bearer protection and pre-return allocation
  controls for the effective client path, including provider-generated errors.
  [Finite received-byte observations](../research/effective-path-method-2026-10-17.md)
  do not establish those controls. A Proposed helper is not a qualified path.
- Implement and accept the exact finite native program, including source/state
  isolation, rendering, navigation, stale results, cancellation and separate
  backend disconnect observations. Existing quotas remain 96 combined FGA
  admissions and 16 receiver/report admissions; inner/outer lifetimes remain
  600000/1200000 ms, one attempt and no replay. Current source needs at least
  150 FGA admissions, 6 receiver admissions and 33 native invocations before
  other required work. The Proposed 96/6 arithmetic is not executable authority.
- Complete all five route-conformance phases for the exact temporary and exact
  original rollback artifacts/configurations: compiled inventory, configuration
  projection, built development HTTP matrix, same-build isolated public HTTPS
  matrix and artifact/deployment binding. VM refusal cases are insufficient.
- Independently establish real provider restoration and changed-secret semantics
  for the captured binding types through separately scoped Case A/B packets.
  The [synthetic restoration model](synthetic-restoration-packet-2026-10-17.md)
  is no provider receipt.
- Supply fresh complete capture and retained-target availability, both paused
  production gate rows/revisions, bounded consistent full-data proof,
  background-writer quiescence/accounting and safe authenticated ordinary reads
  bound to the captured artifact. Row counts and environment flags are
  insufficient.
- Review the full finite provider/ordinary/native operation ledger and exact
  ownership/cleanup scope. Isolated preview, synthetic restoration,
  production-domain installation and native loading/running have distinct
  authorization scopes; generic approval cannot supply missing evidence.

Stop admission before restore, independently confirm the exact disabled run,
restore the exact retained original once, then independently compare full
configuration, module/version, effective edge, production facts and paused gate
revisions. Delete only acknowledged exact owned temporary identities after
verified restoration, in reverse creation order with independent absence
receipts. An ambiguous create, stop, restore or deletion remains
`cleanup_unconfirmed`; never replay a mutation, reset the run, guess an identity,
force restore, rotate a secret back, repair production data or remove a crash
marker automatically. Expiry does not acknowledge cleanup.

## Evidence and handoff

This document records source preparation only. It claims no actual private
assembly receipt until the primary operator supplies a sanitized final-build
receipt for the final reviewed inputs. It records no provider/account request,
credential read/probe, capture access, deployment, native initialization/input/
load/run, real-photo operation or capability activation by its author.

Keep deployment permission, provider restoration, changed-secret semantics,
production preservation, authenticated ordinary-route proof, transport/native
qualification, feasibility-change and release assertions false. Independent
review, final executed checks and Git/board handoff belong to parent integration.
