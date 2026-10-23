# Positional native sender source

Status: prospective source implementation and synthetic verification only.
There is no actual native qualification or action packet in this change.

The Root `NativePositionalBinding` composes `NativePositionalSender` with the
existing closed project graph, strict numeric-address TLS primitive, external
SQLite journal and protected credential delivery. Construction and the default
CLI remain inert. Only `fixed_update_with_exact_count_positional_v1` is selected;
the historical named/default/single-UPDATE paths retain their behavior.

The sender emits the exact two-statement REST body from the accepted positional
codec. It reserves request, statement and actual framed request-byte authority,
plus the worst-case response allowance, before touching the transport. A lost,
late or malformed outcome retains the durable allocation and writer slot.
There is no retry, redirect, fallback, budget reset or mutation repair.
Four separately requested complete PRIMARY control/schema reads surround each
transition; the native invocation producer owns their validation and custody.

Activation requires a typed `ReviewedAdmission` retained by the trusted Primary
after authenticating the actual independent evidence and its native meaning.
There is no JSON loader, generated PASS or default affirmative fact. Its exact
packet/source/protocol/target/window/clock/credential bindings and evidence pins
are rechecked. Pins authenticate bytes under the operator's trust; they cannot
establish that a reviewer, supported native semantic or operational fact is real.
An exact one-use `ProtectedCredential` must match the reviewed delivery reference;
metadata is checked before its protected token file is read.

The [REST query reference](https://developers.cloudflare.com/api/resources/d1/subresources/database/methods/query/)
supports the batch envelope and string parameter arrays. It exposes a PRIMARY
indicator, while its change metadata is approximate and is never used as the
exact count. The sender instead parses the following fixed `changes()` SELECT.
The [prepared-statement documentation](https://developers.cloudflare.com/d1/worker-api/prepared-statements/)
supports ordered parameters and identifies named support as future work.
The [Worker batch documentation](https://developers.cloudflare.com/d1/worker-api/d1-database/)
describes Worker ordering and transactional behavior. Those guarantees cannot
silently qualify the separate REST interface.

Current production activation remains NO-GO: supported REST same-connection,
original TEXT binding, ordering, transaction/rollback, commit and no-interleaving
basis still requires actual independently authenticated evidence. Actual complete
native source/readback, grant, all-writer closure, footprint, stable clock,
filesystem/ACL/power-loss custody and action gates remain separate factual proof.
Source tests use invented files, tokens, SQLite results and trusted-facts objects
with independent socket/DNS blockers; they supply none of those facts.

The sender accepts a valid `application/json` media type with safe syntax and
UTF-8 charset parameters while retaining ordinary response metadata. The concrete
strict transport continues to enforce framing, encoding, duplicate-field, redirect
and wire limits. Regressions run that actual transport/parser over invented TLS
sockets through the public native facade, covering length and chunked framing,
ordinary headers, invalid media types and malformed framing. They check the full
decrypted wire accounting as well as durable one-shot/no-replay behavior.

Accepted source authority:
[exact-count successor](../../docs/operations/pmb1-exact-change-receipt-successor-2026-10-23.md)
and [positional exception](../../docs/operations/pmb1-positional-generation-successor-2026-10-23.md).
No credential, account, provider, DNS, resource, native UI, deployment, migration,
live run or cleanup is authorized or performed by this source increment.
