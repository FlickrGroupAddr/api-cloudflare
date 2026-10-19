# PMB-1 source census and closed-interval consistency validator

Date: 2026-10-19. Ticket #0196. Status: inert public source candidate; actual
qualification, deployed census and action readiness remain **false**.

The controlling authority is the accepted
[PMB-1 contract](prospective-maintenance-contract-decision-2026-10-18.md),
particularly its future-artifact, all-writer, common-interval and reopen clauses.
This source neither changes that contract nor passes #0182/#0163.

## Frozen public scope

[The manifest](../../probes/pmb1-closure-census/source-manifest.json) pins every
public `src/` file, migration, public script source, accepted PMB-1 record, both unregistered #0185/#0186 candidates, package,
lock, compiler configuration and deployment template. It records a reproducible
local esbuild 0.28.1 optimized ESM build of `src/worker.ts`, its exact output
hash/bytes/exports, every third-party build-input digest, imported source graph
and emitted source modules. Node 24.22.0 and native TypeScript 7.0.2 remain pinned.

This is a source-analysis build using explicitly external Node builtins, **not**
a Wrangler/provider artifact, hosted test, deployment configuration read, or the
future maintenance-capable retained target. #0199 must freeze that future
assembly independently after integrating the bridges. Its changed bytes require
a refreshed manifest and review; this manifest cannot claim them in advance.
`freeze.mjs ROOT MANIFEST --check` refuses any source/build-input/output drift.
It reads only public source/dependency bytes and performs an in-memory local build.

[The family census](../../probes/pmb1-closure-census/census.json) binds those pins
to concrete entrypoints, writer families, included store kinds, independent
interfaces and source-ticket obligations. It deliberately retains unresolved
actual discovery. A source template with no queue/service binding is insufficient
to establish that none exists in the effective deployment.

## Reachability and bridge ownership

The exact optimized public build exports `default`, `createWorker`, `safePath`,
`ROUTES`, `PartitionWorker` and `consumePartition`. Exported callable functions
are an adapter/caller surface; they are not additional HTTP routes.

| Source surface | Effects requiring admission, settlement and closure | Named prerequisite |
| --- | --- | --- |
| `worker.ts` fetch, actual registry and pre-registry admin routes | Installation/intake/publication/upload/group/photo/thumbnail routes; browser auth/session/Google/OAuth/plugin codes; audit/quota/rate/status/error/recovery writes; native credential lifecycle and provider results | #0198 |
| Main album binding, obligation, title intent, local removal, create-repair route/store modules | Actual D1 mutations and injected create-repair reader dependency/result effects | #0198, explicitly within its whole-main-handler coverage |
| Main scheduled callback | Status cleanup before dispatch flag check; Google keys/auth/code cleanup/native credential maintenance; group refresh/rate writes; due partition/sweep hints | #0198 |
| `dispatch_worker.ts` class/exported consumer | `/wake` KV binding transaction; `waitUntil` consumption; D1 leases/reservation/dispatch markers/results/permanent suppression/grant-rejection audit; `finally` alarm rearm; native zero-argument alarm recovery | #0197, with #0194 native alarm disposition |
| Fixed D1 operator control/readback | Separate fixed transition, durable external intent, independent full schema/control readback | #0193, reusing #0185 |
| Managed secret replacement/configuration/operator/native stores | Native PATCH and mandatory lifecycle results; effective human/CI/emergency/provider custody, deploy/import/DDL/restore/erasure/guard-removal operations | #0198 for in-artifact call admission/settlement; actual custody and pending-operation evidence remains #0187/#0182 |

`album_attachment_worker`, `album_materialization_worker` and
`album_title_worker` export functions in their own files but are **not imported
or emitted** by this exact main build. Their respective attachment/materialization
stores/transports, title transport, `album_flickr_admission`,
`album_create_repair_discovery`, and `flickr_strict_json` are likewise absent.
The create-repair discovery import in `album_create_repair.ts` is type-only;
actual reader composition is injected. The emitted route/store families listed
above remain included even when feature flags default off.

No additional included standalone album worker family is silently deferred.
#0197/#0198 are concrete source bridge prerequisites for every included family.
If their final scope excludes any listed reachable family, a **named separate
source bridge ticket must be created and made an assembly prerequisite before
#0199 claims completeness**. Importing an absent standalone worker later changes
the candidate and requires that same treatment. Static absence says nothing
about production versions, old callers, active objects or provider facilities.

## Evidence interface and its trust boundary

[validator.ts](../../probes/pmb1-closure-census/validator.ts) is an inert Node
TypeScript function. It accepts an independently retained `Expectations` plan,
untrusted closed-schema receipts and a mandatory `IndependentEvidence` adapter.
There is no network, writer mutation, default verifier, automatic retry,
cleanup or reopen action. Every returned verdict sets `actualQualification:false`,
even for a synthetically consistent packet.

The plan contains the exact candidate digest, complete actual store identities
and exact control generations, per-store writer identities, every admitted
operation requiring disposition, external custodians, ordered capture identities,
restoration/ordinary/equality/cleanup identities and optional separately
authorized reopen identity. Generations use canonical positive int64 decimal
text, including values above JavaScript's safe integer range. Ordering uses
canonical exact integer ticks in one independently qualified order domain;
unrelated client clocks or unsupported order cannot be normalized into evidence.

The adapter must resolve each receipt evidence digest to **independently retained
observations**, with matching candidate, complete normalized expectation-plan
digest, kind, subject, generation and supported coverage boundaries. JSON hashes,
receipt booleans, matching snapshots and a same-writer acknowledgment cannot
authenticate independence, completeness or custody. The adapter must independently
establish the fixed positive meaning of `complete-supported`; the test adapter
only simulates it. A caller that fabricates the plan and adapter can manufacture
synthetic consistency. This checker does not convert such input into evidence.
No signing service or invented global drain API is supplied.

The independently assessed census must cover the **entire** retained plan,
including every actual store/population/writer, admitted operation, automatic
provider metadata, unsupported/unknown state and custody holder. An omitted
store is discoverable only by that qualified actual census; this validator cannot
infer deployed completeness from a list supplied by the same writer. Actual
census adapters, complete readers and qualified ordering/disposition interfaces
are later work and are not implemented here.

Each store requires independent closure and subsequent independent readback
strictly before the interval, mutation-order coverage across the full interval,
per-writer admission/drain and stale-authority coverage, and one completed drain
receipt for each expected admitted operation. All coverage boundaries are closed intervals: drain settlement must end strictly
 before closure begins, and independent readback must begin strictly after closure
 ends. Equal endpoints supply no order. Drain assessment means admission
is off and all admitted external dispatches and required durable safety results
have settled before closure; unresolved results cannot be discarded. Mutation
order assessment means prior mutations committed/aborted before closure and all
later ordinary mutations refuse atomically. It is not a promise inferred from
time, equal state, a generation field or successful close response.

The interval begins strictly after the latest independently confirmed closure
and readback. Baseline, fresh preflight and restored full captures are inside
it in that order. Independent exact retained-target restoration precedes the
ordinary authenticated current-installation check, which precedes the final
capture. The ordinary assessment must prove the accepted exact route/identity/
revision/headers and absence of Flickr, session/quota/audit/maintenance/deferred
included-store writes. Restoration assessment includes nonforced exact target
weight100 and independent admission-off confirmation. Equality assessment means
full accepted typed equality across all included state, not digest/count equality.
Every custody embargo must begin strictly before the earliest included store closure
and remain continuous through the complete common interval/final readback, with no gap.

Reopen consideration additionally follows full equality and authorized cleanup,
lies outside comparison, and requires independent stale-work dispositions through
its entire boundary. Those cover old versions, pre-close/temporary admitted
executions, delayed callbacks, alarm deliveries/retries, queues and direct callers.
Separate authorization belongs to the independent reopen assessment. A closed
state-only guard does not fence stale code after reopening. Any unresolved,
unknown, missing, malformed, unsupported, duplicate or extra receipt refuses;
absence of a reopen request returns no reopen permission.

## Local verification and limits

Thirty-eight synthetic tests cover a consistent finite interval plus missing/unknown store,
writer and admitted-operation evidence, absent or false independent assessment,
wrong artifact/expectation/generation, int64 overflow, schema drift, interval
and embargo gaps, mandatory-result/closure order, readback order, restoration/
ordinary/capture order, equality-only evidence and stale authority at reopen.
They are schema/order/fault checks, not a hosted barrier test.

From the API root with pinned Node on PATH:

```text
node --test probes/pmb1-closure-census/validator.test.mjs
node node_modules/typescript/bin/tsc -p probes/pmb1-closure-census/tsconfig.json --noEmit
node probes/pmb1-closure-census/freeze.mjs . probes/pmb1-closure-census/source-manifest.json --check
```

No private/runtime/configuration/secret/ACL/process/evidence metadata was read;
no provider/account/DNS/native action, schema installation, registration,
deployment, capture or cleanup occurred. Actual full store and writer discovery,
complete SQL/KV/alarm/REAL reading, provider metadata stability, independent
closure/readback/order/drain/custody, retained assembly and action authority remain
unpassed. Source acceptance is useful finite implementation evidence only.


## Independent review corrections

The first High review found custody could start after closure and that equal
closed-interval endpoints could hide overlapping settlement/closure/readback.
The corrected validator requires every embargo before the earliest store closure,
strict settlement-before-close and strict close-before-readback. Seven added
regressions cover each shared endpoint, late custody, and differently ordered
multi-store plans. Actual qualification remains false; independent
re-review passed after correction.

## Independent review and integration

Corrected source passed independent High re-review. Embargo begins strictly
before the earliest closure; settlement and independent readback require strict
nonoverlap with the closure interval. Thirty-eight tests, eighteen independent
fault checks, scoped native TypeScript and frozen source/build verification pass.
The parent reproduced the installed suite, scoped compiler and documented pin
check. JSON consistency and source reachability do not authenticate actual
independent evidence, deployed census or custody. Actual qualification remains
false for every result; #0197/#0198 must cover all included reachable families.
