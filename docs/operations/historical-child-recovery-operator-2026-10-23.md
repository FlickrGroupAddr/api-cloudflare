# Historical-child recovery operator adapters

Date: 2026-10-23. Source implementation; actual readiness remains unconfirmed.

`scripts/historical_child_recovery_operator.py` supplies the concrete filesystem,
source/import, retained-evidence, namespace, parent-read and TLS adapters for the
[accepted recovery controller](historical-child-recovery-source-2026-10-23.md).
Import and CLI perform no protected inspection or execution. The existing
controller runtime body and frozen producer are unchanged. The controller's
required `transport` argument now explicitly permits `None` in its type/docstring
for the qualified original TLS selection below. The historical turn-19 source pin
remains historical evidence; the current controller has its own fresh pin.

## Primary's trust boundary

The primary constructs `ReviewedFacts` only after authenticating the actual
retained original evidence, current observations and independent judgment.
There is no JSON-to-PASS converter. The binding retains the independently
reviewed request digest, original producer source map, historical/current role
digests, explicit named supporting-evidence references and, before dispatch,
the independent actual packet-review reference.

The seven references support exact identity/custody, consumer termination,
cleanup-caller termination, permanent no-readmission, preservation of unknown
resources, actual parent lifetime, and applicability of the standing authority.
Each references an exact private file with an independently authenticated digest.
One genuine record may support several meanings; repeated identical path/digest
references are inventoried once. Alternate spellings or file-identity aliases to
different paths still refuse. No new attestation is required merely to fill a slot.
The existing current witness's `evidenceReference` contains
`sha2-256:<digest>` for the canonical named path/digest map produced by
`fact_reference`. This binds the support roles to the reviewed request without
adding a signature, a new authority decision or a second retirement latch.
Their paths and meanings must be included in the primary's actual packet review.
A hash, a local file, a JSON assertion, elapsed expiry or disappearance of a
process cannot authenticate those facts. The primary retains the ordinary
observation/review artifacts and evaluates their scope and provenance; the
software neither invents observations nor requires a new signing service.

This source supplies the concrete adapters. Actual current observations and
their independent authentication are still factual inputs, not unfinished
adapters. The original terminal bytes and timestamp remain historical evidence.
No source PASS supplies native/account qualification or revocation evidence.

## Concrete boundaries

- Construction binds the complete independently retained original producer
  source map plus the separate current controller and operator files. Source
  files receive exact regular-file/link/ancestor/stable-read/hash checks before
  project imports or protected reads. The original producer pin stays unchanged.
- Imports execute checked source bytes in a private module graph. Project imports
  cannot resolve an ambient `scripts` module or an unpinned file. Non-stdlib
  imports refuse. Loaded source functions and module identities are rechecked;
  declared function/class/method bindings and pinned bootstrap imports/constants
  reject foreign replacements. Private reads check the inventoried file identity
  both before and after the reused stable reader.
  The reviewed interpreter and standard library remain trusted runtime inputs.
- Inventory names only the closed controller roles and the exact supporting
  evidence files. Windows path spelling, case aliases, overlapping roots, links,
  reparse points, hardlinks, file identities and existing SQLite sidecars refuse.
  The existing producer-closure private ACL checker and bounded stable private
  reader are reused. There is no directory listing, credential discovery or ACL
  repair. Credential roles are inventory-only during preparation.
- Original latch inspection deserializes a bounded stable private SQLite read
  into an in-memory query-only database. It checks the original digest and
  acknowledged child before reporting the original `issuer:retire` state. It
  acquires no owner lock and creates or changes no live SQLite file or sidecar.
  The unchanged producer's atomic reservation remains the sole retirement latch.
- Namespace reservation uses exclusive directory creation and private ACL checks.
  Only the three exact controller metadata files may be exclusively created,
  durably flushed and verified. Failure retains the namespace and any bytes;
  the writer provides no overwrite, repair, cleanup or retry path.
- Explicit `Operator.dispatch(..., execute=True)` revalidates actual current
  evidence, packet and original latch before obtaining the pinned producer, then
  uses the unchanged controller and producer. It supplies the exact parent-only
  loader and explicitly selects the verified producer's original TLS branch by
  supplying `transport=None` as the required controller argument. This deliberate
  selection preserves the original numeric-address parsing and its closed-over
  source/approval/clock fence at connect, TLS and send stages. The operator installs
  no replacement TLS wrapper or ambient module lookup. It supplies no
  fallback credential, child read, provider discovery or replay.

## Later primary operation

1. Authenticate and retain the original immutable history/source map and genuine
   current factual evidence. Confirm the actual parent lifetime and unchanged
   cutoff, custody, authority, stopped consumers and cleanup callers, permanent
   no-readmission, preserved unknown resources and unused original latch.
2. Choose a new exclusive recovery identity and namespace. Freeze all role and
   source pins, supporting-evidence paths/digests, one fixed interval and
   independent current judgment. All current observations, judgment, preparation,
   final review and dispatch must fit the same `[start,end)` interval of at most
   600 seconds and before the unchanged parent ceiling.
3. Construct `Operator(request_bytes, facts=authenticated_binding)`. Call the
   unchanged `recovery.prepare` and `recovery.write_preparation` with this operator
   as verifier and writer. These methods make no provider or credential read.
4. Obtain independent actual final packet review, retain its authenticated exact
   path/digest in the binding and construct a dispatch operator for the same
   request. Call its explicit dispatch method with actual UTC and monotonic
   clocks, final review bytes and `execute=True` only when all gates still hold.
   There is no executable command-line shortcut or automatic timing refresh.
5. Independently reconcile the five-call maximum, wire accounting and original
   latch. Preserve unknowns and spent attempts. A DELETE acknowledgement does not
   prove resource cleanup, physical erasure, positive POST evidence or #0061
   qualification.

The private fresh packet source deliberately contains missing values and refuses
execution. It supplies no credentials, current observations, actual namespace,
fresh witness, actual packet review, executable budget or affirmative facts.
The stopped historical run, old namespaces and expired claims remain untouched.

## Verification scope

Synthetic tests use invented evidence and temporary files. Socket and DNS access
are blocked by the existing fixture. The tests exercise exact-byte isolated
imports, actual SQLite latch reads, preparation/refusal behavior, identity and
source drift, evidence/path gates and exclusive writer/no-retry behavior.
Temporary ACL assertions are intercepted; tests do not qualify actual ACLs,
protected paths, genuine facts, provider status, a native session or POST.
