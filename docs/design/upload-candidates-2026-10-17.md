# Advisory upload candidates — staged implementation

Date: 2026-10-17. Scope: #0105; production remains disabled.

Authority: accepted architecture `docs/proposals/upload-ambiguity-candidate-wire-2026-10-16.md` (#0086), ADR0012 and service contract section 5.6. The FGA API backend returns transient display observations only. An empty, failed, partial, stale or capped page establishes no upload outcome.

## Core and wire

`src/upload_candidates.ts` exports the closed GET registry entry, response schema and `uploadCandidatesRequest(env, auth, authorizationId, url, fetcher, optionalMonotonicClock)`. The environment extends the existing DB and secret-read interfaces with `FGA_UPLOAD_CANDIDATES_ENABLED`; only literal `1` enables it. The parent integrates Worker authentication, body rejection, registry and OpenAPI projections; all path responses, including authentication/method failures, require `Cache-Control: private, no-store`.

The handler requires exactly one bounded `page` and `page_size`, retained installation/user ownership, current credential identity and revision, and the authorization's original linked owner/revision. It rechecks credential, grant and authorization after the single read. Signature age does not expire advisory recovery. A committed authorization returns `upload_already_bound`.

The database start observation owns `observedAt` and the fixed issue-relative window: floor(issue seconds)−120 through min(floor(start seconds), floor(issue seconds)+86400), clamped at zero. Future/malformed issue time is unavailable. Old authorizations retain their original day rather than sliding to recent uploads.

The authenticated provider request uses `flickr.people.getPhotos`, the retained owner, content types 0/1/2/3, `date_upload,media,url_q`, explicit bounds and page size. It omits public-only filtering and preserves provider order. Every row must be the exact owner and photo media; classification and visibility do not filter rows. Complete pagination metadata, exact count, unique IDs, UTF-8 title size, inclusive dates and safe thumbnail URLs are checked before publishing any data.

The handler allows one page and no retry/crawl. The 10-second deadline includes secret resolution, database observations, fetch, streaming, validation and serialization. Promise racing bounds waits even when an injected fetch ignores AbortSignal; abort/cancel is cooperative and is not evidence that a real provider's work stopped. Stream bytes are counted before parsing, with a 1 MiB ceiling; serialized display JSON has a 512 KiB ceiling. Either byte failure has the distinct budget error. Out-of-range pages are distinguished from malformed provider metadata. Errors carry no provider content, credentials or candidate fields.

The display projection contains only exact ID, title, upload date, validated q thumbnail and an encoded canonical owner/photo photopage URL. Thumbnail bytes are never fetched. There is no selection, resolution PUT, binding, authorization refresh, recovery-journal write, album or group action.

## Original authority retention

Migration 0019 adds nullable immutable `owner_nsid` and `link_revision` to retained authorizations. Issuance captures both inside its existing guarded transaction. New non-null snapshots must match the current linked record; SQL rejects mixed null/non-null fields and later changes. Existing rows remain null; no link context is inferred or backfilled. Candidate reads of those legacy rows fail unavailable. Unrelated legacy binding behavior remains governed by its existing contract.

## Evidence and limits

`tests/upload_candidates.test.mjs` exercises the actual core with an in-memory SQLite store and injected synthetic transport. It covers exact queries, private rows/order, original-link and credential fences, post-read races, zero/continuation/cap metadata, malformed and duplicate data, raw unsafe URLs, UTF-8 and aggregate budgets, streaming failures, elapsed and hard deadlines, recent/old/future windows and immutable snapshot guards. The existing independent issuance suite now asserts captured authority and retains its signing, race and transaction-fault coverage.

The workspace evidence note is `work-batch-2026-10-17/0105-evidence.md`. These checks are offline implementation evidence. They do not qualify hosted timing/capacity, real Flickr visibility/indexing, thumbnail rendering, native interaction, release enablement or provider acceptance. Client smaller-page restart/manual recovery belongs to subsequent client work; the GET only supplies its accepted error semantics.
