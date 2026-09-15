# Read-only production promotion

Status: deployed; owner client validation required.

On 2026-09-15, the Worker artifact qualified by CI run 34906117856 was
promoted to the existing `fga-api` production service. Executable inputs after
the qualified commit changed only in documentation, and a fresh production
build reproduced the qualified SHA2-256 exactly:

`5127101077a294008f657c28bcf6df27e75739a112ec4d59d3c6c8c113d23ddf`

The active production flags are:

| Feature | Value |
| --- | --- |
| Administration | enabled |
| Authenticated reads | enabled |
| Submission intake | disabled |
| Flickr dispatch | disabled |

The deployment and every user write gate remain paused in D1. Production has
zero dispatch attempts and zero Plugin Code installations. One Flickr
connection is linked with verified write permission; the promotion made no
Flickr call. The custom domain remains active. Anonymous installation reads now
reach the authentication boundary and return JSON `401 invalid_token` with
`Cache-Control: no-store`; before promotion the feature gate returned `503`.
A submission POST still returns JSON `503 service_unavailable`, and an unknown
route returns JSON `404`.

The previous Worker version is retained as the explicit rollback target:

```powershell
node node_modules/wrangler/bin/wrangler.js rollback 1cc91432-c29b-49db-a160-770319a2a803 --name fga-api --config .coordination-runs/production/read-only-promotion-2026-09-15/deploy-wrangler.json --message "Rollback read-only promotion" --yes
```

The ignored promotion directory contains the prior configuration, exact
qualified bundle, active configuration, deployment record and private Wrangler
logs. Its values must not be copied into public evidence.

## Owner handoff

Open [the FGA administration UI](https://flickrgroupaddr.com/admin/) in the
regular browser profile used for the verified owner account. Sign in, open
**Plugin Codes**, and create the first current Plugin Code for the Lightroom
Classic installation. Transfer that one-time value directly into the real
plug-in; do not paste it into chat.

Then run the plug-in's connection/read check. It must call
`GET /api/v001/installations/current` over HTTPS and show the returned current
installation. Report success or the exact client-visible error. No submission
or Flickr group add is part of this handoff. Intake, dispatch and both write
gates stay paused afterward.

The backend portion is ready for review. The real client check cannot be
completed without the owner's browser session and Lightroom host.
