# Supplied retained-capture reconciliation

`scripts.retained_capture_reconciliation.reconcile` checks historical correspondence
using supplied bytes only. It takes the integrity-index bytes, the original
collector receipt bytes, a tuple of unique `(private_basename, bytes)` entries,
and a required independently retained lowercase SHA2-256 index pin. It does not
read a destination, discover files, collect provider data, read credentials,
execute modules, or dereference paths in the input.

The result is a fixed allowlist. `historicalCaptureCorrespondence: matched` means
the entire supplied corpus matches the index and the existing collector's
metadata/module graph contract. It establishes neither capture authenticity
without a trusted external pin nor present provider state. Write-only secret
state remains `unknown`; current deployment, prospective attribution,
restoration, edge qualification and execution authorization remain false.
It cannot satisfy a later preservation gate with an old capture.

The input format comes from existing source, rather than a generic JSON scanner:

- `scripts/fixed_origin_restore.py:validate_capture` owns the integrity-index
  `files` rows (`name`, `bytes`, external field spelling `sha256`) and retained
  basenames. Top-level index metadata is opaque; no unobserved writer schema
  is invented. Duplicate names, extra rows and omitted files are rejected.
- `scripts/existing_photo_inventory.py:collect` owns the restoration input
  record, endpoint selectors, receipt observations, immutable active version
  weights, module metadata and ruleset traversal. The reconciler reuses that
  validator through an in-memory reader and writer with a constant clock and
  the supplied receipt's historical timestamp. It verifies exact generated
  file closure, payload bytes, restoration record and receipt correspondence.
- The reconciler additionally rejects duplicate JSON object members, duplicate
  active version IDs, active metadata ID mismatch, noncanonical base64 and
  numeric/boolean substitutions in generated records. Ruleset locators only
  select already supplied payloads through the collector's exact selectors.

The existing collector still defaults to its real monotonic clock and current
capture timestamp. Its CLI has no replay option. Injected clock and timestamp
arguments exist only to reuse the same validator in deterministic offline code.

Bounds are explicit: at most 96 endpoint responses plus one restoration record,
16 MiB per supplied private file, 80 MiB private corpus, 1 MiB each for the
integrity index and receipt. Replayed endpoint response bytes retain the existing
64 MiB aggregate, 96-request, eight-version, 128-modules-per-version,
eight-pages-per-scope and 32-ruleset limits. The collector's 180-second live
budget is not claimed as elapsed-time evidence for this offline operation.
Malformed or incomplete input produces the same unresolved allowlisted result;
raw errors, private identities, source and settings never enter output or logs.

The independently supplied pin must identify the intended retained index revision.
Do not substitute the legacy restoration helper's embedded pin for a different
published local-retention index digest, or silently treat different pins as
equivalent. This checker makes no claim to resolve that historical provenance gap.

`tests/test_retained_capture_reconciliation.py` uses invented two-version,
two-module captures and a transitive ruleset graph. It checks full correspondence,
omissions, duplicate files/rows/JSON/version/module identities, digest and selector
drift, incorrect weights/version IDs/base64, cyclic settings graphs, malformed
inputs, private-output suppression and refusal to upgrade historical evidence.
