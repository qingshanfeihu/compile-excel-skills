#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import readline from "node:readline";
import * as tools from "../cex_client/tools";

const PKG_VERSION = String(
  JSON.parse(fs.readFileSync(path.resolve(__dirname, "..", "..", "package.json"), "utf8")).version || "0",
);
const SERVER_INFO = { name: "compile-excel", version: PKG_VERSION };
const DEFAULT_PROTOCOL = "2025-06-18";

function result(msgId: any, value: any) {
  return { jsonrpc: "2.0", id: msgId, result: value };
}

function error(msgId: any, code: number, message: string) {
  return { jsonrpc: "2.0", id: msgId, error: { code, message } };
}

async function handle(message: any): Promise<any | null> {
  if (!message || typeof message !== "object" || Array.isArray(message) || message.jsonrpc !== "2.0") {
    return error(null, -32600, "invalid request");
  }
  const method = message.method;
  const msgId = message.id;
  const isNotification = !("id" in message);
  const params = message.params || {};
  if (method === "initialize") {
    const requested = typeof params === "object" && params ? params.protocolVersion : null;
    return result(msgId, {
      protocolVersion: requested || DEFAULT_PROTOCOL,
      capabilities: { tools: { listChanged: false } },
      serverInfo: SERVER_INFO,
    });
  }
  if (method === "notifications/initialized" || method === "notifications/cancelled") {
    return null;
  }
  if (method === "ping") {
    return result(msgId, {});
  }
  if (method === "tools/list") {
    const specs = tools.loadSpecs();
    return result(msgId, {
      tools: specs.map((spec: any) => ({
        name: spec.name,
        description: spec.description,
        inputSchema: spec.input_schema,
        annotations: { readOnlyHint: Boolean(spec.read_only) },
      })),
    });
  }
  if (method === "tools/call") {
    if (typeof params !== "object" || typeof params.name !== "string") {
      return error(msgId, -32602, "tools/call needs a tool name");
    }
    const outcome = await tools.call(params.name, params.arguments || {});
    const failed = outcome && (outcome as any).ok === false && !(outcome as any).pending;
    return result(msgId, {
      content: [{ type: "text", text: JSON.stringify(outcome) }],
      structuredContent: outcome,
      isError: failed,
    });
  }
  if (isNotification) {
    return null;
  }
  return error(msgId, -32601, `method not found: ${method}`);
}

function write(line: any): void {
  process.stdout.write(JSON.stringify(line) + "\n");
}

async function main(): Promise<number> {
  const rl = readline.createInterface({ input: process.stdin, terminal: false });
  for await (const raw of rl) {
    const line = raw.trim();
    if (!line) continue;
    let message: any;
    try {
      message = JSON.parse(line);
    } catch {
      write(error(null, -32700, "parse error"));
      continue;
    }
    if (Array.isArray(message)) {
      const replies = [];
      for (const m of message) {
        const r = await handle(m);
        if (r !== null) replies.push(r);
      }
      if (replies.length) write(replies);
      continue;
    }
    const reply = await handle(message);
    if (reply !== null) write(reply);
  }
  return 0;
}

main().then((code) => process.exit(code));

