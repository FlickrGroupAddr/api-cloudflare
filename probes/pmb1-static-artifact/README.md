# Static prospective Workers artifact

Source/synthetic packaging under accepted PMB-1, ADR0065, ADR0066 and applied
#0242. This new package exports an actual Worker default fetch/scheduled handler,
PartitionWorker, NativeCaptureOwner and NativeCaptureControl. Constructors bind
the reviewed native D1 journal/domain and object disposition mechanisms. The
ordinary exact authenticated current-installation GET remains the unchanged
registry/authentication/LOOKUP_SQL path while application state is closed.

The explicit source contract selects only
`pmb1-private-application-no-real-v1`,
`pmb1-private-object-kv-interface-v1` and
`fixed_update_with_exact_count_positional_v1`. Historical/default artifacts and
named operation forms are unchanged. The external Python D1 operator adapter is
source-pinned in the manifest; Python operator code is not a Worker module.

`build.py --prepare` freezes the source contract. `build.py --output NEW_DIRECTORY --node PINNED_NODE`
requires the existing Node24.22.0, native TypeScript7.0.2 and locked Wrangler4.116.0.
It creates a new copied source stage and empty profile/config/cache directories,
passes an allowlisted environment, disables metrics/error reporting, and uses
Wrangler's ordinary `deploy --dry-run` with `nodejs_compat`. The build-only
`isolate.cjs` rejects network/DNS connections and cached auth/dotenv reads. It is
not a runtime compatibility shim and is not imported into the Worker. No install,
login, account discovery, registration, route/resource creation or deployment runs.

The esbuild metafile binds every actual package/runtime input and emitted module.
The artifact manifest also pins the source superset, locked toolchain, binding,
store/schema/guard manifests and configuration. Source bytes are checked again
after emission. The retained directory copies those exact emitted bytes and
configuration. Nonforced restoration consumes the pinned retained copy and never
rebuilds it. Actual immutable version/resource identity remains null; this is a
prospective provider-compatible artifact, not an actual retained deployment.

Default configuration is inert and refuses. Explicit configuration can bind
source/synthetic resources; it cannot authenticate them. ReviewedCoverage has no
JSON/environment loader: independently authenticated population, writer/version,
retirement and custody facts remain absent. Concrete disposition adapters retain
their missing-capability refusals. There is no HTTP maintenance/read RPC, new
coverage factory, fake qualification result, automatic initialization, close,
reopen, retry or rollback dispatch. The actual native object census/source packet
cannot be conjured from environment strings, and is deliberately not fabricated.

`artifact.test.mjs` independently imports the emitted bytes into the existing
Miniflare/workerd runtime with in-memory synthetic bindings and an outbound
refusal service. It checks real authenticated closed-state success, hostile
authentication/target/methods, journal stop/restart, unknown outcomes and inert
configuration; every runtime is disposed. Emulator compatibility-date lag is
recorded in the private receipt and is not hosted qualification. Native fit,
complete population, actual identity/custody, counted #0187/#0201 footprint,
immutable deployment retention and managed qualification remain later gates.

The existing emulator executes exact emitted bytes with an explicit local-only
2026-08-06 date override; the retained 2026-10-16 configuration is unchanged.
`verify.py` records this distinction and creates an empty host environment with
loopback-only IPC, no cached account state and an outbound-refusal Worker service.

The static object-disposition wrapper binds the declared native owner/control
namespaces but has no independently supplied NativeSourceInput/ReviewedCoverage.
Its gate therefore refuses before acquisition. Parent integration must assemble
those exact trusted factual inputs after their own authorized authentication;
this package does not provide or disguise a JSON truth loader. That is a concrete
remaining integration/factual gate, not another bundler or reader implementation.
