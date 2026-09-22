import unittest

from scripts.orchestrator.failures import (
    Deterministic,
    Fatal,
    HandlerContractError,
    InputContractError,
    PolicyDenied,
    SkillAssetMissing,
    SkillFailure,
    Transient,
    classify,
)


class TestFailureTaxonomy(unittest.TestCase):
    def test_every_declared_failure_has_a_kind(self):
        self.assertEqual(classify(HandlerContractError("x")), Fatal())
        self.assertEqual(classify(InputContractError("x")), Deterministic())
        self.assertEqual(classify(PolicyDenied("x")), Deterministic())
        self.assertEqual(classify(SkillAssetMissing("x")), Deterministic())

    def test_an_unclassified_failure_is_assumed_transient(self):
        """Wasting a retry budget is recoverable; aborting a viable run is not."""
        for error in (ValueError("x"), TimeoutError("x"), RuntimeError("x")):
            self.assertEqual(classify(error), Transient(), error)

    def test_declared_failures_keep_their_builtin_base(self):
        """Existing `except` clauses in handler code must keep working."""
        self.assertIsInstance(PolicyDenied("x"), ValueError)
        self.assertIsInstance(InputContractError("x"), ValueError)
        self.assertIsInstance(SkillAssetMissing("x"), FileNotFoundError)
        self.assertIsInstance(HandlerContractError("x"), TypeError)

    def test_every_declared_failure_shares_one_root(self):
        for error in (
            HandlerContractError("x"),
            InputContractError("x"),
            PolicyDenied("x"),
            SkillAssetMissing("x"),
        ):
            self.assertIsInstance(error, SkillFailure)


if __name__ == "__main__":
    unittest.main()
