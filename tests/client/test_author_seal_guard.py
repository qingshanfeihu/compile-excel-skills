"""编写阶段只在 cex_author_prepare 时那份密封上继续：重组批次被 cex_recompose_prepare 重开
（machine_mindmap.json 被删、回执退回 prepared）或重新密封成别的内容后，提交、判据裁定与出件
都拒绝，并指明先重新密封、再重新出契约卡；重开一个已密封的批次时，prepare 自己也说清楚。"""

from __future__ import annotations

import json

import pytest

from cex_client import author, recompose
from cex_client import workspace as wsmod
from cex_client.errors import ClientError

SEALED = "a" * 64


def _workspace(tmp_path, monkeypatch) -> wsmod.Workspace:
    monkeypatch.delenv("CEX_WORKSPACE", raising=False)
    ws = wsmod.init(tmp_path, server="https://ces.example.test", device_build="B_1")
    author._save_state(ws, {
        "out_name": "demo", "phase": "published", "cases": {}, "sealed": {},
        "pending": {"shape-1": {}},
        "receipt": {"machine_mindmap_sha256": SEALED, "written_autoids": ["100000000000000001"]}})
    return ws


def _calls(ws):
    return (lambda: author.submit_case(ws, "demo", {"autoid": "100000000000000001"}),
            lambda: author.emit(ws, "demo"),
            lambda: author.criterion_record(ws, "demo", "shape-1", {}))


def test_authoring_refuses_a_reopened_batch(tmp_path, monkeypatch):
    ws = _workspace(tmp_path, monkeypatch)
    order = []

    def reopened(_ws, name):
        order.append("seal check")
        raise ClientError(f"the machine mindmap of {name!r} is not sealed (receipt is prepared); "
                          "call cex_recompose_seal first")

    monkeypatch.setattr(author.engine_env, "prepare", lambda _ws: order.append("engine") or (None, {}))
    monkeypatch.setattr(author, "_sealed_batch", reopened)
    for call in _calls(ws):
        with pytest.raises(ClientError, match="cex_recompose_seal, then cex_author_prepare"):
            call()
    # 每个工具调用是新进程：核对密封前必须先接好引擎（数据根），否则连领域文法都读不到
    assert order[:2] == ["engine", "seal check"]


def test_authoring_refuses_a_different_seal_and_goes_on_with_the_same_one(tmp_path, monkeypatch):
    ws = _workspace(tmp_path, monkeypatch)
    monkeypatch.setattr(author, "_current_seal_sha", lambda _ws, _name: "b" * 64)
    for call in _calls(ws):
        with pytest.raises(ClientError, match="sealed again since cex_author_prepare"):
            call()

    class PastTheGuard(Exception):
        pass

    def next_step(_ws):
        raise PastTheGuard

    monkeypatch.setattr(author, "_current_seal_sha", lambda _ws, _name: SEALED)
    monkeypatch.setattr(author.engine_env, "prepare", next_step)
    for call in _calls(ws):
        with pytest.raises(PastTheGuard):
            call()


def test_a_batch_counts_as_sealed_only_with_a_submitted_receipt_and_the_artifact(tmp_path):
    batch = tmp_path / "demo"
    batch.mkdir()
    receipt = batch / ".machine_mindmap_submission.json"
    assert not recompose._is_sealed(batch)
    receipt.write_text(json.dumps({"status": "submitted"}), encoding="utf-8")
    assert not recompose._is_sealed(batch), "a receipt without the artifact is not a seal"
    (batch / "machine_mindmap.json").write_text("{}", encoding="utf-8")
    assert recompose._is_sealed(batch)
    receipt.write_text(json.dumps({"status": "prepared"}), encoding="utf-8")
    assert not recompose._is_sealed(batch), "a reopened batch is not sealed"


def test_lang_query_on_a_sealed_batch_answers_without_recording(tmp_path, monkeypatch):
    """编写阶段也要查参数契约与出处：批次已密封（派发作用域已关）时照常给结果、不记进 grounding。"""
    import sys
    import types

    from cex_client import engine_env

    calls = []
    fake = types.ModuleType("lang_query_tool")
    fake.lang_query = types.SimpleNamespace(func=lambda **kw: calls.append(kw) or "answer")
    monkeypatch.setitem(sys.modules, "cex_core.engine.ist_core.tools.device.lang_query_tool", fake)
    monkeypatch.setattr(recompose, "_load_state", lambda _ws, name: {
        "out_name": name, "data_root": str(tmp_path / "data"), "dispatch_id": "d"})
    monkeypatch.setattr(recompose, "_is_sealed", lambda _batch: True)
    monkeypatch.setattr(engine_env, "activate", lambda _root: None)

    def closed_scope(*_a, **_k):
        raise AssertionError("a sealed batch has no open dispatch scope to enter")

    monkeypatch.setattr(recompose, "_scope", closed_scope)
    ws = types.SimpleNamespace(outputs_dir=tmp_path)
    out = recompose.lang_query(ws, {"kind": "usage", "name": "dig"}, out_name="demo")
    assert out["ok"] and out["result"] == "answer" and "not recorded" in out["note"]
    assert calls == [{"kind": "usage", "name": "dig"}]


def test_criterion_adjudication_goes_on_before_any_receipt_exists(tmp_path, monkeypatch):
    """prepare 停在 criterion_pending 时状态里还没有 receipt：裁定不能被密封核对误拦。"""
    monkeypatch.delenv("CEX_WORKSPACE", raising=False)
    ws = wsmod.init(tmp_path, server="https://ces.example.test", device_build="B_1")
    author._save_state(ws, {"out_name": "demo", "phase": "criterion_pending",
                            "pending": {"shape-1": {}}, "brief": {}, "brief_paths": {},
                            "projected_machine_mindmap_sha256": SEALED})

    class PastTheGuard(Exception):
        pass

    def next_step(_ws):
        raise PastTheGuard

    monkeypatch.setattr(author, "_current_seal_sha", lambda _ws, _name: SEALED)
    monkeypatch.setattr(author.engine_env, "prepare", next_step)
    with pytest.raises(PastTheGuard):
        author.criterion_record(ws, "demo", "shape-1", {})
    monkeypatch.setattr(author, "_current_seal_sha", lambda _ws, _name: "b" * 64)
    with pytest.raises(ClientError, match="sealed again since cex_author_prepare"):
        author.criterion_record(ws, "demo", "shape-1", {})
