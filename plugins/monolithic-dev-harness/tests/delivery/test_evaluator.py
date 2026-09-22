import unittest

from scripts.orchestrator.evaluator import collect_critiques, evaluate_output
from tests.delivery.manifest_fixtures import capability


class TestEvaluator(unittest.TestCase):
    def setUp(self):
        self.manifest = capability(
            {
                "name": "start-ticket",
                "output_signature": {
                    "type": "object",
                    "required": ["ticket_id", "transition_required", "mode"],
                    "properties": {
                        "ticket_id": {"type": "string"},
                        "transition_required": {"type": "string"},
                        "mode": {"type": "string"},
                    },
                },
            }
        )

    def test_valid_output(self):
        self.assertEqual(
            evaluate_output(
                {
                    "ticket_id": "ENG-1",
                    "transition_required": "in_progress",
                    "mode": "instructions",
                },
                self.manifest,
            ),
            [],
        )

    def test_missing_property(self):
        critiques = evaluate_output({"ticket_id": "ENG-1"}, self.manifest)
        self.assertTrue(any("transition_required" in item for item in critiques))

    def test_collect_critiques_preserves_actor_feedback(self):
        output = {
            "ticket_id": "ENG-1",
            "transition_required": "in_progress",
            "mode": "instructions",
            "critiques": "needs verification",
        }
        self.assertEqual(
            collect_critiques(output, self.manifest), ["needs verification"]
        )


if __name__ == "__main__":
    unittest.main()
