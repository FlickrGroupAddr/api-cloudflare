# Isolated private snapshot qualification decision packet

Date: 2026-10-18. Ticket #0172. Status: **narrow conditions accepted; private
draft prepared; final live action ungranted**. Accepted #0170 source is reused
without changing its provider operator, credential loader, reader or codec.
Terry accepted the narrow experiment's conditions and preparation using retained
grant metadata. No new account request, credential-content read, endpoint
observation or resource action occurred. Hosted qualification, actual evidence
custody and cleanup remain unproved.

This packet makes one bounded source candidate reviewable for a later owner
decision. The [reader operations record](private-full-snapshot-reader-2026-10-18.md)
owns its interface and limitations; the accepted
[preservation contract](fixed-origin-preservation-2026-10-17.md) still controls
production full-state evidence. This isolated transport exercise cannot satisfy
that contract's production writer barrier or restoration gates.

## Offline candidate and pins

Run only the preparer during source preparation:

```console
uv run --frozen python -m scripts.prepare_private_snapshot_qualification NEW_STAGE
uv run --frozen python -m scripts.prepare_private_snapshot_qualification STAGE --verify --expected-recipe-sha256 INDEPENDENTLY_RETAINED_RECIPE_SHA2_256
```

Use repository-pinned uv 0.12.5, Python 3.14.7 and the frozen lock. The new stage
has an existing parent outside the checkout. Its four deterministic files are:

- `source-pins.json`: SHA2-256 of the existing reader's 12-file source closure
  and the offline preparer. No executable source, account data or token is copied.
- `recipe.json`: that source set, ordered request bounds and explicit ungranted,
  unqualified status. Retain its canonical-JSON digest independently. The codec's
  SQL and the qualifier's fixed seed remain owned by the pinned source.
- `packet-template.json`: the qualifier's exact field set and source closure,
  with every unknown action-time input null. The preparer pin is deliberately
  outside the existing qualifier's source map.
- `consent-template.json`: `approved=false`, null decision reference and null
  packet pin. It is invalid consent. Preparation never produces true approval,
  synthetic evidence hashes or fabricated effective grants.

Verification compares every byte to the current closed source recipe, rejects
extra/missing/modified/linked files and compares the independent recipe digest.
Source changes require fresh pins and review. These pins establish candidate
integrity, not authority or provider behavior. Keep the stage unchanged; actual
private packet/decision/evidence belongs separately in owner-approved custody.

The prepared 2026-10-18 source candidate has recipe SHA2-256
`c61a59656f68b995057f66ab3e748400d32555fb9c3ab889ce4a1a79fd00200a`.
This public-source digest covers the complete source map and finite recipe;
it is not a digest of a private packet or approval. Recompute after any source
change and require a fresh independent review instead of carrying this pin
forward silently.

## Exact proposed request surface

The reused entry point is `scripts.qualify_private_d1_snapshot.qualify`. Its
existing CLI can perform real HTTPS after genuine exact inputs and consent;
**do not invoke it with filled inputs until every decision below is settled**.
No new operator or credential-delivery path is introduced by this work. Terry's
acceptance of conditions does not supply the final sequenced caller window,
private custody approval or executable consent.

The finite recipe allows at most **26 requests**, in this order, with no retry,
redirect, DNS lookup, account listing, existing-resource lookup, resume or
open-ended polling:

| Order | Maximum | Fixed scope |
| --- | ---: | --- |
| 1 | 1 | POST the exact account's `/d1/database`; name `fga-snapshot-qualification-<runId>`, read replication disabled |
| 2 | 1 | POST fixed `SEED_SQL` to the newly acknowledged UUID's `/query` |
| 3 | 11 | Discover/capture the complete supported schema and data using the pinned codec |
| 4 | 11 | Repeat that exact ordered query manifest through the private reader |
| 5 | 1 | DELETE only that same acknowledged fresh UUID, after terminal equal readback |
| 6 | 1 | GET that UUID once, solely to classify the exact provider response |

All targets are `https://api.cloudflare.com/client/v4/accounts/<accountId>` with
one separately approved numeric endpoint address, normal TLS hostname checking
and identity response encoding. The UUID cannot be an input: creation must
acknowledge the exact run name and a nonzero UUID before seeding. Only that
acknowledgment enables the same-process reader permit; a JSON receipt or source
flag cannot import an existing database. No Worker, route, binding, production
table or existing database is in scope.

The seed has six synthetic values: NULL, both signed 64-bit integer extremes,
empty text, embedded-NUL/Unicode text and a BLOB. No authentication/session or
real photo data is seeded. The census nevertheless reads every table exposed
by the new database, including provider bookkeeping; at most two tables total
and 256 rows per table are allowed. Extra/denied/unsupported state refuses;
there is no provider-table exclusion. The initial capture must independently
match the expected six cells; the exact reader snapshot must then equal it.

The whole caller window is at most **1,200 seconds**, including creation,
seeding, both captures, DELETE and the GET observation. Each request is at most
30 seconds and shrinks to the remaining caller window. Every outer response
has a 262,144-byte body ceiling and a 327,680-byte decrypted HTTP wire cap.
Reader requests have a 262,144-byte wire cap and 2,621,440-byte aggregate wire
cap, including headers/body/framing. The combined conservative response-wire
ceiling is 7,536,640 bytes: at most 15 outer requests plus the reader aggregate.
This is a ceiling derived from fixed per-call limits, not a new measured total
or allowance for extra requests. All source codec bounds also apply.

The action-time packet fixes one start and expiry; none is proposed now.
Provider token expiry is separately recorded and must reach the caller expiry.
The caller deadline neither revokes the token nor cancels a provider operation
already in flight. After expiry there is no automatic cleanup, credential
revocation or follow-up request within this recipe. A later action requires its
own finite approved scope.

## Owner decisions required before live execution

Terry accepted the narrow settlement/uncertainty/cleanup conditions and reuse of
the existing publisher credential's D1 Write grant **for D1 actions only**. The
credential also has Workers Write capability; that broader capability was
acknowledged and remains unused by this experiment. Retained metadata review
passed its account, binding, scope and exact-expiry checks. This supplies no new
Workers action, grant expansion or production exception.

An ACL-protected private draft now retains the reviewed account, credential
fingerprint, effective policy evidence and provider timestamps without rounding.
The fingerprint supplies the credential binding without reading token contents.
A fresh run name is prepared; no database UUID is supplied. The closed draft
packet keeps caller times, actual custody pin and actual sink bindings null;
the separate draft consent remains false. Actual identifiers, policies,
fingerprints, timestamps and paths remain only in protected private records.

The following checklist distinguishes retained inputs from remaining decisions.
Owner/operator identity, private references and decisions must be genuine records,
never values invented to satisfy a hash validator.

| Required input or decision | Exact record to settle |
| --- | --- |
| Operator and authority | Narrow conditions and preparation accepted; parent owns final sequencing, live approval and primary operation |
| Account and fresh run | Retained reviewed account bound privately; fresh 32-hex run/name prepared; numeric address retained from earlier metadata plan rather than freshly observed; no supplied existing database ID |
| Source/tooling | Independently retained recipe pin and qualifier source map; pinned uv/Python/lock and independent source review |
| Management response policy | Complete #0178 before final live readiness; qualifier and reader still use the strict management transport. Any source change needs fresh source/recipe pins and independent review before a later run |
| Caller window | Exact UTC `startsAt` and `expiresAt`, at most 20 minutes; no appointment is inferred |
| Credential | Existing credential reuse accepted for D1 actions; retained fingerprint and exact provider expiry bound privately; parent must settle final delivery authority and revocation owner/deadline |
| Effective grants | Retained independent metadata review passed; D1 Write reused for only fresh create, fixed seed, reads, exact delete and one GET; Workers Write acknowledged unused |
| Custody | Named owner/custodian, three distinct new absolute sink paths, actual ACL/encryption/no-sync/backup/access assessment, evidence pin and review access |
| Retention | Finite evidence/partial-file retention and review deadline, responsible disposer, backup/recovery/telemetry limits and disposal evidence; no secure-erasure claim without proof |
| SQL settlement | Accepted only for this narrow experiment: successful complete provider SQL responses suffice to proceed; unknown SQL/read outcome stops and retains, without deletion or replay; production requirements remain unchanged |
| Cleanup | Limited DELETE/GET observation and possible cleanup-unconfirmed outcome accepted; any follow-up requires separate finite authority; 404/7404 remains an observation rather than absence |
| Unknown outcomes | Named escalation owner and finite decision deadline for an unacknowledged create, unknown SQL/read/delete/GET or incomplete private write; no guessed resource ID, replay or automatic cleanup |

The account/token/grant/custody/source pins bind the **private** execution packet.
The current closed packet has exactly these keys: `schemaVersion`, `kind`,
`runId`, `sourceSha256`, `accountId`, `endpointAddress`, `startsAt`, `expiresAt`,
`providerTokenExpiresAt`, `credentialBinding`, `grantEvidenceSha256`,
`privateCustodySha256`, `journalPath`, `outputPath`, `readerJournalPath`.
There is no `databaseId` input. The separate consent has only `approved`,
`decisionRef`, `packetSha256`; approval refers to the canonical packet digest.
The limited consent schema does not record all owner decisions: retain those
genuine decisions in the referenced private record, including settlement,
retention and cleanup. Hash syntax is no substitute for their acceptance.

The D1 Write token's actual effective scope may be broader than this narrow
request surface. This packet supplies no new token restriction or enforcement
guarantee. Retained grant review was explicitly authorized for preparation;
no new provider observation or credential-content access follows from it.
Token contents, authentication-derived bindings, account/resource
identities, private paths and private evidence digests stay out of public
documents, chat, tickets, logs and commit history.

## Accepted conditions and remaining redlines

Terry selected **accept the conditions and prepare the packet**. This settles
the narrow SQL-response, unknown-outcome and cleanup limits described above;
the immutable source recipe and its pin are unchanged. It does not constitute
the final run approval or a production preservation/cleanup exception.

The prepared private proposal supplies concrete custody, retention, review,
escalation and credential-disposition choices. Its proposed evidence location
is outside known checkouts; the directory has not been created or qualified.
Only the draft directory's protected ACL was checked. Actual evidence ACLs,
encryption, sync/backup behavior and review access remain unverified. Proposed
retention and deadlines remain unaccepted rather than fabricated actual policy.

Before live execution, the parent must sequence this experiment with the other
approved work, fix the exact finite caller window, settle those private custody
and disposition choices, and retain genuine consent to the final packet digest.
There is no appointment or ready flag. If stronger settlement or cleanup proof
is desired, it needs a separate finite experiment; do not append requests,
silently extend this window or replace the existing operator.

The publisher-only
synthetic disposal exception **does not apply** to this database experiment.
Neither a run label nor deletion of a test database proves settlement,
preservation, credential revocation, private artifact erasure or removal from
provider recovery history, backups and telemetry.

## Honest outcomes and handoff

Unknown SQL or reader outcome retains the database and private artifacts;
no DELETE follows. Create uncertainty before acknowledgment can leave an
unknown resource outcome. DELETE uncertainty or an unclassified GET leaves
cleanup unconfirmed. Existing sink paths refuse; partial files and journals
remain no-replay tombstones. Preserve them for the named finite decision,
rather than deleting them to retry.

The single post-delete GET can record HTTP 404 only with the expected closed
Cloudflare envelope and one error code 7404. That records **a provider response
observation**, never verified absence, physical erasure or completed cleanup.
Generic 404, authentication errors, malformed results, HTTP 200, timeout or
uncertainty do not satisfy even that classification. The existing source
returns `complete=true` only when its finite recipe terminates; it still returns
`cleanupVerified=false` and `productionQualified=false`.

Every SQL REAL cell still refuses the full snapshot. This recipe's REAL negative
is a local decoder refusal, not hosted binary64 extraction. Matching captures
prove neither a production all-writer barrier nor a coherent transactional
snapshot, production type coverage, secret/session custody, restoration,
provider absence or a final preservation gate. Synthetic injected transports
must be labeled synthetic and cannot become hosted evidence.

Handoff may therefore report the source candidate/pins, independent review and
offline verification, then list unresolved owner decisions. A later live run
must separately report finite terminal observations, uncertainty, retained
artifacts and required disposition. No hosted measurement is available from
this preparation work.

Offline verification: the preparer, codec, reader and qualifier unittest modules
passed **54 tests** (13 new preparation checks and 41 existing regressions) under
the pinned frozen uv environment. Checks include source/recipe tampering,
independent-pin mismatch, IO boundaries, invalid consent before credential
delivery, existing-ID rejection, fixed budgets and absence of invented evidence.
Scoped Ruff check/format and Pyright passed. Those are local source checks;
all hosted measurements and final action-time consent remain unavailable.

## Independent review record

Fresh independent High review passed the 54 focused/regression tests, scoped
Ruff/format/Pyright checks and the independently recomputed documented recipe
pin. The parent separately passed the thirteen new preparation tests. No
material finding remains in the offline packet. Source acceptance and these
local checks do not supply final custody/window decisions, actual provider
measurements or live authorization. The later accepted narrow conditions and
private draft preparation passed a fresh independent High handoff review. It
verified retained bindings and exact metadata, source/recipe pins, false consent,
deliberately unset execution inputs, draft ACLs and privacy boundaries. The
management-response prerequisite was corrected and rechecked; no material
finding remains. No live or credential-content access occurred.
### Management transport prerequisite

The accepted cookie-discard policy applies only to metadata collection. The
qualifier and reader still use the strict management-response transport. #0178
must qualify the applicable response policy before this experiment's final live
readiness; the draft remains ungranted meanwhile. This records a known policy
gap, not an observed D1 creation response or a prediction of a failed request.
Do not borrow the metadata exception implicitly. Any resulting source change
requires freshly prepared source/recipe pins and independent review; the current
closed draft cannot silently adopt it.

## Explicit ADR0064 preparation path (2026-10-19)

The source preparer and bounded synthetic caller now support the accepted
`adr0064-private-d1-application-state-v1` profile explicitly. This is source
preparation under #0221, following accepted #0219 and reviewed #0220. Historical
recipes, packets, stopped attempts and receipts retain their strict meaning.
Omitting the profile continues to select the original all-table path.

For a new private preparation, supply both `--profile` with that exact identifier
and `--profile-manifest` with the independently reviewed closed manifest. Repeat
both inputs during `--verify` and retain the independent recipe digest. The
manifest must describe the actual intended complete census after the fixed
synthetic seed, classify only exact `main._cf_KV` contents as excluded, and bind
the dependency review of actual applicable source, migrations and schema.
Preparation neither generates this manifest from discovery nor performs its
independent review. Dependency attestations and hashes are reviewed inputs;
their syntactic validity supplies no review or execution authority.

The source recipe, packet and false-consent template carry the same profile,
manifest and actual checkout Git `runtimeCommit`. Exact source byte pins remain
separate and mandatory. A commit change requires fresh preparation and review;
do not guess a future revision. Scoped stage files include the supplied private
census/dependency manifest and must remain in the qualified private destination.
The unchanged default preparation still reads only its public source allowlist.

The caller requires the same context in its genuine packet-bound consent, checks
the actual Git revision before credential delivery and throughout the finite
attempt, and reconciles discovery against the reviewed manifest before content
reads. It passes that explicit profile/manifest into both capture and reader
plan/consent. The generated ordered query/source provenance and context bind the
scoped receipt digest. Readback must match both the exact reader plan and
snapshot before deletion of the acknowledged fresh UUID is permitted.
Unknown names, dependencies, manifest/source/runtime drift or strict/scoped
context confusion refuse. No SQL operation or finite allowance was added.

The scoped result labels application-state equality and returns its binding and
receipt digest with `wholeProviderContentsEqualityVerified=false`. Exact excluded
contents remain `unobserved`, `unfrozen` and `unverified`; no reserved content,
count, empty value or harmlessness guarantee is manufactured. An injected
transport remains synthetic evidence only. `productionQualified=false` and
`cleanupVerified=false` remain, including after the exact-ID not-found response.

Actual #0172 operation still needs the final reviewed committed-source packet,
current independently reviewed effective grant and credential delivery, finite
window, private custody/disposition and genuine applicable owner-action record.
The existing no-replay tombstones, uncertain-outcome retention, exact identity,
equality-before-cleanup and accepted request/row/byte/deadline bounds remain.
REAL extraction, UTF-8, complete application facts and writer consistency,
production preservation, backup/restore and release gates remain separate.
This source change records no account request, credential read, new database,
native action, deployment, provider contact or hosted qualification.

Local source verification passed 146 tests across preparation, caller, profile,
codec, reader, preservation and restore, plus scoped Ruff check/format and
Pyright. Coverage includes the actual JSON preparer outputs passed to the actual
qualifier with genuine checkout HEAD and real clocks; exact source pins,
reserved-content denial, strict defaults, context/consent/runtime mismatch,
census/application drift and equality-before-cleanup refusal. These are synthetic
local checks; fresh independent review and final committed-source preparation
remain required before #0172 can consume this handoff.
