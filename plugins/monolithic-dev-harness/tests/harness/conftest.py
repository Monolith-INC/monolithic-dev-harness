"""Host-neutral test baseline; native-host tests declare their real capability explicitly."""

import pytest


@pytest.fixture(autouse=True)
def neutral_host_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
