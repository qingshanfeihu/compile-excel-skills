# 生成：tools/extract_engine.py ← InfoTest main/case_compiler/card_lint.py（sha256 61d436f8ac309925）。不在这里手改。
from __future__ import annotations
from cex_core.engine._root import _cex_data_path
import json
import re
from pathlib import Path
_AUTOID18_RE = re.compile('(?<!\\d)\\d{18}(?!\\d)')
_REGEX_LEAK_RE = re.compile('\\\\[dswb]|\\[\\^|\\(\\?:|\\.\\*|\\.\\+')
_HINTS = {'card_internal_token': 'internal enum/path token must not reach the signed card face', 'card_bare_autoid': 'render tail digits (…XXXXXX) on the card face; full autoids stay in the machine-readable cases[] payload', 'card_regex_leak': 'move the regex into the credential attachment; describe the expectation in plain Chinese on the card face', 'card_build_identity': 'reference the build via the environment fact source instead of inlining the literal'}

def _full_build_literal() -> str:
    path = _cex_data_path('') / 'knowledge' / 'data' / 'auto_env' / 'env_capabilities.json'
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
        return str(payload.get('build') or '').strip()
    except Exception:
        return ''

def card_lint_findings(text: str, *, internal_text: str | None=None) -> list[dict]:
    """内部禁词只扫描渲染器按字段来源生成的引擎文案视图。

    不能按作者原文的值全局替换：同词也可能出现在引擎措辞面。
    身份、正则及 build 泄漏仍检查原始完整卡面；未给来源视图时检查全文。
    """
    source = str(text or '')
    findings: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def _add(code: str, token: str) -> None:
        key = (code, token)
        if key in seen:
            return
        seen.add(key)
        findings.append({'code': code, 'token': token, 'hint': _HINTS[code]})
    from cex_core.engine.ist_core.compile_engine.user_text_contract import validate_user_facing_text
    validation = validate_user_facing_text({'card_face': source if internal_text is None else internal_text})
    for violation in validation['violations']:
        for token in violation['terms']:
            _add('card_internal_token', token)
    autoid_surface = re.sub('(?m)^签约哈希：[0-9A-Fa-f]{64}\\s*$', '', source)
    for match in _AUTOID18_RE.finditer(autoid_surface):
        _add('card_bare_autoid', match.group(0))
    for match in _REGEX_LEAK_RE.finditer(source):
        _add('card_regex_leak', match.group(0))
    build_literal = _full_build_literal()
    if build_literal and build_literal in source:
        _add('card_build_identity', build_literal)
    return findings
