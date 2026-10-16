# Proposed qualification of the fixed FGA thumbnail origin

Date: 2026-10-16. Status: **Proposed plan only; no deployment authorized or performed by
this document.**

## Authority and measured starting point

Accepted architecture ADR 0061 authorizes development and qualification, while
`architecture-design/docs/hosted-thumbnail-candidate.md` remains Proposed. Its exact
endpoint/edge, supported host, response allocation, redirect credential handling and
complete-page/cache gates still apply. The authority order is in
`architecture-design/docs/README.md`; the HTTP route gate is in
`architecture-design/docs/operations/http-route-conformance.md`.

The parent observed a current terminal receipt from network fixture 0.0.1.2 on Lightroom
Classic 15.6, build `202609251514-f839cde9`: ten GET calls completed with outcome
`characterized`. The controlled cross-origin redirect was followed and its receiver
observed one arrival without Authorization or the synthetic canary. The same-origin
redirect ended in the controlled 404, with the canary not accepted. The 16-second
delayed case timed out after approximately 16.1 seconds. Complete 262145-byte image and
error responses reached Lua before its limit checks. These are observations for the
disposable workers.dev experiment, not fixed-origin policy or universal header-stripping
guarantees. No peak-memory or hard total-deadline guarantee follows. Parent-owned
terminal evidence and separate remote-cleanup evidence must retain their own provenance;
the native receipt cannot confirm remote deletion.

## Recommended concrete scope

Prepare a temporary qualification build of the existing **`fga-api` Worker on
`https://flickrgroupaddr.com`**, retaining its existing whole-host custom-domain
attachment. Do not add a new hostname, path-prefix route, DNS record, redirect rule or
separate production Worker route. This explicitly proposes a change to the existing
production Worker artifact and its narrow qualification bindings, which needs separate
review and authorization before execution.

The temporary build would recognize a closed qualification gate, exact run identity,
allowed method/path/query and finite case selector. Only authenticated qualification
requests would receive an isolated synthetic environment. Ordinary requests would
continue through the captured existing production entrypoint/configuration. Incorrect,
expired or malformed qualification attempts must fail closed without reaching real
credentials, data or upstream fetches. A real production bearer must never be accepted
by the qualification branch, even with the gate. This separation needs implementation
and hostile-input tests; it is not an existing property being claimed here.

Proposed new resources are exactly **one fresh synthetic D1 database** named
`fga-fixed-origin-db-{runId}`, and **one fresh receiver Worker** named
`fga-fixed-origin-recv-{runId}` with its own workers.dev endpoint and the same D1 for
bounded counters. `runId` is fresh 24-character lowercase hex. No new Durable Object,
queue, Secrets Store, OAuth grant or Flickr identity is proposed. Synthetic
application/grant reads would be fixed in-memory fixture implementations; the
qualification environment must receive no production database or secret binding. The
receiver would persist only counts and Authorization-present/canary-match booleans.
Neither Worker would log request headers or bodies. Any temporary Actions secret names
and their exact lifecycle must be listed in the later reviewed execution packet, checked
absent, and removed only if created by that attempt; this plan creates none.

The only synthetic requests allowed at the FGA hostname would be:

| Method and actual path | Purpose |
| --- | --- |
| `GET /api/v001/installations/current` | Exercise production installation authentication and the unchanged native adapter's credential verification using an isolated synthetic installation. |
| `GET /api/v001/existing-public-photos?page=1&page_size=1` | Produce one complete synthetic discovery page through the actual router/handler. |
| `GET /api/v001/existing-public-photos/{syntheticPhotoId}/thumbnail?page=1&page_size=1&linked_flickr_revision={syntheticRevision}` | Exercise the actual thumbnail route, query validation, authentication, handler, response construction and native fixed-origin request path. |

Photo IDs/revisions would be fixed in the reviewed packet, including explicitly
enumerated malformed-query cases. No client-chosen URL, owner, upstream host, delay or
byte count is allowed. Seeding and case control happen privately through the lifecycle,
not a public seed/mutation endpoint. The receiver permits only its exact run-specific
receive path and a gated aggregate report. No qualification request invokes bindings,
membership changes, intake or dispatch.

## Can the actual thumbnail path use synthetic data?

Yes at the application-code seam: `probes/existing-photo-qualification/worker.ts`
already calls `createWorker` from `src/worker.ts` with an isolated synthetic D1,
synthetic secret readers and a fixed injected fetcher. The router calls the actual
`photoThumbnailRequest`; `src/photo_thumbnails.ts` validates discovery, destination,
streamed bounds and final authority. That gives a concrete approach for reusing the
handler without real Flickr access. It does not establish that the proposed production
dispatch isolation is implemented or safe.

Prepare the new wrapper separately. Reuse production handlers without weakening
authentication, route validation, URL checks or limits. Replace the old JPEG signature
marker with a genuinely decodable finite synthetic JPEG for decoder observations. Use
only fixed synthetic upstream responses; the simulated static-Flickr URL is never
fetched over the network. Link/grant/revocation cases mutate only the disposable D1.

The release client's `ExistingPhotoClient.authenticatedRequest` already fixes requests
to `https://flickrgroupaddr.com`. A separately versioned qualification entrypoint could
inject a temporary synthetic secure-store implementation and an SDK HTTP dependency
wrapper that adds the gate only to the enumerated FGA requests, while calling the
unchanged adapter/client code. It must never read the user's actual stored credential.
This is a test dependency configuration, not acceptance of the installed production
configuration. No release capability flag would be enabled. Final complete-page/cache
and narrowly authorized real-account reads remain later gates.

## Matrix and finite limits

Propose one attempt with a **20-minute expiry**, at most **96 admitted FGA qualification
requests total** (including adapter verification and redirect requests), **16 admitted
receiver/report requests**, and no retries. Use durable conditional D1 admission and
expiry checks; do not rely on per-isolate counters. Reject before payload work on
exhausted/expired plans, and check expiry again before publication. Quotas bound
admitted fixture work, not all provider traffic or billing. A missing or interfered
observation remains inconclusive.

Run valid PNG/JPEG, exact 262144-byte success, declared and undeclared 262145-byte
upstream excess, finite 262145-byte upstream error, truncation, wrong media/signature,
upstream redirect refusal, a single 16000-ms stalled upstream, invalid
authentication/query and final installation/link/grant changes. The actual handler must
return bounded sanitized errors for rejected upstream cases; it must never send the
large upstream body to the client. Set a reviewed **4096-byte maximum for
application-created error/denial bodies** in the qualification collector, without
claiming an existing provider error cap. Unexpected excess fails the run and is reported
by length only.

Keep two observation classes explicit. Upstream fault cases test the unmodified
handler's refusal and bounded final output. If native-facing edge redirects or
malformed/oversized final responses are required, use a separately enumerated
qualification-only response fault at the **same actual thumbnail path**, after the
handler boundary, with a maximum final stimulus of **262145 bytes** and only fixed
same-origin or run-specific receiver destinations. Such faults measure native/edge
behavior; they do not represent compliant handler outputs or prove the handler emits
them. Review the exact redirect status codes before execution. Do not extend the
existing workers.dev result to untested codes or routes.

The 15-second native timeout remains per documented connection phase. Record elapsed
observations, partial lengths and backend abort/disconnect observations separately. No
supported independent peak-memory observation method has been selected, so this attempt
cannot close peak allocation by returned length alone. Keep allocation, hard total
deadline, production qualification and transport qualification false until the
candidate's actual remaining obligations are resolved.

## Smallest next engineering work and later execution boundary

This work is engineering-owned preparation. There is no reviewed fault-injection
artifact or deployable configuration yet, and no current owner decision is needed to
start these read-only/offline tasks. The existing approved resume is not blocked by this
future plan.

1. Read back the current deployed artifact/version, bindings, compatibility settings,
   effective custom-domain/routing, cache, redirect, transform, firewall/challenge and
   provider-error behavior relevant to the exact three paths. Record a sanitized digest
   inventory and private rollback manifest. The local template and historical deployment
   files are not current provider evidence.

2. First prepare the smallest offline proof
   of closed dispatch and synthetic binding isolation for these three paths; prove real
   production credentials and malformed selectors cannot enter it, and prove the
   captured normal dispatcher remains the selected implementation for other requests.
   Only after that proof, prepare and independently review the finite lifecycle, native
   entrypoint, output faults/bounds, source hashes and cleanup. Run required native
   TypeScript, route conformance and affected handler/client tests. Verify normal
   production paths and all write gates against the captured production configuration.

3. Establish rollback to the exact captured artifact/configuration without changing
   production data. A qualification-only deployment and later clean candidate deployment
   are different artifacts; compare unchanged handler/edge inputs and rerun applicable
   exact-path checks after removing the qualification branch. A temporary wrapper's pass
   alone cannot qualify the final artifact.

4. Present the complete
   deployment/configuration diff, exact resources, request matrix, credentials'
   synthetic-only scope and rollback/cleanup procedure to the parent for review. Only
   then resolve the specific live deployment/native authorization. ADR 0061 and the
   earlier disposable network approval do not authorize this production change.

## Feasibility questions that remain open

The deployment template has `workers_dev:false`, `preview_urls:false`, a custom domain
for the whole hostname, `run_worker_first:true`, observability disabled and
compatibility date `2026-10-16` with `nodejs_compat`. The ignored local production
Wrangler snapshot instead records date `2026-09-18` and no `enable_request_signal`;
neither proves the current deployed state. The proposed use of incoming disconnect
notification requires reviewing the actual configuration and supported provider
behavior. A flag's presence is not disconnect evidence.

No live zone/ruleset inventory was fetched for this plan. Therefore effective edge
response-size/error bounds, redirects, challenge pages, cache bypass and path-dependent
behavior remain unknown. A distinct test path, a narrower route or a workers.dev
deployment cannot be substituted as equivalent. A provider may reject malformed
targets/duplicate Authorization under the accepted scoped HTTP-400 exception; it does
not provide a general exemption for large provider errors or ordinary API responses.

The temporary-build approach avoids assuming that a path Worker can override an existing
custom domain. If production isolation or restoration cannot be made simple and
demonstrable, stop before deployment and return to design. If a separate route is later
proposed, first verify documented provider precedence and exact effective edge matching;
that would be a revised plan, not an implicit fallback.

## Cleanup and conclusions

Before mutation, journal the exact existing deployment/configuration and new resource
identities privately, with nonsecret recovery correlation. Provision/upload each new
resource once; do not retry ambiguous mutation. Expiry stops qualification admission; it
does not restore the deployment or delete resources.

On success, failure, cancellation or expiry, first disable qualification admission and
restore the exact captured production artifact/configuration, then verify ordinary route
behavior and disabled intake/dispatch/thumbnail gates. Remove only this run's
qualification bindings and temporary secrets. Disable/delete the exact new receiver and
delete its exact synthetic D1; verify both absent. Remove only matching-run local
targets/secret material and native cache files. Verify production data/bindings and
unrelated secrets remain as captured. Preserve exact identity information privately when
any step is ambiguous, report cleanup unconfirmed, and never guess a resource or blindly
repeat a deletion.

Retain only sanitized current-run host/build/source/configuration digests, case
outcomes, statuses/lengths/timings, closed marker/canary observations and explicit
restoration/deletion evidence. No raw URL, credential, response/image bytes, headers or
photography metadata belongs in evidence. Production activation, acceptance of the
Proposed thumbnail contract, and downstream write gates remain separate owner decisions.
