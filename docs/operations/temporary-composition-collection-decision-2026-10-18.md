# Temporary composition: bounded read-only collection decision

Date: 2026-10-18. Ticket #0163. Status: **proposed collection scope; actual private inputs unavailable; NO-GO for provider/native execution**.

The next reviewable action is an owner-mediated, read-only export of the exact
configuration and provenance identified below. This document grants no account
access. No provider collection, credential inspection, private assembly or provider
request occurred in preparing it. A successful offline receipt cannot establish
that supplied inputs describe current provider state.

The [assembled offline packet](temporary-fixed-origin-composition-2026-10-18.md)
owns assembly and lifecycle behavior. The
[preservation contract](fixed-origin-preservation-2026-10-17.md) and
[restoration protocol](fixed-origin-restoration-2026-10-17.md) own comparison and
cleanup requirements; this collection proposal does not amend them. Keep
provider restoration, production preservation, deployment, native qualification,
activation and release assertions false. The strict helper investigation remains
separate from helper adoption or a qualified effective client path.

The parent subsequently prepared a
[sanitized historical target-map receipt](../evidence/temporary-composition-target-metadata-2026-10-18.json)
from selected retained metadata. Retrieve the exact map privately using the
receipt's `privateRetrieval` procedure beneath the operator's existing
`private-evidence` root; verify its independently retained SHA2-256 pin before
use. Supplemental independent comparison passed for those historical identity
relationships and selected source-byte provenance only. Exact identities remain
private. This is not a current or full baseline, collection authority, retained
availability proof or private assembly receipt; actual credential/provider/native
actions remain zero.

## Exact private data and target roles

The operator must privately resolve every role to an exact identity before a
request is approved. Public role names below are deliberately not usable target
identities. Do not discover an account or resource by browsing until one fits.
The first actionable export is metadata-only unless the production consistency
and writer-quiescence seams receive separate engineering review. Complete
production-state evidence remains a requirement, not a claim that a supported
secret-free remote collector exists. If that proof would expose credentials or
photo data, keep `productionState` unavailable and return for an explicit proof
and privacy design; never strip fields and label the result a full-state proof.

| Role / data | Exact content required privately | Source / boundary |
| --- | --- | --- |
| Ordinary Worker | Account identity, exact script identity, current deployment weights, exact original retained version and its availability, module digest | Authorized current provider observation bound to observation time; historical capture is not current availability |
| Full baseline | All eleven explicit sections: `bindings`, `resources`, `runtime`, `assets`, `classLifecycle`, `secretReferences`, `attachment`, `routes`, `domains`, `effectiveEdge`, `capabilities` | Complete independently sourced settings, including descendant rulesets/Page Rules and effective relationships; no omitted field described as inherited |
| Paused production state | Exact production database identity; complete consistent schema/data evidence; both durable deployment and exact user gate rows with unchanged pinned revisions; background-writer quiescence/accounting | Independently reviewed evidence under preservation contract; flags, row counts and an arbitrary nonempty object are insufficient |
| Existing original fixture | Operator-supplied authorized private path and independent capture-index/module pins, immutable retained-version relationship | Reuse verified original bytes and rollback; no recapture, rebuild or replacement candidate |
| Synthetic database / quota database | Two exact separately owned isolated resource identities and four noncolliding binding names | Existing acknowledged identity/ownership evidence, or an explicit unavailable disposition; this read-only scope cannot create them |
| Receiver | Same-account exact isolated Worker identity, target, complete eleven-section configuration, quota/capability-only mapping and reviewed source/module provenance | Complete receiver configuration; no production route/domain, assets, classes, secret, tail or edge relationship |
| Finite attempt scope | Exact run identity, temporary version identity, canary, four binding-role mappings and exact start/expiry | Reviewed private additions/scope inputs; a returned version identity cannot be guessed before upload; 600000-ms inner lifetime, existing 1200000-ms outer lifetime remain unchanged |

The authoritative input shapes remain
[`validate_baseline` / `build_delta`](../../scripts/temporary_composition_delta.py)
and [`validate_scope` / builder](../../scripts/build_temporary_composition.py).
The builder computes the temporary and receiver module digests; do not invent
those digests in the additions input. Full input provenance is external to those
validators. Empty dictionaries/lists are legitimate only with explicit source
evidence establishing emptiness, never as missing-data defaults.

## Effective minimal read authority

Recommended route: Terry exports the reviewed exact evidence into a private
local handoff directory. Delegated provider grants and delegated credential reads
are **zero**. The offline preparer receives only explicitly named files and the
separately retained request digest. Terry's owner-mediated export still needs an
explicit target list and the finite collection scope; this document is not its
approval.

If Terry instead chooses a delegated collector, first review a private grant
ledger containing every exact target, effective read action, independently
sourced provider permission reference, granted resource scope and expiry.
Required read roles are limited to:

- Exact Worker settings, versions/deployment metadata and original retained
  version availability; no upload, deployment, delete or rollback action.
- Exact resource/binding/lifecycle and secret-reference **identity metadata**;
  no secret-value reads, secret changes or broad account enumeration.
- Exact relevant zone/account configuration and effective edge descendants;
  no DNS, route, domain, ruleset or Page Rule mutation.
- Exact isolated-resource/receiver configuration and ownership metadata;
  no creation, initialization, receiver invocation or synthetic admission.
- The specifically scoped production consistency/gate/quiescence evidence;
  no data repair, migration, pause change, write query or background-worker
  operation. Review any SQL transport by its effective read behavior; a POST
  transport alone neither proves nor disproves read-only authority.

These are required effects, not verified Cloudflare permission names. No current
provider permission catalog or effective token scope was inspected here. If the
provider cannot restrict a grant to those effects/targets, use owner-mediated
export or return for a separate, explicit broader-scope decision; never silently
accept account-wide access. A token label or supplied permission reference does
not establish effective scope. No #0157 isolated publisher access or disposal
condition supplies authority for this production-related collection.

## Finite collection and custody proposal

Proposed upper bounds are one approved collection identity, one continuous
window of at most one hour, and at most 18 logical read operations in the reviewed
collection plan. Approval must specify an absolute UTC start and deadline before
any provider access. Stop at the first deadline/budget/scope failure, missing
page, inconsistent observation or unknown actor/target; retain an incomplete
receipt. No automatic retry, budget extension, resource creation or live
qualification follows an incomplete result.

The plan must account for the complete effective inventory, including pagination
and descendants. Eighteen operations is a ceiling, not evidence that eighteen
HTTP requests can capture the account. If a logical collection item needs more
calls than the reviewed request ledger allows, stop and obtain a revised bounded
ledger; never truncate, treat an unvisited page as empty or promote partial data.
The current preparer validates a logical census only; it does not enforce
network deadlines, transfer/allocation limits or a provider request budget.
A separately reviewed transport ledger must bound those before any delegated
network collection. Its input file is capped at 4,000,000 bytes, with existing
configuration depth/type bounds; exceeding a bound refuses rather than truncates.
The collection window is unrelated to the later ten/twenty-minute attempt
windows and does not make an observation fresh enough for execution preflight.

Keep evidence outside Git beneath an explicitly supplied private directory.
Record source reference, collector identity/role, observed UTC time, exact target,
completeness/failure disposition and SHA2-256 digest for each supplied item.
The complete source evidence stays private; public output contains only closed
status categories, counts, digests and sanitized retrieval procedures. Never put
account/resource values, secret values, bearer headers, response bodies or photo
metadata in public docs, logs, receipts or agent messages.

For the recommended export route there is no credential to deliver or revoke.
For any separately approved collector route, Terry alone chooses and privately
records the credential delivery mechanism, named consumer and revoker. Deliver
outside chat, Git, command arguments, screenshots, environment dumps and logs;
expose it only to the reviewed collector. Use short expiry no later than the
approved deadline. Revoke at completion, stop or expiry and record an independent
revocation receipt without recording the credential. Failure to confirm
revocation remains unconfirmed and requires Terry's action; do not probe it by
making an extra unbudgeted request. The offline preparer has no credential reader.

Terry retains private source evidence until independent provenance review and
follow-on disposition; he then explicitly decides private retention/deletion.
This proposal authorizes no automatic deletion of original fixtures, rollback,
production state or private evidence. Sanitized receipts may be committed after
privacy review. No real-photo collection is within this scope.

## Offline preparation interface and interpretation

[`scripts.prepare_temporary_composition_collection`](../../scripts/prepare_temporary_composition_collection.py)
accepts an explicitly supplied collection request and an independently retained
request pin. From the API repository, with existing frozen dependencies:

```console
uv run --frozen python -m scripts.prepare_temporary_composition_collection --request <private-request-json> --expected-request-sha256 <independently-retained-request-pin> --receipt <fresh-sanitized-receipt> --plan-output <fresh-private-evidence-plan-json>
```

The request is `temporary_composition_collection_request`, schema version1,
with exact `authority` and `inputs` objects. `authority` binds a decision reference,
approved boolean, absolute UTC `startsAt`/`expiresAt`, credential delivery and
revocation method references, explicit false privacy flags and exact read-grant
entries. Each grant names `readId`, exact `target`, `effect: read` and independently
sourced `permissionRef`. For owner export those references record the owner's
export authority; they do not mean a delegated credential exists.

All five inputs (`target`, `baseline`, `additions`, `scope`, `fixture`) explicitly
carry `available`, `value` and `provenance`. Missing inputs use exactly
`available: false`, `value: null`, `provenance: null`. Provenance binds source
reference/type, capture time, exact target, canonical content digest,
independent-source assertion, completeness and component references. The full
baseline needs fourteen component records: eleven configuration sections plus
production state, deployment weights and retained version. The source owns
exact field names; this document does not introduce a parallel schema.

The CLI writes a sanitized blocked receipt and exits2 when required values,
approval or active window are absent. It emits a private exact-target logical
plan only after consistent complete inputs; plan output must be outside the
repository beneath `private-evidence`. All output paths must be fresh. A malformed
request/pin refuses with no successful receipt. The expected pin is the digest of
the preparer's canonical request encoding, retained independently; neither that
pin nor `independentlySourced: true` authenticates an observation.

This interface has no provider/credential reader and does not fetch inputs or
create a baseline. Its fixture value is a pinned descriptor, not an inspection
or availability receipt for private bytes. A reviewable plan leaves
`providerExecuted`, `nativeExecuted`, `activationAuthorized` and
`materializationReady` false. It is a consistency preflight, not authorization,
collection execution, a private assembly receipt or actual provenance review.

## Next explicit operator input

Terry's next decision is whether to use the bounded owner-mediated export above.
For that decision to become executable, supply the exact private role-to-target
map, approved absolute UTC window, finite read ledger, delivery directory and
collector/revoker identities (or explicit no-credential export disposition).
Then supply all five independently sourced input categories: target, baseline,
additions, scope and exact retained fixture reference, each with provenance.
Keep unavailable categories unavailable; do not ask the preparer to fill them.

After collection, independent review must establish provenance, completeness,
freshness, effective grants, retained-target availability and paused full-state
proof before the builder may consume the inputs. Then bind final Worker,
receiver, configuration/delta/restore and manifest digests with an independent
manifest pin. Source tests and supplied-envelope equality alone close none of
those gates. Five-phase exact-route conformance, client/helper qualification,
real restoration/changed-secret behavior, finite native program feasibility and
separate live action authority remain open under the assembled offline packet.

This is a concrete collection decision handoff. It is not approval to deploy,
initialize a client, adopt a helper, inspect credentials or execute the attempt.
