// 用真 pi（SDK + faux 脚本模型）跑一遍 compile-excel 包：包清单 → skill 发现 → 扩展加载 →
// 模型发起的工具调用 → 成功与失败（isError）语义。由 tests/test_adapters.py 在装了 pi 的
// node_modules 旁边运行；输出一行 JSON 给 Python 断言。
//   node pi_e2e.mjs <compile-excel 包根目录> <只答探活的假服务端地址>
import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fauxAssistantMessage, fauxToolCall, registerFauxProvider } from "@mariozechner/pi-ai";
import {
	AuthStorage,
	createAgentSession,
	DefaultResourceLoader,
	ModelRegistry,
	SessionManager,
} from "@mariozechner/pi-coding-agent";

const packageRoot = process.argv[2];
const server = process.argv[3];
const base = mkdtempSync(join(tmpdir(), "cex-pi-"));
const agentDir = join(base, "agent");
const project = join(base, "project");
mkdirSync(agentDir);
mkdirSync(project);
// 按用户安装的方式挂包：settings.json 的 packages 指向本地包目录
writeFileSync(join(agentDir, "settings.json"), JSON.stringify({ packages: [packageRoot] }));

const faux = registerFauxProvider({ models: [{ id: "faux-1" }] });
faux.setResponses([
	fauxAssistantMessage([fauxToolCall("cex_status", {})], { stopReason: "toolUse" }),
	fauxAssistantMessage(
		[fauxToolCall("cex_init", { workspace: project, server, device_build: "B_1" })],
		{ stopReason: "toolUse" },
	),
	fauxAssistantMessage([fauxToolCall("cex_status", {})], { stopReason: "toolUse" }),
	fauxAssistantMessage([fauxToolCall("cex_sync", {})], { stopReason: "toolUse" }),
	fauxAssistantMessage("done"),
]);

const loader = new DefaultResourceLoader({ cwd: project, agentDir });
await loader.reload();
const authStorage = AuthStorage.inMemory();
// faux 提供方不连网，pi 仍要求有个 key；给一个占位值
authStorage.setRuntimeApiKey("faux", "placeholder");
const { session } = await createAgentSession({
	cwd: project,
	agentDir,
	resourceLoader: loader,
	model: faux.getModel(),
	sessionManager: SessionManager.inMemory(),
	authStorage,
	modelRegistry: ModelRegistry.inMemory(authStorage),
});
const calls = [];
session.subscribe((event) => {
	if (event.type === "tool_execution_end") {
		const text = (event.result?.content ?? []).map((c) => c.text ?? "").join("");
		calls.push({ tool: event.toolName, isError: event.isError, text });
	}
});
await session.prompt("compile the cases");
const skills = loader.getSkills();
console.log(
	JSON.stringify({
		extensionErrors: loader.getExtensions().errors,
		skills: skills.skills.map((s) => ({ name: s.name, filePath: s.filePath })),
		tools: session.getAllTools().map((t) => t.name).filter((n) => n.startsWith("cex_")),
		calls,
		project,
	}),
);
