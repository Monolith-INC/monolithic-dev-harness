import unittest

from scripts.orchestrator.handlers import (
    get_handler,
    handle_feature_implementation,
    handle_finish_feature_development,
    handle_merge_story_stack_into_feature,
    handle_reconcile_feature_stack,
)
from scripts.orchestrator.invocation import Invocation


def _invocation(skill: str, arguments: dict) -> Invocation:
    return Invocation(
        manifest={"name": skill},
        arguments=arguments,
        instructions=f"run {skill}",
        attempt=1,
    )


class FeatureHandlerTests(unittest.TestCase):
    def test_feature_handlers_emit_structured_plan(self):
        args = {
            "feature_ref": "FEAT-1",
            "children": [
                {
                    "key": "US-1",
                    "title": "One",
                    "state": "in_progress",
                    "missing_artifacts": ["spec"],
                },
                {
                    "key": "US-2",
                    "title": "Two",
                    "state": "done",
                    "missing_artifacts": [],
                },
            ],
        }
        for handler, skill in (
            (handle_feature_implementation, "feature-implementation"),
            (handle_finish_feature_development, "finish-feature-development"),
            (handle_reconcile_feature_stack, "reconcile-feature-stack"),
            (handle_merge_story_stack_into_feature, "merge-story-stack-into-feature"),
        ):
            result = handler(_invocation(skill, args))
            self.assertEqual(result.product["mode"], "instructions")
            self.assertEqual(result.product["plan"]["feature_ref"], "FEAT-1")
            self.assertEqual(
                result.product["plan"]["ordered_story_keys"], ["US-1", "US-2"]
            )
            self.assertIs(get_handler(skill), handler)


if __name__ == "__main__":
    unittest.main()
