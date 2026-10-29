"""Command entry for the existing source chooser and its standard decision delivery."""

import json
from dataclasses import asdict
from pathlib import Path

from core.result import Err, Ok, err, fmap
from harness import work_sessions
from harness.elicitation import SelectionState
from harness.elicitation_store import (
    catalog,
    load,
    present_selection,
    record_hardening,
    save,
    stage,
    stage_result,
)


def command(args) -> int:
    from harness import artifact_review, cli, cli_common

    repo = Path(args.repo).resolve()
    scope = args.session_id or work_sessions.current(repo) or ""
    match work_sessions.require_active(repo, scope):
        case Err() as failed:
            return cli_common.print_result(failed)
        case Ok():
            pass
    match args.operation:
        case "status":
            return cli_common.print_result(
                fmap(
                    load(repo, scope),
                    lambda value: json.dumps(asdict(value)),
                )
            )
        case "start":
            match load(repo, scope):
                case Ok(current):
                    return cli_common.print_result(Ok(json.dumps(asdict(current))))
                case Err():
                    match tuple(args.method_id or ()):
                        case methods if methods and all(
                            method in catalog() for method in methods
                        ):
                            return cli_common.print_result(
                                fmap(
                                    save(
                                        repo,
                                        scope,
                                        SelectionState(
                                            pool=methods,
                                            mode="recommendations"
                                            if args.recommendations
                                            else "shortlist",
                                        ),
                                    ),
                                    lambda value: json.dumps(asdict(value)),
                                )
                            )
                        case _:
                            return cli_common.print_result(
                                err(
                                    "invalid_method_selection",
                                    "Supply canonical --method-id values from the source catalog; this proposes choices and selects nothing.",
                                )
                            )
        case "hardening":
            return cli_common.print_result(
                fmap(
                    record_hardening(
                        repo,
                        scope,
                        args.review_kind or "",
                        args.artifact or "",
                        args.triage or "",
                        args.approach or "",
                    ),
                    lambda value: json.dumps(value),
                )
            )
        case "result":
            match artifact_review.shown(repo, scope, [args.artifact or ""]):
                case Err() as failed:
                    return cli_common.print_result(failed)
                case Ok():
                    prepared = stage_result(repo, scope, args.artifact or "")
        case "present":
            prepared = present_selection(repo, scope)
        case "reopen":
            prepared = stage(
                repo,
                scope,
                "Reopen method selection while keeping the saved choices?",
                {
                    "Reopen selection": {"action": "reopen"},
                    "Keep current selection": {"action": "direction"},
                },
            )
        case _:
            return 2
    match prepared:
        case Err() as failed:
            return cli_common.print_result(failed)
        case Ok(pending):
            return cli.main(
                [
                    "decision",
                    "present",
                    "--repo",
                    str(repo),
                    "--session-id",
                    scope,
                    "--host",
                    args.host,
                    "--question",
                    pending["question"],
                    *(
                        part
                        for option in pending["options"]
                        for part in ("--option", option)
                    ),
                    *(("--allow-free-text",) if args.operation == "present" else ()),
                    *(
                        ("--artifact", pending["artifact"])
                        if pending["artifact"]
                        else ()
                    ),
                ]
            )
