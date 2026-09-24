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

SKILL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SKILL_ROOT.parent
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
