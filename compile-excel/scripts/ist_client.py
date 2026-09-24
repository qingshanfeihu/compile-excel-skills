"""compile-excel 分发客户端共享库（工作流 B；纯 stdlib）。

职责：
- token 生命周期：~/.config/compile-excel/token（0600，原子写盘，读时校验权限）；
- OAuth2 设备授权流（device_authorize → 轮询 /token → refresh）；
- manifest 拉取、工件下载（逐件 SHA256 校验不符即拒）、断网缓存回退（明示版本）。

机密纪律：token 只落 0600 文件，绝不进 argv/日志/异常消息。
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ist_emit._sealed_io import (  # noqa: E402
    atomic_write_bytes_nofollow,
    read_regular_nofollow,
)

DEVICE_GRANT = "urn:ietf:params:oauth:grant-type:device_code"

CONFIG_DIR = Path(
    os.environ.get("COMPILE_EXCEL_CONFIG_DIR")
    or Path.home() / ".config" / "compile-excel"
)
CACHE_DIR = Path(
    os.environ.get("COMPILE_EXCEL_CACHE_DIR")
    or Path.home() / ".cache" / "compile-excel"
)
TOKEN_PATH = CONFIG_DIR / "token"
DEFAULT_SERVER = "http://127.0.0.1:8900"
TOKEN_MAX_BYTES = 8 * 1024


class ClientError(Exception):
    """所有客户端失败的结构化异常；消息不含任何机密。"""


def _load_env_file() -> dict[str, str]:
    """从环境绑定文件读取配置（与 preflight.py 同逻辑）。"""
    candidates = []
    explicit = os.environ.get("COMPILE_EXCEL_ENV")
    if explicit:
        candidates.append(Path(explicit).expanduser())
    candidates.append(Path.cwd() / ".circle" / "compile-excel.env")
    candidates.append(Path.home() / ".config" / "compile-excel" / "env")
    for path in candidates:
        if path.is_file():
            data: dict[str, str] = {}
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                data[key.strip()] = value.strip()
            return data
    return {}


def server_url() -> str:
    """优先级：$COMPILE_EXCEL_SERVER > 环境文件 KMS_ADDR > 默认 127.0.0.1。"""
    explicit = os.environ.get("COMPILE_EXCEL_SERVER")
    if explicit:
        return explicit.rstrip("/")
    env = _load_env_file()
    kms_addr = env.get("KMS_ADDR", "").strip()
    if kms_addr:
        # KMS_ADDR 格式为 host:port，转为 http://host:port
        if not kms_addr.startswith(("http://", "https://")):
            kms_addr = f"http://{kms_addr}"
        return kms_addr.rstrip("/")
    return DEFAULT_SERVER.rstrip("/")


# ── token 存取（0600 原子落盘；读时核权限）──────────────────────────────

def save_token(payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    try:
        atomic_write_bytes_nofollow(
            TOKEN_PATH, body,
            error_type=ClientError,
            invalid_message="token 路径非法",
            unavailable_message="token 写盘失败",
            create_parents=True,
            mode=0o600,
        )
    except ClientError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ClientError(f"token 写盘失败: {type(exc).__name__}") from exc


def load_token() -> dict[str, Any]:
    try:
        payload = read_regular_nofollow(
            TOKEN_PATH,
            error_type=ClientError,
            invalid_message="token 路径非法",
            directory_message="token 目录不可用",
            open_message="未登录（token 不存在）",
            bounds_message="token 文件异常",
            changed_message="token 读取期间发生变化",
            max_bytes=TOKEN_MAX_BYTES,
        )
    except ClientError as exc:
        if "未登录" in str(exc):
            return {}
        raise
    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ClientError("token 文件损坏，请重新 login") from exc
    if not isinstance(data, dict) or "access_token" not in data:
        raise ClientError("token 文件损坏，请重新 login")
    # 权限核验：宽于 0600 的 token 文件拒绝使用（机密纪律，fail-closed）
    try:
        mode = os.stat(TOKEN_PATH, follow_symlinks=False).st_mode & 0o777
    except OSError as exc:
        raise ClientError("token 状态不可读") from exc
    if mode != 0o600:
        raise ClientError(
            f"token 文件权限过宽（{oct(mode)}，要求 600）——请修复或重新 login")
    return data


def clear_token() -> None:
    try:
        TOKEN_PATH.unlink()
    except FileNotFoundError:
        pass


# ── HTTP 基元 ─────────────────────────────────────────────────────────

def _request(
    method: str,
    path: str,
    *,
    data: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> tuple[int, bytes]:
    url = server_url() + path
    body = None
    request_headers = {"Accept": "application/json"}
    if data is not None:
        body = urllib.parse.urlencode(data).encode("utf-8")
        request_headers["Content-Type"] = "application/x-www-form-urlencoded"
    if headers:
        request_headers.update(headers)
    req = urllib.request.Request(url, data=body, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise ConnectionError(f"服务器不可达: {server_url()} ({type(exc).__name__})") from exc


def _json_body(status: int, raw: bytes) -> dict[str, Any]:
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        data = {}
    return data if isinstance(data, dict) else {"raw": raw[:200].decode("utf-8", "replace")}


# ── OAuth2 设备授权流 ─────────────────────────────────────────────────

def device_authorize(client_id: str = "compile-excel-skill") -> dict[str, Any]:
    status, raw = _request("POST", "/device_authorize", data={
        "client_id": client_id,
        "scope": "artifacts:read docs:query",
    })
    payload = _json_body(status, raw)
    if status != 200 or "device_code" not in payload:
        raise ClientError(f"device_authorize 失败: HTTP {status} {payload}")
    return payload


def poll_device_token(
    device_code: str,
    *,
    interval: int,
    expires_in: int,
    on_pending=None,
) -> dict[str, Any]:
    """轮询 /token 直到授权完成或设备码过期。"""
    deadline = time.time() + max(expires_in - 1, 5)
    while time.time() < deadline:
        status, raw = _request("POST", "/token", data={
            "grant_type": DEVICE_GRANT,
            "device_code": device_code,
        })
        payload = _json_body(status, raw)
        if status == 200 and "access_token" in payload:
            return payload
        error = payload.get("error")
        if error == "authorization_pending":
            if on_pending:
                on_pending()
            time.sleep(max(interval, 1))
            continue
        if error == "slow_down":
            time.sleep(max(interval, 1) + 1)
            continue
        raise ClientError(f"device flow 失败: {error or f'HTTP {status}'}")
    raise ClientError("设备码已过期，请重新 login")


def refresh_access(refresh_token: str) -> dict[str, Any]:
    status, raw = _request("POST", "/token", data={
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    })
    payload = _json_body(status, raw)
    if status != 200 or "access_token" not in payload:
        raise ClientError(
            f"token 刷新失败（请重新 login）: {payload.get('error') or f'HTTP {status}'}")
    return payload


def authed_request(
    method: str,
    path: str,
    *,
    data: dict[str, str] | None = None,
    timeout: float = 60.0,
) -> tuple[dict[str, Any], bool]:
    """带 Bearer 的请求；401 时用 refresh_token 换新后重试一次。

    返回 (解析后的 JSON, refreshed_flag)。token 文件在刷新成功后原位更新。
    """
    token = load_token()
    if not token:
        raise ClientError("未登录（token 不存在），先运行 login.py")
    refreshed = False
    for attempt in (0, 1):
        headers = {"Authorization": f"Bearer {token['access_token']}"}
        status, raw = _request(method, path, data=data, headers=headers, timeout=timeout)
        if status != 401:
            return _json_body(status, raw), refreshed
        if attempt == 1 or not token.get("refresh_token"):
            raise ClientError("token 无效或已过期且无法刷新（HTTP 401），请重新 login")
        issued = refresh_access(token["refresh_token"])
        token = {
            "access_token": issued["access_token"],
            "refresh_token": issued.get("refresh_token", token.get("refresh_token")),
            "expires_at": int(time.time()) + int(issued.get("expires_in") or 900),
            "server": server_url(),
        }
        save_token(token)
        refreshed = True
    raise ClientError("unreachable")


# ── artifacts / docs ──────────────────────────────────────────────────

def fetch_manifest(device_build: str = "") -> dict[str, Any]:
    query = f"?device_build={urllib.parse.quote(device_build)}" if device_build else ""
    payload, _refreshed = authed_request("GET", "/v1/artifacts/manifest" + query)
    if "artifacts" not in payload:
        raise ClientError(f"manifest 异常: {json.dumps(payload, ensure_ascii=False)[:200]}")
    return payload


def docs_query(query: str, limit: int = 3) -> dict[str, Any]:
    payload, _refreshed = authed_request("POST", "/v1/docs/query", data={
        "q": query, "limit": str(limit)})
    if "results" not in payload:
        raise ClientError(f"docs/query 异常: {json.dumps(payload, ensure_ascii=False)[:200]}")
    return payload


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_artifact_verified(
    name: str,
    expected_sha256: str,
    dest_dir: Path,
    *,
    timeout: float = 120.0,
) -> Path:
    """鉴权下载 + 边下边算 SHA；不符即拒（temp 清理，绝不污染缓存）。"""
    token = load_token()
    if not token:
        raise ClientError("未登录（token 不存在），先运行 login.py")
    url = server_url() + "/v1/artifacts/" + urllib.parse.quote(name)
    req = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {token['access_token']}"})
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / name
    digest = hashlib.sha256()
    fd, tmp_name = tempfile.mkstemp(prefix=f".{name}.", suffix=".part", dir=str(dest_dir))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp, \
                os.fdopen(fd, "wb") as stream:
            if resp.status != 200:
                raise ClientError(f"下载 {name} 失败: HTTP {resp.status}")
            while True:
                chunk = resp.read(1 << 20)
                if not chunk:
                    break
                digest.update(chunk)
                stream.write(chunk)
        actual = digest.hexdigest()
        if actual != expected_sha256:
            raise ClientError(
                f"工件 {name} SHA256 校验失败：manifest={expected_sha256[:12]}… "
                f"下载={actual[:12]}…，已拒绝落盘")
        os.replace(tmp_name, dest)
        return dest
    except urllib.error.HTTPError as exc:
        raise ClientError(f"下载 {name} 失败: HTTP {exc.code}") from exc
    except (urllib.error.URLError, OSError) as exc:
        raise ConnectionError(f"下载 {name} 时服务器不可达 ({type(exc).__name__})") from exc
    finally:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass


def cached_manifest(device_build: str) -> dict[str, Any] | None:
    candidates: list[Path]
    if device_build:
        candidates = [CACHE_DIR / device_build / "manifest.json"]
    else:
        # 未指定 build：取缓存里最新的 manifest（按 mtime）
        candidates = sorted(
            CACHE_DIR.glob("*/manifest.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
    for path in candidates:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict) and "artifacts" in data:
            return data
    return None


def verify_cached_artifact(entry: dict[str, Any], device_build: str) -> Path:
    """缓存回退前的完整性核验：文件存在且 SHA 与缓存 manifest 一致。"""
    path = CACHE_DIR / device_build / entry["name"]
    if not path.is_file():
        raise ClientError(f"缓存缺失工件 {entry['name']}（缓存不完整，拒绝静默降级）")
    actual = _sha256_file(path)
    if actual != entry["sha256"]:
        raise ClientError(
            f"缓存工件 {entry['name']} SHA256 与缓存 manifest 不符，拒绝使用")
    return path
