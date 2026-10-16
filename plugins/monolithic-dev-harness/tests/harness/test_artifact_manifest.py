"""Prepared documents carry explicit read triggers and verified content hashes."""

import hashlib
import json
from pathlib import Path

from core.result import Err, Ok
from harness import artifact_manifest


def entry(path: str) -> str:
    return json.dumps(
        {
            "path": path,
            "purpose": "Acceptance contract",
            "read_when": "Before changing task behavior",
            "owner": "bmad-spec",
        }
    )


def test_manifest_hashes_the_actual_document_and_saves_atomically(
    tmp_path: Path,
) -> None:
    (tmp_path / "spec.md").write_text("contract")
    saved = artifact_manifest.save(tmp_path, "docs/manifest.md", (entry("spec.md"),))
    assert isinstance(saved, Ok)
    assert hashlib.sha256(b"contract").hexdigest() in saved.value
    assert "Before changing task behavior" in saved.value
    assert (tmp_path / "docs/manifest.md").read_text() == saved.value
    assert tuple((tmp_path / "docs").iterdir()) == (tmp_path / "docs/manifest.md",)


def test_manifest_refuses_missing_metadata_or_escaping_paths(tmp_path: Path) -> None:
    assert isinstance(artifact_manifest.render(tmp_path, ("{}",)), Err)
    assert isinstance(
        artifact_manifest.render(tmp_path, (entry("../outside.md"),)), Err
    )
    assert isinstance(
        artifact_manifest.save(tmp_path, "../manifest.md", (entry("spec.md"),)), Err
    )
    assert isinstance(artifact_manifest.render(tmp_path, ()), Err)
