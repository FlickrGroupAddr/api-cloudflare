# Bounded metadata preparation: source boundaries

Status: source engineering evidence; actual collection and qualification disabled.

A response-body limit alone does not count HTTP status lines, headers or chunk
framing. The existing metadata collectors use the bounded transport in
`scripts/hosted_publisher_execution_provider.py`; no replacement parser is needed.
Its wire metric counts decrypted HTTP bytes, including framing. It does not count
TLS records, TCP/IP overhead or retransmissions.

For a proposed fixed subset of seven configuration GETs and the existing
indivisible three-GET grant sequence, a 65,536-byte body policy gives these
source-derived ceilings:

| Metric | Bytes |
| --- | ---: |
| Outbound HTTP | 43,015 |
| Accepted inbound HTTP | 1,114,112 |
| Conservative inbound, including refusal sentinels | 1,114,122 |
| Bidirectional HTTP, including refusal sentinels | 1,157,137 |

Each configuration request uses a 131,072-byte response HTTP limit and a separate
65,536-byte body limit. Each grant request uses a 65,536-byte response HTTP limit.
The reader may consume one additional sentinel byte when it refuses an oversized
response. The conservative sum includes a sentinel for each call; a real
stop-on-first-failure sequence need not consume all of them. These figures apply
only to the fixed selectors and exact proposed caps, not every supported policy.

Configuration selectors cover three exact D1 identities and deployments/versions
for two exact Worker names. They provide bounded projections, not a complete
current settings, code, namespace, object-population or holder inventory. The
grant order remains test-credential verification, reader verification, then
details of the test ID returned by the first verification. No token listing or
continuation is added.

The configuration collector retains its strict duplicate-header policy. The
grant collector retains its accepted management-only Set-Cookie discard policy:
count and validate each field, discard cookies, and refuse other duplicates.
Framing, redirects, identity encoding, source/grant checks, fixed numeric address,
absolute deadlines, no-replay claims and cleanup remain with their existing
owners. A new planning ledger cannot replace those execution gates.

These HTTP limits do not establish provider-descendant SQL or effect counts,
campaign allocation, actual grants, protected-record custody or full-state
capture completeness. Source validators cannot authenticate their own inputs.
Null current facts remain refusals, and source acceptance supplies no live
qualification or permission to replay a stopped attempt.

The source checks use invented targets and socket/TLS substitutes. Seven focused
tests and five additional independent boundary checks passed. The tests exercise
the existing transport; they are not Cloudflare or native-runtime qualification.
