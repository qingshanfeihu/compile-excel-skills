"""cex_core 与 InfoTest 同一输入同一结果（对拍）。需要同级的 InfoTest 检出与它的依赖，缺就跳过。

- vendor_cmd.resolve_vendor_command：InfoTest 版把「按版本加载投影」打桩成同一份投影，逐条比结果；
- 缺陷页解析：InfoTest 仓里的 HTML 夹具，两边抽出来的字段逐项相等；
- 脱敏：一组含凭据、路径、链接、私钥的文本，两边输出逐字相等。
"""

from __future__ import annotations

import sys
from dataclasses import asdict

import pytest

from conftest import INFOTEST_ROOT

pytestmark = pytest.mark.skipif(
    not (INFOTEST_ROOT / "main" / "case_compiler" / "vendor_stdlib.py").is_file(),
    reason=f"找不到 InfoTest 检出 {INFOTEST_ROOT}（设 INFOTEST_ROOT）")


@pytest.fixture(scope="module")
def infotest():
    sys.path.insert(0, str(INFOTEST_ROOT))
    try:
        import main.case_compiler.vendor_stdlib as it_vendor  # noqa: F401
    except ImportError as exc:
        pytest.skip(f"InfoTest 依赖不全：{exc}")
    yield
    sys.path.remove(str(INFOTEST_ROOT))


PROJECTION = {
    "version": "9.9",
    "device_os_build": "101",
    "heads": {
        "show version": {"src": "xml", "pmax": 0},
        "show slb real": {"src": "xml", "pmax": 2},
        "slb real http": {"src": "xml", "args": [
            {"type": "STRING"}, {"type": "IPADDR"}, {"type": "U16"},
            {"type": "U16", "optional": True}]},
        "slb virtual http": {"src": "xml", "args": [
            {"type": "STRING"}, {"type": "IPADDR"}, {"type": "U16"}]},
        "ip address": {"src": "xml", "manual_pmax": 2, "vendor_pmax": 3},
        "no slb real http": {"src": "xml", "args": [{"type": "STRING"}]},
        "user password": {"src": "xml", "args": [
            {"type": "STRING"}, {"type": "REDACTED_SENSITIVE", "executable": False}]},
    },
}

COMMANDS = [
    "show version", "show version extra", "show slb real", "show slb real r1 all",
    "slb real http r1 10.0.0.1 80", "slb real http r1 10.0.0.1 80 100",
    "slb real http r1 not-an-ip 80", "slb real http r1 10.0.0.1", "slb real http",
    "slb virtaul http v1 10.0.0.2 80", "SLB Virtual HTTP v1 10.0.0.2 80",
    'slb virtual http "v 1" 10.0.0.2 80', "no slb real http r1", "ip address 1.1.1.1 255.0.0.0",
    "user password admin secret", "", "123 show", "[x] y", "show 'unterminated",
]


def test_vendor_cmd_matches_infotest(infotest, monkeypatch):
    import main.case_compiler.vendor_stdlib as it_vendor

    from cex_core import vendor_cmd

    monkeypatch.setattr(it_vendor, "load_vendor_stdlib", lambda *a, **k: PROJECTION)
    for command in COMMANDS:
        assert vendor_cmd.resolve_vendor_command(command, PROJECTION) == \
            it_vendor.resolve_vendor_command(command), command
        assert vendor_cmd.norm_command_tokens(command) == it_vendor.norm_command_tokens(command)
    assert vendor_cmd.resolve_vendor_command("show version", None) == \
        {"decided": False, "hit": False, "head": "", "src": "", "version": "",
         "device_build": "", "origin": ""}


def test_defect_extractors_match_infotest(infotest):
    fixtures = sorted((INFOTEST_ROOT / "tests" / "ingest" / "fixtures").glob("*.html"))
    if not fixtures:
        pytest.skip("InfoTest 没有缺陷页夹具")
    try:
        from main.ingest.html_extractors import get_extractor as it_get
    except ImportError as exc:
        pytest.skip(f"InfoTest 缺陷解析依赖不全：{exc}")

    from cex_core.defects.html_extractors import get_extractor

    for path in fixtures:
        backend = "zentao" if path.name.startswith("zentao") else "bugzilla"
        html = path.read_text(encoding="utf-8", errors="ignore")
        ours = asdict(get_extractor(backend).extract(html))
        theirs = it_get(backend).extract(html).model_dump()
        theirs["attachments"] = [
            {"url": a["url"], "filename": a.get("filename", "")} for a in theirs["attachments"]]
        assert ours == {k: theirs[k] for k in ours}, path.name


SCRUB_SAMPLES = [
    "password=hunter2 and token: abcdef1234567890",
    "see http://intranet.example/path?q=1 and /etc/app/config.yaml",
    "C:\\Users\\someone\\secret.txt",
    "-----BEGIN RSA PRIVATE KEY-----\nMIIB\n-----END RSA PRIVATE KEY-----",
    "api_key: sk-live-000000000000",
    "普通的缺陷描述：配置 slb real http 后流量不通\n\n\n\n复现步骤如下",
    "<b>Authorization: Bearer abc.def.ghi</b>",
    "",
]


def test_scrub_matches_infotest(infotest):
    try:
        from main.defect_spec_source import contains_prohibited_declaration as it_prohibited
        from main.defect_spec_source import scrub_declaration_text as it_scrub
    except ImportError as exc:
        pytest.skip(f"InfoTest 脱敏依赖不全：{exc}")

    from cex_core.defects.scrub import contains_prohibited_declaration, scrub_declaration_text

    for text in SCRUB_SAMPLES:
        assert scrub_declaration_text(text) == it_scrub(text), text
        assert contains_prohibited_declaration(text) == it_prohibited(text), text
