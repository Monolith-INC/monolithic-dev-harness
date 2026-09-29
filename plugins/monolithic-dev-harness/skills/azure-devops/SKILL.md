---
name: azure-devops
description: Use when a harness stage needs Azure DevOps — reading or writing work items, links, branches, pull requests, or review threads — or when the Azure DevOps MCP server needs a health check, authentication, or recovery. Covers locating the server's tools under the host's naming, interactive OAuth, and stale-process recovery. Use this instead of Azure CLI or `az login`.
---

# Azure DevOps

Every harness stage talks to Azure DevOps through one MCP server: `@azure-devops/mcp`, bundled
with this plugin and started with interactive OAuth. This skill is the single place that knows how
to find, check, and recover that server.

## Core rule

Use the bundled `@azure-devops/mcp` server with interactive OAuth. Do not switch to Azure CLI,
do not ask the user to run `az login`, and do not fall back to a PAT unless the user changes that
policy explicitly.

The organization, project, and team come from the repository's `.harness/settings.json`
(`tracker.values` when the tracker is `azure-devops`; `scm.values` for Azure Repos). The plugin has
no defaults. Never hard-code them in a stage. The host-registered server reads the organization
from `AZURE_DEVOPS_ORG`, which the installer sets.

## Finding the tools

The tool names are stable (`wit_work_item`, `wit_work_item_write`, `repo_pull_request`, …). The
prefix in front of them depends on the host and on who registered the server:

| Where the server is registered | Name the agent sees |
| --- | --- |
| This plugin, in Claude Code | `mcp__plugin_monolithic-dev-harness_azure-devops__wit_work_item` |
| A project `.mcp.json` entry named `azure-devops`, in Claude Code | `mcp__azure-devops__wit_work_item` |
| Another plugin that bundles the same server | `mcp__plugin_<plugin>_azure-devops__wit_work_item` |
| Cursor | `wit_work_item`, grouped under the `azure-devops` server |

Before concluding a tool is missing, search for its bare name (`wit_work_item`) in the host's tool
list. In Claude Code, deferred MCP tools only become callable after a tool search loads their
schema. Guidance written for another host names the bare tool; add the prefix you found rather
than assuming the tool is absent.

Run one registration per repository. If a project `.mcp.json` also registers `azure-devops`, two
server processes start and each needs its own OAuth round trip. Remove the project entry, or
disable this plugin's server for that repository.

## Health check

Prefer one targeted read-only call. It reuses the live connection and costs nothing:

- `core_list_projects` with `projectNameFilter=<project>` and `top=1`: success returns the project.
- `wit_work_item` with `action=get`, the project, and a known id.

Never use an unfiltered `core_list_projects` as a health check.

Only if the tools are missing or unresponsive, run the bundled script. It spawns its **own**
server process, so it answers "does OAuth work on this machine at all", not "is this session's
connection healthy":

```bash
node "<plugin root>/skills/azure-devops/scripts/health-check.mjs" --project <project>
```

The script needs only `node` and `npx` on `PATH`. Exit codes: `0` healthy, `1` call failed,
`124` timed out (usually an OAuth redirect nobody completed).

## Subagents

A subagent granted this server's tools inherits the parent session's authenticated connection. It
does not start its own server or its own OAuth. The OAuth cache is per server process and held in
memory, so the one risky case is a **cold start**: a background subagent as the first caller in a
fresh session, with nobody watching the browser redirect. Warm the connection from the main session
(one health-check call) before dispatching background workers that need Azure DevOps.

## Operating workflow

1. If the last call hung or was aborted, look for stale processes before retrying:

   ```bash
   pgrep -af "@azure-devops/mcp|mcp-server-azuredevops|npm exec @azure-devops"
   ```

   Several processes are normal, because each MCP client gets its own. Prove staleness by walking
   the parent chain, never by counting (see `references/oauth.md`).
2. If nothing is stale, make one read-only targeted call.
3. If a blank browser tab opens, wait for the redirect. An already signed-in browser normally
   completes it without a click.
4. `Transport closed` does not prove OAuth is broken. Verify with the script before concluding
   anything.
5. **If calls hang, stop.** Retries pile up server processes waiting on callbacks nobody
   completes. Ask the user to reload the host so MCP restarts cleanly, or ask permission to end
   the one specific stale process.

## Writes

This skill never authorizes a write by itself. Work item creation or edits, links, pull requests,
review threads, votes, and pipeline runs belong to the stage skills that own them, and every write
passes the harness hooks:

- **Approval gate:** a write tool call is blocked unless the user approved that batch in the chat.
- **Protected items:** ids listed in `.harness/settings.json` → `protected_work_items` are
  never written, linked, parented, or mentioned in linking text.

When a hook blocks a write, show the user the batch and ask for approval. Do not retry through a
different tool.

## Recovery rules

- Browser sign-in only supplies the session. The MCP process still needs its own OAuth round trip.
- Read before you write.
- End a server process only with the user's approval, and only the specific stale one. A live
  client's process looks identical in `pgrep`.
- Never log or expose tokens, cookies, tenant ids, or other credential material.

Machine-level detail: [`references/oauth.md`](references/oauth.md).
