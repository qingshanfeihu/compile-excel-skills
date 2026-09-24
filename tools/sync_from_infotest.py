#!/usr/bin/env python3
"""从 InfoTest 源逐字抽取 cex_core 里的判据代码（改判据先改 InfoTest，再跑本脚本）。

  python3 tools/sync_from_infotest.py --infotest-root ../InfoTest_Engine [--out .] [--check]

生成：
- cex_core/vendor_cmd.py            ← main/case_compiler/vendor_stdlib.py 的命令判定函数
- cex_core/defects/html_extractors/  ← main/ingest/html_extractors/（schema 换成 dataclass）
- cex_core/defects/scrub.py          ← main/defect_spec_source.py 的脱敏与禁入判定
- cex_core/security_scrub.py         ← main/ist_core/security_scrub.py（到 scrub_text 为止）
--check 只比对不写，有差异退出码 1（tests/core/test_extraction_drift.py 用它）。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

VENDOR_HEADER = '''"""命令存在性与参数契约判定：读命令树投影（vendor_stdlib JSON），不读原始 XML。

本文件由 InfoTest `main/case_compiler/vendor_stdlib.py` 的判定函数逐字抽出生成
（norm_command_tokens … resolve_vendor_command 与所需常量），唯一改动是
`resolve_vendor_command` 的投影由调用方传入，而不是按版本从本机命令树仓加载。
与 InfoTest 的一致性由 Phase 3 对拍守住；改判据先改 InfoTest 源再重新抽取，不在这里手改。
"""

from __future__ import annotations

import ipaddress
import json
import re
import shlex
from pathlib import Path

'''

VENDOR_FOOTER = '''

def load_projection(path: str | Path) -> dict:
    """读投影 JSON；形态不对（没有 heads 映射）就报错，不把“读不到”当成“命令不存在”。"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("heads"), dict):
        raise ValueError(f"{path} 不是命令树投影（缺 heads 映射）")
    return data
'''

EXTRACTOR_HEADER = ("# ruff: noqa: F401, F601\n# 移植自 InfoTest main/ingest/html_extractors/{name}："
                    "逐字复制，只把包内导入改成相对导入。\n")

SCHEMA_HEAD = '''# 移植自 InfoTest main/ingest/html_extractors/schema.py：字段、默认值与方法逐字保留；
# 客户端不依赖 pydantic，所以换成 dataclass（extra="allow" 的额外字段不保留）。
from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Attachment:
    url: str
    filename: str = ""


@dataclass
class DefectTicket:
    """HTML 解析后的统一缺陷/需求模型。"""

    ticket_id: str
'''

SCHEMA_TAIL = '''

    def to_dict(self) -> dict:
        return asdict(self)
'''

SCRUB_HEADER = '''"""缺陷单文本脱敏与禁入判定。

逐字抽自 InfoTest main/defect_spec_source.py（scrub_declaration_text、contains_prohibited_declaration
及其依赖的正则与归一函数）。改判据先改 InfoTest 源再重新抽取，不在这里手改。
"""

from __future__ import annotations

import html
import re
import unicodedata
from typing import Any

'''

SECURITY_HEADER = ("# ruff: noqa: F401\n# 逐字抽自 InfoTest main/ist_core/security_scrub.py"
                   "（到 scrub_text 为止）。\n# 改判据先改 InfoTest 源再重新抽取，不在这里手改。\n")


def _span(lines: list[str], start_pat: str, end_pat: str) -> str:
    start = next(i for i, line in enumerate(lines) if re.match(start_pat, line))
    end = next(i for i, line in enumerate(lines) if i > start and re.match(end_pat, line))
    return "".join(lines[start:end])


def build(infotest: Path) -> dict[str, str]:
    """返回 {相对路径: 内容}；不写盘。"""
    main = infotest / "main"
    files: dict[str, str] = {}

    lines = (main / "case_compiler" / "vendor_stdlib.py").read_text(
        encoding="utf-8").splitlines(keepends=True)
    consts = _span(lines, r"^_MAX_HEAD_TOKENS = 8", r"^XML_COMMAND_NOT_FOUND = ")
    consts += 'XML_COMMAND_NOT_FOUND = "command_not_found"\n'
    funcs = _span(lines, r"^def norm_command_tokens\(", r"^def resolve_vendor_command\(")
    resolve = _span(lines, r"^def resolve_vendor_command\(", r"^def _recorded_headers\(")
    old_head = ('def resolve_vendor_command(\n    cmd: str,\n    version: str = "",\n'
                '    device_build: str = "",\n) -> dict:\n'
                '    inv = load_vendor_stdlib(version, device_build)\n')
    if old_head not in resolve:
        raise SystemExit("InfoTest resolve_vendor_command 的签名变了，先更新本脚本")
    resolve = resolve.replace(old_head, (
        'def resolve_vendor_command(cmd: str, inv: dict | None) -> dict:\n'
        '    """InfoTest 同名函数的逐字副本，只把「按版本加载投影」换成由调用方传入投影。"""\n'))
    files["cex_core/vendor_cmd.py"] = (VENDOR_HEADER + consts + "\n\n" + funcs
                                       + resolve.rstrip() + "\n" + VENDOR_FOOTER)

    ext_src = main / "ingest" / "html_extractors"
    for name in ("_common.py", "_zh_fold.py", "bugzilla.py", "zentao.py", "__init__.py"):
        text = (ext_src / name).read_text(encoding="utf-8")
        text = re.sub(r"\bfrom main\.ingest\.html_extractors\.", "from .", text)
        text = re.sub(r"\bfrom main\.ingest\.html_extractors import", "from . import", text)
        if "main." in text:
            raise SystemExit(f"{name} 还引用了 InfoTest 的其他模块，先更新本脚本")
        files[f"cex_core/defects/html_extractors/{name}"] = \
            EXTRACTOR_HEADER.format(name=name) + text
    files["cex_core/defects/html_extractors/selectors.yaml"] = \
        (ext_src / "selectors.yaml").read_text(encoding="utf-8")

    schema = (ext_src / "schema.py").read_text(encoding="utf-8")
    methods = schema[schema.index("    def is_valid_detail(self)"):]
    fields = schema[schema.index("    invalid_reason: str"):schema.index("    def is_valid_detail(self)")]
    fields = fields.replace("Field(default_factory=list)", "field(default_factory=list)")
    fields = fields.replace("    ticket_id: str\n", "")
    files["cex_core/defects/html_extractors/schema.py"] = (
        SCHEMA_HEAD + fields.rstrip() + "\n\n" + methods.rstrip() + SCHEMA_TAIL)

    lines = (main / "defect_spec_source.py").read_text(encoding="utf-8").splitlines(keepends=True)
    consts = _span(lines, r"^_CONTROL_RE = ", r"^_MAX_SOURCE_SEMANTIC_CHARS = ")
    funcs = _span(lines, r"^def _normalize_security_markup\(", r"^def _candidate_semantic_size\(")
    lazy = "    from main.ist_core.security_scrub import scrub_text\n"
    if funcs.count(lazy) != 1:
        raise SystemExit("defect_spec_source 对 security_scrub 的引用变了，先更新本脚本")
    funcs = funcs.replace(lazy, "    from ..security_scrub import scrub_text\n")
    files["cex_core/defects/scrub.py"] = SCRUB_HEADER + consts + "\n" + funcs
    files["cex_core/defects/__init__.py"] = \
        '"""缺陷单解析与脱敏（移植自 InfoTest main/ingest 与 defect_spec_source）。"""\n'

    sec = (main / "ist_core" / "security_scrub.py").read_text(encoding="utf-8")
    sec = sec[:sec.index("def _scrub_sha256_identity(")]
    if "from main" in sec or "import main" in sec:
        raise SystemExit("security_scrub 前半段引用了 InfoTest 的其他模块，先更新本脚本")
    files["cex_core/security_scrub.py"] = SECURITY_HEADER + sec.rstrip() + "\n"
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description="从 InfoTest 源逐字抽取 cex_core 判据代码")
    parser.add_argument("--infotest-root", required=True)
    parser.add_argument("--out", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--check", action="store_true", help="只比对不写，有差异退出码 1")
    args = parser.parse_args()
    out = Path(args.out).resolve()
    drift = []
    for rel, content in build(Path(args.infotest_root).resolve()).items():
        target = out / rel
        current = target.read_text(encoding="utf-8") if target.is_file() else None
        if current == content:
            continue
        drift.append(rel)
        if not args.check:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
    for rel in drift:
        print(("与 InfoTest 不一致: " if args.check else "已更新: ") + rel)
    return 1 if (args.check and drift) else 0


if __name__ == "__main__":
    sys.exit(main())
