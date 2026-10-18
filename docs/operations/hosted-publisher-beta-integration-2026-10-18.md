# Hosted publisher Beta integration — 2026-10-18

Status: **Offline source integration; hosted execution remains NO-GO.** This
#0162 procedure implements the direction Terry accepted for #0157 on
2026-10-18: “Accept #0157 as proposed (Recommended)”, identifying canonical
revision `e9552f2eeb16a98fbcac536685dd32b9f39928b2`. The
[accepted scoped contract](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/proposals/hosted-operator-provider-strategy-2026-10-17.md)
and [acceptance record](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/project-log/2026-10-18-hosted-provider-strategy-acceptance.md)
control the Beta identity direction, exclusive finite operator assumption and
six-condition fixture-only disposal rule. This derived procedure grants no
account request, token inspection, deployment, endpoint request or cleanup action.

The [older finite operator](hosted-publisher-finite-operator-2026-10-17.md) and
[provider strategy](hosted-publisher-provider-strategy-2026-10-17.md) retain their
dated evidence. Use the implementation described here for the new integration;
do not interpret historical missing-method descriptions as current behavior.
The [qualification packet](hosted-publisher-qualification-packet-2026-10-17.md)
and [action decision](hosted-publisher-action-decision-2026-10-17.md) retain their
separate gates: #0134 owns the later exact action decision; #0122 owns any
subsequently authorized hosted execution. Production scheduling, real Flickr
access, native Lightroom operation and activation remain outside this scope.

## Immutable candidate and separate reviewed closure

Preserve #0121 source commit `aca532af6d570125c5d8bbcbd6ac1b4a10ae74f7`,
113-file source-artifact SHA2-256
`718b3dd7e1ec669c7e043f4c3a37142ceaad42a5bd3bcbc0639868a2b1e5aed1`, and
652,967-byte optimized Worker SHA2-256
`b2241f88c94ec6561b2a902a5561bf9f63459e420fbd111861db1636feb2a26f`.
These are prior packet identities, not a fresh rehash by this document. Do not
rebuild, recapture or modify the retained candidate, migration bytes or receipts.

Pin the new operator/provider/client/plan source closure separately after final
integration and independent review. Include the precise deployment projection,
migrations 0001–0026, tool versions, tests and this procedure. The final parent
handoff supplies committed revision and byte pins; until populated and reviewed,
this document is not an execution packet. Source inspection or passing synthetic
tests cannot substitute for actual provider readbacks or owner consent.

## Private packet before any runtime use

The authorized operator must have a complete, reviewed private action sheet:

- Exact reviewed source/bundle/operator closure pins, account, four unique
  intended Worker/D1 names and the four cases `happy`, `create_lost`,
  `attachment_lost`, `title_lost`. No existing, reused or shared fixture.
- Exact endpoint mechanism and client numeric address, start, dispatch expiry,
  cleanup deadline, cumulative limits, owner/operator, stop owner, cleanup owner,
  token revocation owner and residual escalation deadline.
- Explicit exclusive owner control for the finite resource lifetime: no dashboard,
  CI or other management writer. This is an operational assumption, not provider
  compare-and-set or exclusion. Any drift stops the ceremony.
- Actual human consent bound to that plan and its precise allowed actions;
  separately bounded exact-target cleanup continuation and fixture disposal.
  A parser-accepted `granted=true` record does not prove human consent.
- Effective management-token grants and excess scope, provider expiry, private
  token identifier and independent revocation means. Review permissions for
  the actual Beta, Scripts and D1 methods; labels or token syntax do not prove
  effective authority. No global API key or automatic authority expansion.
- Private delivery of management authentication and four fresh synthetic probe
  secrets through the reviewed in-memory seams. No secret in command arguments,
  URLs, shell history, tracked files, journals, exceptions or public receipts.
- Staged binding rules: create receipts supply actual Worker IDs, D1 UUIDs,
  version and deployment IDs. Do not manufacture them in advance or adopt an
  existing resource whose name matches an intended name.

All inputs and synthetic-data isolation premises must be verified through their
reviewed source. Metadata verification flags and source capability flags report
state; they neither authorize calls nor prove provider state. An injected
transport is trusted test code, not a network sandbox. The default-disabled
paths do not turn arbitrary injected callables into approved runtime transports.

## Finite budget and journal boundary

Retain one cumulative journal and budget across all four cases, provisioning,
phase dispatch, stop, cleanup and replacement cleanup adapters. New adapters or
process ownership cannot replenish an allowance. Durable intent precedes each
action; consumed intents and phases never become eligible for replay after a
crash or uncertain response. Keep the journal/evidence outside disposable
resources, with its lifetime owner latch and durable cleanup fence.

| Boundary | Maximum; a plan may lower it |
| --- | --- |
| Management calls / mutations | 256 / 160 shared |
| Provider payload | 2 MiB request and response per call; 16 MiB requests / 32 MiB responses shared |
| Provider framing/time | 8 KiB request headers / 64 KiB response framing; 20-second socket / 25-second request / 7,200-second adapter lifetime |
| Whole lifecycle | 14,400 seconds including cleanup |
| Candidate SQL capacity | 8,192 calls / 1,048,576 statements shared |
| Client | 32 requests per case / 128 shared; 262,144 request bytes / 8,388,608 response bytes shared; 65,536 response-wire bytes per request |
| Phase / case access | 60 / 1,800 seconds |
| Synthetic effects | 448 handoffs / 28 POSTs shared; at most 16 / one per uncertain phase |
| Plan | Closed duplicate-free JSON; 256 KiB; exact four cases and unique names/endpoints/run IDs |

SQL reservations include 264 calls and 32,776 statements per phase plus
migration/emptiness capacity. These are conservative submitted-work bounds,
not changed rows, billing measurements or settlement proof. Unknown provider
responses retain conservative byte capacity. Deadlines, stop and cleanup scope
must be checked before every request. Headroom does not authorize extra negative
requests, repeated phases, another create or a deadline extension.

## Actual source interfaces and call sequence

The callable boundary is Python source, not a live shell command. The finite
client command entrypoint remains NO-GO. The reviewed caller must construct
[BetaPublisherProvider](../../scripts/hosted_publisher_worker_deployment.py)
with exact names/account, private token, `exclusive_owner=True`, finite `Limits`,
clocks and journal hooks, then supply it to
[HostedPublisherOperator](../../scripts/hosted_publisher_operator.py) together
with its separate consent, verified grant metadata, private inputs, retained
source/bundle roots, current source root, durable journal and stop predicate.
The built-in provider transport remains refused. This constructor recipe
identifies the source seams; it grants no authority to inject a network callable.

[The plan module](../../scripts/hosted_publisher_operator_plan.py) owns
schema-2 `load_plan`, `validate_artifact`, `validate_current_inputs`, `validate_consent`,
`validate_operator_grant`, `bind_resources` and `deployment_projection`.
`PrivateInputs.fresh(plan)` creates synthetic probe secrets in memory.
`DurableJournal(path, plan.digest)` and `CaseJournal` retain durable action and
phase reservations. `run()` performs source/consent/grant checks and reserves
`operator:run` before provisioning. Schema-1 consent must match the exact
`OWNER_ACTIONS` list, including exclusive operator/synthetic fixture assertions
and the specific dispatch fence/Worker deletion/D1 disposal actions. A completed or unknown reservation cannot
be resumed as another run.

The implemented provisioning/dispatch order is:

1. For each case, call `create_database`, `inspect_database`,
   `verify_empty_database`, then Beta `create_worker`. Bind D1 UUID and returned
   Worker identity from the acknowledged fresh-create receipts in the journal.
   There is no absence-read/Worker-upsert create substitute.
2. Bind all four fresh D1 receipts with `bind_resources`. For each bound case,
   read and hash the retained migrations 0001–0026 against the immutable
   manifest, reserve their SQL capacity, then call `migrate` once per migration.
3. Build `deployment_projection` using that case's actual D1 UUID and call
   `create_version(identity, module, sha2, projection, token, key=...)`. The
   provider submits Beta version creation with `deploy=false` using the
   returned immutable Worker ID; one version intent is consumed per Worker.
4. Call `deploy_version(identity, version, key=...)`. The provider reads the
   version and observes immutable Worker identity before submitting the Scripts
   name-based deployment. It validates the returned deployment/version at 100%
   traffic and observes the immutable Worker identity afterward. No read here
   provides provider CAS or protection from an external account administrator.
5. Check deployment using `inspect_version` and `inspect_deployment`. Version
   readback includes actual modules; deployment readback checks both the exact
   returned deployment and the first actively serving deployment in the bounded
   current read (`page=1&per_page=1`). The identity observations bracket
   the Scripts seam. `assert_endpoint` compares the exact workers.dev origin
   against the observed account subdomain and owned Worker name. Record the
   verified binding before enabling dispatch.
6. Call `enable_worker` by immutable ID, then `inspect_endpoint`; require
   `enabled=true` and `previews_enabled=false`. Only then construct the finite
   client's bound identity and send its seven requests through the separately
   reviewed exact-endpoint transport. Stop/disable each case after dispatch.

The configuration validator binds exact `worker.js` module bytes and SHA2-256,
`main_module`, compatibility date `2026-10-16`, `nodejs_compat`, disabled
observability/logpush and the closed binding projection. `DB` must equal the
actual freshly returned D1 UUID. `PROBE_*` plain-text values bind artifact,
scenario, run, expiry and resource; `PROBE_ACCESS_TOKEN` is the only secret
binding. Duplicate, unexpected or contradictory configuration/bindings refuse.
Beta D1 `database_id` spelling is normalized; secret readback is redacted and
checks binding shape, not an independent re-observation of the secret value.
Unexpected assets, containers, exports, migrations or package dependencies
refuse. The private caller remains responsible for authentic secret delivery.
A matching `PROBE_RESOURCE_ID` header or response label cannot attest `DB`.

[The identity helper](../../scripts/hosted_publisher_worker_identity.py) uses
returned Worker IDs for reads, disable and non-forced deletion; D1 UUIDs and
Worker IDs remain distinct. [The base provider](../../scripts/hosted_publisher_provider.py)
retains bounded TLS/request parsing, D1 primitives and shared callbacks. The
Beta composition uses that same provider session for identity/version/
deployment requests, so it does not create another budget or unknown latch.
[The client](../../scripts/hosted_publisher_finite_client.py) uses one shared
`SharedBudget` with a distinct journal namespace per case. Client handoff counts
are synthetic in-Worker work, distinct from management-call counters.
## Dispatch, stop and fixture disposal

The finite client sends empty-body POSTs once, in order, to the exact endpoint's
`/__publisher/{phase}`: `seed`, `http`, `materialize`, `attach`, `title`, `remove`,
`finish`. Normal completion means 28 requests across four cases. It validates
the immutable candidate's exact response shape, including its deliberate
`status: NO-GO` and `productionSchedulerQualified: false`. These responses do
not qualify production or establish settlement of every raw D1 operation.

On any unknown, stop, drift or deadline failure, durably fence provisioning and
phase dispatch. Preserve the last acknowledged phase, all intents, known and
unknown submitted work and its cost reservations. Do not reset a control row,
repeat a phase, rebuild the candidate or hide an uncertain result with a new run.
An abort, expiry, sleep, endpoint disable or later successful SELECT cannot
cancel already submitted SQL or prove global quiescence.

The accepted disposal exception applies only to these fresh exclusively
synthetic fixtures, with a successful fresh-D1 receipt, verified candidate binding
and no production data/history, real Flickr access, shared binding, route,
schedule, service consumer or external production reference. Apply all six
canonical conditions, including these ordered closure requirements:

1. Persist the dispatch/provisioning fence and preserve journals and evidence
   independently of the fixture. Account for known and unknown work.
2. Disable the acknowledged owned Worker by immutable ID and verify disablement.
   Delete that Worker without force, then independently verify exact-ID absence.
   Unknown or drifted Worker closure means retain its D1.
3. Under separate exact cleanup authority, perform ordinary D1 DELETE for the
   acknowledged UUID within the original remaining deadline and budgets. No
   `unsafeDelete`, guessed name, prefix search or unrelated resource is permitted.
4. Record D1 deletion acknowledgement and independent exact-UUID absence.
   Preserve successful receipts independently so a subsequent authorized
   observation need not demand a Worker already proved absent.
5. Report resource disposal separately from phase and SQL outcomes. Unknown SQL
   settlement/cancellation remains unknown even after acknowledged disposal.
   Disposal does not prove completed business work, physical backup erasure,
   provider-wide quiescence or production conformance.

A missing/lost/contradictory create acknowledgement leaves an unresolved intent.
No create retry, account-wide listing, prefix discovery, same-name adoption or
guessed deletion follows. Retain known exact resources for separately authorized
cleanup; an unidentified possibly billable resource needs a new exact recovery
decision. Lost delete acknowledgements likewise remain unknown; independent
absence evidence is not authority to replay a mutation. Retain exact residual
identities, unknown intents, owner and next decision at budget/deadline exhaustion.
Unresolved outcomes prevent a complete qualification or verified-cleanup claim.

`cleanup_only(authority)` is the separate callable continuation. Its closed
record contains `schema_version=1`, `granted=true`, exact `plan_digest`, cleanup
`owner`, unique `decision_id`, `expires_at` no later than the original cleanup
deadline, and exactly `fence_dispatch`, `disable_access`,
`delete_owned_worker`, `dispose_exact_synthetic_d1` in that order. The record
must embody the actual reviewed owner decision; passing its parser is not
consent evidence. Entry permanently fences dispatch. It recovers only completed
creation/version/deployment/binding receipts from the durable journal and calls
`restore_owned_resources` for cleanup, never discovery or provisioning.

Cleanup uses `disable_worker`, `inspect_endpoint`, `delete_worker`,
`inspect_worker`, `delete_database`, then `inspect_database` under the gates
above. Fixed `dispose:{case}:worker` and `dispose:{case}:database` intent keys
prevent a later cleanup decision from replaying a deletion. A known Worker can
be removed when binding verification never completed, but its D1 remains as
`worker_removed_binding_unverified`. Missing identities and unknown deletes
remain explicit residual statuses. A wholly disposed resource set is reported
as `resources_disposed` or `disposed_with_unknown_outcomes`; `querySettlement`
remains `unproved` and `qualification` remains `not_established`. No
`observe_pending` boolean or invented drain service is required or supplied by
this accepted fixture-disposal path.
## Token closure and later action gate

Probe expiry or local `revoke_local()` reference removal does not revoke the
management grant. After separately authorized cleanup, or immediately on an
emergency stop when required, the named revocation owner uses the independent
revocation means and retains sanitized provider confirmation. If revocation
prevents cleanup, preserve the exact residual handoff; do not regain dispatch
or infer cleanup from credential loss. Token revocation remains an external
owner action, not a result fabricated by the operator.

Before #0134, bind the completed independent review and final committed closure
pins to the concrete private action sheet, effective grants, runtime delivery
seams, exact schedule, budgets, staged returned identities, disposal authority
and revocation owner. Reconcile any remaining source/private/provider seam
explicitly. A complete source packet can support that decision; it does not
make the decision. Any future hosted evidence must bind the same reviewed
bytes and actual provider receipts. Restore/reconciliation, production
composition, native qualification and capability activation remain separate.
