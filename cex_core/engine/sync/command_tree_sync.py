# 生成：tools/extract_engine.py ← InfoTest main/sync/command_tree_sync.py（sha256 dd5c5fb6c6f38938）。不在这里手改。
from __future__ import annotations
from cex_core.engine._root import _cex_data_path
import contextlib
import errno
import fcntl
import hashlib
import http.client
import ipaddress
import json
import logging
import os
import posixpath
import re
import secrets
import socket
import ssl
import stat
import threading
import time
import urllib.parse
import xml.etree.ElementTree as ET
import xml.parsers.expat as expat
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable, Iterable, Mapping
from cex_core.engine.case_compiler._sealed_io import atomic_write_bytes_nofollow, open_directory_nofollow, read_regular_nofollow
from cex_core.engine.common.schema_identity import accepts_schema
_ROOT = _cex_data_path('')
logger = logging.getLogger(__name__)
COMMAND_TREE_STORE_ROOT = _ROOT / 'runtime' / 'command_tree'
ACTIVE_SCHEMA = 'ist.command-tree.active'
MANIFEST_SCHEMA = 'ist.command-tree.generation'
PROJECTION_POLICY_SCHEMA = 'ist.vendor-stdlib.projection-policy'
_PROJECTION_POLICY_RULES = {'declaration_claim_fields': 'forbidden-v1', 'field_contract': 'closed-v2', 'source_xml_identity': 'sha256-bound-v1', 'sensitive_parameter_marker': 'redacted-unexecutable-v3', 'xml_default_literals': 'absent-from-xml-derived-surfaces-v2', 'argument_value_domain': 'multi-source-claims-v14'}
_XML_DERIVED_DOMAIN_SOURCES = frozenset({'xml_limit', 'xml_help'})
DEFAULT_INDEX_MAX_BYTES = 2 * 1024 * 1024
DEFAULT_XML_MAX_BYTES = 16 * 1024 * 1024
DEFAULT_PROJECTION_MAX_BYTES = 16 * 1024 * 1024
DEFAULT_MANIFEST_MAX_BYTES = 256 * 1024
DEFAULT_MAX_PAGES = 32
DEFAULT_MAX_LINKS = 4096
DEFAULT_URL_MAX_CHARS = 2048
DEFAULT_HREF_MAX_CHARS = 2048
_GENERATION_RE = re.compile('^g-[0-9a-f]{24}-[0-9a-f]{24}$')
_VERSION_RE = re.compile('^\\d+(?:\\.\\d+){1,2}$')
_BUILD_RE = re.compile('^\\d+$')
_PRODUCT_RE = re.compile('^[A-Za-z0-9]+$')
_PLATFORM_RE = re.compile('^[A-Za-z0-9_-]+$')
_SHA256_RE = re.compile('^[0-9a-f]{64}$')
_FULL_VERSION_RE = re.compile('^(?P<os>[A-Za-z][A-Za-z0-9_-]*)\\s+(?P<channel>[A-Za-z0-9_-]+)\\.(?P<product>[A-Za-z0-9]+)-(?P<platform>[A-Za-z0-9_-]+)\\.(?P<release>\\d+\\.\\d+(?:\\.\\d+)+)\\.(?P<build>\\d+)$')
_STORE_BOOTSTRAP_LOCK = threading.Lock()
_METADATA_ADDRESSES = frozenset({ipaddress.ip_address('169.254.169.254'), ipaddress.ip_address('169.254.170.2'), ipaddress.ip_address('100.100.100.200'), ipaddress.ip_address('192.0.0.192'), ipaddress.ip_address('fd00:ec2::254')})

class CommandTreeSyncError(RuntimeError):
    pass

class CommandTreeProjectionPolicyStale(CommandTreeSyncError):
    pass

@dataclass(frozen=True)
class BuildIdentity:
    full_version: str
    os_name: str
    channel: str
    product: str
    platform: str
    release: str
    build: str

    @property
    def inventory_version(self) -> str:
        parts = self.release.split('.')
        return '.'.join(parts[:2])

    @property
    def filename_tokens(self) -> tuple[str, ...]:
        return tuple(re.findall('[a-z0-9]+', self.full_version.casefold()))

@dataclass(frozen=True)
class CommandTreeSyncResult:
    product: str
    platform: str
    version: str
    device_build: str
    full_version: str
    generation_id: str
    generation_root: Path
    xml_path: Path
    projection_path: Path
    manifest_path: Path
    manifest_sha256: str
    source_url: str
    source_sha256: str
    source_size: int
    projection_sha256: str
    results_total: int
    results_nonempty: int
    item_count: int
    published: bool
HttpFetcher = Callable[[str, int], bytes]
ProjectionBuilder = Callable[..., dict]

class _HrefParser(HTMLParser):

    def __init__(self, *, max_href_chars: int=DEFAULT_HREF_MAX_CHARS) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []
        self.max_href_chars = max_href_chars
        self.oversized_href = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != 'a':
            return
        for key, value in attrs:
            if key.casefold() == 'href' and value is not None:
                if len(value) > self.max_href_chars:
                    self.oversized_href = True
                else:
                    self.hrefs.append(value)

def parse_build_identity(full_version: str) -> BuildIdentity:
    value = str(full_version or '').strip()
    match = _FULL_VERSION_RE.fullmatch(value)
    if match is None:
        raise CommandTreeSyncError('设备完整版本身份无法解析')
    return BuildIdentity(full_version=value, os_name=match.group('os'), channel=match.group('channel'), product=match.group('product'), platform=match.group('platform'), release=match.group('release'), build=match.group('build'))

def parse_build_identity_from_text(text: str) -> BuildIdentity:
    """从整行或横幅中解析唯一完整设备身份。

    先整串精确匹配；失败则在文本里找完整身份正则的唯一命中。
    0 次或超过 1 次命中都失败关闭，避免从杂质里猜错身份。
    """
    value = str(text or '').strip()
    try:
        return parse_build_identity(value)
    except CommandTreeSyncError:
        pass
    search = re.compile(_FULL_VERSION_RE.pattern.lstrip('^').rstrip('$'))
    matches = list(search.finditer(value))
    if len(matches) != 1:
        raise CommandTreeSyncError('设备完整版本身份无法解析')
    return parse_build_identity(matches[0].group(0))

def inventory_version_from_build(full_version: str) -> str:
    return parse_build_identity(full_version).inventory_version
_VERSION_EXPECTATION_RE = re.compile('^\\d+(?:\\.\\d+){1,3}$')

def resolve_family_key(version: str, full_version: str) -> str:
    """版本轴**期望** → 密封仓族键（内部工单，2026-09-22）。

    病根：批入口把用户填的 product_version 原话直接当仓键用（10.5.0 → 查
    `10.5.0_633` 分区），而写侧协议从第一天起就把键钉成族两段
    （inventory_version，10.5.0.633 → `10.5_633`）。同一份输入，sync 那道门
    把它当"期望"做前缀核对（放行），收敛验收那道门把它当"地址"寻路（查无
    此地）——两把尺子，期望与设备明明一致也被拦死，报错还把人引向
    "构建站缺产物/网络不通"的假方向。

    本函数把两个职责一次钉死：**期望只做逐段核对，寻址只由设备事实生成**。
    - 空串 = 无期望，跟随实机自述（保留 内部工单 推导路，不许回归）；
    - 2~4 段点分形态（10.5 / 10.5.0 / 10.5.0.633）= 期望前缀，与设备事实
      ``release + [build]`` 逐段严格比对，任一段对不上就 fail-closed，
      错误消息同时带期望与实机两个完整值；
    - 核对通过后返回的仓键**永远**由设备事实推导——用户输入触碰不到寻址。
    """
    identity = parse_build_identity(full_version)
    want = str(version or '').strip()
    if not want:
        return identity.inventory_version
    if not _VERSION_EXPECTATION_RE.fullmatch(want):
        raise CommandTreeSyncError(f'版本轴 {want!r} 不是合法版本形态（应为点分数字，如 10.5 / 10.5.0 / 10.5.0.633）；实机自述 {identity.full_version}')
    facts = identity.release.split('.') + [identity.build]
    expected = want.split('.')
    for index, segment in enumerate(expected):
        actual = facts[index] if index < len(facts) else '缺席'
        if actual != segment:
            depth = ('族', '版本段', '修订段', '固件号')[min(index, 3)]
            raise CommandTreeSyncError(f'版本轴 {want} 与实机 {identity.full_version} 不一致：第 {index + 1} 段（{depth}）期望 {segment}，实机 {actual}')
    return identity.inventory_version

def _canonical_json(payload: dict) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8')

def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()

def projection_policy_identity() -> dict:
    signed = {'schema': PROJECTION_POLICY_SCHEMA, 'rules': dict(_PROJECTION_POLICY_RULES)}
    return {**signed, 'policy_sha256': _sha(_canonical_json(signed))}

def _has_forbidden_url_char(value: str) -> bool:
    return any((ord(ch) < 32 or ord(ch) == 127 or ch.isspace() for ch in value))

def _authority(parsed: urllib.parse.SplitResult) -> str:
    host = (parsed.hostname or '').casefold()
    if not host:
        return ''
    try:
        host.encode('ascii')
    except UnicodeEncodeError as exc:
        raise CommandTreeSyncError('构建站 URL host 必须是 ASCII') from exc
    if len(host) > 253:
        raise CommandTreeSyncError('构建站 URL host 长度超限')
    try:
        port = parsed.port
    except ValueError as exc:
        raise CommandTreeSyncError('构建站 URL 端口无效') from exc
    default = 443 if parsed.scheme.casefold() == 'https' else 80
    rendered_host = f'[{host}]' if ':' in host else host
    return rendered_host if port in (None, default) else f'{rendered_host}:{port}'

def _validate_base_url(index_url: str, *, allowed_authorities: Iterable[str], allow_insecure_http: bool) -> tuple[str, str, str]:
    original = str(index_url or '')
    raw = original.strip()
    if len(raw) > DEFAULT_URL_MAX_CHARS or raw != original or _has_forbidden_url_char(raw):
        raise CommandTreeSyncError('构建站索引 URL 含空白或控制字符')
    try:
        parsed = urllib.parse.urlsplit(raw)
    except ValueError as exc:
        raise CommandTreeSyncError('构建站索引 URL 无效') from exc
    scheme = parsed.scheme.casefold()
    if scheme not in {'https', 'http'}:
        raise CommandTreeSyncError('构建站索引只允许 http/https')
    if scheme == 'http' and (not allow_insecure_http):
        raise CommandTreeSyncError('构建站 HTTP 需要显式受控内网风险开关')
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise CommandTreeSyncError('构建站索引 URL 不允许凭据、query 或 fragment')
    if '%' in parsed.path:
        raise CommandTreeSyncError('构建站索引 path 不允许多层编码')
    authority = _authority(parsed)
    allow = {str(item or '').strip().casefold() for item in allowed_authorities}
    if not authority or authority not in allow:
        raise CommandTreeSyncError('构建站 authority 未在显式 allowlist')
    if '\\' in parsed.path or not parsed.path.startswith('/'):
        raise CommandTreeSyncError('构建站索引 path 无效')
    decoded = urllib.parse.unquote(parsed.path)
    decoded_twice = urllib.parse.unquote(decoded)
    if '\\' in decoded or '..' in decoded.split('/') or '..' in decoded_twice.split('/') or ('%00' in parsed.path.casefold()):
        raise CommandTreeSyncError('构建站索引 path 含不安全编码')
    normalized_path = posixpath.normpath(decoded)
    if not normalized_path.endswith('.html'):
        raise CommandTreeSyncError('构建站索引必须是 html 页面')
    prefix = posixpath.dirname(normalized_path).rstrip('/') + '/'
    canonical = urllib.parse.urlunsplit((scheme, parsed.netloc.casefold(), normalized_path, '', ''))
    return (canonical, authority, prefix)

def _validated_link(base_url: str, href: str, *, authority: str, path_prefix: str) -> str | None:
    original = str(href or '')
    raw = original.strip()
    if len(raw) > DEFAULT_HREF_MAX_CHARS or raw != original or _has_forbidden_url_char(raw):
        return None
    if not raw or raw.startswith('//') or '\\' in raw:
        return None
    try:
        joined = urllib.parse.urljoin(base_url, raw)
        if len(joined) > DEFAULT_URL_MAX_CHARS or _has_forbidden_url_char(joined):
            return None
        parsed = urllib.parse.urlsplit(joined)
    except ValueError:
        return None
    base_scheme = urllib.parse.urlsplit(base_url).scheme.casefold()
    if parsed.scheme.casefold() not in {'http', 'https'} or parsed.scheme.casefold() != base_scheme:
        return None
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        return None
    if '%' in parsed.path:
        return None
    try:
        if _authority(parsed) != authority:
            return None
    except CommandTreeSyncError:
        return None
    decoded = urllib.parse.unquote(parsed.path)
    decoded_twice = urllib.parse.unquote(decoded)
    if '\\' in decoded or '..' in decoded.split('/') or '..' in decoded_twice.split('/'):
        return None
    normalized = posixpath.normpath(decoded)
    if not normalized.startswith(path_prefix):
        return None
    return urllib.parse.urlunsplit((parsed.scheme.casefold(), parsed.netloc.casefold(), normalized, '', ''))

def _validated_manifest_source_url(source_url: str) -> str:
    original = str(source_url or '')
    raw = original.strip()
    if len(raw) > DEFAULT_URL_MAX_CHARS or raw != original or _has_forbidden_url_char(raw):
        raise CommandTreeSyncError('命令树 manifest source_url 含空白或控制字符')
    try:
        parsed = urllib.parse.urlsplit(raw)
    except ValueError as exc:
        raise CommandTreeSyncError('命令树 manifest source_url 无效') from exc
    scheme = parsed.scheme.casefold()
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise CommandTreeSyncError('命令树 manifest source_url 含凭据、query 或 fragment')
    if '%' in parsed.path or '\\' in parsed.path or (not parsed.path.startswith('/')):
        raise CommandTreeSyncError('命令树 manifest source_url path 无效')
    normalized = posixpath.normpath(parsed.path)
    basename = posixpath.basename(normalized)
    if normalized != parsed.path or not basename:
        raise CommandTreeSyncError('命令树 manifest source_url 身份无效')
    if scheme == 'local':
        if parsed.netloc != 'workspace-input' or not basename.casefold().endswith('.xml') or Path(basename).name != basename:
            raise CommandTreeSyncError('命令树本地来源标识无效')
        return urllib.parse.urlunsplit((scheme, parsed.netloc, normalized, '', ''))
    if not _target_filename_tokens(basename):
        raise CommandTreeSyncError('命令树 manifest source_url 身份无效')
    if scheme not in {'http', 'https'}:
        raise CommandTreeSyncError('命令树 manifest source_url scheme 无效')
    authority = _authority(parsed)
    if not authority:
        raise CommandTreeSyncError('命令树 manifest source_url 身份无效')
    return urllib.parse.urlunsplit((scheme, parsed.netloc.casefold(), normalized, '', ''))

def _normalize_allowed_ip_networks(values: Iterable[str]) -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for value in values:
        original = str(value or '')
        raw = original.strip()
        if raw != original or not raw or len(raw) > 64 or any((ch.isspace() for ch in raw)):
            raise CommandTreeSyncError('构建站 IP network allowlist 条目无效')
        try:
            network = ipaddress.ip_network(raw, strict=True)
        except ValueError as exc:
            raise CommandTreeSyncError('构建站 IP network allowlist 条目无效') from exc
        networks.append(network)
    if not networks:
        raise CommandTreeSyncError('构建站 IP network allowlist 为空')
    return tuple(networks)

def _forbidden_remote_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return bool(address.is_loopback or address.is_link_local or address.is_unspecified or address.is_multicast or (isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None) or (address in _METADATA_ADDRESSES))

def _resolve_allowed_addresses(host: str, port: int, *, allowed_networks: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]) -> tuple[tuple[int, tuple, ipaddress.IPv4Address | ipaddress.IPv6Address], ...]:
    try:
        answers = socket.getaddrinfo(host, port, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise CommandTreeSyncError('构建站 DNS 解析失败') from exc
    candidates: dict[tuple[int, str, int], tuple[int, tuple, ipaddress.IPv4Address | ipaddress.IPv6Address]] = {}
    disallowed = False
    for family, socktype, proto, _canonname, sockaddr in answers:
        if socktype != socket.SOCK_STREAM or proto not in {0, socket.IPPROTO_TCP}:
            continue
        try:
            address = ipaddress.ip_address(sockaddr[0])
        except (ValueError, IndexError, TypeError) as exc:
            raise CommandTreeSyncError('构建站 DNS 返回地址无效') from exc
        if _forbidden_remote_address(address):
            raise CommandTreeSyncError('构建站 DNS 解析到禁止地址')
        allowed = any((address.version == network.version and address in network for network in allowed_networks))
        if not allowed:
            disallowed = True
            continue
        scope_id = int(sockaddr[3]) if family == socket.AF_INET6 else 0
        candidates[family, str(address), scope_id] = (family, sockaddr, address)
    if disallowed:
        raise CommandTreeSyncError('构建站 DNS 含混合不允许解析地址')
    if not candidates:
        raise CommandTreeSyncError('构建站 DNS 没有 allowlist 内地址')
    return tuple((candidates[key] for key in sorted(candidates)))

def _open_direct_socket(candidates: tuple[tuple[int, tuple, ipaddress.IPv4Address | ipaddress.IPv6Address], ...], *, timeout: float) -> socket.socket:
    last_error: OSError | None = None
    for family, sockaddr, expected_address in candidates:
        connection = socket.socket(family, socket.SOCK_STREAM, socket.IPPROTO_TCP)
        try:
            connection.settimeout(timeout)
            connection.connect(sockaddr)
            peer = ipaddress.ip_address(connection.getpeername()[0])
            if peer != expected_address:
                raise CommandTreeSyncError('构建站实际 peer 与封口地址不一致')
            return connection
        except CommandTreeSyncError:
            connection.close()
            raise
        except OSError as exc:
            last_error = exc
            connection.close()
    raise CommandTreeSyncError('构建站直连失败') from last_error

def _default_fetch(url: str, max_bytes: int, *, allowed_networks: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]) -> bytes:
    original_url = str(url or '')
    if len(original_url) > DEFAULT_URL_MAX_CHARS or not original_url or _has_forbidden_url_char(original_url):
        raise CommandTreeSyncError('构建站请求 URL 不在受控形态')
    try:
        parsed = urllib.parse.urlsplit(original_url)
    except ValueError as exc:
        raise CommandTreeSyncError('构建站请求 URL 无效') from exc
    scheme = parsed.scheme.casefold()
    host = parsed.hostname or ''
    try:
        port = parsed.port or (443 if scheme == 'https' else 80)
    except ValueError as exc:
        raise CommandTreeSyncError('构建站请求 URL 端口无效') from exc
    if scheme not in {'http', 'https'} or not host or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise CommandTreeSyncError('构建站请求 URL 不在受控形态')
    target = parsed.path or '/'
    try:
        request_target = target.encode('ascii')
        host_header = _authority(parsed).encode('ascii')
    except UnicodeEncodeError as exc:
        raise CommandTreeSyncError('构建站请求 URL 必须是 ASCII') from exc
    candidates = _resolve_allowed_addresses(host, port, allowed_networks=allowed_networks)
    connection = _open_direct_socket(candidates, timeout=20.0)
    try:
        if scheme == 'https':
            try:
                connection = ssl.create_default_context().wrap_socket(connection, server_hostname=host)
            except (ssl.SSLError, OSError) as exc:
                raise CommandTreeSyncError('构建站 TLS 握手失败') from exc
        request = b'GET ' + request_target + b' HTTP/1.1\r\nHost: ' + host_header + b'\r\nUser-Agent: InfoTest-Engine/command-tree-sync\r\nAccept-Encoding: identity\r\nConnection: close\r\n\r\n'
        connection.sendall(request)
        response = http.client.HTTPResponse(connection, method='GET')
        response.begin()
        status = int(response.status)
        if status != 200:
            raise CommandTreeSyncError(f'构建站返回非 200 状态(status={status})')
        content_encoding = str(response.getheader('Content-Encoding') or '')
        if content_encoding.casefold() not in {'', 'identity'}:
            raise CommandTreeSyncError('构建站响应编码不受支持')
        declared = response.getheader('Content-Length')
        declared_size: int | None = None
        if declared:
            try:
                declared_size = int(declared)
            except ValueError as exc:
                raise CommandTreeSyncError('构建站 Content-Length 无效') from exc
            if declared_size < 1 or declared_size > max_bytes:
                raise CommandTreeSyncError('构建站响应声明大小超限')
        raw = response.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raise CommandTreeSyncError('构建站响应实际大小超限')
        if declared_size is not None and len(raw) != declared_size:
            raise CommandTreeSyncError('构建站响应长度与声明不一致')
        if not raw:
            raise CommandTreeSyncError('构建站返回空响应')
        return raw
    except CommandTreeSyncError:
        raise
    except (http.client.HTTPException, TimeoutError, OSError) as exc:
        raise CommandTreeSyncError(f'构建站请求失败({type(exc).__name__})') from exc
    finally:
        connection.close()

def _target_filename_tokens(filename: str) -> tuple[str, ...]:
    name = Path(filename).name
    if not name.casefold().startswith('command_tree-') or not name.casefold().endswith('.xml'):
        return ()
    core = name[len('command_tree-'):-len('.xml')]
    return tuple(re.findall('[a-z0-9]+', core.casefold()))

def _page_filename_tokens(url: str) -> tuple[str, ...]:
    filename = posixpath.basename(urllib.parse.urlsplit(url).path)
    stem = filename[:-5] if filename.casefold().endswith('.html') else filename
    return tuple(re.findall('[a-z0-9]+', stem.casefold()))

def _contains_token_sequence(tokens: tuple[str, ...], wanted: tuple[str, ...]) -> bool:
    if not wanted or len(tokens) < len(wanted):
        return False
    return any((tokens[index:index + len(wanted)] == wanted for index in range(len(tokens) - len(wanted) + 1)))

def _discover_xml_url(*, index_url: str, identity: BuildIdentity, fetcher: HttpFetcher, authority: str, path_prefix: str, index_max_bytes: int, max_pages: int, max_links: int) -> str:
    if max_pages < 3:
        raise CommandTreeSyncError('构建站索引遍历页数预算不足')
    link_count = 0

    def links_on(page: str) -> list[str]:
        nonlocal link_count
        raw = fetcher(page, index_max_bytes)
        if len(raw) > index_max_bytes:
            raise CommandTreeSyncError('构建站索引页面超限')
        parser = _HrefParser()
        try:
            parser.feed(raw.decode('latin-1'))
        except Exception as exc:
            raise CommandTreeSyncError('构建站索引 HTML 无法解析') from exc
        if parser.oversized_href:
            raise CommandTreeSyncError('构建站索引 href 长度超限')
        link_count += len(parser.hrefs)
        if link_count > max_links:
            raise CommandTreeSyncError('构建站索引链接数超限')
        links: list[str] = []
        for href in parser.hrefs:
            link = _validated_link(page, href, authority=authority, path_prefix=path_prefix)
            if link is None:
                continue
            links.append(link)
        return links
    release_tokens = tuple(identity.release.split('.'))
    product_token = identity.product.casefold()
    release_pages = {link for link in links_on(index_url) if urllib.parse.urlsplit(link).path.casefold().endswith('.html') and _page_filename_tokens(link) == (product_token, *release_tokens)}
    if len(release_pages) != 1:
        raise CommandTreeSyncError(f'构建站精确 release 页面数量不是 1(count={len(release_pages)})')
    release_page = next(iter(release_pages))
    platform_tokens = tuple((token.casefold() for token in re.findall('[A-Za-z0-9]+', identity.platform)))
    platform_pages = {link for link in links_on(release_page) if urllib.parse.urlsplit(link).path.casefold().endswith('.html') and product_token in _page_filename_tokens(link) and _contains_token_sequence(_page_filename_tokens(link), release_tokens) and _contains_token_sequence(_page_filename_tokens(link), platform_tokens)}
    if len(platform_pages) != 1:
        raise CommandTreeSyncError(f'构建站精确 product/platform 页面数量不是 1(count={len(platform_pages)})')
    platform_page = next(iter(platform_pages))
    matches: set[str] = set()
    for link in links_on(platform_page):
        filename = posixpath.basename(urllib.parse.urlsplit(link).path)
        if _target_filename_tokens(filename) == identity.filename_tokens:
            matches.add(link)
    if len(matches) != 1:
        raise CommandTreeSyncError(f'构建站精确 XML 候选数量不是 1(count={len(matches)})')
    return next(iter(matches))

def preflight_command_tree_xml(raw: bytes, *, max_bytes: int=DEFAULT_XML_MAX_BYTES, error_type: type[Exception]=CommandTreeSyncError) -> dict[str, int]:
    if not raw or len(raw) > max_bytes:
        raise error_type('vendor XML 大小无效')
    if b'\x00' in raw:
        raise error_type('vendor XML 编码不在受控 ASCII 兼容集合')
    upper = raw.upper()
    if b'<!DOCTYPE' in upper or b'<!ENTITY' in upper:
        raise error_type('vendor XML 含禁止的实体声明')
    node_count = 0
    depth = 0
    item_count = 0
    results_total = 0
    results_nonempty = 0
    root_name = ''
    scope_seen = False
    result_text: list[bool] = []
    element_stack: list[str] = []

    def reject_entity(*_args) -> None:
        raise error_type('vendor XML 含禁止的实体声明')

    def start(name: str, _attrs: dict) -> None:
        nonlocal node_count, depth, item_count, results_total, root_name, scope_seen
        depth += 1
        node_count += 1
        if node_count > 250000 or depth > 96:
            raise error_type('vendor XML 结构预算超限')
        if node_count == 1:
            root_name = name
        if name == 'scope' and depth == 2:
            scope_seen = True
        elif name == 'item':
            if element_stack and element_stack[0] == 'commands' and (element_stack[-1] in {'commands', 'scope', 'menu'}) and all((ancestor in {'scope', 'menu'} for ancestor in element_stack[1:])):
                item_count += 1
        elif name == 'results':
            if result_text:
                raise error_type('vendor XML results 不允许嵌套')
            results_total += 1
            result_text.append(False)
        element_stack.append(name)

    def text_data(value: str) -> None:
        if result_text and value.strip():
            result_text[-1] = True

    def end(name: str) -> None:
        nonlocal depth, results_nonempty
        if not element_stack or element_stack[-1] != name:
            raise error_type('vendor XML 元素栈不闭合')
        if name == 'results':
            if not result_text:
                raise error_type('vendor XML results 结构不闭合')
            results_nonempty += int(result_text.pop())
        element_stack.pop()
        depth -= 1
    parser = expat.ParserCreate()
    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.CharacterDataHandler = text_data
    parser.StartDoctypeDeclHandler = reject_entity
    parser.EntityDeclHandler = reject_entity
    parser.ExternalEntityRefHandler = reject_entity
    try:
        parser.Parse(raw, True)
    except error_type:
        raise
    except (expat.ExpatError, ValueError, OverflowError) as exc:
        raise error_type('vendor XML 无法解析') from exc
    if depth != 0 or result_text or element_stack:
        raise error_type('vendor XML 结构不闭合')
    if root_name != 'commands' or not scope_seen:
        raise error_type('vendor XML 根结构不符合 commands/scope 契约')
    if item_count < 1:
        raise error_type('vendor XML 没有命令 item')
    return {'item_count': item_count, 'results_total': results_total, 'results_nonempty': results_nonempty}

def _validate_xml(raw: bytes, *, max_bytes: int) -> dict[str, int]:
    counts = preflight_command_tree_xml(raw, max_bytes=max_bytes)
    try:
        ET.fromstring(raw)
    except ET.ParseError as exc:
        raise CommandTreeSyncError('vendor XML 无法解析') from exc
    return counts

def _partition_root(store_root: Path, product: str, platform: str, version: str, build: str) -> Path:
    if not _PRODUCT_RE.fullmatch(product) or not _PLATFORM_RE.fullmatch(platform) or (not _VERSION_RE.fullmatch(version)) or (not _BUILD_RE.fullmatch(build)):
        raise CommandTreeSyncError('命令树 product/platform/version/build 身份无效')
    return Path(store_root) / 'products' / product / 'platforms' / platform / 'builds' / f'{version}_{build}'

def _read_regular(path: Path, *, max_bytes: int) -> bytes:
    try:
        raw = read_regular_nofollow(path, error_type=CommandTreeSyncError, invalid_message='命令树代际路径无效', directory_message='命令树代际目录不可安全读取', open_message='命令树代际文件不可读', bounds_message='命令树代际文件大小越界', changed_message='命令树代际文件读取期间发生变化', max_bytes=max_bytes, min_bytes=1)
    except FileNotFoundError as exc:
        raise CommandTreeSyncError('命令树代际文件缺失') from exc
    assert isinstance(raw, bytes)
    return raw

def _artifact_entry(raw: bytes) -> dict[str, int | str]:
    return {'size': len(raw), 'sha256': _sha(raw)}

def _generation_id(*, product: str, platform: str, version: str, build: str, full_version: str, source_url: str, xml_sha256: str, projection_sha256: str, xml_counts: dict[str, int]) -> str:
    identity = _sha(_canonical_json({'product': product, 'platform': platform, 'version': version, 'device_build': build, 'full_version': full_version, 'source_url': source_url, 'xml_sha256': xml_sha256, 'projection_sha256': projection_sha256, 'xml_counts': xml_counts}))
    return f'g-{xml_sha256[:24]}-{identity[:24]}'

def _xml_sensitive_literal_pattern(literal: str, *, ignore_case: bool) -> re.Pattern | None:
    text = str(literal or '').casefold()
    if not text:
        return None
    flags = re.IGNORECASE if ignore_case else 0
    if re.fullmatch('[a-z0-9]+', text):
        return re.compile(f'(?<![a-z0-9]){re.escape(text)}(?![a-z0-9])', flags)
    return re.compile(re.escape(text), flags)

def xml_sensitive_literal_count(text: str, values: frozenset[str]) -> int:
    folded = str(text or '').casefold()
    count = 0
    for value in values:
        pattern = _xml_sensitive_literal_pattern(value, ignore_case=False)
        if pattern is None:
            continue
        count += int(pattern.search(folded) is not None)
    return count

def xml_sensitive_literal_replace(text: str, values: frozenset[str]) -> str:
    out = str(text or '')
    for value in values:
        pattern = _xml_sensitive_literal_pattern(value, ignore_case=True)
        if pattern is None:
            continue
        out = pattern.sub('[redacted]', out)
    return out

def _xml_default_literal_closure(xml_raw: bytes) -> frozenset[str]:
    from cex_core.engine.case_compiler.credential_literals import is_credential_argument, is_placeholder_default_literal
    try:
        root = ET.fromstring(xml_raw)
    except ET.ParseError as exc:
        raise CommandTreeSyncError('vendor XML 无法提取 default 闭包') from exc
    return frozenset({literal for argument in root.iter('arg') if is_credential_argument(name=argument.get('name'), arg_type=argument.get('type'), help_string=argument.get('help_string')) for literal in [str(argument.get('default_value') or '').strip()] if literal and (not is_placeholder_default_literal(literal))})

def projection_xml_default_literal_count(payload: dict, xml_raw: bytes) -> int:
    defaults = _xml_default_literal_closure(xml_raw)
    hit_count = 0
    headers = payload.get('headers')
    if not isinstance(headers, dict):
        return 0
    for head, entry in headers.items():
        hit_count += xml_sensitive_literal_count(str(head), defaults)
        if not isinstance(entry, dict):
            continue
        variants = [entry.get('args') or [], *(entry.get('arg_variants') or [])]
        for variant in variants:
            if not isinstance(variant, list):
                continue
            for argument in variant:
                if not isinstance(argument, dict):
                    continue
                for key in ('type', 'name', 'length', 'limit', 'help'):
                    value = argument.get(key)
                    if isinstance(value, str):
                        hit_count += xml_sensitive_literal_count(value, defaults)
                domain = argument.get('value_domain')
                if not isinstance(domain, dict):
                    continue
                for claim in domain.get('enum') or []:
                    if not isinstance(claim, dict):
                        continue
                    if str(claim.get('source')) not in _XML_DERIVED_DOMAIN_SOURCES:
                        continue
                    for member in claim.get('values') or []:
                        if isinstance(member, str):
                            hit_count += xml_sensitive_literal_count(member, defaults)
                for claim in domain.get('default') or []:
                    if not isinstance(claim, dict):
                        continue
                    if str(claim.get('source')) not in _XML_DERIVED_DOMAIN_SOURCES:
                        continue
                    if isinstance(claim.get('value'), str):
                        hit_count += xml_sensitive_literal_count(claim['value'], defaults)
        for result in entry.get('results') or []:
            if not isinstance(result, dict):
                continue
            for key in ('text', 'locator', 'operator'):
                value = result.get(key)
                if isinstance(value, str):
                    hit_count += xml_sensitive_literal_count(value, defaults)
    return hit_count

def _validate_projection(raw: bytes, *, version: str, build: str, xml_name: str, xml_sha: str, xml_raw: bytes, allow_stale_policy: bool=False) -> dict:
    try:
        payload = json.loads(raw.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CommandTreeSyncError('vendor 投影不是合法 JSON') from exc
    source = payload.get('source') if isinstance(payload, dict) else None
    policy = payload.get('projection_policy') if isinstance(payload, dict) else None
    current_policy = projection_policy_identity()
    policy_is_current = policy == current_policy
    expected_key = re.compile('(?:^|_)(?:capability_)?expected(?:_|$)', re.IGNORECASE)
    stack: list[object] = [payload]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            for key, value in current.items():
                normalized_key = re.sub('(?<!^)(?=[A-Z])', '_', str(key)).replace('-', '_')
                if expected_key.search(normalized_key):
                    raise CommandTreeSyncError('vendor 投影不得携带 CapabilityXml expected')
                stack.append(value)
        elif isinstance(current, list):
            stack.extend(current)
    top_keys = {'schema', 'version', 'device_os_build', 'source', 'source_dir', 'source_glob', 'generator', 'stats', 'headers', 'manual_declarations', 'projection_policy'}
    source_keys = {'kind', 'device_os_build', 'sha256', 'filename'}
    entry_keys = {'src', 'pmax', 'enums', 'args', 'arg_variants', 'origin', 'results'}
    argument_keys = {'position', 'type', 'optional', 'name', 'length', 'limit', 'help', 'executable', 'value_domain'}
    result_keys = {'text', 'locator', 'operator'}
    value_domain_keys = {'enum', 'union', 'range', 'length', 'default'}
    value_domain_sources = {'xml_limit', 'xml_help', 'manual_table', 'footprint'}

    def xml_result_projection() -> dict[str, list[dict[str, str]]]:
        try:
            root = ET.fromstring(xml_raw)
        except ET.ParseError as exc:
            raise CommandTreeSyncError('vendor XML results 无法复算') from exc
        projected: dict[str, list[dict[str, str]]] = {}

        def walk_results(node: ET.Element, words: list[str], path_parts: list[str]) -> None:
            for child in node:
                if child.tag in {'scope', 'menu'}:
                    name = str(child.get('name') or '').strip()
                    walk_results(child, words + ([name.lower()] if name else []), path_parts + [name or str(child.get('type') or child.tag)])
                    continue
                if child.tag != 'item':
                    continue
                item_name = re.sub('\\s+', ' ', str(child.get('name') or '').strip().lower())
                head = ' '.join(words + ([item_name] if item_name else [])).strip()
                src_path = '/'.join(path_parts + ([item_name] if item_name else []))
                rows: list[dict[str, str]] = []
                results = child.find('results')
                if results is not None:
                    for index, result in enumerate(results.findall('result'), start=1):
                        text = ''.join(result.itertext()).strip()
                        if not text:
                            continue
                        if set(result.attrib) - {'operator'} or list(result):
                            raise CommandTreeSyncError('vendor XML result declaration 结构不受支持')
                        row = {'text': text, 'locator': f'vendor_xml:{build}:{src_path}/results/result:{index}'}
                        operator = str(result.get('operator') or '').strip()
                        if operator:
                            row['operator'] = operator
                        rows.append(row)
                if rows:
                    merged = projected.setdefault(head, [])
                    for row in rows:
                        if row not in merged:
                            merged.append(row)
        walk_results(root, [], [])
        return projected
    expected_results = xml_result_projection()

    def reject_extra(mapping: object, allowed: set[str], label: str) -> None:
        if not isinstance(mapping, dict) or not set(mapping).issubset(allowed):
            raise CommandTreeSyncError(f'vendor 投影 {label} 字段不在契约闭集')

    def reject_invalid_value_domain(domain: object, label: str) -> None:
        reject_extra(domain, value_domain_keys, f'{label} value_domain')
        assert isinstance(domain, dict)
        if not domain:
            raise CommandTreeSyncError('vendor 投影 value_domain 不得为空对象')
        for kind, claims in domain.items():
            if not isinstance(claims, list) or not claims:
                raise CommandTreeSyncError('vendor 投影 value_domain 声明不是非空数组')
            for claim in claims:
                if not isinstance(claim, dict):
                    raise CommandTreeSyncError('vendor 投影 value_domain 声明无效')
                if str(claim.get('source') or '') not in value_domain_sources or not str(claim.get('locator') or ''):
                    raise CommandTreeSyncError('vendor 投影 value_domain 声明缺少可核出处')
                if kind == 'enum':
                    values = claim.get('values')
                    if set(claim) != {'values', 'source', 'locator'} or not isinstance(values, list) or len(values) < 2 or (not all((isinstance(item, str) and item for item in values))):
                        raise CommandTreeSyncError('vendor 投影 enum 声明无效')
                elif kind == 'union':
                    separator = claim.get('separator')
                    if set(claim) != {'separator', 'source', 'locator'} or not isinstance(separator, str) or len(separator) != 1 or separator.isalnum() or separator.isspace():
                        raise CommandTreeSyncError('vendor 投影 union 声明无效')
                elif kind == 'default':
                    if set(claim) != {'value', 'source', 'locator'} or not isinstance(claim.get('value'), str) or (not claim['value']):
                        raise CommandTreeSyncError('vendor 投影 default 声明无效')
                else:
                    low = claim.get('min')
                    high = claim.get('max')
                    if set(claim) != {'min', 'max', 'source', 'locator'} or not isinstance(low, int) or (not isinstance(high, int)) or isinstance(low, bool) or isinstance(high, bool) or (low > high):
                        raise CommandTreeSyncError(f'vendor 投影 {kind} 声明无效')

    def reject_invalid_argument(argument: object, label: str) -> None:
        reject_extra(argument, argument_keys, label)
        assert isinstance(argument, dict)
        if 'value_domain' in argument:
            reject_invalid_value_domain(argument['value_domain'], label)
        if str(argument.get('type') or '') == 'REDACTED_SENSITIVE':
            if (set(argument) != {'position', 'type', 'optional', 'executable'} or argument.get('executable') is not False) and policy_is_current:
                raise CommandTreeSyncError('vendor 投影敏感参数标记不是最小不可执行形态')
        elif 'executable' in argument and policy_is_current:
            raise CommandTreeSyncError('vendor 投影普通参数不得覆写 executable 语义')
    reject_extra(payload, top_keys, '顶层')
    reject_extra(source, source_keys, 'source')
    for collection_name in ('headers', 'manual_declarations'):
        collection = payload.get(collection_name)
        if not isinstance(collection, dict):
            raise CommandTreeSyncError(f'vendor 投影 {collection_name} 不是合法对象')
        for head, entry in collection.items():
            reject_extra(entry, entry_keys, f'{collection_name} entry')
            if policy_is_current and collection_name == 'headers' and ('enums' in entry):
                raise CommandTreeSyncError('vendor 投影 headers 不得再携带已退役 enums 字段')
            if collection_name == 'manual_declarations' and entry.get('results'):
                raise CommandTreeSyncError('vendor 投影手册声明不得携带 XML results')
            projected_results = entry.get('results') or []
            if not isinstance(projected_results, list):
                raise CommandTreeSyncError('vendor 投影 results 不是合法数组')
            for result in projected_results:
                reject_extra(result, result_keys, 'result')
                if not isinstance(result, dict) or not isinstance(result.get('text'), str) or (not result['text']) or (not isinstance(result.get('locator'), str)) or (not result['locator']):
                    raise CommandTreeSyncError('vendor 投影 result 声明不完整')
            if collection_name == 'headers' and projected_results != expected_results.get(str(head), []):
                raise CommandTreeSyncError('vendor 投影 results 与同代 XML 不闭合')
            for argument in entry.get('args') or []:
                reject_invalid_argument(argument, 'argument')
            for variant in entry.get('arg_variants') or []:
                if not isinstance(variant, list):
                    raise CommandTreeSyncError('vendor 投影 argument variant 不是合法数组')
                for argument in variant:
                    reject_invalid_argument(argument, 'argument variant')
    if not isinstance(payload, dict) or not accepts_schema(payload.get('schema'), 'ist.vendor_stdlib') or str(payload.get('version') or '') != version or (str(payload.get('device_os_build') or '') != build) or (not isinstance(payload.get('headers'), dict)) or (not payload.get('headers')) or (not isinstance(payload.get('manual_declarations'), dict)) or (not isinstance(source, dict)) or (source.get('kind') != 'vendor_command_tree_xml') or (str(source.get('device_os_build') or '') != build) or (str(source.get('filename') or '') != xml_name) or (str(source.get('sha256') or '').lower() != xml_sha):
        raise CommandTreeSyncError('vendor 投影身份与 XML 不闭合')
    if policy_is_current:
        hit_count = projection_xml_default_literal_count(payload, xml_raw)
        if hit_count:
            raise CommandTreeSyncError(f'vendor 投影 XML default 闭包终态扫描失败 (matched_literal_count={hit_count})')
    elif not allow_stale_policy:
        raise CommandTreeProjectionPolicyStale('vendor 投影生成策略已过期，禁止消费并要求同步迁移')
    return payload

def _fsync_directory(path: Path) -> None:
    descriptor = open_directory_nofollow(path, error_type=CommandTreeSyncError, invalid_message='命令树代际目录无效', unavailable_message='命令树代际目录不可安全持久化')
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)

@contextlib.contextmanager
def _partition_publish_lock(partition: Path):
    directory_fd = open_directory_nofollow(partition, error_type=CommandTreeSyncError, invalid_message='命令树分区目录无效', unavailable_message='命令树分区目录不可安全加锁')
    lock_fd: int | None = None
    try:
        flags = os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_CLOEXEC', 0)
        if not getattr(os, 'O_NOFOLLOW', 0):
            raise CommandTreeSyncError('命令树发布锁缺少 no-follow 能力')
        try:
            try:
                lock_fd = os.open('.publish.lock', flags, dir_fd=directory_fd)
            except FileNotFoundError:
                try:
                    lock_fd = os.open('.publish.lock', flags | os.O_CREAT | os.O_EXCL, 384, dir_fd=directory_fd)
                except FileExistsError:
                    lock_fd = os.open('.publish.lock', flags, dir_fd=directory_fd)
        except OSError as exc:
            raise CommandTreeSyncError('命令树发布锁不可用') from exc
        info = os.fstat(lock_fd)
        if not stat.S_ISREG(info.st_mode) or int(info.st_nlink) != 1 or (hasattr(os, 'getuid') and int(info.st_uid) != os.getuid()):
            raise CommandTreeSyncError('命令树发布锁身份无效')
        os.fchmod(lock_fd, 384)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
        except OSError as exc:
            raise CommandTreeSyncError('命令树发布锁认领失败') from exc
        named = os.stat('.publish.lock', dir_fd=directory_fd, follow_symlinks=False)
        if (int(named.st_dev), int(named.st_ino)) != (int(info.st_dev), int(info.st_ino)) or not stat.S_ISREG(named.st_mode) or int(named.st_nlink) != 1:
            raise CommandTreeSyncError('命令树发布锁路径发生换档')
        yield
    finally:
        if lock_fd is not None:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            except OSError:
                pass
            os.close(lock_fd)
        os.close(directory_fd)

def _cleanup_owned_directory(generations: Path, directory_name: str, *, staging: bool, expected_identity: tuple[int, int] | None=None) -> None:
    if staging and (not directory_name.startswith('.staging-')) or (not staging and (not _GENERATION_RE.fullmatch(directory_name))) or Path(directory_name).name != directory_name or (directory_name in {'.', '..'}):
        raise CommandTreeSyncError('命令树代际清理身份无效')
    generations_fd = open_directory_nofollow(generations, error_type=CommandTreeSyncError, invalid_message='命令树 generations 路径无效', unavailable_message='命令树 generations 不可安全清理')
    staging_fd: int | None = None
    try:
        flags = os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0) | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_CLOEXEC', 0)
        if not getattr(os, 'O_DIRECTORY', 0) or not getattr(os, 'O_NOFOLLOW', 0):
            raise CommandTreeSyncError('命令树 staging 清理缺少 no-follow 能力')
        try:
            staging_fd = os.open(directory_name, flags, dir_fd=generations_fd)
        except FileNotFoundError:
            return
        except OSError as exc:
            raise CommandTreeSyncError('命令树 staging 不可安全打开清理') from exc
        opened = os.fstat(staging_fd)
        if not stat.S_ISDIR(opened.st_mode) or (hasattr(os, 'getuid') and int(opened.st_uid) != os.getuid()) or (expected_identity is not None and (int(opened.st_dev), int(opened.st_ino)) != expected_identity):
            raise CommandTreeSyncError('命令树代际清理目录身份无效')
        names = os.listdir(staging_fd)
        for name in names:
            if not name or name in {'.', '..'} or Path(name).name != name:
                raise CommandTreeSyncError('命令树 staging 含无效目录项')
            try:
                info = os.stat(name, dir_fd=staging_fd, follow_symlinks=False)
            except OSError as exc:
                raise CommandTreeSyncError('命令树 staging 清理目录项不可核验') from exc
            if not stat.S_ISREG(info.st_mode) or int(info.st_nlink) != 1 or (hasattr(os, 'getuid') and int(info.st_uid) != os.getuid()):
                raise CommandTreeSyncError('命令树 staging 含不可安全清理的目录项')
        for name in names:
            try:
                os.unlink(name, dir_fd=staging_fd)
            except OSError as exc:
                raise CommandTreeSyncError('命令树 staging 文件清理失败') from exc
        os.fsync(staging_fd)
        current = os.stat(directory_name, dir_fd=generations_fd, follow_symlinks=False)
        if not stat.S_ISDIR(current.st_mode) or (int(current.st_dev), int(current.st_ino)) != (int(opened.st_dev), int(opened.st_ino)):
            raise CommandTreeSyncError('命令树 staging 清理目录发生换档')
        os.rmdir(directory_name, dir_fd=generations_fd)
        os.fsync(generations_fd)
    finally:
        if staging_fd is not None:
            os.close(staging_fd)
        os.close(generations_fd)

def _cleanup_owned_staging(generations: Path, staging_name: str) -> None:
    _cleanup_owned_directory(generations, staging_name, staging=True)

def _cleanup_owned_generation(generations: Path, generation_id: str, *, expected_identity: tuple[int, int]) -> None:
    _cleanup_owned_directory(generations, generation_id, staging=False, expected_identity=expected_identity)

def _result_from_generation(*, store_root: Path, product: str, platform: str, version: str, build: str, generation_id: str, manifest_sha256: str='', published: bool=False, allow_stale_policy: bool=False) -> CommandTreeSyncResult:
    if not _GENERATION_RE.fullmatch(generation_id):
        raise CommandTreeSyncError('命令树 generation_id 无效')
    if not re.fullmatch('[0-9a-f]{64}', str(manifest_sha256 or '')):
        raise CommandTreeSyncError('命令树 manifest SHA 身份无效')
    partition = _partition_root(store_root, product, platform, version, build)
    generation = partition / 'generations' / generation_id
    manifest_path = generation / 'manifest.json'
    manifest_raw = _read_regular(manifest_path, max_bytes=DEFAULT_MANIFEST_MAX_BYTES)
    actual_manifest_sha = _sha(manifest_raw)
    if actual_manifest_sha != manifest_sha256:
        raise CommandTreeSyncError('命令树活动指针与 manifest SHA 不一致')
    try:
        manifest = json.loads(manifest_raw.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CommandTreeSyncError('命令树 manifest 无效') from exc
    if not isinstance(manifest, dict):
        raise CommandTreeSyncError('命令树 manifest 无效')
    manifest_product = str(manifest.get('product') or '')
    manifest_platform = str(manifest.get('platform') or '')
    manifest_version = str(manifest.get('version') or '')
    manifest_build = str(manifest.get('device_build') or '')
    full_version = str(manifest.get('full_version') or '')
    identity = parse_build_identity(full_version)
    manifest_keys = {'schema', 'generation_id', 'product', 'platform', 'version', 'device_build', 'full_version', 'source_url', 'xml_counts', 'artifacts'}
    if set(manifest) != manifest_keys or not accepts_schema(manifest.get('schema'), MANIFEST_SCHEMA) or str(manifest.get('generation_id') or '') != generation_id or (manifest_product != product) or (manifest_platform != platform) or (manifest_version != version) or (manifest_build != build) or (identity.product != product) or (identity.platform != platform) or (identity.build != build) or (identity.inventory_version != version):
        raise CommandTreeSyncError('命令树 manifest 身份不闭合')
    artifacts = manifest.get('artifacts')
    if not isinstance(artifacts, dict):
        raise CommandTreeSyncError('命令树 manifest artifacts 无效')
    xml_name = f'cmdtree_{build}.xml'
    projection_name = f'vendor_stdlib_{version}_{build}.json'
    if set(artifacts) != {xml_name, projection_name}:
        raise CommandTreeSyncError('命令树 manifest 资产集合不完整')
    generation_fd = open_directory_nofollow(generation, error_type=CommandTreeSyncError, invalid_message='命令树代际目录无效', unavailable_message='命令树代际目录不可安全读取')
    try:
        generation_entries = set(os.listdir(generation_fd))
    finally:
        os.close(generation_fd)
    if generation_entries != {'manifest.json', xml_name, projection_name}:
        raise CommandTreeSyncError('命令树代际目录资产集合不闭合')
    xml_path = generation / xml_name
    projection_path = generation / projection_name
    xml_raw = _read_regular(xml_path, max_bytes=DEFAULT_XML_MAX_BYTES)
    projection_raw = _read_regular(projection_path, max_bytes=DEFAULT_PROJECTION_MAX_BYTES)
    for name, raw in ((xml_name, xml_raw), (projection_name, projection_raw)):
        entry = artifacts.get(name)
        if not isinstance(entry, dict) or entry != _artifact_entry(raw):
            raise CommandTreeSyncError('命令树 manifest 资产摘要不一致')
    counts = _validate_xml(xml_raw, max_bytes=DEFAULT_XML_MAX_BYTES)
    _validate_projection(projection_raw, version=version, build=build, xml_name=xml_name, xml_sha=_sha(xml_raw), xml_raw=xml_raw, allow_stale_policy=allow_stale_policy)
    declared_counts = manifest.get('xml_counts')
    if declared_counts != counts:
        raise CommandTreeSyncError('命令树 manifest XML 计数不一致')
    source_url = _validated_manifest_source_url(str(manifest.get('source_url') or ''))
    if urllib.parse.urlsplit(source_url).scheme != 'local' and _target_filename_tokens(posixpath.basename(urllib.parse.urlsplit(source_url).path)) != identity.filename_tokens:
        raise CommandTreeSyncError('命令树 manifest source_url 与产品身份不一致')
    expected_generation_id = _generation_id(product=product, platform=platform, version=version, build=build, full_version=full_version, source_url=source_url, xml_sha256=_sha(xml_raw), projection_sha256=_sha(projection_raw), xml_counts=counts)
    if generation_id != expected_generation_id:
        raise CommandTreeSyncError('命令树 generation_id 与代际内容不一致')
    return CommandTreeSyncResult(product=product, platform=platform, version=version, device_build=build, full_version=full_version, generation_id=generation_id, generation_root=generation, xml_path=xml_path, projection_path=projection_path, manifest_path=manifest_path, manifest_sha256=actual_manifest_sha, source_url=source_url, source_sha256=_sha(xml_raw), source_size=len(xml_raw), projection_sha256=_sha(projection_raw), results_total=counts['results_total'], results_nonempty=counts['results_nonempty'], item_count=counts['item_count'], published=published)

def resolve_active_command_tree(*, product: str, platform: str, version: str, device_build: str, store_root: Path | None=None, _allow_stale_policy: bool=False) -> CommandTreeSyncResult | None:
    product = str(product or '').strip()
    platform = str(platform or '').strip()
    version = str(version or '').strip()
    device_build = str(device_build or '').strip()
    partition = _partition_root(store_root or COMMAND_TREE_STORE_ROOT, product, platform, version, device_build)
    pointer = partition / 'active.json'
    try:
        pointer.lstat()
    except FileNotFoundError:
        return None
    pointer_raw = _read_regular(pointer, max_bytes=64 * 1024)
    try:
        payload = json.loads(pointer_raw.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CommandTreeSyncError('命令树 active 指针无效') from exc
    expected_pointer = {'schema', 'product', 'platform', 'version', 'device_build', 'generation_id', 'manifest_sha256'}
    if not isinstance(payload, dict) or set(payload) != expected_pointer or (not accepts_schema(payload.get('schema'), ACTIVE_SCHEMA)) or (str(payload.get('product') or '') != product) or (str(payload.get('platform') or '') != platform) or (str(payload.get('version') or '') != version) or (str(payload.get('device_build') or '') != device_build):
        raise CommandTreeSyncError('命令树 active 身份无效')
    return _result_from_generation(store_root=store_root or COMMAND_TREE_STORE_ROOT, product=product, platform=platform, version=version, build=device_build, generation_id=str(payload.get('generation_id') or ''), manifest_sha256=str(payload.get('manifest_sha256') or ''), allow_stale_policy=_allow_stale_policy)

def resolve_command_tree_generation(*, product: str, platform: str, version: str, device_build: str, generation_id: str, manifest_sha256: str, store_root: Path | None=None) -> CommandTreeSyncResult:
    return _result_from_generation(store_root=store_root or COMMAND_TREE_STORE_ROOT, product=str(product or '').strip(), platform=str(platform or '').strip(), version=str(version or '').strip(), build=str(device_build or '').strip(), generation_id=str(generation_id or '').strip(), manifest_sha256=str(manifest_sha256 or '').strip().lower())

def _normalize_platform_allowlist(values: Iterable[str]) -> frozenset[str]:
    platforms: set[str] = set()
    for value in values:
        original = str(value or '')
        raw = original.strip()
        if raw != original or not _PLATFORM_RE.fullmatch(raw):
            raise CommandTreeSyncError('命令树 platform allowlist 条目无效')
        platforms.add(raw)
    if not platforms:
        raise CommandTreeSyncError('命令树 platform allowlist 为空')
    return frozenset(platforms)

def _normalize_http_sha256_pins(values: Mapping[str, str] | None) -> dict[str, str]:
    if values is None:
        return {}
    if not isinstance(values, Mapping):
        raise CommandTreeSyncError('构建站 HTTP SHA256 pin 配置无效')
    pins: dict[str, str] = {}
    for full_version, digest in values.items():
        identity_key = str(full_version or '')
        digest_value = str(digest or '')
        parsed_identity = parse_build_identity(identity_key)
        if parsed_identity.full_version != identity_key:
            raise CommandTreeSyncError('构建站 HTTP SHA256 pin 配置无效')
        if not _SHA256_RE.fullmatch(digest_value):
            raise CommandTreeSyncError('构建站 HTTP SHA256 pin 配置无效')
        pins[identity_key] = digest_value
    return pins

def _normalize_trusted_http_authorities(values: Iterable[str]) -> frozenset[str]:
    trusted: set[str] = set()
    for value in values:
        original = str(value or '')
        raw = original.strip()
        if raw != original or not raw or len(raw) > 261 or _has_forbidden_url_char(raw) or any((char in raw for char in '/\\@?#%')):
            raise CommandTreeSyncError('构建站可信 HTTP authority 配置无效')
        try:
            parsed = urllib.parse.urlsplit(f'http://{raw}/')
            canonical = _authority(parsed)
        except (CommandTreeSyncError, ValueError) as exc:
            raise CommandTreeSyncError('构建站可信 HTTP authority 配置无效') from exc
        if canonical != raw.casefold():
            raise CommandTreeSyncError('构建站可信 HTTP authority 配置无效')
        trusted.add(canonical)
    return frozenset(trusted)

def _prepare_staging_generation(*, staging: Path, product: str, platform: str, inventory_version: str, build: str, full_version: str, xml_url: str, xml_raw: bytes, xml_sha: str, counts: dict[str, int], projection_builder: ProjectionBuilder) -> tuple[str, bytes]:
    xml_name = f'cmdtree_{build}.xml'
    projection_name = f'vendor_stdlib_{inventory_version}_{build}.json'
    xml_path = staging / xml_name
    atomic_write_bytes_nofollow(xml_path, xml_raw, error_type=CommandTreeSyncError, invalid_message='vendor XML staging 路径无效', unavailable_message='vendor XML 无法安全写入 staging', create_parents=False)
    try:
        generated = projection_builder(version=inventory_version, device_build=build, xml_path=xml_path, output_dir=staging, manual_version=parse_build_identity(full_version).release)
    except Exception as exc:
        raise CommandTreeSyncError(f'vendor 投影生成失败({type(exc).__name__})') from exc
    projection_path = staging / projection_name
    if isinstance(generated, dict) and generated.get('path'):
        try:
            if Path(generated['path']) != projection_path:
                raise CommandTreeSyncError('投影生成器返回了代际外路径')
        except TypeError as exc:
            raise CommandTreeSyncError('投影生成器返回路径无效') from exc
    projection_raw = _read_regular(projection_path, max_bytes=DEFAULT_PROJECTION_MAX_BYTES)
    projection_sha = _sha(projection_raw)
    _validate_projection(projection_raw, version=inventory_version, build=build, xml_name=xml_name, xml_sha=xml_sha, xml_raw=xml_raw)
    generation_id = _generation_id(product=product, platform=platform, version=inventory_version, build=build, full_version=full_version, source_url=xml_url, xml_sha256=xml_sha, projection_sha256=projection_sha, xml_counts=counts)
    manifest_raw = _canonical_json({'schema': MANIFEST_SCHEMA, 'generation_id': generation_id, 'product': product, 'platform': platform, 'version': inventory_version, 'device_build': build, 'full_version': full_version, 'source_url': xml_url, 'xml_counts': counts, 'artifacts': {xml_name: _artifact_entry(xml_raw), projection_name: _artifact_entry(projection_raw)}})
    if len(manifest_raw) > DEFAULT_MANIFEST_MAX_BYTES:
        raise CommandTreeSyncError('命令树 manifest 大小超限')
    atomic_write_bytes_nofollow(staging / 'manifest.json', manifest_raw, error_type=CommandTreeSyncError, invalid_message='命令树 manifest staging 路径无效', unavailable_message='命令树 manifest 无法安全写入 staging', create_parents=False)
    staging_fd = open_directory_nofollow(staging, error_type=CommandTreeSyncError, invalid_message='命令树 staging 目录无效', unavailable_message='命令树 staging 目录不可安全读取')
    try:
        staging_entries = set(os.listdir(staging_fd))
    finally:
        os.close(staging_fd)
    if staging_entries != {'manifest.json', xml_name, projection_name}:
        raise CommandTreeSyncError('命令树 staging 资产集合不闭合')
    _fsync_directory(staging)
    return (generation_id, manifest_raw)

def _assert_cached_generation_matches_request(cached: CommandTreeSyncResult, *, identity: BuildIdentity, canonical_index: str, authority: str, path_prefix: str, required_http_pin: str) -> None:
    if cached.full_version != identity.full_version:
        raise CommandTreeSyncError('同 version/build 活动代际的完整产品身份冲突')
    current_source = _validated_link(canonical_index, cached.source_url, authority=authority, path_prefix=path_prefix)
    if current_source is None or current_source != cached.source_url:
        raise CommandTreeSyncError('活动命令树来源不符合当前构建站策略')
    if required_http_pin and cached.source_sha256 != required_http_pin:
        raise CommandTreeSyncError('活动 HTTP 命令树与 operator SHA256 pin 不一致')

def _migrate_stale_active_generation(*, root: Path, partition: Path, identity: BuildIdentity, inventory_version: str, build: str, canonical_index: str, authority: str, path_prefix: str, required_http_pin: str, projection_builder: ProjectionBuilder) -> CommandTreeSyncResult:
    generations = partition / 'generations'
    with _partition_publish_lock(partition):
        try:
            current = resolve_active_command_tree(product=identity.product, platform=identity.platform, version=inventory_version, device_build=build, store_root=root)
        except CommandTreeProjectionPolicyStale:
            current = resolve_active_command_tree(product=identity.product, platform=identity.platform, version=inventory_version, device_build=build, store_root=root, _allow_stale_policy=True)
            stale = True
        else:
            stale = False
        if current is None:
            raise CommandTreeSyncError('命令树 stale active 在迁移锁内消失')
        _assert_cached_generation_matches_request(current, identity=identity, canonical_index=canonical_index, authority=authority, path_prefix=path_prefix, required_http_pin=required_http_pin)
        if not stale:
            return current
        logger.warning('命令树代际生成策略过期，按缓存 XML 重铸: %s/%s/%s build=%s stale_generation=%s', identity.product, identity.platform, inventory_version, build, current.generation_id)
        xml_raw = _read_regular(current.xml_path, max_bytes=DEFAULT_XML_MAX_BYTES)
        counts = _validate_xml(xml_raw, max_bytes=DEFAULT_XML_MAX_BYTES)
        xml_sha = _sha(xml_raw)
        if xml_sha != current.source_sha256:
            raise CommandTreeSyncError('命令树 stale XML 摘要在迁移前发生变化')
        staging = generations / f'.staging-{time.time_ns()}-{secrets.token_hex(6)}'
        descriptor = open_directory_nofollow(staging, error_type=CommandTreeSyncError, invalid_message='命令树迁移 staging 路径无效', unavailable_message='命令树迁移 staging 不可安全创建', create_missing=True, create_mode=448)
        os.close(descriptor)
        try:
            generation_id, manifest_raw = _prepare_staging_generation(staging=staging, product=identity.product, platform=identity.platform, inventory_version=inventory_version, build=build, full_version=identity.full_version, xml_url=current.source_url, xml_raw=xml_raw, xml_sha=xml_sha, counts=counts, projection_builder=projection_builder)
        except BaseException as exc:
            try:
                _cleanup_owned_staging(generations, staging.name)
            except Exception as cleanup_exc:
                if isinstance(exc, Exception):
                    raise CommandTreeSyncError('命令树 stale 迁移失败且残件无法安全清理') from cleanup_exc
            raise
        manifest_sha = _sha(manifest_raw)
        final = generations / generation_id
        staging_info = staging.lstat()
        owned_identity = (int(staging_info.st_dev), int(staging_info.st_ino))
        renamed_by_us = False
        try:
            generations_fd = open_directory_nofollow(generations, error_type=CommandTreeSyncError, invalid_message='命令树 generations 路径无效', unavailable_message='命令树 generations 不可安全迁移')
            try:
                try:
                    os.rename(staging.name, final.name, src_dir_fd=generations_fd, dst_dir_fd=generations_fd)
                    renamed_by_us = True
                    os.fsync(generations_fd)
                except OSError as exc:
                    if exc.errno not in {errno.EEXIST, errno.ENOTEMPTY}:
                        raise CommandTreeSyncError('命令树迁移代际 rename 发布失败') from exc
                    final_info = final.lstat()
                    if not stat.S_ISDIR(final_info.st_mode) or final.is_symlink():
                        raise CommandTreeSyncError('命令树迁移既有目标代际身份无效') from exc
            finally:
                os.close(generations_fd)
            _cleanup_owned_staging(generations, staging.name)
            verified = _result_from_generation(store_root=root, product=identity.product, platform=identity.platform, version=inventory_version, build=build, generation_id=generation_id, manifest_sha256=manifest_sha)
            pointer_raw = _canonical_json({'schema': ACTIVE_SCHEMA, 'product': identity.product, 'platform': identity.platform, 'version': inventory_version, 'device_build': build, 'generation_id': generation_id, 'manifest_sha256': verified.manifest_sha256})
            atomic_write_bytes_nofollow(partition / 'active.json', pointer_raw, error_type=CommandTreeSyncError, invalid_message='命令树 active 指针路径无效', unavailable_message='命令树迁移 active 指针无法原子发布', create_parents=False)
            return CommandTreeSyncResult(**{**verified.__dict__, 'published': True})
        except BaseException as exc:
            try:
                _cleanup_owned_staging(generations, staging.name)
                if renamed_by_us:
                    try:
                        active_after_error = resolve_active_command_tree(product=identity.product, platform=identity.platform, version=inventory_version, device_build=build, store_root=root)
                    except CommandTreeSyncError:
                        active_after_error = None
                    if active_after_error is None or active_after_error.generation_id != generation_id or active_after_error.manifest_sha256 != manifest_sha:
                        _cleanup_owned_generation(generations, generation_id, expected_identity=owned_identity)
            except Exception as cleanup_exc:
                if isinstance(exc, Exception):
                    raise CommandTreeSyncError('命令树 stale 迁移发布失败且残件无法安全清理') from cleanup_exc
            raise

def _publish_generation(*, root: Path, identity: BuildIdentity, xml_url: str, xml_raw: bytes, counts: dict[str, int], projection_builder: ProjectionBuilder, replace_active_generation_id: str='') -> CommandTreeSyncResult:
    inventory_version = identity.inventory_version
    build = identity.build
    partition = _partition_root(root, identity.product, identity.platform, inventory_version, build)
    generations = partition / 'generations'
    with _STORE_BOOTSTRAP_LOCK:
        directories = (root, root / 'products', root / 'products' / identity.product, root / 'products' / identity.product / 'platforms', root / 'products' / identity.product / 'platforms' / identity.platform, root / 'products' / identity.product / 'platforms' / identity.platform / 'builds', partition, generations)
        for directory in directories:
            descriptor = open_directory_nofollow(directory, error_type=CommandTreeSyncError, invalid_message='命令树代际仓路径无效', unavailable_message='命令树代际仓不可安全创建', create_missing=True, create_mode=448)
            os.close(descriptor)
    xml_sha = _sha(xml_raw)
    staging = generations / f'.staging-{time.time_ns()}-{secrets.token_hex(6)}'
    descriptor = open_directory_nofollow(staging, error_type=CommandTreeSyncError, invalid_message='命令树 staging 路径无效', unavailable_message='命令树 staging 不可安全创建', create_missing=True, create_mode=448)
    os.close(descriptor)
    manifest_sha = ''
    generation_id = ''
    renamed_by_us = False
    owned_identity: tuple[int, int] | None = None
    try:
        try:
            generation_id, manifest_raw = _prepare_staging_generation(staging=staging, product=identity.product, platform=identity.platform, inventory_version=inventory_version, build=build, full_version=identity.full_version, xml_url=xml_url, xml_raw=xml_raw, xml_sha=xml_sha, counts=counts, projection_builder=projection_builder)
        except BaseException as exc:
            try:
                _cleanup_owned_staging(generations, staging.name)
            except Exception as cleanup_exc:
                if isinstance(exc, Exception):
                    raise CommandTreeSyncError('命令树 staging 生成失败且残件无法安全清理') from cleanup_exc
            raise
        manifest_sha = _sha(manifest_raw)
        final = generations / generation_id
        staging_stat = staging.lstat()
        owned_identity = (int(staging_stat.st_dev), int(staging_stat.st_ino))
        with _partition_publish_lock(partition), contextlib.ExitStack() as rollback:
            rollback.callback(_cleanup_owned_staging, generations, staging.name)
            current = resolve_active_command_tree(product=identity.product, platform=identity.platform, version=inventory_version, device_build=build, store_root=root, _allow_stale_policy=bool(replace_active_generation_id))
            _partition_text = f'{identity.product}/{identity.platform}/{inventory_version} build={build}'
            try:
                _new_projection_sha = str(json.loads(manifest_raw.decode('utf-8'))['artifacts'][f'vendor_stdlib_{inventory_version}_{build}.json']['sha256'])
            except Exception:
                _new_projection_sha = ''
            if current is not None:
                if current.generation_id == generation_id and current.manifest_sha256 == manifest_sha:
                    logger.info('命令树代际复用: %s generation=%s（重生内容与活动代际同一）', _partition_text, generation_id)
                    _cleanup_owned_staging(generations, staging.name)
                    return current
                if current.generation_id != replace_active_generation_id:
                    raise CommandTreeSyncError('命令树活动代际发生并发身份冲突')
                logger.warning('命令树代际换代: %s %s → %s（源 XML 同一=%s；投影 sha %s → %s）', _partition_text, current.generation_id, generation_id, current.source_sha256 == xml_sha, current.projection_sha256[:12], _new_projection_sha[:12])
            else:
                logger.info('命令树代际首发: %s generation=%s', _partition_text, generation_id)
            generations_fd = open_directory_nofollow(generations, error_type=CommandTreeSyncError, invalid_message='命令树 generations 路径无效', unavailable_message='命令树 generations 不可安全发布')
            try:
                try:
                    os.rename(staging.name, final.name, src_dir_fd=generations_fd, dst_dir_fd=generations_fd)
                    renamed_by_us = True
                    rollback.callback(_cleanup_owned_generation, generations, generation_id, expected_identity=owned_identity)
                    os.fsync(generations_fd)
                except OSError as exc:
                    if exc.errno not in {errno.EEXIST, errno.ENOTEMPTY}:
                        raise CommandTreeSyncError('命令树代际 rename 发布失败') from exc
                    final_stat = final.lstat()
                    if not stat.S_ISDIR(final_stat.st_mode) or final.is_symlink():
                        raise CommandTreeSyncError('命令树既有目标代际身份无效') from exc
            finally:
                os.close(generations_fd)
            _cleanup_owned_staging(generations, staging.name)
            verified = _result_from_generation(store_root=root, product=identity.product, platform=identity.platform, version=inventory_version, build=build, generation_id=generation_id, manifest_sha256=manifest_sha)
            pointer_raw = _canonical_json({'schema': ACTIVE_SCHEMA, 'product': identity.product, 'platform': identity.platform, 'version': inventory_version, 'device_build': build, 'generation_id': generation_id, 'manifest_sha256': verified.manifest_sha256})
            atomic_write_bytes_nofollow(partition / 'active.json', pointer_raw, error_type=CommandTreeSyncError, invalid_message='命令树 active 指针路径无效', unavailable_message='命令树 active 指针无法原子发布', create_parents=False)
            rollback.pop_all()
            return CommandTreeSyncResult(**{**verified.__dict__, 'published': True})
    except BaseException as exc:
        try:
            _cleanup_owned_staging(generations, staging.name)
            if renamed_by_us and owned_identity is not None:
                active_after_error = resolve_active_command_tree(product=identity.product, platform=identity.platform, version=inventory_version, device_build=build, store_root=root)
                if active_after_error is None or active_after_error.generation_id != generation_id or active_after_error.manifest_sha256 != manifest_sha:
                    _cleanup_owned_generation(generations, generation_id, expected_identity=owned_identity)
        except Exception as cleanup_exc:
            if isinstance(exc, Exception):
                raise CommandTreeSyncError('命令树发布失败且残件无法安全清理') from cleanup_exc
        raise

def publish_local_command_tree(*, xml_path: Path, expected_sha256: str, full_version: str, version: str, projection_builder: ProjectionBuilder, store_root: Path | None=None) -> CommandTreeSyncResult:
    identity = parse_build_identity(full_version)
    requested_version = str(version or '').strip()
    requested_parts = requested_version.split('.')
    release_parts = identity.release.split('.')
    if not _VERSION_RE.fullmatch(requested_version) or len(requested_parts) not in {2, 3} or requested_parts != release_parts[:len(requested_parts)]:
        raise CommandTreeSyncError('设备完整版本与请求 product version 不一致')
    if not _SHA256_RE.fullmatch(str(expected_sha256 or '')):
        raise CommandTreeSyncError('本地命令树预期 SHA256 无效')
    input_path = Path(xml_path)
    raw = _read_regular(input_path, max_bytes=DEFAULT_XML_MAX_BYTES)
    actual_sha = _sha(raw)
    if actual_sha != expected_sha256:
        raise CommandTreeSyncError('本地命令树 XML SHA256 不一致')
    counts = _validate_xml(raw, max_bytes=DEFAULT_XML_MAX_BYTES)
    source_url = f'local://workspace-input/{actual_sha}.xml'
    return _publish_generation(root=Path(store_root or COMMAND_TREE_STORE_ROOT), identity=identity, xml_url=source_url, xml_raw=raw, counts=counts, projection_builder=projection_builder)

def rebuild_active_command_tree_projection(full_version: str, product_version: str, *, store_root: Path | None=None) -> CommandTreeSyncResult:
    from cex_core.engine.scripts.maintenance.build_vendor_stdlib import generate_vendor_stdlib_projection
    identity = parse_build_identity(full_version)
    requested = str(product_version or '').strip()
    parts = requested.split('.')
    if not _VERSION_RE.fullmatch(requested) or len(parts) not in {2, 3} or parts != identity.release.split('.')[:len(parts)]:
        raise CommandTreeSyncError('设备完整版本与请求 product version 不一致')
    root = Path(store_root or COMMAND_TREE_STORE_ROOT)
    current = resolve_active_command_tree(product=identity.product, platform=identity.platform, version=identity.inventory_version, device_build=identity.build, store_root=root, _allow_stale_policy=True)
    if current is None:
        raise CommandTreeSyncError('真机 build 没有可重生的活动命令树代际')
    xml_raw = _read_regular(current.xml_path, max_bytes=DEFAULT_XML_MAX_BYTES)
    if _sha(xml_raw) != current.source_sha256:
        raise CommandTreeSyncError('命令树 XML 在投影重生前发生身份漂移')
    return _publish_generation(root=root, identity=identity, xml_url=current.source_url, xml_raw=xml_raw, counts=_validate_xml(xml_raw, max_bytes=DEFAULT_XML_MAX_BYTES), projection_builder=generate_vendor_stdlib_projection, replace_active_generation_id=current.generation_id)

def sync_command_tree(*, index_url: str, allowed_authorities: Iterable[str], allowed_platforms: Iterable[str]=(), allowed_ip_networks: Iterable[str]=(), trusted_http_authorities: Iterable[str]=(), insecure_http_sha256_pins: Mapping[str, str] | None=None, expected_product: str='APV', full_version: str, version: str, device_build: str, projection_builder: ProjectionBuilder, fetcher: HttpFetcher | None=None, store_root: Path | None=None, allow_insecure_http: bool=False, index_max_bytes: int=DEFAULT_INDEX_MAX_BYTES, xml_max_bytes: int=DEFAULT_XML_MAX_BYTES, max_pages: int=DEFAULT_MAX_PAGES, max_links: int=DEFAULT_MAX_LINKS) -> CommandTreeSyncResult:
    identity = parse_build_identity(full_version)
    expected = str(expected_product or '')
    if expected != 'APV' or identity.product != expected:
        raise CommandTreeSyncError('命令树同步只接受 expected product=APV')
    platforms = _normalize_platform_allowlist(allowed_platforms)
    if identity.platform not in platforms:
        raise CommandTreeSyncError('设备 platform 未在同步 allowlist')
    allowed_networks = _normalize_allowed_ip_networks(allowed_ip_networks)
    trusted_http = _normalize_trusted_http_authorities(trusted_http_authorities)
    http_pins = _normalize_http_sha256_pins(insecure_http_sha256_pins)
    ver = str(version or '').strip()
    build = str(device_build or '').strip()
    if identity.build != build:
        raise CommandTreeSyncError('设备完整版本与请求 build 不一致')
    requested_parts = ver.split('.')
    release_parts = identity.release.split('.')
    if not _VERSION_RE.fullmatch(ver) or len(requested_parts) not in {2, 3} or requested_parts != release_parts[:len(requested_parts)]:
        raise CommandTreeSyncError('设备完整版本与请求 product version 不一致')
    inventory_version = identity.inventory_version
    root = Path(store_root or COMMAND_TREE_STORE_ROOT)
    partition = _partition_root(root, identity.product, identity.platform, inventory_version, build)
    canonical_index, authority, path_prefix = _validate_base_url(index_url, allowed_authorities=allowed_authorities, allow_insecure_http=allow_insecure_http)
    source_scheme = urllib.parse.urlsplit(canonical_index).scheme.casefold()
    required_http_pin = ''
    if source_scheme == 'http':
        required_http_pin = http_pins.get(identity.full_version, '')
        if authority not in trusted_http and (not required_http_pin):
            raise CommandTreeSyncError('构建站 HTTP authority 未受信任且缺少完整版本身份绑定的 operator SHA256 pin')
    try:
        active = resolve_active_command_tree(product=identity.product, platform=identity.platform, version=inventory_version, device_build=build, store_root=root)
    except CommandTreeProjectionPolicyStale:
        return _migrate_stale_active_generation(root=root, partition=partition, identity=identity, inventory_version=inventory_version, build=build, canonical_index=canonical_index, authority=authority, path_prefix=path_prefix, required_http_pin=required_http_pin, projection_builder=projection_builder)
    if active is not None:
        _assert_cached_generation_matches_request(active, identity=identity, canonical_index=canonical_index, authority=authority, path_prefix=path_prefix, required_http_pin=required_http_pin)
        return active
    fetch = fetcher or (lambda url, max_bytes: _default_fetch(url, max_bytes, allowed_networks=allowed_networks))
    xml_url = _discover_xml_url(index_url=canonical_index, identity=identity, fetcher=fetch, authority=authority, path_prefix=path_prefix, index_max_bytes=index_max_bytes, max_pages=max_pages, max_links=max_links)
    xml_raw = fetch(xml_url, xml_max_bytes)
    xml_sha = _sha(xml_raw)
    if required_http_pin and xml_sha != required_http_pin:
        raise CommandTreeSyncError('下载 HTTP 命令树与 operator SHA256 pin 不一致')
    counts = _validate_xml(xml_raw, max_bytes=xml_max_bytes)
    generations = partition / 'generations'
    with _STORE_BOOTSTRAP_LOCK:
        directories = (root, root / 'products', root / 'products' / identity.product, root / 'products' / identity.product / 'platforms', root / 'products' / identity.product / 'platforms' / identity.platform, root / 'products' / identity.product / 'platforms' / identity.platform / 'builds', partition, generations)
        for directory in directories:
            descriptor = open_directory_nofollow(directory, error_type=CommandTreeSyncError, invalid_message='命令树代际仓路径无效', unavailable_message='命令树代际仓不可安全创建', create_missing=True, create_mode=448)
            os.close(descriptor)
    staging = generations / f'.staging-{time.time_ns()}-{secrets.token_hex(6)}'
    descriptor = open_directory_nofollow(staging, error_type=CommandTreeSyncError, invalid_message='命令树 staging 路径无效', unavailable_message='命令树 staging 不可安全创建', create_missing=True, create_mode=448)
    os.close(descriptor)
    try:
        generation_id, manifest_raw = _prepare_staging_generation(staging=staging, product=identity.product, platform=identity.platform, inventory_version=inventory_version, build=build, full_version=identity.full_version, xml_url=xml_url, xml_raw=xml_raw, xml_sha=xml_sha, counts=counts, projection_builder=projection_builder)
    except BaseException as exc:
        try:
            _cleanup_owned_staging(generations, staging.name)
        except Exception as cleanup_exc:
            if isinstance(exc, Exception):
                raise CommandTreeSyncError('命令树 staging 生成失败且残件无法安全清理') from cleanup_exc
        raise
    final = generations / generation_id
    manifest_sha = _sha(manifest_raw)
    staging_stat = staging.lstat()
    owned_identity = (int(staging_stat.st_dev), int(staging_stat.st_ino))
    renamed_by_us = False
    try:
        with _partition_publish_lock(partition), contextlib.ExitStack() as rollback:
            rollback.callback(_cleanup_owned_staging, generations, staging.name)
            current = resolve_active_command_tree(product=identity.product, platform=identity.platform, version=inventory_version, device_build=build, store_root=root)
            if current is not None:
                if current.generation_id == generation_id and current.manifest_sha256 == manifest_sha:
                    _cleanup_owned_staging(generations, staging.name)
                    return current
                raise CommandTreeSyncError('命令树活动代际发生并发身份冲突')
            generations_fd = open_directory_nofollow(generations, error_type=CommandTreeSyncError, invalid_message='命令树 generations 路径无效', unavailable_message='命令树 generations 不可安全发布')
            try:
                try:
                    os.rename(staging.name, final.name, src_dir_fd=generations_fd, dst_dir_fd=generations_fd)
                    renamed_by_us = True
                    rollback.callback(_cleanup_owned_generation, generations, generation_id, expected_identity=owned_identity)
                    os.fsync(generations_fd)
                except OSError as exc:
                    if exc.errno not in {errno.EEXIST, errno.ENOTEMPTY}:
                        raise CommandTreeSyncError('命令树代际 rename 发布失败') from exc
                    try:
                        final_stat = final.lstat()
                    except OSError as verify_exc:
                        raise CommandTreeSyncError('命令树既有目标代际不可核验') from verify_exc
                    if not stat.S_ISDIR(final_stat.st_mode) or final.is_symlink():
                        raise CommandTreeSyncError('命令树既有目标代际身份无效') from exc
            finally:
                os.close(generations_fd)
            _cleanup_owned_staging(generations, staging.name)
            verified = _result_from_generation(store_root=root, product=identity.product, platform=identity.platform, version=inventory_version, build=build, generation_id=generation_id, manifest_sha256=manifest_sha)
            pointer_raw = _canonical_json({'schema': ACTIVE_SCHEMA, 'product': identity.product, 'platform': identity.platform, 'version': inventory_version, 'device_build': build, 'generation_id': generation_id, 'manifest_sha256': verified.manifest_sha256})
            atomic_write_bytes_nofollow(partition / 'active.json', pointer_raw, error_type=CommandTreeSyncError, invalid_message='命令树 active 指针路径无效', unavailable_message='命令树 active 指针无法原子发布', create_parents=False)
            rollback.pop_all()
            return CommandTreeSyncResult(**{**verified.__dict__, 'published': True})
    except BaseException as exc:
        try:
            _cleanup_owned_staging(generations, staging.name)
            if renamed_by_us:
                active_after_error: CommandTreeSyncResult | None
                try:
                    active_after_error = resolve_active_command_tree(product=identity.product, platform=identity.platform, version=inventory_version, device_build=build, store_root=root)
                except CommandTreeSyncError:
                    active_after_error = None
                if active_after_error is None or active_after_error.generation_id != generation_id or active_after_error.manifest_sha256 != manifest_sha:
                    _cleanup_owned_generation(generations, generation_id, expected_identity=owned_identity)
        except Exception as cleanup_exc:
            if isinstance(exc, Exception):
                raise CommandTreeSyncError('命令树发布失败且残件无法安全清理') from cleanup_exc
        raise

def sync_vendor_command_tree_from_config(full_version: str, product_version: str) -> CommandTreeSyncResult:
    from cex_core.engine.scripts.maintenance.build_vendor_stdlib import generate_vendor_stdlib_projection
    identity = parse_build_identity(full_version)
    index_url = os.environ.get('IST_APV_BUILD_INDEX_URL', '').strip()
    if not index_url:
        raise CommandTreeSyncError('缺少部署配置 IST_APV_BUILD_INDEX_URL，无法同步目标 build 命令树')
    allowed = [item.strip() for item in os.environ.get('IST_APV_BUILD_ALLOWED_AUTHORITIES', '').split(',') if item.strip()]
    if not allowed:
        raise CommandTreeSyncError('缺少部署配置 IST_APV_BUILD_ALLOWED_AUTHORITIES，无法校验构建站来源')
    trusted_http = [item.strip() for item in os.environ.get('IST_APV_BUILD_TRUSTED_HTTP_AUTHORITIES', '').split(',') if item.strip()]
    allowed_platforms = [item.strip() for item in os.environ.get('IST_APV_BUILD_ALLOWED_PLATFORMS', '').split(',') if item.strip()]
    if not allowed_platforms:
        raise CommandTreeSyncError('缺少部署配置 IST_APV_BUILD_ALLOWED_PLATFORMS，无法校验设备平台')
    allowed_networks = [item.strip() for item in os.environ.get('IST_APV_BUILD_ALLOWED_IP_NETWORKS', '').split(',') if item.strip()]
    if not allowed_networks:
        raise CommandTreeSyncError('缺少部署配置 IST_APV_BUILD_ALLOWED_IP_NETWORKS，无法校验构建站地址')
    pins_raw = os.environ.get('IST_APV_BUILD_HTTP_SHA256_PINS', '').strip()
    try:
        http_pins = json.loads(pins_raw) if pins_raw else {}
    except json.JSONDecodeError as exc:
        raise CommandTreeSyncError('部署配置 IST_APV_BUILD_HTTP_SHA256_PINS 不是合法 JSON') from exc
    if not isinstance(http_pins, dict):
        raise CommandTreeSyncError('部署配置 IST_APV_BUILD_HTTP_SHA256_PINS 必须是 JSON 对象')
    allow_http = os.environ.get('IST_APV_BUILD_ALLOW_INSECURE_HTTP', '0').strip().casefold() in {'1', 'true', 'yes', 'on'}
    return sync_command_tree(index_url=index_url, allowed_authorities=allowed, allowed_platforms=allowed_platforms, allowed_ip_networks=allowed_networks, trusted_http_authorities=trusted_http, insecure_http_sha256_pins=http_pins, expected_product='APV', full_version=identity.full_version, version=str(product_version or identity.inventory_version), device_build=identity.build, projection_builder=generate_vendor_stdlib_projection, allow_insecure_http=allow_http)
__all__ = ['BuildIdentity', 'COMMAND_TREE_STORE_ROOT', 'CommandTreeProjectionPolicyStale', 'CommandTreeSyncError', 'CommandTreeSyncResult', 'inventory_version_from_build', 'parse_build_identity', 'parse_build_identity_from_text', 'preflight_command_tree_xml', 'publish_local_command_tree', 'rebuild_active_command_tree_projection', 'projection_policy_identity', 'resolve_active_command_tree', 'resolve_family_key', 'resolve_command_tree_generation', 'sync_command_tree', 'sync_vendor_command_tree_from_config']
