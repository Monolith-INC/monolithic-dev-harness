from pathlib import Path

import pytest

from core.result import Err, Ok
from harness.installation_scope import scope_environment


def test_registration_scope_does_not_change_original_package_locations(tmp_path):
    project = tmp_path / "project with spaces"
    project.mkdir()
    result = scope_environment("local", project, tmp_path / "home")
    assert isinstance(result, Ok)
    values = dict(result.value)
    assert values == dict(scope_environment("user", None, tmp_path / "home").value)
    assert (
        Path(values["HARNESS_HOME"])
        == tmp_path / "home/.local/share/monolithic-dev-harness"
    )
    assert Path(values["HARNESS_BIN_DIR"]) == tmp_path / "home/.local/bin"


def test_user_scope_does_not_reinterpret_as_system_global(tmp_path):
    values = dict(scope_environment("user", None, tmp_path).value)
    assert values["HARNESS_HOME"] == str(
        tmp_path / ".local/share/monolithic-dev-harness"
    )


@pytest.mark.parametrize("scope", ("project", "all", "global", "unknown"))
def test_install_rejects_unimplemented_or_noninstall_scope(tmp_path, scope):
    assert isinstance(scope_environment(scope, tmp_path, tmp_path / "home"), Err)


def test_local_cannot_target_home_or_filesystem_root(tmp_path):
    assert isinstance(scope_environment("local", tmp_path, tmp_path), Err)
    assert isinstance(scope_environment("local", Path("/"), tmp_path), Err)
