# Native disposition and reconciliation source

Source/synthetic implementation under accepted PMB-1, ADR0065 and ADR0066.
This directory registers no Worker, route or RPC and performs no bootstrap,
mutation, retirement, close, reopen, retry, deployment or provider call itself.
Actual qualification and actual action eligibility remain separate and unproved.

`NativeMainEntryObserver` implements the existing `MainEntryObserver`. It reads
both complete external #0243 journal relations under one unchanged stopped
revision, retains full records and reconciles all invocation/effect ownership.
Every handler/effect must have a terminal affirmative local return. Unknown,
rejected, orphan, late, mismatched or pending facts refuse, including after restart.
One final journal bracket follows the complete independent domain acquisition.

`D1DomainReader` uses the native D1 `first-primary` session to obtain the exact
717-record prospective observable schema and all 65 included application tables.
Fixed SQL preflights bound rows and serialized facts before data materializes.
Every INTEGER is converted to canonical decimal TEXT at its SQL source; text and
blob source bytes use hexadecimal. REAL, unknown types, schema drift, unexpected
control population/state/generation, deadline loss and failed reads refuse.
The separately selected ADR0064 `_cf_KV` contents remain excluded; its exact
observable metadata is included. The JSON plan is mechanically extracted from
the already reviewed prospective source manifests and never inferred from the
database being assessed.

Domain validation retains every typed field and inspects native credential and
connection ownership, completed lifecycle results, retired OAuth generations,
Google refresh ownership, group work, D1 transaction obligations, rates, attempt
resolutions/permanent blocks, and admitted album operation phases. Ambiguous and
in-progress outcomes refuse. Queued, unadmitted work remains persisted ordinary
state; a source mechanism does not erase or execute it to manufacture drain.

`NativePartitionDisposition.verify` composes the completed #0245 concrete native
factory and `captureSupportedBoundary`, including complete population, supported
SQL/KV/alarm state, source manifests, external control and original finite bounds.
It checks all captured objects, invocation/domain tuples and exact generation
before returning the existing typed disposition. The accepted object boundary is
only `pmb1-private-object-kv-interface-v1`: raw `__cf_kv` contents/rowids remain
unobserved, unfrozen and unverified. The factory's unknown/once-only behavior is
preserved. A failed attempt is spent and cannot acquire again through this object.

`reconcile` reads the exact original local token under a native transaction and
pre-acquisition byte bound, reconciles its retained claim/lease/attempt tuple and
grant safety result against the complete independently read D1 facts, and rereads
the unchanged local record. It requires separately authenticated native retirement
and terminal-operation custody for that exact old execution. Its return plugs into
the existing `PartitionMaintenance.reconcile`, which records local disposition
without replaying claims, provider dispatch, resolution, retirement or rate release.
No current generation, receipt string, alarm absence or timeout substitutes for
old execution/pending-D1 evidence.

Settled restart records must retain a valid original receipt. Every original
attempt/result field is compared with the complete independent typed domain
facts, including reason/code, dispatch marker, suppression, reservations and
grant retirement/supersession indicators. Active records may acquire their first
receipt only after the original tuple and all domain safety results are proven.
Later ownership changes that no longer match an old receipt refuse; the observer
does not rewrite historical indicators or infer a replacement receipt.

`ReviewedCoverage` is a TRUSTED Primary/independent-reviewer input boundary,
analogous to #0244's `ReviewedAdmission`. It has no JSON/environment/HTTP/packet
loader, default or arbitrary verifier callback. The caller must authenticate the
separately retained actual census, exact source/version/fence meaning, complete
resource/holder custody, and exact native terminal records before construction.
The class compares enumerated writers, versions, source identities, resource IDs
and finite custody intervals against independently retained expectations. It
checks binding and consistency; neither strings nor hashes authenticate truth.
The ordinary application scopes/journal and object generation gates fence old
callbacks. No global process enumeration or provider drain API is invented.

Public observer results retain full private evidence via `retainedEvidence()`;
the digest identifies those facts and does not establish independence. Never log
that evidence. Callers own its protected retention and independent validation.

Constructors are inert. Native database identity/session/transaction/int64 source
semantics, source and deployed writer completeness, actual supported population,
external metadata, effective custody/embargo/retirement, clock domain and full
resource/request/response/heap/deadline footprint still require positive actual
qualification. Every test uses invented records and local SQLite/storage-shaped
fixtures. No source or synthetic success is an all-store or native PASS.

New future D1 control selection stays
`fixed_update_with_exact_count_positional_v1`. This reader sends SELECT only.
Historical named/default controls, Completed source and ordering remain intact.
The caller still orders stop, mandatory settlement, close, readback and the common
closed interval; none is inferred or performed by these observation adapters.
All extra journal/domain/native-control reads and resource effects belong in the
later #0187/#0201 counted campaign packet; this source grants no budget.

Validation with the preinstalled Node24.22 and native TypeScript7.0.2:

```text
node --test probes/pmb1-native-disposition/*.test.mjs
node node_modules/typescript/bin/tsc -p probes/pmb1-native-disposition/tsconfig.json
```

The native fixture calls the actual unchanged #0245 source factory/read adapter;
it does not replace the verifier with a success callback. Main-entry positive
tests use real #0243 guarded SQL and complete prospective D1 source. Boundary
tests cover pending bodies/cancellation, source/schema/control/custody/version
drift, restart ownership, exact tuple substitution and unknown/late reads.
