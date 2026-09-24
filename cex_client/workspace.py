"""工作区：用户的项目文件夹。编译数据、令牌、产物都落在这里，是唯一的路径解析器。

布局：
  <文件夹>/.compile-excel/            0700，自带 .gitignore（整目录不入库）
      config.json                    服务端地址、device_build、通道
      token.json                     OAuth 令牌（0600）；文件夹里唯一的凭据
      login_pending.json             设备流进行中的临时状态（0600）
      client_config.json             服务端下发的组织常量缓存
      bundle/<build>/manifest.json   已同步的数据包清单；条目按包内路径落在同目录下
  <文件夹>/compile_outputs/            编译产物（脑图、用例、xlsx）

找工作区：环境变量 CEX_WORKSPACE → 从当前目录往上找第一个含 .compile-excel/config.json 的目录。
"""

from __future__ import annotations

import ipaddress
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .errors import ClientError

STATE_DIR = ".compile-excel"
CONFIG_SCHEMA = "cex.workspace/v1"
_SAFE_COMPONENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_BAD_COMPONENT_CHARS = set('\\:*?"<>|')


def safe_component(value: Any, what: str) -> str:
    """服务端给的单段名字（构建名等）要拼进本地路径：只收安全文件名。"""
    text = str(value or "")
    if not _SAFE_COMPONENT_RE.fullmatch(text) or ".." in text:
        raise ClientError(f"{what} is not a safe path component: {text!r}")
    return text


def safe_relative_path(value: Any) -> str:
    """数据包条目路径：相对 posix 路径，每段不能是 . / ..、不能以点开头、不含控制字符和保留字符。
    与服务端 registry.check_entry_path 同一套规则，客户端再查一遍，不信任服务端。"""
    text = str(value or "")
    if not text or text.startswith("/") or len(text.encode("utf-8")) > 1024:
        raise ClientError(f"bundle entry path is invalid: {text!r}")
    for part in text.split("/"):
        if (not part or part in (".", "..") or part.startswith(".")
                or any(ord(ch) < 32 or ch in _BAD_COMPONENT_CHARS for ch in part)):
            raise ClientError(f"bundle entry path is invalid: {text!r}")
    return text


def check_server_url(url: str, *, allow_insecure_http: bool) -> str:
    """服务端地址：https 放行；http 只放行回环地址，或工作区显式允许了局域网明文。"""
    url = (url or "").strip().rstrip("/")
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ClientError(f"server must be an http(s) URL: {url!r}")
    if parts.username or parts.password:
        raise ClientError("server URL must not carry credentials")
    if parts.scheme == "http" and not allow_insecure_http:
        host = parts.hostname
        loopback = host == "localhost"
        try:
            loopback = loopback or ipaddress.ip_address(host).is_loopback
        except ValueError:
            pass
        if not loopback:
            raise ClientError(
                "plain http to a non-loopback server sends the token in clear text; use https, "
                "or re-run cex_init with insecure_lan=true if this is a trusted lab network")
    return url


@dataclass
class Workspace:
    root: Path

    @property
    def state_dir(self) -> Path:
        return self.root / STATE_DIR

    @property
    def config_path(self) -> Path:
        return self.state_dir / "config.json"

    @property
    def token_path(self) -> Path:
        return self.state_dir / "token.json"

    @property
    def pending_login_path(self) -> Path:
        return self.state_dir / "login_pending.json"

    @property
    def client_config_path(self) -> Path:
        return self.state_dir / "client_config.json"

    @property
    def outputs_dir(self) -> Path:
        return self.root / "compile_outputs"

    def config(self) -> dict[str, Any]:
        try:
            data = json.loads(self.config_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ClientError(f"workspace config unreadable: {exc}") from None
        if not isinstance(data, dict) or data.get("schema") != CONFIG_SCHEMA:
            raise ClientError("workspace config has an unknown schema; re-run cex_init")
        return data

    def save_config(self, data: dict[str, Any]) -> None:
        write_private_json(self.config_path, {**data, "schema": CONFIG_SCHEMA})

    @property
    def server(self) -> str:
        cfg = self.config()
        return check_server_url(str(cfg.get("server") or ""),
                                allow_insecure_http=bool(cfg.get("allow_insecure_http")))

    @property
    def device_build(self) -> str:
        return safe_component(self.config().get("device_build"), "device_build")

    @property
    def channel(self) -> str:
        channel = str(self.config().get("channel") or "stable")
        if channel not in ("stable", "candidate"):
            raise ClientError(f"unknown channel {channel!r}")
        return channel

    def bundle_dir(self, build: str | None = None) -> Path:
        return self.state_dir / "bundle" / safe_component(build or self.device_build,
                                                          "device_build")


def write_private_json(path: Path, data: dict[str, Any]) -> None:
    """0600 原子写：先写同目录临时文件再改名，不跟随符号链接。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ClientError(f"{path.name} is a symlink; refusing to write")
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0),
                 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=1, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def read_private_json(path: Path) -> dict[str, Any] | None:
    """读 0600 文件；权限宽于 0600 或是符号链接就拒绝，不存在返回 None。"""
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return None
    if not os.path.isfile(path) or os.path.islink(path):
        raise ClientError(f"{path.name} is not a regular file")
    if os.name != "nt" and info.st_mode & 0o077:
        raise ClientError(f"{path.name} permissions are wider than 0600; fix them or log in again")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        raise ClientError(f"{path.name} is corrupted; log in again") from None
    return data if isinstance(data, dict) else None


def find(start: Path | None = None) -> Workspace | None:
    explicit = os.environ.get("CEX_WORKSPACE")
    if explicit:
        root = Path(explicit).expanduser().resolve()
        return Workspace(root) if (root / STATE_DIR / "config.json").is_file() else None
    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        if (candidate / STATE_DIR / "config.json").is_file():
            return Workspace(candidate)
    return None


def require(start: Path | None = None) -> Workspace:
    ws = find(start)
    if ws is None:
        raise ClientError("no compile-excel workspace here; run cex_init in the project folder first")
    return ws


def init(root: Path, *, server: str, device_build: str, channel: str = "stable",
         insecure_lan: bool = False) -> Workspace:
    root = Path(root).expanduser().resolve()
    check_server_url(server, allow_insecure_http=insecure_lan)
    safe_component(device_build, "device_build")
    ws = Workspace(root)
    ws.state_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(ws.state_dir, 0o700)
    ignore = ws.state_dir / ".gitignore"
    if not ignore.exists():
        ignore.write_text("# compile-excel 工作区状态：含令牌，整目录不入库\n*\n", encoding="utf-8")
    previous = {}
    if ws.config_path.is_file():
        try:
            previous = ws.config()
        except ClientError:
            previous = {}
    if previous and previous.get("server") != server.rstrip("/") and ws.token_path.exists():
        # 换服务端：旧令牌属于旧服务端，丢掉
        ws.token_path.unlink()
    ws.save_config({"server": server.rstrip("/"), "device_build": device_build,
                    "channel": channel, "allow_insecure_http": bool(insecure_lan)})
    return ws
