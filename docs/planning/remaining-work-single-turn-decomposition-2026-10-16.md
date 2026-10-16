# Remaining FGA work: single-turn decomposition

Date: 2026-10-16. This is a scheduling/coverage map, not architecture acceptance,
execution authorization or a claim that the remaining product is implemented.

Original #0023–#0026 retain their identities, prior histories, original scope and
completed dependencies. Each now owns one final evidence-only acceptance audit.
Its child cards own the unfinished work; all are scoped Ready For Work even
where explicit blocking links prevent execution. Completed #0027/#0028/#0029/
#0030/#0034 and the prior native/hosted milestones stay closed and retain their
original provenance and limits.

Terry reset every FGA ticket to P2 during this decomposition. P2 is also the
global default for new tickets. Raise priority only for concrete urgency,
impact, deadlines or explicit direction; blocking other work alone is not a
reason for P1. The dependency graph still determines execution order.

A work card fits one focused parent turn with appropriate parallel subagents:
one named component, contract/proof, prepared execution packet, decision or finite
rehearsed run. Its description specifies deliverable, acceptance, exclusions,
exact prerequisites and unresolved input conditions. Implementation includes its
focused tests and required independent review; narrow review-only proposals were
folded into the reviewed output where practical. Future defects or unavailable
provider/SDK facts cannot be guaranteed away by planning: preserve a failed result
or actual blocker and never label an attempted run as qualified.

Owner checkpoints are future, dependency-gated Ready For Work cards. Present the
concrete finished packet before moving one to Needs Terry; reuse applicable
existing permission. A Completed decision card does not mean approval if its
record says declined/deferred. Bot never accepts its own work into Completed.
No desktop, cloud, credential, production-capability or Flickr-write authority is
created by this decomposition. Safety cleanup stays inside its live run; a later
cleanup audit only verifies that work and never defers it.

The dependency graph uses specific shared outputs. #0023 consumes #0024's shared
READ adapter and required proof POST policy/adapter, without waiting for the
whole downstream group workflow. #0024 owns Library selection metadata/editing
and frozen-choice revision consumption; #0026 owns the publish provider consuming
that interface. #0025 retains its already selected private pair; #0025 is related
to #0026, not a prerequisite for all independent publisher engineering.

Accepted architecture contracts and later owner directives remain controlling.
Preparation references: the dated development handoff, fixed-origin plan,
group-selection readiness, controlled-trial runbook/readiness inventory and
new-photo publisher workplan in this repository. The live localswim descriptions
contain the full per-ticket acceptance criteria and current evidence links.

## Original #0023

| Ticket | Single-turn output | Blocking prerequisites | Owner |
| --- | --- | --- | --- |
| #0036 | Capture current fixed-origin artifact, edge and rollback inputs | None | Codex |
| #0037 | Determine supported allocation and edge qualification method | #0036 | Codex |
| #0038 | Prove closed synthetic dispatch on the actual three routes offline | #0036 | Codex |
| #0039 | Implement finite actual-handler fault matrix and collector | #0038 | Codex |
| #0040 | Specify and implement finite native-facing edge fault cases | #0037, #0038 | Codex |
| #0041 | Prepare separately versioned fixed-origin native qualification entrypoint | #0039, #0040, #0057 | Codex |
| #0042 | Implement one-attempt synthetic provisioning and exact cleanup lifecycle | #0038, #0039 | Codex |
| #0043 | Prepare exact captured rollback and rehearse restoration offline | #0036, #0042 | Codex |
| #0044 | Independently review finite fixed-origin execution packet | #0037, #0041, #0042, #0043 | Codex |
| #0045 | Resolve concrete fixed-origin deployment and native execution authority | #0044 | Terry checkpoint |
| #0046 | Execute one reviewed fixed-origin synthetic native attempt | #0045 | Codex |
| #0047 | Assess fixed-origin evidence against every candidate transport gate | #0037, #0046 | Codex |
| #0048 | Prepare clean final artifact qualification delta and execution packet | #0047 | Codex |
| #0049 | Resolve exact clean candidate deployment/readback execution authority | #0048 | Terry checkpoint |
| #0050 | Execute clean artifact exact-path and effective-edge verification | #0049, #0057, #0056 | Codex |
| #0051 | Prepare minimal real-account public-photo read qualification packet | #0050, #0057, #0056, #0061 | Codex |
| #0052 | Resolve narrow real-account read and native action authorization | #0051 | Terry checkpoint |
| #0053 | Execute approved bounded public-photo read and final selector observations | #0052 | Codex |
| #0054 | Present qualified thumbnail contract for owner acceptance | #0047, #0050, #0053, #0057, #0056 | Terry checkpoint |
| #0142 | Prepare the final read-only selector release packet | #0054, #0057, #0061, #0053 | Codex |
| #0143 | Decide exact read-only capability release and host smoke | #0142 | Terry checkpoint |
| #0144 | Execute the approved read-only release and exact-build smoke | #0143 | Codex |

## Original #0024

| Ticket | Single-turn output | Blocking prerequisites | Owner |
| --- | --- | --- | --- |
| #0055 | Pin remaining group workflow adapter and registration contracts | None | Codex |
| #0056 | Implement disabled SDK task, identity and storage adapter factory | #0055 | Codex |
| #0057 | Implement disabled shared authenticated READ and proof protocol adapters | #0055, #0037, #0056 | Codex |
| #0058 | Prepare finite POST characterization packet | #0055 | Codex |
| #0059 | Approve concrete POST characterization action scope | #0058 | Terry checkpoint |
| #0060 | Execute finite native POST characterization and cleanup | #0059, #0037 | Codex |
| #0061 | Implement disabled proof and whole-batch POST transport | #0055, #0060, #0056, #0057 | Codex |
| #0062 | Compose a visible retained-status controller and view | #0055 | Codex |
| #0063 | Implement explicit immutable-handoff reconciliation core | #0055 | Codex |
| #0064 | Implement Library selection scope and unpublished Save adapters | #0055, #0056 | Codex |
| #0065 | Expose frozen-choice revision-consumption adapter for publisher integration | #0064 | Codex |
| #0066 | Add native reconciliation view and complete disabled invocation wiring | #0056, #0057, #0061, #0062, #0063 | Codex |
| #0067 | Prepare integrated native batch, status and recovery qualification packet | #0066, #0057, #0061, #0065 | Codex |
| #0068 | Obtain action-time approval for the reviewed integrated native packet | #0067 | Terry checkpoint |
| #0069 | Execute finite integrated native qualification and exact cleanup | #0068 | Codex |
| #0070 | Prepare fail-closed reviewed release registration candidate | #0066, #0057, #0061, #0065, #0069, #0050, #0053 | Codex |
| #0071 | Approve exact final registered candidate native smoke scope | #0070 | Terry checkpoint |
| #0072 | Qualify final registered artifact on the supported native host | #0071 | Codex |

## Original #0025

| Ticket | Single-turn output | Blocking prerequisites | Owner |
| --- | --- | --- | --- |
| #0073 | Supply the bounded production observation adapter | None | Codex |
| #0074 | Freeze the integrated trial candidate snapshot | #0023, #0024, #0073 | Codex |
| #0075 | Prepare and review one exact hosted rehearsal packet | #0074, #0030 | Codex |
| #0076 | Qualify one frozen backend artifact | #0074, #0075, #0139 | Codex |
| #0077 | Execute the exact integrated hosted rehearsal once | #0075, #0076, #0140 | Codex |
| #0078 | Observe one fresh stopped production baseline, complete census and selected-pair eligibility | #0073, #0076, #0077, #0141 | Codex |
| #0079 | Assemble the reviewable one-pair activation packet | #0074, #0076, #0077, #0078 | Codex |
| #0080 | Owner decides on the exact one-pair execution window | #0079 | Terry checkpoint |
| #0081 | Execute one approved pair and close the window | #0080 | Codex |
| #0139 | Resolve exact frozen-artifact release-run authority | #0075 | Terry checkpoint |
| #0140 | Resolve exact hosted activation/stop rehearsal authority | #0075 | Terry checkpoint |
| #0141 | Resolve the exact production observation/preflight scope | #0073 | Terry checkpoint |

## Original #0026

| Ticket | Single-turn output | Blocking prerequisites | Owner |
| --- | --- | --- | --- |
| #0082 | Freeze the production upload recovery-store contract | #0029 | Codex |
| #0083 | Owner decision: freeze the production upload recovery-store contract | #0082 | Terry checkpoint |
| #0084 | Resolve photo catalog repair after the publish callback | None | Codex |
| #0085 | Close ambiguous-upload candidate wire | None | Codex |
| #0086 | Owner decision: close ambiguous-upload candidate wire | #0085 | Terry checkpoint |
| #0087 | Propose album binding and per-photo association wire | #0089 | Codex |
| #0088 | Owner decision: album binding and photo association protocol | #0087 | Terry checkpoint |
| #0089 | Propose hosted publish-service identity wire | None | Codex |
| #0090 | Owner decision: publish-service identity protocol | #0089 | Terry checkpoint |
| #0091 | Propose album status and explicit create-repair wire | #0087, #0088 | Codex |
| #0092 | Owner decision: album status and create-repair protocol | #0091 | Terry checkpoint |
| #0093 | Propose album title and local-removal lifecycle wire | #0087, #0091 | Codex |
| #0094 | Owner decision: album lifecycle protocol | #0093 | Terry checkpoint |
| #0095 | Implement the bounded upload-attempt catalog store | #0083 | Codex |
| #0096 | Build the unregistered ordinary-Album provider shell | #0090 | Codex |
| #0097 | Consume frozen per-photo choices in the new publish provider | #0095, #0096, #0065 | Codex |
| #0098 | Integrate rendition settings and completed-file preflight | #0095, #0096, #0028 | Codex |
| #0099 | Implement normal upload-origin photo binding | #0034 | Codex |
| #0100 | Implement explicit ambiguous-upload resolution | #0099 | Codex |
| #0101 | Add the plug-in authorization client | #0095, #0034, #0061 | Codex |
| #0102 | Implement one-call multipart transport and definitive-result classification | #0101 | Codex |
| #0103 | Compose normal per-photo upload execution | #0095, #0097, #0098, #0099, #0101, #0102, #0084 | Codex |
| #0104 | Implement catalog-only photo repair and proof recovery | #0084, #0095, #0099, #0100 | Codex |
| #0105 | Implement advisory upload candidates | #0086, #0034 | Codex |
| #0106 | Build per-photo reconciliation and leave-unresolved UI | #0100, #0104, #0105, #0054 | Codex |
| #0107 | Implement deliberate publish-a-new-copy recovery | #0083, #0095, #0103 | Codex |
| #0108 | Implement hosted Album binding and guarded first candidate | #0088, #0099, #0109 | Codex |
| #0109 | Implement hosted publish-service identity provisioning | #0090 | Codex |
| #0110 | Implement idempotent album-photo obligations | #0088, #0092, #0108 | Codex |
| #0111 | Implement fenced first-photo album materialization | #0108, #0110 | Codex |
| #0112 | Implement fresh read/add/read album attachment | #0110, #0111 | Codex |
| #0113 | Implement album ambiguity/status reconciliation endpoints | #0092, #0108, #0110, #0111 | Codex |
| #0114 | Implement revisioned remote album title sync | #0094, #0108, #0111 | Codex |
| #0115 | Implement non-destructive hosted local-removal archival | #0094, #0108, #0110, #0114 | Codex |
| #0116 | Integrate album binding/status and catalog sync | #0096, #0103, #0108, #0110, #0113 | Codex |
| #0117 | Integrate explicit album-create repair UI | #0113, #0116 | Codex |
| #0118 | Integrate local Album rename/reparent/removal callbacks | #0096, #0114, #0115, #0116 | Codex |
| #0119 | Connect proved uploads to immutable group handoff | #0097, #0103, #0104, #0066 | Codex |
| #0120 | Compose truthful publisher status and recovery navigation | #0104, #0106, #0107, #0116, #0117, #0118, #0119 | Codex |
| #0121 | Prepare exact-artifact hosted publisher qualification packet | #0099, #0100, #0105, #0108, #0110, #0111, #0112, #0113, #0114, #0115, #0109 | Codex |
| #0122 | Execute bounded hosted publisher qualification | #0121, #0134 | Codex |
| #0123 | Prepare the native provider/render qualification packet | #0096, #0097, #0098 | Codex |
| #0124 | Prepare the native album/group composition qualification packet | #0116, #0117, #0118, #0119, #0120 | Codex |
| #0125 | Prepare the native upload-recovery qualification packet | #0083, #0103, #0104, #0106, #0107 | Codex |
| #0126 | Qualify native provider, selection and rendition adapters | #0123, #0135 | Codex |
| #0127 | Qualify native upload recovery and catalog repair | #0125, #0083, #0136 | Codex |
| #0128 | Qualify native album/group/status composition | #0124, #0126, #0127, #0072, #0137 | Codex |
| #0129 | Build and review the disabled registered publisher candidate | #0122, #0126, #0127, #0128 | Codex |
| #0130 | Smoke-test the exact registered publisher bundle in the host | #0129, #0138 | Codex |
| #0131 | Prepare the controlled one-photo real-upload packet | #0122, #0126, #0127, #0128, #0130 | Codex |
| #0132 | Owner decision: exact new-photo live publication | #0131 | Terry checkpoint |
| #0133 | Execute the authorized controlled new-photo publication | #0132 | Codex |
| #0134 | Authorize the exact disposable hosted publisher run | #0121 | Terry checkpoint |
| #0135 | Authorize the exact native provider/render fixture | #0123 | Terry checkpoint |
| #0136 | Authorize the exact native upload-recovery fixture | #0125 | Terry checkpoint |
| #0137 | Authorize the exact native album/group fixture | #0124 | Terry checkpoint |
| #0138 | Authorize the exact registered publisher smoke test | #0129 | Terry checkpoint |
