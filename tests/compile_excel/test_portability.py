#!/usr/bin/env python3
"""新机器从零可装的回归：不写死个人路径、拷走的 skill 能找回发行根、命令判定只读投影。

跑法：python3 tests/test_portability.py（或 pytest tests/test_portability.py）
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_ROOT = REPO_ROOT / "skills" / "compile-excel"
SCRIPTS = SKILL_ROOT / "scripts"

# 运行时拼装，避免守卫扫到自身
_PERSONAL_PATH_MARKERS = ("/" + "Users/", "Public" + "/circle", "Public" + "/InfoTest")


class NoPersonalPathsTest(unittest.TestCase):
    def test_tracked_files_carry_no_personal_machine_paths(self) -> None:
        listed = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "ls-files"],
            capture_output=True, text=True, check=True,
        ).stdout.split()
        offenders = []
        for rel in listed:
            path = REPO_ROOT / rel
            if not path.is_file() or path.suffix in {".xlsx", ".png", ".gz"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for marker in _PERSONAL_PATH_MARKERS:
                if marker in text:
                    offenders.append(f"{rel}: {marker}")
        self.assertEqual(offenders, [], "写死的个人机器路径会让别人的机器装不上")


class CopiedSkillFindsDistributionTest(unittest.TestCase):
    """harness 往往把 skill 目录整份拷走：拷走后靠 .cex_home / CEX_HOME 找回 cex_core。"""

    def _run(self, skill: Path, home: Path, extra_env: dict | None = None):
        env = {k: v for k, v in os.environ.items() if k not in ("CEX_HOME", "PYTHONPATH")}
        env.update({"HOME": str(home), **(extra_env or {})})
        return subprocess.run(
            [sys.executable, str(skill / "scripts" / "compile_excel.py"), "--help"],
            capture_output=True, text=True, env=env, timeout=60)

    def test_copied_skill_needs_a_pointer_and_works_with_one(self) -> None:
        import shutil

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            skill = tmp_path / "skills" / "compile-excel"
            shutil.copytree(SKILL_ROOT, skill,
                            ignore=shutil.ignore_patterns("__pycache__", ".cex_home"))
            home = tmp_path / "home"
            home.mkdir()
            lost = self._run(skill, home)
            self.assertNotEqual(lost.returncode, 0)
            self.assertIn("CEX_HOME", lost.stderr + lost.stdout)
            self.assertEqual(self._run(skill, home, {"CEX_HOME": str(REPO_ROOT)}).returncode, 0)
            (skill / ".cex_home").write_text(str(REPO_ROOT) + "\n", encoding="utf-8")
            self.assertEqual(self._run(skill, home).returncode, 0)


class CmdtreeCheckUsesProjectionTest(unittest.TestCase):
    def test_projection_judgment_and_no_implicit_xml(self) -> None:
        import json as _json

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            projection = tmp_path / "vendor_stdlib_9.9_101.json"
            projection.write_text(_json.dumps({"version": "9.9", "heads": {
                "show version": {"src": "xml", "pmax": 0},
                "slb real http": {"src": "xml", "args": [
                    {"type": "STRING"}, {"type": "IPADDR"}, {"type": "U16"}]}}}),
                encoding="utf-8")
            cases = tmp_path / "cases.json"
            cases.write_text(_json.dumps({"cases": [{"autoid": "1", "steps": [
                {"e": "APV_1", "f": "cmd", "g": "show version"},
                {"e": "APV_1", "f": "cmd_config", "g": "slb real http r1 10.0.0.1 80"},
                {"e": "APV_1", "f": "cmd_config", "g": "no slb real http r1 10.0.0.1 80"},
                {"e": "APV_1", "f": "cmd_config", "g": "slb real http r1 bad 80"},
                {"e": "APV_1", "f": "cmd", "g": "shwo version"}]}]}), encoding="utf-8")
            (tmp_path / "cmdtree_decoy.xml").write_text("<cmdtree/>", encoding="utf-8")
            env = {k: v for k, v in os.environ.items() if k != "CEX_WORKSPACE"}
            env["HOME"] = str(tmp_path)
            script = SCRIPTS / "cmdtree_check.py"
            out = subprocess.run([sys.executable, str(script), "--cases", str(cases),
                                  "--projection", str(projection)],
                                 capture_output=True, text=True, env=env, timeout=60)
            self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
            report = _json.loads(out.stdout)
            self.assertEqual(report["checked"], 5)
            self.assertEqual([u["command"] for u in report["unknown"]],
                             ["slb real http r1 bad 80", "shwo version"])
            missing = subprocess.run([sys.executable, str(script), "--cases", str(cases)],
                                     capture_output=True, text=True, env=env, timeout=60)
            self.assertEqual(missing.returncode, 2, "没有投影时不能悄悄退回去读原始 XML")


if __name__ == "__main__":
    unittest.main()
