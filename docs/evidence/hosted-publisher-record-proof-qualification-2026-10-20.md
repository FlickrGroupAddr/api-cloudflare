# Hosted publisher record-proof qualification — 2026-10-20

The hosted publisher's prospective exact-record deployment proof worked, and
the happy scenario passed all seven finite phases. The complete four-scenario
matrix remains unqualified: the `create_lost` scenario stopped at an unknown
seed outcome, before its intentional lost-reply phase. The other two scenarios
did not proceed beyond initial resource creation.

The attempt used source
[`4398fc9`](https://github.com/FlickrGroupAddr/api-cloudflare/commit/4398fc933fe54854d66c63ee04ac1a7a3e891fe1)
and the accepted [deployment-record proof contract](../operations/hosted-publisher-deployment-record-proof-2026-10-20.md).
Two exact-record deployment proofs and their bindings were verified. This is
positive evidence for that narrow proof path, not a production qualification.

The qualification attempt reserved 110 management requests and 74 mutations.
Its 274 journal rows contained 272 complete entries and two unknowns. All 110
management responses were HTTP 200; those statuses do not describe the finite
client's seed response or establish whether that endpoint was reached.
Source review found no intentional seed fault or exhausted local aggregate
budget that explains the stop. The retained evidence cannot identify its cause.

Separate reviewed cleanup added 24 requests/eight mutations for the four
Workers, then eight requests/four mutations for the four acknowledged synthetic
databases. Each resource has a deletion acknowledgement followed by an exact-ID
not-found observation. Total resource-management reservations were 142 requests
and 86 mutations, within the original 256/160 limits. Both original unknowns
remain unchanged. Not-found observations do not prove physical erasure or SQL
settlement, and disposal does not qualify the failed matrix.

Child issuance and its individually verified retirement used five token-management
requests each. The bootstrap parent remains retained under its accepted policy.
The attempt used five DNS operations, no Flickr calls or real photos, no changes
to existing production Workers or databases, and no native input. Existing
production capability and write gates remain paused.

The accompanying finite-client and operator source adds closed local failure
stages that distinguish admission, transport, response validation and journal
persistence without retaining raw exceptions, headers or bodies. Such diagnostics
describe the local stop point, not an asserted remote root cause. They must
preserve strict response acceptance, unknown outcomes, deadlines, fences and no
replay. Its 80 scoped unit tests and 18 focused independent checks passed; this
is source validation, not another hosted run. A later qualification needs fresh
reviewed source and packet bindings,
identities, credentials and finite windows; this attempt must not be replayed.

Independent actual-result reviews retained private source-bound phase receipts,
read-only journal snapshots, cleanup acknowledgements and exact-child retirement
evidence. No private identities, endpoints, records or credential fingerprints are
included here. The applicable runbook is the
[finite hosted operator procedure](../operations/hosted-publisher-finite-operator-2026-10-17.md).
