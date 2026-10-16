# Native finite HTTP characterization, 2026-10-16

The approved separate fixture **0.0.1.2** completed one native invocation on
Lightroom Classic **15.6**, Camera Raw **18.7**, build
`202609251514-f839cde9`, targeting SDK **15.3**. The primary observed the host
identity, loaded fixture version, command invocation and terminal native dialog
through the documented Computer Use API. No real photo, installation credential,
Flickr credential or catalog write participated.

[CI 38945950488](https://github.com/FlickrGroupAddr/api-cloudflare/actions/runs/38945950488)
ran source `2be8334b2f7bced5ee459d522e03f737a6909532` and concluded successfully.
The [retained sanitized record](existing-photo-native-network-run-2026-10-16.json)
contains the complete current-run native receipt, source/configuration digests,
host identity and separate hosted/local cleanup verdicts. The native modules
match the independently reviewed 0.0.1.2 hashes; the disposable hosted source
digests match the local checkout. Earlier preparation and stopped attempts remain
historical records; they are not silently relabeled as executed runs.

## Measured results

The fresh terminal receipt reports `stage: complete`, `outcome: characterized`,
`reasonCode: finite_observations_complete`, ten GET calls, eight ordered expected
cases and two valid receiver reports. All recorded timing observations were
valid under the fixture's wall-clock check.

| Case | Native result | Observed milliseconds |
| --- | --- | ---: |
| PNG | 200, image/png, 68 returned bytes | 234 |
| JPEG | 200, image/jpeg, 634 returned bytes | 172 |
| Boundary image | 200, image/png, 262144 returned bytes | 123 |
| Oversize image | 200, image/png, 262145 returned bytes | 203 |
| Oversize error | 503, text/plain, 262145 returned bytes | 86 |
| Delayed response | `timedOut`, no returned body or partial bytes | 16056 |
| Same-origin redirect | Marked, no-store 404 JSON, 21 bytes | 171 |
| Cross-origin redirect | Valid marked, no-store receiver JSON, 93 bytes | 170 |

The same-origin redirect did not obtain the PNG success response. The source
uses one 404 for several gate, Authorization and route denials, so this result
does not identify a stripped header or a specific refusal cause.

The cross-origin receiver response and final aggregate report agree on exactly
one arrival with Authorization absent and canary absent. This supports the
specific observation that the controlled cross-origin redirect was followed
without the synthetic Authorization marker. The baseline was clean; neither
receiver report sent Authorization. This is not a universal credential-forwarding
policy or evidence from a real installation credential.

## Separate cleanup and limits

The CI receipt reports `cleanup_complete`, `cleanupConfirmed: true`, both exact
acknowledged Workers deleted, the exact synthetic D1 deleted, and no cleanup
error. Its stop reason was the final receiver report; native completion was
verified independently. Source admitted count was eight; receiver admitted
count was three, including the two reports and one redirect arrival.

The primary removed only this attempt's two newly created synthetic Actions
secrets and verified both absent. The unchanged existing Cloudflare CI credential
was retained. The private target was matched to its recorded digest before
removal; synthetic gate/canary values were removed from local operator material.
The fixture created zero response files and cleared response references.

`nativeTransportQualified`, `productionQualified`, `allocationBoundProven` and
`totalDeadlineProven` remain false. The native receipt's
`remoteCleanupConfirmed: false` is preserved: the independent hosted cleanup
receipt owns that separate result. Returned sizes do not establish preallocation
bounds or JPEG decoding; the 16056 ms timeout does not establish a hard total
deadline or active cancellation. No production route, migration, capability or
write gate changed.

## Next engineering boundary

Terry's resume/load/run handoff is resolved. The next work is the reviewed exact
fixed-origin qualification packet described in
[the proposed plan](../operations/existing-photo-fixed-origin-plan-2026-10-16.md).
Preparing that artifact is engineering work. Its concrete deployment and native
execution need authorization covering their actual scope; this disposable run
does not authorize changes to the production domain or accept the Proposed
thumbnail contract. Do not ask Terry to repeat the completed selection UX,
outbox proof, native synthetic matrix, or this finite network run merely to
begin that preparation.
