"""Independent clients read through one gateway; no client can mutate the tracker."""

import json
import os
import subprocess
import sys

from core.result import Err, Ok
from harness import settings
from integrations import registry
from tests.settings_fixture import write_settings


def test_missing_gateway_never_launches_provider(tmp_path):
    write_settings(
        tmp_path,
        tracker={
            "name": "azure-devops",
            "values": {"organization": "o", "project": "p"},
        },
    )
    assert isinstance(
        registry.open_selected(tmp_path, settings.load(tmp_path)).value.get_work_item(
            "8141"
        ),
        Err,
    )
    assert (
        registry.open_selected(tmp_path, settings.load(tmp_path))
        .value.get_work_item("8141")
        .failure.code
        == "gateway_unavailable"
    )


def test_two_subprocess_clients_share_gateway_owner(tmp_path):
    from integrations.gateway_client import call
    from integrations.gateway_endpoint import serve

    write_settings(tmp_path)
    with serve(
        tmp_path, lambda operation, args: Ok({"pid": os.getpid(), "ref": args["ref"]})
    ):
        assert call(tmp_path, "tracker_get_work_item", {"ref": "8141"}) == Ok(
            {"pid": os.getpid(), "ref": "8141"}
        )
        assert (
            tuple(
                json.loads(
                    subprocess.check_output(
                        [
                            sys.executable,
                            "-c",
                            "import json,sys; from pathlib import Path; from integrations.gateway_client import call; print(json.dumps(call(Path(sys.argv[1]), 'tracker_get_work_item', {'ref':'8141'}).value))",
                            str(tmp_path),
                        ],
                        env=os.environ,
                    )
                )
                for _ in range(2)
            )
            == ({"pid": os.getpid(), "ref": "8141"},) * 2
        )
        assert (
            call(
                tmp_path,
                "tracker_transition_work_item",
                {"ref": "8141", "state": "done"},
            ).failure.code
            == "gateway_read_only"
        )
    assert (
        call(tmp_path, "tracker_get_work_item", {"ref": "8141"}).failure.code
        == "gateway_unavailable"
    )


def test_host_connections_are_independent_and_cli_requires_selection_when_ambiguous(
    tmp_path, monkeypatch
):
    from integrations.gateway_client import call
    from integrations.gateway_endpoint import serve

    write_settings(tmp_path)
    with (
        serve(tmp_path, lambda operation, args: Ok({"host": "claude"}), "claude"),
        serve(tmp_path, lambda operation, args: Ok({"host": "codex"}), "codex"),
    ):
        assert call(tmp_path, "tracker_get_work_item", {"ref": "1"}, "claude") == Ok(
            {"host": "claude"}
        )
        assert call(tmp_path, "tracker_get_work_item", {"ref": "1"}, "codex") == Ok(
            {"host": "codex"}
        )
        monkeypatch.delenv("MDH_GATEWAY_HOST", raising=False)
        monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
        monkeypatch.delenv("CURSOR_PROJECT_DIR", raising=False)
        monkeypatch.delenv("CODEX_PROJECT_ROOT", raising=False)
        ambiguous = call(tmp_path, "tracker_get_work_item", {"ref": "1"})
        assert ambiguous.failure.code == "gateway_unavailable"
        assert (
            "Multiple live workflow-integrations instances" in ambiguous.failure.message
        )
        monkeypatch.setenv("MDH_GATEWAY_HOST", "codex")
        assert call(tmp_path, "tracker_get_work_item", {"ref": "1"}) == Ok(
            {"host": "codex"}
        )
        assert (
            call(
                tmp_path,
                "tracker_transition_work_item",
                {"ref": "1", "state": "done"},
                "codex",
            ).failure.code
            == "gateway_read_only"
        )


def test_two_instances_of_one_host_are_independent_and_teardown_is_instance_scoped(
    tmp_path,
):
    from contextlib import ExitStack

    from integrations.gateway_client import call
    from integrations.gateway_endpoint import identity, serve

    write_settings(tmp_path)
    with ExitStack() as stack:
        first = stack.enter_context(
            serve(tmp_path, lambda operation, args: Ok({"instance": "first"}), "codex")
        )
        second = stack.enter_context(
            serve(tmp_path, lambda operation, args: Ok({"instance": "second"}), "codex")
        )
        assert first != second
        records = tuple(
            (tmp_path / ".harness/state/gateway-owners").glob(
                f"{identity(tmp_path)}-codex-*.json"
            )
        )
        assert len(records) == 2
        instances = tuple(json.loads(path.read_text())["instance"] for path in records)
        assert len(set(instances)) == 2
        assert (
            call(tmp_path, "tracker_get_work_item", {"ref": "1"}, "codex").failure.code
            == "gateway_unavailable"
        )
        assert {
            call(
                tmp_path,
                "tracker_get_work_item",
                {"ref": "1"},
                "codex",
                instance,
            ).value["instance"]
            for instance in instances
        } == {"first", "second"}
        stack.pop_all().close()
        assert not tuple(
            (tmp_path / ".harness/state/gateway-owners").glob(
                f"{identity(tmp_path)}-codex-*.json"
            )
        )


def test_crashed_gateway_record_is_ignored_when_selecting_live_owner(tmp_path):
    from integrations.gateway_client import call
    from integrations.gateway_endpoint import identity, serve

    write_settings(tmp_path)
    directory = tmp_path / ".harness/state/gateway-owners"
    directory.mkdir(parents=True, exist_ok=True)
    stale = directory / f"{identity(tmp_path)}-codex-{'a' * 32}.json"
    stale.write_text(
        json.dumps(
            {
                "pid": 99999999,
                "uid": os.getuid(),
                "host": "codex",
                "instance": "a" * 32,
                "endpoint": str(tmp_path / "missing.sock"),
            }
        )
    )
    with serve(tmp_path, lambda operation, args: Ok({"live": True}), "codex"):
        live_owner_records = tuple(
            path
            for path in directory.glob(f"{identity(tmp_path)}-codex-*.json")
            if path != stale
        )
        assert call(tmp_path, "tracker_get_work_item", {"ref": "1"}, "codex") == Ok(
            {"live": True}
        )
        assert (
            stale.exists()
        )  # stale records are ignored, never removed as untrusted input
    assert all(not path.exists() for path in live_owner_records)


def test_busy_gateway_remains_a_live_owner_when_probe_times_out(tmp_path, monkeypatch):
    from integrations import gateway_client
    from integrations.gateway_endpoint import identity, private, serve

    write_settings(tmp_path)

    class BusyProbe:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def settimeout(self, _timeout):
            return None

        def connect(self, _endpoint):
            raise TimeoutError("simulated saturated listener")

    with serve(tmp_path, lambda operation, args: Ok({"live": True}), "codex"):
        owner = json.loads(
            next(
                (tmp_path / ".harness/state/gateway-owners").glob(
                    f"{identity(tmp_path)}-codex-*.json"
                )
            ).read_text()
        )
        monkeypatch.setattr(gateway_client.socket, "socket", lambda *_args: BusyProbe())
        monkeypatch.setattr(gateway_client, "_process_exists", lambda _pid: True)
        assert gateway_client._owner_is_live(owner, private, 0.1)


def test_endpoint_is_scoped_to_project_and_configuration(tmp_path):
    from integrations.gateway_client import call
    from integrations.gateway_endpoint import serve

    write_settings(tmp_path)
    with serve(tmp_path, lambda operation, args: Ok({"owner": True})):
        write_settings(
            tmp_path,
            tracker={
                "name": "azure-devops",
                "values": {"organization": "other", "project": "p"},
            },
        )
        assert (
            call(tmp_path, "tracker_get_work_item", {"ref": "8141"}).failure.code
            == "gateway_unavailable"
        )


def test_multiple_cli_reads_reuse_the_real_provider_pid(tmp_path):
    from integrations import transport
    from integrations.gateway_endpoint import serve
    from tests.integrations.test_transport import SERVER

    write_settings(tmp_path)
    server = tmp_path / "provider.py"
    server.write_text(SERVER)
    provider = transport.mcp(sys.executable, (str(server),), 3)
    with serve(tmp_path, lambda operation, args: provider("pid", {})):
        replies = tuple(
            json.loads(
                subprocess.check_output(
                    [
                        sys.executable,
                        "-c",
                        "import json,sys; from pathlib import Path; from integrations.gateway_client import call; print(json.dumps(call(Path(sys.argv[1]), 'tracker_get_work_item', {'ref':'8141'}).value))",
                        str(tmp_path),
                    ],
                    env=os.environ,
                )
            )
            for _ in range(2)
        )
        assert replies[0] == replies[1]
        assert replies[0]["pid"] != os.getpid()


def test_clients_find_the_owner_whatever_their_temporary_directory(
    tmp_path, monkeypatch
):
    import shutil
    import tempfile

    import pytest

    from integrations.gateway_client import call
    from integrations.gateway_endpoint import serve

    write_settings(tmp_path)
    roots = tuple(tempfile.mkdtemp(prefix="g") for _ in range(2))
    try:
        monkeypatch.setattr(tempfile, "tempdir", roots[0])
        with serve(tmp_path, lambda operation, args: Ok({"owner": True})):
            monkeypatch.setattr(tempfile, "tempdir", roots[1])
            assert call(tmp_path, "tracker_get_work_item", {"ref": "1"}) == Ok(
                {"owner": True}
            )
            reply = subprocess.check_output(
                [
                    sys.executable,
                    "-c",
                    "import json,sys; from pathlib import Path; from integrations.gateway_client import call; print(json.dumps(call(Path(sys.argv[1]), 'tracker_get_work_item', {'ref':'1'}).value))",
                    str(tmp_path),
                ],
                env={**os.environ, "TMPDIR": roots[1]},
            )
            assert json.loads(reply) == {"owner": True}
            with (
                pytest.raises(OSError, match="Another workflow-integrations gateway"),
                serve(tmp_path, lambda operation, args: Ok({"owner": False})),
            ):
                pass
    finally:
        for root in roots:
            shutil.rmtree(root, ignore_errors=True)


def test_an_overlong_socket_path_is_refused_before_listening(tmp_path, monkeypatch):
    import tempfile

    import pytest

    from integrations.gateway_endpoint import serve

    write_settings(tmp_path)
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / ("x" * 120)))
    with (
        pytest.raises(OSError, match="shorter TMPDIR"),
        serve(tmp_path, lambda operation, args: Ok({})),
    ):
        pass
