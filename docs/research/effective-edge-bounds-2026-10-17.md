# Effective edge response bounds: supported controls and gaps

Date: 2026-10-17. Ticket #0147.
Status: Research; no supported complete effective-path qualification established.

## Result and authority

Official Cloudflare documentation establishes useful controls for selected
application responses and selected error classes. It does not establish one
supported control that caps every response body the native client can receive
on a valid FGA HTTPS request, or prevents every redirect before that client
acts. A finite fault matrix can characterize enumerated cases; it cannot supply
that missing guarantee. This is an evidence conclusion, not proof that an
unbounded body or credential forwarding has actually occurred.

Accepted [ADR0061](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/decisions/0061-develop-bounded-hosted-thumbnails.md)
and the still-Proposed [hosted-thumbnail candidate](https://github.com/FlickrGroupAddr/architecture-design/blob/main/docs/hosted-thumbnail-candidate.md)
retain their existing authority and gates. This research refines the provider
half of the [2026-10-16 edge feasibility finding](fixed-origin-edge-measurement-2026-10-16.md);
it neither accepts an amendment nor qualifies a deployment. The existing
[NO-GO disposition](../operations/fixed-origin-feasibility-verdict-2026-10-16.md)
remains applicable until the missing method is resolved.

## Documented behavior versus the needed claim

All public primary sources below were checked on 2026-10-17. Numerical provider
limits retain the documentation's units; KB/MB are not silently converted into
KiB/MiB or a native allocation budget.

| Source and documented behavior | Qualification implication / remaining gap |
| --- | --- |
| [Workers limits](https://developers.cloudflare.com/workers/platform/limits/#request-and-response-limits): no enforced response-body size limit; the separate request-body and cache-object limits concern different boundaries. CPU/memory exhaustion can produce 1102; a free-plan route can fail open to bypass the Worker or fail closed with 1027. | These limits cannot act as the candidate's receive cap. Worker heap, CPU, cache size and upload limits do not bound final decoded native receive bytes. Fail-closed avoids the documented free-plan bypass; it still returns a provider error page. No plan, mode or setting is asserted for the actual deployment here. |
| [Workers errors](https://developers.cloudflare.com/workers/observability/errors/): a production failure preventing a Worker response yields a provider error page, including exception 1101, CPU 1102 and routing 1022 classes. | A final application serializer or catch handler covers its own outputs, not necessarily a response produced before or instead of its execution. The error catalogue supplies no complete final-body ceiling. |
| [Custom Errors overview](https://developers.cloudflare.com/rules/custom-errors/): paid-plan customization requires proxied DNS. Rules target HTTP errors >=400; default security actions require Error Pages rather than Custom Error Rules. WAF custom block responses have precedence. Rules retain existing headers except Content-Type/Length. Error Pages exclude 500/501/503/505 and fall back to default pages without Accept-Encoding. | Coverage and precedence must be proved per layer. Customization is not a blanket final response filter; it does not cover 3xx redirects. Preserved headers require separate review. A valid-request failure may happen outside application execution. The documented exclusions cannot be dismissed merely because ordinary application errors are bounded. |
| [Custom Errors parameters](https://developers.cloudflare.com/rules/custom-errors/reference/parameters/): inline content maximum 10 KB; assets maximum 1.5 MB; replacement status 400–999; optional tokens are substituted before delivery. | The 10 KB parameter limit is useful for a fixed, token-free configured response within its supported scope. It is not a published cap for all provider responses or all expanded output. Asset size is not an appropriate substitute for the candidate budget. A general body truncation/rejection control is not described here. |
| [Error Pages troubleshooting](https://developers.cloudflare.com/rules/custom-errors/troubleshooting/#1xxx-errors): Error Pages cannot customize 1001,1003,1018 or1023. | This is a concrete customization coverage exception. It does not establish that each error can occur on an otherwise valid FGA request; valid-path applicability requires its own evidence. It does prevent claiming all 1xxx errors are normalized from a broad product description. |
| [Redirect execution order](https://developers.cloudflare.com/rules/url-forwarding/#execution-order): matching redirect actions terminate evaluation immediately; Single Redirects precede Bulk Redirects. [Redirect options](https://developers.cloudflare.com/fundamentals/reference/redirects/) also include Pages, Workers and Page Rules. | Application refusal of redirects cannot be assumed to override an earlier terminating rule. Qualification needs every applicable redirect producer and its effective settings, not only the Worker source. |
| [Worker Request API](https://developers.cloudflare.com/workers/runtime-apis/request/): follow-mode fetch forwards headers, including Authorization, to another hostname; manual mode exposes the 3xx to Worker code. | Explicit manual mode is supported for Worker outbound policy. This is not documentation of Lightroom's native GET redirect policy. A post-return status or URL check cannot undo a redirect or header forwarding that already happened. |
| [Cloudflare Trace limitations](https://developers.cloudflare.com/rules/trace-request/limitations/): operational automatic bypasses are absent; products omitted include IP Access rules, Load Balancing and legacy firewall/rate-limit/WAF rules. | A trace result alone is not a complete effective-edge inventory. Empty visible rule sets or a finite successful trace do not establish universal failure behavior. No Trace request was made here. |

## Conditions for a later effective-configuration evidence packet

These are research requirements for a future authorized packet, not instructions
to execute provider calls in this offline batch:

1. Bind the fixed origin, custom-domain/route attachment, version-weight map,
   exact executable artifacts, compatibility settings and bindings to the same
   reviewed candidate. Include applicable account/zone rule entrypoints,
   inherited defaults, security/challenge/error configuration, redirects,
   transforms, caching/compression and origin fallback. Identify which controls
   execute before, around or after the Worker.
2. For each success, application error, provider error, challenge and redirect
   class, identify its actual responder, supported enforcement scope and exact
   decoded body budget before native materialization. Record unsupported or
   unknown coverage explicitly. Fixed application payload sizes and response
   headers alone do not provide a native allocation bound.
3. Separate a documented enforcement guarantee from a configuration observation
   and a finite response observation. Where customization is proposed, prove
   eligibility, precedence, token expansion, fallback behavior and header policy;
   do not infer blanket coverage from a 10 KB content parameter.
4. Reconcile all effective settings before and after a finite matrix, refusing
   unknown reads or drift. Record capture-time facts as such; a double read is
   not an atomic configuration lock and cannot prevent later changes.
5. Keep native redirect/credential behavior, native allocations, backend
   disconnect/cancellation and late-publication fencing as separate claims.
   Receivers and disposable synthetic markers can characterize exact redirect
   cases only. Authorization checks performed after GET returns cannot supply
   protection before the SDK follows.

Even a perfectly reconciled configuration inventory cannot manufacture a
provider response guarantee absent a supported enforcement mechanism. If that
mechanism cannot be established, the method owner must present a concrete
alternative or explicit scoped amendment for architecture review. Research,
configuration observations and selected small provider responses do not accept
that amendment.

## Evidence provenance and next owner

Executed here: public official-document research and read-only local authority
review; ticket lane confirmed In Progress. No account API, deployment, private
capture, credential read, native SDK call, fixture execution or live
qualification occurred. No hosted response-byte measurement or current
account/plan/configuration claim is made.

The #0147 method synthesis owner integrates this provider result with the
independent native SDK finding and any Proposed design alternative. Required
bounds and credential protection remain unresolved now; they are not postponed
to the later live matrix. Independent review and owner acceptance of any
consequential change remain separate gates.
