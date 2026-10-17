# Disabled Album binding admission

Date: 2026-10-17. Ticket #0108. Offline implementation and independent review
passed; hosted conformance, deployment and native qualification remain separate.

## Authority and implemented boundary

The accepted canonical `docs/proposals/album-binding-photo-association-wire-2026-10-16.md`
owns the exact #0088 schemas and transaction semantics. The accepted service
identity contract owns #0090/#0109 authority. This unit implements only:

- `PUT /api/v001/publish-services/{serviceId}/album-bindings/{localId}`:
  ensure the exact natural key and atomically accept its immutable first photo.
- `GET` on that same resource: return one current, owner-scoped binding snapshot.

The general photo-association endpoint and later obligation delivery remain
#0110 and later work. No materialization worker, Flickr create/add, catalog
callback, status/repair endpoint or production provisioning is added here.

`FGA_ALBUM_BINDINGS_ENABLED` must equal `1` to reach authentication/storage;
it is absent/off by default. No production configuration was enabled. The
registered schemas are projected into the generated inventory/OpenAPI from
the executable registry. Those projections are source evidence, not activation.

## Exact admission and persistence

`album_binding_store.ts` performs one conditional insert and returned snapshot
inside one owning-database batch. It derives current installation credential,
user/service ownership, original owner/link identity, usable native grant and
exact current proved photo from that database. Bare, unknown, failed or
unproved upload IDs reserve nothing. Current existing-public proof provenance
or matching upload proof is required; a future/invalid proof cannot reserve a key.

Migration0020 owns the binding, initial obligation and append-only event.
The binding insertion and initial receipt are one atomic operation with an
exact-pair deferred constraint. Every injected batch failure rolls back all
dependent facts. First committed candidate wins, including when request arrival
order differs. Same candidate/natural-key replay returns the retained receipt
without new work or revision inflation, while rechecking current authority and
proof. Another candidate conflicts. New title/stale expected proof input on a
matching replay does not replace committed identity or title.

SQL guards retain immutable user/service/local key, first photo, receipt and
photoset ownership/history. Archived relationships remain terminal and readable;
same receipt replay does not unarchive or schedule work. Hosted semantic/title
revisions cannot be advanced by arbitrary no-op updates. Lost response after an
actual commit recovers through the same natural key, never a second creation.

## HTTP and parent integration

`album_bindings.ts` receives the raw request after current-credential
authentication. It enforces duplicate/unknown/null refusal, a 4096-byte body
limit, exact numeric integer parsing before lossy conversion, scalar Unicode
title bounds and canonical single-segment URI encoding. Response projection
revalidates exact identities and returns fixed sanitized errors/no-store.

The parent integrated the Worker/registry and generated projections. Default-off
and auth-store503 outcomes retain `Retry-After: 5`. GET allows neither body nor
query. Pending rotation credentials cannot reach ordinary admission. Accepted
shared method/Allow and early authentication/provider exceptions remain intact.

## Independent evidence and limits

- Eighteen actual SQLite/handler/Worker tests passed, including authority races,
  reversed commit order, lost reply, rollback, hostile direct SQL and raw framing.
- Eight independent adversarial scenarios passed across current proof/connection,
  encoded aliases, exact byte boundary, outage and semantic revision behavior.
- The five exported schemas exactly match the resolved accepted #0088 schemas;
  generated projections and native TypeScript7.0.2 validation passed.

Detailed synthetic receipts remain in the private workspace batch evidence.
These results do not establish hosted D1 behavior, concurrent provider execution
or native Lightroom behavior. No network provider/Flickr request, real credential
read, catalog/native action, deployment or production write occurred.
