import json
import unittest

from scripts.orchestrator.reducers import reduce_queue_state
from scripts.orchestrator.state import (
    Event,
    FrozenDict,
    QueueState,
    Task,
    TaskState,
)


class TestOrchestratorReducers(unittest.TestCase):
    def setUp(self):
        self.initial_tasks = {
            "task_a": Task(id="task_a", skill_name="parse_ast", state=TaskState.READY),
            "task_b": Task(
                id="task_b",
                skill_name="write_test",
                state=TaskState.BLOCKED,
                dependencies=["task_a"],
            ),
        }
        self.initial_state = QueueState(tasks=self.initial_tasks)

    def test_queue_resolution_on_completion(self):
        state = self.initial_state

        # 1. Spawn Task A
        event_spawn = Event(type="TaskSpawnedEvent", payload={"task_id": "task_a"})
        state = reduce_queue_state(state, event_spawn)
        self.assertEqual(state.tasks["task_a"].state, TaskState.IN_PROGRESS)
        self.assertEqual(state.tasks["task_b"].state, TaskState.BLOCKED)

        # 2. Complete Task A -> Should unblock Task B
        event_complete = Event(
            type="TaskCompletedEvent",
            payload={"task_id": "task_a", "output": "AST parsed"},
        )
        state = reduce_queue_state(state, event_complete)

        self.assertEqual(state.tasks["task_a"].state, TaskState.COMPLETED)
        self.assertEqual(state.tasks["task_a"].output, "AST parsed")
        self.assertEqual(
            state.tasks["task_b"].state,
            TaskState.READY,
            "Task B should be unblocked and READY",
        )

    def test_circuit_breaker_and_reflection_loop(self):
        state = self.initial_state

        state = reduce_queue_state(
            state, Event(type="TaskSpawnedEvent", payload={"task_id": "task_a"})
        )
        state = reduce_queue_state(
            state,
            Event(
                type="TaskFailedEvent",
                payload={"task_id": "task_a", "critique": "Failed compilation"},
            ),
        )

        self.assertEqual(state.tasks["task_a"].state, TaskState.READY)
        self.assertEqual(state.tasks["task_a"].retry_count, 1)
        self.assertEqual(len(state.tasks["task_a"].critiques), 1)

        for critique in ("Missing import", "Still failing"):
            state = reduce_queue_state(
                state, Event(type="TaskSpawnedEvent", payload={"task_id": "task_a"})
            )
            state = reduce_queue_state(
                state,
                Event(
                    type="TaskFailedEvent",
                    payload={"task_id": "task_a", "critique": critique},
                ),
            )

        self.assertEqual(
            state.tasks["task_a"].state,
            TaskState.BLOCKED_REQUIRES_REVIEW,
            "Circuit breaker should block task",
        )
        self.assertEqual(state.tasks["task_a"].retry_count, 3)

        # Authorize Task A after manual review / instruction update
        event_auth = Event(
            type="AuthorizationReceivedEvent",
            payload={"task_id": "task_a", "token": "IMPLEMENTATION APPROVED"},
        )
        state = reduce_queue_state(state, event_auth)

        self.assertEqual(
            state.tasks["task_a"].state,
            TaskState.READY,
            "Task should be READY after authorization",
        )
        self.assertEqual(
            state.tasks["task_a"].retry_count, 0, "Retries should be reset"
        )
        self.assertEqual(
            len(state.tasks["task_a"].critiques), 0, "Critiques should be cleared"
        )

    def test_missing_dependency_does_not_crash_completion(self):
        state = QueueState(
            tasks={
                "task_a": Task(
                    id="task_a", skill_name="parse_ast", state=TaskState.IN_PROGRESS
                ),
                "task_b": Task(
                    id="task_b",
                    skill_name="write_test",
                    state=TaskState.BLOCKED,
                    dependencies=["task_a", "missing_task"],
                ),
            }
        )
        event_complete = Event(
            type="TaskCompletedEvent", payload={"task_id": "task_a", "output": "done"}
        )
        state = reduce_queue_state(state, event_complete)
        self.assertEqual(state.tasks["task_b"].state, TaskState.BLOCKED)

    def test_unrelated_completion_does_not_unblock_dependency_free_task(self):
        state = QueueState(
            tasks={
                "task_a": Task(
                    id="task_a", skill_name="parse_ast", state=TaskState.IN_PROGRESS
                ),
                "held": Task(
                    id="held", skill_name="write_test", state=TaskState.BLOCKED
                ),
            }
        )
        event_complete = Event(
            type="TaskCompletedEvent", payload={"task_id": "task_a", "output": "done"}
        )
        state = reduce_queue_state(state, event_complete)
        self.assertEqual(
            state.tasks["held"].state,
            TaskState.BLOCKED,
            "A task blocked without dependencies must not be released by an unrelated completion",
        )

    def test_completion_only_unblocks_its_own_dependents(self):
        state = QueueState(
            tasks={
                "task_a": Task(
                    id="task_a", skill_name="parse_ast", state=TaskState.IN_PROGRESS
                ),
                "task_b": Task(
                    id="task_b", skill_name="other", state=TaskState.COMPLETED
                ),
                "dependent": Task(
                    id="dependent",
                    skill_name="write_test",
                    state=TaskState.BLOCKED,
                    dependencies=["task_b"],
                ),
            }
        )
        event_complete = Event(
            type="TaskCompletedEvent", payload={"task_id": "task_a", "output": "done"}
        )
        state = reduce_queue_state(state, event_complete)
        self.assertEqual(
            state.tasks["dependent"].state,
            TaskState.BLOCKED,
            "Completing task_a must not release a task that does not depend on it",
        )

    def test_nested_state_is_immutable_and_json_serializable(self):
        source_inputs = {"nested": {"items": ["first"]}}
        source_output = {"nested": {"items": ["result"]}}
        source_dependencies = ["dependency"]
        source_critiques = ["critique"]
        task = Task(
            id="task",
            skill_name="demo",
            inputs=source_inputs,
            dependencies=source_dependencies,
            critiques=source_critiques,
            output=source_output,
        )
        event = Event(type="Observed", payload={"nested": {"value": 1}})
        state = QueueState(tasks={"task": task}, events_history=[event])

        source_inputs["nested"]["items"].append("source mutation")
        source_output["nested"]["items"].append("source mutation")
        source_dependencies.append("source mutation")
        source_critiques.append("source mutation")
        # JSON arrays keep their shape: frozen payloads still compare equal to
        # the documents they came from. Only the declared tuple fields are tuples.
        self.assertEqual(task.inputs["nested"]["items"], ["first"])
        self.assertEqual(task.output["nested"]["items"], ["result"])
        self.assertEqual(task.dependencies, ("dependency",))
        self.assertEqual(task.critiques, ("critique",))
        self.assertEqual(task.inputs, {"nested": {"items": ["first"]}})
        with self.assertRaises(TypeError):
            task.inputs["nested"]["other"] = True
        with self.assertRaises(TypeError):
            task.inputs["nested"]["items"].append("mutation")
        with self.assertRaises(TypeError):
            event.payload["nested"]["value"] = 2
        with self.assertRaises(TypeError):
            state.tasks["other"] = task

        rendered = json.dumps(task.inputs)
        self.assertIn('"first"', rendered)

    def test_preconstructed_frozen_dict_is_recursively_normalized(self):
        nested_items = ["first"]
        task = Task(
            id="task",
            skill_name="demo",
            inputs=FrozenDict({"nested": nested_items}),
        )

        nested_items.append("source mutation")
        self.assertEqual(task.inputs["nested"], ["first"])
        with self.assertRaises(TypeError):
            task.inputs["nested"].append("mutation")

    def test_invalid_transition_is_a_recorded_no_op(self):
        state = QueueState(
            tasks={"task": Task(id="task", skill_name="demo", state=TaskState.READY)}
        )
        event = Event(
            type="TaskCompletedEvent",
            payload={"task_id": "task", "output": "too early"},
        )

        after = reduce_queue_state(state, event)

        self.assertEqual(after.tasks["task"].state, TaskState.READY)
        self.assertIsNone(after.tasks["task"].output)
        self.assertEqual(after.events_history, (event,))

    def test_unknown_and_missing_task_events_are_recorded_once(self):
        state = QueueState()
        events = [Event(type="Unknown"), Event(type="TaskFailedEvent")]
        for event in events:
            state = reduce_queue_state(state, event)
        self.assertEqual(state.events_history, tuple(events))


if __name__ == "__main__":
    unittest.main()
