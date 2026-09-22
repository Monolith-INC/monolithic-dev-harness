from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .artifact_validator import validate_artifact
from .engine import OrchestratorEngine
from .ingest import ingest_file
from .init_scaffold import scaffold_workspace
from .mailbox import read_error_log
from .report_formatter import format_terminal_report, persist_report


def _default_skills_dir() -> Path:
    return (
        Path(__file__).resolve().parents[2] / "skills"
    )  # <plugin>/runtime/orchestrator_core → <plugin>/skills


def _project_root() -> Path:
    for key in ("CODEX_PROJECT_ROOT", "CURSOR_PROJECT_DIR", "CLAUDE_PROJECT_DIR"):
        value = os.environ.get(key, "").strip()
        if value:
            return Path(value)
    return Path.cwd()


def _state_dir(project_root: Path) -> Path:
    """`.agile-backlog-toolkit/` -- where the plugin keeps its own reports, config, and memory."""
    from .project_config import plugin_dir

    return plugin_dir(project_root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Agile Workflow deterministic orchestrator"
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("init", help="Scaffold .agentic/workflow_prompts mailbox")

    validate_p = sub.add_parser(
        "validate", help="Validate an artifact draft (rule-based critic)"
    )
    validate_p.add_argument(
        "--file", required=True, help="Path to a draft markdown file"
    )
    validate_p.add_argument(
        "--persist",
        action="store_true",
        help="Write report to .agile-backlog-toolkit/reports/",
    )
    validate_p.add_argument(
        "--hierarchy-parent-is-feature",
        choices=("true", "false"),
        help="Optional Azure hierarchy assertion for stories",
    )

    eval_p = sub.add_parser(
        "evaluate", help="Quality gate CLI (writes error.log on failure)"
    )
    eval_p.add_argument("--skill", default="validate-artifact")
    eval_p.add_argument("--file", required=True)

    compile_p = sub.add_parser("compile", help="Compile skill prompt to mailbox")
    compile_p.add_argument("--skill", required=True)
    compile_p.add_argument("--file", required=True)
    compile_p.add_argument(
        "--mode", default="novo", choices=("novo", "correcao", "atualizacao")
    )

    resume_p = sub.add_parser(
        "resume", help="Route skill: compile prompt if error.log or new work"
    )
    resume_p.add_argument("--skill", required=True)
    resume_p.add_argument("--file", required=True)

    estimate_p = sub.add_parser("estimate", help="Suggest effort hours for an artifact")
    estimate_p.add_argument("--file", help="Path to a draft markdown file")
    estimate_p.add_argument(
        "--points", type=float, help="Story points, when not reading a file"
    )

    capacity_p = sub.add_parser(
        "capacity", help="Compare sprint capacity against planned work"
    )
    capacity_p.add_argument("--iteration", default="", help="Iteration reference")
    capacity_p.add_argument(
        "--provider", default="filesystem", choices=("filesystem", "azure-devops")
    )
    capacity_p.add_argument(
        "--payloads", help="Path to JSON of pre-fetched Azure payloads"
    )
    capacity_p.add_argument("--process", help="Azure process: agile | scrum | cmmi")

    breakdown_p = sub.add_parser(
        "estimate-breakdown",
        help="Derive hours for every Task under a Story, checked against the assignee",
    )
    breakdown_p.add_argument(
        "--input", required=True, help="Path to JSON: story_id, story_points, tasks[]"
    )
    breakdown_p.add_argument(
        "--payloads", help="Path to JSON of pre-fetched Azure capacity payloads"
    )

    config_p = sub.add_parser("config", help="Show or set project configuration")
    config_p.add_argument(
        "--show", action="store_true", help="Print resolved configuration"
    )
    config_p.add_argument(
        "--set",
        dest="assignments",
        action="append",
        metavar="KEY=VALUE",
        help="Set artifacts_path, azure.org, azure.project, azure.team, or azure.process. Repeatable.",
    )
    config_p.add_argument(
        "--require-team",
        action="store_true",
        help="Treat the team as required when reporting what is missing",
    )

    sub.add_parser("mcp", help="Run MCP stdio server")

    args = parser.parse_args(argv)
    project_root = _project_root()
    skills_dir = Path(
        os.environ.get("ORCHESTRATOR_SKILLS_DIR", str(_default_skills_dir()))
    )
    state_dir = _state_dir(project_root)
    engine = OrchestratorEngine(
        skills_dir,
        project_root=project_root,
        state_dir=state_dir,
        interactive=bool(os.environ.get("ORCHESTRATOR_INTERACTIVE")),
    )

    if args.command == "init":
        scaffold_workspace(project_root)
        return 0

    if args.command == "validate":
        path = Path(args.file)
        record = ingest_file(path)
        hierarchy = None
        if args.hierarchy_parent_is_feature == "true":
            hierarchy = True
        elif args.hierarchy_parent_is_feature == "false":
            hierarchy = False
        results = validate_artifact(
            record, hierarchy_parent_is_feature=hierarchy, state_dir=state_dir
        )
        report = format_terminal_report(record, results)
        print(report)
        if args.persist:
            out = persist_report(record, report, state_dir=state_dir)
            print(f"\n[+] Report persisted: {out}")
        return 1 if any(r.result == "FAIL" for r in results) else 0

    if args.command == "evaluate":
        ok, report = engine.evaluate_file(Path(args.file), skill_name=args.skill)
        print(report)
        return 0 if ok else 1

    if args.command == "compile":
        out = engine.compile_mailbox(args.skill, file_path=args.file, mode=args.mode)
        print(f"[+] Prompt written: {out}")
        return 0

    if args.command == "resume":
        mode = "correcao" if read_error_log(project_root, args.skill) else "novo"
        out = engine.compile_mailbox(args.skill, file_path=args.file, mode=mode)
        print(f"[+] Resume mode={mode} prompt: {out}")
        return 0

    if args.command == "estimate":
        from .estimation import estimate_hours, load_config

        points = args.points
        label = f"{points} points"
        if args.file:
            record = ingest_file(Path(args.file))
            points = record.story_points
            label = record.title or args.file
        if points is None:
            print("[!] No story points found; nothing to estimate.")
            print(
                "    An unestimated item is an honest state -- supply --points to get a suggestion."
            )
            return 1

        estimate = estimate_hours(points, config=load_config(state_dir))
        if estimate is None:
            print(
                f"[!] No band covers {points} points; add one to .agile-backlog-toolkit/estimation.json."
            )
            return 1

        print(f"{label}\n{'=' * 60}")
        print(f"  {estimate.describe()}")
        print(f"  detail: {estimate.detail}")
        if estimate.is_suggestion_only:
            print(
                "\n  This is a suggestion, not a measurement. Confirm it with the team"
            )
            print("  before recording it against any work item.")
        return 0

    if args.command == "capacity":
        from .handlers import handle_plan_capacity

        payloads = {}
        if args.payloads:
            payload_path = Path(args.payloads)
            try:
                payloads = json.loads(payload_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                print(f"[!] Could not read payloads: {exc}")
                return 1

        result = handle_plan_capacity(
            {
                "iteration_ref": args.iteration,
                "provider": args.provider,
                "payloads": payloads,
                "process": args.process,
            },
            skills_dir=skills_dir,
            state_dir=state_dir,
            instructions="",
        )
        if not result.get("ok"):
            print(f"[!] {result.get('error')}")
            return 1

        print(result["report"])
        suggestions = result.get("suggestions") or []
        if suggestions:
            print("\n  Unestimated items -- suggestions requiring confirmation:")
            for suggestion in suggestions:
                print(f"    {suggestion['item_id']}: {suggestion['describe']}")
            print(
                "\n  Nothing above has been written. Confirm each figure before recording it."
            )
        return 1 if result.get("overcommitted") else 0

    if args.command == "estimate-breakdown":
        from .handlers import handle_estimate_breakdown

        try:
            payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[!] Could not read input: {exc}")
            return 1
        if args.payloads:
            try:
                payload["payloads"] = json.loads(
                    Path(args.payloads).read_text(encoding="utf-8")
                )
            except (OSError, json.JSONDecodeError) as exc:
                print(f"[!] Could not read payloads: {exc}")
                return 1

        result = handle_estimate_breakdown(
            payload, skills_dir=skills_dir, state_dir=state_dir, instructions=""
        )
        if not result.get("ok"):
            print(f"[!] {result.get('error')}")
            return 1
        if not result.get("estimated"):
            print(f"[!] Not estimated: {result.get('reason')}")
            return 1

        print(result["report"])
        if result["blocked"]:
            # Exit 2 distinguishes "cannot fit" from "failed to run".
            return 2
        print("\n  Write these to Azure (nothing has been written yet):")
        for op in result["write_ops"]:
            for field, value in op["fields"].items():
                print(f"    {op['item_id']}  {field} = {value}")
        return 0

    if args.command == "config":
        from .project_config import (
            config_path,
            load_project_config,
            save_project_config,
        )

        if args.assignments:
            config = load_project_config(project_root)
            azure_updates: dict[str, str] = {}
            artifacts_update: str | None = None
            for assignment in args.assignments:
                key, _, value = assignment.partition("=")
                key, value = key.strip().lower(), value.strip()
                if not value:
                    print(f"[!] Ignoring '{assignment}': no value given.")
                    continue
                if key in ("artifacts_path", "artifacts"):
                    artifacts_update = value
                elif key.startswith("azure."):
                    field = key.split(".", 1)[1]
                    if field in ("org", "project", "team", "process"):
                        azure_updates[field] = value
                    else:
                        print(
                            f"[!] Unknown azure key '{field}'; expected org, project, team or process."
                        )
                else:
                    print(
                        f"[!] Unknown key '{key}'; expected artifacts_path or azure.<field>."
                    )

            config = config.with_azure(**azure_updates).with_artifacts_path(
                artifacts_update
            )
            written = save_project_config(project_root, config)
            if written is None:
                print(f"[!] Could not write {config_path(project_root)}")
                return 1
            print(f"[+] Saved: {written}")

        config = load_project_config(project_root)
        artifacts = config.resolve_artifacts_dir(project_root)
        print("Project configuration")
        print("=" * 60)
        print(
            f"  artifacts_path: {config.artifacts_path or '<unset — ask the user, never assume>'}"
        )
        if artifacts:
            print(
                f"                  → {artifacts}{'' if artifacts.is_dir() else '  (does not exist yet)'}"
            )
        print(f"  azure.org     : {config.azure.org or '<unset>'}")
        print(f"  azure.project : {config.azure.project or '<unset>'}")
        print(f"  azure.team    : {config.azure.team or '<unset>'}")
        print(f"  azure.process : {config.azure.process or '<unset (assumed agile)>'}")
        print(f"  plugin state  : {_state_dir(project_root)}")
        print(
            f"  sources       : {', '.join(config.sources) or '<none — nothing configured>'}"
        )

        missing = config.missing(require_team=args.require_team)
        if missing:
            print(f"\n  Missing: {', '.join(missing)}")
            print(
                f"  Set with: bin/agile-backlog-toolkit config --set azure.{missing[0]}=<value>"
            )
            return 1
        return 0

    if args.command == "mcp":
        from . import mcp_server

        mcp_server.main()
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
