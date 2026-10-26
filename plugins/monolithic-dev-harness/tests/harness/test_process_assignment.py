from pathlib import Path

from core.result import Err, Ok
from harness import rules
from harness.process_assignment import Assignment, authorize_call, decode_assignment


def test_decode_reviewer_and_worker() -> None:
    assert decode_assignment(
        {"role": "reviewer", "owned_paths": [], "model": "m", "effort": "low"}
    ) == Ok(Assignment("reviewer", (), "m", "low"))
    assert decode_assignment(
        {
            "role": "worker",
            "owned_paths": ["src/a.dart"],
            "model": "m",
            "effort": "high",
        }
    ) == Ok(Assignment("worker", ("src/a.dart",), "m", "high"))


def test_decode_rejects_extra_or_unsafe_fields() -> None:
    for paths in (["../a"], [".git/config"], ["src/*.dart"], [], ["a", "a"]):
        result = decode_assignment(
            {"role": "worker", "owned_paths": paths, "model": "m", "effort": "low"}
        )
        assert isinstance(result, Err)
    assert isinstance(
        decode_assignment(
            {"role": "reviewer", "owned_paths": [], "model": "", "effort": "low"}
        ),
        Err,
    )
    assert isinstance(
        decode_assignment(
            {
                "role": "reviewer",
                "owned_paths": [],
                "model": "m",
                "effort": "low",
                "x": 1,
            }
        ),
        Err,
    )


def test_reviewer_only_reads_and_safe_shell(tmp_path: Path) -> None:
    assignment = Assignment("reviewer", (), "m", "low")
    read = rules.make_call("read", {}, kind="read", file_paths=("anything",))
    assert authorize_call(tmp_path, assignment, read) is None
    assert (
        authorize_call(
            tmp_path, assignment, rules.make_call("x", {}, kind="mcp", server="github")
        ).allowed
        is False
    )
    assert (
        authorize_call(
            tmp_path,
            assignment,
            rules.make_call("shell", {}, kind="shell", command="pwd"),
        )
        is None
    )
    for command in (
        "cat -- README.md",
        "cat -- README.md src/a",
        "rg --no-config -n -- needle README.md",
        "sed -n '1,4p' -- README.md",
    ):
        assert (
            authorize_call(
                tmp_path,
                assignment,
                rules.make_call("shell", {}, kind="shell", command=command),
            )
            is None
        )
    for command in (
        "cat README.md",
        "rg -n needle README.md",
        "sed -n '1,4p' README.md",
        "pwd\ncat README.md",
        "git diff",
        "PATH=/tmp pwd",
        "cat -- README.md;pwd",
        "cat -- /tmp/out",
    ):
        assert (
            authorize_call(
                tmp_path,
                assignment,
                rules.make_call("shell", {}, kind="shell", command=command),
            ).allowed
            is False
        )


def test_worker_edit_is_exact_owned_file_and_symlink_safe(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    assignment = Assignment("worker", ("src/a.dart",), "m", "medium")
    edit = rules.make_call("edit", {}, kind="edit", file_paths=("src/a.dart",))
    assert authorize_call(tmp_path, assignment, edit) is None
    assert (
        authorize_call(
            tmp_path,
            assignment,
            rules.make_call(
                "edit", {}, kind="edit", file_paths=(str(tmp_path / "src" / "a.dart"),)
            ),
        )
        is None
    )
    multi = Assignment("worker", ("src/a.dart", "src/b.dart"), "m", "medium")
    assert authorize_call(tmp_path, multi, edit) is None
    assert (
        authorize_call(
            tmp_path,
            assignment,
            rules.make_call("edit", {}, kind="edit", file_paths=("src/b.dart",)),
        ).allowed
        is False
    )
    assert (
        authorize_call(
            tmp_path,
            assignment,
            rules.make_call(
                "edit", {}, kind="edit", file_paths=("src/a.dart", "src/b.dart")
            ),
        ).allowed
        is False
    )
    outside = tmp_path.parent / "outside-assignment"
    outside.mkdir()
    (tmp_path / "src" / "link.dart").symlink_to(outside, target_is_directory=True)
    linked = Assignment("worker", ("src/link.dart/secret.dart",), "m", "medium")
    assert (
        authorize_call(
            tmp_path,
            linked,
            rules.make_call(
                "edit", {}, kind="edit", file_paths=("src/link.dart/secret.dart",)
            ),
        ).allowed
        is False
    )
    (tmp_path / "secret.dart").write_text("secret")
    (tmp_path / "owned.md").symlink_to(tmp_path / "secret.dart")
    alias = Assignment("worker", ("owned.md",), "m", "medium")
    assert (
        authorize_call(
            tmp_path,
            alias,
            rules.make_call("edit", {}, kind="edit", file_paths=("secret.dart",)),
        ).allowed
        is False
    )
    assert (
        authorize_call(
            tmp_path,
            assignment,
            rules.make_call("run", {}, kind="shell", command="pytest"),
        ).allowed
        is False
    )


def test_decode_rejects_nul_path() -> None:
    assert isinstance(
        decode_assignment(
            {"role": "worker", "owned_paths": ["a\x00b"], "model": "m", "effort": "low"}
        ),
        Err,
    )


def test_ripgrep_reads_must_disable_user_configuration(tmp_path):
    assignment = Assignment("reviewer", (), "m", "low")
    assert (
        authorize_call(
            tmp_path,
            assignment,
            rules.make_call(
                "shell", {}, kind="shell", command="rg -n -- needle README.md"
            ),
        ).allowed
        is False
    )
    assert (
        authorize_call(
            tmp_path,
            assignment,
            rules.make_call(
                "shell",
                {},
                kind="shell",
                command="rg --no-config -n -- needle README.md",
            ),
        )
        is None
    )
