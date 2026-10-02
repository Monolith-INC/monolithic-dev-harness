dev harnness:

1. Azure devops skill: the authentication is being called multiple times, it causes a new tab to be opened and receiving focus, which disturbs computer use. moreover, indicates wasteful network calls. see that the skill instructs the agent on how to properly use the authentication call, and only when necessary
2. the implementation plan and the specs were not shown to the user. they should be shown using a canvas, if possible, and the approval should be a button you click either on the chat window or on the documents themselves
3. during the implementation stage, the agent internal dialogue indicated it was confused on what to do, suggesting the skills are not properly briefing the agent on what and how it should do. example:
---
Starting the carry-over: set the work aside, restart the branch on a fresh develop, then bring the work back.

Stashed tracked work and restarted branch on develop
That change reflects switching from checkout to develop as expected. Now I'll apply the git stash.
The branch is now on the latest develop. Bringing the set-aside changes back:

Applied stashed changes onto the develop base
Everything's staged from the conflict apply, so I should unstage with a mixed reset first to keep the working tree and stage per-task instead. I need to resolve the generate-report.ts conflict, and package.json merged cleanly but I should check it for the cache-experiment line and remove it if present.
Everything came back. package.json merged cleanly, and generate-report.ts has the expected conflict. Let me look at the conflict.

I'm thinking the repeated auth prompts likely come from the tracker_* tools spawning a fresh npx MCP process per call, each triggering its own OAuth flow, whereas the persistent azure-devops MCP plugin with wit_* tools maintains a session and avoids re-authenticating.

But then I realize the real culprit might be the PreToolUse workflow hook itself, which checks work item state on every git command via the gateway adapter, spawning a new npx process and triggering auth each time — something I can't change since it's human-owned config, but I can reduce by batching git operations and using wit_* tools directly for my own reads. Let me check whether the azure-devops skill documents any way to reuse a cached token instead of prompting interactively every time.
Checking why Azure DevOps keeps asking you to sign in.


Ran 2 commands
The OAuth cache is per server process and lives in memory, so since the gateway spawns a fresh npx process for every hook invocation and tracker_* call, each one triggers a new OAuth round trip. That explains why the browser keeps popping up repeatedly with every git commit.

To mitigate this, I should switch to the plugin's persistent wit_* tools instead of tracker_*, and batch remaining commits into as few Bash calls as possible since the hook fires per Bash call rather than per git command. I checked whether the gateway supports a persistent connection or daemon reuse, but found nothing in the config I could adjust myself since settings are human-owned—so the real fix would require the harness reusing a single Azure connection rather than spawning new ones per governed command.

Now I'm looking at batching the remaining commits (7985, 7988, 7989, 7990) into a single Bash call, but I need to check the guarded paths first—tools/package.json requires manual config-approval and docs require manual tech-lead-approval, both needing human-recorded evidence I can't generate myself. I should check the harness CLI help to see how manual evidence gets recorded and how the user is meant to provide it.
Found that each safety check and tracker call spins up a fresh Azure DevOps sign-in, while my own tools reuse one persistent connection. I'll stick to that persistent connection going forward and batch remaining commits to minimize repeated checks, but first need to confirm how manual sign-off for protected files is recorded and whether the extra sign-in processes are accumulating.

Checked manual-evidence command and stray Azure processes
I see 5 azure-devops mcp processes running, which seems normal, so I won't kill them without approval. I'm trying to figure out how manual evidence gets recorded—probably tied to the AskUserQuestion approval hook when the user answers a manual-check question—so I want to grep for how that's actually logged.
Found how manual sign-off evidence is recorded
I need manual approval evidence tied to the exact staged tree. Since package.json for the sync command belongs with task 7985 while docs belong to 7990, I'm figuring out how to sequence commits to minimize back-and-forth with the user for approval.

I'll stage 7985's files first and ask for the config-approval confirmation, commit, then handle 7988/7989 together, then stage docs separately and ask for tech-lead-approval before that final commit. Now I need to check the diff for AiGenerationRequest in generate-student-report-ai-analysis.ts, since only that export needs a partial patch for 7985.
Two protected files—tools' package.json and the docs—need your sign-off, which I can only record if you confirm while the exact change is staged. I'm staging the shared-package commit (Task 7985) first, which includes the export of the request type from the generation file.


Ran 2 commands
That sed attempt didn't match, so I'm considering a different approach: staging a modified version of the report generation file directly into the git index for that commit, adding an exported interface matching the request shape, by crafting the change at the index level rather than the working tree. I want to check the current interface definition in the working file first.
I'm splitting the generation file so only the request-type export goes into the shared-package commit. Reading the exact definition:

Showed the request type and who uses it
I'm building an index version of the HEAD file that inserts the AiGenerationRequest interface before the AiContentGenerator interface, keeping the generateContent signature unchanged, then writing that blob with git hash-object and updating the index via git update-index. After that I need to stage the large set of changed files, including shared-report-context.ts and its test, the student-report assets, and the tools sync.

I'll try to batch these into a single Bash call to minimize hook triggers, though I'm wondering whether git update-index counts as a governed command that will still trigger the hook regardless.
Staged Task 7985 with only the type export
I'm checking whether the indentation matches the working tree version and if lint actually passed on it. I'm also wondering if the pre-commit hook's auto-fix step might re-stage the working tree version of the functions file rather than the intended committed version, which could cause a mismatch.
Staged. One risk: the repository's pre-commit hook re-stages files it auto-fixes, which could pull the whole generation file into this commit. Checking how it re-stages:


Ran 2 commands
Since the hook rejects partial staging, I need a different approach: save the full file to a scratchpad, overwrite the working file with the partial version, commit, then restore the full version afterward. I should also make sure lint passes cleanly on that partial file before committing.
The pre-commit hook blocks commits when a staged file has unstaged changes, so I'll temporarily swap in the one-export version of the generation file to commit, then restore the full version afterward.

Park the full generation file, match disk to index
I should ask the user to confirm by typing `harness manual-check config-approval ok`, explaining briefly that the change adds a single script entry to package.json. I'll stop here and wait for their typed confirmation rather than proceeding further.
Task 7985 (the shared package) is staged and ready to commit. It adds one line to the tools' package.json: a report:sync-reference command that regenerates the distributed glossary from the canonical one. It changes no dependencies or versions.

Because package.json is a protected file, the harness needs your sign-off for this exact staged change. Please reply with exactly:

harness manual-check config-approval ok
Where things stand:

Committed on the Story branch (on top of the latest develop): 7984 (prompt and contract), 7987 (telemetry), 7986 (registry, constants and access-rule test).
Checks on the full set of changes: type-check and lint pass for both the Functions and the local tools. The Functions tests pass: 1,527 tests, with the live test and the emulator-only tests skipped.
Still to commit: 7988 (generation) and 7989 (local tool) after this one. The docs commit (7990) will need one more sign-off from you, the same way.
About the repeated Azure sign-ins: the harness's safety checks run before code-changing commands such as commits and branch moves, and each run opens a brand-new Azure DevOps connection that has to sign in again. A few harness tracker tools I called directly did the same. The Azure tools I use for my own reads and writes keep one connection that stays signed in.

From now on I'm using only that long-lived connection and bundling git steps into fewer commands, so you'll see fewer prompts.
I can't stop the prompts entirely. They come from the harness's own safety checks, which I'm not allowed to change.
The lasting fix would be for the harness to reuse one signed-in connection instead of starting a new one per check. That's a change for whoever maintains it.
---
4. The agent shows approval questions outside the established contract: ui with buttons:

"Task 7985 (the shared package) is staged and ready to commit. It adds one line to the tools' package.json: a report:sync-reference command that regenerates the distributed glossary from the canonical one. It changes no dependencies or versions.

Because package.json is a protected file, the harness needs your sign-off for this exact staged change. Please reply with exactly:
"
5. even though we are working on a feature with one user story, the agent doesnt seem to have picked up we need to run the feature branch implementation, and cut the user story branch from the feature branch. 
