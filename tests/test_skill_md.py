"""SKILL.md 与代码不漂移：正文提到的脚本、参考文档、cex_* 工具都得真实存在。

skill 正文是模型的操作手册，写了不存在的脚本或工具名，模型就会去调一个不存在的东西。
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO_ROOT / "skills"
SKILL = SKILLS_DIR / "compile-excel"
# 技能名 → 描述里必须保留的一个中文触发词（匹配用户的中文输入）
TRIGGERS = {"compile-excel": "编译用例", "mindmap-recompose": "脑图重组"}


def _texts() -> dict[str, str]:
    files = []
    for skill in sorted(SKILLS_DIR.iterdir()):
        if (skill / "SKILL.md").is_file():
            files += [skill / "SKILL.md", *sorted((skill / "references").glob("*.md"))]
    return {str(p.relative_to(SKILLS_DIR)): p.read_text(encoding="utf-8") for p in files}


def test_every_skill_is_known_and_packaged():
    present = {p.parent.name for p in SKILLS_DIR.glob("*/SKILL.md")}
    assert present == set(TRIGGERS)
    install = (REPO_ROOT / "install.py").read_text(encoding="utf-8")
    assert all(f'"{name}"' in install for name in TRIGGERS)


@pytest.mark.parametrize("name", sorted(TRIGGERS))
def test_frontmatter_has_name_and_description(name):
    text = (SKILLS_DIR / name / "SKILL.md").read_text(encoding="utf-8")
    head = text.split("---", 2)[1]
    assert re.search(rf"^name: {name}$", head, re.M)
    description = re.search(r'^description: "(.+)"$', head, re.M)
    assert description and "Do NOT trigger" in description.group(1)
    assert TRIGGERS[name] in description.group(1)


def test_referenced_scripts_and_references_exist():
    missing = []
    for name, text in _texts().items():
        skill = SKILLS_DIR / name.split("/", 1)[0]
        for rel in sorted(set(re.findall(r"\b((?:scripts|references)/[\w.-]+\.(?:py|md))", text))):
            if not (skill / rel).is_file() and not (skill / "references" / Path(rel).name).is_file():
                missing.append(f"{name}: {rel}")
    assert missing == []


def test_named_tools_exist_in_the_tool_specs():
    specs = json.loads((REPO_ROOT / "cex_client" / "tool_specs.json").read_text(encoding="utf-8"))
    known = {tool["name"] for tool in specs["tools"]}
    unknown = []
    for name, text in _texts().items():
        for tool in sorted(set(re.findall(r"\bcex_[a-z_]+\b", text))):
            if tool in ("cex_core", "cex_client", "cex_tool", "cex_home"):
                continue
            if tool not in known:
                unknown.append(f"{name}: {tool}")
    assert unknown == []


def test_recompose_skill_names_no_engine_side_tools():
    """InfoTest 重组孔的工具（fs_* / kb_bug_search / submit_machine_mindmap* / 裸 lang_query）
    在客户端不存在；正文里出现就是让模型去调一个不存在的东西。"""
    engine_only = re.compile(r"\b(fs_(?:read|grep|glob|ls|write)|kb_bug_search"
                             r"|submit_machine_mindmap(?:_cases)?)\b|(?<!cex_)\blang_query\b")
    hits = [f"{name}: {m.group(0)}" for name, text in _texts().items()
            if name.startswith("mindmap-recompose/") for m in engine_only.finditer(text)]
    assert hits == []


def test_skill_does_not_route_to_the_retired_env_binding():
    retired = ("link_status", "preflight.py", "bind_env", "collect_credentials", "login.py",
               "fetch.py", "IST_ENGINE_ROOT", "KNOWLEDGE_DIR", "COMPILE_EXCEL_ENV")
    hits = [f"{name}: {word}" for name, text in _texts().items() for word in retired
            if word in text]
    assert hits == []


def test_shipped_example_compiles_and_passes_static_verification(tmp_path):
    """示例是模型照着学的样板：它自己过不了 verify_batch，就是在教错的写法。"""
    pytest.importorskip("openpyxl")
    scripts = SKILL / "scripts"
    compiled = subprocess.run(
        [sys.executable, str(scripts / "compile_excel.py"), "--cases",
         str(SKILL / "examples" / "slb_cases.json"), "--out", str(tmp_path)],
        capture_output=True, text=True, timeout=120)
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr
    xlsx = json.loads(compiled.stdout)["path"]
    verified = subprocess.run([sys.executable, str(scripts / "verify_batch.py"), "--xlsx", xlsx],
                              capture_output=True, text=True, timeout=120)
    report = json.loads(verified.stdout)
    assert report["fail"] == 0, report.get("failures")
