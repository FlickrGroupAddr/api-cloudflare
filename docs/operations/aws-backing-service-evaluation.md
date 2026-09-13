# Evaluating an AWS backing service

Date: 2026-09-13

Status: Implementation checklist derived from accepted ADRs 0050 and 0052.
This document selects no service and authorizes no provisioning. The controlling
ADRs and scoped owner amendments govern if a checklist item conflicts with them.

## Decision threshold

Keep Cloudflare compute and first try a simple native implementation or an
already accepted operational workflow. An AWS backing service is justified only
by a concrete remaining requirement whose consequence matters for the private,
single-owner deployment. A preferred API shape, a successful AWS prototype,
or a theoretical capability to dismantle SQL guards does not establish need.
A more complicated native workaround is not automatically preferable to AWS.

Use the same behavioral acceptance tests for both candidates. Keep each durable
fact under one authority; never assume an atomic transaction spans providers,
D1 and a Durable Object, or a database and a secret store. An owner-approved
availability tradeoff does not waive suppression, guarded writes, authentication,
lease fencing, or ambiguity handling.

## Reusable decision record

Copy the following fields into a dated research record. Keep evidence and the
recommendation separate from the eventual accepted ADR. Use resource aliases and
sanitized evidence; never copy credentials, account configuration, private board
prose, or photography data into a public record.

| Field | Required content |
| --- | --- |
| Requirement | Exact accepted contract/ADR section, affected component, expected observable behavior, and owner amendments already applied |
| Concrete consequence | What actually fails, how it affects this private deployment, and whether pause/repair is acceptable; label unknown probability rather than inventing one |
| Native baseline | Smallest ordinary native design, one authority per durable fact, and actual adapter/configuration versions |
| Native evidence | Reproducible command, source revision, dated provider documentation, local versus hosted distinction, result, and cleanup; distinguish an implementation defect from a provider limitation |
| Simpler alternatives | Maintenance pause, bounded recovery, manual repair or another conventional native mapping; say which are already approved and which require a decision |
| AWS candidate | Specific backing service and its narrow responsibility, while Cloudflare continues hosting compute; existing resources are candidates, not proof of suitability |
| Identity | Runtime, migration, provisioning and recovery identities; exact operations/resources; credential source, lifetime, refresh, rotation and revocation; explicit cross-account trust if any |
| Network | Worker-to-service path, DNS, verified TLS and hostname checks, ingress restrictions, egress assumptions, region and connection behavior; no broad access as a convenience workaround |
| Failure behavior | Latency budget, timeouts, outage behavior, connection exhaustion, stale reads, lost acknowledgements, duplicate requests and recovery ownership |
| Integrity and recovery | Atomic admission/results, fencing, exact-pair blocks, append-only evidence, migration/rollback and current-schema restore; data and secret references reconciled before resuming |
| Cost | Dated assumptions and monthly low/expected/high estimates, separating requests, storage, cross-provider transfer, connection/proxy charges, backups and existing versus incremental spend |
| Operations | Who diagnoses outages and renews credentials, expected maintenance, observability without secrets, and rollback/repair instructions |
| Exit | Export format, preserved IDs/order/history, pause/cutover sequence, validation, rollback limit and safe decommissioning after confirmation |
| Recommendation | Retain native, request a scoped contract amendment, or propose the named AWS fallback; explain the total simplicity and operational tradeoff |
| Approval and proof | Exact owner decision/ADR reference and separately identified evidence still required before production adoption |

An unmeasured field is recorded as unknown with its next bounded experiment.
It cannot silently count as a pass. Avoid building a generalized broker or
privilege service merely to complete this form.

## Proof checkpoints

1. **Establish need.** Reproduce the remaining native failure under the current
   accepted contract. If the failure is a fixable application bug or an already
   accepted private tradeoff, keep the native path and close the fallback case.
2. **Prove the narrow alternative.** Use disposable synthetic fixtures for the
   candidate service and the actual Worker identity/network path. Measure the
   concrete requirement and negative permissions, not just a successful request.
   Permission to evaluate a candidate is distinct from adopting it in production.
3. **Prove failure and recovery.** Exercise dependency outage, authentication
   expiry/rotation, uncertain acknowledgements, stale workers, concurrent
   operations, backups and restore. Preserve exact-pair suppression and first
   evidence, including facts created after an older backup. Never replay an
   ambiguous Flickr write to test recovery.
4. **Compare the full burden.** Record latency and dated incremental cost, setup,
   support and recovery work. Reuse existing infrastructure only after verifying
   its current version, isolation, available capacity and configuration.
5. **Record the decision.** Obtain the scoped owner decision when a service
   choice or contract amendment is needed, then record it canonically. Existing
   authorization for commits and pushes already covers publishing the sanitized,
   verified in-scope work; it is not another approval checkpoint.
6. **Gate adoption.** Require the real adapter's complete acceptance evidence
   against the exact artifact and migration head, plus an executable rollback/
   recovery procedure. Confirm disposable-resource cleanup and close permissions
   that were needed only for the proof. A prototype pass is not a release pass.

## Applying the threshold to current evidence

| Earlier concern | Current accepted position | Remaining obligation |
| --- | --- | --- |
| A native runtime can remove its own SQL guards | ADR 0051 trusts deployed storage-owning code for this private deployment | Guard ordinary writes and prove application paths, migrations, rollback and restore preserve protected facts; capability alone does not justify RDS |
| Native secrets lack independently addressable provider versions | ADR 0052 accepts durable pause, generation matching, repair/relink and no automatic old-grant rollback | Complete production lifecycle/transport evidence; the 29-case native proof and later integration evidence do not waive release gates |
| Workers time is not independently monotonic during CPU-only stalls | ADR 0056 accepts the private observed-age profile with request preparation before final marker I/O | Prove the actual prepared transport and strict observed-age boundary; changing the database to RDS would not fix the compute clock |
| Existing AWS Secrets Manager/RDS work is available | It remains reusable conditional evidence | Revalidate the actual service/identity/network/recovery boundary only if a concrete unmet native requirement establishes need |

These findings establish no present need to adopt an AWS backing service.
Unfinished production conformance is work to finish, not by itself a service
selection argument. A future failure can reopen evaluation with this record.

## Authority and evidence

- [ADR 0050: Cloudflare and native storage first](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/decisions/0050-select-cloudflare-and-evaluate-native-storage-first.md)
- [ADR 0051: private runtime trust](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/decisions/0051-trust-private-storage-runtime-with-guarded-writes.md)
- [ADR 0052: paused native replacement and high AWS threshold](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/decisions/0052-evaluate-paused-native-credential-replacement.md)
- [ADR 0056: private observed preflight time](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/decisions/0056-accept-private-workers-observed-preflight-time.md)
- [Native foundation and restore evidence](../research/2026-09-11-d1-foundation-and-installation-read.md)
- [Native secret lifecycle evidence](../research/2026-09-11-native-secret-lifecycle-proof.md)
- [Administrative and batch integration evidence](../research/2026-09-12-native-admin-and-batch-integration.md)
- [Historical AWS secret-store proof](../../probes/secrets/README.md)
