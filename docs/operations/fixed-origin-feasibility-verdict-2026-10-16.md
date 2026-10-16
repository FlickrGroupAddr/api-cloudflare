# Fixed-origin feasibility verdict

Date: 2026-10-16. Ticket #0037.
Status: Current method unqualified; return to design now. Research only.

The [native-method research](../research/fixed-origin-native-measurement-2026-10-16.md)
selects independent Windows process counters for finite aggregate memory
characterization. The documented SDK15.3 GET interface returns a complete body
string, offers a per-phase timeout and exposes no GET abort handle or receive
cap. Process counters cannot attribute every transient allocation to one
response. SDK wall-time observations do not establish a monotonic native timer
or hard total deadline. This is a usable characterization method, not proof of
the candidate's required supported effective-path allocation and credential
protection. The absent GET abort handle is an SDK limit, not an additional
acceptance requirement: the candidate requires native cancellation/publication/
cleanup evidence and separately backend abort behavior.

The [edge-method research](../research/fixed-origin-edge-measurement-2026-10-16.md)
finds that the captured runtime does not explicitly enable incoming request
cancellation and that no complete supported bound for provider-generated errors
on valid paths is established. A backend timer or AbortController is distinct
from native cancellation, observed disconnect and remotely stopped work.
Application image limits do not constrain responses generated before or instead
of Worker execution. Finite successful samples cannot close that missing bound.
The accepted early malformed-target/duplicate-Authorization HTTP400 presentation
exceptions do not waive allocation bounds or cover ordinary provider failures.

The [#0036 captured baseline](existing-photo-inventory-2026-10-16.md) is also not
the checkout thumbnail candidate: static inspection of the exact active module
finds no candidate discovery/thumbnail route indicators. This bounded screen
supports an artifact gap, not semantic production-code qualification. Candidate
source limits must not be reported as deployed endpoint behavior.

Return the candidate to architecture design now with these concrete unmet
obligations. The next conventional decision is an offline review of an exact
candidate artifact and runtime configuration against documented supported
receive, provider-response and credential-redirect mechanisms, with separate
native cancellation/publication/cleanup and backend abort/disconnect evidence.
Determine whether the candidate can meet its existing gates before selecting a
live execution packet. If those mechanisms remain unavailable, resolve the
design through the architecture authority process; this note implements no
replacement and accepts no requirement change or waiver.

Dependent live qualification and promotion remain blocked. Future finite host
or edge characterization can supply bounded observations; it cannot by itself
convert unknown provider bounds or process-memory samples into qualified
effective-path allocation or credential-redirect protection. The missing
supported method and candidate-artifact gap ground this verdict; the absence
of a native GET abort handle does not independently fail a candidate gate. No deployment, live request, native run,
credential change or owner contract acceptance occurred in #0037 research.


Later on 2026-10-16, Terry approved #0038's separately pinned b599ca8 candidate
for offline synthetic qualification while preserving the exact captured ordinary
dispatcher/rollback baseline. That settles the source premise for that offline
composition only. It neither changes the currently deployed source nor passes
this effective-edge/native qualification verdict or authorizes live promotion.
