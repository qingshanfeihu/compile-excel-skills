"""工作区解析、明文策略、路径安全、私有文件读写。"""

from __future__ import annotations

import json
import os
import stat

import pytest

from cex_client import workspace as wsmod
from cex_client.errors import ClientError


def test_init_creates_private_state_and_find_walks_up(tmp_path, monkeypatch):
    monkeypatch.delenv("CEX_WORKSPACE", raising=False)
    ws = wsmod.init(tmp_path, server="https://ces.example.test", device_build="B_1")
    assert stat.S_IMODE(os.stat(ws.state_dir).st_mode) == 0o700
    assert (ws.state_dir / ".gitignore").read_text(encoding="utf-8").strip().endswith("*")
    assert stat.S_IMODE(os.stat(ws.config_path).st_mode) == 0o600
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    assert wsmod.find(nested).root == tmp_path.resolve()
    assert wsmod.find(tmp_path.parent) is None or wsmod.find(tmp_path.parent).root != tmp_path


def test_env_override(tmp_path, monkeypatch):
    wsmod.init(tmp_path, server="https://ces.example.test", device_build="B_1")
    monkeypatch.setenv("CEX_WORKSPACE", str(tmp_path))
    assert wsmod.find(tmp_path.parent).root == tmp_path.resolve()


def test_plaintext_policy():
    assert wsmod.check_server_url("http://127.0.0.1:8900", allow_insecure_http=False)
    assert wsmod.check_server_url("http://localhost:8900/", allow_insecure_http=False)
    assert wsmod.check_server_url("https://ces.example.test", allow_insecure_http=False)
    with pytest.raises(ClientError, match="clear text"):
        wsmod.check_server_url("http://10.0.0.5:8900", allow_insecure_http=False)
    assert wsmod.check_server_url("http://10.0.0.5:8900", allow_insecure_http=True)
    for bad in ("ftp://x", "https://user:pw@ces.example.test", "not a url", ""):
        with pytest.raises(ClientError):
            wsmod.check_server_url(bad, allow_insecure_http=True)


def test_changing_server_drops_old_token(tmp_path):
    ws = wsmod.init(tmp_path, server="https://a.example.test", device_build="B_1")
    wsmod.write_private_json(ws.token_path, {"access_token": "x", "server": ws.server})
    wsmod.init(tmp_path, server="https://b.example.test", device_build="B_1")
    assert not ws.token_path.exists()


def test_safe_paths():
    for good in ("spec/docs/规格说明.md", "cmdtree/vendor_stdlib_9.9_101.json"):
        assert wsmod.safe_relative_path(good) == good
    for bad in ("../x", "/etc/passwd", "a//b", "a/./b", "a/../b", "spec/.hidden", "a\\b",
                "a/b:c", "x\n"):
        with pytest.raises(ClientError):
            wsmod.safe_relative_path(bad)
    for good in ("cmdtree_585.xml", "SAMPLE_BUILD_LOCAL", "framework_tree.tar.gz", "v1.2-rc"):
        assert wsmod.safe_component(good, "build") == good
    for bad in ("..", "../evil", "a/b", "/etc/passwd", "", ".x", ".hidden", "a..b", "name\n",
                "x" * 200, None):
        with pytest.raises(ClientError):
            wsmod.safe_component(bad, "build")


def test_private_json_refuses_wide_permissions_and_symlinks(tmp_path):
    path = tmp_path / "token.json"
    wsmod.write_private_json(path, {"a": 1})
    assert wsmod.read_private_json(path) == {"a": 1}
    os.chmod(path, 0o644)
    with pytest.raises(ClientError, match="0600"):
        wsmod.read_private_json(path)
    link = tmp_path / "link.json"
    link.symlink_to(path)
    with pytest.raises(ClientError):
        wsmod.read_private_json(link)
    with pytest.raises(ClientError):
        wsmod.write_private_json(link, {"b": 2})
    assert json.loads(path.read_text(encoding="utf-8")) == {"a": 1}
