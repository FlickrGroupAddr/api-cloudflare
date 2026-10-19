# POST local preparation source binding - 2026-10-19

Ticket #0161. Status: concrete deferred source candidate; independent High
review passed. No current packet, local action, credential custody qualification or
native POST measurement is established by this record.

The [isolated candidate](../../probes/post-local-preparation/README.md) integrates
the unchanged reviewed [#0183 implementation](local-delivery-path-proof-2026-10-18.md).
It defines the actual Windows factory without invoking it. Historical helpers,
manifests, claims and evidence remain unchanged. Both command-line entries are
unconditionally NO APPLY. No deployment or production import is registered.

## Implemented source boundary

- An immutable local packet binds one run, process user SID/PID/start generation
  and executable SHA2-256 pin; full exact existing parent chain/private boundary;
  source/destination; source byte pin and expiration; seven distinct exact marker
  paths; claim/receipt; and an absolute window no longer than fifteen minutes.
- Canonical UTF-8 JSON binds the reviewed packet fingerprint. New integration
  source files have exact packet byte pins; the #0183 guard/adapter retain their
  reviewed public byte pins. A fresh actual packet must include the actual
  applicable marker inventory and provenance. A caller-computed fingerprint is
  not proof of owner approval or global historical run uniqueness.
- The deferred factory obtains current process identity from the Windows token,
  process creation time and bounded executable read. It compares the observed
  identity before any credential/marker operation. Read provenance assumes the
  ordinary trusted local host, including trusted interpreter/imports.
- The bound facade reuses reviewed same-handle security, final-path/identity,
  local NTFS/ACL and protected creation plumbing. It explicitly restricts path
  operations to the packet and rejects directory creation. Existing parent
  chains must qualify; source credentials and marker files are never deleted.
- Seven marker observations must report absent leaves. Missing parents, denied
  access, sharing failures and unknown results refuse. Protected exclusive
  CREATE_NEW claim creation plus exact write/flush/identity checks precedes a
  credential read. No existing-file fallback or cleanup-driven retry exists.
- The source is opened exclusively, held/qualified, read at most once within
  the fixed 8192-byte bound, rechecked and matched to its exact source pin.
  Destination creation is exclusive and protected before the credential read.
  Full write, flush and held-handle identity/security checks precede delivery.
- One UTC/monotonic admission history spans initial DLL setup, process identity,
  executable open/read and final delivery/receipt effects. Each non-cleanup
  native dispatch is admitted, including the reused facade's internal APIs.
  CloseHandle/LocalFree and executable close remain permitted after expiry.
  Backward/nonfinite/expired clocks refuse. An admitted Windows call can finish
  after the deadline; no hard realtime cancellation is claimed. Held-handle
  cleanup always runs, including after expiry.

The source preserves #0183's accepted ordinary trusted-host premises. It neither
adds a universal privileged prior-handle proof nor recommends ACL changes.
Synthetic injection is a trusted test seam, not a Python security sandbox.

## Claim, result and receipt semantics

The factory consumes an invocation under a process lock before DLL setup. Even
pre-claim failures cannot retry in that exact process; another process fails the
packet's process-generation binding. The durable claim owns no-replay across
processes after creation. A present marker or failed,
partial or unknown claim prevents credential dispatch. Claims are never removed;
the returned result retains attempted/confirmed distinctions and counts reads
before dispatch. A failure does not prove that no output was reserved or written.

A protected CREATE_NEW receipt is written only after successful local delivery.
It binds the packet fingerprint and observations. Its persisted cleanup status
is explicitly unconfirmed because its own handle and parents have not yet closed.
The returned result carries final cleanup status. A receipt failure may coexist
with observed delivery; it never retries the credential read or overwrites the
receipt. Any failed close prevents a successful delivery result. Claim/receipt
inspection and reconciliation, if needed, require their own applicable authority;
they cannot justify replay.

The local packet's consent is limited to local preparation. Native consent and
POST action readiness must remain false in this source. The implementation has
no provider, DNS, cloud, Lightroom command or catalog operation.

## Verification and remaining gates

Forty-five injected synthetic tests passed at author handoff, including the
concrete factory route with injected DLL APIs, current identity parsing, handle
binding, exact pins, marker failures, exclusive creation, partial/unknown writes,
one-read accounting, deadlines, receipt failures and cleanup uncertainty. Ruff
check/format and standard Windows/Python 3.14 Pyright pass. This evidence concerns
source behavior; actual Windows API/custody and native POST qualification remain
unperformed. Fresh independent High review passed after the corrections below.

The independent review's initial deadline finding was corrected: setup and
identity retain the original clock history rather than starting a new window.
Regressions refuse setup rollback/expiry and expiry at each identity/read stage,
while proving that owned resources still close after expiry. Failed/unknown
identity cleanup also sets the returned cleanup status to unconfirmed. The
executable stream has an explicit owned close in a finally block; a throwing or
still-open close reports cleanup unconfirmed while the process token still closes.

The remaining action inputs are finite:

1. Complete and independently review a fresh exact private local packet and
   source pins, observed process/paths/custody, source fingerprint, current grant
   evidence/expiration, and the applicable delivery/cross-use/revocation policy.
   The concrete source factory is supplied here; actual host observations and
   approved private bindings are not fabricated by synthetic tests.
2. Obtain a fresh exact bounded local-action decision/window before invoking the
   deferred factory or reading any actual process, credential or marker paths.
   The October 18 window and credential lifetime have expired. Retention wording
   supplies no read/copy authority or lifetime extension. No replacement token is
   requested by this work.
3. Only after actual preparation and its independent result review, complete the
   separate exact cloud/native packet and obtain its fresh one-run decision.
   Recheck current native host/fixture/menu/runtime cells and all original case,
   deadline, stop, teardown and separate local/UI cleanup boundaries.

No credential contents, private packet/evidence/configuration, actual runtime
or marker paths, ACLs or real DLLs were read/loaded during this source work.
No POST case was measured, and no production transport boundary was qualified.

## Independent review and integration

Final independent High review passed with no unresolved material findings.
It verified both the continuous-admission deadline correction and executable-
close cleanup-uncertainty correction. All forty-five injected tests, three
independent injected regressions, Ruff, formatting and standard Pyright pass.
The unchanged #0183 source identities still match their reviewed pins. The
parent reproduced all forty-five installed tests after the final correction.
This closes source review only; actual current custody, valid inputs, concrete
private packet preparation and fresh applicable action authority remain pending.
