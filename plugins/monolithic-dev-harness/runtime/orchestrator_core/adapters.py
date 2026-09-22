from __future__ import annotations

from pathlib import Path

from .artifact_validator import critiques_from_results
from .ingest import ArtifactRecord
from .reflection import ReflectionDecision


def build_skill_prompt(
    *,
    skill_name: str,
    skill_instructions: str,
    mode: str,
    record: ArtifactRecord | None = None,
    file_path: str | None = None,
    reflection: ReflectionDecision | None = None,
    error_log: str | None = None,
    mistakes: list | None = None,
) -> str:
    lines: list[str] = [
        "<system_instructions>",
        skill_instructions.strip(),
        "</system_instructions>",
        "",
        "<execution_context>",
        f"<skill>{skill_name}</skill>",
        f"<mode>{mode}</mode>",
    ]
    if file_path:
        lines.append(f"<artifact_path>{file_path}</artifact_path>")
    if record:
        lines.append(f"<artifact_type>{record.type}</artifact_type>")
        lines.append(f"<artifact_title>{record.title}</artifact_title>")
        lines.append(f"<artifact_source>{record.source}</artifact_source>")
    if error_log:
        lines.append("<quality_gate_errors>")
        lines.append(error_log.strip())
        lines.append("</quality_gate_errors>")
    if reflection and reflection.critiques:
        lines.append("<reflection>")
        lines.append("Previous attempts failed. Address every critique:")
        for index, critique in enumerate(reflection.critiques):
            lines.append(f'<critique index="{index}">{critique}</critique>')
        lines.append("</reflection>")
    if mistakes:
        lines.append("<mistakes_repo>")
        for item in mistakes[-10:]:
            lines.append(f"- {item.get('flaw', '')}")
        lines.append("</mistakes_repo>")
    if record and mode == "correcao":
        lines.append("<failed_artifact>")
        lines.append(record.raw or record.body)
        lines.append("</failed_artifact>")
    lines.append("</execution_context>")
    return "\n".join(lines) + "\n"


def critiques_to_error_log(critiques: list[str]) -> str:
    if not critiques:
        return ""
    return "Quality Gate Failed:\n" + "\n".join(critiques)
