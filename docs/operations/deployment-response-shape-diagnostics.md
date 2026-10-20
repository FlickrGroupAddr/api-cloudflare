# Deployment rejection shape diagnostics

The FGA deployment operator may add `deploymentResponseShape` to a private
unknown-operation journal receipt when strict deployment response validation
rejects the parsed POST result. The existing `deploymentDiagnostic` stage,
field and status object stays unchanged. Existing receipts without the optional
supplement remain readable and are never rewritten.

The supplement has exactly seven fixed keys: `result`, `id`, `created_on`,
`strategy`, `versions`, `metadata`, and `metadata.created_on`. Its values are
only `null`, `boolean`, `number`, `string`, `array`, `object`, `other`, `missing`,
or `unavailable`. `missing` means a known field is absent from an object;
`unavailable` means its parent is not an object. No array contents or arbitrary
object keys are inspected. Only the known `metadata.created_on` nesting is
classified. Values, annotations, identifiers, timestamps, headers, error prose,
URLs, bodies and credentials are never copied into the supplement.

The operator resets supplement state before each deployment operation and
validates the exact built-in string keys and type labels, exact dictionary type,
fixed key set and parent/child consistency
before persistence. An invalid supplement is omitted without preventing unknown
settlement. Successful responses and failures outside response validation do
not produce shape evidence. Local `diagnosticObservedAt` remains a local
observation time, never provider creation time.

The strict UUID, direct timezone-aware `created_on`, percentage strategy and
exact version allocation checks remain required. A nested timestamp does not
satisfy the direct timestamp requirement. This observability change makes no
provider request and changes no replay, fencing, cleanup, request budget or
qualification rule. It cannot recover the lost response from a spent attempt
or authorize another live attempt.
