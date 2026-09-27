"""install.py：发行根落位、重复安装与升级、三个 harness 的挂载、依赖检查。

全部在临时 HOME 里跑：claude / pi 默认用记录参数的假 CLI——假 claude 照真 Claude Code 的做法按
插件版本号缓存插件副本（版本号没变，update 什么都不做）；本机有 claude CLI 时另用真 CLI（隔离的
CLAUDE_CONFIG_DIR）装一遍、改一处内容再升级一遍，设了 PI_NODE_MODULES 时用真 pi（隔离的
PI_CODING_AGENT_DIR）。
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


_FAKE_CLAUDE = """
import json, shutil, sys
from pathlib import Path
state_path = Path(STATE)
state = json.loads(state_path.read_text()) if state_path.exists() else {"markets": {}, "plugins": {}}
args = sys.argv[1:]

def save():
    state_path.write_text(json.dumps(state))

def fetch(plugin_id):
    source = Path(state["markets"][plugin_id.split("@", 1)[1]])
    version = json.loads((source / ".claude-plugin" / "plugin.json").read_text())["version"]
    return source, version

if args[:3] == ["plugin", "marketplace", "list"]:
    print(LISTING if LISTING is not None else json.dumps(
        [{"name": k, "source": "directory", "path": v} for k, v in state["markets"].items()]))
elif args[:3] == ["plugin", "marketplace", "add"]:
    name = json.loads((Path(args[3]) / ".claude-plugin" / "marketplace.json").read_text())["name"]
    state["markets"][name] = args[3]
    save()
elif args[:3] == ["plugin", "marketplace", "update"]:
    pass
elif args[:2] == ["plugin", "list"]:
    print(json.dumps([{"id": k, **v} for k, v in state["plugins"].items()]))
elif args[:2] in (["plugin", "install"], ["plugin", "update"]):
    plugin_id = args[2]
    source, version = fetch(plugin_id)
    current = state["plugins"].get(plugin_id)
    if args[1] == "update" and current and current["version"] == version:
        print(f"already at the latest version ({version})")  # 真 Claude Code 也是这样：版本号没变不换缓存
    else:
        cache = Path(CACHE) / version.replace("+", "-")
        shutil.rmtree(cache, ignore_errors=True)
        shutil.copytree(source, cache)
        state["plugins"][plugin_id] = {"version": version, "installPath": str(cache)}
        save()
"""


def _fake_cli(bin_dir: Path, name: str, log: Path, listing: str | None = None) -> None:
    script = bin_dir / name
    body = ""
    if name == "claude":
        body = (f"STATE = {str(log.with_name('claude_state.json'))!r}\n"
                f"CACHE = {str(log.with_name('claude_cache'))!r}\n"
                f"LISTING = {listing!r}\n" + _FAKE_CLAUDE)
    script.write_text(textwrap.dedent(f"""\
        #!{sys.executable}
        import json, sys
        with open({str(log)!r}, "a", encoding="utf-8") as f:
            f.write(json.dumps([{name!r}, *sys.argv[1:]]) + "\\n")
        """) + body, encoding="utf-8")
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


def test_dry_run_changes_nothing_but_runs_the_read_only_checks(box):
    rc, report = _install(box, "--harness", "all", "--dry-run")
    assert rc == 0 and report["dry_run"] is True
    assert not box["dist"].exists() and not (box["home"] / ".circle").exists()
    assert _calls(box) == [["claude", "plugin", "marketplace", "list", "--json"],
                           ["claude", "plugin", "list", "--json"]], "only read-only probes ran"
    assert any("marketplace add" in a for a in report["harnesses"]["claude"]["actions"])
    assert report["dependencies"]["missing"] == [], "the dependency probe ran too"
    assert "+" in report["distribution"]["plugin_version"]


def test_dry_run_reports_what_the_real_run_would_refuse(box, tmp_path):
    bin_dir = tmp_path / "bin2"
    bin_dir.mkdir()
    _fake_cli(bin_dir, "claude", box["log"],
              listing=json.dumps([{"name": "compile-excel", "path": "/old/copy"}]))
    env = {**box["env"], "PATH": f"{bin_dir}{os.pathsep}{box['env']['PATH']}"}
    rc, report = _install(box, "--harness", "claude", "--dry-run", env=env)
    assert rc == 1 and "/old/copy" in report["harnesses"]["claude"]["error"]


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
        ["claude", "plugin", "list", "--json"],
        ["claude", "plugin", "install", "compile-excel@compile-excel"],
        ["claude", "plugin", "list", "--json"],
        ["pi", "install", str(dist)],
    ]
    claude = report["harnesses"]["claude"]
    stamped = json.loads((dist / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert claude["plugin_version"] == stamped["version"] != "0.1.0"
    assert stamped["version"].startswith("0.1.0+")

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


def _source_copy(tmp_path: Path) -> Path:
    """可改动的源检出副本（git 跟踪 + 未忽略的新文件，不含测试），用来模拟"发了新版本"。"""
    listed = subprocess.run(["git", "-C", str(REPO_ROOT), "ls-files", "-z", "--cached", "--others",
                             "--exclude-standard"], capture_output=True, check=True).stdout
    src = tmp_path / "src"
    for rel in filter(None, listed.decode("utf-8").split("\0")):
        path = REPO_ROOT / rel
        if rel.startswith("tests/") or not path.is_file() or path.is_symlink():
            continue
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, src / rel)
    return src


def test_an_upgrade_reaches_claude_codes_plugin_cache(box, tmp_path):
    """Claude Code 跑的是按版本号缓存的副本：内容变了版本号就得变，升级后缓存里是新内容。"""
    src = _source_copy(tmp_path)
    run = lambda *a: subprocess.run([sys.executable, str(src / "install.py"), *a],  # noqa: E731
                                    capture_output=True, text=True, timeout=600, env=box["env"])
    first = run("--harness", "claude")
    assert first.returncode == 0, first.stdout + first.stderr
    report = json.loads(first.stdout)["harnesses"]["claude"]
    cache = Path(report["cache"])
    assert (cache / "cex_client" / "tools.py").read_bytes() == (src / "cex_client" / "tools.py").read_bytes()
    with open(src / "cex_client" / "tools.py", "a", encoding="utf-8") as stream:
        stream.write("\n# a new release\n")
    upgraded = run("--harness", "claude", "--upgrade")
    assert upgraded.returncode == 0, upgraded.stdout + upgraded.stderr
    after = json.loads(upgraded.stdout)["harnesses"]["claude"]
    assert after["ok"] and after["plugin_version"] != report["plugin_version"]
    assert ["claude", "plugin", "update", "compile-excel@compile-excel"] in _calls(box)
    fresh = Path(after["cache"])
    assert (fresh / "cex_client" / "tools.py").read_text(encoding="utf-8").endswith("# a new release\n")
    assert "restart" in after["note"] and "in place" not in json.dumps(after)


def test_only_distributable_files_are_installed(box, tmp_path):
    src = _source_copy(tmp_path)
    junk = ["compile_outputs/b1/case.xlsx", ".compile-excel/token.json", "lease.json",
            "cex_client/__pycache__/x.pyc", ".pytest_cache/v/x", "node_modules/p/index.js",
            "skills/compile-excel/.compile-excel/config.json", "tests/test_x.py"]
    for rel in junk:
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text("x", encoding="utf-8")
    proc = subprocess.run([sys.executable, str(src / "install.py"), "--harness", "circle"],
                          capture_output=True, text=True, timeout=600, env=box["env"])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    for rel in junk:
        assert not (box["dist"] / rel).exists(), rel
    skill = box["home"] / ".circle" / "skills" / "compile-excel"
    assert (skill / "SKILL.md").is_file() and not (skill / ".compile-excel").exists()


def test_a_failed_dependency_install_is_reported_as_json(box, tmp_path):
    fake = tmp_path / "fake-python"
    fake.write_text("#!/bin/sh\n"
                    'if [ "$1" = "-c" ]; then echo "openpyxl"; exit 0; fi\n'
                    'echo "pip exploded" >&2; exit 1\n', encoding="utf-8")
    fake.chmod(0o755)
    proc = subprocess.run([sys.executable, str(INSTALL), "--harness", "circle", "--install-deps"],
                          capture_output=True, text=True, timeout=600,
                          env={**box["env"], "CEX_PYTHON": str(fake)})
    report = json.loads(proc.stdout)
    assert proc.returncode == 1 and "Traceback" not in proc.stderr
    assert report["dependencies"]["ok"] is False and "pip exploded" in report["dependencies"]["error"]


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
    assert plugins[0]["mcpServers"]["compile-excel"] == {
        "command": "sh", "args": ["${CLAUDE_PLUGIN_ROOT}/bin/cex_mcp"]}
    assert plugins[0]["version"] == report["harnesses"]["claude"]["plugin_version"]
    rc, again = _install(box, "--harness", "claude", "--upgrade", env=env)
    assert rc == 0 and again["ok"], again


def test_real_claude_cli_picks_up_a_changed_release(box, tmp_path):
    real = shutil.which("claude", path=os.environ.get("PATH"))
    if real is None:
        pytest.skip("本机没有 claude CLI")
    src = _source_copy(tmp_path)
    env = {**box["env"], "PATH": os.environ["PATH"], "CLAUDE_CONFIG_DIR": str(box["tmp"] / "cc")}
    run = lambda *a: subprocess.run([sys.executable, str(src / "install.py"), *a],  # noqa: E731
                                    capture_output=True, text=True, timeout=600, env=env)
    first = run("--harness", "claude")
    assert first.returncode == 0, first.stdout + first.stderr
    with open(src / "cex_client" / "tools.py", "a", encoding="utf-8") as stream:
        stream.write("\n# a new release\n")
    upgraded = run("--harness", "claude", "--upgrade")
    assert upgraded.returncode == 0, upgraded.stdout + upgraded.stderr
    listed = subprocess.run(["claude", "plugin", "list", "--json"], capture_output=True, text=True,
                            timeout=120, env=env)
    entry = json.loads(listed.stdout)[0]
    cached = Path(entry["installPath"]) / "cex_client" / "tools.py"
    assert cached.read_text(encoding="utf-8").endswith("# a new release\n"), entry


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
