# Exact captured restoration: offline preparation

Date: 2026-10-17. Ticket #0043. Status: offline preparation and rehearsal;
provider restoration and production conformance remain unverified.

`scripts/fixed_origin_restore.py` prepares the completed #0036 capture as a
private, byte-exact rollback packet. It pins that capture's integrity index and
decoded module digests, checks all fifteen files, reconciles the restoration
input index, exact active version and weights, and verifies captured intake and
dispatch flags remain disabled. The packet includes every captured binding and
runtime setting, routes/domain attachment, Page Rules, account/zone ruleset
catalogues and zone settings. Raw provider metadata and module source stay
outside Git. No token or secret value is read, exported or generated.

Preparation requires a fresh destination beneath `private-evidence`, outside
the repository. It preserves the original captured bytes and writes a private
manifest. Verification checks against the pinned original index, so rewriting
the packet manifest cannot conceal altered configuration or edge inputs.
No provider upload, restore, resource deletion or deployment adapter exists.

The offline rehearsal executes the actual unchanged captured default dispatcher
before and after materializing that packet. It uses the existing reviewed Node
VM host adapter and synthetic SQLite fixture from #0038. It compares registered
ordinary routes with missing credentials, response status/headers/body and the
three intended read paths. Fresh error correlation UUIDs are validated and
normalized before comparison; other response fields are compared unchanged.
This is refusal-path regression coverage; it does
not exercise every authenticated route, assets, scheduled work or real secrets.
Captured capability configuration and absence of temporary qualification bindings
are checked separately. Both synthetic deployment/user durable write gates must
remain paused, with their revisions and the entire synthetic database unchanged.
Throwing host adapters and counters detect host I/O and global network attempts.
The VM is a harness for trusted pinned source, not an arbitrary-code sandbox.

Run using the pinned Node24.22.0 and repository Python tooling, passing the
#0036 capture root, a fresh private output directory and #0038 prepared fixture:

```console
uv tool run --from uv==0.12.5 uv run --frozen python scripts/fixed_origin_restore.py <repository> <private-capture-root> <fresh-private-output> <private-offline-fixture> <pinned-node>
uv tool run --from uv==0.12.5 uv run --frozen python -m unittest tests.test_fixed_origin_restore
```

The runner suppresses raw child diagnostics and emits only a closed sanitized
receipt. Its once-only runner file prevents automatic replay after a failed or
ambiguous attempt; investigate privately and prepare a fresh packet if needed.
Input/packet validation errors fail closed. A successful receipt proves local
artifact/configuration preservation and synthetic rehearsal only.

## Deployment barrier

The captured metadata inventory is complete within #0036's scope. Effective
edge observations are capture-time inputs without an atomic provider fence;
they are not HTTPS behavior qualification. Retained-version restoration and
changed-secret preservation semantics have not been rehearsed on the provider.
There is no current readback of production state or either production durable
gate. The offline receipt therefore keeps `providerRestorationVerified`,
`changedSecretSemanticsVerified`, `productionStateVerified` and
`deploymentAllowed` false. Synthetic gate snapshots must never replace those
production checks.

The original capture returns 401/404/404 on the intended three GET paths; its
missing existing-photo handlers remain missing. No route substitution or
fallback is introduced. #0037 remains unqualified. #0044 packet review and
#0045 concrete authorization cannot treat this offline receipt as provider
restoration proof. Deployment stays prohibited until retained-version/secret
preservation, effective edge/current configuration and both current paused
durable gates are independently established for the exact execution packet.
If a simple exact restoration cannot be demonstrated, return to design.

## Return-to-design handoff: finite preservation protocol

This is the concrete remaining Bot protocol for independent packet review. It
has not been executed on a provider and does not authorize that execution.
The local packet and refusal-path rehearsal pass; exact provider restoration
acceptance remains open. There is no owner access or architecture decision
identified by this gap alone. Bot can prepare the provider adapter and synthetic
rehearsal packet within the later authorized work; #0044/#0045 retain their gates.

**Selected restoration mechanism.** Select the retained version identified by
the private `pinnedActiveVersionWeights` map, whose single entry has weight100.
The prospective operation is
`POST /accounts/{account_id}/workers/scripts/{script_name}/deployments?force=false`,
with `strategy: "percentage"` and that exact version's `version_id`/`percentage`
pair. Resolve all identifiers from the verified private capture; never choose
the latest version, an unversioned download or a rebuilt upload. The provider
API documents this deployment shape and a force override for changed-secret
refusals; this protocol always leaves that override disabled.
([Deployment API](https://developers.cloudflare.com/api/resources/workers/subresources/scripts/subresources/deployments/methods/create/))

Provider rollback selects code while connected resources persist. Missing or
incompatible resources can prevent it. Therefore version selection cannot
restore database contents, deleted resources or historical mutable secret values.
([Rollback boundaries](https://developers.cloudflare.com/workers/versions-and-deployments/rollbacks/))

1. **Freeze and bind the packet.** Before a future mutation, refresh the same
   finite #0036 metadata endpoints and complete every returned ruleset page and
   configured descendant. Privately compare active version/weights, module hash,
   binding references, runtime/settings, domain/routes and effective edge inputs
   with the reviewed baseline. Record the exact retained target as still
   available. Drift requires a new capture and review; do not overwrite the old
   evidence or patch an unexpected production setting to make it match.
2. **Prove continuity before installation.** Record unchanged production D1 ID,
   schema/migration identity, Durable Object namespace/class lifecycle, assets
   and secret-reference identities. No schema, object lifecycle, secret value,
   secret generation, attachment or existing resource changes belong to the
   temporary qualification attempt. Read both deployment/user durable gate rows
   through the already reviewed read-only evidence path; require exactly the
   intended scopes, `enabled=0` and valid pinned revisions. Do not infer them
   from intake/dispatch environment flags. An unavailable observation aborts
   before installation.
3. **Qualify provider semantics separately with synthetic resources.** Prepare
   two isolated nonproduction cases, each with a private exact-identity journal,
   synthetic data, paused gates and its own retained baseline/temporary version.
   Case A keeps every resource/secret reference and synthetic value unchanged:
   one temporary deployment, one latched restore to its explicit retained
   baseline with `force=false`, then exact deployment/configuration/data readback.
   Case B changes only one declared synthetic secret after the temporary
   deployment, then attempts that same nonforced restore once. A refusal must
   leave active state accounted for; an unexpected success must be measured for
   actual reference/value semantics and cannot be treated as historical secret
   restoration. Use synthetic marker comparisons that emit only booleans, not
   values. Cover each captured secret binding type; a normal Worker secret case
   alone cannot establish Secrets Store mutable-reference behavior. No real
   secret is changed or exported. These cases remain future provider work.
4. **Require the preservation result before a production attempt.** Case A must
   preserve exact synthetic database rows/schema, binding/resource identities,
   capabilities and both paused gate values/revisions. Case B must establish a
   detectable refusal or explicitly measured drift outcome; it must never
   justify forcing an older secret configuration into service. If the adapter
   cannot distinguish changed-secret/resource drift before the production
   attempt, stop and return to design. Nonproduction remapped resource IDs prove
   provider semantics only; they are not exact production configuration proof.
5. **Restore and inspect within the later authorized lifecycle.** Disable and
   inspect this run's durable qualification admission first. Latch the one
   nonforced retained-target deployment request before sending it. Independently
   read the active deployment after acknowledgment, then re-read exact target
   module/configuration, all retained binding/resource references and the
   finite effective edge inventory. Require the original weight100 target and
   no temporary qualification bindings. The currently implemented local
   rehearsal supplies rollback route-conformance inputs; the reviewed future
   packet must also name finite authenticated read checks and edge observations
   that avoid Flickr calls, protected mutation and maintenance side effects.
   Their absence keeps ordinary/provider conformance incomplete.
6. **Reconcile data and retire only acknowledged temporary resources.** Compare
   before/after schema and durable production facts using a reviewed bounded
   read-only consistency proof; row counts alone cannot prove unchanged data.
   Require both paused gate rows/revisions unchanged and no credential,
   suppression, admission, intent or dispatch fact lost or added by this
   attempt. Background work must be accounted for or quiesced under its own
   approved mechanism; unexplained drift cannot be normalized away. Only after
   every restoration check passes may #0042 remove this run's acknowledged
   temporary Actions secrets, receiver and synthetic D1 by exact journaled
   identity. Preserve all production resources and original captures.

**Abort and ambiguous outcomes.** A rejected restore, changed secret/reference,
missing resource, new Durable Object lifecycle, digest/edge drift, gate mismatch,
expired scope, cancellation or unknown response leaves `cleanup_unconfirmed`.
Timeout after a latched request allows bounded read-only reconciliation of the
exact request/active deployment, never an automatic retry or forced rollback.
Keep qualification admission disabled, both production write gates paused and
the private journal/resources available for investigation. If any gate cannot
be observed as paused, report that failure rather than claim it was paused.
No repair write, alternate version, new route, resource recreation, secret
replacement or historical data restore is a fallback in this protocol.

**Evidence and acceptance.** Retain private before/after manifests, synthetic
case receipts, request latch/acknowledgment records, exact version/module and
resource comparisons, current edge observations, authenticated read results,
consistent data proof and both durable gate readbacks. Public evidence contains
only digests, booleans, bounded counts and retrieval references. An independent
reviewer must match each result to the exact packet and separate synthetic
provider semantics from production readback. Until the future authorized
execution produces all applicable results, the four false verification/permission
fields above stay false and this is an explicit return-to-design handoff,
not an exact-provider-restoration pass.

Related evidence and boundaries: [capture inventory](existing-photo-inventory-2026-10-16.md),
[split isolation](fixed-origin-isolation-2026-10-16.md),
[lifecycle](fixed-origin-lifecycle-2026-10-17.md).
