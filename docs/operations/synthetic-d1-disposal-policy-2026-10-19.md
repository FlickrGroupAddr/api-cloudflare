# Accepted synthetic D1 disposal policy

Terry accepted this scoped policy on 2026-10-19 to avoid repeatedly deciding
the same disposal exception for later, separately approved synthetic D1 tests.
It changes no production-data preservation requirement or test authorization.

A later cleanup packet may permit disposal despite unknown SQL effects or
unverified bindings only when all of these conditions hold:

- Retained acknowledgements establish the exact fresh run-owned UUID, expected
  name and approved account. The fixture contains no existing or production data.
- Its caller and owned operations are terminal. Every owned Worker has an exact
  deletion acknowledgement followed by an exact-ID absence observation, or no
  Worker was created.
- No DELETE has previously been attempted for that database. A spent or uncertain
  cleanup cannot be retried or resumed under this policy.
- Current pinned source, finite credentials, protected exact paths and fresh
  independent packet review establish the cleanup scope. The whole action
  window fits within the child's actual provider expiry.
- Cleanup is one exact-ID DELETE, then one exact-ID GET only after a valid
  terminal deletion acknowledgement: at most two requests per database,
  twenty seconds per request, in one ten-minute action window.
- Each packet is limited to five databases and ten total requests. A larger
  target set requires a separate explicit decision.
- No SQL, Worker operation, discovery, account-wide operation or other resource
  kind is included. Any unknown outcome stops the attempt without retry.

Preserve original evidence, unknown outcomes and spent claims. A not-found
observation establishes neither physical erasure nor successful qualification.
Missing or uncertain prerequisites retain the fixture for a separate decision.

This acceptance grants no new test run, credential lifetime or automatic
discovery capability. Each later packet still needs current independent review
and applicable execution authority. It does not revive an expired or spent
packet. The five-fixture proposal accepted in the same conversation expired
before execution and sent no deletion requests; its exact exception and window
remain distinct from this future policy.

No general automatic cleanup implementation is enabled by this document.
