"""Run state machine: enforces step order, the human gate and the revision cap."""

from typing import Literal

from mca.config import MAX_REVISIONS
from mca.contracts import Contract

AGENT_STEPS = (1, 2, 3, 4)
REVIEW_STEP = 5
EXPORT_STEP = 6
STEPS_KEPT_ON_REVISION = (1, 2)


class StateError(RuntimeError):
    """A step was requested out of order or beyond the revision cap."""


class RunState(Contract):
    run_id: str
    completed: tuple[int, ...] = ()
    revisions: int = 0
    status: Literal["running", "approved", "exported"] = "running"


def next_step(state: RunState) -> int | None:
    if state.status == "exported":
        return None
    if state.status == "approved":
        return EXPORT_STEP
    pending = [step for step in AGENT_STEPS if step not in state.completed]
    return pending[0] if pending else REVIEW_STEP


def complete(state: RunState, step: int) -> RunState:
    expected = next_step(state)
    if step == REVIEW_STEP:
        raise StateError("step 5 is the human review; record it with `mca feedback`")
    if step != expected:
        raise StateError(f"cannot complete step {step}; next step is {expected}")
    if step == EXPORT_STEP:
        return state.model_copy(update={"completed": (*state.completed, step), "status": "exported"})
    return state.model_copy(update={"completed": (*state.completed, step)})


def record_feedback(state: RunState, decision: Literal["approved", "changes"]) -> RunState:
    if next_step(state) != REVIEW_STEP:
        raise StateError(f"review not due; next step is {next_step(state)}")
    if decision == "approved":
        return state.model_copy(update={"completed": (*state.completed, REVIEW_STEP), "status": "approved"})
    if state.revisions >= MAX_REVISIONS:
        raise StateError(f"revision cap of {MAX_REVISIONS} reached; approve or stop the run")
    return state.model_copy(update={"completed": STEPS_KEPT_ON_REVISION, "revisions": state.revisions + 1})
