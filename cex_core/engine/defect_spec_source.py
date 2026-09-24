# 生成：tools/extract_engine.py ← InfoTest main/defect_spec_source.py（sha256 e3d8b4e15b5573a1）。不在这里手改。
from __future__ import annotations
import hashlib
import html
import json
import math
import re
import unicodedata
from typing import Any, Iterable, Mapping, Sequence
from cex_core.engine.common.schema_identity import accepts_schema
RECEIPT_SCHEMA = 'ist.defect-spec-receipt'
VALIDATION_SCHEMA = 'ist.defect-spec-receipt-validation'
SOURCE_CONTEXT_SCHEMA = 'ist.defect-spec-source-context'
_SHA256_RE = re.compile('^[0-9a-f]{64}$')
_EXACT_TICKET_RE = re.compile('^(?:[A-Za-z][A-Za-z0-9_]*-)?(\\d+)$')
_DOC_TYPE_RE = re.compile('^[a-z][a-z0-9_-]{0,31}$')
_ALLOWED_BACKENDS = {'bugzilla', 'zentao', 'zentao_story'}
_PLACEHOLDER_TOKEN_RE = re.compile('^\\[(?:步骤|步驟|结果|結果|期望|操作|重现步骤|重現步驟)\\]$')
_WIPE_DESCRIPTION_REASONS = frozenset({'description_contains_actual_or_logs', 'declaration_contains_credential_material'})
_FIXED_BACKENDS = ('bugzilla', 'zentao', 'zentao_story')
_CONTROL_RE = re.compile('[\\x00-\\x08\\x0b\\x0c\\x0e-\\x1f\\x7f]')
_URL_RE = re.compile('\\b(?:https?|ftp)://[^\\s<>]+', re.IGNORECASE)
_WINDOWS_PATH_RE = re.compile('(?<!\\w)[A-Za-z]:\\\\(?:[^\\s\\\\]+\\\\)*[^\\s\\\\]+')
_UNIX_PATH_RE = re.compile('(?<![\\w:])/(?:[^\\s/]+/)+[^\\s/]+')
_REPO_PATH_RE = re.compile('\\b(?:workspace|knowledge|runtime|main|tests)/(?:[^\\s/]+/)*[^\\s/]+')
_PRIVATE_KEY_RE = re.compile('-----BEGIN [^-\\r\\n]*PRIVATE KEY-----.*?-----END [^-\\r\\n]*PRIVATE KEY-----', re.IGNORECASE | re.DOTALL)
_ENV_KEY_BODY = '[A-Za-z][A-Za-z0-9_]*(?:PASSWORD|PASSWD|PWD|SECRET|TOKEN|API_KEY|ACCESS_KEY|LICENSE_KEY)'
_GENERIC_CREDENTIAL_KEY_BODY = f'(?:{_ENV_KEY_BODY}|password|passwd|pwd|secret|api[_ -]?key|access[_ -]?token|authorization|cookie|license[_ -]?key)'
_CREDENTIAL_RE = re.compile('(?im)\\b(?:password|passwd|pwd|secret|api[_ -]?key|access[_ -]?token|authorization|cookie|license[_ -]?key)\\b\\s*[:=]\\s*[^\\r\\n]+')
_ENV_CREDENTIAL_RE = re.compile(f"""(?im)(?<![A-Za-z0-9_])[\\"']?{_ENV_KEY_BODY}[\\"']?\\s*[:=]\\s*(?:[\\"'][^\\"'\\r\\n]*[\\"']|[^\\r\\n]+)""")
_HTML_TAG_RE = re.compile('</?[A-Za-z][^>\\r\\n]*>')
_HTML_BLOCK_TAG_RE = re.compile('</?(?:h[1-6]|p|div|li|br|tr|td|th|section|article)[^>\\r\\n]*>', re.IGNORECASE)
_ANSI_ESCAPE_RE = re.compile('\\x1b(?:\\[[0-?]*[ -/]*[@-~]|\\][^\\x07]*(?:\\x07|\\x1b\\\\))')
_MARKDOWN_LINK_RE = re.compile('\\[([^\\]\\r\\n]+)\\]\\([^\\)\\r\\n]*\\)')
_DECORATED_CREDENTIAL_KEY_RE = re.compile(f"""(?im)(?<![A-Za-z0-9_])(?:\\*\\*|__|`{{1,3}})?[\\"']?(?P<key>{_GENERIC_CREDENTIAL_KEY_BODY})[\\"']?(?:\\*\\*|__|`{{1,3}})?\\s*(?P<sep>[:=])""")
_YAML_CREDENTIAL_BLOCK_RE = re.compile(f"""(?im)^[ \\t]*[\\"']?{_GENERIC_CREDENTIAL_KEY_BODY}[\\"']?\\s*[:=]\\s*[|>][+-]?[ \\t]*(?:\\r?\\n[ \\t]+[^\\r\\n]*)+""")
_MARKDOWN_TABLE_CREDENTIAL_RE = re.compile(f"""(?im)^[ \\t]*\\|[ \\t]*(?:\\*\\*|__|`{{1,3}})?[\\"']?{_GENERIC_CREDENTIAL_KEY_BODY}[\\"']?(?:\\*\\*|__|`{{1,3}})?[ \\t]*\\|[ \\t]*[^|\\r\\n]+(?:\\|[^\\r\\n]*)?$""")
_ADJACENT_CREDENTIAL_VALUE_RE = re.compile(f"""(?im)^[ \\t|]*(?:\\*\\*|__|`{{1,3}})?[\\"']?{_GENERIC_CREDENTIAL_KEY_BODY}[\\"']?(?:\\*\\*|__|`{{1,3}})?(?:[ \\t]*\\|[ \\t]*[^|\\r\\n]+|\\r?\\n[ \\t]*[^\\r\\n]+|[ \\t]+[^|\\r\\n]+)(?:\\|[^\\r\\n]*)?$""")
_AUTH_SCHEME_CREDENTIAL_RE = re.compile('(?im)(?<![A-Za-z0-9_])authorization\\s+(?:bearer|basic)\\s+\\S+')
_CLI_CREDENTIAL_RE = re.compile(f"""(?im)(?<![A-Za-z0-9_])--(?:{_GENERIC_CREDENTIAL_KEY_BODY})(?:\\s*=\\s*|\\s+)(?:[\\"'][^\\"'\\r\\n]*[\\"']|\\S+)""")
_SENSITIVE_CREDENTIAL_KEY_RE = re.compile(f'^(?:{_GENERIC_CREDENTIAL_KEY_BODY})$', re.IGNORECASE)
_PROHIBITED_HEADING_RE = re.compile('(?:actual\\s+(?:results?|behaviors?|outputs?)|observed\\s+(?:results?|behaviors?|outputs?)|actual|log\\s+(?:outputs?|entries?|history)|logs?|steps?\\s+to\\s+reproduce|reproduction(?:\\s+steps?)?|repro(?:duction)?(?:\\s+steps?)?|comment\\s+history|comments?|how\\s+to\\s+reproduce|cli\\s+output|notes?|remarks?|show\\s+version|detail\\s+information|实际结果|实际现象|当前结果|实际输出|复现步骤|复现过程|评论|备注|日志|复现|设备回显)', re.IGNORECASE)
_PROHIBITED_LABEL_RE = re.compile(f'(?<![A-Za-z0-9_])(?:{_PROHIBITED_HEADING_RE.pattern})(?:\\s*(?:for|on|/|[-–—]|[\\[(（【])[^:：\\r\\n]*)?\\s*(?:[:：]|$)', re.IGNORECASE)
_MARKDOWN_DECORATION_RE = re.compile('^[*_~`\\s]+|[*_~`\\s]+$')
_ATX_OPEN_RE = re.compile('^#{1,6}\\s+')
_ATX_CLOSE_RE = re.compile('\\s+#{1,6}\\s*$')
_BLOCKQUOTE_RE = re.compile('^>\\s*')
_UNORDERED_LIST_RE = re.compile('^[-+*]\\s+')
_ORDERED_LIST_RE = re.compile('^\\d+[.)、．]\\s*')
_CHINESE_ORDER_RE = re.compile('^(?:[（(][一二三四五六七八九十百千]+[）)]|[一二三四五六七八九十百千]+[、.)）．])\\s*')
_TASK_LIST_RE = re.compile('^\\[(?: |x|X)\\]\\s*')
_MAX_SOURCE_SEMANTIC_CHARS = 1024 * 1024
_MAX_DEFECT_CANDIDATES = 64
_MAX_CANDIDATE_SEMANTIC_CHARS = 512 * 1024
_MAX_TOTAL_CANDIDATE_SEMANTIC_CHARS = 4 * 1024 * 1024
_MAX_CANDIDATE_JSON_BYTES = 2 * 1024 * 1024
_MAX_CANDIDATE_JSON_TOKENS = 100000
_MAX_CANDIDATE_JSON_DEPTH = 64

def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')

def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()

def _source_context_sha256(*, title: str, text: str) -> str:
    return _sha256_json({'title': title, 'text': text})

def _build_source_context_binding(*, source_title: str, source_text: str, source_sha256: str) -> tuple[dict[str, Any] | None, str]:
    try:
        source_bytes = source_text.encode('utf-8', errors='strict')
    except UnicodeEncodeError:
        return (None, 'sealed_source_text_not_utf8')
    if hashlib.sha256(source_bytes).hexdigest() != source_sha256:
        return (None, 'sealed_source_text_sha256_mismatch')
    if source_title:
        title_start = source_text.find(source_title)
        if title_start < 0 or source_text.find(source_title, title_start + 1) >= 0:
            return (None, 'source_title_not_uniquely_located')
        title_locator: dict[str, Any] = {'kind': 'utf8_character_range', 'start': title_start, 'end': title_start + len(source_title)}
    else:
        title_locator = {'kind': 'absent'}
    return ({'schema': SOURCE_CONTEXT_SCHEMA, 'encoding': 'utf-8', 'text_locator': {'kind': 'whole_file'}, 'title_locator': title_locator}, '')

def validate_source_context_binding(*, source_bytes: bytes, source_sha256: str, source_context: Mapping[str, Any], source_content_sha256: str) -> bool:
    if hashlib.sha256(source_bytes).hexdigest() != source_sha256:
        return False
    try:
        source_text = source_bytes.decode('utf-8', errors='strict')
    except UnicodeDecodeError:
        return False
    if len(source_text) > _MAX_SOURCE_SEMANTIC_CHARS:
        return False
    if set(source_context) != {'schema', 'encoding', 'text_locator', 'title_locator'}:
        return False
    if source_context.get('schema') != SOURCE_CONTEXT_SCHEMA or source_context.get('encoding') != 'utf-8' or source_context.get('text_locator') != {'kind': 'whole_file'}:
        return False
    title_locator = source_context.get('title_locator')
    if not isinstance(title_locator, Mapping):
        return False
    if title_locator == {'kind': 'absent'}:
        source_title = ''
    else:
        if set(title_locator) != {'kind', 'start', 'end'}:
            return False
        start = title_locator.get('start')
        end = title_locator.get('end')
        if title_locator.get('kind') != 'utf8_character_range' or isinstance(start, bool) or (not isinstance(start, int)) or isinstance(end, bool) or (not isinstance(end, int)) or (start < 0) or (end <= start) or (end > len(source_text)):
            return False
        source_title = source_text[start:end]
        if source_text.count(source_title) != 1:
            return False
    return source_content_sha256 == _source_context_sha256(title=source_title, text=source_text)

def _candidate_json_bytes(ticket: Mapping[str, Any]) -> bytes:
    stack: list[tuple[Any, int]] = [(ticket, 1)]
    active_containers: set[int] = set()
    tokens = 0
    estimated_bytes = 0
    while stack:
        value, depth = stack.pop()
        if depth > _MAX_CANDIDATE_JSON_DEPTH:
            raise ValueError('candidate JSON depth budget exceeded')
        if isinstance(value, Mapping):
            identity = id(value)
            if identity in active_containers:
                raise ValueError('candidate JSON contains a container cycle')
            active_containers.add(identity)
            tokens += 1 + len(value)
            if tokens > _MAX_CANDIDATE_JSON_TOKENS:
                raise ValueError('candidate JSON token budget exceeded')
            for key, child in value.items():
                if not isinstance(key, str):
                    raise ValueError('candidate JSON object keys must be strings')
                if len(key) > _MAX_CANDIDATE_JSON_BYTES:
                    raise ValueError('candidate JSON byte budget exceeded')
                estimated_bytes += len(key.encode('utf-8')) + 4
                if estimated_bytes > _MAX_CANDIDATE_JSON_BYTES:
                    raise ValueError('candidate JSON byte budget exceeded')
                stack.append((child, depth + 1))
            active_containers.discard(identity)
            continue
        if isinstance(value, Sequence) and (not isinstance(value, (str, bytes, bytearray))):
            identity = id(value)
            if identity in active_containers:
                raise ValueError('candidate JSON contains a container cycle')
            active_containers.add(identity)
            tokens += 1 + len(value)
            if tokens > _MAX_CANDIDATE_JSON_TOKENS:
                raise ValueError('candidate JSON token budget exceeded')
            stack.extend(((child, depth + 1) for child in value))
            active_containers.discard(identity)
            continue
        tokens += 1
        if tokens > _MAX_CANDIDATE_JSON_TOKENS:
            raise ValueError('candidate JSON token budget exceeded')
        if isinstance(value, str):
            if len(value) > _MAX_CANDIDATE_JSON_BYTES:
                raise ValueError('candidate JSON byte budget exceeded')
            estimated_bytes += len(value.encode('utf-8')) + 2
        elif value is None or isinstance(value, bool):
            estimated_bytes += 5
        elif isinstance(value, int):
            if value.bit_length() > 4096:
                raise ValueError('candidate JSON integer budget exceeded')
            estimated_bytes += max(1, value.bit_length() // 3 + 2)
        elif isinstance(value, float):
            if not math.isfinite(value):
                raise ValueError('candidate JSON number is not finite')
            estimated_bytes += 32
        else:
            raise ValueError('candidate contains a non-JSON value')
        if estimated_bytes > _MAX_CANDIDATE_JSON_BYTES:
            raise ValueError('candidate JSON byte budget exceeded')
    try:
        payload = _canonical_json_bytes(ticket)
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise ValueError('candidate cannot be canonically serialized') from exc
    if len(payload) > _MAX_CANDIDATE_JSON_BYTES:
        raise ValueError('candidate JSON byte budget exceeded')
    from cex_core.engine.case_compiler._sealed_io import validate_json_budget
    validate_json_budget(payload, error_type=ValueError, message='candidate JSON structure budget exceeded', max_depth=_MAX_CANDIDATE_JSON_DEPTH, max_tokens=_MAX_CANDIDATE_JSON_TOKENS)
    return payload
_RUNTIME_TICKET_KEYS = {'_resolver_backend_hint', '_ticket_file_sha256', '_ticket_file_sha256_verified', '_ticket_payload_sha256', 'defect_spec_candidate'}

def canonical_ticket_payload_sha256(ticket: Mapping[str, Any]) -> str:
    _candidate_json_bytes(ticket)
    payload = _candidate_json_bytes({str(key): value for key, value in ticket.items() if str(key) not in _RUNTIME_TICKET_KEYS})
    return hashlib.sha256(payload).hexdigest()

def _exact_ticket_number(value: Any) -> str | None:
    match = _EXACT_TICKET_RE.fullmatch(str(value or '').strip())
    return match.group(1) if match else None

def _safe_ticket_id(value: Any) -> str:
    raw = str(value or '').strip()
    if not _EXACT_TICKET_RE.fullmatch(raw):
        return ''
    return raw if raw.isdigit() else raw.upper()

def _semantic_tokens(text: str) -> set[str]:
    tokens = {word.lower() for word in re.findall('[A-Za-z][A-Za-z0-9_-]{1,}', text or '')}
    for segment in re.findall('[\\u4e00-\\u9fff]+', text or ''):
        if len(segment) == 1:
            tokens.add(segment)
        else:
            tokens.update((segment[i:i + 2] for i in range(len(segment) - 1)))
    return tokens

def _normalize_security_markup(value: Any, *, preserve_blocks: bool) -> str:
    text = _ANSI_ESCAPE_RE.sub('', html.unescape(str(value or '')))
    text = ''.join((char for char in text if unicodedata.category(char) != 'Cf'))
    if preserve_blocks:
        text = _HTML_BLOCK_TAG_RE.sub('\n', text)
    text = _HTML_TAG_RE.sub(' ', text)
    text = _MARKDOWN_LINK_RE.sub(lambda match: match.group(1), text)
    return text

def _normalize_credential_markup(value: Any) -> str:
    text = _normalize_security_markup(value, preserve_blocks=False)
    return _DECORATED_CREDENTIAL_KEY_RE.sub(lambda match: f"{match.group('key')}{match.group('sep')}", text)

def is_sensitive_credential_key(value: Any) -> bool:
    normalized = _normalize_credential_markup(value).strip()
    normalized = _MARKDOWN_DECORATION_RE.sub('', normalized).strip()
    normalized = normalized.strip('|[](){}<>"\' ')
    normalized = normalized.removeprefix('--')
    return bool(_SENSITIVE_CREDENTIAL_KEY_RE.fullmatch(normalized))

def _contains_credential_material(value: Any) -> bool:
    normalized = _normalize_credential_markup(value)
    from cex_core.engine.ist_core.security_scrub import scrub_text
    return bool(scrub_text(normalized, scrub_paths=False) != normalized or _PRIVATE_KEY_RE.search(normalized) or _YAML_CREDENTIAL_BLOCK_RE.search(normalized) or _MARKDOWN_TABLE_CREDENTIAL_RE.search(normalized) or _ADJACENT_CREDENTIAL_VALUE_RE.search(normalized) or _AUTH_SCHEME_CREDENTIAL_RE.search(normalized) or _CLI_CREDENTIAL_RE.search(normalized) or _ENV_CREDENTIAL_RE.search(normalized) or _CREDENTIAL_RE.search(normalized))

def contains_credential_material(value: Any) -> bool:
    return _contains_credential_material(value)

def _coverage(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left)

def _dice(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return 2 * len(left & right) / (len(left) + len(right))

def scrub_declaration_text(value: Any, *, limit: int=8000) -> str:
    text = _CONTROL_RE.sub('', _normalize_credential_markup(value))
    if _contains_credential_material(text):
        return '[redacted-credential-field]'[:limit]
    text = _PRIVATE_KEY_RE.sub('[redacted-private-key]', text)
    text = _YAML_CREDENTIAL_BLOCK_RE.sub('[redacted-credential]', text)
    text = _ENV_CREDENTIAL_RE.sub('[redacted-credential]', text)
    text = _CREDENTIAL_RE.sub('[redacted-credential]', text)
    text = _URL_RE.sub('[redacted-url]', text)
    text = _WINDOWS_PATH_RE.sub('[redacted-path]', text)
    text = _UNIX_PATH_RE.sub('[redacted-path]', text)
    text = _REPO_PATH_RE.sub('[redacted-path]', text)
    text = re.sub('[ \\t]+', ' ', text)
    text = re.sub('\\n{3,}', '\n\n', text).strip()
    return text[:limit]

def contains_prohibited_declaration(value: Any) -> bool:
    normalized = _normalize_security_markup(value, preserve_blocks=True)
    for raw_line in normalized.splitlines():
        line = raw_line.strip()
        for _ in range(12):
            previous = line
            for pattern in (_BLOCKQUOTE_RE, _ATX_OPEN_RE, _UNORDERED_LIST_RE, _ORDERED_LIST_RE, _CHINESE_ORDER_RE, _TASK_LIST_RE):
                line = pattern.sub('', line, count=1).strip()
            if line == previous:
                break
        line = _ATX_CLOSE_RE.sub('', line).strip()
        line = _MARKDOWN_DECORATION_RE.sub('', line).strip()
        if not line:
            continue
        if _PROHIBITED_LABEL_RE.search(line):
            return True
        if line.startswith('[') and ']' in line:
            heading = line[1:line.index(']')]
        else:
            heading = re.split('[:：]', line, maxsplit=1)[0]
        heading = _ATX_CLOSE_RE.sub('', heading).strip()
        heading = _MARKDOWN_DECORATION_RE.sub('', heading).strip()
        match = _PROHIBITED_HEADING_RE.match(heading)
        qualifier = heading[match.end():] if match is not None else ''
        if match is not None and (not qualifier or re.fullmatch('\\s*(?:[\\[(（【].*[\\])）】]|[-–—]\\s*.+)', qualifier)):
            return True
    return False

def _candidate_semantic_size(ticket: Mapping[str, Any], *, canonical_payload: bytes | None=None) -> int:
    return len(canonical_payload or _candidate_json_bytes(ticket))
_contains_prohibited_declaration = contains_prohibited_declaration

def _metadata(ticket: Mapping[str, Any]) -> Mapping[str, Any]:
    value = ticket.get('metadata')
    return value if isinstance(value, Mapping) else {}

def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        items: Iterable[Any] = [value]
    elif isinstance(value, Sequence) and (not isinstance(value, (bytes, bytearray))):
        items = value
    else:
        items = []
    return sorted({scrub_declaration_text(item, limit=256) for item in items if str(item or '').strip()})

def _raw_ticket_sha256(ticket: Mapping[str, Any]) -> str:
    supplied = str(ticket.get('_ticket_file_sha256') or '').lower()
    supplied_payload = str(ticket.get('_ticket_payload_sha256') or '').lower()
    if ticket.get('_ticket_file_sha256_verified') is True and _SHA256_RE.fullmatch(supplied) and _SHA256_RE.fullmatch(supplied_payload) and (supplied_payload == canonical_ticket_payload_sha256(ticket)):
        return supplied
    nested = ticket.get('defect_spec_candidate')
    if isinstance(nested, Mapping):
        nested_sha = str(nested.get('ticket_sha256') or '').lower()
        nested_payload_sha = str(nested.get('ticket_payload_sha256') or '').lower()
        if nested.get('ticket_sha256_verified') is True and _SHA256_RE.fullmatch(nested_sha) and _SHA256_RE.fullmatch(nested_payload_sha):
            return nested_sha
    return canonical_ticket_payload_sha256(ticket)

def _candidate_fields(ticket: Mapping[str, Any], *, backend_hint: str='') -> dict[str, Any]:
    _candidate_json_bytes(ticket)
    nested = ticket.get('defect_spec_candidate')
    if isinstance(nested, Mapping):
        base: Mapping[str, Any] = nested
        md: Mapping[str, Any] = nested
    else:
        base = ticket
        md = _metadata(ticket)
    ticket_id = _safe_ticket_id(base.get('ticket_id') or ticket.get('ticket_id') or '')
    raw_backend = str(ticket.get('_resolver_backend_hint') or ticket.get('probe_backend') or backend_hint or base.get('backend') or md.get('backend') or ticket.get('backend') or '').strip().lower()
    backend = raw_backend if raw_backend in _ALLOWED_BACKENDS else ''
    if ticket_id.upper().startswith('STORY-'):
        backend = 'zentao_story'
    title = str(base.get('title') or ticket.get('title') or '')
    description = str(base.get('description') or ticket.get('description') or '')
    metadata = _metadata(ticket)
    raw_doc_type = str(base.get('doc_type') or metadata.get('doc_type') or '').strip().lower()
    doc_type = raw_doc_type if _DOC_TYPE_RE.fullmatch(raw_doc_type) else ''
    product = str(base.get('product') or metadata.get('product') or '')
    status = str(base.get('status') or metadata.get('status') or '')
    affected = base.get('affected_versions')
    if affected is None:
        affected = metadata.get('affected_versions')
    fixed = base.get('fixed_versions')
    if fixed is None:
        fixed = metadata.get('fixed_versions')
    if isinstance(nested, Mapping):
        semantic_text = '\n'.join((title, description))
    else:
        semantic_parts = [title, description, ticket.get('fix_summary'), ticket.get('page_content'), ticket.get('steps_to_reproduce'), metadata.get('module'), metadata.get('product')]
        semantic_text = '\n'.join((str(part or '') for part in semantic_parts))
    declaration_block_reason = ''
    if contains_prohibited_declaration(f'{title}\n{description}'):
        declaration_block_reason = 'description_contains_actual_or_logs'
    elif _contains_credential_material(f'{title}\n{description}'):
        declaration_block_reason = 'declaration_contains_credential_material'
    elif backend not in _ALLOWED_BACKENDS or not ticket_id or (not doc_type) or (not product.strip()) or (not status.strip()):
        declaration_block_reason = 'ticket_identity_metadata_incomplete'
    elif _declaration_is_placeholder_only(description):
        declaration_block_reason = 'declaration_is_placeholder_only'
    elif not description.strip():
        declaration_block_reason = 'description_declaration_unavailable'
    return {'backend': backend, 'ticket_id': ticket_id, 'ticket_number': _exact_ticket_number(ticket_id), 'title': title, 'description': description, 'semantic_text': semantic_text, 'doc_type': doc_type, 'product': product, 'status': status, 'affected_versions': _string_list(affected), 'fixed_versions': _string_list(fixed), 'ticket_sha256': _raw_ticket_sha256(ticket), 'declaration_block_reason': declaration_block_reason}

def _declaration_is_placeholder_only(text: str) -> bool:
    compact = re.sub('\\s+', '', str(text or '').strip())
    if not compact:
        return False
    tokens = re.findall('\\[[^\\]\\n]{1,12}\\]', compact)
    if not tokens or ''.join(tokens) != compact:
        return False
    return all((_PLACEHOLDER_TOKEN_RE.fullmatch(token) for token in tokens))

def build_defect_spec_candidate(ticket: Mapping[str, Any], *, backend_hint: str='') -> dict[str, Any]:
    fields = _candidate_fields(ticket, backend_hint=backend_hint)
    wipe = fields['declaration_block_reason'] in _WIPE_DESCRIPTION_REASONS
    description = '' if wipe else scrub_declaration_text(fields['description'])
    return {'backend': fields['backend'], 'ticket_id': fields['ticket_id'], 'doc_type': fields['doc_type'], 'product': scrub_declaration_text(fields['product'], limit=256), 'status': scrub_declaration_text(fields['status'], limit=128), 'affected_versions': fields['affected_versions'], 'fixed_versions': fields['fixed_versions'], 'title': scrub_declaration_text(fields['title'], limit=1000), 'description': description, 'claimable_declaration': not bool(fields['declaration_block_reason']), 'declaration_block_reason': fields['declaration_block_reason'], 'ticket_sha256': fields['ticket_sha256'], 'ticket_payload_sha256': canonical_ticket_payload_sha256(ticket), 'ticket_sha256_verified': bool(ticket.get('_ticket_file_sha256_verified') is True)}

def _safe_projection(fields: Mapping[str, Any]) -> dict[str, Any]:
    description = ''
    if not fields.get('declaration_block_reason'):
        description = scrub_declaration_text(fields.get('description'))
    return {'authority_group': 'spec', 'backend': fields.get('backend', ''), 'ticket_id': fields.get('ticket_id', ''), 'doc_type': fields.get('doc_type', ''), 'product': scrub_declaration_text(fields.get('product'), limit=256), 'status': scrub_declaration_text(fields.get('status'), limit=128), 'affected_versions': list(fields.get('affected_versions') or []), 'fixed_versions': list(fields.get('fixed_versions') or []), 'title': scrub_declaration_text(fields.get('title'), limit=1000), 'description': description}

def _invalid_receipt(*, ticket_number: str, source_sha256: str, source_content_sha256: str, source_context: dict[str, Any] | None=None, status: str, reason: str, candidates: list[dict[str, Any]] | None=None, lookup: dict[str, Any] | None=None) -> dict[str, Any]:
    return {'schema': RECEIPT_SCHEMA, 'status': status, 'eligible': False, 'authority_group': 'spec', 'reason': reason, 'ticket_number': ticket_number, 'source_sha256': source_sha256, 'source_content_sha256': source_content_sha256, 'source_context': source_context, 'selection': None, 'ticket': None, 'projection': None, 'projection_sha256': None, 'candidates': candidates or [], 'lookup': lookup or {'complete': False, 'errors': [{'backend': '', 'error_code': 'lookup_unbound'}], 'backend_closure': {'schema': 'ist.defect-backend-closure', 'fixed_backends': list(_FIXED_BACKENDS), 'outcomes': []}, 'candidate_set_sha256': ''}}

def _lookup_summary(platform_errors: Sequence[Mapping[str, Any]], *, candidates: Sequence[Mapping[str, Any]], ticket_number: str) -> dict[str, Any]:
    hits: dict[str, list[dict[str, Any]]] = {backend: [] for backend in _FIXED_BACKENDS}
    closure_errors: set[tuple[str, str]] = set()
    for raw in candidates:
        if not isinstance(raw, Mapping):
            continue
        try:
            fields = _candidate_fields(raw)
        except (TypeError, ValueError, OverflowError, RecursionError):
            closure_errors.add(('', 'candidate_unreadable'))
            continue
        probe_backend = str(raw.get('_resolver_backend_hint') or raw.get('probe_backend') or fields.get('backend') or '').strip().lower()
        if probe_backend not in _FIXED_BACKENDS:
            closure_errors.add((probe_backend, 'unknown_backend'))
            continue
        if fields.get('ticket_number') != ticket_number:
            closure_errors.add((probe_backend, 'ticket_identity_mismatch'))
            continue
        nested = raw.get('defect_spec_candidate')
        nested = nested if isinstance(nested, Mapping) else {}
        verified = bool(raw.get('_ticket_file_sha256_verified') is True or nested.get('ticket_sha256_verified') is True)
        payload_sha = str(raw.get('_ticket_payload_sha256') or nested.get('ticket_payload_sha256') or canonical_ticket_payload_sha256(raw)).strip().lower()
        ticket_sha = str(fields.get('ticket_sha256') or '').strip().lower()
        hits[probe_backend].append({'backend': probe_backend, 'status': 'hit', 'ticket_id': str(fields.get('ticket_id') or ''), 'ticket_file_sha256': ticket_sha if verified else None, 'ticket_payload_sha256': payload_sha, 'ticket_sha256_verified': verified})
    misses: dict[str, list[str]] = {backend: [] for backend in _FIXED_BACKENDS}
    for item in platform_errors:
        if not isinstance(item, Mapping):
            continue
        backend = str(item.get('probe_backend') or '').strip().lower()
        code = str(item.get('error_code') or 'unknown').strip().lower()
        if backend not in _FIXED_BACKENDS:
            closure_errors.add((backend, 'unknown_backend'))
            continue
        misses[backend].append(code)
    outcomes: list[dict[str, Any]] = []
    for backend in _FIXED_BACKENDS:
        backend_hits = hits[backend]
        backend_misses = misses[backend]
        if len(backend_hits) == 1 and (not backend_misses):
            outcomes.append(backend_hits[0])
            continue
        if not backend_hits and backend_misses == ['not_found']:
            outcomes.append({'backend': backend, 'status': 'not_found'})
            continue
        if len(backend_hits) > 1:
            code = 'duplicate_backend_hit'
        elif backend_hits and backend_misses:
            code = 'conflicting_backend_outcome'
        elif len(backend_misses) > 1:
            code = 'duplicate_backend_outcome'
        elif backend_misses:
            code = backend_misses[0]
        else:
            code = 'backend_outcome_missing'
        closure_errors.add((backend, code))
        outcomes.append({'backend': backend, 'status': 'unavailable', 'error_code': code})
    closure = {'schema': 'ist.defect-backend-closure', 'fixed_backends': list(_FIXED_BACKENDS), 'outcomes': outcomes}
    errors = sorted(closure_errors)
    return {'complete': not bool(errors), 'errors': [{'backend': backend, 'error_code': code} for backend, code in errors], 'backend_closure': closure, 'candidate_set_sha256': _sha256_json(closure)}

def build_defect_backend_lookup(*, ticket_id: str, candidates: Sequence[Mapping[str, Any]], platform_errors: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return _lookup_summary(platform_errors, candidates=candidates, ticket_number=_exact_ticket_number(ticket_id) or '')

def defect_backend_lookup_is_sealable(lookup: Any, *, ticket_id: str='') -> bool:
    if not isinstance(lookup, Mapping) or set(lookup) != {'complete', 'errors', 'backend_closure', 'candidate_set_sha256'}:
        return False
    closure = lookup.get('backend_closure')
    if lookup.get('complete') is not True or lookup.get('errors') != [] or (not isinstance(closure, Mapping)) or (set(closure) != {'schema', 'fixed_backends', 'outcomes'}) or (not accepts_schema(closure.get('schema'), 'ist.defect-backend-closure')) or (closure.get('fixed_backends') != list(_FIXED_BACKENDS)) or (str(lookup.get('candidate_set_sha256') or '') != _sha256_json(dict(closure))):
        return False
    expected_ticket_number = _exact_ticket_number(ticket_id) if str(ticket_id or '').strip() else None
    if str(ticket_id or '').strip() and expected_ticket_number is None:
        return False
    outcomes = closure.get('outcomes')
    if not isinstance(outcomes, list) or len(outcomes) != len(_FIXED_BACKENDS):
        return False
    for backend, outcome in zip(_FIXED_BACKENDS, outcomes, strict=True):
        if not isinstance(outcome, Mapping) or outcome.get('backend') != backend:
            return False
        if outcome.get('status') == 'not_found':
            if set(outcome) != {'backend', 'status'}:
                return False
            continue
        if outcome.get('status') != 'hit' or set(outcome) != {'backend', 'status', 'ticket_id', 'ticket_file_sha256', 'ticket_payload_sha256', 'ticket_sha256_verified'}:
            return False
        if outcome.get('ticket_sha256_verified') is not True or _exact_ticket_number(outcome.get('ticket_id')) is None or (expected_ticket_number is not None and _exact_ticket_number(outcome.get('ticket_id')) != expected_ticket_number) or (_SHA256_RE.fullmatch(str(outcome.get('ticket_file_sha256') or '')) is None) or (_SHA256_RE.fullmatch(str(outcome.get('ticket_payload_sha256') or '')) is None):
            return False
    return True

def resolve_defect_spec(*, ticket_id: str, source_title: str, source_text: str, source_sha256: str, candidates: Sequence[Mapping[str, Any]], platform_errors: Sequence[Mapping[str, Any]]=(), min_score: float=0.08, min_margin: float=0.04) -> dict[str, Any]:
    ticket_number = _exact_ticket_number(ticket_id) or ''
    source_sha = str(source_sha256 or '').strip().lower()
    source_semantic_chars = len(str(source_title or '')) + len(str(source_text or ''))
    if source_semantic_chars <= _MAX_SOURCE_SEMANTIC_CHARS:
        source_content_sha = _source_context_sha256(title=str(source_title or ''), text=str(source_text or ''))
    else:
        source_content_sha = _sha256_json({'semantic_budget_exceeded': True, 'chars': source_semantic_chars})
    if _SHA256_RE.fullmatch(source_sha) and (str(source_title or '').strip() or str(source_text or '').strip()) and (source_semantic_chars <= _MAX_SOURCE_SEMANTIC_CHARS):
        source_context, source_context_error = _build_source_context_binding(source_title=str(source_title or ''), source_text=str(source_text or ''), source_sha256=source_sha)
    else:
        source_context, source_context_error = (None, '')
    lookup = _lookup_summary(platform_errors, candidates=candidates, ticket_number=ticket_number)
    if not ticket_number:
        return _invalid_receipt(ticket_number='', source_sha256=source_sha, source_content_sha256=source_content_sha, status='invalid_source', reason='ticket_id_not_exact', lookup=lookup)
    if not _SHA256_RE.fullmatch(source_sha):
        return _invalid_receipt(ticket_number=ticket_number, source_sha256=source_sha, source_content_sha256=source_content_sha, status='invalid_source', reason='sealed_source_sha256_required', lookup=lookup)
    if not str(source_title or '').strip() and (not str(source_text or '').strip()):
        return _invalid_receipt(ticket_number=ticket_number, source_sha256=source_sha, source_content_sha256=source_content_sha, status='invalid_source', reason='source_context_unavailable', lookup=lookup)
    if source_semantic_chars > _MAX_SOURCE_SEMANTIC_CHARS:
        return _invalid_receipt(ticket_number=ticket_number, source_sha256=source_sha, source_content_sha256=source_content_sha, status='invalid_source', reason='source_semantic_budget_exceeded', lookup=lookup)
    if source_context_error:
        return _invalid_receipt(ticket_number=ticket_number, source_sha256=source_sha, source_content_sha256=source_content_sha, source_context=None, status='invalid_source', reason=source_context_error, lookup=lookup)
    if len(candidates) > _MAX_DEFECT_CANDIDATES:
        return _invalid_receipt(ticket_number=ticket_number, source_sha256=source_sha, source_content_sha256=source_content_sha, status='unavailable', reason='candidate_count_budget_exceeded', lookup=lookup)
    total_candidate_chars = 0
    for raw in candidates:
        if not isinstance(raw, Mapping):
            continue
        try:
            candidate_payload = _candidate_json_bytes(raw)
        except (TypeError, ValueError, OverflowError, RecursionError):
            return _invalid_receipt(ticket_number=ticket_number, source_sha256=source_sha, source_content_sha256=source_content_sha, status='unavailable', reason='candidate_semantic_budget_exceeded', lookup=lookup)
        candidate_chars = _candidate_semantic_size(raw, canonical_payload=candidate_payload)
        total_candidate_chars += candidate_chars
        if candidate_chars > _MAX_CANDIDATE_SEMANTIC_CHARS or total_candidate_chars > _MAX_TOTAL_CANDIDATE_SEMANTIC_CHARS:
            return _invalid_receipt(ticket_number=ticket_number, source_sha256=source_sha, source_content_sha256=source_content_sha, status='unavailable', reason='candidate_semantic_budget_exceeded', lookup=lookup)
    if not lookup['complete']:
        return _invalid_receipt(ticket_number=ticket_number, source_sha256=source_sha, source_content_sha256=source_content_sha, status='unavailable', reason='backend_lookup_incomplete', lookup=lookup)
    source_title_tokens = _semantic_tokens(source_title)
    source_full_tokens = _semantic_tokens(f'{source_title}\n{source_text}')
    ranked_internal: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for raw in candidates:
        if not isinstance(raw, Mapping):
            continue
        fields = _candidate_fields(raw)
        if fields['ticket_number'] != ticket_number:
            continue
        identity = (str(fields['backend']), str(fields['ticket_id']).upper(), str(fields['ticket_sha256']))
        if identity in seen:
            continue
        seen.add(identity)
        title_score = _coverage(source_title_tokens, _semantic_tokens(str(fields['title'])))
        semantic_score = _dice(source_full_tokens, _semantic_tokens(str(fields['semantic_text'])))
        if source_title_tokens:
            score = 0.75 * title_score + 0.25 * semantic_score
        else:
            score = semantic_score
        ranked_internal.append({'fields': fields, 'score': round(score, 6), 'title_score': round(title_score, 6), 'semantic_score': round(semantic_score, 6)})
    ranked_internal.sort(key=lambda row: (-row['score'], -row['title_score'], -row['semantic_score'], str(row['fields']['backend']), str(row['fields']['ticket_id']), str(row['fields']['ticket_sha256'])))
    candidates_public = [{'backend': row['fields']['backend'], 'ticket_id': row['fields']['ticket_id'], 'ticket_sha256': row['fields']['ticket_sha256'], 'title': scrub_declaration_text(row['fields']['title'], limit=1000), 'claimable_declaration': not bool(row['fields']['declaration_block_reason']), 'declaration_block_reason': row['fields']['declaration_block_reason'], 'score': row['score'], 'title_score': row['title_score'], 'semantic_score': row['semantic_score']} for row in ranked_internal]
    if not ranked_internal:
        return _invalid_receipt(ticket_number=ticket_number, source_sha256=source_sha, source_content_sha256=source_content_sha, status='missing', reason='exact_ticket_id_not_found', candidates=candidates_public, lookup=lookup)
    top = ranked_internal[0]
    runner_score = ranked_internal[1]['score'] if len(ranked_internal) > 1 else 0.0
    margin = round(top['score'] - runner_score, 6)
    if top['score'] < min_score or (len(ranked_internal) > 1 and margin < min_margin):
        return _invalid_receipt(ticket_number=ticket_number, source_sha256=source_sha, source_content_sha256=source_content_sha, status='ambiguous', reason='semantic_score_or_margin_below_threshold', candidates=candidates_public, lookup=lookup)
    fields = top['fields']
    projection = _safe_projection(fields)
    selection_reason = 'unique_full_text_semantic_match'
    if top['title_score'] > 0 and (len(ranked_internal) == 1 or top['title_score'] > ranked_internal[1]['title_score']):
        selection_reason = 'unique_source_title_match'
    selection = {'reason': selection_reason, 'score': top['score'], 'title_score': top['title_score'], 'semantic_score': top['semantic_score'], 'runner_up_score': runner_score, 'margin': margin}
    ticket_binding = {'backend': fields['backend'], 'ticket_id': fields['ticket_id'], 'doc_type': fields['doc_type'], 'product': scrub_declaration_text(fields['product'], limit=256), 'status': scrub_declaration_text(fields['status'], limit=128), 'affected_versions': fields['affected_versions'], 'fixed_versions': fields['fixed_versions'], 'ticket_sha256': fields['ticket_sha256']}
    block_reason = str(fields['declaration_block_reason'] or '')
    return {'schema': RECEIPT_SCHEMA, 'status': 'candidate_only' if block_reason else 'resolved', 'eligible': not bool(block_reason), 'authority_group': 'spec', 'reason': f'selected_ticket_{block_reason}' if block_reason else selection_reason, 'ticket_number': ticket_number, 'source_sha256': source_sha, 'source_content_sha256': source_content_sha, 'source_context': source_context, 'selection': selection, 'ticket': ticket_binding, 'projection': projection, 'projection_sha256': _sha256_json(projection), 'candidates': candidates_public, 'lookup': lookup}

def resolve_defect_spec_from_tool_result(*, tool_result: Mapping[str, Any], ticket_id: str, source_title: str, source_text: str, source_sha256: str) -> dict[str, Any]:
    rows = tool_result.get('results')
    candidates = rows if isinstance(rows, list) else []
    return resolve_defect_spec(ticket_id=ticket_id, source_title=source_title, source_text=source_text, source_sha256=source_sha256, candidates=[row for row in candidates if isinstance(row, Mapping)], platform_errors=[row for row in tool_result.get('platform_errors') or [] if isinstance(row, Mapping)])

def validate_defect_spec_receipt(receipt: Mapping[str, Any], *, ticket_id: str, source_title: str, source_text: str, source_sha256: str, candidates: Sequence[Mapping[str, Any]], platform_errors: Sequence[Mapping[str, Any]]=()) -> dict[str, Any]:
    expected = resolve_defect_spec(ticket_id=ticket_id, source_title=source_title, source_text=source_text, source_sha256=source_sha256, candidates=candidates, platform_errors=platform_errors)
    valid = _canonical_json_bytes(dict(receipt)) == _canonical_json_bytes(expected)
    return {'schema': VALIDATION_SCHEMA, 'valid': valid, 'reason': 'receipt_current' if valid else 'source_or_ticket_drift', 'expected_receipt_sha256': _sha256_json(expected), 'provided_receipt_sha256': _sha256_json(dict(receipt))}
__all__ = ['RECEIPT_SCHEMA', 'SOURCE_CONTEXT_SCHEMA', 'build_defect_spec_candidate', 'build_defect_backend_lookup', 'canonical_ticket_payload_sha256', 'contains_prohibited_declaration', 'defect_backend_lookup_is_sealable', 'resolve_defect_spec', 'resolve_defect_spec_from_tool_result', 'scrub_declaration_text', 'validate_defect_spec_receipt', 'validate_source_context_binding']
