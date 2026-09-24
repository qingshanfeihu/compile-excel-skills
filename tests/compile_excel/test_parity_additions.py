#!/usr/bin/env python3
"""引擎对齐新增件的回归：恒真断言族 / provenance 边车 / 返工闸 / 机械归因。

跑法：python3 tests/test_parity_additions.py（或 pytest tests/test_parity_additions.py）
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_ROOT = REPO_ROOT / "skills" / "compile-excel"
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from verify_batch import _tautology_family  # noqa: E402
from run_device import attribute_fail  # noqa: E402

def _run(script: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script), *args],
        capture_output=True, text=True, timeout=120,
    )


def _row(autoid, e="", f="", g="", h="", i=""):
    return [autoid or "", "", "", "", e, f, g, h, i]


class TautologyFamilyTest(unittest.TestCase):
    def _data(self, cp_rows, feed="show slb virtual httplist vs_x"):
        rows = [
            _row("202609239000010001"),
            _row("", "APV_0", "cmd_config", feed),
        ]
        rows.extend(cp_rows)
        rows.append(_row("", "check_point", "found", "vs_x", "", ""))
        return rows

    def test_prompt_like_expected_is_tautology(self):
        rows = [
            _row("202609239000010001"),
            _row("", "APV_0", "cmd_config", "show version"),
            _row("", "check_point", "found", "APV", "", ""),
        ]
        bad = _tautology_family(rows)
        self.assertTrue(any("恒真" in b for b in bad), bad)

    def test_empty_matching_regex_is_tautology(self):
        rows = [
            _row("202609239000010001"),
            _row("", "APV_0", "cmd_config", "show version"),
            _row("", "check_point", "found", "\\d*", "", ""),
        ]
        bad = _tautology_family(rows)
        self.assertTrue(any("空串" in b for b in bad), bad)

    def test_not_found_of_command_token_is_false_by_construction(self):
        rows = [
            _row("202609239000010001"),
            _row("", "APV_0", "cmd_config", "show slb virtual httplist vs_del"),
            _row("", "check_point", "not_found", "vs_del", "", ""),
        ]
        bad = _tautology_family(rows)
        self.assertTrue(any("恒假" in b for b in bad), bad)

    def test_legitimate_assertions_pass(self):
        rows = [
            _row("202609239000010001"),
            _row("", "APV_0", "cmd_config", "show slb virtual httplist"),
            _row("", "check_point", "not_found", "vs_del", "", ""),
            _row("", "APV_0", "cmd_config", "show version"),
            _row("", "check_point", "found", "10\\.4\\.6", "", ""),
        ]
        self.assertEqual(_tautology_family(rows), [])


class AttributionTest(unittest.TestCase):
    def test_g_layer(self):
        att = attribute_fail("... % invalid input at '^' marker ...")
        self.assertEqual(att["layer"], "G")

    def test_transient_suspect(self):
        att = attribute_fail("read_until timeout after 10s")
        self.assertEqual(att["layer"], "transient?")

    def test_undetermined(self):
        att = attribute_fail("expected 'vs_x' not found in show output")
        self.assertEqual(att["layer"], "undetermined")


class ProvenanceAndReworkIT(unittest.TestCase):
    """compile→verify（provenance 检查）→run_results→rework_gate 全链。"""

    CASES = {
        "batch": "parity_it",
        "init_commands": ["config terminal"],
        "cases": [
            {
                "autoid": "202609239000010001",
                "steps": [
                    {"e": "APV_0", "f": "cmd_config", "g": "show version",
                     "h": "", "i": ""},
                    {"e": "check_point", "f": "found", "g": "version",
                     "h": "", "i": "",
                     "source": {"kind": "author-verbatim",
                                "ref": "mindmap:202609239000010001"}},
                ],
            },
            {
                "autoid": "202609239000010002",
                "steps": [
                    {"e": "APV_0", "f": "cmd_config", "g": "show date",
                     "h": "", "i": ""},
                    {"e": "check_point", "f": "found", "g": "2026",
                     "h": "", "i": ""},  # 无 source → 应回落 author-verbatim
                ],
            },
        ],
    }

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.cases = self.root / "cases.json"
        self.cases.write_text(json.dumps(self.CASES, ensure_ascii=False),
                              encoding="utf-8")
        self.out = self.root / "compile_outputs"

    def tearDown(self):
        self._tmp.cleanup()

    def test_roundtrip(self):
        # 1) compile → provenance.json + defaulted 计数
        proc = _run("compile_excel.py", "--cases", str(self.cases),
                    "--out", str(self.out))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        stats = json.loads(proc.stdout)
        self.assertEqual(stats.get("sources_defaulted"), 1)
        prov_path = self.out / "parity_it" / "provenance.json"
        self.assertTrue(prov_path.is_file())
        prov = json.loads(prov_path.read_text(encoding="utf-8"))
        self.assertEqual(prov["schema"], "ist.excel.provenance")
        self.assertEqual(len(prov["cases"]["202609239000010002"]), 1)
        self.assertEqual(
            prov["cases"]["202609239000010002"][0]["source"]["kind"],
            "author-verbatim",
        )

        # 2) verify → provenance 检查通过
        xlsx = self.out / "parity_it" / "case.xlsx"
        proc = _run("verify_batch.py", "--xlsx", str(xlsx))
        report = json.loads(proc.stdout)
        prov_check = next(c for c in report["checks"]
                          if c["name"].startswith("provenance"))
        self.assertTrue(prov_check["ok"], prov_check)

        # 删掉边车 → 必须报缺
        prov_path.unlink()
        proc = _run("verify_batch.py", "--xlsx", str(xlsx))
        report = json.loads(proc.stdout)
        prov_check = next(c for c in report["checks"]
                          if c["name"].startswith("provenance"))
        self.assertFalse(prov_check["ok"])

    def test_rework_gate(self):
        batch_dir = self.out / "parity_it"
        _run("compile_excel.py", "--cases", str(self.cases), "--out", str(self.out))
        # 伪造上机结果：案1 pass、案2 fail
        run = {
            "schema": "ist.excel.device-run-result",
            "cases": [
                {"autoid": "202609239000010001", "verdict": "pass"},
                {"autoid": "202609239000010002", "verdict": "fail"},
            ],
            "totals": {"cases": 2, "pass": 1, "fail": 1, "not_run": 0},
        }
        (batch_dir / "run_results.json").write_text(
            json.dumps(run, ensure_ascii=False), encoding="utf-8")

        # 首轮闸：通过，round 1
        proc = _run("rework_gate.py", "--batch-dir", str(batch_dir),
                    "--cases", str(self.cases))
        self.assertEqual(proc.returncode, 0, proc.stdout)

        # 只改 fail 案 → 闸通过，redispatch=[案2]
        doc2 = json.loads(json.dumps(self.CASES))
        doc2["cases"][1]["steps"][1]["g"] = "2027"
        c2 = self.root / "cases2.json"
        c2.write_text(json.dumps(doc2, ensure_ascii=False), encoding="utf-8")
        proc = _run("rework_gate.py", "--batch-dir", str(batch_dir),
                    "--cases", str(c2))
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("202609239000010002",
                      json.loads(proc.stdout)["redispatch"])

        # 改 pass 案 → 闸拦截（exit 1）
        doc3 = json.loads(json.dumps(self.CASES))
        doc3["cases"][0]["steps"][1]["g"] = "Version"
        c3 = self.root / "cases3.json"
        c3.write_text(json.dumps(doc3, ensure_ascii=False), encoding="utf-8")
        proc = _run("rework_gate.py", "--batch-dir", str(batch_dir),
                    "--cases", str(c3))
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertTrue(json.loads(proc.stdout)["violations"])


if __name__ == "__main__":
    unittest.main()
