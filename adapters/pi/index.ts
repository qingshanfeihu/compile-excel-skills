// compile-excel 的 pi 扩展：把 cex_* 工具注册进 pi，执行时调发行根的 bin/cex_tool。
//
// 工具说明与参数 schema 来自 tools.generated.ts（由 cex_client/tool_specs.json 生成）；
// 工具逻辑只有 cex_client 一份，这里只负责转发和把结果交回 pi。
// 参数经 stdin 传（`cex_tool <名> -`）：整批用例这类大参数放进命令行会撞上长度上限（Linux 单个
// 参数 128 KiB），pi.exec 又不能喂 stdin，所以这里自己起子进程。
// cex_tool 退出码：0 成功（含 pending）；1 工具返回 ok:false；2 用法错误。非 0 时抛错，pi 把结果标成 isError。
import { spawn } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";
import { CEX_TOOLS } from "./tools.generated";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const CEX_TOOL = resolve(ROOT, "bin", "cex_tool");
// 单次调用的上限：登录/扫码等待最长 300 秒，一次上机可以更久，按最长的给
const TIMEOUT_MS = 45 * 60 * 1000;
// 超时或取消时先 SIGTERM，过这么久还没退再 SIGKILL
const KILL_GRACE_MS = 5000;

interface RunResult {
	stdout: string;
	stderr: string;
	code: number;
	killed: boolean;
}

function runCexTool(
	python: string,
	name: string,
	input: string,
	options: { signal?: AbortSignal; timeout: number; cwd?: string },
): Promise<RunResult> {
	return new Promise((resolvePromise) => {
		const child = spawn(python, [CEX_TOOL, name, "-"], {
			cwd: options.cwd,
			stdio: ["pipe", "pipe", "pipe"],
		});
		const stdout: Buffer[] = [];
		const stderr: Buffer[] = [];
		let killed = false;
		let settled = false;
		let hardKill: ReturnType<typeof setTimeout> | undefined;
		const stop = () => {
			if (killed || child.exitCode !== null) {
				return;
			}
			killed = true;
			child.kill("SIGTERM");
			hardKill = setTimeout(() => child.kill("SIGKILL"), KILL_GRACE_MS);
		};
		const timer = setTimeout(stop, options.timeout);
		const onAbort = () => stop();
		options.signal?.addEventListener("abort", onAbort, { once: true });
		const finish = (result: RunResult) => {
			if (settled) {
				return;
			}
			settled = true;
			clearTimeout(timer);
			if (hardKill) {
				clearTimeout(hardKill);
			}
			options.signal?.removeEventListener("abort", onAbort);
			resolvePromise(result);
		};
		child.stdout.on("data", (chunk: Buffer) => stdout.push(chunk));
		child.stderr.on("data", (chunk: Buffer) => stderr.push(chunk));
		child.on("error", (error: Error) => {
			// 解释器不在（CEX_PYTHON 指错）之类：当成一次失败的调用交回
			finish({ stdout: "", stderr: `${python}: ${error.message}`, code: -1, killed });
		});
		child.on("close", (code: number | null) => {
			finish({
				stdout: Buffer.concat(stdout).toString("utf8"),
				stderr: Buffer.concat(stderr).toString("utf8"),
				code: code ?? -1,
				killed,
			});
		});
		// 子进程提前退出时写 stdin 会 EPIPE：吞掉，结果照 close 事件报
		child.stdin.on("error", () => undefined);
		child.stdin.end(input, "utf8");
		if (options.signal?.aborted) {
			stop();
		}
	});
}

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
				const result = await runCexTool(python, tool.name, JSON.stringify(params ?? {}), {
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
