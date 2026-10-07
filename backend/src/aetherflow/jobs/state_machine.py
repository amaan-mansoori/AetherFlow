"""Authoritative Job state machine and transition policy."""

from aetherflow.api.errors import ApiError
from aetherflow.infrastructure.database.models import JobState

TERMINAL_STATES: frozenset[JobState] = frozenset(
    {
        JobState.SUCCEEDED,
        JobState.FAILED,
        JobState.CANCELLED,
        JobState.DEAD_LETTERED,
    }
)

VALID_TRANSITIONS: dict[JobState, frozenset[JobState]] = {
    JobState.ACCEPTED: frozenset({JobState.QUEUED, JobState.CANCEL_REQUESTED, JobState.CANCELLED}),
    JobState.QUEUED: frozenset(
        {
            JobState.RUNNING,
            JobState.CANCEL_REQUESTED,
            JobState.RETRY_SCHEDULED,
            JobState.DEAD_LETTERED,
        }
    ),
    JobState.RUNNING: frozenset(
        {
            JobState.SUCCEEDED,
            JobState.FAILED,
            JobState.RETRY_SCHEDULED,
            JobState.CANCEL_REQUESTED,
        }
    ),
    JobState.RETRY_SCHEDULED: frozenset(
        {JobState.QUEUED, JobState.CANCEL_REQUESTED, JobState.DEAD_LETTERED}
    ),
    JobState.CANCEL_REQUESTED: frozenset(
        {
            JobState.CANCELLED,
            JobState.SUCCEEDED,
            JobState.FAILED,
        }
    ),
    JobState.SUCCEEDED: frozenset(),
    JobState.FAILED: frozenset(),
    JobState.CANCELLED: frozenset(),
    JobState.DEAD_LETTERED: frozenset(),
}


def is_terminal_state(state: JobState) -> bool:
    """Return True if the state is terminal."""
    return state in TERMINAL_STATES


def can_transition(current_state: JobState, target_state: JobState) -> bool:
    """Check if transitioning from current_state to target_state is permitted."""
    allowed = VALID_TRANSITIONS.get(current_state, frozenset())
    return target_state in allowed


def validate_transition(current_state: JobState, target_state: JobState) -> None:
    """Validate transition, raising ApiError if invalid."""
    if is_terminal_state(current_state):
        raise ApiError(
            "INVALID_STATE_TRANSITION",
            f"Cannot transition job from terminal state '{current_state}'.",
            409,
        )
    if not can_transition(current_state, target_state):
        raise ApiError(
            "INVALID_STATE_TRANSITION",
            f"Cannot transition job from '{current_state}' to '{target_state}'.",
            409,
        )
