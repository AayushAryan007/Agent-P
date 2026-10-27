"""Allowed state transitions (DATABASE_DESIGN.md §4). Every status change goes through `check_*`."""

RUN_TRANSITIONS: dict[str, frozenset[str]] = {
    "queued": frozenset({"running", "cancelled", "failed"}),
    "running": frozenset({"waiting_approval", "completed", "failed", "cancelled"}),
    "waiting_approval": frozenset({"running", "failed", "cancelled"}),
    "completed": frozenset(),
    "failed": frozenset(),
    "cancelled": frozenset(),
}

STEP_TRANSITIONS: dict[str, frozenset[str]] = {
    "pending": frozenset({"running", "skipped", "cancelled"}),
    "running": frozenset({"waiting_approval", "completed", "failed", "cancelled", "skipped"}),
    "waiting_approval": frozenset({"completed", "failed", "cancelled"}),
    "completed": frozenset(),
    "failed": frozenset(),
    "cancelled": frozenset(),
    "skipped": frozenset(),
}


class InvalidTransition(RuntimeError):
    pass


def check_run(current: str, target: str) -> None:
    if target not in RUN_TRANSITIONS.get(current, frozenset()):
        raise InvalidTransition(f"run: {current} → {target} is not allowed")


def check_step(current: str, target: str) -> None:
    if target not in STEP_TRANSITIONS.get(current, frozenset()):
        raise InvalidTransition(f"step: {current} → {target} is not allowed")
