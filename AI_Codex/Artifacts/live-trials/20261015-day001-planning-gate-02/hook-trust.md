# Hook trust (between rounds 2 and 3)

Rounds 1 and 2 ran with no harness hook active: the isolated Codex home had no persisted hook trust,
and `codex exec` shows no trust prompt. Evidence: the relayed answer to the planning-depth decision
was not captured (decision still pending after round 2), no `.harness/state/host_sessions/` record,
and no hook activity in the trial Codex logs.

The human opened interactive Codex once in the trial home and project, accepted the
"Hooks need review" prompt (6 hooks), and quit without a prompt. No bypass flag was used.
Recorded trust entries (trial codex-home/config.toml, [hooks.state]):
[hooks.state."monolithic-dev-harness@monolithic-dev-harness:hooks/codex.hooks.json:pre_tool_use:0:0"]
trusted_hash = "sha256:27bdb2033fe68837bdc6d85a0cf19ed5bf2b2bbf59bfd06576abcca5f6400799"
--
[hooks.state."monolithic-dev-harness@monolithic-dev-harness:hooks/codex.hooks.json:pre_tool_use:1:0"]
trusted_hash = "sha256:d74e6496c01fda305178e45720277ec4d3e01c8f917df2f17de8704ebfaa9aec"
--
[hooks.state."monolithic-dev-harness@monolithic-dev-harness:hooks/codex.hooks.json:post_tool_use:0:0"]
trusted_hash = "sha256:2621259a26de85efc881b198ddcfda7fa6be065f48b39ad4ac7ef66c83ad6cf0"
--
[hooks.state."monolithic-dev-harness@monolithic-dev-harness:hooks/codex.hooks.json:post_tool_use:1:0"]
trusted_hash = "sha256:7947cc9074eb78497d96917035fc0d9f14fccf93b673b490f6abe4eb8da2fa7f"
--
[hooks.state."monolithic-dev-harness@monolithic-dev-harness:hooks/codex.hooks.json:user_prompt_submit:0:0"]
trusted_hash = "sha256:de6ec7021b43d30347efe94a339a33cf78fb8acea882d3fd0ba3055fe33788bf"
--
[hooks.state."monolithic-dev-harness@monolithic-dev-harness:hooks/codex.hooks.json:stop:0:0"]
trusted_hash = "sha256:80a952be8e7e861d08b19abff20d1dac7bec4e510650dff54bb542df8e62fa6a"
