"""三个 harness 适配器：工具集与 tool_specs.json 一致，清单能被各 harness 接受，调用语义一致。

- pi：生成的 TypeBox 定义不漂移；设了 PI_NODE_MODULES（装有 @mariozechner/pi-coding-agent 与
  typescript 的 node_modules）时，用真 pi 的类型做 tsc 严格检查，并用 pi SDK + faux 脚本模型
  真跑一遍包（tests/adapters/pi_e2e.mjs）。
- Claude Code：插件与 marketplace 清单自洽；本机有 claude CLI 时跑 `claude plugin validate --strict`。
- circle：按扩展 API 契约用假 api 注册并调用；有同级 circle 检出（或 CIRCLE_ROOT）时
  再用 circle 真实的扩展宿主加载一遍。
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
