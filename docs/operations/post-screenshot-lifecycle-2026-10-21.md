# Fresh POST screenshot lifecycle — 2026-10-21

`scripts/post_screenshot_lifecycle.py` prepares the original finite synthetic
POST fixture through the shared hosted management transport and returned-ID
Workers Beta machinery. It does not authorize an invocation or qualify native
POST behavior. The screenshot controller, sealed/renewed manifests, receiver
module, SQL schema and original 23-case fixture remain unchanged.

The fresh caller supplies the exact current source closure, account, credential,
numeric management address, sole management owner, current runtime permit and
native evidence. The permit must expose `authorize()`, `remaining_seconds()` and
an irreversible `begin_cleanup()` phase. The caller supplies `Lifecycle` a fresh
exclusive run directory and one numeric owner. Construction claims a private
owner file exclusively; durable request intent is flushed before every request.
The journal contains private resource identities and must remain private.

## Management and configuration

- `Provider` requires explicit `bounded-stateless-cookie-discard-v1` selection.
  The reused execution transport validates and charges every raw Set-Cookie
  line, then discards it without retaining or resending cookies. Other duplicate
  fields, redirects, malformed framing and oversized responses remain refused.
  The separate probe client retains its strict parser.
- The shared provider gains protected resource-name validation; the shared
  deployment helper gains protected projection, module-name and secret-overlay
  hooks. Publisher defaults preserve their original names, `worker.js`,
  `PROBE_*` projection and one-secret behavior. POST overrides accept exactly
  `fga-post-src-<run>`, `fga-post-recv-<run>` and `fga-post-db-<run>`.
- The POST projection accepts only the pinned `worker.mjs`, one created D1,
  `RUN_ID`, `ROLE`, `SUBDOMAIN`, `EXPIRES`, and distinct `ACCESS`/`CANARY`
  secrets. Empty compatibility flags explicitly represent the original absence
  of flags; `nodejs_compat` is not enabled. Observability and logpush are false.
- Creation returns immutable Worker IDs. Version readback checks exact module
  bytes and the closed binding projection (secret names/types are redacted by
  the provider). Deployment's name-addressed seam is bracketed with ID checks
  under the independently established sole-writer assumption. These checks do
  not establish CAS or exclude an external writer.
- The POST strategy is `post-screenshot-returned-id-v1`, without inheriting the
  publisher's disposal-authority label. Before any creation, two exact read-only
  Scripts-name settings GETs must each return 404. These preserve the original
  absence gate; they never adopt an existing Worker or authorize a name-addressed
  mutation. Beta creation still supplies the only owned Worker ID.

## Finite bounds and receipts

Every nested identity, version, deployment, endpoint, query and teardown request
uses one shared 120-call budget, 20-second request/socket bound and 65,536-byte
management response-body cap. The first actual request rechecks at least 1,200
seconds of action authority after source preparation. Resource lifetime is
1,200 seconds; preparation has at most 240 seconds, and ordinary work leaves
the final 240 seconds and ten provider calls for observation and cleanup.

The reserved ten calls comprise one observation export, three calls per Worker
(owned-ID GET, DELETE, exact-ID absence GET), and three D1 calls (owned UUID/name
GET, DELETE, absence GET). The POST lifecycle retains its original direct
deletion of enabled Workers; adding the publisher's separate disable ceremony
would exceed this original reserve. The individual D1 disposal phase remains
DELETE plus one absence read after its prerequisite identity read. A deadline
or budget failure records `cleanup_unconfirmed`; it never enlarges the bounds.
Lifecycle cutoff and first-effect-window checks run again after durable intent,
at the last injected/concrete transport boundary and concrete transport steps.
The final ready-state save is followed by another preparation-cutoff check before
the target can return. Slow local durability never extends the action window.

Unknown create, version, deployment, query or delete acknowledgements close the
shared provider. There is no retry, discovery, name adoption or session restore.
Observation export reuses the original closed 46-row validator.

D1 disposal requires every owned management operation terminal, every Worker
deletion acknowledged and its exact ID absent, no earlier D1 DELETE, and current
permit/account/UUID/name checks. A run that never published a target and made no
native invocation has no acknowledged native caller. Otherwise disposal also
requires the consumed target to match the prepared target exactly and the
same-run validated native terminal status with `responseReferencesCleared`.
Private hashes bind that terminal evidence to the owner/run. A freely supplied
boolean is insufficient. The accepted pinned fixture publishes status only
after its sequential SDK-calling task returns; this establishes the local
producer/SDK-caller terminal state, never remote SQL settlement. Missing,
unknown or inconsistent evidence retains D1 as unknown.
A DELETE returning 404 is recorded only as absence evidence. It never supplies
the deletion acknowledgement required for D1 disposal. An unacknowledged D1
DELETE admits no post-delete GET; the resource remains unconfirmed.

## Verification

Synthetic tests cover exact scope, distinct secrets, source readback drift,
durable intent before transport, explicit profile/owner admission, first-effect
window, account drift, ten-call reserve, exact-ID teardown, local terminal
evidence, lost acknowledgements and retained resources. Existing shared provider,
Worker identity, deployment and concrete transport suites remain required.
All tests use synthetic files, clock and injected transport. No live provider,
DNS, credential, native, catalog or Flickr action forms part of this evidence.
