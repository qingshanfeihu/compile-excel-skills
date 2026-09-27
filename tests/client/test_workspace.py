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


def test_env_applies_only_without_an_explicit_workspace(tmp_path, monkeypatch):
    """CEX_WORKSPACE 只在没给起点时生效：工具参数里明说的 workspace 不能被环境变量盖掉。"""
    env_ws = tmp_path / "from_env"
    arg_ws = tmp_path / "from_arg"
    wsmod.init(env_ws, server="https://ces.example.test", device_build="B_1")
    wsmod.init(arg_ws, server="https://ces.example.test", device_build="B_2")
    monkeypatch.setenv("CEX_WORKSPACE", str(env_ws))
    assert wsmod.find().root == env_ws.resolve()
    assert wsmod.find(arg_ws).root == arg_ws.resolve()
    from cex_client import tools

    status = tools.call("cex_status", {"workspace": str(arg_ws)})
    assert status["workspace"] == str(arg_ws.resolve()) and status["device_build"] == "B_2"


def test_changing_server_drops_everything_that_belonged_to_the_old_one(tmp_path):
    ws = wsmod.init(tmp_path, server="https://a.example.test", device_build="B_1")
    for path in (ws.token_path, ws.client_config_path, ws.lease_path, ws.pending_login_path):
        wsmod.write_private_json(path, {"server": ws.server, "gateway": {"url": "https://gw.a"}})
    wsmod.init(tmp_path, server="https://a.example.test", device_build="B_2")
    assert ws.client_config_path.exists(), "same server: the cached org config stays"
    wsmod.init(tmp_path, server="https://b.example.test", device_build="B_1")
    for path in (ws.token_path, ws.client_config_path, ws.lease_path, ws.pending_login_path):
        assert not path.exists(), path.name


def test_safe_writes_refuse_symlinks_on_the_way(tmp_path):
    root = tmp_path / "ws"
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "compile_outputs" / "b1").mkdir(parents=True)
    victim = outside / "victim.txt"
    victim.write_text("keep", encoding="utf-8")
    (root / "compile_outputs" / "b1" / "cases.json").symlink_to(victim)
    with pytest.raises(ClientError, match="symlink"):
        wsmod.write_file_safely(root, root / "compile_outputs" / "b1" / "cases.json", b"x")
    (root / "defects").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ClientError, match="symlink"):
        wsmod.write_file_safely(root, root / "defects" / "bugzilla" / "BUG-1.json", b"x")
    assert victim.read_text(encoding="utf-8") == "keep" and not (outside / "bugzilla").exists()
    # 预先放好的固定临时名（旧实现写 .<名>.tmp）不再被跟随
    batch = root / "compile_outputs" / "b2"
    batch.mkdir()
    (batch / ".mindmap_source.json.tmp").symlink_to(victim)
    wsmod.write_file_safely(root, batch / "mindmap_source.json", b"new")
    assert (batch / "mindmap_source.json").read_bytes() == b"new"
    assert victim.read_text(encoding="utf-8") == "keep"
    with pytest.raises(ClientError, match="outside"):
        wsmod.write_file_safely(root, outside / "x.json", b"x")


def test_state_paths_are_relative_and_old_absolute_ones_follow_a_renamed_folder(tmp_path):
    ws = wsmod.init(tmp_path / "renamed", server="https://ces.example.test", device_build="B_1")
    inside = ws.outputs_dir / "b1" / "cases" / "1" / "mechanical_case.json"
    assert wsmod.to_state_path(ws, inside) == "compile_outputs/b1/cases/1/mechanical_case.json"
    assert wsmod.from_state_path(ws, "compile_outputs/b1/x.json") == ws.root / "compile_outputs/b1/x.json"
    old = "/somewhere/old-name/.compile-excel/engine/0123456789abcdef"
    assert wsmod.from_state_path(ws, old) == ws.state_dir / "engine" / "0123456789abcdef"
    old_artifact = "/somewhere/old-name/compile_outputs/202609240000000001/mechanical_case.json"
    assert wsmod.from_state_path(ws, old_artifact) == \
        ws.outputs_dir / "202609240000000001" / "mechanical_case.json"


def test_state_lock_serialises_read_modify_write_across_processes(tmp_path):
    """同一把工作区锁下的"读—改—写"不丢更新（每个进程各加一项）。"""
    import subprocess
    import sys

    from conftest import REPO_ROOT

    ws = wsmod.init(tmp_path, server="https://ces.example.test", device_build="B_1")
    script = f"""
import json, sys, time
from pathlib import Path
sys.path.insert(0, {str(REPO_ROOT)!r})
from cex_client import workspace as wsmod
ws = wsmod.Workspace(Path({str(ws.root)!r}))
path = ws.state_dir / "counter.json"
with wsmod.state_lock(ws, "counter"):
    data = wsmod.read_private_json(path) or {{}}
    time.sleep(0.2)
    data[sys.argv[1]] = True
    wsmod.write_private_json(path, data)
"""
    procs = [subprocess.Popen([sys.executable, "-c", script, str(i)]) for i in range(4)]
    assert [p.wait(timeout=60) for p in procs] == [0, 0, 0, 0]
    assert sorted(wsmod.read_private_json(ws.state_dir / "counter.json")) == ["0", "1", "2", "3"]


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
