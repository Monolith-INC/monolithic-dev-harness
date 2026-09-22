#!/usr/bin/env node
// Out-of-band health check for the Azure DevOps MCP server.
//
//   node health-check.mjs --project <project> [--org <org>] [--timeout <seconds>]
//
// The organization comes from --org or AZURE_DEVOPS_ORG; there is no default.
//
// Spawns its own `npx -y @azure-devops/mcp <org>` process and speaks MCP over stdio
// (newline-delimited JSON-RPC), so it needs nothing but node and npx on PATH.
// Exit codes: 0 healthy, 1 call failed, 2 bad arguments, 124 timed out.
import { spawn } from "node:child_process";

function parseArgs(argv) {
  const options = {
    org: process.env.AZURE_DEVOPS_ORG || "",
    project: "",
    timeout: 75,
  };
  for (let i = 0; i < argv.length; i += 2) {
    const key = argv[i];
    const value = argv[i + 1];
    if (!value) return null;
    if (key === "--org") options.org = value;
    else if (key === "--project") options.project = value;
    else if (key === "--timeout") options.timeout = Number(value);
    else return null;
  }
  if (!options.org || !options.project) return null;
  return Number.isFinite(options.timeout) && options.timeout > 0 ? options : null;
}

const options = parseArgs(process.argv.slice(2));
if (!options) {
  console.error("usage: health-check.mjs --project <project> [--org <org>] [--timeout <seconds>]  (org also from AZURE_DEVOPS_ORG)");
  process.exit(2);
}

const server = spawn("npx", ["-y", "@azure-devops/mcp", options.org], {
  env: { ...process.env, LOG_LEVEL: "error" },
  stdio: ["pipe", "pipe", "ignore"],
});

const pending = new Map();
let nextId = 1;
let buffer = "";

function finish(code, message) {
  clearTimeout(timer);
  if (message) (code === 0 ? console.log : console.error)(message);
  server.kill();
  process.exit(code);
}

const timer = setTimeout(() => finish(124, "azure-devops-mcp: timeout"), options.timeout * 1000);

server.on("error", (error) => finish(1, `azure-devops-mcp: cannot start npx (${error.message})`));
server.on("exit", (code) => {
  if (pending.size > 0) finish(1, `azure-devops-mcp: server exited early (code ${code})`);
});

server.stdout.setEncoding("utf8");
server.stdout.on("data", (chunk) => {
  buffer += chunk;
  let newline;
  while ((newline = buffer.indexOf("\n")) >= 0) {
    const line = buffer.slice(0, newline).trim();
    buffer = buffer.slice(newline + 1);
    if (!line) continue;
    let message;
    try {
      message = JSON.parse(line);
    } catch {
      continue;
    }
    const resolve = pending.get(message.id);
    if (resolve) {
      pending.delete(message.id);
      resolve(message);
    }
  }
});

function request(method, params) {
  const id = nextId++;
  server.stdin.write(`${JSON.stringify({ jsonrpc: "2.0", id, method, params })}\n`);
  return new Promise((resolve) => pending.set(id, resolve));
}

function notify(method, params) {
  server.stdin.write(`${JSON.stringify({ jsonrpc: "2.0", method, params })}\n`);
}

const init = await request("initialize", {
  protocolVersion: "2025-06-18",
  capabilities: {},
  clientInfo: { name: "monolithic-dev-harness-health", version: "1.0.0" },
});
if (init.error) finish(1, `azure-devops-mcp: initialize failed: ${init.error.message}`);
notify("notifications/initialized", {});

const call = await request("tools/call", {
  name: "core_list_projects",
  arguments: { projectNameFilter: options.project, top: 1 },
});
if (call.error || call.result?.isError) {
  finish(1, `azure-devops-mcp: core_list_projects failed: ${JSON.stringify(call.error ?? call.result)}`);
}

const text = (call.result?.content ?? []).map((part) => part.text ?? "").join("");
if (!text.includes(options.project)) {
  finish(1, `azure-devops-mcp: project "${options.project}" not found in response`);
}
finish(0, `azure-devops-mcp: healthy (org ${options.org}, project ${options.project})`);
