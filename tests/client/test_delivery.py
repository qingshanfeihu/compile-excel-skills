"""交付台账（issue #6）：拒收理由落盘、出件写批目录台账、叙事点名未进卷案。

假引擎只替闸与封印；台账的两个 fact 件用 fake_author_engine 的忠实替身（闭集拒未知名、
occurrence_id 防吞行），真模块的语义由不装假引擎的钉住用例直接 import 验证。"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import fake_author_engine as fe
from cex_client import author, delivery
from cex_client import workspace as wsmod
from conftest import REPO_ROOT
from cex_client.errors import ClientError

A = "202609240000000001"
B = "245861784181666726"
C = "245861784181694845"

REJECT = {"gate": "command_tree", "code": "command_not_in_tree", "locus": "blocks[0].F",
          "detail": "the step names a command the device tree does not carry"}


@pytest.fixture()
def ws(tmp_path, monkeypatch):
    monkeypatch.delenv("CEX_WORKSPACE", raising=False)
    fe.GATE_ROOTS.clear()
    fe.STAMPED_ROOTS.clear()
    fe.GATE_REJECTS.clear()
    fe.install(monkeypatch.setitem, monkeypatch.setattr)
    return wsmod.init(tmp_path / "ws", server="https://ces.example.test", device_build="B_1")


def _facts(batch: Path) -> list[dict]:
    path = batch / "facts.jsonl"
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_a_rejected_submission_survives_in_state_and_the_fact_ledger(ws):
    fe.published_batch(ws, "demo", [A, B])
    assert author.submit_case(ws, "demo", fe.body(A, "good case"))["ok"]
    fe.GATE_REJECTS[B] = [dict(REJECT)]
    first = author.submit_case(ws, "demo", fe.body(B, "bad case"))
    assert first["status"] == "rejected"
    second = author.submit_case(ws, "demo", fe.body(B, "still bad"))
    assert second["status"] == "rejected"

    state = author._load_state(ws, "demo")
    assert state["submissions"][A]["status"] == "sealed"
    assert state["submissions"][B]["attempt"] == 2
    assert state["submissions"][B]["status"] == "rejected"
    assert state["submissions"][B]["violations"][0]["code"] == "command_not_in_tree"

    batch = ws.outputs_dir / "demo"
    lines = _facts(batch)
    # 封存不占台账行；两次拒收各占一行（occurrence_id 不被幂等吞掉）
    assert [fact["ev"] for fact in lines] == ["mechanical_case_submission_rejected"] * 2
    assert lines[0]["aid"] == B and lines[0]["attempt"] == 1
    assert lines[1]["attempt"] == 2
    assert lines[0]["occurrence_id"] != lines[1]["occurrence_id"]
    assert lines[0]["violations"][0]["code"] == "command_not_in_tree"
    assert lines[0]["out_name"] == "demo"


def test_an_open_decision_is_recorded(ws):
    fe.published_batch(ws, "demo", [A])
    body = fe.body(A, "who answers this?")
    body["blocks"][0]["answerer"] = {"kind": "undetermined", "note": "who decides?"}
    out = author.submit_case(ws, "demo", body)
    assert out["status"] == "needs_user_decision"
    state = author._load_state(ws, "demo")
    assert state["submissions"][A]["status"] == "needs_user_decision"
    lines = _facts(ws.outputs_dir / "demo")
    assert [fact["ev"] for fact in lines] == ["needs_decision"]
    assert lines[0]["aid"] == A


def test_repeated_open_decisions_keep_one_ledger_line(ws):
    fe.published_batch(ws, "demo", [A])
    for _ in range(2):
        body = fe.body(A, "who answers this?")
        body["blocks"][0]["answerer"] = {"kind": "undetermined", "note": "who decides?"}
        assert author.submit_case(ws, "demo", body)["status"] == "needs_user_decision"
    assert len(_facts(ws.outputs_dir / "demo")) == 1  # needs_decision 幂等键 (ev, aid)，与原版一致


def test_emit_writes_the_ledger_and_names_every_missing_case(ws):
    fe.published_batch(ws, "demo", [A, B, C])
    assert author.submit_case(ws, "demo", fe.body(A, "good"))["ok"]
    fe.GATE_REJECTS[B] = [dict(REJECT)]
    assert author.submit_case(ws, "demo", fe.body(B, "bad"))["status"] == "rejected"
    out = author.emit(ws, "demo")
    assert out["ok"] is False and "error" in out

    batch = ws.outputs_dir / "demo"
    for name in ("manifest.json", "engine_report.json", "delivery_report.md",
                 "unsuccessful_cases.md"):
        assert (batch / name).is_file(), name
        assert Path(out["reports"][name]) == batch / name

    report = json.loads((batch / "engine_report.json").read_text(encoding="utf-8"))
    assert report["schema"] == "cex.engine-report"
    assert report["hard_check_contracted_equals_delivered"] is False
    totals = report["totals"]
    assert (totals["contracted"], totals["delivered"]) == (3, 1)
    assert totals["rejected_last"] == 1 and totals["not_submitted"] == 1
    assert report["cases"][A]["status"] == "delivered"
    assert report["cases"][A]["mechanical_case_sha256"]
    assert report["cases"][B]["status"] == "rejected"
    assert report["cases"][B]["last_submission"]["violations"][0]["code"] == "command_not_in_tree"
    assert report["cases"][C]["status"] == "not_submitted"
    assert sorted(report["not_delivered_autoids"]) == sorted([B, C])
    assert re.fullmatch(r"[0-9a-f]{64}", report["artifacts"]["case.xlsx.sha256"])

    md = (batch / "unsuccessful_cases.md").read_text(encoding="utf-8")
    assert f"## {B}" in md and "command_not_in_tree" in md
    assert f"## {C}" in md
    assert "无提交违规记录" in md  # C 从未提交：机理引文如实说没有记录，不编故事
    assert f"## {A}" not in md  # 进卷案不出现在未通过详报里

    delivery_md = (batch / "delivery_report.md").read_text(encoding="utf-8")
    assert "contracted 3 == delivered 1" in delivery_md and "不通过" in delivery_md
    assert "unsuccessful_cases.md" in delivery_md


def test_a_complete_batch_still_gets_the_ledger_without_the_failure_narrative(ws):
    fe.published_batch(ws, "demo", [A, B])
    for aid, text in ((A, "one"), (B, "two")):
        assert author.submit_case(ws, "demo", fe.body(aid, text))["ok"]
    out = author.emit(ws, "demo")
    assert out["ok"] is True

    batch = ws.outputs_dir / "demo"
    report = json.loads((batch / "engine_report.json").read_text(encoding="utf-8"))
    assert report["hard_check_contracted_equals_delivered"] is True
    assert report["not_delivered_autoids"] == []
    assert not (batch / "unsuccessful_cases.md").exists()
    assert (batch / "manifest.json").is_file() and (batch / "delivery_report.md").is_file()
    assert not (batch / "facts.jsonl").exists()  # 全成：没有拒收，台账不产空表
    manifest = json.loads((batch / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == "cex.batch-manifest"
    assert sorted(manifest["written_autoids"]) == sorted([A, B])
    assert manifest["contract_sha256_by_autoid"][A]


def test_a_batch_that_emits_nothing_still_leaves_the_ledger_behind(ws):
    fe.published_batch(ws, "demo", [A, B])
    fe.GATE_REJECTS[A] = [dict(REJECT)]
    fe.GATE_REJECTS[B] = [dict(REJECT)]
    for aid in (A, B):
        assert author.submit_case(ws, "demo", fe.body(aid, "x"))["status"] == "rejected"
    fe.GATE_REJECTS.clear()

    with pytest.raises(ClientError) as raised:
        author.emit(ws, "demo")
    assert "delivery_report.md" in str(raised.value)
    batch = ws.outputs_dir / "demo"
    assert not (batch / "case.xlsx").exists()
    report = json.loads((batch / "engine_report.json").read_text(encoding="utf-8"))
    assert report["totals"]["delivered"] == 0
    assert set(report["not_delivered_autoids"]) == {A, B}
    md = (batch / "unsuccessful_cases.md").read_text(encoding="utf-8")
    assert f"## {A}" in md and f"## {B}" in md
    assert "无提交违规记录" not in md  # 两案都有拒收记录，机理引文不是空话


def test_the_fact_ledger_appends_each_projection_and_dedupes_by_the_engines_keys(ws):
    batch = ws.outputs_dir / "demo"
    batch.mkdir(parents=True)
    receipt = {"ev": "recompose_done", "reentry_round": 0, "written": 1}
    delivery.append_facts(ws, batch, [delivery.recompose_done_event("demo", receipt)])
    delivery.append_facts(ws, batch, [delivery.recompose_done_event("demo", receipt)])
    # 重发布总落新行：读者从尾往前找最新一条，被旧回执顶住就是错账
    assert len(_facts(batch)) == 2
    delivery.append_facts(ws, batch, [delivery.decision_event("demo", A, ["note"])])
    delivery.append_facts(ws, batch, [delivery.decision_event("demo", A, ["note"])])
    assert len(_facts(batch)) == 3  # needs_decision 走原版幂等键 (ev, aid)
    with pytest.raises((ClientError, ValueError)):  # 闭集拒未知名（UnregisteredFactEvent）
        delivery.append_facts(ws, batch, [{"ev": "cex_something_new"}])


def test_the_written_facts_pass_the_real_engine_gate_and_the_tables_stay_pinned():
    # 不装假引擎：钉住真抽取件——事件名在闭集里、词表与 display_lexicon 一致、TS 镜像同值。
    from cex_core.engine.ist_core.compile_engine.fact_events import FACT_EVENTS
    from cex_core.engine.ist_core.display_lexicon import DELIVERY_FILE_LABEL_CN

    for name in (delivery.EV_RECOMPOSE_DONE, delivery.EV_SUBMISSION_REJECTED,
                 delivery.EV_NEEDS_DECISION):
        assert name in FACT_EVENTS, name
    for name, label in delivery.DELIVERY_FILE_LABELS.items():
        assert DELIVERY_FILE_LABEL_CN[name] == label, name

    ts = (REPO_ROOT / "ts" / "src" / "cex_client" / "delivery.ts").read_text(encoding="utf-8")

    def ts_const(name: str) -> str:
        found = re.search(rf"export const {name} = \"([^\"]+)\";", ts)
        assert found, name
        return found.group(1)

    assert ts_const("MANIFEST_SCHEMA") == delivery.MANIFEST_SCHEMA
    assert ts_const("REPORT_SCHEMA") == delivery.REPORT_SCHEMA
    assert ts_const("EV_RECOMPOSE_DONE") == delivery.EV_RECOMPOSE_DONE
    assert ts_const("EV_SUBMISSION_REJECTED") == delivery.EV_SUBMISSION_REJECTED
    assert ts_const("EV_NEEDS_DECISION") == delivery.EV_NEEDS_DECISION
    ts_labels = dict(re.findall(r"\"([\w.]+)\": \"(.*?)\"", ts.split("DELIVERY_FILE_LABEL_CN")[1]
                               .split("};")[0]))
    assert ts_labels == {k: v for k, v in delivery.DELIVERY_FILE_LABELS.items()}


def test_the_tool_specs_promise_the_ledger():
    for specs in (json.loads((REPO_ROOT / "cex_client" / "tool_specs.json").read_text("utf-8")),
                  json.loads((REPO_ROOT / "ts" / "src" / "cex_client" /
                              "tool_specs.json").read_text("utf-8"))):
        by_name = {tool["name"]: tool["description"] for tool in specs["tools"]}
        assert "delivery ledger" in by_name["cex_author_emit"]
        assert "engine_report.json" in by_name["cex_author_emit"]
        assert "batch ledger" in by_name["cex_author_submit_case"]
        assert "facts.jsonl" in by_name["cex_author_submit_case"]
