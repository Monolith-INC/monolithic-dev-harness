"""BMad runs from what the plugin ships: no template left unrendered, no `uv`, no dangling path."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

from harness import bmad

PLUGIN = Path(__file__).resolve().parents[2]
SKILLS = PLUGIN / "skills"
BMAD_SKILLS = sorted(
    path
    for path in SKILLS.iterdir()
    if path.name.startswith(("bmad-", "bmod-")) and path.is_dir()
)
SCRIPTS = PLUGIN / "vendor" / "bmad" / "skills"
# Where `_bmad/<folder>/<script>` comes from once setup has installed it.
INSTALLED = {
    "scripts": SCRIPTS / "bmad" / "scripts",
    "method/scripts": SCRIPTS / "bmad-ticket" / "scripts",
}
SKILL_PATH = re.compile(r"\{skill-root\}/([A-Za-z0-9_./-]+)")
PROJECT_SCRIPT = re.compile(r"\{project-root\}/_bmad/([a-z/]+)/([a-z_]+\.py)")


def shipped(skill: Path) -> list[Path]:
    return [path for path in skill.rglob("*.md") if "tests" not in path.parts]


def test_the_bmad_skills_ship() -> None:
    names = {path.name for path in BMAD_SKILLS}
    assert {"bmad-build", "bmad-spec", "bmad-architecture", "bmod-method"} <= names


@pytest.mark.parametrize(
    "skill",
    [path for path in BMAD_SKILLS if path.name != "bmad-build"],
    ids=lambda path: path.name,
)
def test_other_shipped_files_need_no_renderer_and_no_uv(skill: Path) -> None:
    for path in shipped(skill):
        text = path.read_text(encoding="utf-8")
        for marker in ("{{", "{%", "uv run", "_bmad/render", "/tmp/"):
            assert marker not in text, f"{path.relative_to(PLUGIN)} contains {marker!r}"


@pytest.mark.parametrize("skill", BMAD_SKILLS, ids=lambda path: path.name)
def test_every_skill_root_path_exists(skill: Path) -> None:
    for path in shipped(skill):
        for target in SKILL_PATH.findall(path.read_text(encoding="utf-8")):
            assert (skill / target.rstrip(".")).exists(), (
                f"{path.relative_to(PLUGIN)} names {{skill-root}}/{target}"
            )


@pytest.mark.parametrize("skill", BMAD_SKILLS, ids=lambda path: path.name)
def test_every_project_script_is_one_setup_installs(skill: Path) -> None:
    for path in shipped(skill):
        for folder, script in PROJECT_SCRIPT.findall(path.read_text(encoding="utf-8")):
            assert (INSTALLED[folder] / script).is_file(), (
                f"{path.relative_to(PLUGIN)} runs _bmad/{folder}/{script}"
            )


def test_stage_zero_routes_to_bmad_build() -> None:
    harness = (SKILLS / "harness" / "SKILL.md").read_text(encoding="utf-8")
    assert "../../references/harness-stage-guide.md" in harness
    guide = (PLUGIN / "references/harness-stage-guide.md").read_text(encoding="utf-8")
    stage_zero = guide[guide.index("## Stage 0") : guide.index("## Stage 1")]
    assert "invoke `bmad-build`" in stage_zero
    assert not (SKILLS / "harness" / "references" / "technical-discovery.md").exists()


# --- the project runtime ---------------------------------------------------------------------


def test_bootstrap_setup_creates_the_runtime_and_points_output(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    first = bmad.prepare(tmp_path, "docs/planning").value
    assert first["output"] == "artifacts_path"
    assert bmad.ready(tmp_path)
    for folder, source in INSTALLED.items():
        for script in (
            ("resolve_config.py", "memlog.py")
            if folder == "scripts"
            else ("tickets.py",)
        ):
            assert (tmp_path / "_bmad" / folder / script).is_file()
            assert (source / script).is_file()
    team = tmp_path / "_bmad" / "custom" / "config.toml"
    assert 'output_folder = "{project-root}/docs/planning"' in team.read_text()

    team.write_text('[core]\noutput_folder = "{project-root}/elsewhere"\n')
    assert bmad.prepare(tmp_path, "docs/planning").value["output"] == "unchanged"
    assert "elsewhere" in team.read_text()


def test_without_artifacts_path_bmad_keeps_its_own_folder(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    assert bmad.prepare(tmp_path, "").value["output"] == "unchanged"
    assert not (tmp_path / "_bmad" / "custom" / "config.toml").exists()


@pytest.mark.parametrize("skill", BMAD_SKILLS, ids=lambda path: path.name)
def test_a_prepared_project_asks_no_setup_questions(
    tmp_path: Path, skill: Path
) -> None:
    if not (skill / "customize.toml").is_file():
        pytest.skip("no customization to resolve")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    assert isinstance(bmad.prepare(tmp_path, "docs/planning").value, dict)
    resolved = subprocess.run(
        [
            sys.executable,
            str(tmp_path / "_bmad" / "scripts" / "resolve_customization.py"),
            "--skill",
            str(skill),
            "--project-root",
            str(tmp_path),
            "--key",
            "workflow",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert resolved.returncode == 0, resolved.stderr
    assert "setup:" not in resolved.stdout + resolved.stderr
