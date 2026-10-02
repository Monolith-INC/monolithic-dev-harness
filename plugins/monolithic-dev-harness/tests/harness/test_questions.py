"""Questions to the user: plain language before they are shown, and approval by click after.

The hook is driven as a subprocess with the payloads Claude Code sends for AskUserQuestion
(recorded from a real session).
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.harness import questions, state
from tests.settings_fixture import write_settings

HOOK = Path(__file__).resolve().parents[2] / "scripts" / "harness" / "hook.py"

PLAIN = "Create these 3 work items in Azure under the photo storage story?"
PLANNING = "Would you like to plan the idea before I draft the work items?"


def ask(text: str = PLAIN, *more: dict, **extra: object) -> dict:
    return {
        "questions": [
            {
                "question": text,
                "header": "Azure",
                "multiSelect": False,
                "options": [
                    {"label": "Approve", "description": "I create them now."},
                    {"label": "Not now", "description": "Nothing is written."},
                ],
            },
            *more,
        ],
        **extra,
    }


def planning_offer() -> dict:
    return {
        "questions": [
            {
                "question": PLANNING,
                "header": "Starting point",
                "multiSelect": False,
                "options": [
                    {
                        "label": "Plan the idea",
                        "description": "Explore it first and produce a clear product plan.",
                    },
                    {
                        "label": "Draft work items",
                        "description": "Use what you provided and draft the work items now.",
                    },
                ],
            }
        ]
    }


def run(repo: Path, event: str, payload: dict, host: str = "claude") -> dict | None:
    proc = subprocess.run(
        [sys.executable, str(HOOK), "--host", host, "--event", event],
        input=json.dumps(
            {
                "cwd": str(repo),
                "tool_name": "request_user_input"
                if host == "codex"
                else "AskUserQuestion",
                **payload,
            }
        ),
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout) if proc.stdout.strip() else None


class ProblemsTests(unittest.TestCase):
    def test_a_plain_question_passes(self) -> None:
        self.assertEqual(questions.problems(ask()), [])

    def test_what_a_person_would_have_to_decode_is_sent_back(self) -> None:
        for text, expected in (
            (
                "Reply approve HB-4TRK to write .harness/review/sources.json?",
                "batch id",
            ),
            ("Run workflow_skip_tracker first?", "underscores"),
            ("Revert the line in `.gitignore`?", "backticks"),
            ("Move the rule into .git/info/exclude?", "dotfile"),
            ("Edit projects/aplicatudo/lib/main.dart now?", "path"),
            ("Update sources.json?", "file name"),
            ("The human-owned rule blocked this. Retry?", "rule name"),
            ("Is the spec ready for G2?", "gate number"),
            ("Pause tracking? And link the spec?", "more than one thing"),
            (" ".join(["word"] * 60) + "?", "words"),
        ):
            with self.subTest(text=text):
                found = questions.problems(ask(text))
                self.assertTrue(any(expected in item for item in found), found)

    def test_one_question_at_a_time(self) -> None:
        found = questions.problems(ask(PLAIN, ask()["questions"][0]))
        self.assertTrue(any("2 questions" in item for item in found))

    def test_answers_filled_in_by_the_agent_are_refused(self) -> None:
        found = questions.problems(ask(answers={PLAIN: "Approve"}))
        self.assertTrue(any("only the user answers" in item for item in found))

    def test_stage_zero_offer_uses_the_plain_question_contract(self) -> None:
        self.assertEqual(questions.problems(planning_offer()), [])


class ChoiceContractTests(unittest.TestCase):
    def test_same_choice_has_native_and_numbered_presentations(self) -> None:
        choice = questions.Choice(
            "language",
            "Language",
            "Idioma",
            "Which language would you prefer?",
            "Qual idioma você prefere?",
            (
                questions.ChoiceOption(
                    "en", "English", "Inglês", "Use English.", "Usar inglês."
                ),
                questions.ChoiceOption(
                    "pt-br",
                    "Português (Brasil)",
                    "Português (Brasil)",
                    "Use Brazilian Portuguese.",
                    "Usar português do Brasil.",
                ),
            ),
        )
        codex = questions.render_choice(choice, "pt-br", "codex", True)
        fallback = questions.render_choice(choice, "pt-br", "text", False)
        self.assertEqual(codex["questions"][0]["id"], "language")
        self.assertEqual(codex["questions"][0]["options"][0]["label"], "Inglês")
        self.assertIn("error", fallback)
        self.assertNotIn("text", fallback)
        self.assertEqual(questions.problems(codex), [])

    def test_approval_requires_clickable_control(self) -> None:
        choice = questions.Choice(
            "publish",
            "Publish",
            "Publicar",
            "Create these two work items?",
            "Criar estes dois itens de trabalho?",
            (
                questions.ChoiceOption(
                    "approve",
                    "Approve",
                    "Aprovar",
                    "Create them now.",
                    "Criá-los agora.",
                ),
                questions.ChoiceOption(
                    "later",
                    "Not now",
                    "Agora não",
                    "No items are created.",
                    "Nenhum item será criado.",
                ),
            ),
            approval=True,
        )
        fallback = questions.render_choice(choice, "en", "text", False)
        self.assertNotIn("text", fallback)
        self.assertNotIn("questions", fallback)
        self.assertIn("questions", questions.render_choice(choice, "en", "codex", True))
        self.assertIn("error", questions.render_choice(choice, "en", "text", False))


class ApprovalByClickTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        write_settings(self.repo)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _answer(self, label: str, tool_use_id: str = "toolu_1") -> dict | None:
        tool_input = ask()
        return run(
            self.repo,
            "answer",
            {
                "tool_use_id": tool_use_id,
                "tool_input": {**tool_input, "answers": {PLAIN: label}},
                "tool_response": {**tool_input, "answers": {PLAIN: label}},
            },
        )

    def test_clicking_approve_opens_a_window(self) -> None:
        self.assertIsNone(
            run(self.repo, "ask", {"tool_use_id": "toolu_1", "tool_input": ask()})
        )
        out = self._answer("Approve")
        self.assertIn("approved", out["hookSpecificOutput"]["additionalContext"])
        active = state.active_approval(self.repo)
        self.assertIsNotNone(active)
        self.assertEqual(active[1]["question"], PLAIN)

    def test_codex_picker_answer_opens_a_window(self) -> None:
        tool_input = {
            "questions": [
                {
                    "id": "approval",
                    "question": PLAIN,
                    "header": "Azure",
                    "options": [
                        {
                            "label": "Approve (Recommended)",
                            "description": "I create them now.",
                        },
                        {"label": "Not now", "description": "Nothing is written."},
                    ],
                }
            ],
            "isBlocking": True,
        }
        self.assertIsNone(
            run(
                self.repo,
                "ask",
                {"tool_use_id": "codex-tool-1", "tool_input": tool_input},
                host="codex",
            )
        )
        response = {"answers": {"approval": {"answers": ["Approve (Recommended)"]}}}
        out = run(
            self.repo,
            "answer",
            {
                "tool_use_id": "codex-tool-1",
                "tool_input": tool_input,
                "tool_response": response,
            },
            host="codex",
        )
        self.assertIn("approved", out["hookSpecificOutput"]["additionalContext"])
        self.assertIsNotNone(state.active_approval(self.repo))

    def test_clicking_approve_pins_the_notes_marked_approved(self) -> None:
        write_settings(self.repo, artifacts_path="Vault")
        (self.repo / "Vault").mkdir()
        (self.repo / "Vault/plan.md").write_text(
            "---\nstory: 7824\nstatus: approved\n---\n"
        )
        (self.repo / "Vault/draft.md").write_text(
            "---\nstory: 7825\nstatus: draft\n---\n"
        )
        run(self.repo, "ask", {"tool_use_id": "toolu_1", "tool_input": ask()})
        out = self._answer("Approve")
        self.assertIn(
            "1 plan or spec note", out["hookSpecificOutput"]["additionalContext"]
        )
        self.assertEqual(len(state.pinned_notes(self.repo)), 1)

    def test_not_now_opens_nothing(self) -> None:
        run(self.repo, "ask", {"tool_use_id": "toolu_1", "tool_input": ask()})
        self.assertIsNone(self._answer("Not now"))
        self.assertIsNone(state.active_approval(self.repo))

    def test_stage_zero_choice_opens_no_approval_window(self) -> None:
        tool_input = planning_offer()
        self.assertIsNone(
            run(
                self.repo,
                "ask",
                {"tool_use_id": "stage-zero", "tool_input": tool_input},
            )
        )
        response = {**tool_input, "answers": {PLANNING: "Plan the idea"}}
        self.assertIsNone(
            run(
                self.repo,
                "answer",
                {
                    "tool_use_id": "stage-zero",
                    "tool_input": response,
                    "tool_response": response,
                },
            )
        )
        self.assertIsNone(state.active_approval(self.repo))

    def test_typing_approve_as_other_opens_nothing(self) -> None:
        run(self.repo, "ask", {"tool_use_id": "toolu_1", "tool_input": ask()})
        self.assertIsNone(self._answer("approve"))
        self.assertIsNone(state.active_approval(self.repo))

    def test_a_question_that_skipped_the_check_opens_nothing(self) -> None:
        self.assertIsNone(self._answer("Approve", tool_use_id="toolu_unchecked"))
        self.assertIsNone(state.active_approval(self.repo))

    def test_an_answer_is_honoured_once(self) -> None:
        run(self.repo, "ask", {"tool_use_id": "toolu_1", "tool_input": ask()})
        self._answer("Approve")
        state.revoke_approvals(self.repo)
        self.assertIsNone(self._answer("Approve"))
        self.assertIsNone(state.active_approval(self.repo))

    def test_a_question_sent_back_is_not_marked(self) -> None:
        out = run(
            self.repo,
            "ask",
            {"tool_use_id": "toolu_2", "tool_input": ask("Write `x`?")},
        )
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIsNone(self._answer("Approve", tool_use_id="toolu_2"))

    def test_the_agent_cannot_mark_a_question_itself(self) -> None:
        payload = {
            "cwd": str(self.repo),
            "tool_name": "Bash",
            "tool_input": {
                "command": "mkdir -p .harness/state/asked && touch .harness/state/asked/x.json"
            },
        }
        proc = subprocess.run(
            [sys.executable, str(HOOK), "--host", "claude", "--event", "pre-tool"],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("human-owned", proc.stdout)

    def test_ungoverned_repositories_are_left_alone(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(
                run(
                    Path(tmp),
                    "ask",
                    {"tool_use_id": "t", "tool_input": ask("Write `x`?")},
                )
            )


class AdoptionApprovalTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        write_settings(self.repo)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _question(self, adoption_id: str) -> tuple[str, dict]:
        text = f"Approve adoption plan {adoption_id} as shown?"
        return text, {
            "questions": [
                {
                    "question": text,
                    "header": "Adoption",
                    "multiSelect": False,
                    "options": [
                        {
                            "label": "Approve adoption",
                            "description": "Create its exact recovery worktree when requested.",
                        },
                        {"label": "Not now", "description": "Do not approve it."},
                    ],
                }
            ]
        }

    def test_adoption_click_pins_the_exact_plan(self) -> None:
        adoption_id = "HA-0123456789"
        folder = self.repo / ".harness/state/adoptions" / adoption_id
        folder.mkdir(parents=True)
        state.write_json(folder / "plan.json", {"id": adoption_id, "digest": "exact"})
        text, tool_input = self._question(adoption_id)
        self.assertIsNone(
            run(
                self.repo,
                "ask",
                {"tool_use_id": "adopt-1", "tool_input": tool_input},
            )
        )
        response = {**tool_input, "answers": {text: "Approve adoption"}}
        answered = run(
            self.repo,
            "answer",
            {
                "tool_use_id": "adopt-1",
                "tool_input": response,
                "tool_response": response,
            },
        )
        self.assertIn("approved for its exact content", str(answered))
        self.assertEqual(
            state.read_json(folder / "approval.json")["plan_digest"], "exact"
        )


if __name__ == "__main__":
    unittest.main()
