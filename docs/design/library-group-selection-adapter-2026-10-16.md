# Disabled Library selection adapter

Date: 2026-10-16. Ticket #0064. Status: implementation evidence; no production
qualification, registration or native execution approval.

The FGA LrC plug-in's `LibraryGroupSelectionAdapter.lua` resolves the exact
Library selection before composing the existing selection controller, private
store and dual-list dialog. Authority remains architecture ADR0045 as amended
by accepted ADRs0062/0063, and the implementation
[controller](group-selection-controller.md), [store](group-selection-store.md)
and [adapter map](group-workflow-adapter-map-2026-10-16.md). This document does
not amend those contracts.

`resolve(deps)` returns a captured SDK catalog/photo/Album/service and exact
scope, or `nil, "scope_invalid"`. It requires one target photo belonging to the
active catalog, one ordinary non-smart `LrPublishedCollection`, its exact
`LrPublishService` owned by the major-specific FGA toolkit, positive safe-integer
local IDs, object-identical membership and a persistent UUID. Names establish
no authority. Ambiguous selection, foreign services, smart collections,
missing membership, malformed IDs, errors and cancellation fail closed.

`new(deps)` captures that scope. Dependencies are the owning task's `call`
(`LrTasks.pcall`), `activeCatalog`, `_PLUGIN` as `plugin` and optional cooperative
`cancelled` reader. It is compatible with the local task dependencies from
`GroupWorkflowAdapterFactory`; it does not launch that factory or require its
network-capable initialization. The private `GroupSelectionStore` receives a
scope fence that repeats resolution before, inside and after its synchronous
private catalog gate. A catalog, target photo, Album, service, UUID, membership
or cancellation change prevents dependent writes or a successful save result.
The existing five-second gate, late-callback fence and exact readback remain
with the store. No extra persistence implementation is introduced.

The returned session exposes `unpublishedController(groups)` and
`showUnpublished(groups)`. The caller must establish unpublished status in its
trusted binding context before selecting this explicitly unpublished path.
The complete validated discovery aggregate passes through the existing
`GroupSelectionEligibility.assemble` with absent membership/history inputs;
stale, incomplete, duplicate or malformed data disables selection. The adapter
does not determine a hosted binding from a photo name, remote ID or saved
selection. Bound Queue, binding lookup and publish-provider callbacks remain
separate composition work. The session neither queries membership nor consumes
an injected network, render or upload operation.

`unpublishedController` returns the existing actual controller. `showUnpublished`
uses that controller with `GroupSelectionDialog.show`; filename and Album name
are display context only. Missing choice remains missing until an explicit
Save. Empty Save replaces this exact scope with `choice: none`, retaining the
store's revision behavior and all unrelated scopes/photos. Unavailable saved
IDs remain visible and require the existing explicit removal action. The
controller retains its 0–60 limit and creates no unpublished handoff.

`MetadataDefinition.lua` declares only the accepted private, untitled string
field `groupAdditionSelections`. `Info.lua` is unchanged and does not register
this definition, adapter, menu command or publish provider. The adapter retains
`PRODUCTION_QUALIFIED=false`.

## Verification and limits

The qualification target remains Lightroom Classic 15.6 Release,
`202609251514-f839cde9`, and Adobe SDK15.3, `202604090947-8f3672ed`.
Local licensed SDK module references for `LrCatalog`, `LrPhoto`,
`LrPublishedCollection` and `LrPublishService`, plus the metadata sample, were
inspected for the exact methods and field surface. Licensed materials are not
copied into this repository.

`tests/test_library_group_selection_adapter.py` executes the actual Lua5.1
adapter, controller, eligibility assembler and store with a synthetic SDK
fixture. Eleven tests cover empty Save/absence/explicit none, same photo in two
services and two Albums, same-service different Albums, other photo preservation,
unavailable IDs, malformed/duplicate/oversized schema, 64-entry and 60-group
limits, timeout and delayed callbacks, scope changes before/inside/after the
private gate, group-snapshot failures, disabled registration and private metadata.
Unexpected external-operation adapters throw in the fixture.

Validation used the pinned wrapper
`uv tool run --from uv==0.12.5 uv run --frozen`: focused tests (11), existing
group-selection discovery tests (43), Ruff format/check. Adobe SDK15.3's actual
Windows `luac.exe -p` passed for the new adapter, metadata definition and fixture.
These are synthetic boundary and compiler checks. Actual host catalog behavior,
integrated binding/transport invocation, metadata registration and exact native
artifact smoke remain separate gates; no later Lightroom major is qualified.
