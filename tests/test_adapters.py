"""三个 harness 适配器：工具集与 tool_specs.json 一致，清单能被各 harness 接受，调用语义一致。

- pi：生成的 TypeBox 定义不漂移；设了 PI_NODE_MODULES（装有 @mariozechner/pi-coding-agent 与
  typescript 的 node_modules）时，用真 pi 的类型做 tsc 严格检查，并用 pi SDK + faux 脚本模型
  真跑一遍包（tests/adapters/pi_e2e.mjs）。
- Claude Code：插件与 marketplace 清单自洽；本机有 claude CLI 时跑 `claude plugin validate --strict`。
- circle：按扩展 API 契约用假 api 注册并调用；有同级 circle 检出（或 CIRCLE_ROOT）时
  再用 circle 真实的扩展宿主加载一遍。extension.py 对 0.5.0 及更早（Python 版），
  extension.mjs 对 1.0 起（TypeScript 版，要本机有 node）。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import REPO_ROOT

SPECS = json.loads((REPO_ROOT / "cex_client" / "tool_specs.json").read_text(encoding="utf-8"))["tools"]
PI_NODE_MODULES = os.environ.get("PI_NODE_MODULES", "")
CIRCLE_ROOT = Path(os.environ.get("CIRCLE_ROOT") or REPO_ROOT.parent / "circle")
NODE = shutil.which("node")
CIRCLE_MJS = REPO_ROOT / "adapters" / "circle" / "extension.mjs"
# 假 circle api（TypeScript 版的 registerTool 形状）：注册后按 argv 里的脚本调用工具，结果打成 JSON
_FAKE_TS_API = """
const [url, calls] = process.argv.slice(1);
class ToolError extends Error {}
const tools = {};
const api = {
  ToolError,
  registerTool(name, description, parameters, execute, options = {}) {
    if (tools[name]) throw new Error('duplicate ' + name);
    tools[name] = { description, parameters, execute, readOnly: Boolean(options.readOnly) };
  },
};
await (await import(url)).register(api);
const results = [];
for (const [name, args, abortAfter] of JSON.parse(calls || '[]')) {
  const controller = new AbortController();
  if (abortAfter !== undefined) setTimeout(() => controller.abort(), abortAfter);
  const started = Date.now();
  try {
    results.push({ ok: await tools[name].execute(args, { signal: controller.signal }) });
  } catch (error) {
    results.push({ error: error.message, toolError: error instanceof ToolError,
                   name: error.name, ms: Date.now() - started });
  }
}
console.log(JSON.stringify({
  tools: Object.entries(tools).map(([name, t]) => [name, t.parameters, t.readOnly]),
  results,
}));
"""


def _with_specs(root: Path) -> Path:
    """假发行根也要有 tool_specs.json：extension.mjs 注册时从 CEX_HOME 读它。"""
    (root / "cex_client").mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO_ROOT / "cex_client" / "tool_specs.json", root / "cex_client" / "tool_specs.json")
    return root


def _run_ts_adapter(entry: Path, calls: list, env: dict[str, str] | None = None) -> dict:
    if NODE is None:
        pytest.skip("node is not installed")
    proc = subprocess.run([NODE, "--input-type=module", "-e", _FAKE_TS_API, entry.as_uri(),
                           json.dumps(calls)], capture_output=True, text=True, timeout=120,
                          env=env or _env_without_workspace())
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return json.loads(proc.stdout.strip().splitlines()[-1])


def _env_without_workspace() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if k not in ("CEX_WORKSPACE", "CEX_HOME")}


# ── pi ──────────────────────────────────────────────────────────────

def test_generated_pi_tools_match_the_specs():
    proc = subprocess.run([sys.executable, str(REPO_ROOT / "tools" / "gen_adapters.py"), "--check"],
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, "运行 tools/gen_adapters.py 重新生成：\n" + proc.stdout


def test_pi_package_manifest():
    package = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))
    assert "pi-package" in package["keywords"]
    for rel in package["pi"]["extensions"]:
        assert (REPO_ROOT / rel).is_file(), rel
    for rel in package["pi"]["skills"]:
        assert (REPO_ROOT / rel / "compile-excel" / "SKILL.md").is_file(), rel
    # pi 自带这几个核心包；标成可选 peer，pi install 跑 npm install 时不会再装一份
    for name in package["peerDependencies"]:
        assert package["peerDependenciesMeta"][name]["optional"] is True
    assert not package.get("dependencies")
    # 没有锁文件：Claude Code 装插件时不会去跑 npm install
    assert not any((REPO_ROOT / f).exists() for f in ("package-lock.json", "bun.lock",
                                                      "npm-shrinkwrap.json"))


def _pi_workdir(tmp_path: Path) -> Path:
    modules = Path(PI_NODE_MODULES)
    if not (modules / "@mariozechner" / "pi-coding-agent").is_dir() or shutil.which("node") is None:
        pytest.skip("设 PI_NODE_MODULES 指向装有 @mariozechner/pi-coding-agent 的 node_modules")
    work = tmp_path / "pi"
    work.mkdir()
    (work / "node_modules").symlink_to(modules)
    return work


def test_pi_extension_typechecks_against_real_pi_types(tmp_path):
    work = _pi_workdir(tmp_path)
    tsc = Path(PI_NODE_MODULES) / ".bin" / "tsc"
    if not tsc.exists():
        pytest.skip("PI_NODE_MODULES 里没有 typescript")
    (work / "tsconfig.json").write_text(json.dumps({
        "compilerOptions": {
            "target": "ES2022", "module": "ESNext", "moduleResolution": "Bundler", "strict": True,
            "noEmit": True, "skipLibCheck": True, "baseUrl": str(work),
            "paths": {"*": ["node_modules/*", "node_modules/@types/*"]},
            "typeRoots": [str(work / "node_modules" / "@types")], "types": ["node"]},
        "files": [str(REPO_ROOT / "adapters" / "pi" / "index.ts"),
                  str(REPO_ROOT / "adapters" / "pi" / "tools.generated.ts")]}), encoding="utf-8")
    proc = subprocess.run([str(tsc), "-p", str(work / "tsconfig.json")], capture_output=True,
                          text=True, timeout=300)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_pi_runs_the_package_with_a_scripted_model(tmp_path):
    work = _pi_workdir(tmp_path)
    shutil.copy2(REPO_ROOT / "tests" / "adapters" / "pi_e2e.mjs", work / "pi_e2e.mjs")
    proc = subprocess.run(["node", str(work / "pi_e2e.mjs"), str(REPO_ROOT)], capture_output=True,
                          text=True, timeout=300, cwd=work, env=_env_without_workspace())
    assert proc.returncode == 0, proc.stdout[-2000:] + proc.stderr[-2000:]
    report = json.loads(proc.stdout.strip().splitlines()[-1])
    assert report["extensionErrors"] == []
    assert [s["name"] for s in report["skills"]] == ["compile-excel"]
    assert set(report["tools"]) == {s["name"] for s in SPECS}
    calls = [(c["tool"], c["isError"]) for c in report["calls"]]
    # 没有工作区 → 失败；建工作区 → 成功；按 pi 会话的 cwd 找到工作区 → 成功；未登录同步 → 失败
    assert calls == [("cex_status", True), ("cex_init", False), ("cex_status", False),
                     ("cex_sync", True)]
    assert "not logged in" in report["calls"][3]["text"]


# ── Claude Code ─────────────────────────────────────────────────────

def test_claude_plugin_and_marketplace_manifests():
    plugin = json.loads((REPO_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    market = json.loads((REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    package = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))
    assert plugin["name"] == "compile-excel" and plugin["version"] == package["version"]
    server = plugin["mcpServers"]["compile-excel"]
    script = server["args"][0]
    assert script.startswith("${CLAUDE_PLUGIN_ROOT}/")
    assert (REPO_ROOT / script.removeprefix("${CLAUDE_PLUGIN_ROOT}/")).is_file()
    # MCP 配置只放在插件清单里：仓根的 .mcp.json 会在有人于本仓里开 Claude Code 时被当成项目配置
    assert not (REPO_ROOT / ".mcp.json").exists()
    entry = next(p for p in market["plugins"] if p["name"] == plugin["name"])
    assert entry["source"] == "./"
    assert (REPO_ROOT / "skills" / "compile-excel" / "SKILL.md").is_file()


def test_claude_accepts_the_plugin():
    if shutil.which("claude") is None:
        pytest.skip("本机没有 claude CLI")
    proc = subprocess.run(["claude", "plugin", "validate", str(REPO_ROOT), "--strict"],
                          capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stdout + proc.stderr


# ── circle ──────────────────────────────────────────────────────────

class _FakeCircleApi:
    class ToolError(Exception):
        pass

    def __init__(self):
        self.tools: dict[str, dict] = {}

    def register_tool(self, *, name, description, parameters, execute, read_only=False):
        assert name not in self.tools
        self.tools[name] = {"description": description, "parameters": parameters,
                            "execute": execute, "read_only": read_only}


def _load_circle_extension():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "cex_circle_extension", REPO_ROOT / "adapters" / "circle" / "extension.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_circle_extension_registers_the_spec_tools_and_reports_failures(tmp_path, monkeypatch):
    monkeypatch.delenv("CEX_WORKSPACE", raising=False)
    monkeypatch.delenv("CEX_HOME", raising=False)
    api = _FakeCircleApi()
    _load_circle_extension().register(api)
    assert list(api.tools) == [s["name"] for s in SPECS]
    for spec in SPECS:
        tool = api.tools[spec["name"]]
        assert tool["parameters"] == spec["input_schema"]
        assert tool["read_only"] is bool(spec.get("read_only"))

    project = tmp_path / "project"
    project.mkdir()
    with pytest.raises(api.ToolError, match="No workspace here"):
        api.tools["cex_status"]["execute"]({"workspace": str(project)})
    created = api.tools["cex_init"]["execute"]({"workspace": str(project),
                                                "server": "http://127.0.0.1:9", "device_build": "B_1"})
    assert created["ok"] is True
    status = api.tools["cex_status"]["execute"]({"workspace": str(project)})
    assert status["logged_in"] is False and status["device_build"] == "B_1"
    with pytest.raises(api.ToolError, match="not logged in"):
        api.tools["cex_sync"]["execute"]({"workspace": str(project)})


def _recording_cex_tool(root: Path) -> Path:
    """假发行根：bin/cex_tool 把收到的 argv 与 stdin 长度原样回显。"""
    (root / "bin").mkdir(parents=True)
    (root / "bin" / "cex_tool").write_text(
        "import json, sys\n"
        "data = sys.stdin.read()\n"
        "print(json.dumps({'ok': True, 'argv': sys.argv[1:], 'stdin': len(data),\n"
        "                  'keys': sorted(json.loads(data or '{}'))}))\n", encoding="utf-8")
    return root


def test_circle_passes_arguments_on_stdin_and_reports_a_missing_interpreter(tmp_path, monkeypatch):
    """整批用例这类大参数经 stdin 传（Linux 单个命令行参数上限 128 KiB）；解释器起不来报成
    ToolError，而不是把 OSError 漏给宿主。"""
    root = _recording_cex_tool(tmp_path / "dist")
    monkeypatch.setenv("CEX_PYTHON", sys.executable)
    module = _load_circle_extension()
    execute = module.make_executor(root, "cex_recompose_submit_cases", _FakeCircleApi.ToolError)
    big = {"out_name": "b1", "cases": [{"autoid": str(i), "text": "x" * 1000} for i in range(300)]}
    out = execute(big)
    assert out["argv"] == ["cex_recompose_submit_cases", "-"]
    assert out["stdin"] > 300_000 and out["keys"] == ["cases", "out_name"]
    monkeypatch.setenv("CEX_PYTHON", str(tmp_path / "no-such-python"))
    broken = module.make_executor(root, "cex_status", _FakeCircleApi.ToolError)
    with pytest.raises(_FakeCircleApi.ToolError, match="could not start"):
        broken({})


def test_circle_mjs_registers_the_spec_tools_and_reports_failures(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    out = _run_ts_adapter(CIRCLE_MJS, [
        ["cex_status", {"workspace": str(project)}],
        ["cex_init", {"workspace": str(project), "server": "http://127.0.0.1:9",
                      "device_build": "B_1"}],
        ["cex_status", {"workspace": str(project)}],
        ["cex_sync", {"workspace": str(project)}],
    ])
    assert out["tools"] == [[s["name"], s["input_schema"], bool(s.get("read_only"))] for s in SPECS]
    missing, created, status, sync = out["results"]
    assert missing["toolError"] and "No workspace here" in missing["error"]
    assert created["ok"]["ok"] is True
    assert status["ok"]["logged_in"] is False and status["ok"]["device_build"] == "B_1"
    assert sync["toolError"] and "not logged in" in sync["error"]


def test_circle_mjs_passes_arguments_on_stdin_and_reports_a_missing_interpreter(tmp_path):
    root = _with_specs(_recording_cex_tool(tmp_path / "dist"))
    big = {"out_name": "b1", "cases": [{"autoid": str(i), "text": "x" * 1000} for i in range(300)]}
    env = {**_env_without_workspace(), "CEX_HOME": str(root), "CEX_PYTHON": sys.executable}
    out = _run_ts_adapter(CIRCLE_MJS, [["cex_recompose_submit_cases", big]], env)
    reply = out["results"][0]["ok"]
    assert reply["argv"] == ["cex_recompose_submit_cases", "-"]
    assert reply["stdin"] > 300_000 and reply["keys"] == ["cases", "out_name"]
    env["CEX_PYTHON"] = str(tmp_path / "no-such-python")
    out = _run_ts_adapter(CIRCLE_MJS, [["cex_status", {}]], env)
    assert out["results"][0]["toolError"] and "could not start" in out["results"][0]["error"]


def test_circle_mjs_stops_the_tool_process_when_the_call_is_cancelled(tmp_path):
    """esc 取消一次调用：子进程收到 SIGTERM，调用以 AbortError 结束，不等它跑完。"""
    root = tmp_path / "dist"
    (root / "bin").mkdir(parents=True)
    (root / "bin" / "cex_tool").write_text("import time\ntime.sleep(60)\n", encoding="utf-8")
    _with_specs(root)
    env = {**_env_without_workspace(), "CEX_HOME": str(root), "CEX_PYTHON": sys.executable}
    out = _run_ts_adapter(CIRCLE_MJS, [["cex_status", {}, 300]], env)
    result = out["results"][0]
    assert result["name"] == "AbortError" and result["ms"] < 10_000


def test_cex_tool_reads_large_arguments_from_stdin(tmp_path):
    ws_dir = tmp_path / "project"
    ws_dir.mkdir()
    args = {"workspace": str(ws_dir), "server": "http://127.0.0.1:9", "device_build": "B_1",
            "channel": "stable"}
    proc = subprocess.run([sys.executable, str(REPO_ROOT / "bin" / "cex_tool"), "cex_init", "-"],
                          input=json.dumps(args), capture_output=True, text=True, timeout=60,
                          env=_env_without_workspace())
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert json.loads(proc.stdout)["workspace"] == str(ws_dir.resolve())
    big = json.dumps({"workspace": str(ws_dir), "commands": ["show version"] * 20000})
    proc = subprocess.run([sys.executable, str(REPO_ROOT / "bin" / "cex_tool"), "cex_cmd_check", "-"],
                          input=big, capture_output=True, text=True, timeout=60,
                          env=_env_without_workspace())
    reply = json.loads(proc.stdout)
    assert len(big) > 200_000 and reply["ok"] is False and "20000" in reply["error"]
    bad = subprocess.run([sys.executable, str(REPO_ROOT / "bin" / "cex_tool"), "cex_status", "-"],
                         input="{not json", capture_output=True, text=True, timeout=60)
    assert bad.returncode == 2 and "bad arguments" in bad.stdout


def test_the_claude_plugin_launcher_honours_cex_python(tmp_path):
    """插件清单不写死 python3：MCP 入口按 CEX_PYTHON 选解释器。"""
    plugin = json.loads((REPO_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    server = plugin["mcpServers"]["compile-excel"]
    assert "python" not in server["command"]
    launcher = REPO_ROOT / server["args"][0].removeprefix("${CLAUDE_PLUGIN_ROOT}/")
    fake = tmp_path / "fake-python"
    fake.write_text("#!/bin/sh\necho \"chosen $1\"\n", encoding="utf-8")
    fake.chmod(0o755)
    proc = subprocess.run([server["command"], str(launcher)], capture_output=True, text=True,
                          timeout=60, env={**os.environ, "CEX_PYTHON": str(fake)})
    assert proc.stdout.strip() == f"chosen {launcher.parent / 'cex_mcp_proxy.py'}"
    message = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    proc = subprocess.run([server["command"], str(launcher)], input=message + "\n",
                          capture_output=True, text=True, timeout=60,
                          env={**os.environ, "CEX_PYTHON": sys.executable})
    assert json.loads(proc.stdout)["result"]["serverInfo"]["name"] == "compile-excel"


def test_circle_extension_through_the_real_circle_host(tmp_path, monkeypatch):
    """有同级 circle 检出时，用 circle 真实的扩展宿主加载本仓扩展（不再只靠假 api）。"""
    if not (CIRCLE_ROOT / "circle" / "extensions.py").is_file():
        pytest.skip(f"no circle checkout with the extension API at {CIRCLE_ROOT} (set CIRCLE_ROOT)")
    monkeypatch.delenv("CEX_WORKSPACE", raising=False)
    monkeypatch.delenv("CEX_HOME", raising=False)
    monkeypatch.syspath_prepend(str(CIRCLE_ROOT))
    extensions = pytest.importorskip("circle.extensions")
    home = tmp_path / "circle-home"
    entry = home / "extensions" / "compile-excel" / "extension.py"
    entry.parent.mkdir(parents=True)
    # 与 install.py 写的入口同形：转到本仓里的实现
    entry.write_text("import runpy\n\nregister = runpy.run_path("
                     f"{str(REPO_ROOT / 'adapters' / 'circle' / 'extension.py')!r})['register']\n",
                     encoding="utf-8")
    host = extensions.ExtensionHost(home=home, workspace=tmp_path, trusted=False).load()
    assert [e.error for e in host.extensions] == [""]
    assert [t.name for t in host.tool_specs()] == [s["name"] for s in SPECS]
    assert set(host.interrupt_on()) == {s["name"] for s in SPECS if not s.get("read_only")}
    status = next(t for t in host.tools() if t.name == "cex_status")
    message = status.invoke({"type": "tool_call", "name": "cex_status", "id": "c1",
                             "args": {"workspace": str(tmp_path)}})
    assert message.status == "error" and "No workspace here" in message.content


def test_circle_mjs_through_the_real_typescript_host(tmp_path):
    """有同级 circle 1.0 检出（src/extensions.ts，装好 node_modules）时，用它真实的扩展宿主加载
    install.py 写的那种 extension.mjs 入口。"""
    host_source = CIRCLE_ROOT / "src" / "extensions.ts"
    if NODE is None or not host_source.is_file() or not (CIRCLE_ROOT / "node_modules" / "tsx").is_dir():
        pytest.skip(f"no circle 1.0 checkout with node_modules at {CIRCLE_ROOT} (set CIRCLE_ROOT)")
    home = tmp_path / "circle-home"
    entry = home / "extensions" / "compile-excel" / "extension.mjs"
    entry.parent.mkdir(parents=True)
    entry.write_text(f"const impl = {json.dumps(CIRCLE_MJS.as_uri())};\n"
                     "export async function register(api) {\n"
                     "  return (await import(impl + '?load=' + Date.now())).register(api);\n"
                     "}\n", encoding="utf-8")
    script = f"""
import {{ ExtensionHost }} from {json.dumps(host_source.as_uri())};
const host = await new ExtensionHost({{ home: {json.dumps(str(home))},
  workspace: {json.dumps(str(tmp_path))}, trusted: false }}).load();
const tools = host.tools();
const status = tools.find((tool) => tool.name === 'cex_status');
let error = '';
try {{
  await status.run({{ workspace: {json.dumps(str(tmp_path))} }},
    {{ signal: new AbortController().signal, sessionId: 's' }});
}} catch (caught) {{ error = caught.constructor.name + ': ' + caught.message; }}
console.log(JSON.stringify({{
  errors: host.extensions.map((ext) => ext.error),
  tools: tools.map((tool) => [tool.name, tool.approval, tool.effect]),
  error,
}}));
"""
    proc = subprocess.run([NODE, "--import", "tsx", "--input-type=module", "-e", script],
                          capture_output=True, text=True, timeout=120, cwd=CIRCLE_ROOT,
                          env=_env_without_workspace())
    assert proc.returncode == 0, proc.stdout + proc.stderr
    out = json.loads(proc.stdout.strip().splitlines()[-1])
    assert out["errors"] == [""]
    assert out["tools"] == [[s["name"], not s.get("read_only"),
                             "read" if s.get("read_only") else "unknown"] for s in SPECS]
    assert out["error"].startswith("ToolError") and "No workspace here" in out["error"]
