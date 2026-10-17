# Disabled publish-service identity implementation

Date: 2026-10-17. Implementation evidence for #0109; qualification remains pending.

The [accepted create/read contract](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/proposals/publish-service-identity-wire-2026-10-16.md)
and its 2026-10-16 #0090 owner acceptance control. This note describes its
implementation, not a second wire specification. Every successful POST creates
a distinct backend-generated identity. Lost responses can leave retained unused
rows; no client nonce, catalog key, reservation, expiry or activation is added.

- `src/publish_services.ts` exports registry metadata and the disabled handler.
  The parent Worker authenticates each request with `allowPending=false` before
  calling it, preserving the raw request for the bounded closed POST parser.
  Pending credentials retain the shared 403 behavior; revoked or replaced
  credentials fail shared authentication. The committing database statement
  independently requires the current credential.
- Migration `0018_publish_service_identities.sql` retains immutable identity,
  owning user, issuing installation and link snapshot. SQL rejects modification,
  deletion and replacement. No provider credentials, catalog paths, names,
  albums, uploads or work scheduling are stored or invoked.
- One `INSERT ... SELECT` derives and inserts the current active installation
  and verified link snapshot inside the D1 transaction. Coarse linked state,
  native credential generation metadata and the connection's durable transition
  pause all participate. No preflight snapshot authorizes a later insert.
- GET joins authenticated installation, same-user identity and current link in
  one statement. Missing/foreign resources have the same sanitized 404.
  Transition/unavailability precedes link change; the issuance revision stays
  immutable. A ready response is an observation, never later write authority.
- The default feature flag remains off and `hostQualified=false`. No actual
  provisioning, deployed D1 changes, native SDK callbacks, Flickr access or
  live account/credential actions were performed.

`PublishServiceIdentityClient.lua` is a pure Lua configuration adapter with
injected settings, serialization and HTTP seams. `configure(settings)` rereads
durable per-service settings under `withServiceLock`, resumes any saved identity
through exact GET, and creates only when the identity is absent and
`hasRetainedRecords(settings)` explicitly returns false. It validates the
complete success, saves the immutable record and rereads its exact contents
before returning an identity. Failed/malformed saves or responses return no
usable identity. Another observed saved identity takes precedence over an
unused create response. No failure automatically replaces a saved identity.

`verifyService(settings)` performs only fresh GET and durable exact-record
verification, returning `{ok=true, identity=..., linkStatus='ready'}` only on
success. The #0096 shell may inject a closure calling this method on the
documented collection's owning `publishSettings`. It never provisions during
publish. Identity includes schema version and all five immutable persisted
fields; link status is never stored as authority.

The injected `request(method,path,body)` returns `{status,body,headers}` with a
decoded JSON body and canonical security-header names. The future HTTP adapter
must enforce the accepted same-origin HTTPS, credential, bounded response and
JSON transport rules. `withServiceLock(settings,callback)` must serialize the
configured service; `read` must distinguish absent (`nil`) from incomplete or
failed reads, `save` must report durable success, and all seams must use the
exact passed configured service. These injected seams are synthetic evidence,
not Lightroom Classic host persistence or serialization qualification.

Verification: actual TypeScript core under Node 24.22.0 with SQLite and local D1
batches; actual Lua 5.1 core via pinned uv 0.12.5/lupa. Tests cover distinct
issuance, shared-user resume, foreign/absent privacy, stale authority and
transition races, atomic failure, immutable retention, malformed/duplicate/
oversized requests, saved-ID resume, orphan-safe create failure, durable
readback mismatch and link-change stops. Local D1 uses pinned Miniflare's
2026-07-30 compatibility profile, not hosted runtime evidence. See the batch
evidence record for exact commands and results. Full native TypeScript checking
and independent review are integration gates owned by the parent.

Album admission must independently recheck the saved service's immutable user
and link snapshot with current authority in its committing transaction. This
implementation cannot qualify later album revisions, copied-catalog conflicts,
SDK 15.3 callbacks, hosted restore, link repair or any release/live action.
