# Catalog outbox host-proof review and checklist

Date: 2026-10-15. Status: independent implementation-readiness review for the
bounded catalog-property probe. No owner acceptance, live-host persistence
qualification, production outbox or storage guarantee is asserted here.

Companion: [persistence-boundary research](lrc15-outbox-persistence-boundary.md).
The architecture repository's `AGENTS.md`, `docs/README.md`, accepted ADRs
0011/0012/0045 and plug-in/service contract control. Research cannot amend them.

## Decision-ready conclusion

The smallest useful proof remains one bounded versioned JSON string in one
catalog-wide plug-in property, changed through a synchronous private write
gate. It uses documented catalog APIs and avoids custom file-journal machinery.
Keep it separate from editable per-photo selection metadata. A source inspection
supports the capability choice; actual isolated-host observations must establish
the behavior attributed to the running host. A successful immediate readback
alone establishes neither restart persistence nor crash durability.

Do not treat a successful fixture proof as production outbox acceptance. It
answers whether this host supports this private catalog-property behavior for
this fixture. Production retention, bounds, recovery, conflict and restore
semantics remain separately testable implementation work.

## Exact SDK boundary reviewed

Local Adobe SDK 15.3 API Reference,
`C:\Projects\FGA\architecture-design\vendor\LrC SDK\15.3\API Reference\modules\LrCatalog.html`:

| Location | Supported statement | Unsupported inference |
| --- | --- | --- |
| `getPropertyForPlugin`, line 1367 | Reads previously set plug-in-specific catalog data. | A value read twice is necessarily flushed to stable storage. |
| `setPropertyForPlugin`, line 1551 | Stores undeclared catalog-wide scalar values including a string; requires one of the `with___WriteAccessDo` gates. | A table can be stored directly, or a separate metadata declaration is needed. |
| `withPrivateWriteAccessDo`, line 1719 | Supports plug-in metadata changes without ordinary undo and serializes catalog access. | Every rollback/commit/flush promise documented for the ordinary gate automatically appears in the private-gate contract. |
| Private gate return, line 1739 | Synchronous mode returns executed/aborted; queued belongs to asynchronous mode. | Queued, missing, thrown or aborted return means durable completion. |
| `withWriteAccessDo`, line 1801 | Explicitly documents error rollback and application after successful callback completion. | Switching the outbox to the ordinary undoable gate is harmless if private behavior fails. |

`LrTasks.pcall` protects yielding SDK operations; a raw Lua `pcall` fake only
tests control flow. Do not add hidden catalog SQL, undocumented flushing APIs,
SDK UUID generation or a native helper to make this small proof appear stronger.
Use the current SDK15.3 reference confirmed by Terry on this date and qualify
the installed Lightroom Classic15.6/Camera Raw18.7 build
`202609251514-f839cde9` separately from older diagnostics.

## Smallest safe host sequence

The parent owns the live UI. This review performs no host/catalog mutation.

1. Create a new empty fixture catalog named `FGA-Outbox-Probe.lrcat` in a
   deliberately chosen disposable location. Keep the production catalog closed.
   Record the fixture identity privately. A matching leaf filename is only a
   mistake-prevention guard, not proof a catalog is empty or safe.
2. Load the exact standalone probe build, verifying its incremented `Info.lua`
   VERSION and installed host version. Start the bounded receipt monitor before
   invoking a visible command. Do not load a changed runtime under the previous
   version number.
3. Run the private write/rollback command once. Bind its receipt and catalog
   value to one explicit synthetic run identifier. A fixed reusable fixture
   string can otherwise produce a misleading restart pass from an older run.
   The identifier is non-secret correlation, not cryptographic entropy.
4. Check synchronous executed status and exact immediate readback. Deliberately
   throw after a different property replacement, catch the failure outside the
   gate, and verify the original exact run value remains. Retain both actual
   observations separately. If either fails, stop; do not compensate the catalog
   to manufacture a passing receipt.
5. Close normally, independently observe host shutdown, reopen the same fixture
   catalog and verify the same run value. Receipt verification alone cannot
   prove a restart occurred. Preserve external lifecycle evidence rather than
   having the command label itself a restart success.
6. Use a separate identified fixture run for abrupt process-stop observation.
   Confirm only the disposable catalog is active and no production-catalog
   process is present before any termination. If that cannot be established,
   defer this operation. Never force-terminate a host using a real catalog.
   Record stop method, receipt stage and restarted exact-value observation.
   This is process-crash evidence, not a disk or power-cut test.
7. Retain the fixture and sanitized receipts for review. No photo upload,
   credential access, group call, ordinary photo catalog write, catalog cleanup
   or deletion belongs to the proof. Failure is useful evidence; preserve it.

The current minimal probe does not by itself exercise timeout contention,
concurrent compare-and-set updates, disk-full behavior, record bounds, backup
restore or all intermediate upload/handoff crash points. Those omissions must
remain visible in the handoff.

## Receipt acceptance checklist

- A fresh complete JSON document records schema/probe/build/phase/run identity,
  time, host version and sanitized outcome codes. No raw exception text, catalog
  path, photo metadata, credentials or envelope fields are needed.
- The receipt is written after success and caught failure, including a failed
  catalog guard. A stale earlier success is distinguishable from this command.
- Publish the receipt only after the complete document closes. Receipt I/O is
  separate observation, not the outbox's durable storage authority; a receipt
  write failure must not become a false catalog-state success.
- Same-session, rollback, normal-restart and abrupt-stop results are distinct.
  Missing, malformed, stale or wrong-run receipts are unconfirmed observations.
- The observer records lifecycle actions separately. A matching catalog property
  is evidence of persistence only across the independently observed lifecycle.

No actual host outcome is recorded in this review. Incorporate the parent's
sanitized observed results into the companion research only after they exist.

Independent source review of probe build `0.0.2.3` confirmed the receipt contract
now supplies UTC write time, bounded documented host version/build context,
fixed probe version, and distinct stage/whole-command terminal flags. A passed
same-session stage is no longer a whole-command terminal result before rollback.
Ten injected Lua5.1 tests pass independently. Those corrections resolve the
earlier missing-provenance and premature-terminal findings. A null timestamp
or invalid host context remains unqualified evidence as the probe README states.
SDK timestamp components may retain fractional seconds; a precision policy
that floors validated seconds would avoid unnecessarily null write times.

## Restore gap requiring an explicit production rule

A restored catalog can contain an old pre-dispatch record or no local record
even though a later version of that catalog already dispatched an upload.
Restricting uncertainty handling to restored `upload_may_have_been_invoked`
records is insufficient. Absence and an older earlier phase do not prove no
image POST occurred. A restored upload authorization is also not single-use
authority, and a candidate query returning nothing is not proof of failure.

Catalog-local state alone cannot detect every copy or restoration that erases
the evidence used to detect it. Production implementation must define the
explicit restore/copy recovery gate and available hosted reconciliation before
resuming pending uploads. Operator knowledge may be required; do not invent an
automatic restore detector or silently treat restored earlier state as fresh.
For already-bound photos, hosted natural keys and fresh proof can support
idempotent downstream recovery. They do not resolve an ambiguous image upload
that has no definitive photo ID.

A bounded fixture restore test should preserve a known earlier snapshot,
advance synthetic phases, restore the earlier snapshot while the host is
closed, and verify the recovery classifier refuses to conclude no dispatch
from absent/older local state. This needs no actual Flickr call or production
catalog. It proves the specified recovery behavior, not a guarantee against
unrecognized historical restoration in an unimplemented production provider.

## Production gates after the capability proof

Define and test record-count/byte limits without evicting unresolved work;
strict schema/version validation; per-record immutable correlation and revision;
whole-record replacement under a non-yielding synchronous gate; aborted/error
and mismatched-readback refusal; compare-and-set against stale callbacks;
matching selection consumption only after durable acknowledged handoff; safe
catalog switch/copy/restore; and explicit storage-full/unavailable behavior.

Exercise upload dispatch-marker/result-write crash points separately from safe
backend idempotent batch retries. No failed backend operation permits image
replay. Preserve normal upload-result catalog-write ordering under ADR0011 and
the distinct photographer-reconciled acknowledgement-before-catalog ordering
under ADR0012. A local record cannot replace hosted identity, album obligations,
retained intent status or permanent group-pair suppression.

Normal and abrupt restart observations can justify a documented conventional
host-storage assumption. They cannot establish arbitrary power-loss durability.
If a stronger storage requirement is proposed, record the requirement and
available evidence explicitly before choosing additional machinery.
