# Isolated private snapshot qualification decision packet

Date: 2026-10-18. Ticket #0172. Status: **offline preparation; live action
ungranted**. Accepted #0170 source is reused without changing its provider
operator, credential loader, reader or codec. No current account, token, private
artifact, endpoint or resource was inspected for this packet. No hosted result,
effective grant, approval, custody qualification or cleanup pass is asserted.

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
No new operator or credential-delivery path is introduced by this work.

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

Every row is currently **unknown / ungranted**. Owner/operator identity, private
retrieval references and decisions must be genuine, independently reviewed
records, never values invented to satisfy a hash validator.

| Required input or decision | Exact record to settle |
| --- | --- |
| Operator and authority | Named primary operator; Terry's actual decision reference covering this candidate, request ceiling and proposed cleanup limits |
| Account and fresh run | Independently established permitted account ID; fresh 32-hex run ID; exact numeric endpoint provenance; prohibit a supplied existing database ID |
| Source/tooling | Independently retained recipe pin and qualifier source map; pinned uv/Python/lock and independent source review |
| Caller window | Exact UTC `startsAt` and `expiresAt`, at most 20 minutes; no appointment is inferred |
| Credential | Exact credential delivery file/reader authority, credential binding retained privately, real provider expiry and named revocation owner/deadline |
| Effective grants | Independent evidence of actual D1 Write scope and every broader effective capability; explicit permission for fresh create, fixed seed, reads, exact delete and single GET |
| Custody | Named owner/custodian, three distinct new absolute sink paths, actual ACL/encryption/no-sync/backup/access assessment, evidence pin and review access |
| Retention | Finite evidence/partial-file retention and review deadline, responsible disposer, backup/recovery/telemetry limits and disposal evidence; no secure-erasure claim without proof |
| SQL settlement | Decide whether documented provider terminal responses establish settlement sufficiently for this experiment; if evidence is missing, defer live work or first approve a separate bounded settlement qualification |
| Cleanup | Explicitly accept the limited DELETE/GET observation and retained uncertainty, or defer pending independent absence/cleanup qualification; never relabel 404/7404 as absence |
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
guarantee. Do not inspect or claim those grants until separate exact authority
exists. Token contents, authentication-derived bindings, account/resource
identities, private paths and private evidence digests stay out of public
documents, chat, tickets, logs and commit history.

## Reviewable redline choices

The conventional recommendation is to **defer live execution** until the exact
inputs and settlement/cleanup/custody decision are complete. Terry can choose
one of these concrete next actions without treating preparation as execution:

1. **Keep source preparation only.** Retain this packet and independent review;
   record the missing inputs above. No account request, credential read, new D1
   resource or private snapshot is authorized.
2. **Approve the narrow experiment after filling every required decision.**
   Explicitly accept possible resource retention after an uncertain operation,
   `cleanupVerified=false` even on nominal completion, and the separate finite
   reconciliation/revocation decision required afterward. The existing source
   remains the only operator and the ceiling stays 26. This is not a production
   preservation or cleanup exception.
3. **Require stronger settlement/cleanup proof first.** Approve a separate
   finite experiment specifying the exact allowed observation or reconciliation,
   source, identities, time/request budget and retention. Do not silently append
   requests, implement a new live operator here, or extend this recipe's window.

These are proposed choices, not recorded owner selections. The publisher-only
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
all hosted measurements and action-time grants remain unavailable.

## Independent review record

Fresh independent High review passed the 54 focused/regression tests, scoped
Ruff/format/Pyright checks and the independently recomputed documented recipe
pin. The parent separately passed the thirteen new preparation tests. No
material finding remains in the offline packet. Source acceptance and these
local checks do not supply the missing private inputs, settlement/cleanup/
custody decisions, actual provider measurements or live authorization above.
