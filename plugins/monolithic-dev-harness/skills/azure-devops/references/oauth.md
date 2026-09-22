# Azure DevOps MCP: OAuth and process notes

The harness runs `@azure-devops/mcp` with interactive OAuth. Claude Code and Cursor start the same
server package from the plugin's MCP configuration; they differ only in how tool names appear
(see the table in `SKILL.md`).

| | Claude Code | Cursor |
| --- | --- | --- |
| Server config | plugin `.mcp.json` → `azure-devops` | plugin manifest `mcpServers` → `azure-devops` |
| Command | `npx -y @azure-devops/mcp <org>` (from `PATH`) | same |
| Organization | `${AZURE_DEVOPS_ORG}` (required) | `${env:AZURE_DEVOPS_ORG}` (required) |

If the host cannot start the server but `npx @azure-devops/mcp` works in a terminal, check the
host's launch `PATH` first, not OAuth. GUI-launched hosts often lack the shell's `nvm` path.

## Expected behavior

- No `--authentication` flag: the server selects interactive OAuth.
- The first authenticated call opens the browser. The tab may look blank while the Microsoft
  redirect completes.
- An existing Microsoft session in the browser normally completes OAuth without interaction.
- Subagents inherit the parent session's connection: no separate OAuth, no extra process.

## Known failure modes

- `Transport closed` does not prove OAuth is broken.
- An aborted call can leave a server process waiting on an incomplete OAuth callback.
- Repeated retries create duplicate `npm exec @azure-devops/mcp` / `mcp-server-azuredevops`
  processes waiting on callbacks nobody completes.
- A background subagent that is the first caller in a cold session has nobody watching its
  browser redirect. Warm the connection from the main session first.

## Proving a process is stale

A raw process count proves nothing: every MCP client (each Claude session, Cursor's own client)
gets its own server process. Walk the parent chain instead:

```bash
for p in $(pgrep -f mcp-server-azuredevops); do
  ps -o pid,lstart,args -p "$p"
  ps -o pid,args -p "$(ps -o ppid= -p "$p" | tr -d ' ')"
done
```

A server whose client is still running is in use; ending it breaks that session. Walking far
enough up always reaches `systemd --user` or `launchd`; that is normal and not evidence of
orphaning. A process is stale only when the client that spawned it is gone.

## Recovery order

1. Inspect with `pgrep` and the parent walk above.
2. If one process is stale, end only that process, after the user approves.
3. Otherwise reload the host window.
4. Retry exactly one read-only call.

Never log or store access tokens, cookies, tenant identifiers, or other credentials.
