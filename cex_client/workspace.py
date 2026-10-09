"""工作区：用户的项目文件夹。编译数据、令牌、产物都落在这里，是唯一的路径解析器。

布局：
  <文件夹>/.compile-excel/            0700，自带 .gitignore（整目录不入库）
      config.json                    服务端地址、device_build、通道、ca_sha256（连接串里的 CA 指纹）
      ca.pem                         核对过指纹的服务端内置 CA 证书（连接串带 #ca= 时才有）
      token.json                     OAuth 令牌（0600）；文件夹里唯一的凭据
      login_pending.json             设备流进行中的临时状态（0600）
      client_config.json             服务端下发的组织常量缓存
      bundle/<build>/manifest.json   已同步的数据包清单；条目按包内路径落在同目录下
  <文件夹>/compile_outputs/            编译产物（脑图、用例、xlsx）

找工作区：显式给的起点（工具参数 workspace）往上找 → 没给起点时用环境变量 CEX_WORKSPACE →
从当前目录往上找第一个含 .compile-excel/config.json 的目录。

状态文件里记的路径一律相对工作区根（to_state_path / from_state_path），文件夹改名、挪位置后照样能用；
旧版记下的绝对路径按其中的 .compile-excel / compile_outputs 段换算到当前工作区。
"""

from __future__ import annotations

import base64
import binascii
import fcntl
import hashlib
import ipaddress
import json
import os
import re
import ssl
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from .errors import ClientError

STATE_DIR = ".compile-excel"
OUTPUTS_DIR = "compile_outputs"
CONFIG_SCHEMA = "cex.workspace/v1"
_SAFE_COMPONENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_BAD_COMPONENT_CHARS = set('\\:*?"<>|')
DEFAULT_SERVER_PORT = 8900
CONNECTION_STRING_FORM = f"https://主机:{DEFAULT_SERVER_PORT}#ca=指纹"
NO_DEVICE_BUILD = "还没有选构建号：登录后会自动选；服务端有多个构建时，用 cex_init 的 device_build 指定"
# 同一份 CA（按指纹）只建一次 SSL 上下文：同步时每个 blob 一次请求
_SSL_CONTEXTS: dict[str, ssl.SSLContext] = {}


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


def is_loopback_host(host: str | None) -> bool:
    host = (host or "").strip("[]")
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def check_server_url(url: str, *, allow_insecure_http: bool, what: str = "服务端") -> str:
    """服务端（或网关）地址：https 放行；http 只放行回环地址，或工作区显式允许了局域网明文。"""
    url = (url or "").strip().rstrip("/")
    parts = urlsplit(url)
    fix = (f"最好直接用管理员给的连接串（形如 {CONNECTION_STRING_FORM}）" if what == "服务端"
           else "网关地址由服务端下发，请管理员核对 gateway.url")
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ClientError(f"{what}地址不对（{url!r}）：要写成 https://主机:端口；{fix}")
    try:
        port = parts.port
    except ValueError:
        port = -1
    if port is not None and not 0 < port < 65536:
        raise ClientError(f"{what}地址里的端口不对（{url!r}）：端口是 1–65535 的数字；{fix}")
    if parts.username or parts.password:
        raise ClientError(f"{what}地址里不能带用户名或口令（{parts.hostname}）：去掉 @ 及前面的部分")
    if parts.scheme == "http" and not allow_insecure_http and not is_loopback_host(parts.hostname):
        raise ClientError(
            f"明文 http 连非本机的{what}（{parts.hostname}）会把登录令牌明文发到网络上：请改用 https，{fix}。"
            f"确认是可信实验网、{what}确实只开了明文时，才在 cex_init 里加 insecure_lan=true 放行")
    return url


_DEFAULT_PORTS = {"https": 443, "http": 80}


def normalize_server_url(url: str) -> str:
    """同一个服务端的不同写法统一成一种（判断"是不是同一个服务端"、写进配置都用它）：协议与主机名
    小写，https 去掉 :443、http 去掉 :80，IPv6 用 urlsplit 解出的地址（再写成最短形式）加方括号，
    去掉末尾的 /。解析不了的原样返回（由 check_server_url 报错）。"""
    text = (url or "").strip().rstrip("/")
    try:
        parts = urlsplit(text)
        port = parts.port
    except ValueError:
        return text
    scheme, host = parts.scheme.lower(), parts.hostname
    if scheme not in _DEFAULT_PORTS or not host:
        return text
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and address.version == 6:
        host = f"[{address.compressed}]"
    if port is not None and port != _DEFAULT_PORTS[scheme]:
        host += f":{port}"
    return urlunsplit((scheme, host, parts.path.rstrip("/"), parts.query, ""))


def same_server(a: Any, b: Any) -> bool:
    """两个地址是不是同一个服务端（按规范化后的写法比较；空的不算）。"""
    left, right = str(a or "").strip(), str(b or "").strip()
    return bool(left and right) and normalize_server_url(left) == normalize_server_url(right)


_PEM_BEGIN = "-----BEGIN CERTIFICATE-----"
_PEM_END = "-----END CERTIFICATE-----"


def _whole_der_sequence(der: bytes) -> bool:
    """DER 是一个完整的 SEQUENCE，长度正好到末尾（后面不许再拖别的字节）。"""
    if len(der) < 2 or der[0] != 0x30:
        return False
    if der[1] < 0x80:
        return 2 + der[1] == len(der)
    count = der[1] & 0x7F
    if not 1 <= count <= 4 or len(der) < 2 + count:
        return False
    return 2 + count + int.from_bytes(der[2:2 + count], "big") == len(der)


def pem_to_der(pem: str) -> bytes:
    """严格解析恰好一张证书的 PEM，返回 DER。ssl.PEM_cert_to_DER_cert 解码宽松：拼接的第二张、
    夹在中间的非法字符都会被悄悄吞掉，按它算指纹可被绕过。这里只认：首尾只有空白、恰好一个
    BEGIN/END CERTIFICATE 块、块内只有 base64 字符与换行（严格解码）、解出来是一个完整的 DER 序列。
    不合要求抛 ValueError。"""
    text = pem.strip()
    if not (text.startswith(_PEM_BEGIN) and text.endswith(_PEM_END)) or text.count("-----") != 4:
        raise ValueError("not exactly one PEM certificate block")
    body = re.sub(r"[\r\n]+", "", text[len(_PEM_BEGIN):-len(_PEM_END)])
    try:
        der = base64.b64decode(body, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError("the PEM body is not strict base64") from None
    if not _whole_der_sequence(der):
        raise ValueError("the PEM body is not one DER certificate")
    return der


def ca_fingerprint(pem: str) -> str:
    """CA 证书 DER 编码的 SHA-256（64 位小写十六进制），与连接串里 #ca= 后面的指纹同一算法。
    按 pem_to_der 严格解析；不是恰好一张 PEM 证书时抛 ValueError。"""
    return hashlib.sha256(pem_to_der(pem)).hexdigest()


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
    def lease_path(self) -> Path:
        return self.state_dir / "lease.json"

    @property
    def ca_path(self) -> Path:
        return self.state_dir / "ca.pem"

    @property
    def outputs_dir(self) -> Path:
        return self.root / OUTPUTS_DIR

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
        return normalize_server_url(check_server_url(
            str(cfg.get("server") or ""), allow_insecure_http=bool(cfg.get("allow_insecure_http"))))

    @property
    def device_build(self) -> str:
        build = self.config().get("device_build")
        if not build:
            raise ClientError(NO_DEVICE_BUILD)
        return safe_component(build, "device_build")

    @property
    def selected_build(self) -> str:
        """已选的构建号；还没选时是空串（不抛错，给 cex_status 这类只报告状态的地方用）。"""
        return str(self.config().get("device_build") or "")

    def ssl_context(self) -> ssl.SSLContext | None:
        """发往服务端、网关的 https 用哪个校验上下文：连接串带了 CA 指纹时是"系统证书库 + 工作区
        ca.pem"（每次按配置里的指纹核对 ca.pem）；没带指纹返回 None，只用系统证书库（或 SSL_CERT_FILE）。
        ca.pem 按 pem_to_der 严格解析，只信任解出的那一张（文件被追加了别的证书就整份拒绝）。"""
        expected = str(self.config().get("ca_sha256") or "")
        if not expected:
            return None
        broken = ("工作区里的 CA 证书（.compile-excel/ca.pem）{}：请用管理员给的连接串"
                  f"（形如 {CONNECTION_STRING_FORM}）重新执行 cex_init")
        if self.ca_path.is_symlink() or not self.ca_path.is_file():
            raise ClientError(broken.format("不见了"))
        try:
            der = pem_to_der(self.ca_path.read_text(encoding="ascii"))
        except (OSError, UnicodeError, ValueError):
            raise ClientError(broken.format("读不出来，或不是恰好一张证书")) from None
        if hashlib.sha256(der).hexdigest() != expected:
            raise ClientError(broken.format("与配置里记的指纹不一致，可能被改动过"))
        context = _SSL_CONTEXTS.get(expected)
        if context is None:
            context = ssl.create_default_context()
            try:
                context.load_verify_locations(cadata=der)
            except ssl.SSLError:
                raise ClientError(broken.format("读不出来，或不是恰好一张证书")) from None
            _SSL_CONTEXTS[expected] = context
        return context

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


def write_file_safely(root: Path, path: Path, data: bytes, *, mode: int = 0o644) -> None:
    """在 root 之下原子写一个文件：路径上任何一级（含目标本身）是符号链接、或落到 root 之外
    就拒绝；先写同目录的随机临时文件（O_EXCL，不跟随预先放好的链接）再改名。
    回执、cases.json、缺陷单、脑图快照这类落在用户文件夹里的产物都走这里。"""
    root, path = Path(root), Path(path)
    try:
        rel = path.relative_to(root)
    except ValueError:
        raise ClientError(f"{path} is outside {root}; refusing to write") from None
    if not rel.parts or any(part in ("", ".", "..") for part in rel.parts):
        raise ClientError(f"{path} is not a file path under {root}")
    current = root
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise ClientError(f"{current} is a symlink; refusing to write through it")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


@contextmanager
def state_lock(ws: Workspace, kind: str, key: str = "", *, shared: bool = False) -> Iterator[None]:
    """工作区内跨进程的互斥（fcntl.flock，随文件描述符释放）。每个工具调用可能是独立进程，
    同时跑的调用对同一份状态做"读—改—写"时先拿锁；锁文件在 .compile-excel/locks/ 下。"""
    name = safe_component(kind, "lock kind")
    if key:
        name += "." + hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
    directory = ws.state_dir / "locks"
    directory.mkdir(parents=True, exist_ok=True)
    fd = os.open(directory / f"{name}.lock",
                 os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_SH if shared else fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def to_state_path(ws: Workspace, path: Path | str) -> str:
    """状态文件里记路径：工作区内的一律记相对工作区根的 posix 路径。"""
    path = Path(path)
    try:
        return path.relative_to(ws.root).as_posix()
    except ValueError:
        pass
    try:
        return path.resolve().relative_to(ws.root.resolve()).as_posix()
    except (OSError, ValueError):
        return str(path)


def from_state_path(ws: Workspace, value: Any) -> Path:
    """状态文件里的路径 → 当前工作区里的路径。相对路径接在工作区根下；旧版记的绝对路径
    （文件夹改名、挪位置后已失效）按最后一个 .compile-excel / compile_outputs 段换算过来，
    不去读别的文件夹里的同名文件。"""
    text = str(value or "")
    if not text:
        raise ClientError("the workspace state records an empty path")
    path = Path(text)
    if not path.is_absolute():
        return ws.root / path
    root = ws.root.resolve()
    if path == ws.root or ws.root in path.parents or root in path.parents:
        return path
    parts = path.parts
    for index in range(len(parts) - 1, 0, -1):
        if parts[index] in (STATE_DIR, OUTPUTS_DIR):
            return ws.root.joinpath(*parts[index:])
    return path


def find(start: Path | None = None) -> Workspace | None:
    """显式起点优先（工具参数里的 workspace 不被环境变量盖掉）；没给起点才看 CEX_WORKSPACE。"""
    if start is None:
        explicit = os.environ.get("CEX_WORKSPACE")
        if explicit:
            root = Path(explicit).expanduser().resolve()
            return Workspace(root) if (root / STATE_DIR / "config.json").is_file() else None
    here = (start or Path.cwd()).expanduser().resolve()
    for candidate in (here, *here.parents):
        if (candidate / STATE_DIR / "config.json").is_file():
            return Workspace(candidate)
    return None


def require(start: Path | None = None) -> Workspace:
    ws = find(start)
    if ws is None:
        raise ClientError("这里还没有 compile-excel 工作区：先在项目文件夹里执行 cex_init"
                          f"（server 用管理员给的连接串，形如 {CONNECTION_STRING_FORM}）")
    return ws


def init(root: Path, *, server: str, device_build: str = "", channel: str = "stable",
         insecure_lan: bool = False, ca_sha256: str = "", ca_pem: str = "") -> Workspace:
    """写工作区配置（不联网；探活与核对 CA 在 connect.setup 里做完才调这里）。
    ca_sha256/ca_pem 是核对过的内置 CA；不给就删掉旧的 ca.pem，只用系统证书库。
    地址按 normalize_server_url 规范化后保存，"是不是同一个服务端"也按规范化的写法判断。"""
    root = Path(root).expanduser().resolve()
    server = normalize_server_url(check_server_url(server, allow_insecure_http=insecure_lan))
    if device_build:
        safe_component(device_build, "device_build")
    if ca_sha256 and ca_fingerprint(ca_pem) != ca_sha256:
        raise ClientError("CA 证书与指纹对不上，拒绝保存：请用管理员给的连接串重新执行 cex_init")
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
    if previous and (not same_server(previous.get("server"), server)
                     or str(previous.get("ca_sha256") or "") != ca_sha256):
        # 换服务端（或换了信任的 CA）：令牌、服务端下发的组织常量（网关地址等）、租约、
        # 进行中的登录都属于旧的那个，丢掉
        for stale in (ws.token_path, ws.client_config_path, ws.lease_path, ws.pending_login_path):
            stale.unlink(missing_ok=True)
    if ca_sha256:
        write_file_safely(ws.root, ws.ca_path, ca_pem.encode("ascii"), mode=0o644)
    else:
        ws.ca_path.unlink(missing_ok=True)
    ws.save_config({"server": server, "device_build": device_build, "channel": channel,
                    "allow_insecure_http": bool(insecure_lan), "ca_sha256": ca_sha256})
    return ws
