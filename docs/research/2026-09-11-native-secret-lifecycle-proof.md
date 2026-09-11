# Paused native secret lifecycle evidence

Date: 2026-09-11

Status: Bounded synthetic proof complete; all 29 hosted cases passed and all
fixture cleanup was confirmed. Production FGA UI/API integration remains
outstanding. This is evidence for the accepted private tradeoff in
[ADR 0052](https://github.com/FlickrGroupAddr/architecture-design/blob/abcb2d192063783400634aa50c736c1d0a6a523a/docs/decisions/0052-evaluate-paused-native-credential-replacement.md),
not an independent production-release approval.

## Finding

Cloudflare D1 and Secrets Store support the tested paused replacement flow
without provider-version lookup or AWS. D1 retained lifecycle authority while
the native binding returned the current token-pair bundle. Replacement,
retirement, and subsequent relink reused the same secret entry/binding without
credential-triggered Worker deployment. A separate deliberate deployment
replacement tested persistence of a pending pause.

The final run `rp-a06a9c9c31c552258b6d016d` passed 29 cases at hosted compatibility
date `2026-09-11`. Source hashes matched the checkout when evidence was exported;
the bundle has its own SHA2-256 digest. Responses checked build identity and
`Cache-Control: no-store`. The deployment after the intentional restart was
unchanged through the remaining lifecycle cases. The final run needed no
transport retry or incidental acknowledgement reconciliation.
[Sanitized evidence, including preceding attempts](../evidence/native-secret-lifecycle-2026-09-11.json).

| Behavior | Actual evidence |
| --- | --- |
| Authentication | Wrong Worker bearer returned 401; a correctly shaped invalid management token returned 401/code 10000 without a result. |
| Read/management boundary | Native get resolved the synthetic pair; no management credential was deployed. A scoped unsupported binding write invocation was rejected. |
| Competing replacements | Two D1-journaled attempts, one revision increment and one transition event; responses were 200 and 409. |
| Pause and restart | Ordinary resolution stopped; a replacement deployment observed the same pending operation and revision in hosted D1. Local workerd disposal/reopen also retained the pause. |
| Lost store response | Acknowledgement of a real PATCH was deliberately discarded. The expected native generation became observable on the third check; the database stayed paused. |
| Failed activation | An intentionally failing CHECK in the same D1 batch rolled back the link update and trigger-created audit event. The expected injected failure code was verified. |
| Lost activation response | The committed active generation/revision was recovered from D1; replay at the old revision was rejected. |
| Late/malformed values | Deliberately injected older and malformed native values produced closed outcomes; restoring the matching value repaired resolution. |
| Disconnect serialization | New resolution stopped before retirement; relink was refused while cleanup was pending. Stale cleanup could not acquire authority over a successor. |
| Correlated retirement | D1 retained the retiring generation. Three consecutive native observations matched its noncredential marker. An old marker could not complete a newer disconnect. |
| Relink after disconnect | A third generation became usable through the same native entry and binding, without another deployment. |
| Retained audit | All eight successful state transitions had the exact ordered revision/event sequence; activation never resumed the write gate. |
| Cleanup | Worker, D1 database, secret object, and run-owned temporary store were deleted and absence confirmed. |

These observations support continuing with the native candidate. No unmet
store-lifecycle requirement demonstrated here warrants moving to AWS under
Terry's high need threshold. Existing AWS evidence remains a fallback.

## Retirement semantics

The fixed slot is retained while the private deployment operates. Disconnect
replaces its credential payload with a small noncredential marker carrying the
exact generation being retired. A generic empty marker would be insufficient:
a delayed marker from an earlier disconnect must not count as retirement of a
newer pair. The native Worker checks that identity itself before completing
the D1 transition; unavailable or malformed values do not prove retirement.

Physical deletion of the secret entry is a separate teardown step after its
Worker is removed. The provider documentation advises removing deployed usage
before deleting a secret. Keeping a noncredential slot during normal
disconnect allows later relink to reuse its binding. This proves the observed
payload replacement and subsequent resource removal, not zeroization of every
provider replica/backup or a globally atomic propagation boundary.
[Cloudflare update/deletion interfaces](https://developers.cloudflare.com/secrets-store/manage-secrets/how-to/),
[native binding](https://developers.cloudflare.com/secrets-store/integrations/workers/).

## Earlier attempts and test corrections

All preceding hosted attempts are retained in the evidence and had confirmed
cleanup. They are not rewritten as passing runs. Early assertions assumed an
invalid token would always return 401/403, that a callable-looking method
implied authority, or that HTTP acknowledgements/deployment propagation would
be immediate and uniform. Early diagnostics did not retain enough detail to
classify every failure. The final harness tests actual method refusal,
uses D1's attempt/audit records, retains bounded edge diagnostics, and checks
known identical-build instances during the intentional deployment overlap.

Several earlier attempts received non-JSON 404/500 responses or an unexpected
401 during otherwise authenticated requests. The final setup includes the
bearer in the first deployed version, rather than exposing an intermediate
version without it, and requires repeated GET/POST/D1 readiness. That avoids
the identified setup window; it does not retrospectively prove the cause of
every earlier response. The final case sequence had no such failures.

The local tests caught Node stripping's unsupported parameter-property syntax,
a Windows workerd external-module-path issue, and incorrect splitting of SQL
trigger bodies. The corrected local harness loads the compiled bundle in
memory and provisions complete statements. These are harness corrections,
not native service limitations or reasons to add AWS.

## Validation and limits

Validation passed: reproducible `npm ci`, the pinned native TypeScript 7.0.2
compiler before provider bundling, 8 native JavaScript/runtime tests, all 55
Python tests (11 new native-controller tests), 18 AWS-probe regressions, 3 route
regressions, Ruff lint/format, Pyright, documentation links, privacy inspection,
and whitespace checks. npm still reported 7.0.2 as the latest stable compiler
on 2026-09-11. No dependency was added or upgraded.

The existing development toolchain has four high-severity package findings
(Miniflare, Wrangler, Undici, and Sharp); the wrapper findings inherit the
underlying packages. npm's suggested direct Miniflare replacement is an alpha,
so no automatic force/preview upgrade was introduced. The local tests accept
no external traffic or images and intercept outbound requests; the native
hosted bundle imports no third-party package. These scope limits do not make
the toolchain vulnerability-free. Reconcile the stable toolchain before broader
development exposure. The previous
[Undici tradeoff](2026-09-07-worker-routing-proof.md) remains context, and the
[Sharp advisory](https://github.com/advisories/GHSA-rgj7-g3m4-5g8c) is the additional
finding observed by this install.

The hosted fault injections are deliberate synthetic stimuli: discarded
acknowledgements, a failing D1 statement, or operator writes that bypass the
ordinary lifecycle gate. They do not prove an independently occurring outage
or prevent a privileged operator from physically overwriting data. Their
required result is closed consumption, durable state, and truthful recovery.
No Flickr request, real Flickr grant, AWS API call, public FGA API route, or
production schema was exercised.

The read/update permission evidence uses the real native binding and a local
Wrangler operator credential. It does not establish a narrowly scoped
unattended production writer identity. The fixture schema and controller are
not production authentication, UI/wire mapping, migration/restore acceptance,
or the complete Flickr dispatch path. Production integration must preserve
operation ownership across its real topology, validate the owner and grant,
and reuse the existing final dispatch/recovery safeguards. Those implementation
steps remain separate from this completed bounded native capability proof.

[Reproduction and cleanup procedure](../../probes/native-secrets/README.md).
