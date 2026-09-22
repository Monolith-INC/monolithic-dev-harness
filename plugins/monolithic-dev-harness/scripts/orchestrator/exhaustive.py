"""Compile-time exhaustiveness for pattern matches over sum types.

Python checks nothing about a `match` at runtime beyond what executes, so a
missing arm over an algebraic type is invisible until the value that needs it
appears. Passing the unmatched value here makes the type checker do that work:
in an exhaustive match the fallthrough arm narrows to `Never` and this call is
valid, and adding a constructor without handling it makes the same call a type
error at the point of the omission.

The runtime raise is the backstop for anything that reaches production
unchecked.
"""

from __future__ import annotations

from typing import NoReturn


def assert_never(value: NoReturn) -> NoReturn:
    """Assert that ``value`` is unreachable. Fails the type check if it is not."""
    raise AssertionError(f"non-exhaustive match over {type(value).__name__}: {value!r}")
