# 生成：tools/extract_engine.py ← InfoTest main/ist_core/security_scrub.py（sha256 03e12bd2ebe933b4）。不在这里手改。
from __future__ import annotations
from cex_core.engine._root import _cex_data_path
import hashlib
import json
import os
import re
from urllib.parse import quote
from pathlib import Path
from typing import Any
_SENSITIVE_KEY_RE = re.compile('(?i)(?:password|passwd|pwd|secret|token|authorization|cookie|api[_-]?key|apikey|access[_-]?key|private[_-]?key|credential|community|jumphost[_-]?pass|(?<![a-z])pin(?![a-z])|密码|口令|令牌|密钥|凭据)')
_METRIC_AMBIGUOUS_KEY_RE = re.compile('(?i)(?:token|credential)')
_STRONG_SECRET_KEY_RE = re.compile('(?i)(?:password|passwd|pwd|(?<![a-z])pin(?![a-z])|private[_-]?key|jumphost[_-]?pass|密码|口令)')
_SHA256_HEX_RE = re.compile('^[0-9A-Fa-f]{64}$')
_AUTHORIZATION_SCHEME_RE = re.compile('(?ix)\n    (?P<prefix>\n      ["\']?Authorization["\']?\n      (?:\\s*[:=]\\s*|\\s+)\n      (?P<quote>["\']?)\n    )\n    (?:Bearer|Basic)\\s+[A-Za-z0-9._~+/=-]+\n    (?P=quote)\n    ')
_QUOTED_SECRET_RE = re.compile('(?ix)\n    (?P<prefix>\n      ["\']?\n      (?:OPENAI_API_KEY|DEEPSEEK_API_KEY|MINERU_TOKEN|\n         IST_JUMPHOST_PASS|JUMPHOST_PASS|APV_PASSWORD|\n         Authorization|password|passwd|pwd|secret|token|\n         api[\\s_-]?key|access[\\s_-]?token|auth[\\s_-]?token|\n         credential|community|密码|口令|令牌|密钥|凭据)\n      ["\']?\n      \\s*(?::|=)\\s*\n    )\n    (?P<quote>["\'])\n    (?P<value>.*?)\n    (?P=quote)\n    ')
_UNQUOTED_PHRASE_SECRET_RE = re.compile('(?ix)\n    (?P<prefix>\n      \\b(?:password|passwd|pwd|secret|token|\n          api[\\s_-]?key|access[\\s_-]?token|auth[\\s_-]?token|\n          credential|community)\n      \\s*(?::|=)\\s*\n    )\n    (?P<value>\n      (?!\\s*(?:["\']|\\*{4}))\n      (?=[^,\\r\\n;}\\]]*\\s)\n      [^,\\r\\n;}\\]]+?\n    )\n    (?=\n      \\s+\\b(?:password|passwd|pwd|secret|token|\n             api[\\s_-]?key|access[\\s_-]?token|auth[\\s_-]?token|\n             credential|community)\\b\\s*(?::|=)\n      |[,;\\r\\n}\\]]\n      |$\n    )\n    ')
_NAMED_SECRET_RE = re.compile('(?ix)\n    (?P<prefix>\n      ["\']?\n      (?:OPENAI_API_KEY|DEEPSEEK_API_KEY|MINERU_TOKEN|\n         IST_JUMPHOST_PASS|JUMPHOST_PASS|APV_PASSWORD|\n         Authorization|Bearer|password|passwd|pwd|secret|token|\n         api[\\s_-]?key|access[\\s_-]?token|auth[\\s_-]?token|credential|community)\n      ["\']?\n      \\s*(?::|=)\\s*\n    )\n    (?P<quote>["\']?)\n    (?P<value>Bearer\\s+[^,\\s}\\]]+|[^,\\s}\\]"\']+)\n    (?P=quote)\n    ')
_SPACE_SECRET_RE = re.compile('(?ix)\n    \\b(?P<key>Authorization|password|passwd|pwd|secret|\n       token|api[\\s_-]?key|access[\\s_-]?token|auth[\\s_-]?token|\n       credential|community)\n    (?P<sep>[^\\S\\r\\n]+)\n    (?P<value>Bearer\\s+\\S+|\\S+)\n    ')
_BEARER_RE = re.compile('(?i)\\bBearer\\s+[A-Za-z0-9._~+/=-]+')
_SSHPASS_RE = re.compile('\\bsshpass\\s+(?:-[A-Za-z]\\s+\\S+\\s+)*?-p\\s*(?P<value>\\S+)')
_CURL_USER_RE = re.compile('(?ix)\n    \\bcurl\\b (?P<gap>[^\\r\\n&|;]{0,200}?)\n    (?<=\\s)\n    (?P<flag>--user[=\\s]|-u\\s*)\n    (?P<quote>["\']?)\n    (?P<user>[^:\\s"\']{0,120}:)\n    (?P<value>[^\\s"\']+)\n    ')
_SUDO_STDIN_RE = re.compile('(?ix)\n    \\becho\\s+\n    (?P<quote>["\'])(?P<value>[^\\r\\n]{0,200}?)(?P=quote)\n    (?P<pipe>\\s*\\|\\s*(?:/usr/bin/)?sudo\\b[^\\r\\n]{0,40}?-S\\b)\n    ')
_SENDLINE_RE = re.compile('(?ix)\n    \\bsendline\\s*\\(\\s*\n    (?P<quote>["\'])(?P<value>[^\\r\\n]{0,200}?)(?P=quote)\n    (?P<tail>\\s*\\))\n    ')
_URL_USERINFO_RE = re.compile('(?x)\n    (?P<prefix>[A-Za-z][A-Za-z0-9+.\\-]*://[^\\s/:@]{1,120}:)\n    (?P<value>[^\\s@/]{1,200})\n    (?P<at>@)\n    ')
_SUDO_PROMPT_RE = re.compile('(?ix)\n    (?P<prefix>\n      \\[sudo\\]\\s*\n      (?:password|passwd|口令|密码)[^\\r\\n:：]{0,40}[:：]\\s*\n    )\n    (?P<value>[^\\r\\n]+)\n    ')
_DEVICE_INTERNAL_PATH_RE = re.compile('(?<![\\w.-])/home/test(?:/[^\\s`\'\\"<>|]*)?')
_UNIX_INTERNAL_PATH_RE = re.compile('(?x)\n    (?<![\\w.-])\n    /(?:Users|private|var|tmp|opt|etc|home|root)\n    (?:/[^\\s`\'"<>|:;,)\\]}]+)+\n    ')
_WINDOWS_INTERNAL_PATH_RE = re.compile('(?ix)\n    \\b[A-Z]:\\\\(?:Users|ProgramData|Windows|Temp)\n    (?:\\\\[^\\s`\'"<>|:;,)\\]}]+)+\n    ')
_BUSINESS_TOKENS = frozenset({'auto_block', 'author_definition_gap_disclosed', 'batch_abandon', 'batch_use_case', 'batch_use_xml', 'case_terminal_static_void', 'confirm', 'continue', 'correct', 'defect', 'defect_conditional', 'deesc_defect', 'deesc_engineering_fault', 'deesc_keep', 'deesc_rebed', 'deesc_reswitch', 'deesc_retry', 'downgrade', 'keep', 'reflow_tau', 'reorder', 'resume', 'retry', 'stop', 'suspend'})
_NON_SECRET_CREDENTIAL_KEYS = frozenset({'bed_lease_id', 'credential_refs', 'credential_valid', 'lint_credential_id', 'option_tokens', 'tokens', 'tokens_in', 'tokens_out'})
_OVERRIDE_PROJECTION_KEYS = frozenset({'override_schema', 'override_class', 'override_token_sha256'})
_SENSITIVE_KEYS_CACHE: tuple[frozenset[str], tuple[str, ...]] = (frozenset(), ())
_CREDENTIAL_ENV_SUFFIXES = ('_KEY', '_TOKEN', '_PASS', '_PASSWORD', '_SECRET')
_NON_CREDENTIAL_ENV_SUFFIXES = ('_HOST_KEY', '_FIELD', '_TOKENS')

def _is_credential_env_name(name: str) -> bool:
    if name.endswith(_NON_CREDENTIAL_ENV_SUFFIXES):
        return False
    return bool(_SENSITIVE_KEY_RE.search(name)) or name.endswith(_CREDENTIAL_ENV_SUFFIXES)

def _sensitive_env_keys() -> tuple[str, ...]:
    global _SENSITIVE_KEYS_CACHE
    keys = frozenset(os.environ)
    cached_keys, cached = _SENSITIVE_KEYS_CACHE
    if keys == cached_keys:
        return cached
    found = tuple(sorted((k for k in keys if _is_credential_env_name(k))))
    _SENSITIVE_KEYS_CACHE = (keys, found)
    return found
_PERCENT_ESCAPE_RE = re.compile('%[0-9A-F]{2}')
_SECRET_VALUES_CACHE: tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]] = ((), (), ())

def _encoded_twins(candidate: str) -> tuple[str, ...]:
    """一个凭据字面值在响应正文里可能出现的编码形态。

    端点把密钥拼回 URL 再回显时是 percent-encoding：Python 侧 `quote(safe="")` 与
    JS 侧 `encodeURIComponent`（参考实现 `reference/opencode/packages/llm/src/route/
    executor.ts` 的 `secretValues()` 用的就是它）的保留字集合不同——JS 不编码
    `! ' ( ) *`——两种都算；十六进制大小写各一份。

    编码不出来就只留原串：POSIX 下 `os.environ` 用 surrogateescape 解码，凭据值带
    非 UTF-8 字节时是带孤立代理的 str，`quote` 默认 `errors="strict"` 会抛
    `UnicodeEncodeError`。这一趟是兜底，绝不能因为孪生算不出而把原串那一趟一起抛掉
    ——`scrub_text` 此前是全函数，调用点里有按「它不会抛」写的 handler。
    """
    twins: list[str] = []
    for safe in ('', "!'()*"):
        try:
            encoded = quote(candidate, safe=safe, errors='surrogateescape')
        except (UnicodeError, TypeError):
            continue
        if encoded == candidate:
            continue
        twins.append(encoded)
        lowered = _PERCENT_ESCAPE_RE.sub(lambda m: m.group(0).lower(), encoded)
        if lowered != encoded:
            twins.append(lowered)
    return tuple(twins)

def _loaded_secret_values() -> tuple[str, ...]:
    """进程里真正装着的凭据字面值，连同它们的编码形态。

    规则式脱敏只认「键名旁边的值」与几种已知前缀；端点把密钥原样回显在错误正文里、
    而它既不带已知前缀也不挨着任何键名时，规则一条都不命中。字面值这一趟是兜底。

    参考实现把这一层单独做了一遍：`reference/opencode/packages/llm/src/route/executor.ts`
    的 `secretValues()` 收集本次请求真正发出去的那些值（含 `Bearer <token>` 里的裸 token），
    再把它们**连同 URL 编码形态**在响应正文里逐一替换；守门是
    `reference/opencode/packages/llm/test/executor.test.ts` 里回显密钥那条。编码形态见
    `_encoded_twins`；结果按键集 + 原始值精确缓存（`_SECRET_VALUES_CACHE`）。
    """
    global _SECRET_VALUES_CACHE
    keys = _sensitive_env_keys()
    raw = tuple((str(os.environ.get(key) or '') for key in keys))
    cached_keys, cached_raw, cached_values = _SECRET_VALUES_CACHE
    if keys == cached_keys and raw == cached_raw:
        return cached_values
    values: set[str] = set()
    for value in raw:
        for candidate in (value, value.strip()):
            if len(candidate) < 8:
                continue
            values.add(candidate)
            values.update(_encoded_twins(candidate))
    result = tuple(sorted(values, key=len, reverse=True))
    _SECRET_VALUES_CACHE = (keys, raw, result)
    return result
_SK_PREFIX_TOKEN_RE = re.compile('(?i)\\bsk-[A-Za-z0-9_-]{16,}')
_URL_QUERY_SECRET_RE = re.compile('(?ix)\n    (?P<prefix>[?&](?:api[_-]?key|apikey|access[_-]?token|auth[_-]?token|key|token)=)\n    (?P<value>[^&\\s"\'<>]+)\n    ')
_DISCLOSURE_NEAR_TOKEN_RE = re.compile('(?ix)\n    (?P<prefix>\n      \\b(?:api[\\s_-]?key|apikey|access[\\s_-]?token|auth[\\s_-]?token|token|\n           secret|password|passwd|credential)\\b\n      |令牌|密钥|秘钥|口令|密码|凭据\n    )\n    (?P<gap>[^\\r\\n]{0,40}?[\\s:=,"\'（(])\n    (?P<value>(?=[A-Za-z0-9_-]*[A-Za-z])(?=[A-Za-z0-9_-]*\\d)[A-Za-z0-9_-]{16,})\n    ')

def scrub_disclosure_text(text: Any, *, scrub_paths: bool=True) -> str:
    out = scrub_text(text, scrub_paths=scrub_paths)
    if not out:
        return ''
    out = _URL_QUERY_SECRET_RE.sub(lambda m: f"{m.group('prefix')}****", out)
    out = _SK_PREFIX_TOKEN_RE.sub('****', out)
    out = _DISCLOSURE_NEAR_TOKEN_RE.sub(lambda m: f"{m.group('prefix')}{m.group('gap')}****", out)
    return out
_PROJECT_ROOT: str | None = None
_HOME_CACHE: tuple[str, str] = ('\x00', '')

def _path_roots() -> tuple[str, str]:
    global _PROJECT_ROOT, _HOME_CACHE
    if _PROJECT_ROOT is None:
        _PROJECT_ROOT = str(_cex_data_path(''))
    home_env = os.environ.get('HOME') or ''
    if _HOME_CACHE[0] != home_env:
        _HOME_CACHE = (home_env, str(Path.home()))
    return (_PROJECT_ROOT, _HOME_CACHE[1])

def scrub_text(text: Any, *, scrub_paths: bool=True) -> str:
    out = str(text or '')
    if not out:
        return ''
    out = _AUTHORIZATION_SCHEME_RE.sub(lambda m: f"{m.group('prefix')}****{m.group('quote')}", out)
    out = _QUOTED_SECRET_RE.sub(lambda m: f"{m.group('prefix')}{m.group('quote')}****{m.group('quote')}", out)
    out = _UNQUOTED_PHRASE_SECRET_RE.sub(lambda m: f"{m.group('prefix')}****", out)
    out = _NAMED_SECRET_RE.sub(lambda m: f"{m.group('prefix')}{m.group('quote')}****{m.group('quote')}", out)
    out = _SPACE_SECRET_RE.sub(lambda m: f"{m.group('key')}{m.group('sep')}****", out)
    out = _BEARER_RE.sub('Bearer ****', out)
    out = _SSHPASS_RE.sub(lambda m: m.group(0)[:m.start('value') - m.start(0)] + '****', out)
    out = _CURL_USER_RE.sub(lambda m: f"curl{m.group('gap')}{m.group('flag')}{m.group('quote')}{m.group('user')}****{m.group('quote')}", out)
    out = _SUDO_STDIN_RE.sub(lambda m: f"echo {m.group('quote')}****{m.group('quote')}{m.group('pipe')}", out)
    out = _SENDLINE_RE.sub(lambda m: f"sendline({m.group('quote')}****{m.group('quote')}{m.group('tail')}", out)
    out = _SUDO_PROMPT_RE.sub(lambda m: f"{m.group('prefix')}****", out)
    out = _URL_USERINFO_RE.sub(lambda m: f"{m.group('prefix')}****{m.group('at')}", out)
    for value in _loaded_secret_values():
        out = out.replace(value, '****')
    if scrub_paths:
        project, home = _path_roots()
        if project:
            out = out.replace(project, '<project-root>')
        if home:
            out = out.replace(home, '<user-home>')
        out = _DEVICE_INTERNAL_PATH_RE.sub('<device-internal-path>', out)
        out = _UNIX_INTERNAL_PATH_RE.sub('<internal-path>', out)
        out = _WINDOWS_INTERNAL_PATH_RE.sub('<internal-path>', out)
    return out

def _scrub_sha256_identity(value: Any, *, scrub_paths: bool) -> str:
    if not isinstance(value, str):
        return '****'
    scrubbed = scrub_text(value, scrub_paths=scrub_paths)
    if scrubbed != value:
        return '****'
    return value if _SHA256_HEX_RE.fullmatch(value) else '****'

def _closed_override_projection(value: dict) -> dict[str, str]:
    if str(value.get('ev') or '') != 'decision':
        return {}
    token = value.get('token')
    if not isinstance(token, str) or not token.startswith('override:'):
        return {}
    try:
        from cex_core.engine.ist_core.compile_engine.blocking_taxonomy import project_override_decision
    except (ImportError, AttributeError):
        return {}
    return project_override_decision(token)

def scrub_value(value: Any, *, scrub_paths: bool=True) -> Any:
    if isinstance(value, dict):
        override_projection = _closed_override_projection(value)
        cleaned = {}
        for key, item in value.items():
            cleaned_key = scrub_text(key, scrub_paths=scrub_paths) if isinstance(key, str) else key
            if str(key) == 'token' and str(item or '') in _BUSINESS_TOKENS:
                cleaned[cleaned_key] = str(item)
            elif str(key) in {'mutation_credential_sha256', 'lint_credential_sha256', 'override_token_sha256'}:
                if str(key) == 'lint_credential_sha256' and isinstance(item, dict):
                    cleaned[cleaned_key] = {scrub_text(str(identity), scrub_paths=scrub_paths): _scrub_sha256_identity(digest, scrub_paths=scrub_paths) for identity, digest in item.items()}
                else:
                    cleaned[cleaned_key] = _scrub_sha256_identity(item, scrub_paths=scrub_paths)
            elif str(key) in _NON_SECRET_CREDENTIAL_KEYS:
                cleaned[cleaned_key] = scrub_value(item, scrub_paths=scrub_paths)
            elif _SENSITIVE_KEY_RE.search(str(key)):
                if _METRIC_AMBIGUOUS_KEY_RE.search(str(key)) and (not _STRONG_SECRET_KEY_RE.search(str(key))) and (isinstance(item, bool) or isinstance(item, (int, float))):
                    cleaned[cleaned_key] = item
                else:
                    cleaned[cleaned_key] = '****'
            else:
                cleaned[cleaned_key] = scrub_value(item, scrub_paths=scrub_paths)
        if override_projection:
            cleaned.update(override_projection)
        elif str(value.get('ev') or '') == 'decision' and 'token' in value and (str(value.get('token') or '') != '****'):
            for key in _OVERRIDE_PROJECTION_KEYS:
                cleaned.pop(key, None)
        return cleaned
    if isinstance(value, list):
        return [scrub_value(item, scrub_paths=scrub_paths) for item in value]
    if isinstance(value, tuple):
        return tuple((scrub_value(item, scrub_paths=scrub_paths) for item in value))
    if isinstance(value, str):
        return scrub_text(value, scrub_paths=scrub_paths)
    return value

def canonical_persisted_value(value: Any) -> Any:
    return scrub_value(value, scrub_paths=False)

def persisted_surface_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()
__all__ = ['canonical_persisted_value', 'persisted_surface_sha256', 'scrub_disclosure_text', 'scrub_text', 'scrub_value']
