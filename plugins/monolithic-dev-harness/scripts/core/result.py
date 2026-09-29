"""A step that can fail returns `Ok(value)` or `Err(failure)` instead of raising.

Callers chain steps with `bind` and `fmap`, and decide what a failure means with `match`. Only the
edges that touch the outside world (files, subprocesses, JSON) catch exceptions, through `attempt`,
and turn them into an `Err` there.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from itertools import dropwhile, takewhile, tee
from typing import Any, Generic, TypeVar

T = TypeVar("T")
U = TypeVar("U")


@dataclass(frozen=True)
class Failure:
    """Why a step failed, in a form safe to show to a workflow, a hook, or a person."""

    code: str
    message: str
    retryable: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "retryable": self.retryable}


@dataclass(frozen=True)
class Ok(Generic[T]):
    value: T


@dataclass(frozen=True)
class Err:
    failure: Failure


Result = Ok[T] | Err


def err(code: str, message: str, *, retryable: bool = False) -> Err:
    return Err(Failure(code, message, retryable))


def bind(result: Result[T], step: Callable[[T], Result[U]]) -> Result[U]:
    match result:
        case Ok(value):
            return step(value)
        case Err() as failed:
            return failed


def fmap(result: Result[T], transform: Callable[[T], U]) -> Result[U]:
    match result:
        case Ok(value):
            return Ok(transform(value))
        case Err() as failed:
            return failed


def map_failure(
    result: Result[T], transform: Callable[[Failure], Failure]
) -> Result[T]:
    match result:
        case Err(failure):
            return Err(transform(failure))
        case Ok() as kept:
            return kept


def recover(result: Result[T], fallback: Callable[[Failure], Result[T]]) -> Result[T]:
    match result:
        case Err(failure):
            return fallback(failure)
        case Ok() as kept:
            return kept


def value_or(result: Result[T], default: T) -> T:
    match result:
        case Ok(value):
            return value
        case Err():
            return default


def sequence(results: Iterable[Result[T]]) -> Result[tuple[T, ...]]:
    """All values in order, or the first failure. Results after the first failure are never produced."""
    ahead, behind = tee(results)
    values = tuple(result.value for result in takewhile(_succeeded, ahead))
    match next(dropwhile(_succeeded, behind), None):
        case Err() as failed:
            return failed
        case _:
            return Ok(values)


def _succeeded(result: Result[Any]) -> bool:
    return isinstance(result, Ok)


def oks(results: Iterable[Result[T]]) -> tuple[T, ...]:
    """The values of the results that succeeded, in order."""
    return tuple(result.value for result in results if isinstance(result, Ok))


def failures(results: Iterable[Result[T]]) -> tuple[Failure, ...]:
    return tuple(result.failure for result in results if isinstance(result, Err))


def require(condition: bool, code: str, message: str) -> Result[None]:
    return Ok(None) if condition else err(code, message)


def attempt(
    action: Callable[[], T],
    code: str,
    context: str,
    *errors: type[BaseException],
) -> Result[T]:
    """Run `action` at an edge; the listed exceptions become an `Err`, anything else propagates."""
    caught = errors or (Exception,)
    try:
        return Ok(action())
    except caught as exc:
        return err(code, f"{context}: {exc}")
