# Protected screenshot POST admission

This additive source boundary implements the finite synthetic POST admission in
[the successor contract](post-screenshot-successor-2026-10-21.md). It supplies no
current action qualification. Import and the default CLI are inert. Only the
trusted primary calls `admit(packet_path, independently_retained_approval_sha2_256,
config=config)` after authenticating genuine owner direction and inspecting the
current native UI evidence. Hash-bound JSON preserves scope and provenance; it
cannot authenticate a human, turn a source review into permission, or supply an
unobserved native, credential, custody or account fact.

The executable closed schemas are in `scripts/post_screenshot_admission.py`.
Unknown fields, missing references, changed hashes, stale initial witnesses,
expired deadlines, wider policies and unknown issuer outcomes refuse admission.
This document explains the evidence preparation order and trust boundary; it does
not replace the accepted action, native dispatch, credential or disposal contracts.

The native receipt separates `authorityOwner` (Terry, bound to `authority.owner`)
from `witness` (the actual Bot/Root primary inspector) and its
`witnessReference`. It binds that inspector record to the same exact
source/window/PID/time facts. These strings preserve truthful provenance;
the trusted primary's externally authenticated approval remains the trust
boundary. Likewise actual review author/reviewer identities describe who did
the work; they do not attribute Bot observations or reviews to the human owner.

## Protected inputs and preparation order

The separately retained approval digest identifies the exact protected
`approved-packet.json`. That packet hashes the complete protected `config.json`
and the exact successor source manifest. The configuration points to its exact
sibling `action-evidence.json` and hashes its bytes. All referenced documents are
absolute, protected regular files, without symlink/reparse or hardlink aliases,
read through the established race-guarded private-file helpers. Evidence paths
must be distinct and cannot name the execution token. The complete source closure
is rehashed at admission and before every later authorization.

The configuration declares the actual `parentTokenFile` solely for metadata
checks and alias exclusion; admission never reads its contents. Before reading
referenced evidence bytes, admission preflights the complete reference inventory
against both credential paths and file identities. Paths must be canonical,
absolute local paths; parent traversal, UNC/device paths, stream names, resolved
aliases and either credential identity are refused. The actual issuer plan must
bind exactly those declared parent/child paths.

Use the following order to avoid a circular hash dependency:

1. Freeze and independently review the successor source manifest. Record the
   actual source review with `subjects: {"manifest": <manifest SHA2-256>}`.
2. Retain current issuer, provider grant, native, cell, account, custody and
   consumed-run evidence. Bind their hashes into the configuration.
3. Compute `config_intent_sha2_256(config)`. It hashes UTF-8 JSON with sorted
   keys, compact separators and no nonfinite numbers, excluding only
   `evidenceSha2_256`. The intent still includes every identity, path, account,
   credential, cell, deadline, parser and current-evidence pin.
4. The primary records genuine owner-direction applicability in `authority`,
   naming `configIntentSha2_256`, the exact manifest, exact scope, actual owner
   decision reference and current finite validity. This records the already
   accepted direction and its application, not newly invented human approval.
5. A fresh non-author reviewer records the actual packet review. Its subjects
   bind `configIntent`, `manifest` and every referenced evidence digest except
   the packet review itself. Do not write `pass` before that review occurred.
6. Hash the complete action evidence, finish `config.json`, hash that complete
   configuration into `approved-packet.json`, then independently retain the
   exact final packet digest. The final digest closes the complete graph.

A review record has exactly `schemaVersion`, `author`, `reviewer`, `verdict` and
`subjects`. The version is integer 1, verdict is `pass`, identities are nonempty
and distinct, and subjects must match exactly. The trusted primary remains
responsible for the truth and independence of the review identities.

## Required current evidence

Every `references` entry has exactly `path` and `sha2_256`. The action evidence
kind is `post_screenshot_action_evidence`; its exact run and manifest must match
the final packet. It also fixes one canonical public numeric management address
for the reviewed pinned HTTPS transport and the finite cleanup inventory.

| Reference | Retained fact and validation |
| --- | --- |
| `authority` | Genuine owner direction reference, exact run/scope/source/config intent, owner, current validity and explicit native-action, cancel-case and local-cleanup applicability. |
| `native` | Primary's current UI witness with its actual `witnessReference`: same actual process PID, exact supported window, Lightroom Classic host 15.6/SDK 15.3 and observed build, fixture/toolkit, current source equality, enabled fixture, sole operator, full supported frame inspection, fresh native/run paths and reviewed cells. The controller creates and enforces its fresh generation after admission. |
| `cells` | Exact reviewed runtime-cell source bytes; hashes are checked again before input by the caller. A source digest is not evidence that the cells actually ran. |
| `custody` | Exact local delivered-child path/fingerprint, same owner, current protected delivery/custody observation and actual path-review reference. |
| `accountProvenance` | Exact account/subdomain, current same-owner observation and actual source reference. A syntactically valid account string alone is insufficient. |
| `spentHistory` | Current private complete consumed-run inventory and provenance. Its bounded unique lower-hex 24-character list matches `spentRunIds`, its digest matches `spentHistorySha2_256`, and the candidate is absent. The primary/reviewer checks completeness against actual private history; public source contains no private historical IDs. |
| `issuerPlan` | Actual accepted automated issuance plan, not a fabricated human dashboard issuance. Exact account, child path/profile, parent fingerprint, child expiry, bounded issuer inventory, cleanup/revoker and original source identity remain bound. |
| `issuerApproval`, `issuerAuthority` | Actual issuer approval and genuine retained human authority evidence; the actual issuer evidence header must bind both through their exact hashes and accepted bootstrap decision. |
| `issuerEvidence` | Original protected issuer JSONL: header followed by parent verification, permission catalog, parent details, acknowledged creation, child details and exclusive protected delivery, in that order. |
| `issuerJournal` | Protected immutable snapshot of the actual completed issuer SQLite journal. Exactly six producer intents, in order, must be complete: started, reads 1/2/3, creation mutation and read 5. Every method/path/request digest and read/mutation receipt must match; started records finished/five calls with finite positive response accounting. No missing/extra/retirement intent is accepted. Admission reads an in-memory copy and performs no journal write. |
| `issuerReview` | Fresh actual non-author review binding the exact issuer plan, approval, human evidence, journal and creation/delivery evidence. |
| `grant` | Current observed child/parent verify results and actual full child details, exact run and distinct fingerprints. Full provider policies must be exactly account-scoped D1 Write and Workers Scripts Write, with no child token-management power; actual issue/not-before/expiry and parent seven-day/fixed-cutoff policy are validated. |
| `grantCollection`, `grantPlan` | Actual retained metadata-collector output and its exact plan. The current grant projection must equal the actual three result bodies and both fingerprints; collection time must fall within that actual finite plan window. The original child path and local parent metadata-reader path remain bound. |
| `sourceReview`, `packetReview` | Actual independent review records binding their exact subjects. Neither is fabricated by preparation. |

Initial native, grant and consumed-history observations must be at most 300
seconds old. Initial admission requires 1230–1800 seconds remaining. Rechecks
preserve the original fixed observation timestamps and expiries; they do not
renew witnesses or invent a moving window. Source/config/evidence hashes and
all current credential validity checks remain mandatory throughout cleanup.

Historical issuer and collector source maps contain their full exact producer
closures and match the current reviewed source bytes. Issuer JSONL phases are
closed; header retention/source/approval bindings, active parent verification,
creation/detail identity/name fields and issue/approval/cleanup/retention windows
agree with the actual producer plan. The child cannot outlive the parent.

For this dedicated child, `credentialExpiryUnix` equals `actionDeadlineUnix`,
the final resource/provider-cleanup cutoff. Every required witness/authority
expiry covers that full window. The declared revocation responsibility is due
no later than that child expiry; the packet does not acquire the publisher's
four-hour execution lifetime. A failed or expired retirement remains explicit.
Parent-admin retirement after expiry needs a separate exact reviewed issuer
action and packet. Expiry alone does not prove revocation or authorize parent
calls through this admission.

The grant document is a closed projection of actual retained provider results,
with `schemaVersion`, `runId`, `observedAtUnix`, `childSha2_256`,
`parentSha2_256`, `childVerify`, `parentVerify` and `childDetails`. The primary
retains the original provider collection evidence privately as `grantCollection`
and the independent packet reviewer verifies the projection against it. A caller-authored assertion
that a grant is effective is insufficient.

## One-shot seam, stops and cleanup

`authorize()` rechecks immutable private inputs, source closure, current fixed
expiries and both wall and monotonic limits. It refuses a different process,
closed permit, new-work cutoff, operator stop or native stop. `remaining_seconds()`
never extends the initial deadline.

An observed stop is sticky. Removing a stop file does not permit new work again;
only the irreversible bounded cleanup phase remains available. Authorization
checks its clocks again after evidence/source/stop I/O before returning; token
delivery also rechecks after its one protected read.

`read_token_once()` authorizes, exclusively creates the protected
`token-read.claim`, flushes its approval digest durably, verifies that claim,
authorizes again and performs one race-guarded protected token read. The actual
raw ASCII child bytes must match the admitted fingerprint. The claim is retained
on all failures and is never cleared or reused. Admission, default commands and
source review do not read the child token or parent token.

`begin_cleanup()` is irreversible. It permits only the existing same-owner
bounded observation/cleanup composition after a stop, within the original
accepted deadline and actual credential expiry. The lifecycle and provider
continue to enforce exact returned identities, route restrictions, terminal
prerequisites, unknown-outcome retention, the single 120-call meter and its ten
reserved calls. The phase does not grant arbitrary provider operations or revive
an expired credential. `close()` permanently closes this permit.

## Verification and remaining premises

The synthetic admission tests run the actual issuer writer with fake
source/OS/transport boundaries to obtain its real journal and JSONL. Adversarial
tests mutate retained copies after production. They exercise positive admission,
no early token read, one-shot
claims, hash drift, unknown issuance, missing delivery, widened effective policy,
actual process binding, stale witnesses, stop-to-cleanup and fixed expiry.
They also reject missing/extra/altered producer intents, empty source maps,
inconsistent retention/verification and credential evidence aliases before reads.
OS/private-read and source-validation boundaries are faked; no test contacts the
provider, reads actual credentials or native paths, or claims Windows ACL proof.

Source completion does not supply the current genuine direction record, actual
issuer/grant/custody/account data, current native/UI witnesses, complete consumed
history, final runtime cells, source/packet review or final retained digest. The
primary must obtain and independently review those concrete facts before apply.
