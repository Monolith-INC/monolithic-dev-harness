import unittest

from orchestrator_core.reducers import reduce_queue_state
from orchestrator_core.state import Event, QueueState, Task, TaskState
from orchestrator_core.stream import OrchestratorStream


class TestStream(unittest.TestCase):
    def test_task_failure_trips_circuit_breaker(self) -> None:
        task = Task(id="t1", skill_name="validate-artifact")
        state = QueueState(tasks={"t1": task})
        stream = OrchestratorStream(state, max_retries=3)
        for i in range(3):
            stream.dispatch(
                Event(type="TaskFailedEvent", payload={"task_id": "t1", "critique": f"fail-{i}"})
            )
        self.assertEqual(stream.state.tasks["t1"].state, TaskState.BLOCKED_REQUIRES_REVIEW)

    def test_authorization_resets_task(self) -> None:
        task = Task(
            id="t1",
            skill_name="auto-fix-artifact",
            state=TaskState.BLOCKED_REQUIRES_REVIEW,
            retry_count=3,
            critiques=["a"],
        )
        state = QueueState(tasks={"t1": task})
        new_state = reduce_queue_state(
            state,
            Event(
                type="AuthorizationReceivedEvent",
                payload={"task_id": "t1", "token": "IMPLEMENTATION APPROVED"},
            ),
        )
        self.assertEqual(new_state.tasks["t1"].state, TaskState.READY)
        self.assertEqual(new_state.tasks["t1"].retry_count, 0)


if __name__ == "__main__":
    unittest.main()
