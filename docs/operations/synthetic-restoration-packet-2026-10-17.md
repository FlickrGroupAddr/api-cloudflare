# Synthetic restoration Case A and Case B packets

Date: 2026-10-17. Ticket #0150. Status: reviewable offline preparation;
**no provider experiment, credential access or hosted restoration proof**.

`scripts/synthetic_restoration_packet.py` builds a closed packet and executes
its finite in-memory restoration model with a SQLite attempt journal. It has
no HTTP implementation, credential reader, provider SDK import, dynamic adapter
loader or native application interaction. The model makes its simulated provider
outcome explicit; its favorable result is not empirical provider behavior.
The [#0043 negative restoration verdict](fixed-origin-restoration-2026-10-17.md)
and [#0045 NO-GO disposition](fixed-origin-authorization-disposition-2026-10-17.md)
remain controlling. Each future provider experiment needs its own exact authority
checkpoint; this packet grants none.

## Captured type coverage and provenance

Only a sanitized metadata projection of `/result/resources/bindings` was read
for this task. It reports 26 bindings, five types and zero unclassified bindings.
The pinned `active_version_0.json` source has SHA2-256
`8d41009f984b5292e2e5ae6a89cdd2529d01b7aac5a7e8f8e0ad1d7e375ed097`;
the original #0036 integrity-index SHA2-256 is
`ea43ba41d7bb5c6ae7fae569f77a8d126cfcfb7a0a550e5f92856c771b9f8202`.
The parent produced the projection without names, resource IDs, reference fields
or values. The source constants preserve the counts and provenance without
opening raw captures or credentials.

| Captured binding type | Count | Role in this packet |
| --- | ---: | --- |
| `assets` | 1 | Synthetic asset identity preserved |
| `d1` | 1 | Synthetic schema and complete finite rows preserved |
| `durable_object_namespace` | 1 | Synthetic namespace identity preserved |
| `plain_text` | 14 | Synthetic capability/runtime configuration preserved |
| `secrets_store_secret` | 9 | Sole captured secret type; independent A and B cases |

There is no captured `secret_text` binding. A normal Worker secret example does
not establish the captured Secrets Store behavior. Each case uses one fresh
synthetic store secret as a representative of the captured **type**, not nine
production secrets or their names. This is type coverage, not a replay of every
production binding. Production configuration and all nine reference identities
still require the separate #0043 exact private readback.

## Closed resources, operations and ownership

One lowercase 32-hex run identity owns exactly two independent cases. For case
`a` or `b`, the prefix is `fga-rst-{run}-{case}`. Both cases allocate exactly:

| Resource label | Exact synthetic identity |
| --- | --- |
| Worker | `{prefix}` |
| D1 | `{prefix}-db` |
| Durable Object namespace | `{prefix}-do` |
| Asset bundle | `{prefix}-assets` |
| Secrets Store secret | `{prefix}-secret` |
| Secrets Store | `{prefix}-store` |

The baseline and temporary version labels are `{prefix}-retained` and
`{prefix}-temporary`. These are deliberately synthetic model labels, not valid
claims about provider-issued UUIDs. The plan never selects latest, rebuilds the
restoration target or chooses a different version after failure. A future real
adapter must bind acknowledged account/resource/version IDs, exact artifacts,
class lifecycle and upload manifests into a new private packet digest before
review/authority. It must translate asset/namespace provisioning and retirement
into reviewed provider operations; this script does not implement those APIs.
No production resource, route, hostname, DNS record, OAuth/Flickr identity,
Actions secret, receiver or fixed-origin qualification resource belongs here.

Owner is exactly `bot`, with one primary operator. Every resource name must be
absent before any simulated create. The in-memory model uses only acknowledged
resource identities and deletes only those exact identities. The finite sequence
per case is six absence checks, six creates, fixture initialization, baseline
upload/deployment/readback, temporary upload/deployment/readback, one nonforced
retained-target restore, restoration readback, and up to six exact deletions.
Case B adds exactly one synthetic secret change and its observation. Thus Case A
has 27 ordinary operations; Case B has 29. Each case has at most two additional
read-only reconciliation observations, for absolute caps of 29 and 31. Each
operation is attempted at most once. Synthetic Worker observations are bounded
by four per case. These are model-operation caps; they do not represent an
already authorized provider-request budget or a billing/unsolicited-traffic cap.

The work window is 600,000 ms from the pinned start; the outer lifecycle is
1,200,000 ms, leaving ten minutes for cleanup. New work, including restore,
refuses at the work deadline. Neither deadline establishes restoration or
deletion. Exact owned cleanup and the two reconciliation reads remain available
after expiry, with their unchanged count limits. There is no background work,
external outbound destination or enabled intake/dispatch/scheduled capability.
Both deployment and user fixture gates remain false at revisions 7 and 11.

## Case A: exact synthetic preservation

1. Create this case's six synthetic resources and paused fixture; pin its exact
   retained baseline version, module digest, bindings/configuration, asset and
   namespace identities, finite schema/rows, marker match and both gate revisions.
2. Upload/deploy the declared temporary version without resource, secret,
   schema, lifecycle or gate changes. Pin its active version and weight100 map.
3. Commit the restore attempt latch before one simulated request with
   `strategy: percentage`, `force: false` and exactly the retained baseline at
   percentage100. An acknowledgment alone cannot pass the case.
4. Compare complete before/after snapshots using canonical JSON equality.
   Code/version/weights, resources, bindings, runtime/capabilities, full fixture
   data, secret marker and both gate values/revisions must match. Row counts
   alone cannot pass. The exact local result is `preserved`.
5. Only that successful preservation permits the six exact acknowledged
   synthetic deletions. A pending/unknown deletion leaves `cleanup_unconfirmed`.
   The combined offline run then stops before starting B and names B in its
   `notAttemptedCases` receipt field.

## Case B: changed-secret refusal or measured drift

The baseline and temporary setup use separate resources from A. After deploying
the temporary version, change only this case's synthetic secret and require a
measured false baseline-match boolean. Neither the source nor receipt contains
an actual secret or secret-derived digest. Attempt the same one nonforced
retained-target restore once, and classify the complete readback:

| Observation | Exact local classification and meaning |
| --- | --- |
| Refusal; readback equals complete changed temporary state | `refusal_accounted` |
| Refusal; active/configuration/data differs | `refusal_with_drift` |
| Success; original baseline fully observed | `accepted_baseline_observed`; measured observation, not a general historical-secret guarantee |
| Success; baseline code/configuration/data but changed marker persists | `accepted_changed_value_drift` |
| Success; any other resource/configuration/data/gate drift | `accepted_configuration_or_data_drift` |
| Unknown acknowledgment/outcome | `unknown_cleanup_unconfirmed`; two read-only observations, no retry |

Every B result retains `cleanup_unconfirmed`. In particular, an accounted
refusal leaves the temporary version active and its synthetic resources retained
for investigation; it is not an A preservation pass. A future authorized
provider case must identify the precise paused surviving state and return it to
independent review before any further mutation or retirement. It may not force,
repair, rotate back, create replacement resources or relabel drift as success.

## Journal, failure and custody

`Journal` binds one packet digest to SQLite and acquires an exclusive sibling
`.owner` marker. It commits each operation as pending before the simulated
effect and requires its acknowledgment before the next ordinary operation.
Reopening the journal cannot replay completed/pending mutations. Competing
operators refuse. A crash marker is never automatically considered stale or
removed by another invocation. Cancellation/expiry/unknown outcome requires
investigation, retains pending latches and cannot widen the packet. The only
post-ambiguity seam is two finite read-only reconciliation entries; it cannot
acknowledge or replay the ambiguous mutation.

The CLI requires a fresh destination outside the repository beneath a
`private-evidence` directory. It writes `packet.json`, `journal.sqlite3` and
`receipt.json`; SQLite sidecars and the owner marker share that custody. Retain
these together under the primary operator's private evidence boundary. The CLI
returns a closed failure receipt without raw exception/path diagnostics. No
credentials are imported, generated, queried for presence or stored. Future
provider IDs, raw metadata and request acknowledgments would remain private;
public evidence may contain only digests, booleans, bounded counts, closed
classifications and sanitized retrieval references.

Run with the repository's pinned uv0.12.5/Python3.14.7 tooling:

```console
uv run --frozen python scripts/synthetic_restoration_packet.py <32-lower-hex-run> <start-ms> <fresh-private-evidence-output> --synthetic-outcome refused
uv run --frozen python -m unittest tests.test_synthetic_restoration_packet
```

The alternative synthetic outcomes `changed_value`, `baseline`, `unknown` and
`resource_drift` deliberately exercise classifications. They do not assert what
the provider would do. All receipts keep `providerRestorationVerified`,
`changedSecretSemanticsVerified`, `productionStateVerified` and
`deploymentAllowed` false. The next owner is Bot's independent packet reviewer,
then the primary operator for any separately scoped exact authority checkpoint.

## Executed offline verification

On 2026-10-17, the pinned uv0.12.5/Python3.14.7 run passed all 16 tests in
`tests/test_synthetic_restoration_packet.py`. Ruff0.16.3 lint/format checks passed;
Pyright1.1.411 reported zero errors for the source and tests. The suite covers
closed packet mutations, every snapshot dimension, strict JSON scalar types,
all B classifications, deadlines, ordering/acknowledgments, exclusive ownership,
pending/reopened attempts, finite reconciliation and unknown deletion.

The CLI also ran against a fresh private local journal. Its packet SHA2-256 was
`3c5fe131dacfba5eb6828e9791000aa230a3fe4608cda5b3814e30bdb24078a4`.
Case A reported `preserved` after27 model operations and confirmed only offline
cleanup; Case B reported `refusal_accounted` after23 model operations and retained
`cleanup_unconfirmed`. All four hosted-verification/permission fields stayed
false. Private packet/journal/receipt retrieval is recorded in the batch's
`private-evidence/0150-final-cli` directory outside the repository. No provider
request, private source/value read or native input occurred.

## Current primary-source evidence

Official documentation was checked on 2026-10-17. Cloudflare documents selecting
a prior Worker version at100% while connected resources persist, with resource
and class-lifecycle compatibility restrictions. This is a reason to compare
resources and data separately, not proof this capture restores.
([Rollback documentation](https://developers.cloudflare.com/workers/versions-and-deployments/rollbacks/))

The deployment API documents percentage/version selection and a force override
for otherwise blocked changed-secret rollback. This packet pins force=false and
has no forced fallback; a public API description does not establish the outcome
for the captured Secrets Store type.
([Deployment API](https://developers.cloudflare.com/api/resources/workers/subresources/scripts/subresources/deployments/methods/create/))

Secrets Store Workers bindings identify a store and secret name and expose an
asynchronous retrieval method. This supports treating the captured type as a
separate mutable-reference experiment. It does not promise that deployment
rollback restores an earlier secret value.
([Workers integration](https://developers.cloudflare.com/secrets-store/integrations/workers/))
