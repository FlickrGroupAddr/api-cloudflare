# Private D1 qualifier response evidence

`qualify_private_d1_snapshot.qualify(..., evidence_path=...)` optionally retains
returned outer management/seed/census responses before semantic validation.
The default remains `None`; the CLI and exact packet fields are unchanged.
An independently reviewed trusted caller must bind the exact new private path
and current source pins separately before use. This option supplies neither
provider authority nor a reusable attempt, credential, or cleanup permission.

- The path must be canonical, absolute, separate from all existing packet sinks,
  exclusively new, and beneath an existing protected directory. Existing ACL,
  link and hardlink checks apply before any credential read or dispatch.
- Each private JSON line contains the packet digest, request ordinal, fixed
  phase, returned HTTP status, byte count and base64 response body. No separately
  collected headers, request URLs, request bodies, credentials or exception text
  are added to the evidence fields.
  Literal credential echoes and authentication/cookie markers in raw bodies or
  normalized JSON refuse capture. Benign JSON Unicode escapes remain supported;
  malformed Unicode-escaped text and residual nested escape spellings refuse
  body capture rather than introduce another decoding format. Keep all resulting
  evidence private; never commit or log it.
- Limits are 262,144 raw body bytes per record, 26 records, 7,536,640 raw bytes
  in aggregate and 11 MiB of encoded file bytes. Every record is flushed and
  fsynced. Capture refusal stops the run without a further provider request.
- Source and deadline fences remain before capture and after persistence.
  Reader SQL continues through the existing same-process isolated permit and
  transport. This option does not capture the reader's returned bodies; reader
  failures retain their closed error categories and existing private journal.

Capture precedes status, metadata, JSON shape and terminal SQL validation. A returned
failure can therefore be diagnosed privately without treating it as a terminal
success. Lost responses have no fabricated body. Oversized, unsafe or malformed
response objects may be refused without a response record. Existing unknown
retention, typed equality, finite request budgets and no-replay stops remain.
No retries, discovery, resumed cleanup, or qualification claims are added.

The qualifier receives only its execution token; no bootstrap parent token is
passed to its transport. Echo checks protect that known execution token and
authentication/cookie markers; they cannot identify unrelated unknown secrets.

Fresh source preparation pins the 14 qualifier inputs plus the preparer (15
files). Historical stages remain immutable and cannot verify against changed
source; prepare a fresh reviewed stage instead of updating an old packet.
