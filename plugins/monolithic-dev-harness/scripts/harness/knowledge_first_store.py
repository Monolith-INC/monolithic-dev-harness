"""Protected, per-conversation state for knowledge-first observations.

Each prompt replaces its epoch. A late tool result cannot satisfy a later prompt.
"""

import fcntl
import hashlib
import secrets
from dataclasses import asdict, dataclass
from pathlib import Path

from core.result import Result, attempt, err
from harness import knowledge_first, state


@dataclass(frozen=True)
class Record:
    epoch: str
    value: knowledge_first.State
    pending: tuple[str, ...] = ()


def _path(repo: Path, host: str, conversation: str) -> Path:
    identity = (host + "\0" + conversation).encode("utf-8")
    return (
        state.state_dir(repo)
        / "knowledge-first"
        / (hashlib.sha256(identity).hexdigest() + ".json")
    )


def _decode(value: dict | None) -> Record | None:
    match value:
        case {
            "epoch": str() as epoch,
            "searched": bool() as searched,
            "reminded": bool() as reminded,
            "empty_noticed": bool() as noticed,
            "pending": list() as pending,
        } if epoch and all(isinstance(item, str) and item for item in pending):
            return Record(
                epoch,
                knowledge_first.State(searched, reminded, noticed),
                tuple(pending),
            )
        case _:
            return None


def _locked(path: Path, action):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix(".lock").open("a", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return action()


def _write(path: Path, record: Record) -> Record:
    state.write_json(
        path,
        {
            "epoch": record.epoch,
            **asdict(record.value),
            "pending": list(record.pending),
        },
    )
    return record


def begin_prompt(repo: Path, host: str, conversation: str) -> Result[Record]:
    path = _path(repo, host, conversation)
    match bool(host.strip()) and bool(conversation.strip()):
        case False:
            return err(
                "knowledge_state_unavailable", "Conversation identity is unavailable."
            )
        case True:
            return attempt(
                lambda: _locked(
                    path,
                    lambda: _write(
                        path, Record(secrets.token_hex(16), knowledge_first.State())
                    ),
                ),
                "knowledge_state_unavailable",
                "Could not reset the knowledge reminder",
                OSError,
                ValueError,
            )


def read(repo: Path, host: str, conversation: str) -> Record | None:
    return _decode(state.read_json(_path(repo, host, conversation)))


def transition(
    repo: Path,
    host: str,
    conversation: str,
    epoch: str,
    available: bool,
    action: knowledge_first.Action,
) -> Result[knowledge_first.Outcome | None]:
    path = _path(repo, host, conversation)

    def apply() -> knowledge_first.Outcome | None:
        match _decode(state.read_json(path)):
            case Record(epoch=found, value=value) as record if found == epoch:
                result = knowledge_first.evaluate(value, True, available, action)
                _write(path, Record(found, result.state, record.pending))
                return result
            case _:
                return None

    match bool(host.strip()) and bool(conversation.strip()) and bool(epoch.strip()):
        case False:
            return err(
                "knowledge_state_unavailable", "Conversation identity is unavailable."
            )
        case True:
            return attempt(
                lambda: _locked(path, apply),
                "knowledge_state_unavailable",
                "Could not update the knowledge reminder",
                OSError,
                ValueError,
            )


def observe_read(
    repo: Path, host: str, conversation: str, epoch: str, tool_use_id: str
) -> Result[bool]:
    path = _path(repo, host, conversation)

    def apply() -> bool:
        match _decode(state.read_json(path)):
            case Record(epoch=found) as record if (
                found == epoch and tool_use_id and tool_use_id not in record.pending
            ):
                _write(
                    path, Record(found, record.value, (*record.pending, tool_use_id))
                )
                return True
            case _:
                return False

    match (
        bool(host.strip())
        and bool(conversation.strip())
        and bool(epoch.strip())
        and bool(tool_use_id.strip())
    ):
        case False:
            return err(
                "knowledge_state_unavailable",
                "Conversation or tool identity is unavailable.",
            )
        case True:
            return attempt(
                lambda: _locked(path, apply),
                "knowledge_state_unavailable",
                "Could not observe knowledge read",
                OSError,
                ValueError,
            )


def complete_read(
    repo: Path, host: str, conversation: str, tool_use_id: str, success: bool
) -> Result[bool]:
    path = _path(repo, host, conversation)

    def apply() -> bool:
        match _decode(state.read_json(path)):
            case Record() as record if tool_use_id and tool_use_id in record.pending:
                remaining = tuple(
                    item for item in record.pending if item != tool_use_id
                )
                value = (
                    knowledge_first.evaluate(
                        record.value, True, True, "knowledge_read"
                    ).state
                    if success
                    else record.value
                )
                _write(path, Record(record.epoch, value, remaining))
                return success
            case _:
                return False

    match (
        bool(host.strip()) and bool(conversation.strip()) and bool(tool_use_id.strip())
    ):
        case False:
            return err(
                "knowledge_state_unavailable",
                "Conversation or tool identity is unavailable.",
            )
        case True:
            return attempt(
                lambda: _locked(path, apply),
                "knowledge_state_unavailable",
                "Could not confirm knowledge read",
                OSError,
                ValueError,
            )
