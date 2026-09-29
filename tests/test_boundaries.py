"""仓库边界守门：compile-excel 的代码不读 InfoTest 的配置文件、不 import InfoTest 的环境加载模块；
发出去的文件不带内部实证记录（实验床内网地址、批次名、用例号）。

上机已改走跳板机网关（run_device.py 不再借 InfoTest 引擎的客户端）。
"""

from __future__ import annotations

import io
import json
import os
import re
import subprocess
import tokenize
import zipfile

from conftest import REPO_ROOT

# tools/sync_from_infotest.py 以文本方式读取 InfoTest 源码做逐字抽取（字符串里必然出现 main.），
# 从不 import InfoTest；它是唯一例外。
ALLOWED = {"tools/sync_from_infotest.py"}
# 运行时拼装，避免守卫扫到自身
_PATTERNS = [
    re.compile(r"langchain" + r"_env"),
    re.compile(r"""["'/]\s*""" + "environ" + r"""ment["']"""),
    re.compile(r"from\s+main\.|import\s+main\."),
]
# 逐字放行的同名字面（文件 → 原文）：不是配置文件路径。只剥这一段原文再扫，同一文件里别处
# 再出现照样报。三处都不是配置文件路径：facts.py 是编写失败原因的枚举值（环境类原因）；
# excel_capability_receipts.py 读 Excel 晋升回执里的字段；environment_prepare.py 读模板选择结果的属性。
_ENV = "environ" + "ment"
_KNOWN_LITERALS = {
    "cex_core/engine/ist_core/compile_engine/facts.py": (f"AUTHORING_CAUSE_ENV = '{_ENV}'",),
    "cex_core/engine/case_compiler/excel_capability_receipts.py":
        (f"_object(receipt.get('{_ENV}'), label='{_ENV}')",),
    "cex_core/engine/ist_core/compile_engine/environment_prepare.py":
        (f"getattr(selection, '{_ENV}', None)",),
}


# 抽取来的引擎里 "environment" 常作枚举值（失败归因类别、负责方）；读 InfoTest 的配置文件
# 在引擎里只能是拼路径（root / 'environment'、_cex_data_path('environment')），引擎文件按这个查
_ENGINE_ENV_PATH = re.compile(r"""(?:/\s*|_cex_data_path\(\s*)["']""" + "environ" + r"""ment["']""")


def _engine_env_loader_is_outside_the_closure() -> bool:
    """引擎代码里的 langchain_env 只能是闭包外的延迟 import（调到就 ModuleNotFoundError）。"""
    manifest = json.loads((REPO_ROOT / "cex_core" / "engine" / "MANIFEST.json")
                          .read_text(encoding="utf-8"))
    loader = "main.langchain" + "_env"
    return (loader in manifest["boundary_targets"]
            and loader not in {entry["module"] for entry in manifest["modules"]})


def test_code_does_not_touch_infotest_configuration():
    tracked = subprocess.run(["git", "ls-files", "*.py", "bin/*"], cwd=REPO_ROOT,
                             capture_output=True, text=True, check=True).stdout.split()
    loader_outside = _engine_env_loader_is_outside_the_closure()
    offenders = []
    for rel in tracked:
        if rel in ALLOWED or rel.startswith("tests/"):
            continue
        text = (REPO_ROOT / rel).read_text(encoding="utf-8", errors="ignore")
        for literal in _KNOWN_LITERALS.get(rel, ()):
            assert text.count(literal) == 1, f"{rel}: 放行的原文变了，重核这条放行：{literal}"
            text = text.replace(literal, "")
        for pattern in _PATTERNS:
            if pattern is _PATTERNS[0] and rel.startswith("cex_core/engine/") and loader_outside:
                continue
            if pattern is _PATTERNS[1] and rel.startswith("cex_core/engine/"):
                pattern = _ENGINE_ENV_PATH
            if pattern.search(text):
                offenders.append(f"{rel}: {pattern.pattern}")
    assert offenders == []


def test_tool_specs_and_registry_agree():
    from cex_client import tools

    specs = tools.load_specs()
    assert [s["name"] for s in specs] == list(tools.TOOLS)
    for spec in specs:
        assert spec["input_schema"]["type"] == "object"
        assert spec["description"].isascii(), f"{spec['name']}: tool descriptions are LLM-facing English"


def test_everything_imports_and_runs_without_infotest(tmp_path):
    """在屏蔽 InfoTest `main` 包的子进程里导入全部模块、跑一遍脱敏与解析：
    抽取来的代码里若残留函数内的延迟导入，这里会炸（对拍测试因为 InfoTest 在 sys.path 上看不出来）。

    cex_core.engine 除外：它的模块像在 InfoTest 里一样导入时就读数据，没有数据根导入即失败；
    带数据根的独立导入在 tests/core/test_engine_extract.py 里查。"""
    import sys

    script = tmp_path / "probe.py"
    script.write_text(f'''
import builtins, importlib, pkgutil, sys
sys.path.insert(0, {str(REPO_ROOT)!r})
_real = builtins.__import__
def _guard(name, *a, **k):
    if name == "main" or name.startswith("main."):
        raise ImportError("InfoTest imported: " + name)
    return _real(name, *a, **k)
builtins.__import__ = _guard
import cex_core, cex_client
for pkg in (cex_core, cex_client):
    for mod in pkgutil.walk_packages(pkg.__path__, pkg.__name__ + ".",
                                     onerror=lambda name: None):
        if mod.name.startswith("cex_core.engine."):
            continue
        importlib.import_module(mod.name)
from cex_core.defects.scrub import scrub_declaration_text, contains_prohibited_declaration
assert scrub_declaration_text("password=hunter2 x") != "password=hunter2 x"
contains_prohibited_declaration("token: abc")
print("ok")
''', encoding="utf-8")
    proc = subprocess.run([sys.executable, str(script)], capture_output=True, text=True,
                          timeout=120)
    assert proc.returncode == 0 and proc.stdout.strip() == "ok", proc.stderr[-2000:]


# ── 发出去的文件不带内部实证记录 ──────────────────────────────────────────────
# 安装器照检出整份拷走（tests/ 除外），网关 vendor 整包拷 cex_core/：这些文件里不许有实验床
# 内网地址、批次名、用例号这类内部运行记录。例外逐条登记：值 → (限定的文件前缀, 理由)。
_LAB_IP = re.compile(r"(?<![\d.])(?:10\.4|172\.16)\.\d{1,3}\.\d{1,3}(?!\d)")
# 按人名缩写起头的批次：名单同 tools/extract_engine.py 从 CEX_INTERNAL_HANDLES 注入
# （公开仓不携带真实名单；名单为空时该项不查，RUN_/日期形批次照查）
os.environ.setdefault("CEX_INTERNAL_HANDLES", "internala")  # 本文件守门自测用中性名
_HANDLES = tuple(h.strip() for h in os.environ.get("CEX_INTERNAL_HANDLES", "").split(",")
                 if h.strip())
_HANDLE_PART = (rf"(?i:(?<![A-Za-z0-9])(?:{'|'.join(_HANDLES)})[A-Za-z0-9_-]*)"
                if _HANDLES else "")
_BATCH_LIKE = re.compile(
    _HANDLE_PART
    + ("|" if _HANDLE_PART else "")
    + r"\bRUN_20\d{2}[A-Za-z0-9_-]*"                         # 引擎运行号
    # 小写蛇形/连字符名字、以月日（或年月日）收尾：slb_virtual_list_0923 这类批次名
    r"|(?<![A-Za-z0-9_-])[a-z][a-z0-9]*(?:[_-][a-z0-9]+)*[_-](?:20\d{2})?"
    r"(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])(?![A-Za-z0-9_-])")
# 6–20 位数字串（用例号、它的六位尾号）；两边挨着字母数字或点的不算（十六进制摘要、版本号）
_ID_DIGITS = re.compile(r"(?<![0-9A-Za-z.])\d{6,20}(?![0-9A-Za-z.])")
_SAMPLE_AUTOID = ("skills/", "技能文档与示例里的合成案号（日期形状、顺序编号），不是生产用例")
_LEAK_ALLOWED: dict[str, tuple[str, str]] = {
    "999999999999999": ("", "框架在文件末尾执行的伪案（哨兵）案号，是执行契约的一部分"),
    "990000000000000001": ("", "环境收敛生成能力样例卷用的合成案号（抽取脚本也按它放行）"),
    "202609236681010001": _SAMPLE_AUTOID,
    "202609236681020001": _SAMPLE_AUTOID,
    "202609236683010001": _SAMPLE_AUTOID,
    "202609240000000001": _SAMPLE_AUTOID,
    "1135317": ("cex_core/engine/kms/manual_chapter_locator.py",
                "手册里的字符偏移，说明按偏移定位会漂，不是案号"),
    "1135756": ("cex_core/engine/kms/manual_chapter_locator.py",
                "手册里的字符偏移，说明按偏移定位会漂，不是案号"),
    "172.16.35.215": ("cex_core/engine/scripts/gen_capability_atlas.py",
                      ("框架取证书的 TFTP 源：能力图谱的策展说明照框架源码写出这条床事实，模型据此"
                       "判断证书导入走哪条分支；数据包里的框架镜像同样带着它，换成别的地址就是错的")),
    "smoke_0923": ("skills/compile-excel/SKILL.md", "cases.json 示例里的批次名（示例，可换成中性名）"),
}


def _shipped_files() -> list[str]:
    tracked = subprocess.run(["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True,
                             check=True).stdout.splitlines()
    return [rel for rel in tracked if not rel.startswith("tests/") and (REPO_ROOT / rel).is_file()]


def _text_spans(rel: str, text: str):
    """(行号, 文本)：.py 只看字符串与注释（代码里的整数常量不是记录），其余文件看全文。"""
    if rel.endswith(".py"):
        try:
            spans = [(tok.start[0], tok.string)
                     for tok in tokenize.generate_tokens(io.StringIO(text).readline)
                     if tok.type in (tokenize.STRING, tokenize.COMMENT)]
        except (tokenize.TokenError, SyntaxError):
            spans = None
        if spans is not None:
            yield from spans
            return
    yield from enumerate(text.splitlines(), 1)


def _leaks(rel: str, text: str, rules) -> list[str]:
    hits = []
    for line_no, span in _text_spans(rel, text):
        for rule in rules:
            for match in rule.finditer(span):
                value = match.group(0)
                if value.isdigit() and (int(value) % 1000 == 0 or int(value) & (int(value) - 1) == 0):
                    continue  # 整万、2 的幂：常量，不是案号
                allowed = _LEAK_ALLOWED.get(value)
                if allowed is not None and rel.startswith(allowed[0]):
                    continue
                hits.append(f"{rel}:{line_no}: {value}")
    return hits


def test_shipped_files_carry_no_internal_run_records():
    """内网地址（10.4.x.x 跳板机段、172.16.x.x 床段）、批次名、6–20 位用例号：发出去的文件里
    一个都不许有；确需保留的逐条登记在 _LEAK_ALLOWED，说明为什么留。"""
    offenders = []
    for rel in _shipped_files():
        raw = (REPO_ROOT / rel).read_bytes()
        if rel.endswith(".xlsx"):
            with zipfile.ZipFile(io.BytesIO(raw)) as book:  # 工作簿里的 XML：样式色值不是案号
                for member in book.namelist():
                    text = book.read(member).decode("utf-8", errors="ignore")
                    offenders += _leaks(f"{rel}!{member}", text, (_LAB_IP, _BATCH_LIKE))
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            offenders.append(f"{rel}: not UTF-8 text, cannot be checked for run records")
            continue
        offenders += _leaks(rel, text, (_LAB_IP, _BATCH_LIKE, _ID_DIGITS))
    assert offenders == []


def test_the_leak_guard_catches_each_kind_of_record():
    samples = {
        "见 10.4.127.103 上的框架": _LAB_IP, "床段 172.16.33.215/24": _LAB_IP,
        "批次 internala-final1": _BATCH_LIKE, "RUN_20260924_x": _BATCH_LIKE,
        "skill 路线 slb_virtual_list_0923 = 5/5": _BATCH_LIKE,
        "case 202609240000000001": _ID_DIGITS, "044605 evidence": _ID_DIGITS,
    }
    for text, rule in samples.items():
        assert _leaks("docs/x.md", text, (rule,)), text
    assert _leaks("docs/x.md", "sha 46aa14dfffbe767ec486dc6b186d582458d666de8a8f6", (_ID_DIGITS,)) == []
    assert _leaks("docs/x.md", "version 10.5.0.585, budget 250000", (_LAB_IP, _ID_DIGITS)) == []
    assert _leaks("cex_core/x.py", "LIMIT = 4294967295\n# 1234567 in a comment\n",
                  (_ID_DIGITS,)) == ["cex_core/x.py:2: 1234567"]
