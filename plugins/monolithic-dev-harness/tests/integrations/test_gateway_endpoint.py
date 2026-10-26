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
