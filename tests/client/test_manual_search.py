"""Manual queries use the verified bundle for this workspace's device build."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from cex_client import auth, manual_search, tools
from cex_client import workspace as wsmod
from cex_client.errors import ServerUnreachable


def _bundle(ws: wsmod.Workspace, files: dict[str, str], *, bundle_id: str = "bundle-test") -> None:
    root = ws.bundle_dir()
    root.mkdir(parents=True)
    entries = []
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = text.encode("utf-8")
        path.write_bytes(raw)
        entries.append({"path": rel, "kind": "manual", "sha256": hashlib.sha256(raw).hexdigest()})
    (root / "manifest.json").write_text(json.dumps({
        "schema": "cex.bundle/v1", "build": ws.device_build,
        "bundle_id": bundle_id, "entries": entries,
    }), encoding="utf-8")


def test_queries_all_manual_markdown_and_returns_citations(tmp_path: Path, monkeypatch) -> None:
    ws = wsmod.init(tmp_path / "ws", server="https://unused.example", device_build="SAMPLE_BUILD_LOCAL")
    _bundle(ws, {
        "manual/10.5.0/cli_cn.md": (
            "# CLI\n"
            "slb virtual list\n"
            "The HTTPSLIST entry.\n"
            "slb virtual httpslist add service\n"
            "下一行是上下文\n"
            "配置虚拟服务的 httplist。\n"
        ),
        "manual/10.5.0/app_cn.md": "# APP\n虚拟服务的设置\n",
        "manual/10.6.0/extra.md": "# Extra\nSLB VIRTUAL httpslist\n",
        "manual/10.5.0/cli_cn.md.catalog.json": '{"description": "slb virtual httpslist"}',
    })
    monkeypatch.setattr(auth, "request_json", lambda *_args, **_kwargs: {"results": []})

    out = tools.call("cex_docs_query", {"workspace": str(ws.root),
                                        "q": "SLB virtual HTTPSLIST", "limit": 2})
    assert out["ok"] is True and out["build"] == "SAMPLE_BUILD_LOCAL"
    assert out["bundle_id"] == "bundle-test" and out["manuals_searched"] == 3
    assert len(out["results"]) == 2
    assert out["results"][0]["path"] == "10.5.0/cli_cn.md"
    assert out["results"][0]["line"] == 4
    assert out["results"][0]["ref"] == "manual:10.5.0/cli_cn.md:4"
    assert "3: The HTTPSLIST entry." in out["results"][0]["snippet"]
    assert all(row["all_terms"] for row in out["results"])

    chinese = tools.call("cex_docs_query", {"workspace": str(ws.root), "q": "虚拟服务"})
    assert chinese["results"][0]["ref"] == "manual:10.5.0/app_cn.md:2"


def test_full_line_match_outranks_nearby_terms_and_limit_is_clamped(
        tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(auth, "request_json", lambda *_args, **_kwargs: {"results": []})
    ws = wsmod.init(tmp_path / "ws", server="https://unused.example", device_build="SAMPLE_BUILD_LOCAL")
    _bundle(ws, {"manual/v/cli.md": (
        "alpha\n"
        "beta\n"
        "alpha beta\n"
        "alpha beta twice alpha beta\n"
        "alpha only\n"
    )})
    one = tools.call("cex_docs_query", {"workspace": str(ws.root), "q": "alpha beta", "limit": 0})
    assert len(one["results"]) == 1 and one["results"][0]["line"] == 4
    ten = tools.call("cex_docs_query", {"workspace": str(ws.root), "q": "alpha", "limit": 99})
    assert 1 < len(ten["results"]) <= 10


@pytest.mark.parametrize("query", [
    "slb virtual http", '"slb virtual http"', "`slb virtual http`",
    "slb virtual http,", "slb-virtual-http", "SLB，VIRTUAL，HTTP",
])
def test_punctuation_and_case_share_search_terms(tmp_path: Path, query: str) -> None:
    ws = wsmod.init(tmp_path / "ws", server="https://unused.example",
                    device_build="SAMPLE_BUILD_LOCAL")
    _bundle(ws, {"manual/v/cli.md": "slb virtual http add service\n"})
    result = manual_search.query(ws, query, 3)
    assert result["results"][0]["ref"] == "manual:v/cli.md:1"
    assert result["results"][0]["all_terms"] is True


@pytest.mark.parametrize("query", ["“虚拟服务”", "配置HTTP虚拟服务"])
def test_han_characters_match_inside_manual_lines(tmp_path: Path, query: str) -> None:
    ws = wsmod.init(tmp_path / "ws", server="https://unused.example",
                    device_build="SAMPLE_BUILD_LOCAL")
    _bundle(ws, {"manual/v/cli.md": "配置HTTP虚拟服务\n"})
    result = manual_search.query(ws, query, 3)
    assert result["results"][0]["ref"] == "manual:v/cli.md:1"
    assert result["results"][0]["all_terms"] is True


def test_more_distinct_terms_outrank_repeated_partial_match(tmp_path: Path) -> None:
    ws = wsmod.init(tmp_path / "ws", server="https://unused.example",
                    device_build="SAMPLE_BUILD_LOCAL")
    _bundle(ws, {"manual/v/cli.md": "alpha alpha alpha alpha\nalpha beta\n"})
    result = manual_search.query(ws, "alpha beta", 3)
    assert result["results"][0]["line"] == 2


def test_online_search_appends_server_documents_without_manual_citations(
        tmp_path: Path, monkeypatch) -> None:
    ws = wsmod.init(tmp_path / "ws", server="https://unused.example",
                    device_build="SAMPLE_BUILD_LOCAL")
    _bundle(ws, {"manual/v/cli.md": "alpha beta\n"})
    calls = []

    def server_docs(_ws, method, path, **kwargs):
        calls.append((method, path, kwargs))
        return {"schema": "ist.excel.docs-query", "results": [
            {"doc": "EXCEL_FUNCS.md", "title": "Functions", "snippet": "alpha beta",
             "ref": "manual:wrong.md:1"}]}

    monkeypatch.setattr(auth, "request_json", server_docs)
    out = tools.call("cex_docs_query", {"workspace": str(ws.root), "q": "alpha beta", "limit": 2})
    assert out["ok"] and out["server_searched"] and len(out["results"]) == 2
    assert out["results"][0]["source"] == "local_manual"
    assert out["results"][0]["ref"] == "manual:v/cli.md:1"
    assert out["results"][1]["source"] == "server_document"
    assert out["results"][1]["doc"] == "EXCEL_FUNCS.md"
    assert "ref" not in out["results"][1]
    assert calls[0][0:2] == ("POST", "/v1/docs/query")


def test_bundle_without_manuals_uses_server_and_reports_offline_supply_failure(
        tmp_path: Path, monkeypatch) -> None:
    ws = wsmod.init(tmp_path / "ws", server="https://unused.example",
                    device_build="SAMPLE_BUILD_LOCAL")
    _bundle(ws, {"spec/reference.md": "not a manual\n"})
    monkeypatch.setattr(auth, "request_json", lambda *_args, **_kwargs: {
        "results": [{"doc": "EXCEL_FUNCS.md", "snippet": "lookup method"}]})
    online = tools.call("cex_docs_query", {"workspace": str(ws.root), "q": "lookup"})
    assert online["ok"] and online["manuals_searched"] == 0
    assert online["results"][0]["source"] == "server_document"
    assert "No searchable local manuals" in online["local_note"]

    def offline(*_args, **_kwargs):
        raise ServerUnreachable("server unreachable (test offline)")

    monkeypatch.setattr(auth, "request_json", offline)
    unavailable = tools.call("cex_docs_query", {"workspace": str(ws.root), "q": "lookup"})
    assert unavailable["ok"] is False and unavailable["results"] == []
    assert unavailable["server_searched"] is False
    assert "server unreachable" in unavailable["error"]
    assert "supply failure" in unavailable["error"]


def test_offline_search_returns_local_manual_with_server_note(tmp_path: Path, monkeypatch) -> None:
    ws = wsmod.init(tmp_path / "ws", server="https://unused.example",
                    device_build="SAMPLE_BUILD_LOCAL")
    _bundle(ws, {"manual/v/cli.md": "alpha beta\n"})
    monkeypatch.setattr(auth, "request_json", lambda *_args, **_kwargs: (
        _ for _ in ()).throw(ServerUnreachable("server unreachable (test offline)")))
    out = tools.call("cex_docs_query", {"workspace": str(ws.root), "q": "alpha"})
    assert out["ok"] and not out["server_searched"]
    assert "were not searched" in out["server_note"]
    assert [row["source"] for row in out["results"]] == ["local_manual"]


def test_missing_or_modified_bundle_fails_with_sync_hint(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(auth, "request_json", lambda *_args, **_kwargs: (
        _ for _ in ()).throw(ServerUnreachable("server unreachable (test offline)")))
    ws = wsmod.init(tmp_path / "ws", server="https://unused.example", device_build="SAMPLE_BUILD_LOCAL")
    missing = tools.call("cex_docs_query", {"workspace": str(ws.root), "q": "slb"})
    assert missing["ok"] is False and missing["build"] == "SAMPLE_BUILD_LOCAL"
    assert "cex_sync" in missing["next"]

    _bundle(ws, {"manual/v/cli.md": "slb virtual\n"})
    (ws.bundle_dir() / "manual/v/cli.md").write_text("tampered\n", encoding="utf-8")
    corrupt = tools.call("cex_docs_query", {"workspace": str(ws.root), "q": "slb"})
    assert corrupt["ok"] is False and "cex_sync" in corrupt["error"]
