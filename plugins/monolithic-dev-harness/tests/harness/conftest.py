"""Host-neutral test baseline; native-host tests declare their real capability explicitly."""

import pytest


@pytest.fixture(autouse=True)
def neutral_host_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory
) -> None:
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    # The machine's own saved preferences (its language) must not reach a test.
    monkeypatch.setenv(
        "HARNESS_USER_STATE_DIR", str(tmp_path_factory.mktemp("preferences"))
    )
