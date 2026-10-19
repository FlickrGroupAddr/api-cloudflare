# Deferred POST local preparation: path roles

Date: 2026-10-19. Ticket: #0189. Status: source correction passed independent
High review. Actual private preparation, native readiness and POST remain unpassed.

The deferred `probes/post-local-preparation/local_action.py:live_factory` now
expresses the documented distinct retained-source, caller-destination, native
marker and local-record parents. Both CLI entries remain unconditional
`NO_APPLY_source_only`; the factory remains unregistered. Only public source and
injected invented observations were used. No private path, evidence, credential,
ACL, process or runtime marker was read; no real DLL, native, provider or DNS
operation occurred.

## Packet and path contract

The former single `roots`/`private_from` pair cannot express the documented
layout. `LocalPacket` replaces it with these independently pinned roles:

- `source_parents`: complete retained-source parent chain.
- `destination_parents`: complete fixed caller-destination parent chain.
- `native_parents`: seven complete chains, paired in order with the exact native
  marker inventory: `target.json`, `target.used.json`, `status.json`, `stop.json`,
  `target.json.tmp`, `status.json.tmp`, `stop.json.tmp`.
- `claim_parents` and `receipt_parents`: complete chains for separately reviewed
  local records. These may share a parent but are additional file roles.

Each `ParentChain` contains exact `roots` from `C:\` to the immediate parent,
and an explicit integer `private_from` boundary after the volume root. All roles,
including native markers, require their declared private boundary; a marker
parent is not qualified merely because its ancestors are nonmutable. Security,
reparse, local-volume, owner, sharing and same-handle evidence remain required.
Source, destination, seven native markers, claim and receipt are eleven distinct
file paths; no file role may also name a participating directory. Case aliases
of a shared parent and missing intermediate parents refuse before setup.

All seven native leaves and the three prospective local outputs are observed
absent before claim creation. Present, unknown, malformed, inaccessible or
missing-parent observations refuse. These checks never authorize overwriting:
claim, destination and receipt still require protected, exclusive `CREATE_NEW`.
No native marker is created, moved, copied, replaced or repurposed as a local
record. No directory creation, existing ACL repair or layout migration exists.

## Held parents and cleanup

`HeldParents` caches each exact ancestor path once across all eleven roles. It
holds and qualifies the parent before resolving an immediate child. Borrowing a
shared prefix inspects that same retained handle and compares identity/security,
then requalifies its full prefix under the borrowing role's private boundary.
Different paths cannot alias the same object; each full role chain must remain
on the root volume. Source and output qualification receive their own full
retained chains, rather than a shared terminal parent.

Logical reference counts record each role's acquired prefixes, including partial
acquisition. They release together only after effects stop. The facade remains
the sole native-handle owner: one reverse ledger drain closes each retained
handle once. Logical release failure, native close failure and temporary marker
handle close failure all preserve cleanup uncertainty and prohibit a success
claim. No output or claim is deleted, even after a partial write or deadline.

## Narrow path-policy compatibility correction

The unchanged #0183 lexical validator also rejected the documented ordinary
`.coordination-runs` directory component. `role_policy.py` supplies a separate
`RolePolicy` subclass with the original metadata, full-chain and held-parent
rules and exactly that additional allowed component. Actual node paths remain
unchanged; there is no path rewriting, global monkeypatch or #0183 byte change.
Security, source and protected-new-file checks remain inherited. This new policy
requires independent review; the old hash alone does not prove the extension.

Other leading-dot names, dot/dot-dot traversal, trailing dots/spaces, empty
components, slash spellings, ADS, device/UNC/extended paths and reserved names
still refuse. The exact packet continues to restrict the full allowed paths;
accepting this one component is not arbitrary-path authority. Every parent must
already exist and pass qualification; missing parents still stop preparation.

## Authority and retained limits

The packet fingerprint covers every role chain, private boundary, process
SID/PID/start-generation/executable hash, public source pins, source hash and
expiry, consent and UTC window. `current_source_pins` now additionally pins
`role_policy.py`. Existing single-parent packets and old source pins cannot be
silently reused. The frozen #0161 proposal still records the earlier source
contradiction as history and needs its own later reviewed update.

One continuous UTC/monotonic admission history spans setup, process observation,
all branch acquisition/observations and effects. The live invocation is consumed
before DLL setup. Maximum window remains 900 seconds. Source expiry must exceed
the deadline. At most one bounded 8192-byte credential read occurs, with exact
source fingerprint, source metadata and process bindings preserved. Claims and
uncertain or partial outputs prevent replay; receipt failure never permits a
second source read. Closing owned resources remains mandatory after expiry.

The durable receipt records pre-close cleanup as unknown; only the separately
returned result records final close outcomes. Neither receipt enables native
consent or POST readiness: `nativeConsent` and `actionReady` remain false. Fresh
actual inspection, applicable current credential/grant evidence, independently
reviewed exact packet and genuine bounded local-action consent remain unpassed.
Expired October 18 authority is not reused and no replacement token is requested.
Caller handshake/result-root freshness and final cloud/native/operator gates
remain separate, unproved work.

## Source-only verification

Pinned uv 0.12.5, frozen environment, Python 3.14.7, Ruff 0.16.3 and standard
Windows/Python 3.14 Pyright 1.1.411:

- 57 deferred-probe tests pass: the prior 45 adapted regressions plus 12 new
  topology/custody/fault tests. Public documented path literals pass only with
  invented handle/security/process/credential observations. Shared-prefix counts
  and single-close outcomes are asserted. Both CLI defaults remain NO APPLY.
- Cases cover role substitution, exact marker inventory, record/native and
  file/directory collisions, case/object aliases, reparse, ACL/private-boundary,
  share, volume, unknown/present outputs, partial writes, no second read,
  continuous branch deadlines and cleanup uncertainty.
- All 38 unchanged #0183 regressions pass. Its adapter and guard SHA2-256 pins
  remain `dda739925d0a3d55aecad3c914f7690f15c5d7518f4927d3980d351e0d5ba3d9`
  and `856d98523a82722bc1bedbdd6a47a95be6011a524472a3620559995964ff0c6a`.
- Scoped Ruff check/format, standard Pyright and `git diff --check` pass.

The c138206 operations record
[`post-local-preparation-binding-2026-10-19.md`](post-local-preparation-binding-2026-10-19.md)
remains unchanged. Passing injected source checks establishes path expressibility
and modeled refusal behavior, not actual custody, token eligibility or delivery.

## Independent review and integration

Fresh independent High review passed with no material findings. All fifty-seven
deferred tests and thirty-eight unchanged #0183 regressions pass, with Ruff,
formatting, standard Pyright and whitespace checks. Extra injected cases cover
distinct native/claim/receipt branches, post-acquisition failures, private role
boundaries, strongest shared-boundary checks and lexical escapes. The parent
reproduced all fifty-seven installed deferred tests. These are source/injected
checks only; actual private custody, current packet and local/native/POST action
authority remain unqualified.
