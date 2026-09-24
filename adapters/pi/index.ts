// compile-excel 的 pi 扩展：把 cex_* 工具注册进 pi，执行时调发行根的 bin/cex_tool。
//
// 工具说明与参数 schema 来自 tools.generated.ts（由 cex_client/tool_specs.json 生成）；
// 工具逻辑只有 cex_client 一份，这里只负责转发和把结果交回 pi。
// cex_tool 退出码：0 成功（含 pending）；1 工具返回 ok:false；2 用法错误。非 0 时抛错，pi 把结果标成 isError。
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { CEX_TOOLS } from "./tools.generated";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const CEX_TOOL = resolve(ROOT, "bin", "cex_tool");
// 单次调用的上限：登录/扫码等待最长 300 秒，一次上机可以更久，按最长的给
const TIMEOUT_MS = 45 * 60 * 1000;

export default function compileExcel(pi: ExtensionAPI) {
	const python = process.env.CEX_PYTHON || "python3";
	for (const tool of CEX_TOOLS) {
		pi.registerTool({
			name: tool.name,
			label: tool.label,
			description: tool.description,
			promptSnippet: tool.snippet,
			parameters: tool.parameters,
			// 改状态的工具（登录、租约、提交）一个一个来，只读的可以并发
			executionMode: tool.readOnly ? "parallel" : "sequential",
			async execute(_toolCallId, params, signal, _onUpdate, ctx) {
				const result = await pi.exec(python, [CEX_TOOL, tool.name, JSON.stringify(params ?? {})], {
					signal,
					timeout: TIMEOUT_MS,
					cwd: ctx.cwd,
				});
				let payload: unknown;
				try {
					payload = JSON.parse(result.stdout);
				} catch {
					const tail = (result.stderr || result.stdout).slice(-800);
					throw new Error(`${tool.name} returned no JSON (exit ${result.code}${result.killed ? ", killed" : ""}): ${tail}`);
				}
				const text = JSON.stringify(payload, null, 1);
				if (result.code !== 0) {
					throw new Error(text);
				}
				return { content: [{ type: "text", text }], details: payload };
			},
		});
	}
}
