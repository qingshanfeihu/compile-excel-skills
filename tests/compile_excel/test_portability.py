#!/usr/bin/env python3
"""新机器从零可装的回归：不写死个人路径、服务端名字不能逃出缓存目录、上机阶段的引擎根只从绑定读。

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
sys.path.insert(0, str(SCRIPTS))

import ist_client  # noqa: E402
from run_device import resolve_engine_root  # noqa: E402

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


class SafePathComponentTest(unittest.TestCase):
    def test_accepts_plain_names(self) -> None:
        for name in ("cmdtree_585.xml", "SAMPLE_BUILD_LOCAL", "framework_tree.tar.gz", "v1.2-rc"):
            self.assertEqual(ist_client.safe_path_component(name, "x"), name)

    def test_rejects_anything_that_could_leave_the_cache_dir(self) -> None:
        for name in ("", "..", "../evil", "a/b", "/etc/passwd", ".hidden", "a..b",
                     "name\n", "x" * 200, None):
            with self.assertRaises(ist_client.ClientError, msg=repr(name)):
                ist_client.safe_path_component(name, "x")

    def test_download_refuses_bad_name_before_any_network_call(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ist_client.ClientError):
                ist_client.download_artifact_verified("../escape", "0" * 64, Path(tmp))
            self.assertEqual(list(Path(tmp).iterdir()), [])


class EngineRootTest(unittest.TestCase):
    def setUp(self) -> None:
        self._saved = os.environ.pop("IST_ENGINE_ROOT", None)

    def tearDown(self) -> None:
        if self._saved is not None:
            os.environ["IST_ENGINE_ROOT"] = self._saved

    def test_missing_binding_yields_none_instead_of_a_guessed_path(self) -> None:
        self.assertIsNone(resolve_engine_root({}))

    def test_binding_must_point_at_a_checkout_with_the_framework_client(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertIsNone(resolve_engine_root({"IST_ENGINE_ROOT": str(root)}))
            client = root / "main" / "case_compiler" / "device_mcp_client.py"
            client.parent.mkdir(parents=True)
            client.write_text("", encoding="utf-8")
            self.assertEqual(resolve_engine_root({"IST_ENGINE_ROOT": str(root)}), root)


if __name__ == "__main__":
    unittest.main()


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
