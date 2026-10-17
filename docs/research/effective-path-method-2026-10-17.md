# Effective-path qualification method and design disposition

Date: 2026-10-17. Ticket #0147.
Status: Research complete; current SDK/Cloudflare method remains unqualified.
No replacement design, waiver, production contract or execution authority accepted.
The [canonical Proposed alternative](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/proposals/effective-path-alternative-2026-10-17.md)
provides an exact owner-review private observed-boundary option and the retained
strict/helper alternatives; it is not current policy.

## Outcome

No supported complete method has been established for the current direct
`LrHttp.get` path. The pinned SDK supplies neither a receive ceiling nor
pre-follow redirect refusal. The documented Cloudflare controls reviewed here
do not supply a final response ceiling covering every provider-generated
response on a valid request. Combining these two gaps with finite successful
observations does not close them.

Keep the existing-public-photo production selector and thumbnail capability
disabled. Preserve the existing #0037 unqualified result, #0044 negative review
and #0045 NO-GO disposition. A later native or hosted fault matrix is
characterization within its cases; it cannot establish missing supported
controls. This is a supported-interface evidence conclusion, not proof that an
unbounded response or credential leak occurred, and not a claim that every
possible alternative is impossible.

## Authority and evidence

Accepted [ADR0061](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/decisions/0061-develop-bounded-hosted-thumbnails.md)
accepts bounded hosted-thumbnail development and qualification. Its
[thumbnail candidate](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/hosted-thumbnail-candidate.md)
remains Proposed, requires a documented bounded effective client path and
credential protection, and expressly returns an unqualifiable path to design.
The trusted private backend/edge assumption excludes an arbitrary malicious
replacement server; it does not document a provider error ceiling or SDK
redirect policy.

The accepted [authority hierarchy](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/README.md)
prevents this research from changing that decision. The existing
[intake contract](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/existing-public-photo-intake.md)
requires recognizable complete pages with exact public thumbnails. Omitting
thumbnails, moving routine selection to a browser or treating a known photo ID
as proof would change accepted boundaries rather than solve the transport gap.

Two independently authored source inventories support this synthesis:

- [Pinned SDK15.3 capabilities](sdk-transport-capabilities-2026-10-17.md):
  exact local Adobe source references, hashes, documented signatures and
  helper seams. Host15.6 is historical; no supported host was observed here.
- [Effective edge controls](effective-edge-bounds-2026-10-17.md):
  public official Cloudflare documentation checked on 2026-10-17, with each
  control's coverage and exclusions. No current account/plan/configuration
  claim or account API request is made.

## Proof obligations and their current disposition

| Required claim | Supported facility/evidence | Disposition |
| --- | --- | --- |
| Bound the accepted backend image | The candidate's streaming image limit is 256 KiB, with declared-length rejection, signature/media checks, fixed destination and manual redirects. | A bounded candidate application path; not a bound on responses created before or instead of that handler. Candidate source is not deployed evidence. |
| Bound native response allocation on the effective path | SDK15.3 GET returns a complete body string. No documented receive sink, byte ceiling or allocation ceiling was found. Cloudflare Workers explicitly has no enforced response-body limit. | Unresolved. The returned length cannot describe allocations that occurred before return. No numeric native-copy or TLS overhead allowance is invented. |
| Bound provider-generated valid-path failures | Custom Error Rules and Error Pages can replace selected error classes. Their documented scopes, exclusions, precedence and fallback behavior do not cover every potential response; customization is not a general final-body filter. | Unresolved. A 10 KB inline-content parameter is not an all-provider-response ceiling. Error-class applicability must also be proved; an exclusion alone is not proof that it occurs on this origin. |
| Protect installation credentials before a redirect follow | Backend upstream requests can use manual redirects and fresh credential-free image headers. SDK15.3 exposes no documented native redirect mode or forwarding policy. | Backend upstream protection is separate from native-to-edge protection. A fixed initial URL or post-return Location/status check cannot retract a followed request. |
| Native cancellation/publication/cleanup | Documented progress cancellation is cooperative; the plug-in can poll, reject stale results and clean temporary files. | Requires later exact-host evidence. Missing caller-operated GET abort is an SDK limit; it is not invented as an additional candidate requirement. |
| Backend abort/disconnect | Candidate timers, AbortController and logical publication fences are separately inspectable. Incoming-disconnect support depends on effective runtime configuration. | Requires separate exact-build/configuration proof and observations. Native timeout, closed UI or requested abort does not prove stopped remote work. |
| Native timing | SDK phase timeouts and wall-time observations can characterize finite outcomes. | No hard total deadline or monotonic SDK clock is established. The candidate does not promise a hard real elapsed stall bound. |

The [earlier feasibility verdict](../operations/fixed-origin-feasibility-verdict-2026-10-16.md)
and [authorization disposition](../operations/fixed-origin-authorization-disposition-2026-10-17.md)
remain controlling handoff evidence within their scope. No required bound is
moved into a later live matrix merely to obtain a passing preparation result.

## Concrete design alternatives and material tradeoffs

The conventional recommendation is to preserve the accepted safety gates and
leave this path unavailable while selecting a supported client receive
boundary. Do not add a custom credential broker, local service or second secure
store merely to make an SDK limitation disappear from the report.

| Alternative | Exact boundary or change | Cost and verdict |
| --- | --- | --- |
| Preserve the current design and stop promotion | Retain the fixed authenticated hosted resource and all accepted recognizable-page, fresh-proof and protection rules. Do not enable remote selector/thumbnail production behavior or execute a qualification packet that claims to close the unsupported controls. Resume only when an exact supported method or owner-accepted replacement is available. | Recommended current disposition. The existing-public-photo customer workflow remains unavailable; this is a feature/release limitation, not a qualified substitute. No accepted contract change is needed merely to keep an unqualified feature disabled. |
| Move network receive into a bundled native transport helper | The helper, rather than `LrHttp`, owns every network receive in the selector's initial-installation/discovery/image path. It must refuse all redirects before following, bound response headers and decoded body reads for every status, keep installation credentials out of arguments/files/logs, and export only validated bounded page data and opaque image files to the plug-in. The helper must own cancellation, process lifetime and failure cleanup; the plug-in retains complete-page publication and fresh server proof. | A concrete replacement boundary, not an implemented solution. Documented `LrTasks.execute` and localhost sockets are launch/IPC seams only. Secure credential handoff, IPC identity/allocation limits, signing/update provenance, per-platform packaging, crash recovery and the memory claim still require an exact independently reviewed design. Selecting or implementing that larger trusted component requires architecture review. |
| Accept the direct SDK path's residual risks | The canonical Proposed alternative specifies exact private scope, source clauses needing amendment, post-return caps, configuration snapshots and finite redirect/cancel evidence, while naming the unresolved allocation/provider-error/pre-follow bearer risks. | Not recommended because a long-lived installation bearer may be exposed before plug-in code regains control. This changes the promised safety property; no synthetic matrix, private deployment label or generic execution approval accepts it. The present task records no waiver or justification. |
| Drop remote thumbnail presentation or move it to the browser | Change the accepted intake interaction and recognizable-photo requirement explicitly; discovery/proof transport still needs its own safe boundary. | Not a transport fix. It loses accepted in-Lightroom Classic visual identity or workflow behavior and cannot be slipped in as a fallback. |
| Change hosted platform or add another reverse proxy | Place another responder between the same SDK and the current backend, then prove that platform's complete effective failure/redirect behavior. | Does not supply the missing SDK receive/redirect controls by itself. No concrete unmet storage requirement or comparative operational evidence justifies an AWS fallback here. |

For the helper alternative, supported Windows facilities illustrate why a
separate boundary could be investigated, without establishing a complete
design: [WinHTTP redirect policy](https://learn.microsoft.com/en-us/windows/win32/winhttp/option-flags)
can return 30x without following and exposes a response-header bound;
[WinHttpReadData](https://learn.microsoft.com/en-us/windows/win32/api/winhttp/nf-winhttp-winhttpreaddata)
accepts a caller-owned fixed read buffer. These controls can bound application
consumption with a checked cumulative counter, independent of whether an error
originated in the Worker. They do not publish a universal WinHTTP/TLS allocation
ceiling. A process-isolation proposal would separately define its memory claim:
Windows [job memory limits](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_extended_limit_information)
bound committed virtual memory for the assigned process/job, not all kernel,
driver or operating-system memory. No such helper/job exists in this batch.

No secure helper credential interface has been selected. A socket close alone
does not abort its HTTP operation; a helper launch does not authenticate IPC.
Passing the bearer on a shell command line, environment, ordinary temporary
file or diagnostic handoff is not an acceptable shortcut. A second persisted
credential store would also conflict with the accepted
[installation lifecycle](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/decisions/0019-revisioned-installation-credential-lifecycle.md)
and [private transfer ceremony](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/private-install-credential-transfer.md)
unless explicitly amended. Required proof remains ahead of implementation and
qualification; this note does not promote the helper option on an incomplete
happy-path demonstration.

## Review and next owner

The exact next decision is whether to retain the accepted feature gates,
consider the canonical Proposed private observed-boundary amendment, or pursue
a separately scoped native-helper design through architecture authority. The current engineering result is
complete negative feasibility evidence and the concrete alternatives above;
there is no supported positive method ready for the main native attempt.
Generic live permission cannot resolve it.

The parent coordinator owns independent review, any owner-decision handoff,
board state, integration and verified publication. The canonical proposal is ready for independent architecture/security review
and deliberately recommends keeping the strict contract. Implementation must
not rely on its private amendment until the governing ADR/contract changes are
accepted. No accepted source was amended here because no replacement was
selected or accepted.

Executed for this synthesis: read-only board lane verification, authority and
source-inventory review, and public official-document research. No tests were
needed for this evidence-only document. No account/provider API, native
initialization/input, credential read or presence probe, private capture,
real-photo input, capability activation or live qualification occurred. Static
format/link checks are reported separately from independent review. All
deployment, provider-restoration, changed-secret, production-preservation,
transport/native-qualification, feasibility-change and release assertions remain
false.
