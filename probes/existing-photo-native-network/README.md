# Finite native HTTP characterization packet

Status: this reviewed packet executed once after explicit owner approval on
2026-10-16. [The retained result](../../docs/evidence/existing-photo-native-network-run-2026-10-16.md)
records finite native characterization, successful CI and exact cleanup. No
production capability was enabled. This remains separate from the passing
disposable hosted matrix and ten native synthetic fixture scenarios; none of
these results establishes native preallocation or total-deadline guarantees.
The proposed-scope wording below is the historical execution packet, not new
permission to repeat its mutations.

## Proposed finite permission scope

Create exactly two fresh workers.dev Workers and one fresh synthetic D1:

- `fga-native-network-src-{runId}`;
- `fga-native-network-recv-{runId}`;
- `fga-native-network-db-{runId}`.

`runId` is 24 fresh lowercase hex characters, never all zero. No existing resource,
custom domain, production binding, real Flickr identity/credential, DO namespace,
queue or Secrets Store is involved. Both Workers use only this directory's fixed
artifact/schema. Their only durable data are two role quota rows with expiry,
request counts and aggregate canary booleans. No headers or credential strings
are persisted or logged. The stock configs are deliberately unreachable and
unbound; reviewed generated copies enable only their own workers.dev endpoints.

The proposed live window is **20 minutes**, starting at the recorded expiry
generation. Each role admits at most **32** case/receiver/report requests through
one conditional parameterized D1 UPDATE; quotas do not reset per isolate. Expiry
is checked by runtime configuration, the same SQL update's database clock and
again before publication, including after delay. Rejected traffic gets a small
JSON response; this quota bounds admitted payload work, not all incoming network
requests or provider billing. At most 8,388,640 source payload bytes can be admitted
at the largest case size. The receiver may admit at most 32 small observations/
reports. It accepts only its one fixed run-specific receiver path or gated report.

This packet does not grant live resource creation, CI dispatch, deployment or a
new Lightroom fixture installation. The primary must obtain the required fresh
Windows action-time approval before installing/invoking the separate new plug-in.
Any review or consent delay consumes no live resource time: generate the expiry
and start the isolated lifecycle only after the concrete scope is approved.

## Exact native target contract

Private `C:/Temp/FGA-existing-photo-network/target.json` has exactly these keys:

```json
{
  "schemaVersion": 1,
  "planVersion": "fga-native-network-v1",
  "runId": "1234567890abcdef12345678",
  "workersDevSubdomain": "synthetic-example",
  "accessToken": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "canaryToken": "SYNTHETIC-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "expiresAtUnix": 1792167600
}
```

Those example values are inert synthetic documentation, not usable deployment
configuration. Generate `accessToken` as 32 CSPRNG bytes/64 lowercase hex, canary
as `SYNTHETIC-` plus 16 CSPRNG bytes/32 lowercase hex, and `expiresAtUnix` as the
current UTC Unix second plus at most 1200. The strict workers.dev account subdomain
is recorded from the reviewed account; origins derive from exact names above,
never from an arbitrary target URL. The client sends `X-FGA-Network-Access` on
source/report requests and `Authorization: Bearer <synthetic canary>` only on
source case requests. Real credentials are forbidden. Report requests must omit
Authorization; the fixed receiver path intentionally needs no custom gate so
redirect header stripping can be observed rather than concealed by a gate.

All responses constructed by this artifact have no-store, nosniff and
`X-FGA-Network-Probe: fga-native-network-v1`, including denials. The public marker
is diagnostic and forgeable. Unknown paths/queries/origins, non-GET methods,
unsupported source authorization and missing/wrong gates are rejected without
charging an admitted-payload quota. There is no client URL, byte count, delay,
owner or redirect-destination parameter.

| Source GET path | Status and finite response |
| --- | --- |
| `/v1/cases/png` | 200, image/png, 68 bytes; decodable synthetic pixel |
| `/v1/cases/jpeg` | 200, image/jpeg, 634 bytes; generated solid-color 2x2 JPEG |
| `/v1/cases/boundary-image` | 200, image/png, 262144 bytes; signature/allocation fixture |
| `/v1/cases/oversize-image` | 200, image/png, 262145 bytes; signature/allocation fixture |
| `/v1/cases/oversize-error` | 503, text/plain, 262145 fixed bytes |
| `/v1/cases/slow-response` | 200/image/png/68 bytes after exactly one 16000 ms delay, subject to expiry |
| `/v1/cases/redirect-same` | 302 only to derived source `/v1/cases/png` |
| `/v1/cases/redirect-cross` | 302 only to derived receiver `/v1/receive/{runId}` |

The native fixture uses its documented 15-second HTTP timeout. Boundary/oversize
PNG markers are deliberately not photographs or full decoder fixtures. The byte
cap here limits the test stimulus; it does not establish pre-allocation control
inside `LrHttp.get` or qualify the fixed production endpoint.

Receiver GET `/v1/receive/{runId}` returns only:
`{schemaVersion:1,receiverReached:true,authorizationPresent:boolean,canaryMatched:boolean}`.
Gated receiver GET `/v1/report` returns only:
`{schemaVersion:1,receiverRequests:integer,authorizationObserved:boolean,canaryObserved:boolean}`.
Report calls charge receiver role total quota but never receiverRequests/canary
flags. A fresh baseline must be zero/false/false. Report failure, expiry, quota
refusal, unexpected counts or external interference yields an inconclusive
characterization, never a forwarding or credential-protection pass.

## Bounded lifecycle and exact cleanup

1. Before any mutation, persist private account/run journal and nonsecret exact
   fresh resource-name recovery marker. Check both exact Worker names absent.
   Do not accept resource IDs or names from an old run.
2. Create the one D1 once. Validate and journal its returned canonical ID/name
   before applying `schema.sql` or any dependent operation. Seed exactly two rows
   using the fixed statement below with bound run ID, role and shared expiry.
3. Build this artifact once with the pinned native TypeScript gate and Wrangler
   dry-run. Record artifact/schema/generated configuration hashes. Generate the
   two private configs from the stock templates: exact names, only the new D1,
   role/run/subdomain/expiry and the synthetic gate/canary. Enable observability
   neither in configs nor metadata; never attach a tail that records headers.
4. Upload each Worker once and journal its acknowledged exact identity before
   enabling that Worker's endpoint or another dependent operation. Do not retry
   ambiguous create/upload. Retain exact-name provenance for read-only ownership
   reconciliation; no broad name-prefix scans/deletion.
5. Only after parent review and fresh Windows action-time consent, write the
   private target file and install/invoke the separate finite native fixture.
   Its eight source cases and baseline/final receiver reports are bounded; a
   followed same-origin redirect consumes one additional source request. No
   production plug-in setting or actual Flickr request participates.
6. On completion, cancellation or failure, disable the two acknowledged endpoints
   and delete only the exact two Workers and D1 created by this run. Verify both
   Worker identities and the D1 absent. Unknown/ambiguous resources are not guessed
   or deleted; they require private exact-name/ownership review. Expiry alone is
   not cleanup. A forced process stop may prevent cleanup; preserve the recovery
   correlation and report that state truthfully.
7. Remove only this run's private target/config/temporary secret files, checking
   their recorded identity/hash so a later run's file cannot be deleted. Retain
   only sanitized case/status/length/time/marker/canary booleans and cleanup state;
   exclude origins, account/resource IDs, bodies, headers, tokens and journals.

Fixed seed statement, executed once for each role with parameters:

```sql
INSERT INTO network_probe_budget(run_id,role,expires_at_unix) VALUES(?,?,?);
```

No cross-service atomicity is assumed: each role's quota/observation is one
conditional SQL operation owned by the disposable D1. A lost observation/report
stays inconclusive. There is no production state transfer or authority claim.

## Offline verification

```console
node --test tests/existing_photo_native_network.test.mjs
node node_modules/typescript/bin/tsc --ignoreConfig --noEmit --strict --target ES2023 --module ESNext --moduleResolution Bundler --types @cloudflare/workers-types,node --skipLibCheck --allowImportingTsExtensions probes/existing-photo-native-network/worker.ts
```

Five offline tests pass on portable Node 24.22.0, including finite cases,
fixed redirects, denial before quota use, baseline/report privacy, a concurrent
32-of-64 admitted-request check and expiry including delayed publication.
Pinned native TypeScript 7 passes. The JPEG was generated locally from a solid
2x2 bitmap and its decoder successfully read its dimensions; no real photo was
used. No hosted or Lightroom action is evidence from this packet preparation.

## Manual Actions execution mechanism (prepared, not dispatched)

The separate `.github/workflows/existing-photo-native-network.yml` and
`scripts/existing_photo_native_network_lifecycle.py` reuse the proven bounded
provider transport, credentials reader and local bundle helper. They do not
change the passing hosted harness or any production runtime/release artifact.
No local operator token file or local Cloudflare environment is needed.

After explicit approval, the primary first checks that these two repository
Actions secret names are absent; never overwrite a pre-existing secret:

- `FGA_NATIVE_NETWORK_ACCESS_TOKEN`: fresh 64 lowercase hex synthetic gate;
- `FGA_NATIVE_NETWORK_CANARY_TOKEN`: fresh `SYNTHETIC-` plus 32 lowercase hex.

The existing `FGA_CLOUDFLARE_CI_TOKEN` and account variable are reused unchanged.
Only the approved primary creates/removes the two temporary secrets; the new
workflow has no repository-secret management permission. Remove only those two
newly created secrets after the run, including preparation failure. No secret
value belongs in dispatch inputs, arguments, URLs, logs or uploaded artifacts.

One manual workflow has these fixed stages:

1. Locked Node 24.22.0/npm 12.2.0/Python installation and offline server/lifecycle
   checks, before provider credentials enter a step.
2. `prepare` creates exactly one D1 and two Workers once, persists exact created
   identities before dependent operations and uploads only the fixed artifact.
   Its four-minute observed preparation deadline is checked between bounded
   operations; the step has ten minutes for an in-flight bundle/call and cleanup.
   Fewer than five minutes left in the original 20-minute window refuses ready.
3. The ready step publishes `existing-photo-native-network-ready/ready.json`
   while endpoints remain available. Its complete nonsecret operator handoff is
   `{schemaVersion,planVersion,runId,workersDevSubdomain,expiresAtUnix}`. It is not
   tracked evidence and contains no token, account ID, actual resource ID or URL.
   The primary combines it privately with the two synthetic values for the exact
   seven-key local target. Ready upload failure skips waiting and triggers cleanup.
4. The always-run `hold-cleanup` stage reads the same job's private journal,
   checks account/job and derived resource identities, and polls only the two
   fixed D1 counter rows at most 121 times, with ten-second sleeps capped by the
   original expiry. Counter/report failure triggers cleanup. At the second gated
   receiver report (baseline plus final), it waits a practical **60-second grace**,
   also capped by expiry, then cleans up. The report counter is committed before
   the native HTTP response finishes: this grace does not prove client completion.
   The primary must separately verify the native terminal receipt.
5. Cleanup deletes only acknowledged exact resources and verifies absence; a
   deletion marked attempted is never blindly repeated. An ambiguous create or
   upload is never retried or guessed, and leaves cleanup unconfirmed. Finally
   retains only sanitized `cleanup.json`, with exact-name recovery, source/
   artifact/schema hashes, finite counters and cleanup flags. No native capability
   pass is inferred from preparation, the final-report counter or cleanup alone.

The hold/cleanup step has twenty-five minutes and the job has thirty-five minutes.
The original resource expiry remains twenty minutes from preparation, regardless
of job duration. One in-flight bounded call can finish after expiry before
cleanup. Job/process termination may prevent finally or artifact upload; the
runner flushes only fresh nonsecret run/name correlation before mutation for
read-only ownership reconciliation. Never rerun a mutation to resolve ambiguity.
The private ID journal remains on that ephemeral runner and is never uploaded.

Approval still must cover exactly two Workers plus one D1, the two temporary
Actions secrets, the finite lifetime/payloads above and later fresh Windows
action-time approval for the separate new native plug-in. No installation or
invocation is authorized merely by accepting server code or CI cleanup. The
fixed production FGA endpoint/edge and real-credential path remain unqualified.

Lifecycle review corrections: the hold/cleanup step is twenty-five minutes,
inside the thirty-five-minute job. The original twenty-minute expiry is shared
across preparation and holding. A fake-clock no-final-report run waits the full
1200 seconds, then simulates all nine cleanup calls taking their 30-second
transport budgets: 1470 seconds total, below the 1500-second step. The practical
60-second final-report grace remains capped by the original expiry.

The sanitized cleanup receipt distinguishes `dryRunConfigSha2_256` from each
Worker's `uploadMetadataSecretElidedSha2_256`. The latter hashes actual upload
metadata with both secret_text values replaced by `[SECRET_ELIDED]`, using
canonical sorted JSON. Only hashes are published, never raw config, resource
IDs or secret values. The regression extracts actual multipart metadata to
verify both elisions and the receipt digest. Seven fake lifecycle tests pass;
Ruff and Pyright pass. No live operation or dispatch was performed.
