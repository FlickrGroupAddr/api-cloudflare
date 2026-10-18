# Bot-operated temporary-composition metadata collection

Date: 2026-10-18. Ticket #0163. Status: **source preparation; account access and private assembly remain NO-GO**.

Terry chose Bot-operated read-only configuration-metadata collection on this
date. That settles the delivery direction. It does not authorize account
access, credential delivery, provider requests or native input. No such action
was performed to prepare this runbook.

This supplements the [earlier collection proposal](temporary-composition-collection-decision-2026-10-18.md).
Its recommendation to choose owner-mediated export is historical; Terry has now
chosen Bot operation. The [assembly packet](temporary-fixed-origin-composition-2026-10-18.md),
[preservation contract](fixed-origin-preservation-2026-10-17.md) and
[restoration protocol](fixed-origin-restoration-2026-10-17.md) retain their full
requirements. A partial metadata result cannot satisfy or weaken them.

## Disclose the unavailable seams first

Before asking Terry to authorize a concrete collection, disclose all of these:

- Worker settings can contain plain-text binding values. A client projection
  happens after bytes arrive and cannot establish that secret values were
  never read. There is no approved server-side field filter for those responses.
  Settings, version-detail, content and secret endpoints must remain excluded.
- The safe metadata subset cannot reconstruct all eleven baseline sections,
  complete effective edge descendants, current retained-module provenance,
  production full-state consistency, paused gate revisions or writer quiescence.
  Terry excludes production photo/database records and secret values; neither
  may be collected to make the assembly validator pass.
- The collector now has an explicit token-file CLI. The exact private file,
  restrictive ACLs, delivery/consumer/revocation steps and effective grants still
  require independent operator review before account access. The CLI does not
  establish custody, effective permission or genuine human consent.
- Existing isolated database/quota resources, receiver configuration and
  ownership/availability receipts cannot be created by read-only collection.
  A returned temporary-version identity also cannot be invented before upload;
  that assembly/lifecycle ordering gap remains open.

If one of these unavailable seams is necessary for the proposed action's stated
outcome, stop preparing that action as executable. Present the attainable
metadata outcome and the missing engineering or separately scoped proof. Do not
ask for broad approval to fill the gap during the run.

## Exact supported subset

The [projection source](../../scripts/temporary_composition_metadata_projection.py)
owns field validation and derives these GET paths. `A`, `S`, `Z` and `D` below
mean the exact privately supplied account, script, zone and database identities;
they are notation, not discoverable defaults. All requests use
`https://api.cloudflare.com/client/v4`.

| Scope | Fixed path after `/client/v4` | Retained private fields |
| --- | --- | --- |
| `deployments` | `/accounts/A/workers/scripts/S/deployments` | Deployment id/time, percentage strategy, version ids/weights |
| `versions` | `/accounts/A/workers/scripts/S/versions?page=1&per_page=100` | Version id and optional version number |
| `schedules` | `/accounts/A/workers/scripts/S/schedules` | Cron and available creation/modification times |
| `script_subdomain` | `/accounts/A/workers/scripts/S/subdomain` | Enabled and previews-enabled booleans |
| `d1_database` | `/accounts/A/d1/database/D?fields=uuid` | Exact database UUID only |
| `zone_routes` | `/zones/Z/workers/routes` | All returned route ids, patterns and optional script identities |

Only D1's documented `fields=uuid` request supplies provider-side field
selection. Deployment authors/source/annotations and version metadata/annotations
are not retained; they can arrive in the approved response. Unknown fields cause
refusal. Lists remain partial observations even when the response reports no
continuation. Every projection records `baselineComplete: false`.

The Worker role is **Individual Workers Metadata Read-Only**, scoped to each
exact existing Worker. Routes require **Workers Routes Read** for the exact
zone, and the endpoint returns all zone routes; approval must explicitly cover
that response-wide visibility. **D1 Read** is an account permission; no
per-database-only effective grant has been established. Restricting the request
to one database does not narrow that credential grant. Omit D1 collection until
the broader effective read scope receives a separate concrete owner decision.
These permission conclusions require current independent grant verification at
packet review; source validation cannot establish them. See the official
[Worker roles guide](https://developers.cloudflare.com/workers/authorization/workers/),
[routes endpoint](https://developers.cloudflare.com/api/resources/workers/subresources/routes/methods/list/)
and [D1 database endpoint](https://developers.cloudflare.com/api/resources/d1/subresources/database/methods/get/).

## Prepare the exact private request packet

The primary operator prepares one private directory outside Git beneath an
explicitly supplied `private-evidence` root. Do not discover private captures,
credentials or targets. Reuse only the exact historical target map and retained
fixture references separately authorized and independently verified by the
primary operator. Historical relationships do not prove current availability.

The packet must contain a finite request ledger, authority record, grant ledger,
source pins and delivery/custody instructions. Before presenting it for approval:

1. Resolve each used role to one exact account, script, zone or database identity.
   Include the ordinary Worker and only explicitly identified isolated resources.
   Omit unused roles. Supply each request's derived exact URL and the reviewed public
   numeric endpoint address; preserve the provider hostname for TLS verification.
   Do not list accounts/zones/resources to discover a target.
2. Select only the fixed safe GET categories implemented by the collector. Include
   every approved request individually. The versions request fixes page1 with
   per_page100; there is no continuation request or automatic pagination. Record
   each ordinal, exact target, response category and permitted projected fields.
   The source allowlist owns the exact wire fields; no
   arbitrary URL, query, body or field selector is accepted.
3. Record each effective permission, provider permission reference, resource scope,
   expiry, named credential consumer and revoker. Compare actual effective grants
   with this ledger independently. A token label or read-only assertion does not
   prove scope. If provider grants are broader than the exact target set, disclose
   that mismatch and resolve it before asking to use them.
4. Choose absolute UTC start and expiry, at most one hour apart. Fix at most 18
   HTTP GET attempts, at most 60 seconds per request and at most 262144 response-body
   bytes per request. The finite transport additionally allows 65536 wire bytes
   for framing/headers (327680 wire bytes maximum at that body cap). No retry,
   redirect, token-verification call, account discovery
   or extra page may be added after approval. The transport must also enforce its
   bounded streaming/deadline policy; source tests are not live qualification.
5. Name fresh exact private projection-output and journal paths, the independently
   retained canonical plan pin, and the separate consent record bound to that pin.
   Set `outputPath` and `journalPath` to their absolute resolved path strings;
   CLI arguments must match them. Bind the independently reviewed effective
   grant evidence digest in both records' `grantEvidenceSha256` fields.
   Name the person responsible for privacy review, revocation and retention.
   Keep the credential itself out of every packet field.
6. Freeze the reviewed source closure and credential-delivery adapter. Have an
   independent reviewer compare the packet, pin, target map, grant ledger,
   response privacy semantics, endpoint address and operational wrapper against
   the source. An input boolean cannot replace that review.

An 18-request ceiling does not establish inventory completeness. If a response
reports more pages than the approved ledger contains, mark the collection
incomplete and stop; do not infer that unvisited pages are empty. GET alone also
does not prove a response excludes secrets. Keep unsafe endpoints out of the
ledger before any request is dispatched.

## Obtain concrete action authority and deliver credentials

After the unavailable seams and final reviewed packet are visible, the primary
operator presents Terry with the exact proposed outcome, targets, requests,
permissions, response field categories, timing/byte/request limits, credential
consumer/revoker, private paths and failure behavior. Ask for approval of that
single pinned scope only. The direction decision recorded above is not that
approval. No credential read may occur while this step is pending.

The [collector source](../../scripts/temporary_composition_metadata_collector.py)
exposes `collect(plan, expected_plan_sha256, consent, credential, output_path,
journal_path, *, now, clock, transport)`. Its module docstring owns the closed
plan and consent fields; `source_sha256()` supplies the seven-file transport/
projection source closure and `digest(value)` supplies the canonical plan pin.
The plan/consent bind the exact credential through `credentialBinding`, its
SHA2-256 digest; the actual credential remains absent from the packet. Retain
that digest privately too. Source hashes taken from the current checkout must
be compared with the separately reviewed retained source manifest.

The CLI reads the credential from the explicitly supplied `--token-file`. Before
execution, independently verify the exact file's private custody and restrictive
Windows ACLs, limiting access to Terry and the reviewed collector identity plus
necessary operating-system principals. Keep it outside Git and shared/synced
locations. Deliver the token outside chat, command arguments, screenshots,
environment dumps and logs. The file contains only 16..4096 ASCII token characters
from `[A-Za-z0-9_.-]`, with no newline or BOM. Do not use a command that prints or
echoes its value. Record its exact private path and finite retention/disposal
procedure in the approved custody record.

The CLI reads the bounded plan and consent first. It does not resolve, stat or
open the token file until the plan/pin/source/consent/window/scope checks pass,
the exact output/journal paths match the plan, and fresh exclusive sinks exist.
It then reads at most 4097 bytes to enforce the 4096-byte token bound and compares
the token's SHA2-256 digest with `credentialBinding`. No token verification,
discovery, refresh or revocation request follows from that comparison.

Terry provisions the reviewed finite read grants and a credential expiry no
later than the approved deadline. The named consumer receives the credential
only through the reviewed channel. Grant provisioning and revocation are owner
operations outside this collector's GET budget; the collector performs neither
and must not silently gain grant-management privileges. Do not probe token
validity with a new unbudgeted provider request.

## Execute and deliver the attainable evidence

Only after exact consent and independently verified credential custody/grants,
the primary operator may invoke the following command once from the API
repository using frozen dependencies. Replace every path and pin with the exact
reviewed private packet values; placeholders are not permission to discover
them. This command is documented for later execution and was not run here.

```console
uv run --frozen python -m scripts.temporary_composition_metadata_collector --plan <exact-private-plan-json> --expected-plan-sha256 <independently-retained-plan-pin> --consent <exact-private-consent-json> --token-file <exact-private-token-file> --output <plan-outputPath> --journal <plan-journalPath>
```

Exit0 prints only `collection_complete_partial_metadata_only`; exit1 prints only
`collection_refused_or_aborted_no_replay`. Do not interpret either stdout string
as a complete baseline or provider qualification. Inspect only the authorized
private outputs and sanitized disposition; do not enable raw-response logging.

The collector must refuse malformed, expired, out-of-scope or unsafe requests
before credential access. Commit each attempt to the single-use journal before
dispatch. Stop on the first deadline, budget, response-shape, incomplete-page,
transport or scope failure. Never replay an uncertain attempt or resume by
removing/replacing the journal. A new attempt needs a newly reviewed scope and
consent; it is not a retry of the approved run.

Provider JSON is projected through the fixed field/type allowlist. Do not retain
or print raw response bodies, bearer headers, provider error text, secret values
or private photo records. Treat projected identifiers, version metadata,
schedules, route patterns and database metadata as private too. Unknown or
malformed values yield closed failure categories, never their original values.
Projection does not prove that excluded bytes never arrived: that boundary must
come from the approved endpoint response semantics before dispatch.

At success, stop or expiry:

1. Deliver the private projection and journal to the named custodian at the exact
   approved paths, with actual file digests retained independently. Record whether
   collection was complete or stopped and preserve every negative disposition.
   An aborted run can leave an empty output tombstone and an aborted journal;
   it supplies no successful projection receipt. Do not replace it with raw bodies.
2. Have the named revoker revoke the credential and independently retain a
   sanitized revocation receipt. If revocation is unconfirmed, report that fact
   and Terry's required action; do not run an extra verification request.
3. Independently review target/provenance/freshness, grants, source pins, request
   census and privacy before producing a public receipt. Public output may contain
   closed status categories, counts, digests and sanitized retrieval instructions.
   It must exclude identities, paths containing private names, response values,
   routes, schedules, bearer material and account/grant details.
4. Retain private evidence for review and follow-on disposition. Terry explicitly
   chooses later retention/deletion. Never automatically delete original fixtures,
   rollback evidence, production evidence or the single-use journal.

No deployment, upload, rollback, synthetic initialization, receiver invocation,
D1 query, production record read, resource mutation or native action is part of
this collection. No transport success authorizes one of those follow-on actions.

## Map evidence without fabricating an assembly

Keep the metadata projection separate from the existing
[offline input preparer](../../scripts/prepare_temporary_composition_collection.py).
The preparer validates supplied target/baseline/additions/scope/fixture inputs;
it does not fetch them, authenticate provenance or establish provider truth.
Its full-baseline requirements remain intact.

For every unavailable input, preserve the preparer's unavailable representation
(`available: false`, `value: null`, `provenance: null`). Do not manufacture empty
binding/configuration objects, infer absent resources from missing pages, copy
historical observations into a current capture or label projection completeness
as baseline completeness. Metadata can support individually reviewed identity
and deployment facts only within its actual observation and source limits.

Private assembly still requires complete eleven-section configuration and
component provenance; consistent production-state and both paused gate proofs;
writer accounting; independently established isolated-resource/receiver receipts;
retained fixture custody and current version availability; exact finite run and
capability scope; and a resolved temporary-version identity sequence. The
metadata-only plan neither creates those inputs nor grants authority to obtain
them by reading excluded records. Five-phase route conformance, provider restore
and changed-secret behavior, helper/client qualification and finite native
feasibility remain separate gates under the assembly packet.

This runbook records the chosen delivery direction and a bounded operational
handoff. Source acceptance, final private packet review, credential-custody
readiness and exact account-access consent must precede any collection. Keep
provider/native execution, private materialization, activation and promotion
assertions false until their own evidence and authority exist.
