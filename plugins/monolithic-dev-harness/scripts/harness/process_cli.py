"""Read-only command acknowledgment for adapter-applied process operations."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from core.result import Ok, Result, bind, err, fmap
from harness import process_bus
from harness.cli_common import print_result, resolve_repo
from harness.process_messages import Context, ProcessStatus
from host_adapters import process_channel


def add_parser(sub: argparse._SubParsersAction) -> argparse.ArgumentParser:
    match sub.add_parser(
        "process",
        help="list subagents, inspect process state or request cancellation through the adapter",
    ):
        case parser:
            parser.add_argument(
                "operation", choices=("list", "status", "cancel", "report")
            )
            parser.add_argument("process_id", nargs="?")
            parser.add_argument("--repo", default=".")
            parser.add_argument("--session-id")
            parser.add_argument(
                "--status", choices=tuple(value.value for value in ProcessStatus)
            )
            parser.add_argument(
                "--host",
                default=process_channel.default_host(),
            )
            return parser


def run(args: argparse.Namespace) -> int:
    return print_result(
        bind(
            process_channel.cli_context(
                args.host,
                resolve_repo(args.repo),
            ),
            lambda context: _run(args, context),
        )
    )


def _run(args: argparse.Namespace, context: Context) -> Result[str]:
    match args.session_id:
        case str() as scope if scope != context.work_session_id:
            return err(
                "process_scope_mismatch", "the command names another work session"
            )
        case _:
            return fmap(
                _query(args, context),
                lambda payload: json.dumps(payload, sort_keys=True),
            )


def _query(args: argparse.Namespace, context: Context) -> Result[dict]:
    match args.operation, args.process_id:
        case "list", None:
            return fmap(
                process_bus.list_records(resolve_repo(args.repo), context),
                lambda records: {"processes": [asdict(record) for record in records]},
            )
        case "status" | "cancel" | "report", str() as pid:
            return bind(
                process_bus.get_record(resolve_repo(args.repo), context, pid),
                lambda record: _ack(args.operation, record, args.status),
            )
        case _:
            return err(
                "invalid_process_command",
                "status/cancel require one process identifier; list takes none",
            )


def _ack(
    operation: str, record: process_bus.ProcessRecord, reported: str | None = None
) -> Result[dict]:
    match operation, record.revoked:
        case "cancel", False:
            return err(
                "process_request_not_observed",
                "the adapter has not applied this cancellation; run the command through the main agent's authenticated host tool",
            )
        case "report", _ if not reported or record.reported_status != reported:
            return err(
                "process_request_not_observed",
                "the adapter has not applied this process report",
            )
        case _:
            return Ok(
                {
                    "process": asdict(record),
                    "permission_revoked": record.revoked,
                    "runtime_stopped": record.runtime_status
                    in ("completed", "failed", "interrupted"),
                }
            )
