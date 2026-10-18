# Temporary composition: compile first, bind returned identities later

Date: 2026-10-18. Ticket #0168. Status: **offline source implementation;
NO-GO for provider actions, private materialization and deployment**.

This procedure describes the separate staged interface for a temporary Worker
whose version identity is assigned after upload. It supplements the
[fully supplied offline builder](temporary-fixed-origin-composition-2026-10-18.md);
that builder and its immutable source pins remain unchanged. The staged interface
does not provide a provider transport, credentials, account discovery or consent.
No actual creation, upload or readback receipts exist in this source-only turn.

The scope embedded in the temporary and receiver modules contains the run,
lifetime, canary and binding-role names. It contains no temporary-version ID.
Consequently compilation can precede the returned version identity; final
configuration binding must follow it. A guessed identity, request-target echo,
old unrelated version or synthetic rehearsal result cannot close that boundary.

## Inputs and authority before private work

The primary operator must supply exact authorized paths and independently
retained input pins. Never discover or recreate an original fixture to satisfy
the command. Preserve the captured original module, fixture manifest, archived
candidate and source/migration closure described in the
[assembly packet](temporary-fixed-origin-composition-2026-10-18.md#authority-and-artifact-custody).
Historical pins alone do not prove that the original retained provider version
still exists or is the current baseline.

Before any real operation, separately review its exact target, endpoint,
effective grants, credential delivery/custody, time window, finite request and
cleanup budget, dispatch latch and reconciliation behavior. Source acceptance
and a locally valid receipt file do not authorize that operation. The current
metadata-only collection scope cannot create or initialize resources, upload
modules, deploy a receiver, quiesce writers or read production records.

The existing full baseline and delta contracts still control:

- Supply every one of the eleven configuration sections, exact account/script,
  retained original identity at weight100 and complete production-state proof.
  Missing fields remain unavailable; absence of metadata never means an empty
  configuration section. The exact schema belongs to
  [`temporary_composition_delta.py`](../../scripts/temporary_composition_delta.py).
- Establish both production durable gate rows as stored integer `enabled=0`,
  with positive pinned unchanged revisions. Establish consistent actual
  schema/full-data evidence and background-writer quiescence or a separately
  accepted consistency/accounting replacement. Flags, counts, partial checksums
  and a nonempty object cannot replace that evidence. The
  [preservation contract](fixed-origin-preservation-2026-10-17.md#paused-gates-and-consistent-full-data)
  retains ownership of these requirements.
- Establish two distinct isolated D1 identities and one same-account receiver,
  all noncolliding with production references and bound to this run. Obtain
  independently verified creation, initialization, deployment/readback and
  cleanup ownership evidence as applicable. The receiver's quota/capability
  configuration and exact module must agree with the final binding. An offline
  service reference proves no deployment or availability.

Unresolved inputs stop private materialization. This source procedure does not
weaken a validator, manufacture a baseline, accept an unobserved empty state or
replace a real receipt with a supplied claim.

## Ordered private procedure

1. **Compile and freeze.** Use only the reviewed original/candidate/scope inputs
   and pinned local tooling to create fresh private staged output. Retain the
   exact temporary and receiver module bytes and independently retain the stage
   manifest pin. This output has no provider-assigned temporary-version ID and
   makes no upload, deployment or live-readiness claim.
2. **Review the concrete action packet.** Bind the frozen module digests and
   exact configuration intent to the separately reviewed creation/upload/
   readback scope. Complete the full baseline, state, resource and receiver
   requirements above before treating an eventual final delta as actionable.
   Obtain actual owner approval before any account action. This runbook supplies
   no such approval or executable live adapter.
3. **Retain actual returned receipts.** Only a later separately authorized
   provider operation may produce the missing identities. Retain the creation
   acknowledgment and independent exact readback, including the exact target,
   run relationship, module/configuration identity and result disposition.
   Observe the receiver separately. Do not translate ambiguity into success,
   repeat an upload to obtain a convenient ID or rebuild modules after receipt.
4. **Finalize offline.** Supply the independently pinned staged packet and the
   reviewed receipt input to the staged finalizer. Bind the actual returned
   temporary-version identity into the full configuration/delta/manifest while
   preserving the frozen module bytes. The finalizer validates supplied receipt
   consistency; it does not authenticate provider provenance or observe any
   account state.
5. **Verify and review the final packet.** Retain the final manifest pin outside
   the packet and verify against it. Independently compare staged/final module
   bytes, source closure, receiver, full delta and retained restore projection.
   Source success permits this review only. Deployment, production preservation,
   restoration, route-conformance, transport/native qualification and release
   remain separate unpassed gates.

## Executable offline interface

[`scripts/stage_temporary_composition.py`](../../scripts/stage_temporary_composition.py)
owns the staged CLI and evidence validation. Run from the API repository only
with exact operator-supplied private paths. Fixture, scope, baseline, additions,
evidence and output paths must satisfy the private-path checks; each output is a
fresh directory outside the repository beneath a `private-evidence` parent.
The stage output must also be separate from the original fixture: neither may
contain the other. Final output must be separate from, and neither contain nor be contained by,
the staged directory. Keep uv0.12.5, frozen Python3.14.7, Node24.22.0 and
esbuild0.28.1; these commands install no dependencies.

```console
uv run --frozen python -m scripts.stage_temporary_composition stage --repository . --fixture <exact-authorized-fixture> --scope <reviewed-scope-json> --output <fresh-private-stage> --node <pinned-node-executable>
uv run --frozen python -m scripts.stage_temporary_composition verify-stage --output <same-private-stage> --manifest-sha256 <independently-retained-stage-manifest-pin>
uv run --frozen python -m scripts.stage_temporary_composition finalize --repository . --staged <same-private-stage> --stage-manifest-sha256 <independently-retained-stage-manifest-pin> --baseline <verified-full-baseline-json> --additions <reviewed-returned-identity-additions-json> --evidence <reviewed-supplied-evidence-json> --evidence-sha256 <independently-retained-evidence-object-pin> --output <fresh-private-final>
uv run --frozen python -m scripts.stage_temporary_composition verify-final --output <same-private-final> --manifest-sha256 <independently-retained-final-manifest-pin>
```

The first pair requires no temporary-version identity, baseline or additions.
Its `offline_unbound_temporary_composition` inventory contains `worker.mjs`,
`receiver.mjs`, the exact `source/` closure and `manifest.json`. Scope still
contains the exact run, canary, binding names and 600000-ms inner window;
compilation does not refresh that window. The offline interface checks interval arithmetic, not the current clock or consent. The existing 1200000-ms outer bound
remains unchanged. Expired scope cannot be repaired by receipt binding.

The finalizer receives complete baseline and additions under the existing delta
schema. Additions supply the actual returned `temporaryVersion`; do not supply
`moduleSha256`, `scope` or the receiver's `moduleSha256`, which the finalizer
binds from the frozen stage. It copies bytes without invoking the bundler and
adds the full delta, temporary/receiver configurations, `restore.json`,
`supplied-evidence.json`, `stage-manifest.json` and final `manifest.json`.
The final kind is `offline_bound_temporary_composition`; `identityBound=true`
means the supplied envelope is bound consistently. Provider provenance, current
baseline, production state, deployment and native/transport qualification stay
false.

Manifest pins are SHA2-256 of the exact raw `manifest.json` bytes. The evidence
pin is different: SHA2-256 of the canonical JSON **object**, using
[`synthetic_restoration_packet.digest`](../../scripts/synthetic_restoration_packet.py),
not a hash of its pretty-printed file. Retain each pin independently before
using it. A self-calculated replacement pin gives no independent integrity.

The exact evidence fields belong to `validate_evidence` in the staged module.
Its `supplied_offline_composition_evidence` envelope has these roles:

| Input role | Required consistency / retained proof reference |
| --- | --- |
| Stage | Exact independently pinned stage manifest |
| Baseline | Complete baseline and production-state object digests plus capture, consistency, paused-gate and writer receipt digests |
| Resources | Three ordered exact run-owned resources, each with creation, initialization and cleanup-authority receipt digests |
| Receiver | Exact target/run, staged receiver module, configuration digest, version identity and deployment/readback receipt digests |
| Upload and readback | Both acknowledged; same exact target/run, returned temporary version, staged module/configuration and stage pin; distinct operation identities and receipt digests |

Digest fields only name retained private proofs. The implementation cannot
inspect their content, establish their independence, check provider signatures,
authenticate their author or prove observation time/current account state.
Independent private review must establish those facts separately. Synthetic
tests may supply this shape; actual operation requires actual returned receipts.

After validation, finalization exclusively creates
`<stage>/finalization-claim.json` before writing final output. This local claim
consumes that stage's finalization attempt. A second attempt refuses, including
after a partial output failure. Preserve the claim and partial output for
review; do not delete/reset them to retry. Verification allows the claim without
changing the independently pinned stage manifest. This is a local replay guard,
not a durable provider operation journal or distributed concurrency guarantee.


## Failure, restore and custody

Missing, drifted, ambiguous, foreign-run or inconsistent identity evidence must
refuse finalization. Never edit the frozen stage, replace its independently held
pin with a freshly calculated one, or change executable scope to fit a receipt.
If reviewed scope or module inputs change, retain the original attempt and
prepare a new separately reviewed attempt; a new directory is not replay
authorization. A local exclusive output/latch cannot prevent another account
operator from changing provider state.

The final restore projection must still select the exact retained original
provider version at weight100 with `force=false`. Preserve its original captured
bytes and receipt; rollback never recompiles or uploads a replacement original.
For any later approved live lifecycle, stop admission and independently confirm
the exact disabled run before restore. Independently compare full restored
configuration, module/version, effective edge, production facts and paused gate
revisions before deleting only acknowledged run-owned resources in reverse
creation order with independent absence receipts. Ambiguity remains
`cleanup_unconfirmed`; expiry does not acknowledge cleanup. The
[restoration protocol](fixed-origin-restoration-2026-10-17.md) and
[complete-delta rehearsal](temporary-fixed-origin-composition-2026-10-18.md#complete-delta-lifecycle-rehearsal)
retain their existing limits, including the distinction between a synthetic
transition and a real provider receipt.

Keep private targets, receipts, configuration, modules and full-state evidence
outside Git under approved private custody. Public evidence may retain reviewed
digests, counts, closed dispositions and sanitized retrieval references. Do not
retain bearer or secret values in receipt/configuration envelopes. Do not print
private paths, receipt bodies or raw provider responses into public evidence.

## Source-safe verification

The synthetic suite exercises staged compilation and supplied returned-ID
binding. It uses synthetic module/fixture evidence; it does not open a retained
private capture, contact an account or prove actual receipt provenance.

```console
uv run --frozen python -m unittest tests.test_stage_temporary_composition tests.test_build_temporary_composition tests.test_temporary_composition_delta
uv run --frozen ruff check scripts/stage_temporary_composition.py tests/test_stage_temporary_composition.py
uv run --frozen pyright scripts/stage_temporary_composition.py tests/test_stage_temporary_composition.py
```

This recipe states the relevant verification scope, not a claim that this
document's author executed those checks. Final counts and independent review
belong to the integrated ticket handoff.

## Evidence disposition

This document records source preparation and a future private ordering only.
It reports no private fixture access, current baseline, empty production state,
provider ID, credential use, provider request, resource creation, upload,
deployment, restore, deletion, native execution or actual private packet.
The helper feasibility and finite native-program amendments remain Proposed;
the [authorization disposition](fixed-origin-authorization-disposition-2026-10-17.md)
and all other live/client gates remain unchanged.

Independent source review, executed verification, final Git handoff and board
updates belong to parent integration. Supplied receipt-shaped test fixtures are
synthetic evidence only; they are not observed provider facts.
