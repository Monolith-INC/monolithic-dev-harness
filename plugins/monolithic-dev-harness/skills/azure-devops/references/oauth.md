# Azure DevOps transport and OAuth notes

This is maintainer guidance for the `workflow-integrations` gateway. The agent-facing MCP server is
the gateway; its Azure adapter starts and reuses the native `@azure-devops/mcp` transport. Do not
register the provider server separately in a host or launch an extra copy for a health check.

## Expected behavior

- The gateway reads Azure organization, project, and repository values from harness settings.
- The first Azure operation may open a browser for interactive OAuth.
- The gateway keeps its provider transport alive across calls so later operations reuse the same
  authenticated process.
- Do not use Azure CLI authentication, `az login`, a PAT, or a second direct MCP connection.

## Recovery

- A timeout or `Transport closed` does not establish that OAuth is invalid.
- Stop after a failed gateway call; repeated retries can leave provider processes waiting for OAuth
  callbacks.
- Reload the host before retrying once through `workflow-integrations`.
- If investigating a process, establish that its owning gateway client is gone before terminating
  it. A process count or process name alone does not prove staleness.

Never log or store access tokens, cookies, or credentials.
