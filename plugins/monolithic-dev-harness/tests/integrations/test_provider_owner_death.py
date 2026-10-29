"""An abruptly killed gateway must not leave its authentication process running."""

import os
import subprocess
import sys
import time
from pathlib import Path


def stopped(pid: str) -> bool:
    match Path(f"/proc/{pid}/stat").exists():
        case False:
            return True
        case True:
            return Path(f"/proc/{pid}/stat").read_text().split()[2] == "Z"


def _assert_gateway_death_cleans_provider(tmp_path, provider):
    marker = tmp_path / "provider-pid"
    code = f"from integrations import transport; import sys; transport.mcp(sys.executable, ('-c', {provider!r}), 30)('read', {{}})"
    with subprocess.Popen([sys.executable, "-c", code], env=os.environ) as owner:
        assert next(
            (True for _ in range(100) if not time.sleep(0.02) and marker.exists()),
            False,
        )
        owner.kill()
        owner.wait(timeout=2)
        assert next(
            (
                True
                for _ in range(100)
                if not time.sleep(0.02) and stopped(marker.read_text())
            ),
            False,
        )


def test_gateway_death_terminates_its_provider_group(tmp_path):
    _assert_gateway_death_cleans_provider(
        tmp_path,
        f"import os,time; from pathlib import Path; Path({str(tmp_path / 'provider-pid')!r}).write_text(str(os.getpid())); time.sleep(30)",
    )


def test_gateway_death_kills_provider_that_ignores_term(tmp_path):
    _assert_gateway_death_cleans_provider(
        tmp_path,
        f"import os,signal,time; from pathlib import Path; signal.signal(signal.SIGTERM, signal.SIG_IGN); Path({str(tmp_path / 'provider-pid')!r}).write_text(str(os.getpid())); time.sleep(30)",
    )
