# Disabled Album photo-association admission

Date: 2026-10-17. Ticket #0110. Offline implementation evidence only;
hosted D1 qualification, deployment and native execution retain separate gates.

The accepted canonical `docs/proposals/album-binding-photo-association-wire-2026-10-16.md`
owns the admission schema and natural-key replay semantics. Accepted #0092
status vocabulary is consumed by storage; proposed #0094 lifecycle commands
are not exposed by this work.

`PUT /api/v001/album-bindings/{bindingId}/photo-associations/{photoBindingId}`
authenticates a current installation credential, refuses pending rotation,
and hands the raw request to the strict Album parser. The request has exactly
`schemaVersion`, `expectedBindingRevision` and `expectedVerificationRevision`.
Canonical path encoding, no query, duplicate-member refusal, exact safe
integer parsing and the 4096-byte UTF-8 JSON bound apply before admission.

The owning database transaction derives user, service, link and exact photo
authority. A new natural-key obligation requires current expected revisions
and an active collection; it advances binding revision once. Exact replay
returns the retained receipt with 200 without revision inflation, including
an archived relationship, while rechecking current authority. New work
returns 201; neither response claims remote membership or carries Location.
Unknown/foreign resources, stale fences and failed authority reads retain
the accepted sanitized errors. Failed admission retains no partial obligation.

`FGA_ALBUM_OBLIGATIONS_ENABLED` must equal `1`; it is absent/off by default.
The executable registry owns the request/response projection and generated
inventory/OpenAPI. Default-off and unavailable authentication retain
`Retry-After: 5`. No Flickr dispatch, worker wake, image upload replay,
materialization, status/repair route or lifecycle command is added here.

Focused integration verification used pinned Node24.22.0, native
TypeScript7.0.2, API generation/check and the existing route tests. Storage,
HTTP adversarial tests and independent review have separate evidence in the
parent batch handoff. No live/native conformance is claimed by these checks.
