import sys
import unittest
from io import StringIO
from unittest.mock import patch

from scripts.orchestrator.hooks import authorization_hook, cli_ui_hook
from scripts.orchestrator.state import Event, QueueState, Task, TaskState
from scripts.orchestrator.stream import OrchestratorStream


class TestHooksAndStream(unittest.TestCase):
    def setUp(self):
        self.initial_tasks = {
            "task_c": Task(
                id="task_c", skill_name="blueprint_architect", state=TaskState.READY
            )
        }
        self.initial_state = QueueState(tasks=self.initial_tasks)
        self.stream = OrchestratorStream(self.initial_state)

        # Subscribe the hooks
        self.stream.subscribe(cli_ui_hook)
        self.stream.subscribe(authorization_hook)

    @patch("builtins.input", return_value="IMPLEMENTATION APPROVED")
    def test_authorization_hook_flow(self, mock_input):
        # Capture stderr to verify cli_ui_hook (stdout is reserved for MCP JSON-RPC).
        captured_output = StringIO()
        sys.stderr = captured_output

        # 1. Spawn task
        self.stream.dispatch(
            Event(type="TaskSpawnedEvent", payload={"task_id": "task_c"})
        )

        # 2. Fail 3 times to trip the circuit breaker
        self.stream.dispatch(
            Event(
                type="TaskFailedEvent",
                payload={"task_id": "task_c", "critique": "Error 1"},
            )
        )
        self.stream.dispatch(
            Event(type="TaskSpawnedEvent", payload={"task_id": "task_c"})
        )
        self.stream.dispatch(
            Event(
                type="TaskFailedEvent",
                payload={"task_id": "task_c", "critique": "Error 2"},
            )
        )
        self.stream.dispatch(
            Event(type="TaskSpawnedEvent", payload={"task_id": "task_c"})
        )

        # The 3rd failure will trip the circuit breaker, changing state to BLOCKED_REQUIRES_REVIEW.
        # The authorization_hook will catch this, prompt the user (mocked), and dispatch an AuthorizationReceivedEvent.
        # This will immediately change the state back to READY.
        self.stream.dispatch(
            Event(
                type="TaskFailedEvent",
                payload={"task_id": "task_c", "critique": "Error 3"},
            )
        )

        # Restore stderr
        sys.stderr = sys.__stderr__

        # Verify final state
        final_task = self.stream.state.tasks["task_c"]
        self.assertEqual(
            final_task.state,
            TaskState.READY,
            "Task should have been auto-recovered by the auth hook dispatch",
        )
        self.assertEqual(final_task.retry_count, 0, "Retries should be cleared")
        self.assertEqual(len(final_task.critiques), 0, "Critiques should be cleared")

        # Verify the history contains the AuthorizationReceivedEvent emitted by the hook
        event_types = [e.type for e in self.stream.state.events_history]
        self.assertIn("AuthorizationReceivedEvent", event_types)

        # Verify UI output
        output_str = captured_output.getvalue()
        self.assertIn("Task [task_c] is now In_Progress", output_str)
        self.assertIn("Circuit Breaker tripped for task 'task_c'", output_str)
        self.assertIn("Authorization received for task 'task_c'", output_str)

    def test_nested_dispatch_uses_latest_state(self):
        def outer_hook(state, event, stream):
            if (
                event.type == "TaskFailedEvent"
                and state.tasks["task_c"].state == TaskState.BLOCKED_REQUIRES_REVIEW
            ):
                stream.dispatch(
                    Event(
                        type="AuthorizationReceivedEvent",
                        payload={
                            "task_id": "task_c",
                            "token": "IMPLEMENTATION APPROVED",
                        },
                    )
                )

        stream = OrchestratorStream(self.initial_state, max_retries=3)
        stream.subscribe(outer_hook)
        for i in range(3):
            stream.dispatch(
                Event(type="TaskSpawnedEvent", payload={"task_id": "task_c"})
            )
            stream.dispatch(
                Event(
                    type="TaskFailedEvent",
                    payload={"task_id": "task_c", "critique": f"err {i}"},
                )
            )

        self.assertEqual(stream.state.tasks["task_c"].state, TaskState.READY)
        event_types = [event.type for event in stream.state.events_history]
        self.assertIn("AuthorizationReceivedEvent", event_types)


if __name__ == "__main__":
    unittest.main()
