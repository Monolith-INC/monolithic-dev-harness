"""The hook path cannot import code that starts a process, reaches the network or walks the project.

A hook may only read a small, fixed set of local records. This test follows every import
statically (also those inside functions, relative ones resolved) from the two hook entry points,
`harness/hook.py` and `hook_runtime.py`, with the same search path the hook process builds
(the plugin root, then `scripts/`). Only local modules are followed; the standard library and
third-party modules are leaves.

`STILL_TO_REMOVE` lists today's offenders as `(importing module, forbidden target)`. The later
tasks that cut the hook path off from the slow code (T3 to T10) remove their entries, and the list
must be empty at the end. A new offender fails the test, and so does an entry that no longer
offends: the list only shrinks and stays exact.
"""

from __future__ import annotations

import ast
from functools import reduce
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = PLUGIN_ROOT / "scripts"
SEARCH_PATH = (PLUGIN_ROOT, SCRIPTS)
ENTRY_POINTS = ("harness.hook", "hook_runtime")

FORBIDDEN_STDLIB = frozenset({"subprocess", "socket", "urllib", "http", "threading"})
REGISTRY = "integrations.registry"
PROJECT_WALK_MODULE = "harness.code_content"
PROJECT_WALK = "code_content.files"

# Sorted, one per line. Emptied by T3 to T10.
STILL_TO_REMOVE: frozenset[tuple[str, str]] = frozenset(
    {
        ("harness.adoption", "code_content.files"),
        ("harness.adoption", "integrations.registry"),
        ("harness.bmad", "subprocess"),
        ("harness.decisions", "code_content.files"),
        ("harness.documents", "integrations.registry"),
        ("harness.gitstate", "subprocess"),
        ("harness.hook", "code_content.files"),
        ("harness.hook", "integrations.registry"),
        ("harness.hook_budget", "threading"),
        ("harness.installation_files", "subprocess"),
        ("harness.mode_hooks", "threading"),
        ("harness.route_facts", "integrations.registry"),
        ("harness.routing", "integrations.registry"),
        ("harness.rules", "code_content.files"),
        ("harness.setup", "integrations.registry"),
        ("harness.setup", "subprocess"),
        ("harness.tracker_policy", "integrations.registry"),
        ("harness.workflow", "subprocess"),
        ("harness.workflow_requirements", "code_content.files"),
        ("harness.workflow_requirements", "integrations.registry"),
        ("hook_runtime", "code_content.files"),
        ("hook_runtime", "integrations.registry"),
        ("hook_runtime", "subprocess"),
        ("host_adapters.installation_layouts", "subprocess"),
        ("integrations.desktop_environment", "subprocess"),
        ("integrations.gateway", "integrations.registry"),
        ("integrations.onboarding", "integrations.registry"),
        ("integrations.provider_process", "subprocess"),
        ("integrations.provider_process", "threading"),
        ("integrations.readiness", "integrations.registry"),
        ("integrations.scm", "integrations.registry"),
        ("integrations.scm", "subprocess"),
        ("integrations.transport", "subprocess"),
        ("integrations.transport", "threading"),
        ("policy.git_utils", "subprocess"),
        ("policy.task_evidence", "code_content.files"),
    }
)


def _source_file(module: str) -> Path | None:
    candidates = (
        candidate
        for root in SEARCH_PATH
        for base in (root.joinpath(*module.split(".")),)
        for candidate in (base.with_suffix(".py"), base / "__init__.py")
    )
    return next((c for c in candidates if c.is_file()), None)


def _canonical(module: str) -> str | None:
    """One name per file: `scripts.hook_runtime` and `hook_runtime` are the same module."""
    source = _source_file(module)
    return (
        None
        if source is None
        else ".".join(
            source.relative_to(SCRIPTS if SCRIPTS in source.parents else PLUGIN_ROOT)
            .with_suffix("")
            .parts
        ).removesuffix(".__init__")
    )


def _package_of(module: str) -> str:
    source = _source_file(module)
    return (
        module
        if source is not None and source.name == "__init__.py"
        else module.rpartition(".")[0]
    )


def _absolute(node: ast.ImportFrom, module: str) -> str:
    anchor = _package_of(module).split(".") if node.level else []
    base = anchor[: len(anchor) - (node.level - 1)] if node.level else []
    return ".".join([*base, *([node.module] if node.module else [])])


def _imported_names(module: str) -> frozenset[str]:
    """Every dotted name the module imports, plus `base.name` for each `from base import name`."""
    source = _source_file(module)
    tree = (
        ast.parse(source.read_text(encoding="utf-8")) if source else ast.Module([], [])
    )
    plain = (
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    named = (
        name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for base in (_absolute(node, module),)
        for name in (base, *(f"{base}.{alias.name}" for alias in node.names))
    )
    return frozenset((*plain, *named))


def _with_parent_packages(name: str) -> tuple[str, ...]:
    parts = name.split(".")
    return tuple(".".join(parts[:n]) for n in range(1, len(parts) + 1))


def _local_targets(module: str) -> frozenset[str]:
    return frozenset(
        canonical
        for name in _imported_names(module)
        for prefix in _with_parent_packages(name)
        if (canonical := _canonical(prefix)) is not None
    )


def _offences(module: str) -> frozenset[tuple[str, str]]:
    names = _imported_names(module)
    return frozenset(
        (module, target)
        for target in (
            *(
                stdlib
                for stdlib in sorted(FORBIDDEN_STDLIB)
                if any(n == stdlib or n.startswith(f"{stdlib}.") for n in names)
            ),
            *((REGISTRY,) if _canonical(REGISTRY) in _local_targets(module) else ()),
            *((PROJECT_WALK,) if PROJECT_WALK_MODULE in _local_targets(module) else ()),
        )
    )


def _is_forbidden_local(module: str) -> bool:
    return module in {_canonical(REGISTRY), PROJECT_WALK_MODULE}


def _closure(entries: tuple[str, ...]) -> frozenset[str]:
    """Local modules reachable from the entries. A forbidden local module is a leaf: what it
    imports is reachable only through an import that is itself reported."""

    def step(seen: frozenset[str], module: str) -> frozenset[str]:
        fresh = frozenset() if module in seen else frozenset({module})
        grown = seen | fresh
        return (
            grown
            if _is_forbidden_local(module) or not fresh
            else reduce(step, sorted(_local_targets(module)), grown)
        )

    return reduce(step, [c for e in entries if (c := _canonical(e))], frozenset())


def _render(pairs: frozenset[tuple[str, str]]) -> str:
    return "\n".join(f"    {pair!r}," for pair in sorted(pairs)) or "    (none)"


def test_hook_path_cannot_import_process_network_or_tree_walking_code() -> None:
    found = frozenset(
        pair for module in _closure(ENTRY_POINTS) for pair in _offences(module)
    )

    added = found - STILL_TO_REMOVE
    stale = STILL_TO_REMOVE - found

    assert found == STILL_TO_REMOVE, (
        "The hook path imports code that may run long (process, network, tracker, project walk).\n"
        f"New offenders, not allowed (cut the import):\n{_render(added)}\n"
        f"Stale entries, no longer offending (delete them from STILL_TO_REMOVE):\n{_render(stale)}"
    )
