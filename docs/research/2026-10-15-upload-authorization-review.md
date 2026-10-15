# Hosted direct-upload authorization review (#0034)

Status: independent source review and 40 local synthetic checks passed,
2026-10-15, including the staged public Worker integration. Complete candidate
qualification remains a parent integration gate.

This review concerns issuance of an in-memory signed upload envelope and its
durable non-secret correlation record. It does not authorize deployment, a real
Flickr request, an image upload, client publish integration or broader #0026 work.

## Governing authority

- Canonical architecture `AGENTS.md` and accepted ADR0005 define backend signing,
  direct client-to-Flickr multipart upload, secret custody and the reusable-bearer
  limitation. Accepted ADR0013 requires both deployment and linked-user gates
  before issuing an upload authorization. ADR0051 permits guarded native storage
  for the private owner without weakening atomicity, fencing or audit.
- Accepted `plugin-service-contract.md` section4 owns the exact request metadata
  and response fields. Its gate section requires `503 flickr_writes_paused`,
  `retryable:false`, correlation ID and no `Retry-After` when either gate is paused.
- The accepted administrative-control-plane audit section requires a successful
  database mutation and its audit event to commit together. A failed audit append
  must refuse envelope issuance rather than leave an unaudited authorization.
- `research/upload-signing-boundary.md` is supporting evidence, not independent
  permission to alter those rules. It documents that Flickr accepted a reused
  nonce during its timestamp window; no implementation may claim provider-enforced
  single use, a shorter hard expiry, image-byte signature binding or distributed
  cancellation of an already issued envelope.

## Required boundary

`POST /api/v001/upload-authorizations` authenticates a current installation and
accepts only `{schemaVersion:1,flickrMetadata:{...}}`. Optional `title`,
`description` and `tags` are strings. Required string enums are `is_public`,
`is_friend`, `is_family` (0/1), `safety_level`, `content_type` (1/2/3) and `hidden`
(1/2). Reject client-supplied `photo`, `api_key`, OAuth fields, unknown fields,
invalid types and invalid combinations. The scoped contract does not define a
specific prohibition on public visibility combined with friend/family flags;
do not invent that restriction as accepted policy.

Successful JSON returns exactly schema version, generated upload authorization
ID, issue time, fixed `https://up.flickr.com/services/upload/`, OAuth Authorization
header and exact signed metadata with backend-injected `api_key`. The signature
covers every non-file upload field. Image bytes are absent from this API.
The response is sensitive bearer material and requires `Cache-Control:no-store`;
it must not be logged, traced or persisted. No expiry/single-use guarantee is
part of this response.

Before handing out that response, persist the authenticated installation, FGA
user, issue time and nullable photo ID initialized to null, keyed by the generated
authorization ID. Persist no title, description, tags, signed metadata, URL,
Authorization header, application secret or token secret. Final commit must
revalidate current installation authority, linked owner/revision/generation and
both enabled gate revisions after asynchronous secret resolution/signing.

## Independent validation plan

1. Exercise the public Worker route using synthetic installation/native-secret
   fixtures and a provider callback that refuses unexpected network operations.
   Check strict request types, known field enums, injected-field denial, body/media
   limits, expired/revoked/foreign credentials and both durable gates.
2. Reconstruct the RFC5849 normalized parameter string and HMAC-SHA1 signature
   independently with Node crypto using fixed synthetic secrets and the emitted
   nonce/timestamp. This checks actual transmitted metadata, punctuation, Unicode,
   whitespace and empty strings without verifying the OAuth library against itself.
3. Check no-store on successful/error responses, exact response fields, no secrets
   in errors/logs, no provider upload call and no persisted envelope/metadata.
4. Force failure at every actual issuance batch statement, including audit,
   confirming complete rollback and no response envelope. Inject revocation,
   owner/link/generation/lifecycle/gate changes during secret resolution and
   confirm final authority fences refuse issuance.
5. Record exact executed test results and review findings after implementation
   exists. Local synthetic proof does not qualify a new production artifact;
   deployment and the real publishing path retain their independent gates.

## Findings resolved during implementation

The initial issuance transaction lacked a first-class audit append. The backend
implementation now commits `upload_authorization.issued` with the correlation
record and refuses envelope release if any statement fails. Failure audits are
separate sanitized evidence and do not make an issuance transaction successful.

The first authority check reused `linkedGrant` without consulting native
connection availability. The implementation now also requires linked/available
connection state with no pending operation at initial authority selection,
after secret resolution and in the final transaction. This matches the existing
production dispatch boundary. A pending native generation or a mismatched owner
also defeats the operation.

The new schema now guards ordinary inserts against foreign installation/user
ownership and pre-populated photo IDs; it preserves authorization identity and
retained records. These protections complement the application commit guard.

## Observed evidence

`tests/upload_authorization_independent.test.mjs` and
`tests/upload_authorization_route.test.mjs` passed **40/40** against the staged
implementation/Worker/registry, all current base migrations and the new 0015 migration.
The isolated runner adapted source import paths into writable staging; it did
not modify the implementation checkout. Runtime was Node.js 24.20.0 with its
local SQLite 3.53.4 adapter. This is local behavior evidence, not Cloudflare D1
engine provenance or a hosted conformance pass.

The checks cover independent signature reconstruction over exact Unicode,
punctuation, newline and empty-string metadata; strict input/enum/field rejection;
paused/deactivated gates and no-store responses; forged installation/owner/
generation refusal; twelve authority mutations during secret resolution and
the same twelve immediately before the final batch; failure at each of the five
issuance transaction statements including audit; minimal persisted data;
ordinary-SQL ownership/retention guards; bounded payload rejection and sanitized
errors/logging; fresh nonce/authorization IDs; and no expiry/single-use claims.
The revocation fixtures commit both version and installation changes with the
required null pointers and revocation timestamp; race tests mark a mutation as
applied only after its SQL succeeds.

The eight HTTP tests exercise the actual Worker route and existing common
authentication/JSON-framing code. They establish current installation bearer
authentication, pending rotation `403 insufficient_scope`, revoked credential
`401`, refusal of cookie-only/malformed/duplicated credentials, dedicated flag
rejection before credential lookup, method/path/query rejection, request media/
encoding/body limits, unchanged nonretryable paused-gate responses and no
provider call. Issuance succeeds with its dedicated flag enabled while group
intake and dispatch remain disabled. The route does not bypass the common
installation authentication policy or accept a browser session as authority.

SHA2-256 of the tested staged inputs:

| Input | Digest |
| --- | --- |
| `src/upload_authorization.ts` | `6aa5ef5086e4166adba95e469333bd5642fa0604c25004a2ac22a58343260dff` |
| `migrations/0015_upload_authorizations.sql` | `0bcc8f137c338008b58b5b31030aa7c171faede5452bbb55002e327713b1fef1` |
| `src/worker.ts` | `3ad9effe30b71dc5d007045122e30048f051935f8553eb1d5b1941b0be695d4c` |
| `src/registry.ts` | `07086001e4df52648bd4ccfa757bca68d1bda19d9679fd909cfda771934b0747` |
| Independent module test | `42af9e590aa192e267c8948ef5da89fb6206ec19b6779776c5a4638eea16e592` |
| Worker HTTP test | `2c60daa7e9200cf345702d8501e6a7a778a6b22e8344777c4d59ce57e75e33b4` |

After copying the staged implementation and both tests into the implementation
checkout, reproduce the focused checks with:

```powershell
node --test tests/upload_authorization_independent.test.mjs tests/upload_authorization_route.test.mjs
```

Before #0034 becomes ready for review, integrate the route/registry/disabled
feature flag, regenerate and verify OpenAPI, compile with pinned native
TypeScript and run the relevant full regression checks. Rerun the focused tests
against the final integrated source. Preserve the disabled production configuration
and independent exact-artifact qualification requirement. Nothing here proves a
real upload, uploaded-photo binding or complete client publish lifecycle.

No live provider request, credential retrieval, catalog access, board write or
shared implementation-source modification occurred during this review.
