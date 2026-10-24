# Nullable original parent: separately named recovery source

This source increment supports an original issuance plan whose permitted
`parent_id` value is null. It implements the existing [accepted recovery
contract](historical-child-recovery-contract-2026-10-23.md); it grants no actual
inspection, new recovery session, credential access, provider request or retry.

The two new modules are `scripts/historical_child_recovery_nullable_v2.py` and
`scripts/historical_child_recovery_operator_nullable_v2.py`. Their import and CLI
remain inert. The original controller, operator, producer, historical packets and
spent sessions remain unchanged. In particular, this source change establishes
neither the cause nor the read/write extent or partial output of any old stop.
Those facts remain unknown.

## Original acknowledged parent

The v2 controller first completes the unchanged request, inventory, source,
original-latch, historical authentication and current authentication gates. The
trusted historical verifier still authenticates complete original issuance,
approval, ownership receipts, journal snapshot, original source/commit, review,
security fields and immutable closure evidence. Matching hashes alone do not
supply that judgment.

It then requires the original seven records in their existing order: issuance
header, parent verification, permission catalog, parent details, acknowledged
creation, child details and delivery. The parent identity must agree between
the retained verification, parent details and acknowledged child ownership,
and with the exact recovery request. The acknowledged child, parent fingerprint,
account, profile, child expiry, name and condition must retain their original
bindings. A nonnull original parent must also agree. Missing, malformed, reordered,
duplicate or mismatching lineage refuses before namespace reservation.

Only the new recovery plan receives the authenticated acknowledged `parent_id`.
The original plan bytes and digest remain unchanged. The new plan retains its
reference to the original plan digest, child details, issuance journal and
historical validation timestamp. The unchanged producer still validates the
new plan, active parent and exact expired child, and reserves the original sole
`issuer:retire` latch atomically. No new latch, identity normalization, fallback
credential, listing or retry is introduced.

## Exact provenance role and private boundary

`ReviewedFacts.original_manifest.provenance` denotes the separately retained
**private original-manifest provenance evidence**, not the public source manifest.
`OriginalManifestBinding.provenance_role` must equal
`private_original_manifest_provenance`. This label declares the required role;
it proves no current filesystem fact.

The Primary must independently authenticate the exact reference's historical
meaning and original root, commit, manifest digest and complete map. The same
existing exact reference is inventoried, with the ordinary regular-file,
single-link, reparse, identity and alias checks. `_private` requires both the
file and its immediate parent to satisfy the unchanged native private owner/ACL
checks. Authentication rereads those exact bytes through `_read` and checks the
retained digest. The public exception still applies only to `sourceManifest`.

A locator, digest, constructor label or descriptor cannot establish private
custody. If the exact evidence does not satisfy that role or its private
file-and-parent requirements, this implementation refuses. It neither adopts a
public file as private provenance nor copies original inputs, searches for an
alternative, repairs ACLs or broadens the public exception. Any future acquisition
of genuine factual evidence needs its own concrete reviewed scope; this source
increment performs no such acquisition or generic owner file-finding request.

## Concrete preparation and final handoff

A separately authorized trusted Primary constructs the v2 `Operator` from an
independently authenticated `ReviewedFacts` and exact request. The exact source
closure contains the unchanged producer's complete original source map and the
two v2 module paths/digests. The request's `controllerSource` must identify the
v2 controller itself. There is no ambient discovery or alternate-module fallback.

`Operator.prepare_metadata(now=..., execute=True)` runs concrete preparation,
repeats preparation before any exclusive write, and reserves and writes only
the new namespace's plan, approval and binding. It returns `PreparationOutcome`:
the private packet and a separate safe report. The default `execute=False`
refuses. This method is single use on its operator; an error retains any namespace
or partial bytes and returns no usable packet. A new operator object is not
authority to retry a spent attempt.

A genuine independent packet review and current facts remain required before
the existing explicit `Operator.dispatch(..., execute=True)` handoff. That method
rebuilds the packet, authenticates exact current facts and the independent review,
checks final bytes and the original latch, then calls the unchanged pinned
producer once using its original TLS transport and credential boundary. The
producer retains its final deadline, per-send fence, five-call and byte limits.
All current interval, parent expiry, provenance custody, cleanup and no-replay
facts must be proved separately. This document and the local tests prove none of
them and authorize no actual invocation.

## Closed preparation diagnostics

The safe report includes only a finite status, phase, failure category,
`failedCallEffects` and integer counters. Recognized exact refusal labels are
allowlisted; known private-storage refusals and ordinary storage/interruption
classes have fixed labels. Every other exception becomes `UNEXPECTED_EXCEPTION`.
No raw exception arguments, identity, path, fingerprint, evidence content or
provider body appears in the report.

Counters distinguish attempted and completed private-reader calls, namespace
reservations and metadata creation, plus returned private bytes and confirmed
metadata bytes. They count this boundary's calls, not physical file-system
operations, underlying reads, or reconstructed historical extent. On failure,
effects of the failed call remain `UNKNOWN`, even when earlier calls completed.
Neither a zero counter nor a closed failure category proves zero native effects.
The packet remains private and must never be printed with the safe report.

## Why these modules are separate copies

The frozen implementation binds its literal controller filename, module
`__file__`, loaded function code, ambient imports/constants and exact two-module
source closure. Importing its controller under another identity or subclassing
its native operator would fail those guards or require weakening them. These
ordinary standalone copies preserve them and leave frozen entrypoints byte exact;
there is no runtime monkeypatch, code rewriting or generic adapter qualification.

The limited controller differences are its v2 self-name, an explicit phase method
in the verifier interface, acknowledged-parent lineage validation and populating
only the new plan's parent. The limited operator differences are its v2 import,
the explicit private provenance role and closed single-attempt preparation
reporting. All other original source, inventory, private-reader, source-loader,
latch, writer, final-review, dispatch and producer-boundary logic is retained.

`tests/test_historical_child_recovery_nullable_v2.py` uses invented issuance,
temporary files, fake native security metadata, fake Git receipts and fake TLS
sockets. It exercises the concrete v2 operator through prepare, repeated
prepare/write, final recheck and the unchanged producer's complete five-call
path, plus mismatch, privacy, partial-write and redaction failures. No genuine
role file, native security DLL, network socket, DNS lookup, provider or recovery
session is used. A passing test remains source evidence only.
