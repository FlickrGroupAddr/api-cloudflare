# Controlled-trial D1 observation adapter

The bounded adapter is `scripts/controlled_trial_observations.py`. This is the
#0073 implementation handoff, not a production measurement or permission to run
one. It reuses the mature `controlled_trial_pause.request` provider transport
(official account/database D1 query endpoint, no redirects, bounded response,
no automatic retry). No existing operator supplied a complete all-user census;
the pause operator only observes its own two gates. This adapter adds fixed
SELECT operations without expanding that operator's mutation surface.

The only operations are `users`, `gates`, `partitions`, `intents`, `attempts`,
`blocks`, `counts`, and `pair`. There is no SQL, projection, table, endpoint,
destination URL, or mutation option in the private plan. Tokens are never plan
fields or command-line values. The provider token remains in memory after
reading a private plain token file; no native Flickr credential bundle is read.
The CLI prints only constructed count/boolean projections or a fixed failure
state. Exception details and provider bodies never reach stdout.

## Private plan template

Save this outside the public checkout in the approved private operator inventory,
with its normal restricted filesystem access. Replace the illustrative values
from the reviewed production identity and existing owner-selected pair; do not
request another pair merely to prepare this adapter.

```json
{
  "schemaVersion": 1,
  "accountId": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "databaseId": "11111111-1111-4111-8111-111111111111",
  "fgaUserId": "approved-owner",
  "photoId": "approved-photo",
  "groupId": "approved-group"
}
```

The default is offline validation:

```console
uv tool run --from uv==0.12.5 uv run --frozen python -m scripts.controlled_trial_observations --plan PRIVATE_PLAN
```

## Single bounded production procedure, after separate authorization

1. Satisfy the first-controlled-group-addition runbook's production observation
   authorization and stopped-writer barrier. Independently identify the deployed
   Worker/version, bindings, disabled intake/dispatch flags, and absent in-flight
   invocations/other writers using the reviewed configuration inventory procedure.
   D1 gate facts alone do not observe Worker flags or prove a stopped runtime.
   Keep the existing writer/configuration freeze in effect through both sweeps.
2. Review the exact private plan against that inventory, the frozen adapter
   revision, migration head/digest, and the approved selected pair. Record these
   references privately; account/database identity is not learned from tokens.
3. Run exactly one observation command with the dedicated provider read
   credential and a fresh private output filename outside the repository:

   ```console
   uv tool run --from uv==0.12.5 uv run --frozen python -m scripts.controlled_trial_observations --plan PRIVATE_PLAN --observe --token-file PRIVATE_TOKEN_FILE --private-output PRIVATE_INVENTORY
   ```

4. Require exit zero and a complete private JSON record. A refusal, empty file,
   interrupted process, provider size refusal, malformed page, changed sweep,
   count mismatch or page-budget exhaustion is a failed observation. Keep the
   deployment stopped; do not use partial rows, raise limits ad hoc, or replay
   a write. A new observation after fixing the cause needs a new filename.
5. Inspect all private gate revisions, every user/partition and active FIFO
   member. Sort active members by partition and numeric `ordinal` to identify
   each head and every successor. Account for future `due_us`, `probe_due_us`
   and `retry_due_us` without dropping delayed/throttled work. Inventory includes
   partitions with no active member and retained leases, even expired leases.
   Join each attempt's `intent_id` to its intent and partition; inspect every
   unresolved attempt, with/without dispatch, and retained lease/generation to
   account for abandoned work. No clock-based filter hides it. A trial requires
   the complete empty-active-queue decision and all other runbook gates; the CLI
   does not make an activation decision.
6. Read private `pair` facts: binding ownership and link revision must agree
   with the linked owner, verified write/delete native reference and available
   lifecycle state; blocks and retained intents are exact photo/group matches.
   Inspect that pair's intents and joined attempts/membership/preflight/dispatch/
   resolution facts from the inventories. A permanent block or unresolved
   dispatch never becomes permission to replay. Any failed eligibility check
   stops this procedure for review.
   The private `binding_metadata`, `link_metadata`, `native_metadata` and
   `connection_metadata` JSON projections retain exact identities, binding
   verification revision/time, link revision, native active generation and
   lifecycle authority. Compare these to the approved private identity record;
   their equality across both sweeps is required even if eligibility counts
   remain unchanged and no membership cache exists. These projections never
   enter the public receipt.
7. Retain private plan, complete inventories, UTC observation interval, adapter
   SHA2-256, configuration/migration provenance and observation authorization.
   Share only the constructed stdout receipt and private evidence reference.
   The receipt states `observed_only_not_authorization`; preserve stopped flags.

Each inventory uses binary ascending keyset continuation, a fixed 100-row page,
and a 10,000-page ceiling per inventory per sweep. Even an exact page multiple
requires the final empty page. Counts before/after and two identical complete
sweeps must agree; all gates, users, partitions, intents, attempts and blocks
are included. Attempts LEFT JOIN immutable membership/preflight/dispatch/result
evidence. There is no user or due-time filter. Changes that preserve counts
still fail when projected facts differ. These checks detect observed drift;
they cannot prove a serializable snapshot across separate provider requests or
detect a writer that changes and restores a value between reads. The external
stopped-writer barrier is therefore mandatory, not inferred from equal sweeps.

Membership observations are a replaceable **advisory cache**. The pair query
checks validity plus binding/link/native-generation agreement and reports the
observation time and cached target membership. A valid absent cache row is not
a fresh exact-photo membership read, group moderation preflight, or authority
to add. The normal worker must still perform fresh Flickr membership then fresh
group getInfo immediately before each authorized add. This procedure performs
no Flickr request and cannot fill that evidence gap.

Authenticated application status GETs perform durable admission/audit
bookkeeping and are user-scoped. They are not substitutes for these SELECT-only
D1 observations or the deployment-wide census.

## Local verification and remaining boundary

`tests/test_controlled_trial_observations.py` applies every current migration to
SQLite and exercises 103 users/partitions, 206 delayed FIFO members and abandoned
attempts, retained expired leases, multiple continuation pages, query-only/no-row-
write execution, short-page truncation, repeated cursors, same-count drift,
bounded exhaustion, strict operations/parameters, generation mismatch and public
redaction. Pair-authority regression checks retain private metadata and refuse
same-count binding-verification/native-generation changes with no membership
cache. Run with the pinned uv command and unittest module of that name.

Local verification does not qualify hosted provider behavior or record a fresh
production baseline. Independent Sol / High review, parent integration and the
separate production observation authorization/execution remain required.
