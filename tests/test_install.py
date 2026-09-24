"""install.py：发行根落位、重复安装与升级、三个 harness 的挂载、依赖检查。

全部在临时 HOME 里跑：claude / pi 默认用记录参数的假 CLI；本机有 claude CLI 时另用真 CLI
（隔离的 CLAUDE_CONFIG_DIR）装一遍，设了 PI_NODE_MODULES 时用真 pi（隔离的 PI_CODING_AGENT_DIR）。
"""

from __future__ import annotations

import json
import os
import runpy
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from conftest import REPO_ROOT

INSTALL = REPO_ROOT / "install.py"
SPEC_NAMES = [t["name"] for t in json.loads(
    (REPO_ROOT / "cex_client" / "tool_specs.json").read_text(encoding="utf-8"))["tools"]]


def _fake_cli(bin_dir: Path, name: str, log: Path, listing: str = "[]") -> None:
    script = bin_dir / name
    script.write_text(textwrap.dedent(f"""\
        #!{sys.executable}
        import json, sys
        with open({str(log)!r}, "a", encoding="utf-8") as f:
            f.write(json.dumps([{name!r}, *sys.argv[1:]]) + "\\n")
        if sys.argv[1:4] == ["plugin", "marketplace", "list"]:
            print({listing!r})
        """), encoding="utf-8")
    script.chmod(0o755)


@pytest.fixture()
def box(tmp_path):
    home = tmp_path / "home"
    bin_dir = tmp_path / "bin"
    home.mkdir()
    bin_dir.mkdir()
    log = tmp_path / "cli.log"
    _fake_cli(bin_dir, "claude", log)
    _fake_cli(bin_dir, "pi", log)
    env = {k: v for k, v in os.environ.items()
           if k not in ("CEX_HOME", "CEX_WORKSPACE", "CEX_PI", "CLAUDE_CONFIG_DIR",
                        "PI_CODING_AGENT_DIR")}
    env.update(HOME=str(home), CIRCLE_HOME=str(home / ".circle"),
               PATH=f"{bin_dir}{os.pathsep}{env.get('PATH', '')}", CEX_PYTHON=sys.executable)
    dist = home / ".local" / "share" / "compile-excel" / "current"
    return {"home": home, "env": env, "log": log, "dist": dist, "tmp": tmp_path}


def _install(box, *args: str, env: dict | None = None) -> tuple[int, dict]:
    proc = subprocess.run([sys.executable, str(INSTALL), *args], capture_output=True, text=True,
                          timeout=600, env=env or box["env"])
    return proc.returncode, json.loads(proc.stdout)


def _calls(box) -> list[list[str]]:
    if not box["log"].exists():
        return []
    return [json.loads(line) for line in box["log"].read_text(encoding="utf-8").splitlines()]


class _FakeCircleApi:
    class ToolError(Exception):
        pass

    def __init__(self):
        self.tools: dict[str, dict] = {}

    def register_tool(self, **kwargs):
        self.tools[kwargs["name"]] = kwargs


def test_dry_run_changes_nothing(box):
    rc, report = _install(box, "--harness", "all", "--dry-run")
    assert rc == 0 and report["dry_run"] is True
    assert not box["dist"].exists() and not (box["home"] / ".circle").exists()
    assert _calls(box) == []
    assert any("marketplace add" in a for a in report["harnesses"]["claude"]["actions"])


def test_all_harnesses_then_rerun_and_upgrade(box):
    rc, report = _install(box, "--harness", "all")
    assert rc == 0 and report["ok"], report
    dist = box["dist"]
    assert (dist / "cex_core" / "__init__.py").is_file() and (dist / ".cex_install.json").is_file()
    assert not (dist / "tests").exists() and not (dist / ".git").exists()
    assert os.access(dist / "bin" / "cex_tool", os.X_OK)
    # 抽取时外置的生产身份字面只给服务端生成链用，不发给客户端
    assert not (dist / "cex_core" / "engine" / "_identities.json").exists()
    assert report["verify"] == {"ok": True, "tools": len(SPEC_NAMES)}
    assert _calls(box) == [
        ["claude", "plugin", "marketplace", "list", "--json"],
        ["claude", "plugin", "marketplace", "add", str(dist)],
        ["claude", "plugin", "install", "compile-excel@compile-excel"],
        ["pi", "install", str(dist)],
    ]

    circle = box["home"] / ".circle"
    for name in ("compile-excel", "mindmap-recompose"):
        skill = circle / "skills" / name
        assert (skill / "SKILL.md").is_file()
        assert (skill / ".cex_home").read_text(encoding="utf-8").strip() == str(dist)
    api = _FakeCircleApi()
    runpy.run_path(str(circle / "extensions" / "compile-excel" / "extension.py"))["register"](api)
    assert list(api.tools) == SPEC_NAMES
    project = box["tmp"] / "project"
    project.mkdir()
    made = api.tools["cex_init"]["execute"]({"workspace": str(project),
                                             "server": "http://127.0.0.1:9", "device_build": "B_1"})
    assert made["ok"] is True

    rc, again = _install(box, "--harness", "circle")
    assert rc == 3 and again["installed_version"] == report["distribution"]["version"]
    (dist / "stale_marker").write_text("x", encoding="utf-8")
    rc, upgraded = _install(box, "--harness", "circle", "--upgrade")
    assert rc == 0 and upgraded["ok"]
    assert not (dist / "stale_marker").exists()
    assert sorted(p.name for p in dist.parent.iterdir()) == ["current"]


def test_refuses_to_replace_what_it_did_not_write(box):
    box["dist"].mkdir(parents=True)
    (box["dist"] / "mine.txt").write_text("user data", encoding="utf-8")
    rc, report = _install(box, "--harness", "circle", "--upgrade")
    assert rc == 1 and "not written by this installer" in report["error"]
    assert (box["dist"] / "mine.txt").read_text(encoding="utf-8") == "user data"

    foreign = box["home"] / ".circle" / "skills" / "compile-excel"
    foreign.mkdir(parents=True)
    (foreign / "SKILL.md").write_text("someone else's skill", encoding="utf-8")
    rc, report = _install(box, "--harness", "circle", "--prefix", str(box["tmp"] / "dist2"))
    assert rc == 1 and "not written by this installer" in report["harnesses"]["circle"]["error"]
    assert (foreign / "SKILL.md").read_text(encoding="utf-8") == "someone else's skill"


def test_marketplace_pointing_elsewhere_is_reported_not_overwritten(box, tmp_path):
    bin_dir = tmp_path / "bin2"
    bin_dir.mkdir()
    _fake_cli(bin_dir, "claude", box["log"],
              listing=json.dumps([{"name": "compile-excel", "path": "/old/copy"}]))
    env = {**box["env"], "PATH": f"{bin_dir}{os.pathsep}{box['env']['PATH']}"}
    rc, report = _install(box, "--harness", "claude", env=env)
    assert rc == 1 and "/old/copy" in report["harnesses"]["claude"]["error"]
    assert not any(call[1:4] == ["plugin", "marketplace", "add"] for call in _calls(box))


def test_missing_dependencies_are_reported_not_installed(box, tmp_path):
    bare = tmp_path / "bare-python"
    bare.write_text(f"#!/bin/sh\nexec {sys.executable} -I -S \"$@\"\n", encoding="utf-8")
    bare.chmod(0o755)
    rc, report = _install(box, "--harness", "circle", env={**box["env"], "CEX_PYTHON": str(bare)})
    deps = report["dependencies"]
    assert set(deps["missing"]) == set(runpy.run_path(str(INSTALL))["DEP_MODULES"])
    assert "--install-deps" in deps["next"] and deps["actions"] == []


def test_real_claude_cli_installs_the_plugin(box):
    real = shutil.which("claude", path=os.environ.get("PATH"))
    if real is None:
        pytest.skip("本机没有 claude CLI")
    env = {**box["env"], "PATH": os.environ["PATH"], "CLAUDE_CONFIG_DIR": str(box["tmp"] / "cc")}
    rc, report = _install(box, "--harness", "claude", env=env)
    assert rc == 0 and report["ok"], report
    listed = subprocess.run(["claude", "plugin", "list", "--json"], capture_output=True, text=True,
                            timeout=120, env=env)
    plugins = json.loads(listed.stdout)
    assert [p["id"] for p in plugins] == ["compile-excel@compile-excel"]
    assert plugins[0]["mcpServers"]["compile-excel"]["args"] == [
        "${CLAUDE_PLUGIN_ROOT}/bin/cex_mcp_proxy.py"]
    rc, again = _install(box, "--harness", "claude", "--upgrade", env=env)
    assert rc == 0 and again["ok"], again


def test_real_pi_cli_registers_the_package(box):
    pi = Path(os.environ.get("PI_NODE_MODULES", "")) / ".bin" / "pi"
    if not pi.exists():
        pytest.skip("设 PI_NODE_MODULES 指向装有 pi 的 node_modules")
    agent_dir = box["tmp"] / "pi-agent"
    env = {**box["env"], "PATH": os.environ["PATH"], "CEX_PI": str(pi),
           "PI_CODING_AGENT_DIR": str(agent_dir)}
    rc, report = _install(box, "--harness", "pi", env=env)
    assert rc == 0 and report["ok"], report
    listed = subprocess.run([str(pi), "list"], capture_output=True, text=True, timeout=120, env=env)
    assert str(box["dist"]) in listed.stdout


def test_dependency_check_covers_every_requirement():
    """依赖自检只探 DEP_MODULES 里的包；requirements.txt 加了包而表里没有，缺依赖就查不出来。"""
    installer = runpy.run_path(str(INSTALL))
    names = set()
    for line in (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        spec = line.split("#", 1)[0].strip()
        if spec:
            names.add(spec.split(">", 1)[0].split("=", 1)[0].split("<", 1)[0].strip())
    assert names == set(installer["DEP_MODULES"])
