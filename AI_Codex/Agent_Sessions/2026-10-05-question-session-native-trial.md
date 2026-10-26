# Lower-tier question and session trial

Date: 2026-10-05
Candidate: Monolithic Dev Harness 0.5.3 from the current checkout
Model: GPT-6 Luna, low reasoning
Workspace: disposable Daybook copy with local planning settings
Sandbox: read-only; no implementation or work-item creation authorized

## Result

The fresh Codex home installed and enabled candidate version 0.5.3. Its harness skill was loaded.
The agent inspected DAY-001, the task screen, its provider, and project notes, then reached the
proposal review gate. It made no file changes, created no work items, and did not implement.

The automatic question hook refused the agent's first attempted clickable question because it was
79 words and included internal terms and file references. The agent then showed the proposal and
textual choices in its final response. This `codex exec` run did not produce a native button or wait
for a human choice, so it does not verify native question controls or reply handling.

The tracker and workflow servers initially failed to start because this trial installed a copy of
the source folder directly into a temporary marketplace instead of using the repository installer.
The source Codex manifest uses `${PLUGIN_ROOT}` in `codex.mcp.json`; `install.sh` copies that file
and replaces the placeholder with the installed path. My temporary marketplace instead loaded the
generic `.mcp.json`, which contains `${CLAUDE_PLUGIN_ROOT}`. A later no-model check used
`install.sh --source ... --host codex --yes` with temporary `CODEX_HOME`, `HARNESS_HOME`, and
`HARNESS_BIN_DIR`; all three servers then initialized and returned 22, 22, and 17 tools. The saved
result is [the tool-server check](2026-10-05-candidate-tool-server-startup-check.json). The earlier
startup errors were a faulty trial setup, not a confirmed defect in the supported package.

## Reading and use

The saved transcript contains four distinct shell-command calls: three succeeded and one failed
while following a misplaced workflow reference. It has no explicit file-read events. The corrected
counter confirms 10 direct file displays from fully successful commands and marks four operands in
the failed command as unverified. Inspecting its output confirms one of those displays succeeded
before the missing reference failed, while the two later chained displays never ran. That gives 11
successful direct file displays over 11 unique existing paths: eight project files and three plugin
references, plus one missing-path attempt. Repository-wide `rg` searches are not counted as
individual file reads. The agent reported 179,856 input tokens, 154,880 cached input tokens, and
1,190 output tokens; the high input volume makes a narrower next prompt important.

Transcript: [JSONL](2026-10-05-question-session-native-trial.jsonl)

## Focused checks still needed

- Install through the supported installer in a private Codex home and confirm the candidate MCP
  tools start before spending another model call.
- In an interactive host that can show clickable controls, test delayed response, unrelated text,
  changed question text, wrong-session reply, reopening after the timer, one correct answer, and a
  duplicate reply. Never supply or infer a human answer during the test.
- Keep this as a process-level result until the actual control and response are captured in the
  native host.
