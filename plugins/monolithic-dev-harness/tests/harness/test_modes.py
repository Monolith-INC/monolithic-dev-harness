"""A mode folder loads only when its manifest, files, operations and skills all check out."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from core.result import Err, Ok
from harness import modes

REQUIRED_FIELDS = (
    "name",
    "goal",
    "expectations",
    "entry_skill",
    "skills",
    "operations",
    "hooks",
    "knowledge",
    "exit",
)
FIXTURE_SKILL = "harness"
FIXTURE_OPERATION = "scm_get_pull_request"

VALID_FIELDS = {
    "name": "fixture",
    "goal": "Exercise the loader.",
    "expectations": ["Each refusal is named."],
    "entry_skill": FIXTURE_SKILL,
    "skills": [{"name": FIXTURE_SKILL, "when": "always"}],
    "operations": [FIXTURE_OPERATION],
    "hooks": ["orient", "operations"],
    "knowledge": "first",
    "exit": ["The loader accepts the fixture."],
}


def render(fields: dict) -> str:
    """The manifest as TOML: top-level keys first, then the `[[skills]]` tables."""
    top = [
        f"{key} = {json.dumps(value)}"
        for key, value in fields.items()
        if key != "skills"
    ]
    tables = [
        f"[[skills]]\nname = {json.dumps(skill['name'])}\nwhen = {json.dumps(skill['when'])}"
        for skill in fields.get("skills", [])
    ]
    return "\n".join(top + tables) + "\n"


def write_mode(
    root: Path,
    name: str = "fixture",
    fields: dict | None = None,
    files: tuple[str, ...] = ("workflow.md", "rules.md"),
) -> Path:
    folder = root / name
    folder.mkdir(parents=True)
    if fields is not None:
        (folder / "mode.toml").write_text(render(fields), encoding="utf-8")
    for filename in files:
        (folder / filename).write_text("# fixture\n", encoding="utf-8")
    return folder


def with_fields(**changes) -> dict:
    return {**VALID_FIELDS, **changes}


def refusal(result) -> tuple[str, str]:
    match result:
        case Err(failure):
            return failure.code, failure.message
        case Ok(value):
            raise AssertionError(f"expected a refusal, loaded {value!r}")


def test_a_valid_manifest_loads_with_its_fields(tmp_path: Path) -> None:
    folder = write_mode(tmp_path, fields=VALID_FIELDS)

    match modes.load("fixture", root=tmp_path):
        case Ok(mode):
            assert mode.name == "fixture"
            assert mode.goal == "Exercise the loader."
            assert mode.expectations == ("Each refusal is named.",)
            assert mode.entry_skill == FIXTURE_SKILL
            assert mode.skills == (modes.SkillRef(FIXTURE_SKILL, "always"),)
            assert mode.operations == (FIXTURE_OPERATION,)
            assert mode.hooks == ("orient", "operations")
            assert mode.knowledge == "first"
            assert mode.exit == ("The loader accepts the fixture.",)
            assert mode.root == folder
        case Err(failure):
            raise AssertionError(failure.message)


@pytest.mark.parametrize("field", REQUIRED_FIELDS)
def test_a_missing_field_is_refused_and_named(tmp_path: Path, field: str) -> None:
    fields = {key: value for key, value in VALID_FIELDS.items() if key != field}
    write_mode(tmp_path, fields=fields)

    code, message = refusal(modes.load("fixture", root=tmp_path))

    assert code == "invalid_mode"
    assert field in message


def test_an_unknown_knowledge_value_is_refused(tmp_path: Path) -> None:
    write_mode(tmp_path, fields=with_fields(knowledge="sometimes"))

    code, message = refusal(modes.load("fixture", root=tmp_path))

    assert code == "invalid_mode"
    assert "knowledge" in message


def test_an_unknown_hook_id_is_refused_and_named(tmp_path: Path) -> None:
    write_mode(tmp_path, fields=with_fields(hooks=["orient", "telepathy"]))

    code, message = refusal(modes.load("fixture", root=tmp_path))

    assert code == "invalid_mode"
    assert "hooks" in message
    assert "telepathy" in message


def test_an_operation_that_is_not_a_gateway_tool_is_refused_and_named(
    tmp_path: Path,
) -> None:
    write_mode(tmp_path, fields=with_fields(operations=["not_a_gateway_tool"]))

    code, message = refusal(modes.load("fixture", root=tmp_path))

    assert code == "invalid_mode"
    assert "operations" in message
    assert "not_a_gateway_tool" in message


def test_a_skill_missing_from_the_plugin_is_refused_and_named(tmp_path: Path) -> None:
    write_mode(
        tmp_path,
        fields=with_fields(skills=[{"name": "no-such-skill", "when": "always"}]),
    )

    code, message = refusal(modes.load("fixture", root=tmp_path))

    assert code == "invalid_mode"
    assert "skills" in message
    assert "no-such-skill" in message


def test_an_entry_skill_missing_from_the_plugin_is_refused_and_named(
    tmp_path: Path,
) -> None:
    write_mode(tmp_path, fields=with_fields(entry_skill="no-such-skill"))

    code, message = refusal(modes.load("fixture", root=tmp_path))

    assert code == "invalid_mode"
    assert "entry_skill" in message
    assert "no-such-skill" in message


@pytest.mark.parametrize("missing", ["workflow.md", "rules.md"])
def test_a_mode_without_its_procedure_or_rules_is_refused(
    tmp_path: Path, missing: str
) -> None:
    present = tuple(name for name in ("workflow.md", "rules.md") if name != missing)
    write_mode(tmp_path, fields=VALID_FIELDS, files=present)

    code, message = refusal(modes.load("fixture", root=tmp_path))

    assert code == "invalid_mode"
    assert missing in message


def test_a_manifest_named_differently_from_its_folder_is_refused(
    tmp_path: Path,
) -> None:
    write_mode(tmp_path, name="alias", fields=with_fields(name="realname"))

    code, message = refusal(modes.load("alias", root=tmp_path))

    assert code == "invalid_mode"
    assert "folder name" in message
    assert "alias" in message
    assert "realname" in message


@pytest.mark.parametrize(
    "unsafe",
    ["", ".", "..", "a/b", "a\\b", "/etc"],
    ids=["empty", "dot", "dotdot", "slash", "backslash", "absolute"],
)
def test_a_mode_name_that_is_not_one_plain_folder_name_is_refused(
    tmp_path: Path, unsafe: str
) -> None:
    code, message = refusal(modes.load(unsafe, root=tmp_path))

    assert code == "invalid_mode"
    assert "folder name" in message


def test_a_mode_cannot_be_loaded_from_outside_the_modes_folder(tmp_path: Path) -> None:
    root = tmp_path / "modes"
    root.mkdir()
    # The manifest agrees with the name that points at it, so only the name can refuse it.
    write_mode(tmp_path, name="outside", fields=with_fields(name="../outside"))

    code, message = refusal(modes.load("../outside", root=root))

    assert code == "invalid_mode"
    assert "folder name" in message


def test_a_folder_without_a_manifest_is_refused(tmp_path: Path) -> None:
    write_mode(tmp_path, fields=None)

    code, message = refusal(modes.load("fixture", root=tmp_path))

    assert code == "invalid_mode"
    assert "mode.toml" in message


def test_available_lists_mode_folders_in_order(tmp_path: Path) -> None:
    write_mode(tmp_path, name="beta", fields=VALID_FIELDS)
    write_mode(tmp_path, name="alpha", fields=VALID_FIELDS)

    assert modes.available(tmp_path) == ("alpha", "beta")


def test_available_is_empty_before_any_mode_exists(tmp_path: Path) -> None:
    assert modes.available(tmp_path / "modes") == ()


# the discovery mode that ships with the plugin

DISCOVERY_OPERATIONS = (
    "tracker_describe",
    "tracker_preflight",
    "tracker_search_work_items",
    "tracker_get_work_item",
    "tracker_create_work_item",
    "tracker_list_artifacts",
    "tracker_publish_artifact",
    "tracker_revise_artifact",
)


def discovery() -> modes.Mode:
    match modes.load("discovery"):
        case Ok(mode):
            return mode
        case Err(failure):
            raise AssertionError(failure.message)


def test_the_discovery_mode_loads() -> None:
    mode = discovery()

    assert mode.name == "discovery"
    assert mode.entry_skill == "discovery"
    assert mode.operations == DISCOVERY_OPERATIONS
    assert mode.hooks == ("orient", "operations")
    assert mode.knowledge == "first"
    assert mode.exit == ("The PRD is approved.",)
    assert "discovery" in modes.available()


def test_the_discovery_rules_are_imperatives_only() -> None:
    lines = (discovery().root / "rules.md").read_text(encoding="utf-8").splitlines()

    assert lines and all(re.match(r"[A-Z]{3,}\b", line) for line in lines)


def test_the_discovery_skill_and_procedure_call_only_the_gateway_tools_the_mode_lists() -> (
    None
):
    mode = discovery()
    skill = modes.SKILLS_ROOT / mode.entry_skill / "SKILL.md"

    for path in (skill, mode.root / "workflow.md"):
        named = set(re.findall(r"\b(?:tracker|scm)_[a-z_]+\b", path.read_text("utf-8")))
        assert named, path
        assert named <= set(mode.operations), (path.name, named - set(mode.operations))


def section(text: str, heading: str) -> str:
    """The body of the section whose heading starts with `heading`, up to the next heading."""
    start = text.index(heading)
    following = re.search(r"\n#{2,3} ", text[start + len(heading) :])
    return (
        text[start : start + len(heading) + following.start()]
        if following
        else text[start:]
    )


def test_the_discovery_skill_asks_the_gate_before_it_creates_root_or_publishes() -> (
    None
):
    text = (modes.SKILLS_ROOT / "discovery" / "SKILL.md").read_text("utf-8")
    writing = section(text, "## Writing a document")
    gates = section(text, "## Gates")

    writes = [
        bullet
        for bullet in writing.split("\n- ")
        if "tracker_create_work_item" in bullet or "tracker_publish_artifact" in bullet
    ]
    assert writes
    assert all("approve-document" in bullet for bullet in writes), writes
    assert (
        gates.index("decision present")
        < gates.index("tracker_create_work_item")
        < gates.index("tracker_publish_artifact")
    )
    assert "no `description`" in gates


def test_the_discovery_procedure_tells_the_same_order_as_the_skill() -> None:
    text = (discovery().root / "workflow.md").read_text("utf-8")

    for step in ("### Step 1", "### Step 2"):
        assert "Publish" not in section(text, step), step
    for gate in ("### Gate G1", "### Gate G2"):
        assert "once" in section(text, gate), gate
        assert "Approved" in section(text, gate), gate
    first = section(text, "### Gate G1")
    assert (
        first.index("approve-document")
        < first.index("tracker_create_work_item")
        < first.index("tracker_publish_artifact")
    )
