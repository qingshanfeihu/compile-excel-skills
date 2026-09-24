"""link_status reports missing OAuth and device credentials without printing secrets."""

import json
import os
import stat
import subprocess
import time
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "link_status.py"


def _run(env_file: Path, config_dir: Path) -> tuple[int, dict]:
    proc = subprocess.run(
        ["python3", str(SCRIPT)],
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "COMPILE_EXCEL_ENV": str(env_file),
            "COMPILE_EXCEL_CONFIG_DIR": str(config_dir),
        },
        check=False,
    )
    return proc.returncode, json.loads(proc.stdout)


def test_missing_oauth_and_device_password(tmp_path: Path) -> None:
    env_file = tmp_path / "env"
    env_file.write_text("KMS_ADDR=127.0.0.1:8900\nJUMPHOST_IP=127.0.0.1\n", encoding="utf-8")
    code, payload = _run(env_file, tmp_path / "cfg")
    assert code == 5
    assert payload["oauth"]["ok"] is False
    assert payload["device_credentials"]["missing"] == ["APV_USER", "APV_PASSWORD"]
    assert {item["key"] for item in payload["ask"]} == {"APV_USER", "APV_PASSWORD"}
    assert all(item["secret"] is True for item in payload["ask"])
    by_key = {item["key"]: item for item in payload["ask"]}
    assert by_key["APV_USER"]["mask"] is False
    assert by_key["APV_PASSWORD"]["mask"] is True
    assert any("重新登录" in msg for msg in payload["messages"])
    assert payload["run"][0]["script"] == "scripts/login.py"
    assert "设备用户名" in payload["prompt"]
    assert "root-password" not in proc_text(payload)


def test_ready_when_token_and_device_credentials_exist(tmp_path: Path) -> None:
    env_file = tmp_path / "env"
    env_file.write_text(
        "KMS_ADDR=127.0.0.1:8900\nJUMPHOST_IP=127.0.0.1\n"
        "APV_USER=admin\nAPV_PASSWORD=secret\n",
        encoding="utf-8",
    )
    config = tmp_path / "cfg"
    config.mkdir()
    token = config / "token"
    token.write_text(json.dumps({
        "access_token": "tok",
        "expires_at": int(time.time()) + 600,
        "server": "http://127.0.0.1:8900",
    }), encoding="utf-8")
    os.chmod(token, stat.S_IRUSR | stat.S_IWUSR)
    code, payload = _run(env_file, config)
    assert code == 0
    assert payload["ok"] is True
    assert payload["ask"] == []
    assert "secret" not in json.dumps(payload)


def proc_text(payload: dict) -> str:
    return json.dumps(payload)
