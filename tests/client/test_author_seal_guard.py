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

    def reopened(_ws, name):
        raise ClientError(f"the machine mindmap of {name!r} is not sealed (receipt is prepared); "
                          "call cex_recompose_seal first")

    monkeypatch.setattr(author, "_sealed_batch", reopened)
    for call in _calls(ws):
        with pytest.raises(ClientError, match="cex_recompose_seal, then cex_author_prepare"):
            call()


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
