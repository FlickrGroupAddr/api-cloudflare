# Independent group-discovery JSON review

Date: 2026-10-15. Scope: staged `GroupDiscoveryClient.lua` strict grammar
changes and `tests/test_lightroom_groups_client.py`; no production host or
network operation.

No actionable correctness defect was found in the reviewed group-client
change. The 14 staged focused tests pass in actual Lua5.1. An independent
16-case adversarial review also passes: trailing literal/NUL/BOM; incomplete
number/fraction/exponent forms; lone high/low and mismatched surrogate display
names; unknown/short Unicode escapes; escaped-equivalent duplicate keys; and
nesting beyond the parser's depth limit. The temporary review driver is a
review artifact, not part of production test discovery.

The grammar checks the complete bounded response before dkjson decoding;
decoded string keys detect escaped-equivalent duplicates. Required explicit
null and array identity are retained by dkjson rather than inferred from empty
Lua tables. Subsequent closed-shape/domain validation rejects malformed Unicode
display strings. Number grammar rejects extensions and missing digits while
allowing valid JSON exponent notation. The response byte limit and parser
depth bound constrain input; page/row limits constrain aggregate growth.

HTTP and sleep callbacks remain outside ordinary Lua5.1 `pcall`; protection
around decoding and local credential retrieval does not wrap those yielding
operations. The focused coroutine test actually yields through installation
verification, groups HTTP and retry wait, including cancellation while asleep.
UI-owner yielding protection remains a separate host integration obligation.

This is independent source and synthetic-runtime review, not actual host
qualification or acceptance of a changed selector interaction.
