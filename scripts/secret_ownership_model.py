"""Offline counterexamples for fixed-name Actions secret ownership.

Only name metadata, unconditional create-or-update, and unconditional deletion
by name are modeled. Each call is atomic, a favorable assumption for the
operator. No values, timestamps, provider clients, credentials, or network exist.
``lineage`` is a test oracle unavailable through the provider metadata API;
it must never be mistaken for an acknowledged immutable secret identity.

The local lock excludes operators sharing that journal only. The alternative
models *only* removal of Actions secret mutations, not capability handoff,
Worker secrets, restoration, or any complete execution/qualification protocol.
See docs/research/synthetic-secret-ownership-2026-10-17.md for evidence
and proposal status. This model is not hosted/provider proof.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Event:
    operation: str
    actor: str
    previous_lineage: str | None


@dataclass
class NameOnlyStore:
    """Synthetic single-name upsert/delete surface; lineage is oracle-only."""

    name: str = "FGA_FIXED_ORIGIN_CAPABILITY"
    lineage: str | None = None
    events: list[Event] = field(default_factory=list)

    def metadata(self) -> str | None:
        return self.name if self.lineage is not None else None

    def put(self, actor: str) -> None:
        self.events.append(Event("put", actor, self.lineage))
        self.lineage = actor

    def delete(self, actor: str) -> None:
        self.events.append(Event("delete", actor, self.lineage))
        self.lineage = None


@dataclass
class LocalAttempt:
    """Overgenerous metadata recheck still cannot make delete conditional."""

    store: NameOnlyStore
    locked: bool = False
    absent_observed: bool = False
    acknowledged_name: str | None = None
    cleanup_observed: bool = False
    refused: bool = False

    def acquire(self) -> bool:
        if self.locked:
            return False
        self.locked = True
        return True

    def step(self, operation: str) -> None:
        if not self.locked:
            raise ValueError("local_lock_required")
        if operation not in LOCAL_STEPS:
            raise ValueError("unknown_model_step")
        if self.refused:
            return
        if operation == "absence":
            self.absent_observed = self.store.metadata() is None
            self.refused = not self.absent_observed
        elif operation == "put":
            if not self.absent_observed:
                raise ValueError("absence_required")
            self.store.put("local")
            self.acknowledged_name = self.store.name
        elif operation == "metadata_recheck":
            self.cleanup_observed = self.store.metadata() == self.acknowledged_name
        elif operation == "delete":
            if self.acknowledged_name is None or not self.cleanup_observed:
                self.refused = True
                return
            self.store.delete("local")


LOCAL_STEPS = ("absence", "put", "metadata_recheck", "delete")


def interleaving(foreign_gap: int, *, name: str = "FGA_FIXED_ORIGIN_CAPABILITY") -> NameOnlyStore:
    """Insert one independent writer at every possible gap in local order.

    Gap 0 precedes absence; gap 4 follows deletion. Foreign writes do not use
    the local journal lock, as a repository administrator/API writer need not.
    """
    if type(foreign_gap) is not int or not 0 <= foreign_gap <= len(LOCAL_STEPS):
        raise ValueError("invalid_model_gap")
    store = NameOnlyStore(name=name)
    attempt = LocalAttempt(store)
    assert attempt.acquire()
    for index, operation in enumerate(LOCAL_STEPS):
        if foreign_gap == index:
            store.put("foreign")
        attempt.step(operation)
    if foreign_gap == len(LOCAL_STEPS):
        store.put("foreign")
    return store


def violations(store: NameOnlyStore) -> tuple[str, ...]:
    """Audit ghost provenance, never infer ownership from a name receipt."""
    return tuple(
        "foreign_overwritten" if event.operation == "put" else "foreign_deleted"
        for event in store.events
        if event.actor == "local" and event.previous_lineage == "foreign"
    )


def mutation_free_boundary(foreign_gap: int, *, initially_present: bool) -> NameOnlyStore:
    """Proposed zero-Actions-secret-write boundary, with arbitrary foreign timing.

    Four orchestration checkpoints are no-ops on this surface. This proves only
    absence of local damage here. It provides no proof for the private handoff
    replacing Actions secrets, nor exclusion of foreign writers elsewhere.
    """
    if type(foreign_gap) is not int or not 0 <= foreign_gap <= len(LOCAL_STEPS):
        raise ValueError("invalid_model_gap")
    store = NameOnlyStore(lineage="foreign-initial" if initially_present else None)
    for index in range(len(LOCAL_STEPS) + 1):
        if foreign_gap == index:
            store.put("foreign")
    return store


def main() -> None:
    outcomes = {gap: violations(interleaving(gap)) for gap in range(len(LOCAL_STEPS) + 1)}
    print("OFFLINE MODEL ONLY; no provider calls or ownership qualification")
    for gap, failures in outcomes.items():
        print(f"foreign PUT gap {gap}: {', '.join(failures) or 'no local damage'}")
    print("Proposed zero Actions secret writes: no local damage on this modeled surface")


if __name__ == "__main__":
    main()
