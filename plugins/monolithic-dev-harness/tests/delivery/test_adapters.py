import unittest

from scripts.orchestrator.adapters import (
    to_anthropic_dialect,
    to_anthropic_tool,
)
from scripts.orchestrator.state import Task, TaskState


class TestAdapters(unittest.TestCase):
    def setUp(self):
        self.instructions = "You must analyze the AST."
        self.task = Task(
            id="task_1",
            skill_name="ast_parser",
            state=TaskState.READY,
            inputs={"file_path": "main.py"},
        )
        self.task_with_critiques = self.task.copy_with(
            critiques=["Failed to identify class names.", "Missed imports."]
        )

        self.manifest = {
            "name": "ast_parser",
            "description": "Parses python AST.",
            "input_schema": {
                "type": "object",
                "properties": {"file_path": {"type": "string"}},
            },
        }

    def test_anthropic_dialect(self):
        result = to_anthropic_dialect(self.instructions, self.task_with_critiques)
        self.assertIn("<instructions>", result)
        self.assertIn("You must analyze the AST.", result)
        self.assertIn("<task_payload>", result)
        self.assertIn('"file_path": "main.py"', result)
        self.assertIn("<reflection>", result)
        self.assertIn(
            '<critique index="0">Failed to identify class names.</critique>', result
        )

    def test_anthropic_tool_binding(self):
        tool = to_anthropic_tool(self.manifest)
        self.assertEqual(tool["name"], "ast_parser")
        self.assertEqual(tool["description"], "Parses python AST.")
        self.assertIn("properties", tool["input_schema"])


if __name__ == "__main__":
    unittest.main()
