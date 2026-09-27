"""编写阶段的批次隔离与出件核对（胶水层；引擎函数用 fake_author_engine 替身）：

- 两个批次含同一 autoid：每案目录在各自批目录下，谁也不覆盖谁；闸按本批每案目录核出处（H3）；
- 出件逐案核封存时记下的哈希：文件被换过就不出这一案并点名；有未封存或被换过的案 ok=false（H3）；
- 旧版布局（compile_outputs/<autoid>/）的批：出件时核过哈希搬进本批目录，提交前按回执重盖（H3）；
- 同时提交几案：封存记录一条不丢（M4）；
- 契约卡给出闸认的 (块, 算子) 配对与本案的 concretizations；披露里客户端做不到的邀请换成如实说明（I5）。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import fake_author_engine as fe
from cex_client import author
from cex_client import workspace as wsmod
from conftest import REPO_ROOT

A = "202609240000000001"
B = "245861784181666726"
C = "245861784181694845"


@pytest.fixture()
def ws(tmp_path, monkeypatch):
    monkeypatch.delenv("CEX_WORKSPACE", raising=False)
    fe.GATE_ROOTS.clear()
    fe.STAMPED_ROOTS.clear()
    fe.install(monkeypatch.setitem, monkeypatch.setattr)
    return wsmod.init(tmp_path / "ws", server="https://ces.example.test", device_build="B_1")


def test_two_batches_sharing_an_autoid_keep_their_own_cases(ws):
    fe.published_batch(ws, "list-a", [A])
    fe.published_batch(ws, "list-b", [A])
    first = author.submit_case(ws, "list-a", fe.body(A, "batch A text"))
    assert first["ok"], first
    sealed_a = Path(first["artifact"])
    before = sealed_a.read_bytes()
    second = author.submit_case(ws, "list-b", fe.body(A, "batch B variant"))
    assert second["ok"], second
    assert sealed_a == ws.outputs_dir / "list-a" / "cases" / A / "mechanical_case.json"
    assert Path(second["artifact"]) == ws.outputs_dir / "list-b" / "cases" / A / "mechanical_case.json"
    assert sealed_a.read_bytes() == before, "batch B did not overwrite batch A's sealed case"
    assert fe.GATE_ROOTS == [str(ws.outputs_dir / "list-a" / "cases"),
                             str(ws.outputs_dir / "list-b" / "cases")]
    emitted = author.emit(ws, "list-a")
    assert emitted["ok"], emitted
    cases_json = (ws.outputs_dir / "list-a" / "cases.json").read_text(encoding="utf-8")
    assert "batch A text" in cases_json and "batch B variant" not in cases_json
    state = json.loads((ws.state_dir / "author" / "list-a.json").read_text(encoding="utf-8"))
    assert state["sealed"][A]["artifact"] == f"compile_outputs/list-a/cases/{A}/mechanical_case.json"


def test_emit_skips_a_replaced_sealed_file_and_reports_a_partial_batch(ws):
    fe.published_batch(ws, "demo", [A, B, C])
    assert author.submit_case(ws, "demo", fe.body(A, "original A"))["ok"]
    assert author.submit_case(ws, "demo", fe.body(C, "case C"))["ok"]
    artifact = ws.outputs_dir / "demo" / "cases" / A / "mechanical_case.json"
    # 有效封印、别的内容：像别的批按同一路径又封存了一次
    artifact.write_text(json.dumps(fe.seal_document(fe.body(A, "someone else's A"))),
                        encoding="utf-8")
    out = author.emit(ws, "demo")
    assert out["ok"] is False
    assert out["emitted_autoids"] == [C]
    assert out["not_sealed_autoids"] == [B]
    assert [item["autoid"] for item in out["not_emitted"]] == [A]
    assert "overwritten" in out["not_emitted"][0]["reason"]
    assert B in out["error"] and A in out["error"]
    cases_json = (ws.outputs_dir / "demo" / "cases.json").read_text(encoding="utf-8")
    assert "someone else's A" not in cases_json


def test_a_legacy_batch_moves_into_its_own_directory(ws):
    fe.published_batch(ws, "old", [A, B], legacy=True)
    legacy = ws.outputs_dir / A / "mechanical_case.json"
    legacy.parent.mkdir(parents=True)
    document = fe.seal_document({**fe.body(A, "sealed before the upgrade"),
                                 "binding": {"contract_sha256": author._load_state(ws, "old")[
                                     "receipt"]["contract_sha256_by_autoid"][A]}})
    legacy.write_text(json.dumps(document), encoding="utf-8")

    def seal_legacy(state):
        state["sealed"][A] = {"artifact": str(Path("/old/location/ws") / "compile_outputs" / A
                                              / "mechanical_case.json"),
                              "mechanical_case_sha256": document["seal"]["mechanical_case_sha256"],
                              "contract_sha256": document["binding"]["contract_sha256"]}

    author._update_state(ws, "old", seal_legacy)
    # 提交前按回执把每案重盖到本批目录（intent 在旧位置可能已被同 autoid 的别的批覆盖）
    assert author.submit_case(ws, "old", fe.body(B, "new B"))["ok"]
    assert fe.STAMPED_ROOTS == [str(ws.outputs_dir / "old" / "cases")] * 2
    assert fe.GATE_ROOTS == [str(ws.outputs_dir / "old" / "cases")]
    out = author.emit(ws, "old")
    assert out["ok"], out
    moved = ws.outputs_dir / "old" / "cases" / A / "mechanical_case.json"
    assert moved.read_bytes() == legacy.read_bytes()
    state = author._load_state(ws, "old")
    assert state["sealed"][A]["artifact"] == f"compile_outputs/old/cases/{A}/mechanical_case.json"
    assert state["cases_root"] == "compile_outputs/old/cases"


def test_concurrent_submissions_keep_every_sealed_case(ws):
    aids = [A, B, C]
    fe.published_batch(ws, "demo", aids)
    tests_dir = Path(__file__).resolve().parent
    script = f"""
import json, sys
from pathlib import Path
sys.path.insert(0, {str(REPO_ROOT)!r})
sys.path.insert(0, {str(tests_dir)!r})
import fake_author_engine as fe
fe.install()
from cex_client import author, workspace as wsmod
ws = wsmod.Workspace(Path({str(ws.root)!r}))
print(json.dumps(author.submit_case(ws, "demo", fe.body(sys.argv[1], "text " + sys.argv[1]))))
"""
    env = {**os.environ, "FAKE_GATE_DELAY": "0.6"}
    procs = [subprocess.Popen([sys.executable, "-c", script, aid], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True, env=env) for aid in aids]
    results = [p.communicate(timeout=120) for p in procs]
    assert all(json.loads(out)["ok"] for out, _err in results), results
    sealed = author._load_state(ws, "demo")["sealed"]
    assert sorted(sealed) == sorted(aids), "no sealed record was lost"


def test_contract_cards_carry_the_gate_slots_and_the_concretizations(tmp_path):
    batch = tmp_path / "demo"
    (batch / "contracts").mkdir(parents=True)
    contract = {"intent_verbatim": "t", "expectations": [
        {"text": "配置未被保存", "author_claim": {"expectation_id": "e1", "semantic_key": "k1",
                                          "kind": "Author"},
         "normalized_claim": {"criterion_type": "reachability", "criterion_label_zh": "可达性"}}]}
    (batch / "contracts" / f"{A}.json").write_text(json.dumps(contract, ensure_ascii=False),
                                                   encoding="utf-8")
    slots = {"reachability": [["OBSERVE_ASSERT", "abs_found"], ["OBSERVE_ASSERT", "found"],
                              ["OBSERVE_EXIT", ""]]}
    concretizations = [{"slot": "port", "author_text": "端口", "value": "53"}]
    card = author._card_view(batch, A, slots, {"autoid": A, "concretizations": concretizations})
    expectation = card["expectations"][0]
    assert expectation["allowed_slots"] == slots["reachability"]
    assert "allowed_block_kinds" not in expectation and "allowed_operators" not in expectation
    assert card["concretizations"] == concretizations


def test_the_card_slots_are_the_gates_own_table(tmp_path):
    """allowed_slots 取的就是提交规则闸 criterion_type_binding 用的那张表。"""
    code = f"""
import json, sys
sys.path.insert(0, {str(REPO_ROOT)!r})
from cex_client import author
from cex_core.engine.case_compiler import mechanical_case_gate as gate
table = {{k: sorted([list(p) for p in v]) for k, v in gate.CRITERION_TYPE_ALLOWED_SLOTS.items()}}
print(json.dumps({{"ours": author._allowed_slots(), "gate": table}}))
"""
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                          timeout=300, env={**os.environ, "CEX_ENGINE_DATA_ROOT": str(tmp_path)})
    assert proc.returncode == 0, proc.stderr[-3000:]
    result = json.loads(proc.stdout.strip().splitlines()[-1])
    assert result["ours"] == result["gate"] and result["ours"]
    assert ["OBSERVE_EXIT", ""] in result["ours"]["reachability"]


def test_the_disclosure_no_longer_offers_a_veto_nobody_can_execute():
    projector = (REPO_ROOT / "cex_core" / "engine" / "case_compiler"
                 / "mindmap_contract_projector.py").read_text(encoding="utf-8")
    template = "这条归类是引擎裁定的，与你写的不符就可以翻掉：答「"
    assert template in projector, "the engine wording changed; revisit the rewrite"
    message = ("依据手册 cli_cn.md:12；这条归类是引擎裁定的，与你写的不符就可以翻掉：答「否决并重裁」"
               "（键 0123456789abcdef），下次同类编译重新裁定")
    rewritten = author.client_disclosure_message(message)
    assert "否决并重裁" not in rewritten and "翻掉：答" not in rewritten
    assert rewritten.startswith("依据手册 cli_cn.md:12；") and "报告" in rewritten


def test_a_precedent_source_without_the_identity_table_is_a_clear_error(ws, monkeypatch):
    """提交规则闸拿引擎的拒用包身份表核 precedent 出处；发行版不带这张表时说清楚缺什么，
    而不是让闸报一个看不出原因的 E_PACKAGE_INDEX_UNAVAILABLE。"""
    from cex_client import tools

    fe.published_batch(ws, "demo", [A, B])
    monkeypatch.setattr(author, "_identity_table_missing",
                        lambda: "CEX_ENGINE_IDENTITIES is not set")
    cited = fe.body(A, "cites a verified package")
    cited["blocks"][0]["ref"] = "precedent:case.xlsx"
    out = tools.call("cex_author_submit_case", {"workspace": str(ws.root), "out_name": "demo",
                                                "mechanical_case": cited})
    assert out["ok"] is False and "identity table" in out["error"] and "block(s) [0]" in out["error"]
    assert "CEX_ENGINE_IDENTITIES" in out["error"] and fe.GATE_ROOTS == [], "stopped before the gate"
    assert author.submit_case(ws, "demo", fe.body(B, "no precedent"))["ok"], "other cases go on"


def test_the_identity_check_uses_the_engine_table_and_expansion(tmp_path):
    """真引擎：身份表不可用且引用了 precedent（块级或断言级）→ 说清楚的 ClientError；
    表可用、或没引用 precedent → 放行。块的展开要 Excel 函数契约：只读地借 InfoTest 检出当数据根。"""
    from conftest import INFOTEST_ROOT

    if not (INFOTEST_ROOT / "knowledge" / "data" / "compile_ref" / "excel_contract.json").is_file():
        pytest.skip(f"no InfoTest checkout with the Excel function contract at {INFOTEST_ROOT}")
    code = f"""
import json, os, sys
sys.path.insert(0, {str(REPO_ROOT)!r})
from cex_client import author
from cex_client.errors import ClientError
config = {{"kind": "CONFIG", "host": "APV_0", "cmds": ["slb real http r 10.0.0.1 80"], "desc": "c"}}
observe = {{"kind": "OBSERVE_ASSERT", "host": "APV_0", "cmd": "show slb real", "desc": "o",
            "asserts": [{{"op": "found", "pattern": "r", "ref": "precedent:x.xlsx#1"}}]}}
out = {{}}
for label, blocks in (("assert_level", [config, observe]),
                      ("block_level", [dict(config, ref="precedent:x.xlsx")]),
                      ("none", [config])):
    try:
        author._require_identity_table({{"blocks": blocks}})
        out[label] = ""
    except ClientError as exc:
        out[label] = str(exc)
print(json.dumps(out))
"""
    missing = tmp_path / "absent.json"
    table = tmp_path / "identities.json"
    table.write_text(json.dumps({"main/case_compiler/package_advisories.py:DENIED_668_AUTOIDS": []}),
                     encoding="utf-8")
    results = {}
    for name, identities in (("missing", missing), ("present", table)):
        proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                              timeout=300, env={**os.environ, "CEX_ENGINE_DATA_ROOT": str(INFOTEST_ROOT),
                                                "CEX_ENGINE_IDENTITIES": str(identities)})
        assert proc.returncode == 0, proc.stderr[-3000:]
        results[name] = json.loads(proc.stdout.strip().splitlines()[-1])
    assert "block(s) [1]" in results["missing"]["assert_level"]
    assert "block(s) [0]" in results["missing"]["block_level"]
    assert "identity table" in results["missing"]["block_level"] and str(missing) in \
        results["missing"]["block_level"]
    assert results["missing"]["none"] == ""
    assert results["present"] == {"assert_level": "", "block_level": "", "none": ""}
