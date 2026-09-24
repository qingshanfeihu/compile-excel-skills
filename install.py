#!/usr/bin/env python3
"""compile-excel 安装器：把发行根放到固定位置，再挂进选定的 harness。

  python3 install.py --harness claude|pi|circle|all [--harness ...] [--upgrade] [--install-deps]
                     [--prefix DIR] [--dry-run]

1. 发行根（cex_core/、cex_client/、bin/、skills/、adapters/）复制到 --prefix
   （缺省 ~/.local/share/compile-excel/current）。已存在时不覆盖，退出码 3，除非给了 --upgrade；
   替换是先写旁边的 .new 再改名，旧版在新版就位后才删。各 harness 都引用这个固定路径，所以升级只换这一处。
2. 依赖：检查 python3 能否 import requirements.txt 里的包；缺了只报告，给了 --install-deps 才
   `python3 -m pip install --user -r requirements.txt`。
3. 按 harness 挂载：
   - claude：`claude plugin marketplace add <发行根>`（目录型 marketplace，插件就地加载）+
     `claude plugin install compile-excel@compile-excel`；
   - pi：`pi install <发行根>`（本地路径包，不复制）；
   - circle：skills/ 下每个技能拷到 $CIRCLE_HOME/skills/<名字>（写 .cex_home 指回发行根），
     扩展入口写到 $CIRCLE_HOME/extensions/compile-excel/extension.py（转到发行根里的实现）。
4. 自检后打印一段 JSON 报告。不读、不写任何口令；登录在首次使用时由 skill 引导。

退出码：0 全部成功；1 有 harness 失败；2 用法错误；3 已安装且没给 --upgrade。
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

SOURCE = Path(__file__).resolve().parent
HARNESSES = ("claude", "pi", "circle")
MARKETPLACE = "compile-excel"
PLUGIN = "compile-excel@compile-excel"
INSTALL_RECORD = ".cex_install.json"
SHIM_MARKER = "# compile-excel install.py"
# _identities.json：抽取时外置的生产身份字面，只给服务端生成链用，不发给客户端
_SKIP = {".git", "tests", "__pycache__", ".pytest_cache", ".ruff_cache", "node_modules",
         "_identities.json"}
SKILLS = ("compile-excel", "mindmap-recompose")
# requirements.txt 的包名 → import 名；依赖自检按这张表探（测试钉住两边一致）
DEP_MODULES = {"openpyxl": "openpyxl", "beautifulsoup4": "bs4", "PyYAML": "yaml",
               "pydantic": "pydantic", "langchain-core": "langchain_core"}
_REQUIRED = ("cex_core/__init__.py", "cex_client/tools.py", "bin/cex_tool", "bin/cex_mcp_proxy.py",
             *(f"skills/{name}/SKILL.md" for name in SKILLS),
             "adapters/circle/extension.py", "adapters/pi/index.ts",
             ".claude-plugin/plugin.json", "package.json", "requirements.txt")


class InstallError(Exception):
    pass


class Installer:
    def __init__(self, prefix: Path, dry_run: bool):
        self.prefix = prefix
        self.dry_run = dry_run
        self.python = os.environ.get("CEX_PYTHON") or shutil.which("python3") or sys.executable

    # ── 小工具 ────────────────────────────────────────────
    def run(self, argv: list[str], actions: list[str], *, timeout: int = 300,
            check: bool = True) -> subprocess.CompletedProcess | None:
        actions.append("$ " + " ".join(argv))
        if self.dry_run:
            return None
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        if check and proc.returncode != 0:
            raise InstallError(f"{argv[0]} {' '.join(argv[1:3])} failed (exit {proc.returncode}): "
                               f"{(proc.stderr or proc.stdout).strip()[-600:]}")
        return proc

    def version(self, root: Path) -> str:
        try:
            return json.loads((root / "package.json").read_text(encoding="utf-8"))["version"]
        except (OSError, ValueError, KeyError):
            return "unknown"

    # ── 1. 发行根 ─────────────────────────────────────────
    def place_distribution(self, upgrade: bool) -> dict[str, Any]:
        missing = [rel for rel in _REQUIRED if not (SOURCE / rel).is_file()]
        if missing:
            raise InstallError(f"source checkout is incomplete, missing: {', '.join(missing)}")
        report: dict[str, Any] = {"path": str(self.prefix), "version": self.version(SOURCE),
                                  "actions": []}
        if self.prefix.resolve() == SOURCE:
            report["actions"].append("running from the installed copy; nothing to copy")
            return report
        if self.prefix.exists():
            if not upgrade:
                raise AlreadyInstalled(self.prefix, self.version(self.prefix))
            if not (self.prefix / INSTALL_RECORD).is_file():
                raise InstallError(f"{self.prefix} exists but was not written by this installer; "
                                   "choose another --prefix or move it away yourself")
        staged = self.prefix.with_name(self.prefix.name + ".new")
        old = self.prefix.with_name(self.prefix.name + ".old")
        report["actions"].append(f"copy {SOURCE} -> {self.prefix}")
        if self.dry_run:
            return report
        for leftover in (staged, old):
            if leftover.exists():
                shutil.rmtree(leftover)
        self.prefix.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(SOURCE, staged, ignore=lambda _d, names: [n for n in names if n in _SKIP])
        (staged / INSTALL_RECORD).write_text(json.dumps({
            "version": report["version"], "installed_at": int(time.time()),
            "source": str(SOURCE)}, indent=1) + "\n", encoding="utf-8")
        for rel in ("bin/cex_tool", "bin/cex_mcp_proxy.py"):
            os.chmod(staged / rel, 0o755)
        if self.prefix.exists():
            self.prefix.rename(old)
        staged.rename(self.prefix)
        if old.exists():
            shutil.rmtree(old)
        return report

    # ── 2. 依赖 ───────────────────────────────────────────
    def check_deps(self, install: bool) -> dict[str, Any]:
        modules = DEP_MODULES
        probe = "import importlib.util,sys; print(','.join(m for m in sys.argv[1:] " \
                "if importlib.util.find_spec(m) is None))"
        report: dict[str, Any] = {"python": self.python, "actions": []}
        if self.dry_run:
            report["missing"] = "not checked (dry run)"
            return report
        proc = subprocess.run([self.python, "-c", probe, *modules.values()], capture_output=True,
                              text=True, timeout=60)
        missing = [name for name, mod in modules.items() if mod in proc.stdout.strip().split(",")]
        report["missing"] = missing
        requirements = str(self.prefix / "requirements.txt")
        if missing and install:
            self.run([self.python, "-m", "pip", "install", "--user", "-r", requirements],
                     report["actions"], timeout=900)
            report["missing"] = []
        elif missing:
            report["next"] = (f"ask the user, then: {self.python} -m pip install --user -r "
                              f"{requirements} (or re-run install.py with --install-deps)")
        return report

    # ── 3. harness ────────────────────────────────────────
    def claude(self) -> dict[str, Any]:
        actions: list[str] = []
        if shutil.which("claude") is None:
            raise InstallError("claude CLI not found on PATH")
        listing = self.run(["claude", "plugin", "marketplace", "list", "--json"], actions,
                           check=False)
        existing = []
        if listing is not None and listing.returncode == 0:
            try:
                existing = json.loads(listing.stdout or "[]")
            except ValueError:
                existing = []
        current = next((m for m in existing if m.get("name") == MARKETPLACE), None)
        if current is None:
            self.run(["claude", "plugin", "marketplace", "add", str(self.prefix)], actions)
        elif Path(str(current.get("path") or "")).resolve() != self.prefix.resolve():
            raise InstallError(f"a marketplace named {MARKETPLACE} already points to "
                               f"{current.get('path')}; remove it with `claude plugin marketplace "
                               f"remove {MARKETPLACE}` if it is an old copy")
        else:
            actions.append(f"marketplace {MARKETPLACE} already points to {self.prefix}")
        self.run(["claude", "plugin", "install", PLUGIN], actions)
        return {"ok": True, "actions": actions,
                "note": "the plugin loads in place from the distribution; new sessions pick it up"}

    def pi(self) -> dict[str, Any]:
        actions: list[str] = []
        pi = os.environ.get("CEX_PI") or shutil.which("pi")
        if pi is None:
            raise InstallError("pi CLI not found on PATH (set CEX_PI to its path)")
        self.run([pi, "install", str(self.prefix)], actions)
        return {"ok": True, "actions": actions}

    def circle(self) -> dict[str, Any]:
        actions: list[str] = []
        home = Path(os.environ.get("CIRCLE_HOME") or Path.home() / ".circle").expanduser()
        skills = [home / "skills" / name for name in SKILLS]
        ext_dir = home / "extensions" / "compile-excel"
        for target in (*skills, ext_dir):
            if target.exists() and not self._ours(target):
                raise InstallError(f"{target} exists and was not written by this installer; "
                                   "move it away first")
        actions.extend(f"copy skill -> {skill}" for skill in skills)
        actions.append(f"write extension entry -> {ext_dir / 'extension.py'}")
        if self.dry_run:
            return {"ok": True, "actions": actions}
        for skill in skills:
            if skill.exists():
                shutil.rmtree(skill)
            shutil.copytree(self.prefix / "skills" / skill.name, skill,
                            ignore=lambda _d, names: [n for n in names if n in _SKIP])
            (skill / ".cex_home").write_text(str(self.prefix) + "\n", encoding="utf-8")
        ext_dir.mkdir(parents=True, exist_ok=True)
        impl = self.prefix / "adapters" / "circle" / "extension.py"
        (ext_dir / "extension.py").write_text(
            f"{SHIM_MARKER}：入口转到发行根里的实现，升级发行根即可，不用改这里。\n"
            "import runpy\n\n"
            f"register = runpy.run_path({str(impl)!r})[\"register\"]\n", encoding="utf-8")
        return {"ok": True, "actions": actions,
                "note": "circle loads it once its extension API (C1) is available"}

    @staticmethod
    def _ours(path: Path) -> bool:
        if (path / ".cex_home").is_file():
            return True
        entry = path / "extension.py"
        return entry.is_file() and entry.read_text(encoding="utf-8").startswith(SHIM_MARKER)

    # ── 4. 自检 ───────────────────────────────────────────
    def verify(self) -> dict[str, Any]:
        if self.dry_run:
            return {"ok": True, "skipped": "dry run"}
        tools = subprocess.run([self.python, str(self.prefix / "bin" / "cex_tool"), "list"],
                               capture_output=True, text=True, timeout=60)
        root = subprocess.run([self.python, str(self.prefix / "skills" / "compile-excel" / "scripts"
                                                / "_cex_path.py")],
                              capture_output=True, text=True, timeout=60,
                              env={k: v for k, v in os.environ.items() if k != "CEX_HOME"})
        ok = tools.returncode == 0 and root.stdout.strip() == str(self.prefix.resolve())
        report: dict[str, Any] = {"ok": ok}
        if tools.returncode == 0:
            report["tools"] = len(json.loads(tools.stdout))
        else:
            report["error"] = (tools.stderr or tools.stdout).strip()[-400:]
        return report


class AlreadyInstalled(InstallError):
    def __init__(self, path: Path, version: str):
        super().__init__(f"compile-excel {version} is already installed at {path}; "
                         "ask the user, then re-run with --upgrade to replace it")
        self.path = path
        self.version = version


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="install compile-excel into agent harnesses")
    parser.add_argument("--harness", action="append", choices=(*HARNESSES, "all"), required=True)
    parser.add_argument("--prefix", default=str(Path.home() / ".local" / "share" / "compile-excel"
                                                / "current"))
    parser.add_argument("--upgrade", action="store_true", help="replace an existing installation")
    parser.add_argument("--install-deps", action="store_true",
                        help="pip install --user the Python requirements if any are missing")
    parser.add_argument("--dry-run", action="store_true", help="print the plan, change nothing")
    args = parser.parse_args(argv)
    harnesses = list(HARNESSES) if "all" in args.harness else list(dict.fromkeys(args.harness))
    installer = Installer(Path(args.prefix).expanduser().absolute(), args.dry_run)
    report: dict[str, Any] = {"ok": False, "dry_run": args.dry_run}
    try:
        report["distribution"] = installer.place_distribution(args.upgrade)
    except AlreadyInstalled as exc:
        report.update(error=str(exc), installed_version=exc.version, path=str(exc.path))
        print(json.dumps(report, ensure_ascii=False, indent=1))
        return 3
    except InstallError as exc:
        report["error"] = str(exc)
        print(json.dumps(report, ensure_ascii=False, indent=1))
        return 1
    report["dependencies"] = installer.check_deps(args.install_deps)
    report["harnesses"] = {}
    for name in harnesses:
        try:
            report["harnesses"][name] = getattr(installer, name)()
        except (InstallError, subprocess.TimeoutExpired, OSError) as exc:
            report["harnesses"][name] = {"ok": False, "error": str(exc)}
    report["verify"] = installer.verify()
    report["ok"] = report["verify"]["ok"] and all(h["ok"] for h in report["harnesses"].values())
    report["next"] = ("Start a new session in the harness. On first use in a project folder the "
                      "skill asks for the server URL and device build, then signs in through the "
                      "browser (cex_init, cex_login_start).")
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
