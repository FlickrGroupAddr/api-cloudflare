# String-preserving preparation command boundary

Collector preparation previously refused before creating its final packet
because PowerShell's default JSON decoder converted ISO UTC strings to date
objects. Casting those objects back to strings produced culture-specific text,
which failed the helper's exact UTC parser. This reproduces the command-layer
failure mechanism; the original suppressed exception was not recovered.

Use the reviewed external preparation controller's Python JSON decoder and
direct list argument boundary. Every metadata value must remain a string; reject
unknown, missing, duplicate, empty, nonstring or NUL fields. The controller is
inert by default, exposes only an explicit preparation opt-in, pins the original
helper closure and producer binding, and invokes fixed Python/helper paths with
`subprocess.run(..., shell=False)`. It does not provide execution authority.

The private successor runbook supplies exact preparation invocation vectors and
retains actual packet review before any separate execution. Do not deserialize
command metadata through default `ConvertFrom-Json` or rebuild a shell string.
Keep each option encoded as one `--name=value` list element so option-looking
values reach the parser unchanged. The helper retains full source, role,
custody, original evidence and current-window validation.

For retirement, complete readiness first and record truthful terminal facts just
in time. Preserve the original attestation timestamp. Both that timestamp and
the actual authority timestamp must fall inside the same interval of at most
600 seconds; the actual dispatch clock must also remain before its exclusive
end. Preparation does not extend the interval. Stop if the window cannot fit;
never retimestamp, replay a spent packet or manufacture a later attestation.

Offline regression validation covers both real helper parsers with actions
intercepted before path processing, exact string fidelity, closed input schemas,
helper/source bindings, inert defaults, no retry, and pinned original timing
boundaries. No credentials, provider requests or live preparation are involved.
These checks supply no positive qualification or authorization for a fresh run.

Private evidence bundle: `0161-command-integration-20261022.zip`, SHA2-256
`a433d1a9bce2fc03db48bec522f999004654418817c16a15bb5ecf52dd3b1d65`.
The reviewed source remains in private project operations evidence. The private
implementation-board ticket 0161 handoff records its actual custody and relative
artifact location. A board attachment requires separate owner authorization;
do not assume that an attachment exists. If one is available, verify its exact
filename and digest; otherwise retrieve the retained local artifact from that
private handoff location. Do not publish the private payload or arguments.

The ZIP contains the successor `COMMAND-PROCEDURE.txt`, controller, tests,
validation summary and `BUNDLE-SHA256.json`. Verify each recorded hash before
using exact commands. Original helpers and producer source are pinned and
retained separately; the ZIP is not a self-contained runtime. The public note
is excluded from the ZIP to avoid a circular digest. Historical attempt evidence
remains private and immutable; expiry passage alone confirms neither provider
expiry nor revocation.

## October 23 source-only recovery proposal

Proposed recovery amendment — pending owner acceptance and implementation

The existing preparation controller preserves the original terminal-freshness
and fixed-namespace rules. It cannot recover a historical stopped attempt by
changing dates or reusing its preserved retirement packet.

The independently reviewed source proposal would retain the original terminal
attestation and timestamp as historical closure evidence, require an additional
genuine current recovery witness and independent judgment within one new finite
dispatch window, and use one separate exclusive recovery-only metadata namespace.
That namespace would bind the unchanged original issuance and child identity,
source/evidence pins, permanent stop and original single-use retirement latch.

This is a proposed material contract amendment. Advance plan authority does not
accept it. Acceptance would permit subsequent engineering and independent source
review; it would supply no actual packet, current facts, credential validity,
provider status or readiness. The existing runner does not implement the proposed
semantics. Original evidence and clocks remain immutable; unknown outcomes forbid
retry. A fresh POST attempt retains its separate readiness and qualification gates.

Fresh independent High review passed six package hashes, seventeen source pins
and eleven combined offline checks. The concrete proposal and review are retained
privately with implementation-board card 0161. Provider expiry and revocation
remain unconfirmed. No account, credential, native or execution action occurred.

## Subsequent owner acceptance — October 23

The proposal above is retained as historical pre-decision evidence. Terry later
accepted the [historical-child recovery source contract](historical-child-recovery-contract-2026-10-23.md)
in decision `call_85ff42c39e6343dcbd60e8d1d7ee6c32`. Its two changes and required
engineering/factual gates now govern a separate recovery implementation. This
acceptance supplies no credential access, retirement, POST run or current facts.
The original controller and historical evidence remain unchanged.
