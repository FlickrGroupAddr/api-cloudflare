# Bounded local delivery path proof - 2026-10-18

Ticket #0183. Status: source-only conditional proof and inert candidate reviewed;
no live binding, credential delivery or physical custody qualification.

The [standalone probe](../../probes/local-delivery-path-proof/README.md) contains
the reviewed guard, complete Win32 facade, effect orchestration and injected
regressions. Its main entry is unconditionally NO APPLY. Trusted synthetic API
injection is a test seam, not a sandbox against trusted Python code.

## Corrected source properties

- Directory opens request FILE_LIST_DIRECTORY in addition to metadata/security
  access so that the intended sharing check participates.
- Attribute/EA grants need separate checks. Share denial alone does not cover
  them; reparse mutation can use WRITE_DATA or WRITE_ATTRIBUTES.
- Public ancestor read/traverse and exclusive child creation are distinguished
  from untrusted repoint, attribute/EA, delete and security mutation rights.
  The exact Windows servicing owner is recognized only at the volume root.
- Full held parent chains, same-handle security/identity, final normalized path,
  disk/local-NTFS/persistent-ACL properties and distinct same-volume file IDs
  precede the modeled read/write operation.
- Protected CREATE_NEW has no existing-file fallback. Read-attempt accounting,
  deadlines immediately before effects and partial/unknown write/flush/cleanup
  outcomes remain explicit. Failure is not proof that no output was reserved.

The contract assumes ordinary trusted-local-host operation: trusted principals
preserve namespace/security during the bounded operation. Universal absence of
previous privileged handles is not proved or introduced as a new owner gate.
Actual untrusted mutation rights remain refusals. No Windows permissions change
or new credential is recommended by this source record.

## Verification

Fresh independent High review passed the final source pair and tests with no
unresolved findings. Thirty-eight tests passed: seventeen guard-model and twenty-
one orchestration/native-contract cases, including partial-open and internal
size-refusal cleanup exceptions. Ruff check/format and the repository's standard
Pyright Windows/Python 3.14 policy passed; staging changed import/environment
paths only. All APIs and values were injected synthetic fixtures, not real OS
bindings or credential paths.

The predecessor local attempt had zero credential reads/copies. The old successor
and its HOLD evidence remain preserved; this probe does not retroactively qualify
it or authorize replay. The previous fifteen-minute local window expired. Terry
explicitly retained the same protected token for later separately approved uses;
provider expiry and later revocation responsibilities remain unchanged.

## Remaining work

#0161 must integrate and independently review an exact source/action binding
before requesting a fresh local window. Real source/destination custody,
provenance, fingerprints and effective paths remain private and unqualified here.
No credential read, marker mutation, native fixture, account/DNS/provider request
or final POST action is authorized by this record or by passing its tests.

Primary Windows references include [CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew),
[MS-FSA access/share processing](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-fsa/8c0e3f4f-0729-49f4-a14d-7f7add593819),
and [FSCTL_SET_REPARSE_POINT access processing](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-fsa/4aeefef8-92c3-4abc-af7a-a610caf8a165).
Source review distinguishes those API contracts from actual host observations.

A held child/nonempty parent alone is not used to relax metadata rights. The
[WDK nonempty-directory reparse contract](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/ns-ntifs-_open_reparse_list_entry)
recognizes exception classes; no all-tags prevention proof is claimed from the
generic empty-directory rule. The conservative metadata guard remains unchanged.
