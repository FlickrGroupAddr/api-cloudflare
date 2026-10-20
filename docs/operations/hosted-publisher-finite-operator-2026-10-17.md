# Finite hosted publisher operator — 2026-10-17

Status: **Offline engineering; hosted execution remains NO-GO.** This procedure
describes the #0155 operator preparation for the immutable #0121 synthetic
publisher candidate. It records no account access, credential inspection,
resource creation, endpoint request, deployment or owner consent. #0134 owns
the later exact action decision; #0122 owns any authorized hosted execution.

The [qualification packet](hosted-publisher-qualification-packet-2026-10-17.md)
and [action decision](hosted-publisher-action-decision-2026-10-17.md) retain their
accepted-authority and production exclusions. This document supplies neither an
architecture amendment nor production Album scheduling, Flickr transport,
credential retrieval, native operation or activation authority.

## Candidate identity and separate operator closure

The candidate source commit is
`aca532af6d570125c5d8bbcbd6ac1b4a10ae74f7`. Its 113-file source-artifact digest is
`718b3dd7e1ec669c7e043f4c3a37142ceaad42a5bd3bcbc0639868a2b1e5aed1`;
the optimized Worker digest is
`b2241f88c94ec6561b2a902a5561bf9f63459e420fbd111861db1636feb2a26f`
(652,967 bytes). These are packet identities, not a new hash verification by
this procedure. The action decision carries the other original pins.

Keep the original closure immutable. Retain operator/client/provider sources,
their final reviewed digests, migration 0001–0026 byte identities and the exact
deployment overlay as a separate closure. The parent must pin its final bytes
after integration and independent review. An unset digest or an unreviewed edit
keeps execution NO-GO; a previous source/bundle receipt cannot attest a changed
overlay, operator or client.

## Private action sheet and consent sequence

Do not put real values into an example or tracked configuration. The private
action sheet must contain all of the following before a live operator is used:

- The owner decision, authorized operator, account boundary, exact source,
  optimized module, operator/client/provider and migration pins; the reviewed
  endpoint mechanism and configuration projection.
- Four unique intended Worker/D1 names, one for each of `happy`, `create_lost`,
  `attachment_lost`, `title_lost`; no existing database, shared resource,
  production binding, name reuse or cross-case reuse.
- Exact start, dispatch expiry, lifecycle/cleanup deadlines, cumulative budgets,
  stop owner, cleanup owner, escalation contact and provider-token revocation
  owner. These are separate responsibilities even when Terry holds each role.
- Fresh run and probe-access identities per case; the private delivery channel
  and token grant/expiry/revocation record. Probe secret values stay outside the
  action sheet's sanitized receipt projection.
- Consent for staged creation of only the intended names. Returned actual D1
  UUIDs and deployed Worker versions are unknown before creation; bind them in
  the private ledger after exact response/identity verification and before
  migration, enablement or dispatch. Do not invent IDs in advance.
- A separate cleanup-only continuation scope: exact known resources, permitted
  status/disable/delete actions, cumulative residual budget and final deadline.
  Dispatch expiry never grants indefinite cleanup authority.

The later decision must approve the concrete reviewed inputs and actions.
Approval of a scope in principle is insufficient. New source, endpoint,
overlay, identity, tool or schedule drift requires stopping and comparing the
new facts against that decision. Neither Completed #0121 nor completed offline
#0155 preparation grants live permission.

## Concrete source interfaces and limits

`scripts/hosted_publisher_operator_plan.py` parses closed, duplicate-free JSON
through `load_plan(raw)` into `OperatorPlan`, `CasePlan` and `Budgets`.
`validate_artifact(source_root, bundle_path)` checks the original 113-file
manifest/source and optimized bytes; `validate_current_inputs(plan, root)`
checks the separate operator closure. `validate_consent(plan, consent, now)`
requires the exact plan digest and closed action list. These functions perform
offline validation; a syntactically valid `granted=true` object is not evidence
that Terry actually made that decision.

`bind_resources(plan, creation_receipts)` consumes four exact fresh-creation
receipts before returning `BoundCase` values. `deployment_projection(...)`
constructs the closed module/binding/settings projection using the actual D1
UUID; `validate_deployed_projection(expected, actual)` compares a provider
readback. Passing a manufactured receipt or passing expected data as actual
does not supply provider proof. `PrivateInputs.fresh(plan)` generates fresh
in-memory synthetic access tokens; `token(scenario)` supplies them and
`revoke_local()` drops references, without claiming provider revocation or
guaranteed memory erasure.

`scripts/hosted_publisher_finite_client.py` provides `ClientIdentity`,
`SharedBudget`, `FiniteClient` and `HttpsTransport`. The client takes an injected
`token_supplier`, durable journal, shared budget, clocks and stop predicate.
`run()` reserves each phase before dispatch, validates the immutable Worker's
exact success shape and stops on any uncertain result. The lifecycle must give
each case its own journal namespace and share one cumulative budget across all
four cases. The HTTP response contains no deployed identity attestation; client
receipt identities refer to the separately verified target.

### Local failure diagnostics — 2026-10-20

The finite client records a closed `diagnostic` object on terminal failures and
passes it through the caller's terminal unknown receipt. `stage` and `code` must
match the fixed `FAILURE_CODES` table; optional `parsedHttpStatus` is an exact
integer from 100 through 599. The journal rejects extra fields, unknown codes,
mismatched pairs and coerced status values before writing them. Diagnostics
contain no exception text, headers, bodies, credentials, resource IDs or origins.

Stages distinguish admission, durable reservation, local preparation before
dispatch, the transport call, response accounting/fences/status/headers/oracle,
activity accounting and journal completion/unknown persistence. A transport
failure means the local call failed; it does not prove the endpoint was reached
or identify a Worker/provider cause. Failure bodies are never interpreted.
Response acceptance, deadlines, worst-case reservations and no replay remain
unchanged. This source update supplies no hosted qualification or live authority.

If unknown persistence fails, the returned result remains `unknown` with a
`journal_unknown` diagnostic. The durable row can remain an unresolved intent;
an already committed completion is preserved if its acknowledgement was lost.
Neither condition permits replay. The in-memory diagnostic does not attest
that a durable diagnostic was written. A later hosted attempt needs a wholly
fresh reviewed candidate, packet, identities, credentials, windows and run.

`HttpsTransport(address, enabled=False)` is a concrete, default-disabled TLS
transport. A later approved operator must supply the reviewed numeric address;
the transport connects there while verifying the exact endpoint hostname. It
uses no DNS lookup, proxy, redirect following or retry. Address selection and
its authorization cannot be invented by this procedure. The client command
entrypoint always exits NO-GO; there is no live command in this document.

`scripts/hosted_publisher_provider.py` supplies `CloudflareProvider` with injected
account/token, at most four exact Worker names and four database names,
`Limits`, transport, clock and before/after-request journal callbacks. Methods
cover exact D1 creation, emptiness verification, migration, module/settings and
endpoint readback, endpoint enable/disable and scoped deletion primitives.
Public `upload_worker` unconditionally refuses with zero provider calls,
including with an injected transport. A private `_synthetic_upload_worker`
exercises encoding only and refuses the actual HTTPS transport.
Names must satisfy its `fga-publisher-...` constraint as well as plan validation.
The injected provider token is ASCII and at most 4,096 characters; this input
validation says nothing about its effective grants.
The actual default provider transport uses TLS to `api.cloudflare.com` and can
resolve that fixed host; it does not use the client's numeric-address transport.
Construction does not call it. Future use must wire the lifecycle's durable
intent and budget callbacks before allowing a request.

The provider explicitly does **not** implement atomic create-only Worker upload
(the provider PUT can replace a Worker and an absence check has a race),
lost-D1-create reconciliation when no UUID was received, provider/D1 in-flight
quiescence proof, operator token revocation/verification, or atomic same-version
Worker disable/delete fencing. Name-based settings inspection followed by a
mutation can race replacement; a matching readback is not an atomic condition
on the later action. These are hard
residual gates. Preserve an
unknown ledger and obtain a reviewed exact-target recovery/observation and
revocation mechanism; a fake adapter's result is not a live proof. There is no
complete unattended live create-to-delete ceremony while these seams remain.
An ambiguous provider request latches that adapter closed, including later
disable requests; a new cleanup-only adapter requires its own bounded approved
scope and cannot prove cancellation of the old request.

These are limitations of the current **Scripts adapter and unqualified
lifecycle**, not a claim that Cloudflare has no native resource-identity API.
Official documentation reviewed on 2026-10-17 describes a separate Workers
**Beta** API: `POST /accounts/{account_id}/workers/workers` creates a Worker
before code upload and returns a stable immutable ID. ID-addressed `PATCH` and
`DELETE` are documented; PATCH includes workers.dev/preview disable settings.
See the [Beta API announcement](https://developers.cloudflare.com/changelog/post/2025-09-03-new-workers-api/),
[create](https://developers.cloudflare.com/api/resources/workers/subresources/beta/subresources/workers/methods/create/),
[edit](https://developers.cloudflare.com/api/resources/workers/subresources/beta/subresources/workers/methods/edit/)
and [delete](https://developers.cloudflare.com/api/resources/workers/subresources/beta/subresources/workers/methods/delete/)
references. Treat returned Worker IDs as opaque; do not apply the D1 UUID format
validator to them or fall back to mutable names.

The Beta path is unselected, unimplemented and unqualified here. The reviewed
documentation does not establish the required collision/no-replacement
guarantee, create-intent recovery after a lost acknowledgement, or a conditional
mutation against a prior version. Stable identity alone does not establish
those properties or D1 in-flight quiescence. Selecting it would require review
of the full create/version/deployment/disable/delete chain and exact recovery
rules; it does not relax the current refusal or authorize provider experiments.
Lost D1-create recovery without its UUID and ordinary-query drain remain
unproven under the existing exact-only authority.

`scripts/hosted_publisher_operator.py` provides `DurableJournal`, `CaseJournal`
and `HostedPublisherOperator`. The operator receives the plan, separate consent,
provider, client transport, private inputs, retained source/bundle and current
source roots, journal, clocks and stop predicate. It also requires injected
`operator_grant` metadata; the default `None` always rejects action.
`validate_operator_grant` checks a closed record with grant/account IDs,
`["D1:Edit", "Workers Scripts:Edit"]`, `exact-account-only` scope, issue/current
expiry, matching revocation owner and trusted `metadata_verified=true`.
The secret value is never part of this metadata. A self-asserted verification
flag is not provider verification; the later reviewed private seam must supply
trusted grant evidence. `run()` checks owner/pins and
refuses the concrete provider's unsupported atomic create-only Worker operation
**before any provider request**. The four-pair success path is executable only
against a synthetic adapter that supplies the missing contracts; it is not a
live provisioning recipe.

`DurableJournal(path, plan_digest)` uses SQLite `synchronous=FULL` and a lifetime
OS owner latch in a caller-chosen private directory. Intents are reserved before
actions and never released for replay, including after a crash. `CaseJournal`
namespaces phase reservations by scenario. A new owner may observe/recover
cleanup from the journal; it cannot resume provisioning or phase dispatch.
Provider hooks persist cumulative calls/mutations, and SQL reservations charge
capacity before submission: 264 calls and 32,776 statements per phase plus
migration/emptiness capacity. These conservative submitted-operation bounds
are not measured changed-row counts or proof that work has drained.
Read receipts retain closed minimal presence metadata and upload ETag hashes,
not arbitrary provider settings or response prose. Provider payload byte budgets
also aggregate durably across new cleanup adapters; unknown responses retain a
2 MiB conservative reservation. Entering cleanup durably and permanently fences
dispatch across journal reopening, and lifecycle execution is serialized.

`cleanup_only(authority)` requires a separate closed record containing
`schema_version`, `granted`, exact `plan_digest`, cleanup `owner`, `decision_id`,
`expires_at` and exactly `disable_access`, `observe_pending`,
`delete_exact_pairs`. Its expiry cannot exceed the original cleanup deadline.
The narrower authority expiry is checked before each provider request alongside
the original plan deadline and monotonic lifetime.
It recovers identities from completed journal create/upload receipts, checks
deployed identity and disables access. The concrete provider lacks
`observe_pending`, so cleanup returns pending and performs no deletion. Only a
reviewed exact-D1 quiescence observation can make deletion eligible; the
synthetic adapter's `{quiescent: true}` response supplies test evidence only.
Provider-token revocation remains explicitly external-owner-required.
Cleanup also requires a present Worker for identity/version inspection. If its
DELETE takes effect but its acknowledgement is lost, later cleanup sees the
Worker absent and returns `cleanup_unknown`, retaining the exact D1. Automatic
reconciliation of that absence is not implemented; a separately reviewed
recovery path is required before proceeding. The cleanup instructions below
state eligibility requirements and do not claim this recovery already exists.

| Boundary | Implemented ceiling or required finite input |
| --- | --- |
| Plan input | 256 KiB; exact four cases in closed order, unique names/endpoints/run IDs |
| Endpoint | Exact disposable Worker `workers.dev` HTTPS origin; no production route |
| Provider lifecycle plan | At most 256 calls and 160 mutations across the run |
| Provider transport | At most 2 MiB request/response payload per call; 16 MiB requests / 32 MiB responses cumulative; 8 KiB request headers and 64 KiB response framing/header allowance per call; 20-second socket / 25-second request / 7,200-second adapter lifetime |
| Candidate SQL plan | At most 8,192 wrapper calls and 1,048,576 statements; retain distinction from changed rows and provider billing |
| Lifecycle time | At most 14,400 seconds including cleanup; plan can lower it |
| Client requests | At most 32 per case / 128 shared, including any authorized negatives |
| Client bytes | Operator sets 262,144 request bytes / 8,388,608 response bytes shared; 65,536 response-wire-byte ceiling per request |
| Phase and case | At most 60 seconds per phase; at most 1,800 seconds remaining access per case |
| Synthetic effects | At most 448 handoffs and 28 POSTs shared; at most 16/one reserved for an uncertain phase |

The finite client currently sends only the seven positive phase requests per
case: 28 requests in a normal complete run. Its budget headroom does not create
negative-case requests or authority to invent them. Server rejection/replay,
crash/restart and restoration coverage remain separate evidence. The provider
control-plane budget and client `provider_calls` are different counters: the
latter records synthetic in-Worker handoffs, not Cloudflare management calls.

## Private input and least privilege

Keep provider-management authentication separate from the four synthetic probe
access secrets. The provider secret must reach the reviewed transport directly
through its private in-memory input seam, and the probe token must reach both
the Worker secret binding and the matching client header. Never supply either
as command arguments, query parameters, tracked files, shell history, trace
output, exception text, receipts or progress messages. No preparation step
reads, checks for or creates a real credential.

Before granting a future operator credential, its owner reviews the exact API
methods and selects the narrowest supported account/resource scope. Cloudflare
documents API-token permissions, resource scopes, optional source-IP filtering
and token TTL; its upload API accepts Workers script write permissions and D1
creation accepts `D1 Write`. Those permissions can be broader than these eight
resources. Record the effective scope and any excess authority explicitly;
application checks are not provider-side resource isolation. Do not substitute
a global API key or infer effective grants from token syntax. See
[token creation](https://developers.cloudflare.com/fundamentals/api/get-started/create-token/),
[Worker upload](https://developers.cloudflare.com/api/resources/workers/subresources/scripts/methods/update/)
and [D1 creation](https://developers.cloudflare.com/api/resources/d1/subresources/database/methods/create/).

The revocation owner retains the provider token identifier privately, its
provider expiry and a separate means to revoke it. Probe expiry protects
candidate entry; it does not revoke provider-management grants. At stop or
completion, remove probe access, complete the separately authorized cleanup
with the necessary narrow credential, then revoke management access and retain
sanitized provider confirmation. If emergency revocation happens first, retain
the exact disabled/residual-resource handoff; do not revive dispatch to regain
cleanup. Removing a local file or losing a credential is not revocation proof.

## Endpoint, binding and dispatch checks

The sealed candidate has `workers_dev=false`, `preview_urls=false`, no route or
cron and no production binding. It cannot be treated as a reachable deployment.
The final provider implementation must supply and verify its exact finite
reachability mechanism. A placeholder URL or a valid-looking overlay does not
establish endpoint reachability or provider state.

Before dispatch, verify the exact deployed Worker version/module digest,
configuration and actual `DB` binding UUID against the private ledger; verify
the corresponding fresh-empty D1/schema/migration receipt. Bind the separate
source-artifact and deployed-module hashes correctly. `PROBE_RESOURCE_ID` and
its matching header are labels enforced by the candidate, not independent
proof of the actual bound D1. A self-asserted version or UUID cannot replace
the reviewed provider observation.

Each request is an empty-body POST to the exact endpoint's
`/__publisher/{phase}`, with no query and the private access/artifact/run/resource
headers. Use `seed`, `http`, `materialize`, `attach`, `title`, `remove`, `finish`
once, in order, for each fresh pair. Unexpected redirect, external access,
provider egress, identity mismatch, malformed response, failed phase or unknown
outcome stops dispatch. Never clear a control row or replay a phase to obtain a
clean receipt.

## Stop and cleanup-only continuation

1. Persist the stop and fence new client/provider work. Close candidate endpoint
   access using the reviewed exact-resource method. Mark the outcome unknown
   when the disable reply is absent; admission expiry alone is not disable proof.
2. Preserve the durable intent/outcome journal, request counters, exact resource
   ledger and last accepted phase. A timed-out create/upload/migration/request
   or delete may already have taken effect. Never blindly repeat it.
3. Use only the authorized exact-target observation path to reconcile pending
   operations. A phase timer, client abort or configuration change cannot cancel
   already submitted D1 work. Establish the reviewed no-in-flight criterion and
   inspect final durable markers before deletion; unresolved busy work remains
   unresolved. No sleep duration or one successful GET proves quiescence.
4. During cleanup-only authority, permit only its listed observations, disablement
   and exact deletion. No fresh resources, migrations, enables, phases, reset,
   broad account list, wildcard or prefix selection. Revalidate the original
   account/Worker version/binding/run and D1 identity before deleting each target.
5. Record Worker and D1 results independently. A lost delete reply requires exact
   absence reconciliation; a lost create reply may leave an unbound resource and
   therefore blocks any success claim. Never infer deletion from expiry or local
   credential removal.
6. At cleanup deadline, budget exhaustion, identity drift or failed observation,
   stop the continuation and retain disabled/expired access plus the exact
   known/unknown residual census, journal, owner and next decision deadline.
   Preserve unresolved journals for scoped recovery. Do not broaden deletion
   authority or claim cleanup passed.
7. Record probe-access closure and provider-token revocation separately. A
   remaining unknown result stays unknown in the handoff even when another
   resource was deleted successfully.

## Receipt and release gate

Sanitized evidence binds the reviewed closure, scenario, counters, outcome,
stop reason, quiescence assessment, cleanup and revocation status. Private
resource/account identities, authorization evidence and exact residual targets
remain in the private action sheet/journal; no secret or response payload is
copied into tracked evidence. Keep public outcome summaries separate from the
private recovery ledger without discarding either.

Before requesting #0134's exact decision, the parent must reconcile the
implemented interfaces and caps above with their actual source, record the
final closure pins and independent review, and name any remaining provider or
private-delivery seam explicitly. Synthetic tests establish implementation
behavior only. Hosted receipts, current-schema restore/reconciliation,
production composition, native qualification and activation remain separate
gates.
