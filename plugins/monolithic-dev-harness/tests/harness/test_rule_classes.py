"""Every harness rule is marked `always` or `mode`, and an `always` rule needs no session.

Modes scope the process, not the safety net: a rule that guards the project or the user stays on
whether or not a work session is bound. `rules.CLASS` marks each rule, and these tests keep the
marks complete and honest, so a later change cannot drop a guard by accident.
"""

from __future__ import annotations

import ast
import inspect
import json

from harness import mode_hooks, rules, sessions
from tests.harness.test_hook_rules import AZ, HookTestCase, sh


def rule_names_evaluate_can_report() -> set[str]:
    """Every name a rule that `rules.evaluate` runs passes to `Decision.deny`.

    Read from the source, so a rule added to `evaluate` (or a new name reported by a helper a rule
    calls) shows up here without anyone remembering to list it. A rule may live in `mode_hooks`
    and be reached as `mode_hooks.<name>`, so both modules are read.
    """
    functions: dict[str, ast.FunctionDef] = {}
    for module in (rules, mode_hooks):
        for node in ast.parse(inspect.getsource(module)).body:
            if isinstance(node, ast.FunctionDef):
                functions[node.name] = node
    reachable: set[str] = set()
    pending = ["evaluate"]
    while pending:
        name = pending.pop()
        if name in reachable:
            continue
        reachable.add(name)
        pending.extend(
            node.id if isinstance(node, ast.Name) else node.attr
            for node in ast.walk(functions[name])
            if (isinstance(node, ast.Name) and node.id in functions)
            or (isinstance(node, ast.Attribute) and node.attr in functions)
        )
    names: set[str] = set()
    for name in reachable:
        for call in ast.walk(functions[name]):
            if not (
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Attribute)
                and call.func.attr == "deny"
            ):
                continue
            first = call.args[0]
            assert isinstance(first, ast.Constant) and isinstance(first.value, str), (
                f"{name} reports a rule name that is not a string literal, so this test "
                "cannot classify it"
            )
            names.add(first.value)
    return names


class TestEveryRuleIsClassified:
    def test_every_rule_has_exactly_one_class(self) -> None:
        assert set(rules.CLASS) == rule_names_evaluate_can_report()
        assert set(rules.CLASS.values()) <= {"always", "mode"}

    def test_the_session_bound_checks_are_not_rules(self) -> None:
        assert not {"work-session-context", "work-session-mismatch"} & set(rules.CLASS)


class TestAlwaysControlsDenyWithNoSession(HookTestCase):
    """The existing deny case of each `always` rule, run through the hook with no work session.

    A deny case is the method named after the rule (`history-preserved` is `history_preserved`),
    taken from the matching test in test_hook_rules.py.
    """

    def use_tracker(self, tracker: dict) -> None:
        settings = {
            **json.loads((self.repo / ".harness" / "settings.json").read_text()),
            "tracker": tracker,
        }
        (self.repo / ".harness" / "settings.json").write_text(json.dumps(settings))

    def pull_request(self, **extra: object) -> dict | None:
        return self.claude(
            AZ + "repo_pull_request_write",
            {"action": "create", "repositoryId": "r", **extra},
        )

    def human_owned(self) -> dict | None:
        return self.claude(
            "Edit", {"file_path": str(self.repo / ".harness/settings.json")}
        )

    def tracked_tickets(self) -> dict | None:
        self.use_tracker({"name": "local"})
        ready = self.repo / "Tickets/Ready"
        ready.mkdir(parents=True)
        item = ready / "0001-reset-notice.md"
        item.write_text('---\nprovider_id: "STORY-0001"\n---\n\nBody\n')
        return self.claude(
            "Edit", {"file_path": str(item), "old_string": "Body", "new_string": "x"}
        )

    def tracker_invalid(self) -> dict | None:
        self.use_tracker({"name": "azure-devops", "values": {"organization": "o"}})
        self.approve()
        return self.claude(AZ + "wit_work_item_write", {"action": "create"})

    def protected_items(self) -> dict | None:
        self.approve()
        return self.claude(
            AZ + "wit_work_item_write",
            {"action": "update", "id": 1001, "updates": []},
        )

    def feature_branch(self) -> dict | None:
        sessions.start(
            self.repo,
            "1",
            "feature-implementation",
            expected_base_ref="feature/900-parent",
            expected_base_commit=sh(self.repo, "rev-parse", "HEAD").strip(),
        )
        return self.pull_request(isDraft=True, targetRefName="refs/heads/develop")

    def draft_reviewed_prs(self) -> dict | None:
        self.approve()
        self.write("test/a_test.dart")
        self.write("lib/a.dart")
        sh(self.repo, "add", "-A")
        sh(self.repo, "commit", "-q", "-m", "feature")
        return self.pull_request(isDraft=False)

    def history_preserved(self) -> dict | None:
        self.approve()
        return self.claude("Bash", {"command": "git rebase develop"})

    def approval_required(self) -> dict | None:
        return self.claude(AZ + "wit_work_item_write", {"action": "create"})

    def generated_files(self) -> dict | None:
        return self.claude("Edit", {"file_path": str(self.repo / "lib/a.g.dart")})

    def fresh_repo(self) -> None:
        """A deny case changes the repository (a tracker, a session, a commit): start each over."""
        self.tearDown()
        self.setUp()

    def test_always_controls_deny_with_no_session(self) -> None:
        always = sorted(name for name, kind in rules.CLASS.items() if kind == "always")
        self.assertTrue(always)
        for rule in always:
            with self.subTest(rule=rule):
                self.fresh_repo()
                deny_case = getattr(self, rule.replace("-", "_"), None)
                self.assertIsNotNone(
                    deny_case, f"{rule} is always-on and needs a deny case here"
                )
                self.assertDenied(deny_case(), rule)
                work_sessions = self.repo / ".harness" / "state" / "work_sessions"
                self.assertEqual(sorted(work_sessions.glob("WS-*")), [])
