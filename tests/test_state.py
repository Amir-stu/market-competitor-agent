import pytest

from mca.config import MAX_REVISIONS
from mca.state import RunState, StateError, complete, next_step, record_feedback


def fresh() -> RunState:
    return RunState(run_id="r1")


def done_through_four() -> RunState:
    state = fresh()
    for step in (1, 2, 3, 4):
        state = complete(state, step)
    return state


def test_next_step_when_fresh_returns_one():
    assert next_step(fresh()) == 1


def test_complete_when_in_order_advances():
    state = complete(complete(fresh(), 1), 2)
    assert state.completed == (1, 2)
    assert next_step(state) == 3


def test_complete_when_out_of_order_raises():
    with pytest.raises(StateError):
        complete(fresh(), 2)


def test_complete_does_not_mutate_input():
    state = fresh()
    complete(state, 1)
    assert state.completed == ()


def test_next_step_when_four_done_returns_review():
    assert next_step(done_through_four()) == 5


def test_complete_when_step_five_raises():
    with pytest.raises(StateError):
        complete(done_through_four(), 5)


def test_feedback_when_approved_moves_to_export():
    state = record_feedback(done_through_four(), "approved")
    assert state.status == "approved"
    assert next_step(state) == 6


def test_feedback_when_changes_resets_to_step_three():
    state = record_feedback(done_through_four(), "changes")
    assert state.completed == (1, 2)
    assert state.revisions == 1
    assert next_step(state) == 3


def test_feedback_when_steps_missing_raises():
    with pytest.raises(StateError):
        record_feedback(complete(fresh(), 1), "approved")


def test_feedback_when_cap_reached_raises():
    state = done_through_four()
    for _ in range(MAX_REVISIONS):
        state = complete(complete(record_feedback(state, "changes"), 3), 4)
    with pytest.raises(StateError, match="cap"):
        record_feedback(state, "changes")


def test_feedback_when_cap_reached_still_allows_approval():
    state = done_through_four()
    for _ in range(MAX_REVISIONS):
        state = complete(complete(record_feedback(state, "changes"), 3), 4)
    assert record_feedback(state, "approved").status == "approved"


def test_complete_six_when_not_approved_raises():
    with pytest.raises(StateError):
        complete(done_through_four(), 6)


def test_complete_six_when_approved_marks_exported():
    state = complete(record_feedback(done_through_four(), "approved"), 6)
    assert state.status == "exported"
    assert next_step(state) is None
