# Fixed-origin packet lifecycle and restoration review

Date: 2026-10-17. Ticket #0044. Independent review of the offline packet inputs.
Status: **NO-GO for deployment or native execution.** Offline lifecycle checks
pass within their stated scope; provider restoration, exact route conformance
and the supported effective-path qualification remain unproved.

This review supplies evidence and concrete remaining work. It does not accept
the Proposed thumbnail contract, authorize a provider experiment, widen the
resource inventory or reopen completed implementation cards. Card #0044 was
verified In Progress through the shared CLI before review.

## Reviewed offline lifecycle

The source uses one 32-lowercase-hex run, a private SQLite journal and an
exclusive ownership marker. Each operation is committed as attempted before
its injected seam is called. A missing acknowledgment cannot become a second
create, install, restore or delete. Scope mismatch and a retained owner marker
refuse work; a crashed marker requires explicit reconciliation, never an
assumption that it is stale.

The finite inventory is one new synthetic D1 and one receiver Worker, the two
temporary Actions secret names and the five qualification bindings listed in
[the lifecycle record](fixed-origin-lifecycle-2026-10-17.md). All four fresh
resource/secret names require absence before creation. Only acknowledged exact
identities may be deleted. The production Worker retains its existing
whole-host attachment; new routes, domains, DNS records, production schema or
resource changes are outside the proposed attempt.

The current composition supports the complete twenty-case handler matrix and
ten post-handler edge cases. The earlier lifecycle record's statement that
full twenty-case integration remains #0041 work describes the earlier scope;
the current source and focused tests now establish that integration offline.
That progress does not supply a deployable provider adapter or live evidence.

Durable conditional SQL admits at most 96 FGA requests and 16 combined
receiver/report requests. Same-origin receive/report forwarding consumes the
FGA total before the receiver's separate admission. Ordinary dispatch preserves
the captured Request and environment without quota or receiver access.
Replacement writes cannot reset or reenable the singleton. The maximum
ten-minute inner qualification window fits inside the twenty-minute outer
resource window; expiry stops admission and publication, not restoration or
deletion. These counters bound admitted fixture work, not provider billing.

The composition rechecks expiry and the original request signal after awaited
scope/admission/publication reads. It passes the original signal to the narrow
receiver service binding and cancels suppressed bodies. These are tested local
request fences; they do not establish native GET abort, provider disconnect or
remotely stopped work.

Cleanup durably disables admission, inspects the matching disabled run, requires
the exact captured restore receipt and only then removes acknowledged temporary
identities in reverse order. Failed disable inspection, restoration, unknown
creation or unconfirmed deletion retains `cleanup_unconfirmed`; subsequent
cleanup reads that terminal result without replay. The model deliberately
offers no automatic recovery of ambiguous operations.

The Python CLI refuses execution and accepts only an `offline: true` operations
seam. Its `ordinaryRoutesVerified`, `writeGatesDisabled`,
`productionStateUnchanged` and deletion acknowledgments are injected model
results. They establish neither current provider state nor a usable live
cleanup implementation. A future provider adapter must bind each one-attempt
request and acknowledgment to the private exact identity and configuration;
an ambiguous result permits bounded read-only reconciliation, never mutation
replay, alternate-version selection or forced rollback.

## Concrete unmet restoration conditions

The [#0043 restoration record](fixed-origin-restoration-2026-10-17.md) remains
negative for provider restoration. Its exact capture preservation and local VM
replay do not provide these missing results:

- Synthetic provider Case A: one nonforced restore to the explicit retained
  baseline, preserving exact synthetic schema/data, binding/resource identities,
  secret references and both paused durable gate values/revisions.
- Synthetic Case B for each captured secret-binding type: a declared changed
  synthetic secret and one nonforced retained-target restore, establishing a
  detectable refusal or explicitly measured drift. One ordinary Worker secret
  case cannot prove mutable Secrets Store reference semantics.
- Fresh exact production inventory, retained version availability, full active
  version/weight map, module/configuration/binding references and effective edge
  inputs, privately compared with the reviewed capture before installation and
  independently after restoration. Capture-time inputs have no atomic provider
  fence and are not current HTTPS edge behavior evidence.
- Both current production deployment/user durable gate rows, intended scopes,
  `enabled=0` and pinned revisions. Environment intake/dispatch flags and the
  offline fixture's paused rows cannot stand in for these readbacks.
- Finite authenticated ordinary-route reads that avoid Flickr, protected
  mutation and maintenance side effects; plus a bounded consistent before/after
  production-data proof covering schema and durable credential, suppression,
  admission, intent and dispatch facts. Row counts alone do not prove
  preservation; unexplained background drift cannot be normalized away.
- Actual admission-off, exact retained-target restoration, binding absence,
  resource/secret deletion and matching-run local target/cache removal receipts.
  A native terminal receipt cannot prove remote cleanup.

The proposed two synthetic provider cases require their own explicit resource,
secret, request and cleanup inventory before execution. They are prerequisites
to establishing semantics, not hidden additions to the one D1/one receiver
production-qualification inventory. The current offline work authorizes neither
case. If continuity or secret/resource drift cannot be detected before the
production attempt, the recorded response is return to design.

The future provider ownership protocol must also establish that the two fixed
Actions secret names cannot overwrite another operator's intervening creation.
The offline model's `absent()` and `create()` calls are separate; a successful
absence preflight alone is not a concurrency proof. Its local owner marker
serializes users of that private journal, not other provider operators. The
adapter must prove no overwrite and exact acknowledged ownership at cleanup;
the current missing adapter supplies no such provider claim.

## Required route-conformance evidence

The accepted architecture [HTTP route-conformance contract](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/operations/http-route-conformance.md)
requires all five phases for the exact temporary artifact and the exact
rollback artifact:

1. Generate and validate the inventory from the compiled route registry.
2. Project the exact development/deployment routing configurations, proving
   first-match ownership and asset/shell reachability.
3. Run the complete safe matrix over HTTP through the built development
   topology.
4. Run that same build/matrix through an isolated provider preview's public
   HTTPS edge.
5. Bind the result to application build ID, inventory, development-router and
   deployment-artifact digests, opaque preview deployment identity and pass time.

No phase may be absent, skipped, stale or inconclusive. The contract includes
rollback artifacts and provides no production-only or skipped-preview exception.
The #0043 twenty-five-route VM refusal comparison supplies useful inputs; it is
not development HTTP or preview HTTPS conformance and does not exercise all
authenticated routes, assets or scheduled work.

The repository's current `scripts/route_conformance.py` builds
`probes/routes/worker.ts`, labels its scope `isolated-routing-proof` and sets
`productionConformance: false`. Its historical fixture/configuration cannot
approve the temporary composition or captured rollback. A packet must supply
the exact required adapter/artifacts and phase receipts, with an independently
reviewed finite preview lifecycle. Preview resources are not implicitly
authorized by the current production-qualification resource inventory. Merely
requesting permission to change the production Worker does not close this gap.

## Verification and disposition

Fresh independent checks used pinned Node24.22.0, pinned uv0.12.5 and the private
#0038 parent-final fixture. The fixture/source digests are checked by the actual
composition suite before execution. Results:

- 11 Python lifecycle tests passed: journal scope, exact identities, name
  absence, ambiguous create/delete, ownership exclusion, expiry, admission-off
  and restore barriers, no replay, cleanup after failure and disabled CLI.
- 40 Node quota/composition tests passed with real SQLite and the actual pinned
  candidate/captured modules. They cover the complete handler matrix, SQL
  replacement refusal, concurrent 96/16 admission, ordinary dispatcher identity,
  receiver forwarding and all delayed scope/admission/publication expiry/abort
  boundaries.
- Static review matched the lifecycle, quota, receiver and composition to the
  restoration protocol and accepted route phases. The provider-capable
  route-conformance command was inspected but not run.

The initial Node invocation omitted the required fixture environment and
correctly refused; the corrected invocation passed all forty tests. Sandbox uv
cache access failed, and the scoped authorized retry passed without updating
tools. Detailed commands and private evidence references stay in workspace
`work-batch-2026-10-17-next`; no raw captures, secret values or provider output
belong in this public note.

The missing supported effective-path allocation and credential-protection
method in [#0037's verdict](fixed-origin-feasibility-verdict-2026-10-16.md) is
also unresolved. Successful finite native/edge samples or cleanup rehearsals
cannot qualify unknown provider response bounds. `providerRestorationVerified`,
`changedSecretSemanticsVerified`, `productionStateVerified`,
`deploymentAllowed`, transport qualification and production capability remain
false. #0044 can hand off a concrete no-go; #0045 cannot turn these absent
engineering results into evidence by granting generic owner permission.

## Final packet delta review

Independently read the assembled
[execution packet](fixed-origin-execution-packet-2026-10-17.md), including its
source inventory, five route phases, separate synthetic provider A/B scope,
missing deployable configuration and exact preservation/cleanup barriers. These
claims correctly keep the local model distinct from provider proof. Its newly
identified schedule gap is material: thirty four-request fault invocations
already exceed 96 admissions, before browser/receiver/terminal observations;
the once-only consumed target also prevents treating separate invocations as
an executable schedule. The packet's no-go is therefore supported independently
of the restoration and route gaps recorded above. No generic execution
authorization can resolve those missing artifact/schedule/evidence definitions.
