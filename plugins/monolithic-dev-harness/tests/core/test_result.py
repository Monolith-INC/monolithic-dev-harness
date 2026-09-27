from __future__ import annotations

import unittest

from core.result import (
    Err,
    Failure,
    Ok,
    attempt,
    bind,
    err,
    fmap,
    recover,
    sequence,
    value_or,
)


class ResultTest(unittest.TestCase):
    def test_bind_and_fmap_chain_until_the_first_failure(self) -> None:
        self.assertEqual(bind(Ok(2), lambda n: Ok(n * 3)), Ok(6))
        self.assertEqual(fmap(Ok(2), str), Ok("2"))
        failed = err("bad", "no")
        self.assertIs(bind(failed, lambda n: Ok(n)), failed)
        self.assertIs(fmap(failed, str), failed)

    def test_sequence_keeps_order_or_returns_the_first_failure(self) -> None:
        self.assertEqual(sequence([Ok(1), Ok(2)]), Ok((1, 2)))
        self.assertEqual(
            sequence([Ok(1), err("a", "x"), err("b", "y")]), Err(Failure("a", "x"))
        )
        self.assertEqual(sequence([]), Ok(()))

    def test_recover_and_value_or(self) -> None:
        self.assertEqual(
            recover(err("a", "x"), lambda failure: Ok(failure.code)), Ok("a")
        )
        self.assertEqual(value_or(err("a", "x"), 5), 5)
        self.assertEqual(value_or(Ok(1), 5), 1)

    def test_attempt_turns_listed_exceptions_into_failures(self) -> None:
        self.assertEqual(
            attempt(lambda: int("7"), "bad_int", "parse", ValueError), Ok(7)
        )
        result = attempt(lambda: int("x"), "bad_int", "parse", ValueError)
        self.assertIsInstance(result, Err)
        self.assertEqual(result.failure.code, "bad_int")
        with self.assertRaises(ZeroDivisionError):
            attempt(lambda: 1 // 0, "bad", "divide", ValueError)

    def test_sequence_stops_producing_after_the_first_failure(self) -> None:
        produced: list[int] = []

        def result(n: int):
            produced.append(n)
            return Ok(n) if n != 2 else err("stop", "two")

        self.assertEqual(sequence(result(n) for n in range(5)).failure.code, "stop")
        self.assertEqual(produced, [0, 1, 2])
