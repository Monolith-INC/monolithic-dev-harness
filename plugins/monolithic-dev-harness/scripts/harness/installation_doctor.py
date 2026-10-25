"""Installation census and explicit, fingerprint-bound repair selections."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from core.result import Err, Ok
from harness.installation_inventory import findings, scan
from harness.installation_lifecycle import (
    _context,
    _serialize,
    apply_repairs,
    discover_projects,
)


def identifier(repair) -> str:
    return hashlib.sha256(
        json.dumps(_serialize(repair), sort_keys=True).encode()
    ).hexdigest()[:16]


def preview(projects: tuple[Path, ...], scope: str = "all") -> dict:
    match discover_projects(projects):
        case Ok(roots):
            return _preview(roots, scope)
        case Err(failure):
            return {"error": failure.to_dict()}


def _preview(projects: tuple[Path, ...], scope: str) -> dict:
    inventory = scan(_context(projects))
    issues = findings(inventory)
    repairs = tuple(
        {
            identifier(repair): repair
            for issue in issues
            for repair in issue.repairs
            if (scope == "all" or repair.component.scope == scope)
        }.values()
    )
    return {
        "coverage": "Current user profiles, host-known projects and explicit project roots. Unknown checkouts require --project. File presence does not prove active runtime registration.",
        "projects": [str(project) for project in projects],
        "inventory": _serialize(inventory),
        "findings": _serialize(issues),
        "repairs": [
            {"id": identifier(repair), **_serialize(repair)} for repair in repairs
        ],
        "instructions": "Select individual repair IDs to preview. Pass the returned selection digest with --apply-repairs to apply. Keep one installation for each required host effect.",
    }


def run(args) -> int:
    projects = tuple(
        dict.fromkeys(
            Path(path).expanduser().resolve()
            for path in (getattr(args, "project", None) or [args.repo])
        )
    )
    match discover_projects(projects):
        case Ok(roots):
            return _run(args, roots)
        case Err(failure):
            print(json.dumps({"error": failure.to_dict()}))
            return 1


def _run(args, projects: tuple[Path, ...]) -> int:
    context = _context(projects)
    inventory = scan(context)
    issues = findings(inventory)
    available = {
        identifier(repair): repair
        for issue in issues
        for repair in issue.repairs
        if args.scope == "all" or repair.component.scope == args.scope
    }
    requested = tuple(dict.fromkeys(args.repair_id))
    match tuple(key for key in requested if key not in available):
        case ():
            selected = tuple(available[key] for key in requested)
            digest = hashlib.sha256(
                json.dumps(_serialize(selected), sort_keys=True).encode()
            ).hexdigest()
            match args.apply_repairs:
                case None:
                    output = {
                        **preview(projects, args.scope),
                        "selection": list(requested),
                        "selection_digest": digest if requested else None,
                    }
                    print(json.dumps(output, indent=2))
                    return 1 if inventory.errors or issues else 0
                case value if requested and value == digest:
                    match apply_repairs(selected, context):
                        case Ok(paths):
                            print(
                                json.dumps(
                                    {
                                        "repaired": _serialize(paths),
                                        "after": preview(projects, args.scope),
                                    },
                                    indent=2,
                                )
                            )
                            after = scan(context)
                            return 1 if after.errors or findings(after) else 0
                        case Err(failure):
                            print(json.dumps({"error": failure.to_dict()}))
                            return 1
                case _:
                    print(
                        json.dumps(
                            {
                                "error": "Select at least one repair ID and use its current selection_digest. Rescan after any change."
                            }
                        )
                    )
                    return 2
        case missing:
            print(
                json.dumps(
                    {"error": "Unknown or stale repair IDs", "ids": list(missing)}
                )
            )
            return 2
