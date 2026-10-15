# Reading volume in the ended baseline trial

Counted from explicit file-content commands in the saved test-agent transcript: **34 requests across 30 distinct file paths**, including one memory-content search. Four project files were read again during the requested state-management revision.

Breakdown: 12 harness instruction/reference files (12 requests); 9 project request/documentation files (9 requests); 8 project source/test/configuration files (12 requests); 1 memory file (1 search).

Method: count each explicit file argument to cat, sed, or nl, plus the memory-content search. Exclude directory listings, shell help, generated command output, evidence writes, implicit tool/runtime file access, and root-agent reading. This measures requested file reads, not verified full consumption or token cost. The two files named README.md are distinct paths.

The agent made 44 recorded shell-command requests overall. Some read multiple files; others inspect state, save evidence, or update checkpoints. This number is not a count of documents.

## Per-file counts

| File | Requests |
| --- | --- |
| installed harness/skills/bootstrap/SKILL.md | 1 |
| installed harness/skills/harness/SKILL.md | 1 |
| /home/monolith/.codex/memories/MEMORY.md | 1 |
| backlog/README.md | 1 |
| docs/README.md | 1 |
| backlog/DAY-001-task-counts.md | 1 |
| installed harness/skills/bmad-build/SKILL.md | 1 |
| installed harness/skills/harness/references/technical-discovery.md | 1 |
| installed harness/references/workflow-storyboard.md | 1 |
| docs/00-context/current-state.md | 1 |
| docs/02-design/current-interaction.md | 1 |
| docs/03-engineering/architecture.md | 1 |
| docs/03-engineering/testing.md | 1 |
| docs/03-engineering/development.md | 1 |
| lib/domain/task.dart | 2 |
| lib/application/daybook_providers.dart | 2 |
| lib/presentation/task_list_page.dart | 2 |
| test/domain/task_test.dart | 2 |
| lib/domain/auth.dart | 1 |
| lib/main.dart | 1 |
| lib/presentation/login_page.dart | 1 |
| pubspec.yaml | 1 |
| docs/01-product/vision.md | 1 |
| installed harness/skills/generate-work-item/SKILL.md | 1 |
| installed harness/skills/enrich-work-item/SKILL.md | 1 |
| installed harness/skills/decompose-backlog/SKILL.md | 1 |
| installed harness/skills/generate-breakdown-work-items/SKILL.md | 1 |
| installed harness/references/tracker-contract.md | 1 |
| installed harness/references/decomposition-rules.md | 1 |
| installed harness/references/ticket-structure.md | 1 |
