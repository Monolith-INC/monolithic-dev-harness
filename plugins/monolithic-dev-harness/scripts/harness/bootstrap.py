#!/usr/bin/env python3
"""Opt a repository into the harness: write its policy and the per-component configuration.

    bootstrap.py --repo <dir> --policy-from <policy.json> [--branch-template '{category}/{key}-{slug}']
                 [--discover] [--force]

Everything goes under `.harness/` (see `layout.py`). Writes, once:
  .harness/policy.json            the harness rules (copied from --policy-from; never replaced)
  .git/info/exclude               ignores .harness/state/ (local to this clone; the shared
                                  .gitignore is never edited)
  .harness/integrations.json      delivery: Azure Boards tracker + Azure Repos SCM
                                  (repaired in place when it exists; --force rewrites it)
  .harness/backlog/config.json    backlog: org / project / team

A repository set up by an earlier version has its old folders moved into `.harness/` first.
Review configuration (.harness/review/sources.json) is interactive: run the `review-setup` skill
afterwards. Hooks and MCP servers come from the plugin itself; nothing is wired into the
repository's host settings.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PLUGIN_ROOT))
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))

from harness.config import POLICY_RELATIVE_PATH, PolicyError, load_policy  # noqa: E402


def _ensure_local_exclude(repo: Path) -> bool:
    """Ignore `.harness/state/` in this clone only: git's own exclude file, not the tracked `.gitignore`."""
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--git-path", "info/exclude"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return False
    path = Path(result.stdout.strip())
    path = path if path.is_absolute() else repo / path
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    if ".harness/state/" in lines:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join([*lines, ".harness/state/"]) + "\n", encoding="utf-8")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--repo", required=True)
    parser.add_argument("--policy-from", required=True)
    parser.add_argument("--branch-template", default="{category}/{key}-{slug}")
    parser.add_argument(
        "--discover",
        action="store_true",
        help="query Azure DevOps for capabilities (starts OAuth)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="rewrite .harness/integrations.json from scratch (the policy is never replaced)",
    )
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    if not (repo / ".git").exists():
        print(f"{repo} is not a git repository root", file=sys.stderr)
        return 2

    policy_path = repo / POLICY_RELATIVE_PATH
    if policy_path.exists():
        # The policy is human-owned: an existing one is kept even with --force.
        print(f"kept existing {POLICY_RELATIVE_PATH}")
    else:
        policy_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(args.policy_from, policy_path)
        print(f"wrote {POLICY_RELATIVE_PATH}")
    try:
        policy = load_policy(repo)
    except PolicyError as exc:
        print(f"policy is invalid: {exc}", file=sys.stderr)
        return 2
    if not policy["azure"]["organization"]:
        org = os.environ.get("AZURE_DEVOPS_ORG", "").strip()
        if not org:
            print(
                "no Azure DevOps organization: set azure.organization in the policy or AZURE_DEVOPS_ORG",
                file=sys.stderr,
            )
            return 2
        raw = json.loads(policy_path.read_text(encoding="utf-8"))
        raw.setdefault("azure", {})["organization"] = org
        policy_path.write_text(
            json.dumps(raw, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        policy["azure"]["organization"] = org
        print(
            f"recorded organization {org} (from AZURE_DEVOPS_ORG) in {POLICY_RELATIVE_PATH}"
        )
    if _ensure_local_exclude(repo):
        print("ignored .harness/state/ in .git/info/exclude (this clone only)")
    from harness.layout import BACKLOG, INTEGRATIONS, migrate

    for note in migrate(repo):
        print(note)

    azure = policy["azure"]
    integrations = repo / INTEGRATIONS
    if integrations.exists() and not args.force:
        from harness.integrations_setup import repair_integrations

        repairs = repair_integrations(integrations, azure)
        for repair in repairs:
            print(f"repaired {INTEGRATIONS}: {repair}")
        if not repairs:
            print(f"kept existing {INTEGRATIONS}")
    else:
        from harness.integrations_setup import configure_integrations

        configure_integrations(
            repo,
            tracker="azure_devops",
            scm="azure_repos",
            branch_template=args.branch_template,
            discover=args.discover,
            runtime_dir=PLUGIN_ROOT,
            project=str(azure.get("project") or ""),
            repository=str(azure.get("repository") or ""),
        )
        print(f"wrote {INTEGRATIONS} (azure_devops + azure_repos)")

    backlog = policy.get("backlog", {})
    pairs = {
        "azure.org": azure["organization"],
        "azure.project": azure["project"],
        "azure.team": azure["team"],
        "artifacts_path": backlog.get("artifacts_path", ""),
    }
    missing = [key for key, value in pairs.items() if not value]
    if missing:
        print(
            f"policy is missing values the backlog stage needs: {', '.join(missing)}",
            file=sys.stderr,
        )
        return 2
    cli = PLUGIN_ROOT / "bin" / "agile-backlog-toolkit"
    set_args = [
        arg for key, value in pairs.items() for arg in ("--set", f"{key}={value}")
    ]
    subprocess.run(
        [str(cli), "config", *set_args], cwd=repo, check=True, stdout=subprocess.DEVNULL
    )
    backlog_config = repo / BACKLOG / "config.json"
    data = json.loads(backlog_config.read_text(encoding="utf-8"))
    data["provider_mode"] = "azure"
    backlog_config.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"configured {BACKLOG}/config.json (provider_mode azure)")

    print(
        json.dumps(
            {"next": ["run the review-setup skill", "restart the agent session"]}
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
