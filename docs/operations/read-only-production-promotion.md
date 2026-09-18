# Read-only production promotion

Status: deployed; real Lightroom Classic read-only validation passed; ready for review.

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

At promotion time, the deployment and every user write gate were paused in D1.
Production had zero dispatch attempts and zero Plugin Code installations. One Flickr
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

## Real-client validation

On 2026-09-18, Terry loaded `FGA-LrC15.lrplugin` 0.1.0.4 in Lightroom Classic
15.5.1. He created the first Plugin Code in the signed-in FGA administration
UI, transferred it directly into Lightroom, and used **Verify stored credential**
after the initial client error was fixed. The plug-in displayed **Connected**
for installation `5446176d-911f-4157-8a22-cac3013969dd`, revision 1.
The bounded local log recorded `request_started` followed by `connected`, with
no credential or HTTP payload. Terry confirmed the browser transfer view and
clipboard were cleared and the private window closed.

Fresh read-only D1 checks after the client connection found one installation,
zero dispatch attempts, and zero enabled deployment or user write gates. They
wrote no rows. The plug-in has no publication or group-add entry point. No
submission or live Flickr group-add was part of this validation; intake and
dispatch remain disabled. The initial promotion's zero-installation count above
is a dated snapshot, not the current production count.

The real-client read-only vertical slice is ready for review. Enabling intake,
dispatch, or either write gate remains a separate future decision.
