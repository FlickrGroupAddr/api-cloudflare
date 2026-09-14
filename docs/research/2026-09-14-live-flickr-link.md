# Live native Flickr connection verified

Date: 2026-09-14

The real owner completed Flickr authorization. The initial callback returned
while credential verification was still pending, and the administrative page
showed replacing/replacement pending. Subsequent read-only inspection confirmed:

- connection linked, credential available, revision 3;
- verified Flickr permission write;
- verified owner and native-generation revision match the configured link;
- lifecycle operation complete;
- temporary OAuth transaction/payload retired; and
- both user and deployment write gates paused.

The persistent authority is the connection record, not the earlier callback's
unconfirmed URL marker. No second authorization or credential replacement was
needed to complete this operation. Google owner sign-in, the Strict-cookie
callback continuation and the real Flickr link are now verified. The prior
operator and browser setup blockers are resolved.

The UI previously loaded this metadata only once. It now refreshes every fifteen
seconds while the visible connection has pending lifecycle work. Polling pauses
while hidden, busy, logged out or transferring a Plugin Code, stops on a settled
state, rejects late results after cleanup, and uses a bounded request timeout.
It reads only the connection API and starts no Flickr operation. Tests cover
completion, in-flight cleanup and conditional/retry behavior. Native TypeScript,
JavaScript syntax, Ruff and Pyright checks passed.

The local deployment operator helper also supplies an explicit FGA User-Agent.
This avoids the default Python-client rejection encountered during read-only
inspection; no Cloudflare authorization or zone security scope was changed.

The native credential integration can proceed to owner review. Full production
fail-polite conformance remains separate work: the 56-case/28-mutation runner,
process/deployment-stop adapters, hosted restore/reconciliation and promotion
checks are not complete. Installation reads, intake and group dispatch remain
disabled; only administration is enabled. The live link does not authorize
turning on real Flickr group adds.

[Sanitized evidence](../evidence/live-flickr-link-2026-09-14.json) records the
current artifact, gates and completed lifecycle stages. Refresh an already-open
administration page once to load the new polling controller.
