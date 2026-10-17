# Fixed-origin v1 actual-handler dependency configuration

This preparation module is qualification-only. It composes the unchanged pinned
candidate `b599ca828d2a645b686aca0354d6c8ee2c2a0250`; it implements synthetic
upstream responses, not an alternate application handler. The captured ordinary
dispatcher, candidate router, authentication and thumbnail implementation remain
unchanged. Native/hosted qualification and #0037 remain unresolved.

## Required construction

- Use a new disposable synthetic D1 binding with the pinned candidate migrations.
  Never inject the production DB or the separate durable quota DB.
- Before opening admission, call `await initializeHandlerCaseNamespaces(db)` once.
  This appends all twenty isolated user/installation/credential/link/grant
  namespaces in one transaction. A repeated initializer fails rather than
  replacing or resetting anything. It needs no extra production migration.
- Construct `createHandlerCaseProvider({ candidate, syntheticDb: db, counters })`.
  The wrapper calls its `fetch(request, scenario)` only after the outer exact
  origin/path/header/time checks and durable FGA admission. The composition still
  owns the 10-minute inner window, 20-minute durable lifetime, 96 FGA/16 receiver
  quotas, abort and final publication fences. This provider cannot access that
  ledger and never initializes or restores it.
- Extend the wrapper/composition's closed selector set from `HANDLER_CASES`,
  retaining aliases `ok` -> `png` and `invalid-auth` -> `bad-auth`. Keep edge
  responses layered on the actual `ok` candidate response.
- Use `HANDLER_PATHS` and `BROWSER_PATHS` as exact full path/query allowlists.
  Unknown selectors, incompatible route/case pairs, alternate query spelling,
  extra parameters and non-GET/body requests return an empty 404 before candidate
  work. The `bad-query` stimulus appends its malformed query only internally.

The provider replaces every inbound header with its internal synthetic bearer,
or no bearer/invalid bearer for those explicit cases. It supplies only disabled
write capability flags and synthetic application/grant values. There is no
ambient fetch, client destination, configurable response size or configurable
delay. Upstream Flickr REST/image requests are intercepted in memory and strictly
validated; they never reach Flickr.

## Identity and page binding

`handlerCaseIdentity(scenario)` is the exact configuration source for the expected
installation ID. It is `qualification-<canonical-case>-install`; `ok` and all
browser observation modes use `qualification-png-install`. Tokens are publicly
known synthetic case values, generated internally and not native stored secrets.
The qualification config must not contain an actual installation credential.

The original three paths exercise installation/current, a one-row page and that
row's exact thumbnail. Only normal `png`/`ok` admits the five additional browser
paths. Browser page size is exactly 2, total 3, pages 2: page 1 is `photo1,photo2`;
page 2 is `photo3`. The three matching thumbnail references use linked revision
1. Use unchanged `ExistingPhotoClient.discover(..., page, 2)` and its
`thumbnailPath` construction. Navigation/cancel/stale are runner observations,
not new server selectors, delays or parameters. Row titles identify the fixed
synthetic rows; images are decodable grayscale PNG or generated solid-color JPEG.

Every case has a separate authority namespace provisioned up front. Only the
three `final-*` cases perform precisely scoped authority mutations during their
image fetch; actual final candidate fences determine their responses. Those
mutations persist, including after provider reconstruction. Execute each final
fault once in a run; replays observe the already changed authority and cannot
restore the initial conditions. Use a new disposable run/database for a fresh
matrix. Never delete/reset protected history, case authority or quota state.

## Focused offline check

Run pinned Node 24.22.0 with `--experimental-vm-modules --test
probes/fixed-origin-lifecycle/handler_cases.test.mjs` and `FGA_OFFLINE_FIXTURE`
pointing to the private pinned #0038 fixture. The test verifies fixture/source
digests, the actual VM candidate, SQLite authority/history preservation, all
twenty original #0039 statuses, complete browser pages, exact image bytes,
Worker-only module linkage and closed requests. It does not load Lightroom,
deploy a Worker, contact a provider, or establish SDK allocation/cancellation,
native UI/cache behavior or transport qualification.
