# Bounded Workers clock investigation

Run `uv run --frozen python scripts/clock_probe.py local` for local workerd or
`uv run --frozen python scripts/clock_probe.py hosted` for isolated Cloudflare
resources. The command performs diagnostic cases on both a Worker and a Durable
Object, saves private evidence under `.coordination-runs/`, and cleans up.
A successful exit means the investigation completed with cleanup; it does **not**
mean the clock satisfies the accepted production requirement. The report keeps
that distinction explicit.

The controlled HTTPS peer and D1 marker are synthetic. There is no Flickr token,
account, group or public application route in this fixture. Native performance,
wall and Node compatibility timer observations are compared with independently
observed peer POST receipt and controller request duration. CPU loops are finite
and capped, and the deployed Worker has a 5,000 ms CPU limit and thirty-minute
bearer-protected lifetime. The public-fetch routing flag is a fixture transport
requirement, not a timing workaround.

Cases cover CPU intervals before/after the marker and after an extra I/O sample,
delayed marker commits, an I/O-yield suspension, negative-clock injection and
independent wall-time injection. They cannot force real provider process
suspension or clock rollback. Peer receipt includes network delay. The experiment
is not a claim about typical incident frequency or exact remote handoff time.

The native TypeScript gate precedes bundling. Hosted deployment uses the frozen,
minified bundle with `no_bundle`, and its SHA2-256 digest is recorded. For an
interrupted hosted run, use the existing scoped cleanup command:

`uv run --frozen python scripts/coordination_probe.py cleanup --run <private-run-directory>`

Cleanup uses ordinary Worker deletion and declarative retirement of the exact
probe Durable Object namespace before deleting the exact disposable database.
No force deletion or production resource cleanup is part of this command.

See [the investigation and owner handoff](../../docs/research/2026-09-11-workers-preflight-clock.md).
