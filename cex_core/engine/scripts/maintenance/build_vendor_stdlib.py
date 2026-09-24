# 生成：tools/extract_engine.py ← InfoTest scripts/maintenance/build_vendor_stdlib.py（sha256 6509ba73200bdb95）。不在这里手改。
from __future__ import annotations
from cex_core.engine._root import _cex_data_path
import argparse
import hashlib
import json
import os
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from cex_core.engine.case_compiler.credential_literals import MirrorCredentialLiteralError, is_credential_argument, is_placeholder_default_literal, matching_credential_literal_count, mirror_credential_literals
from cex_core.engine.case_compiler._sealed_io import open_directory_nofollow, read_regular_at_nofollow, read_regular_nofollow
from cex_core.engine.kms.manual_catalog_store import catalog_alternate_row_enum_is_closed_set, catalog_enum_is_closed_set, catalog_manual_claims, catalog_row_describes_one_parameter, load_coupled_catalog, manual_root as _default_manual_root
ROOT = _cex_data_path('')
PLACEHOLDER = re.compile('[<\\[]([^<>\\[\\]]+)[>\\]]')
ENUM = re.compile('\\{([^{}]+)\\}')
_LEDGER_FILE_RE = re.compile('^[a-z][a-z0-9_-]{0,63}\\.jsonl$')
_FOOTPRINT_MAX_FILES = 8192
_DOMAIN_MAX_TEXT_CHARS = 4096
_ENUM_MAX_MEMBERS = 64
_NUMERIC_ARGUMENT_TYPES = frozenset({'U16', 'U32'})
_TEXT_ARGUMENT_TYPES = frozenset({'STRING', 'XSTRING'})
_VALUE_DOMAIN_SOURCE_RANK = {'xml_limit': 0, 'xml_help': 1, 'manual_table': 2, 'footprint': 3}
_XML_DERIVED_VALUE_DOMAIN_SOURCES = frozenset({'xml_limit', 'xml_help'})
_SENTENCE_SPLIT_RE = re.compile('(?:<br\\s*/?>|。|；|;|\\n)')
_LENGTH_WORDS = ('长度', '字节', '字符', 'byte', 'character')
_ALTERNATION_WORDS = ('或', '|', '以及', ' or ')
_CONDITIONAL_WORDS = ('当', '如果', '若', '除非', '仅当')
_VALUE_STATEMENT_WORDS = ('取值', '范围', '之间')
_DOMAIN_NUMBER = '\\d[\\d,]*'
_RANGE_CORE_RE = re.compile(f'(?P<lo>{_DOMAIN_NUMBER})\\s*(?:到|至|~|～)\\s*(?P<hi>{_DOMAIN_NUMBER})')
_RANGE_WHOLE_RE = re.compile(f'^\\s*(?P<lo>{_DOMAIN_NUMBER})\\s*(?:到|至|~|～|-|—)\\s*(?P<hi>{_DOMAIN_NUMBER})\\s*(?:之间的整数|之间|的整数|)\\s*$')
_LENGTH_RE = re.compile(f'长度不?(?:大于|超过|多于|得超过)\\s*(?P<hi>{_DOMAIN_NUMBER})\\s*个?\\s*(?:字节|字符)')
_XML_LIMIT_RE = re.compile(f'^\\[\\s*(?P<lo>{_DOMAIN_NUMBER})\\s*-\\s*(?P<hi>{_DOMAIN_NUMBER})\\s*\\]$')
_DOMAIN_LITERAL_RE = re.compile('[A-Za-z0-9_.:+-]+')
_ENUM_SEPARATOR_RE = re.compile('\\s*(?:、|｜|\\||，|,|或者|或)\\s*')
_ENUM_LEAD_RE = re.compile('(?:取值(?:必须|只能)?为|取值是|可选值(?:为|是))\\s*(?P<body>.+)$')
_XML_HELP_ALTERNATION_RE = re.compile('(?:[A-Za-z0-9_.:+-]+[ \\t]*\\|[ \\t]*)+[A-Za-z0-9_.:+-]+')
_XML_HELP_MIN_ALTERNATIVES = 3
_XML_HELP_UNION_RE = re.compile('union\\s+by\\s+\\w+\\s*\\(\\s*(?P<sep>[^\\w\\s])\\s*\\)', re.IGNORECASE)
_XML_HELP_UNION_DEFAULT_RE = re.compile('default\\s+(?:is|=)\\s*(?P<body>[A-Za-z0-9]+(?:[^\\w\\s][A-Za-z0-9]+)+)', re.IGNORECASE)
_DEFAULT_RE = re.compile('默认(?:值)?(?:为|是|＝|=)\\s*[“”\\"\'`]?(?P<v>[^“”\\"\'`，。；、\\s]+)[“”\\"\'`]?')

def _xml_sensitive_literal_count(text: str, values: frozenset[str]) -> int:
    from cex_core.engine.sync.command_tree_sync import xml_sensitive_literal_count
    return xml_sensitive_literal_count(text, values)

def _xml_sensitive_literal_redact(text: str, values: frozenset[str]) -> str:
    from cex_core.engine.sync.command_tree_sync import xml_sensitive_literal_replace
    return xml_sensitive_literal_replace(text, values)

def xml_default_value_closure(root: ET.Element) -> frozenset[str]:
    return frozenset({literal for argument in root.iter('arg') if is_credential_argument(name=argument.get('name'), arg_type=argument.get('type'), help_string=argument.get('help_string')) for literal in [str(argument.get('default_value') or '').strip()] if literal and (not is_placeholder_default_literal(literal))})

def build_behavior_ledger_identity(ledger_dir: Path, device_os_build: str) -> tuple[list[dict], dict]:
    expected_build = str(device_os_build or '').strip()
    files = sorted(ledger_dir.glob('*.jsonl'))
    if not files or any((not _LEDGER_FILE_RE.fullmatch(path.name) for path in files)):
        raise ValueError('behavior ledger must contain safely named module jsonl files')
    rows: list[dict] = []
    file_identities: dict[str, dict] = {}
    for path in files:
        raw = path.read_bytes()
        if not raw.strip():
            raise ValueError(f'behavior ledger file is empty: {path.name}')
        parsed: list[dict] = []
        try:
            lines = raw.decode('utf-8').splitlines()
        except UnicodeDecodeError as exc:
            raise ValueError(f'behavior ledger file is not utf-8: {path.name}') from exc
        for line_number, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f'behavior ledger row is not json: {path.name}:{line_number}') from exc
            if not isinstance(row, dict):
                raise ValueError(f'behavior ledger row is not an object: {path.name}:{line_number}')
            row_build = str(row.get('device_os_build') or row.get('build') or '').strip()
            if not str(row.get('command') or '').strip() or not str(row.get('status') or '').strip() or (not row_build) or (not row_build.endswith(f'_{expected_build}') and row_build != expected_build):
                raise ValueError(f'behavior ledger row identity mismatch: {path.name}:{line_number}')
            parsed.append({**row, '_ledger_source_file': path.name, '_ledger_line_number': line_number})
        if not parsed:
            raise ValueError(f'behavior ledger file has no records: {path.name}')
        rows.extend(parsed)
        file_identities[path.name] = {'entry_count': len(parsed), 'sha256': hashlib.sha256(raw).hexdigest()}
    return (rows, {'schema': 'ist.behavior-ledger.identity', 'device_os_build': expected_build, 'entry_count': len(rows), 'files': file_identities})

def _register(heads: dict, head: str, src: str, pmax: int, credential_values: frozenset[str], suppressed_heads: set[str] | None=None, args: list[dict] | None=None, results: list[dict] | None=None) -> None:
    if matching_credential_literal_count(head, credential_values):
        if suppressed_heads is not None:
            suppressed_heads.add(head)
        return
    e = heads.get(head)
    if e is None:
        heads[head] = {'src': src, 'pmax': pmax}
        if args is not None:
            heads[head]['args'] = args
        if results:
            heads[head]['results'] = results
    else:
        e['pmax'] = max(e['pmax'], pmax)
        if args is not None and e.get('args') != args:
            variants = e.setdefault('arg_variants', [])
            if args not in variants and args != e.get('args'):
                variants.append(args)
        if results:
            merged_results = e.setdefault('results', [])
            for result in results:
                if result not in merged_results:
                    merged_results.append(result)
MANUAL_CATALOG_FAMILIES = ('cli', 'app')

def resolve_manual_catalog_version(version: str, *, root: Path | None=None) -> str:
    base = Path(root) if root is not None else _default_manual_root()
    ver = str(version or '').strip()
    if not ver:
        raise ValueError('manual catalog version resolution requires a version')
    try:
        names = sorted((entry.name for entry in base.iterdir() if entry.is_dir() and (entry.name == ver or entry.name.startswith(f'{ver}.'))))
    except OSError:
        names = []
    coupled = [name for name in names if any((load_coupled_catalog(name, family, root=base)[1]['status'] == 'ok' for family in MANUAL_CATALOG_FAMILIES))]
    if not coupled:
        raise ValueError(f'manual_catalog_version_unresolved: {ver} 在 manual 根下没有任何耦合 catalog 的版本目录（扫描到 {names}）')
    if len(coupled) > 1:
        raise ValueError(f'manual_catalog_version_ambiguous: {ver} 命中多个耦合 catalog 的版本目录 {coupled}，拒绝猜测')
    return coupled[0]

def catalog_value_domain_index(catalogs: dict[str, dict]) -> dict[str, list[dict]]:
    index: dict[str, list[dict]] = {}
    for catalog in catalogs.values():
        params_by_head: dict[str, list[str]] = {}
        for signature in catalog.get('signatures') or []:
            if not isinstance(signature, dict):
                continue
            tokens = signature.get('head_tokens') or []
            head_key = re.sub('\\s+', ' ', ' '.join((str(token) for token in tokens)).strip().lower())
            if not head_key or head_key in params_by_head:
                continue
            params_by_head[head_key] = [str(param.get('name') or '').strip() for param in signature.get('params') or [] if isinstance(param, dict)]
        for row in catalog.get('value_domains') or []:
            if not isinstance(row, dict):
                continue
            head = re.sub('\\s+', ' ', str(row.get('head') or '').strip().lower())
            if not head:
                continue
            param = str(row.get('param') or '').strip()
            names = params_by_head.get(head) or []
            matches = [position for position, name in enumerate(names) if name.casefold() == param.casefold()]
            index.setdefault(head, []).append({'param': param, 'param_index': matches[0] if len(matches) == 1 else None, 'param_count': len(names), 'enums': row.get('enums') or [], 'desc': str(row.get('desc') or ''), 'src': str(row.get('src') or '').strip()})
    return index

def _catalog_enum_members(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    members = [str(item).strip() for item in values if str(item).strip()]
    if len(members) < 2 or len(members) > _ENUM_MAX_MEMBERS:
        return []
    if not all((_DOMAIN_LITERAL_RE.fullmatch(member) for member in members)):
        return []
    if any((re.fullmatch('\\d+\\s*-\\s*\\d+', member) for member in members)):
        return []
    if len({member.casefold() for member in members}) != len(members):
        return []
    return members

def _load_manual_catalog_side(version: str, manual_version: str | None, *, root: Path | None=None) -> tuple[str, dict[str, dict], dict[str, list[dict]], dict[str, str]]:
    base = Path(root) if root is not None else _default_manual_root()
    resolved = str(manual_version or '').strip() or resolve_manual_catalog_version(version, root=base)
    catalogs: dict[str, dict] = {}
    statuses: dict[str, str] = {}
    identities: dict[str, dict] = {}
    for family in MANUAL_CATALOG_FAMILIES:
        catalog, verdict = load_coupled_catalog(resolved, family, root=base)
        status = str(verdict.get('status') or '')
        statuses[family] = status
        if status == 'ok':
            assert catalog is not None
            catalogs[family] = catalog
            identities[family] = {'catalog_sha256': str(verdict.get('catalog_sha256') or ''), 'md_sha256': str(verdict.get('md_sha256') or '')}
        elif status == 'md_missing':
            continue
        else:
            raise ValueError(f"manual catalog 未生效（{status}: {family}@{resolved}），拒绝生成 vendor 投影: {str(verdict.get('detail') or '')}")
    if not catalogs:
        raise ValueError(f"manual catalog 未生效（no_coupled_family: cli={statuses.get('cli')}, app={statuses.get('app')}@{resolved}），拒绝生成 vendor 投影")
    claims: dict[str, dict] = {}
    for family in MANUAL_CATALOG_FAMILIES:
        catalog = catalogs.get(family)
        if catalog is None:
            continue
        for head, entry in catalog_manual_claims(catalog).items():
            claims.setdefault(head, entry)
    return (resolved, claims, catalog_value_domain_index(catalogs), statuses, identities)

def _domain_int(text: str) -> int | None:
    try:
        return int(str(text).replace(',', ''))
    except (TypeError, ValueError):
        return None

def _domain_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_SPLIT_RE.split(str(text or '')) if s.strip()]

def _domain_mentions(text: str, words: tuple[str, ...]) -> bool:
    folded = text.casefold()
    return any((word in folded for word in words))

def parse_enum_alternatives(body: str) -> list[str]:
    text = str(body or '').strip().rstrip('。.;；,，')
    if not text:
        return []
    normalized = _ENUM_SEPARATOR_RE.sub('\x00', text)
    parts = [part.strip().strip('"“”\'`') for part in normalized.split('\x00')]
    parts = [part for part in parts if part]
    if len(parts) < 2 or len(parts) > _ENUM_MAX_MEMBERS:
        return []
    if not all((_DOMAIN_LITERAL_RE.fullmatch(part) for part in parts)):
        return []
    if any((re.fullmatch('\\d+\\s*-\\s*\\d+', part) for part in parts)):
        return []
    if len({part.casefold() for part in parts}) != len(parts):
        return []
    return parts

def parse_xml_help_alternatives(help_text: str) -> list[str]:
    text = str(help_text or '')
    best: list[str] = []
    for run in _XML_HELP_ALTERNATION_RE.findall(text):
        members = [part.strip().rstrip('.') for part in run.split('|')]
        members = [part for part in members if part]
        if len(members) < _XML_HELP_MIN_ALTERNATIVES:
            continue
        if len(members) > _ENUM_MAX_MEMBERS:
            continue
        if not all((_DOMAIN_LITERAL_RE.fullmatch(part) for part in members)):
            continue
        if len({part.casefold() for part in members}) != len(members):
            continue
        if len(members) > len(best):
            best = members
    return best

def parse_xml_help_union_separator(help_text: str, members: list[str]) -> str:
    text = str(help_text or '')
    if not text.strip():
        return ''
    folded_members = {str(item).casefold() for item in members if str(item)}
    if not folded_members:
        return ''
    match = _XML_HELP_UNION_RE.search(text)
    if match is not None:
        return match.group('sep')
    normalized = re.sub('\\\\[nrt]', ' ', text)
    for candidate in _XML_HELP_UNION_DEFAULT_RE.finditer(normalized):
        body = candidate.group('body')
        separators = {char for char in body if not char.isalnum()}
        if len(separators) != 1:
            continue
        separator = separators.pop()
        parts = [part.casefold() for part in body.split(separator) if part]
        if len(parts) < 2:
            continue
        if len(set(parts)) != len(parts):
            continue
        if all((part.isdigit() for part in parts)):
            continue
        if all((part in folded_members for part in parts)):
            return separator
    return ''

def help_witnesses_any(help_text: str, values: list[str]) -> bool:
    text = str(help_text or '')
    if not text.strip():
        return True
    folded = re.sub('\\\\[nrt]', ' ', text).casefold()
    for value in values:
        literal = str(value or '').casefold()
        if not literal:
            continue
        if re.search(f'(?<![a-z0-9]){re.escape(literal)}(?![a-z0-9])', folded) is not None:
            return True
    return False

def parse_xml_argument_limit(limit: str, arg_type: str) -> dict:
    match = _XML_LIMIT_RE.match(str(limit or '').strip())
    if match is None:
        return {}
    low = _domain_int(match.group('lo'))
    high = _domain_int(match.group('hi'))
    if low is None or high is None or low > high:
        return {}
    if arg_type in _NUMERIC_ARGUMENT_TYPES:
        return {'range': {'min': low, 'max': high}}
    if arg_type == 'STRING':
        return {'length': {'min': low, 'max': high}}
    return {}

def parse_prose_value_domain(text: str, *, whole_string: bool) -> dict:
    out: dict = {}
    raw = str(text or '').strip()
    if not raw or len(raw) > _DOMAIN_MAX_TEXT_CHARS:
        return out
    if whole_string:
        match = _RANGE_WHOLE_RE.match(raw)
        if match is not None and (not _domain_mentions(raw, _LENGTH_WORDS)):
            low = _domain_int(match.group('lo'))
            high = _domain_int(match.group('hi'))
            if low is not None and high is not None and (low <= high):
                return {'range': {'min': low, 'max': high}}
        members = parse_enum_alternatives(raw)
        if members:
            return {'enum': members}
    candidates: list[tuple[int, int]] = []
    emittable: list[tuple[int, int]] = []
    for sentence in _domain_sentences(raw):
        if _domain_mentions(sentence, _LENGTH_WORDS):
            continue
        if not _domain_mentions(sentence, _VALUE_STATEMENT_WORDS):
            continue
        publishable = not (_domain_mentions(sentence, _ALTERNATION_WORDS) or _domain_mentions(sentence, _CONDITIONAL_WORDS))
        for match in _RANGE_CORE_RE.finditer(sentence):
            low = _domain_int(match.group('lo'))
            high = _domain_int(match.group('hi'))
            if low is None or high is None or low > high:
                continue
            if (low, high) not in candidates:
                candidates.append((low, high))
            if publishable and (low, high) not in emittable:
                emittable.append((low, high))
    if len(candidates) == 1 and emittable:
        out['range'] = {'min': emittable[0][0], 'max': emittable[0][1]}
    for sentence in _domain_sentences(raw):
        if 'length' not in out:
            match = _LENGTH_RE.search(sentence)
            if match is not None:
                high = _domain_int(match.group('hi'))
                if high is not None:
                    out['length'] = {'min': 0, 'max': high}
        if 'enum' not in out:
            match = _ENUM_LEAD_RE.search(sentence)
            if match is not None:
                members = parse_enum_alternatives(match.group('body'))
                if members:
                    out['enum'] = members
        if 'default' not in out:
            match = _DEFAULT_RE.search(sentence)
            if match is not None:
                value = match.group('v').strip().strip('"“”\'`')
                if value and _DOMAIN_LITERAL_RE.fullmatch(value):
                    out['default'] = value
    return out

def value_domain_compatible_with_type(domain: dict, arg_type: str) -> dict:
    kept = dict(domain)
    if 'range' in kept and str(arg_type) not in _NUMERIC_ARGUMENT_TYPES:
        kept.pop('range')
    if 'length' in kept and str(arg_type) not in _TEXT_ARGUMENT_TYPES:
        kept.pop('length')
    members = kept.get('enum')
    if isinstance(members, (list, tuple, set)) and str(arg_type) in _NUMERIC_ARGUMENT_TYPES and (not all((str(m).strip().lstrip('+-').isdigit() for m in members))):
        kept.pop('enum')
    return kept

def footprint_parameter_tables(footprint_dir: Path) -> tuple[dict[str, dict], dict]:
    tables: dict[str, dict] = {}
    stats = {'files': 0, 'commands': 0, 'parameters': 0}
    try:
        directory_fd = open_directory_nofollow(footprint_dir, error_type=ValueError, invalid_message='footprint directory path is invalid', unavailable_message='footprint directory is unavailable')
    except (OSError, ValueError):
        return (tables, stats)
    try:
        names: list[str] = []
        enumerated = 0
        with os.scandir(directory_fd) as entries:
            for entry in entries:
                enumerated += 1
                if enumerated > _FOOTPRINT_MAX_FILES:
                    raise ValueError('footprint directory entry count exceeds the parser budget')
                if entry.name.endswith('.json'):
                    names.append(entry.name)
        names.sort()
        total_bytes = 0
        for name in names:
            raw = read_regular_at_nofollow(directory_fd, name, error_type=ValueError, open_message='footprint node is unavailable', bounds_message='footprint node exceeds per-file size budget', changed_message='footprint node changed while reading', max_bytes=4 * 1024 * 1024, min_bytes=1)
            assert isinstance(raw, bytes)
            total_bytes += len(raw)
            if total_bytes > 256 * 1024 * 1024:
                raise ValueError('footprint corpus exceeds the total parser budget')
            try:
                payload = json.loads(raw.decode('utf-8'))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if not isinstance(payload, dict):
                continue
            stats['files'] += 1
            feature_id = str(payload.get('feature_id') or name)
            commands = (payload.get('cli') or {} if isinstance(payload.get('cli'), dict) else {}).get('commands')
            for command in commands if isinstance(commands, list) else []:
                if not isinstance(command, dict):
                    continue
                text = str(command.get('catalog_head') or command.get('command') or '')
                if not text:
                    continue
                stats['commands'] += 1
                head = re.sub('\\{[^}]*\\}', ' ', text)
                head = re.sub('[<\\[][^<>\\[\\]]*[>\\]]', ' ', head)
                head = re.sub('\\s+', ' ', head).strip().lower().rstrip('_ ').strip()
                params = [item for item in command.get('parameters') or [] if isinstance(item, dict)]
                stats['parameters'] += len(params)
                if not head or head in tables or (not params):
                    continue
                tables[head] = {'placeholders': [token.strip() for token in PLACEHOLDER.findall(text)], 'params': params, 'src': f"footprint:{feature_id}:{str(command.get('fact_key') or '')}"}
    finally:
        os.close(directory_fd)
    return (tables, stats)

def _append_claim(bucket: dict, kind: str, payload: dict, source: str, locator: str) -> None:
    claim = {**payload, 'source': source, 'locator': locator}
    claims = bucket.setdefault(kind, [])
    if claim not in claims:
        claims.append(claim)

def _claims_from_domain(bucket: dict, domain: dict, source: str, locator: str) -> None:
    for kind in ('enum', 'range', 'length', 'default'):
        if kind not in domain:
            continue
        value = domain[kind]
        if kind == 'enum':
            _append_claim(bucket, kind, {'values': list(value)}, source, locator)
        elif kind == 'default':
            _append_claim(bucket, kind, {'value': str(value)}, source, locator)
        else:
            _append_claim(bucket, kind, {'min': int(value['min']), 'max': int(value['max'])}, source, locator)

def _sorted_claims(bucket: dict) -> dict:
    ordered: dict = {}
    for kind in ('enum', 'union', 'range', 'length', 'default'):
        claims = bucket.get(kind)
        if not claims:
            continue
        ordered[kind] = sorted(claims, key=lambda claim: (_VALUE_DOMAIN_SOURCE_RANK.get(str(claim.get('source')), 9), str(claim.get('locator') or '')))
    return ordered

def merge_argument_value_domains(headers: dict[str, dict], manual_catalog_domains: dict[str, list[dict]], footprint_tables: dict[str, dict], credential_values: frozenset[str], xml_sensitive_values: frozenset[str]=frozenset(), help_witness: dict[str, dict[int, list[str]]] | None=None) -> dict:
    stats: Counter[str] = Counter()
    witness = help_witness or {}
    for head, entry in headers.items():
        signatures = [entry.get('args') or [], *(entry.get('arg_variants') or [])]
        signatures = [item for item in signatures if isinstance(item, list) and item]
        if not signatures:
            continue
        catalog_rows = manual_catalog_domains.get(head) or []
        footprint = footprint_tables.get(head) or {}
        for signature in signatures:
            arity = len(signature)
            buckets: dict[int, dict] = {}
            for argument in signature:
                if not isinstance(argument, dict):
                    continue
                position = int(argument.get('position') or 0)
                arg_type = str(argument.get('type') or '')
                if arg_type == 'REDACTED_SENSITIVE':
                    continue
                domain = parse_xml_argument_limit(str(argument.get('limit') or ''), arg_type)
                if domain:
                    stats['xml_limit_args'] += 1
                    _claims_from_domain(buckets.setdefault(position, {}), domain, 'xml_limit', f"{entry.get('src', '')}/arguments/arg:{position}/limit")
            for row in catalog_rows:
                param = str(row.get('param') or '').strip().casefold()
                raw_locator = str(row.get('src') or '').strip()
                locator = f'manual:{raw_locator}' if raw_locator else ''
                raw_param = str(row.get('param') or '')
                desc_text = str(row.get('desc') or '')
                members = _catalog_enum_members(row.get('enums') or [])
                if not catalog_row_describes_one_parameter(raw_param):
                    if members and catalog_alternate_row_enum_is_closed_set(raw_param, members, desc_text):
                        domain = {'enum': members}
                    else:
                        stats['manual_catalog_claims_skipped'] += 1
                        continue
                else:
                    domain = parse_prose_value_domain(desc_text, whole_string=False)
                    if members and catalog_enum_is_closed_set(raw_param, members, desc_text):
                        domain = {**domain, 'enum': members}
                if not param or not locator or (not domain):
                    stats['manual_catalog_claims_skipped'] += 1
                    continue
                named = [argument for argument in signature if isinstance(argument, dict) and str(argument.get('name') or '').strip().casefold() == param]
                signature_has_names = any((str(argument.get('name') or '').strip() for argument in signature if isinstance(argument, dict)))
                if signature_has_names:
                    if len(named) != 1:
                        stats['manual_catalog_claims_skipped'] += 1
                        continue
                    argument = named[0]
                else:
                    param_index = row.get('param_index')
                    param_count = int(row.get('param_count') or 0)
                    if param_index is None or param_count != arity or (not 0 <= int(param_index) < len(signature)):
                        stats['manual_catalog_claims_skipped'] += 1
                        continue
                    argument = signature[int(param_index)]
                if not isinstance(argument, dict):
                    stats['manual_catalog_claims_skipped'] += 1
                    continue
                if str(argument.get('type') or '') == 'REDACTED_SENSITIVE':
                    stats['manual_catalog_claims_skipped'] += 1
                    continue
                domain = value_domain_compatible_with_type(domain, str(argument.get('type') or ''))
                if not domain:
                    stats['manual_catalog_claims_skipped'] += 1
                    continue
                stats['manual_catalog_args'] += 1
                _claims_from_domain(buckets.setdefault(int(argument.get('position') or 0), {}), domain, 'manual_table', locator)
            if footprint and len(footprint.get('placeholders') or []) == arity:
                names = [str(item.get('name') or '') for item in footprint['params']]
                if names == footprint['placeholders']:
                    stats['footprint_aligned_signatures'] += 1
                    for index, item in enumerate(footprint['params'], start=1):
                        argument = signature[index - 1]
                        if str(argument.get('type') or '') == 'REDACTED_SENSITIVE':
                            continue
                        domain = value_domain_compatible_with_type(parse_prose_value_domain(str(item.get('value_range') or ''), whole_string=True), str(argument.get('type') or ''))
                        declared = str(item.get('default') or '').strip().strip('"\'')
                        if declared and _DOMAIN_LITERAL_RE.fullmatch(declared):
                            domain = {**domain, 'default': declared}
                        if domain:
                            stats['footprint_args'] += 1
                            _claims_from_domain(buckets.setdefault(index, {}), domain, 'footprint', f"{footprint.get('src', 'footprint:')}:{names[index - 1]}")
                else:
                    stats['footprint_name_mismatch_signatures'] += 1
            elif footprint:
                stats['footprint_arity_mismatch_signatures'] += 1
            head_witness = witness.get(head) or {}
            for argument in signature:
                if not isinstance(argument, dict):
                    continue
                position = int(argument.get('position') or 0)
                helps = head_witness.get(position) or []
                bucket = buckets.get(position)
                if bucket:
                    kept = []
                    for claim in bucket.get('enum') or []:
                        members = [str(item) for item in claim.get('values') or []]
                        if helps and (not any((help_witnesses_any(text, members) for text in helps))):
                            stats['enum_claims_without_help_witness'] += 1
                            continue
                        kept.append(claim)
                    if kept:
                        bucket['enum'] = kept
                    else:
                        bucket.pop('enum', None)
                if str(argument.get('type') or '') != 'REDACTED_SENSITIVE':
                    for text in helps:
                        members = parse_xml_help_alternatives(text)
                        if not members:
                            continue
                        stats['xml_help_args'] += 1
                        _append_claim(buckets.setdefault(position, {}), 'enum', {'values': members}, 'xml_help', f"{entry.get('src', '')}/arguments/arg:{position}/help")
                    bucket = buckets.get(position)
                    declared_members = [str(item) for claim in (bucket or {}).get('enum') or [] for item in claim.get('values') or []]
                    for text in helps:
                        separator = parse_xml_help_union_separator(text, declared_members)
                        if not separator:
                            continue
                        stats['xml_help_union_args'] += 1
                        _append_claim(buckets.setdefault(position, {}), 'union', {'separator': separator}, 'xml_help', f"{entry.get('src', '')}/arguments/arg:{position}/help")
                    bucket = buckets.get(position)
                if not bucket:
                    continue
                ordered = _sorted_claims(bucket)
                serialized = json.dumps(ordered, ensure_ascii=False, sort_keys=True)
                if matching_credential_literal_count(serialized, credential_values):
                    stats['suppressed_credential_value_domains'] += 1
                    continue
                literals = [str(member) for claim in ordered.get('enum') or [] if str(claim.get('source')) in _XML_DERIVED_VALUE_DOMAIN_SOURCES for member in claim.get('values') or []] + [str(claim.get('value') or '') for claim in ordered.get('default') or [] if str(claim.get('source')) in _XML_DERIVED_VALUE_DOMAIN_SOURCES]
                if any((_xml_sensitive_literal_count(literal, xml_sensitive_values) for literal in literals)):
                    stats['suppressed_xml_default_value_domains'] += 1
                    continue
                if ordered:
                    argument['value_domain'] = ordered
                    stats['args_with_value_domain'] += 1
                    for kind in ordered:
                        stats[f'kind_{kind}'] += 1
    return dict(stats)

def _safe_xml_text(value: str, credential_values: frozenset[str], xml_sensitive_values: frozenset[str], redaction_counter: list[int]) -> str:
    text = str(value or '').strip()
    if not text:
        return text
    if matching_credential_literal_count(text, credential_values):
        redaction_counter[0] += 1
        return '[redacted by credential closure]'
    if _xml_sensitive_literal_count(text, xml_sensitive_values):
        redaction_counter[0] += 1
        return _xml_sensitive_literal_redact(text, xml_sensitive_values)
    return text

def _assert_headers_have_no_xml_sensitive_literal(headers: dict[str, dict], xml_sensitive_values: frozenset[str]) -> None:
    hit_count = 0
    for head, entry in headers.items():
        hit_count += _xml_sensitive_literal_count(head, xml_sensitive_values)
        for result in entry.get('results') or []:
            if isinstance(result, dict):
                for key in ('text', 'locator', 'operator'):
                    value = result.get(key)
                    if isinstance(value, str):
                        hit_count += _xml_sensitive_literal_count(value, xml_sensitive_values)
        variants = [entry.get('args') or [], *(entry.get('arg_variants') or [])]
        for variant in variants:
            for argument in variant:
                for key in ('type', 'name', 'length', 'limit', 'help'):
                    value = argument.get(key)
                    if isinstance(value, str):
                        hit_count += _xml_sensitive_literal_count(value, xml_sensitive_values)
                domain = argument.get('value_domain') or {}
                for claim in domain.get('enum') or []:
                    if str(claim.get('source')) not in _XML_DERIVED_VALUE_DOMAIN_SOURCES:
                        continue
                    for member in claim.get('values') or []:
                        hit_count += _xml_sensitive_literal_count(str(member), xml_sensitive_values)
                for claim in domain.get('default') or []:
                    if str(claim.get('source')) not in _XML_DERIVED_VALUE_DOMAIN_SOURCES:
                        continue
                    hit_count += _xml_sensitive_literal_count(str(claim.get('value') or ''), xml_sensitive_values)
    if hit_count:
        raise RuntimeError(f'vendor XML sensitive-literal gate rejected projection (matched_literal_count={hit_count})')

def parse_vendor_xml(xml_path: Path, device_build: str, credential_values: frozenset[str], *, xml_bytes: bytes | None=None, help_witness: dict[str, dict[int, list[str]]] | None=None) -> tuple[dict[str, dict], dict]:
    if not credential_values:
        raise ValueError('credential closure is empty; refusing to parse vendor XML')
    raw = xml_bytes
    if raw is None:
        raw = read_regular_nofollow(xml_path, error_type=ValueError, invalid_message='vendor XML path is invalid', directory_message='vendor XML directory is unavailable', open_message='vendor XML is unavailable', bounds_message='vendor XML exceeds size budget', changed_message='vendor XML changed while reading', max_bytes=16 * 1024 * 1024, min_bytes=1)
        assert isinstance(raw, bytes)
    from cex_core.engine.sync.command_tree_sync import preflight_command_tree_xml
    preflight_command_tree_xml(raw, max_bytes=16 * 1024 * 1024, error_type=ValueError)
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ValueError('vendor XML cannot be parsed') from exc
    xml_sensitive_values = xml_default_value_closure(root)
    heads: dict[str, dict] = {}
    suppressed_heads: set[str] = set()
    arg_types: Counter[str] = Counter()
    redactions = [0]
    item_count = arg_count = default_count = missing_type = 0
    result_declaration_count = 0
    node_count = 1

    def walk(node: ET.Element, words: list[str], xml_path_parts: list[str], depth: int) -> None:
        nonlocal item_count, arg_count, default_count, missing_type, node_count
        nonlocal result_declaration_count
        for child in node:
            node_count += 1
            if node_count > 250000 or depth + 1 > 96:
                raise ValueError('vendor XML structure exceeds the parser budget')
            if child.tag in {'scope', 'menu'}:
                name = str(child.get('name') or '').strip()
                next_words = words + ([name.lower()] if name else [])
                label = name or str(child.get('type') or child.tag)
                walk(child, next_words, xml_path_parts + [label], depth + 1)
                continue
            if child.tag != 'item':
                continue
            item_count += 1
            item_name = re.sub('\\s+', ' ', str(child.get('name') or '').strip().lower())
            head = ' '.join(words + ([item_name] if item_name else [])).strip()
            args_node = child.find('arguments')
            arg_schema: list[dict] = []
            if args_node is not None:
                for pos, arg in enumerate(args_node.findall('arg'), start=1):
                    arg_count += 1
                    typ = str(arg.get('type') or '').strip()
                    arg_types[typ or '<missing>'] += 1
                    missing_type += not bool(typ)
                    default_count += bool(str(arg.get('default_value') or '').strip())
                    schema = {'position': pos, 'type': typ, 'optional': str(arg.get('optional') or '').strip().upper() == 'YES'}
                    if help_witness is not None:
                        witness_help = str(arg.get('help_string') or '')
                        if witness_help:
                            bucket = help_witness.setdefault(head, {}).setdefault(pos, [])
                            if witness_help not in bucket:
                                bucket.append(witness_help)
                    if is_credential_argument(name=arg.get('name'), arg_type=typ, help_string=arg.get('help_string')):
                        schema['type'] = 'REDACTED_SENSITIVE'
                        schema['executable'] = False
                        redactions[0] += 1
                    else:
                        for attr in ('name', 'length', 'limit', 'help_string'):
                            safe = _safe_xml_text(str(arg.get(attr) or ''), credential_values, xml_sensitive_values, redactions)
                            if safe:
                                schema['help' if attr == 'help_string' else attr] = safe
                    arg_schema.append(schema)
            src_path = '/'.join(xml_path_parts + ([item_name] if item_name else []))
            result_declarations: list[dict] = []
            results_node = child.find('results')
            if results_node is not None:
                for result_index, result in enumerate(results_node.findall('result'), start=1):
                    raw_result = ''.join(result.itertext()).strip()
                    if not raw_result:
                        continue
                    if set(result.attrib) - {'operator'} or list(result):
                        raise ValueError('vendor XML result declaration has unsupported structure')
                    safe_result = _safe_xml_text(raw_result, credential_values, xml_sensitive_values, redactions)
                    if safe_result != raw_result:
                        raise ValueError('vendor XML result declaration intersects credential closure')
                    declaration = {'text': safe_result, 'locator': f'vendor_xml:{device_build}:{src_path}/results/result:{result_index}'}
                    operator = _safe_xml_text(str(result.get('operator') or ''), credential_values, xml_sensitive_values, redactions)
                    if operator:
                        declaration['operator'] = operator
                    result_declarations.append(declaration)
                    result_declaration_count += 1
            if _xml_sensitive_literal_count(head, xml_sensitive_values):
                suppressed_heads.add(head)
                continue
            _register(heads, head, f'vendor_xml:{device_build}:{src_path}', len(arg_schema), credential_values, suppressed_heads, args=arg_schema, results=result_declarations)
    walk(root, [], [], 1)
    _assert_headers_have_no_xml_sensitive_literal(heads, xml_sensitive_values)
    schema_variants = sum((len(v.get('arg_variants') or []) for v in heads.values()))
    stats = {'items': item_count, 'arguments': arg_count, 'unique_heads': len(heads), 'argument_types': dict(sorted(arg_types.items())), 'missing_argument_type': missing_type, 'default_values_omitted': default_count, 'credential_fields_redacted': redactions[0], 'suppressed_known_credential_heads': len(suppressed_heads), 'duplicate_head_schema_variants': schema_variants, 'result_declarations': result_declaration_count, 'parameter_schema_coverage': round((arg_count - missing_type) / arg_count, 6) if arg_count else 1.0}
    return (heads, stats)

def diff_vendor_stdlibs(old_payload: dict, new_payload: dict) -> dict:
    old_headers = old_payload.get('headers') or {}
    new_headers = new_payload.get('headers') or {}
    old_names = set(old_headers)
    new_names = set(new_headers)
    changed: list[dict] = []
    for head in sorted(old_names & new_names):
        old_schema = {'pmax': old_headers[head].get('pmax'), 'args': old_headers[head].get('args') or [], 'arg_variants': old_headers[head].get('arg_variants') or []}
        new_schema = {'pmax': new_headers[head].get('pmax'), 'args': new_headers[head].get('args') or [], 'arg_variants': new_headers[head].get('arg_variants') or []}
        if old_schema != new_schema:
            changed.append({'head': head, 'from': old_schema, 'to': new_schema})
    return {'schema': 'ist.vendor_stdlib.diff', 'from': {'version': str(old_payload.get('version') or ''), 'device_os_build': str(old_payload.get('device_os_build') or ''), 'source_sha256': str((old_payload.get('source') or {}).get('sha256') or '')}, 'to': {'version': str(new_payload.get('version') or ''), 'device_os_build': str(new_payload.get('device_os_build') or ''), 'source_sha256': str((new_payload.get('source') or {}).get('sha256') or '')}, 'added_headers': sorted(new_names - old_names), 'removed_headers': sorted(old_names - new_names), 'changed_argument_schemas': changed, 'stats': {'added': len(new_names - old_names), 'removed': len(old_names - new_names), 'changed_argument_schemas': len(changed)}}

def _assert_payload_has_no_known_credential(payload: dict, credential_values: frozenset[str]) -> None:
    serialized = json.dumps(payload, ensure_ascii=False)
    hit_count = matching_credential_literal_count(serialized, credential_values)
    if hit_count:
        raise RuntimeError(f'command inventory credential closure gate rejected payload (matched_literal_count={hit_count})')

def _write_payload_atomic(path: Path, payload: dict) -> None:
    from cex_core.engine.case_compiler._sealed_io import atomic_write_bytes_nofollow
    raw = (json.dumps(payload, ensure_ascii=False, indent=1) + '\n').encode('utf-8')
    atomic_write_bytes_nofollow(path, raw, error_type=RuntimeError, invalid_message='vendor projection path is invalid', unavailable_message='vendor projection cannot be published atomically')

def _sync_sibling_command_tree_xml(*, output_dir: Path, device_build: str, source_xml: Path, source_raw: bytes) -> None:
    from cex_core.engine.case_compiler._sealed_io import atomic_write_bytes_nofollow, read_regular_nofollow
    sibling = output_dir / f'cmdtree_{device_build}.xml'
    try:
        if sibling.resolve() == source_xml.resolve():
            return
    except OSError:
        pass
    if sibling.is_file() and (not sibling.is_symlink()):
        try:
            existing = read_regular_nofollow(sibling, error_type=ValueError, invalid_message='sibling vendor XML path is invalid', directory_message='sibling vendor XML directory is unavailable', open_message='sibling vendor XML is unavailable', bounds_message='sibling vendor XML exceeds size budget', changed_message='sibling vendor XML changed while reading', max_bytes=16 * 1024 * 1024, min_bytes=1)
        except (OSError, ValueError):
            existing = None
        if existing == source_raw:
            return
    atomic_write_bytes_nofollow(sibling, source_raw, error_type=RuntimeError, invalid_message='sibling vendor XML path is invalid', unavailable_message='sibling vendor XML cannot be published atomically')

def generate_vendor_stdlib_projection(*, version: str, device_build: str, xml_path: Path, output_dir: Path | None=None, manual_version: str | None=None, manual_root: Path | None=None, footprint_dir: Path | None=None, credential_values: frozenset[str] | None=None) -> dict:
    ver = str(version or '').strip()
    build = str(device_build or '').strip()
    source_xml = Path(xml_path)
    if not ver or not build:
        raise ValueError('version and device_build are required')
    if source_xml.name != f'cmdtree_{build}.xml':
        raise ValueError('vendor XML filename must match the requested device build')
    source_raw = read_regular_nofollow(source_xml, error_type=ValueError, invalid_message='vendor XML path is invalid', directory_message='vendor XML directory is unavailable', open_message='vendor XML is unavailable', bounds_message='vendor XML exceeds size budget', changed_message='vendor XML changed while reading', max_bytes=16 * 1024 * 1024, min_bytes=1)
    assert isinstance(source_raw, bytes)
    values = credential_values
    if values is None:
        try:
            values = mirror_credential_literals()
        except MirrorCredentialLiteralError as exc:
            raise RuntimeError('credential closure unavailable; refusing to generate inventory') from exc
    if not values:
        raise ValueError('credential closure is empty; refusing to generate inventory')
    help_witness: dict[str, dict[int, list[str]]] = {}
    headers, xml_stats = parse_vendor_xml(source_xml, build, values, xml_bytes=source_raw, help_witness=help_witness)
    for entry in headers.values():
        entry['origin'] = 'vendor_xml'
    resolved_manual_version, manual_claims, manual_value_domains, catalog_statuses, catalog_identities = _load_manual_catalog_side(ver, manual_version, root=manual_root)
    footprints = footprint_dir or ROOT / 'knowledge' / 'footprints' / 'nodes'
    footprint_tables, footprint_stats = footprint_parameter_tables(footprints)
    try:
        xml_sensitive_values = xml_default_value_closure(ET.fromstring(source_raw))
    except ET.ParseError as exc:
        raise ValueError('vendor XML cannot be parsed') from exc
    value_domain_stats = merge_argument_value_domains(headers, manual_value_domains, footprint_tables, values, xml_sensitive_values, help_witness)
    catalog_base = Path(manual_root) if manual_root is not None else _default_manual_root()
    catalog_dir = catalog_base / resolved_manual_version
    try:
        manual_source_dir = str(catalog_dir.relative_to(ROOT))
    except ValueError:
        manual_source_dir = catalog_dir.name
    source = {'kind': 'vendor_command_tree_xml', 'device_os_build': build, 'sha256': hashlib.sha256(source_raw).hexdigest(), 'filename': source_xml.name}
    stats = {'vendor_header_count': len(headers), 'vendor_argument_count': int(xml_stats.get('arguments') or 0), 'vendor_parameter_schema_coverage': float(xml_stats.get('parameter_schema_coverage') or 0.0), 'vendor_noise': 0, 'manual_declaration_count': 0, 'manual_bold_lines': 0, 'manual_noise': 0, 'manual_coverage_excl_noise': 0.0, 'manual_shared_with_vendor': len(set(manual_claims) & set(headers)), 'default_values_omitted': int(xml_stats.get('default_values_omitted') or 0), 'credential_fields_redacted': int(xml_stats.get('credential_fields_redacted') or 0), 'suppressed_known_credential_headers': int(xml_stats.get('suppressed_known_credential_heads') or 0), 'value_domain': {**{key: int(count) for key, count in sorted(value_domain_stats.items())}, 'footprint_nodes_read': int(footprint_stats.get('files') or 0), 'footprint_commands_read': int(footprint_stats.get('commands') or 0), 'footprint_param_tables': len(footprint_tables), 'manual_catalog': {'schema': 'ist.manual-command-catalog', 'version': resolved_manual_version, 'families': catalog_statuses, 'identity': catalog_identities, 'signature_claims': len(manual_claims), 'value_domain_rows': sum((len(rows) for rows in manual_value_domains.values()))}}}
    payload = {'schema': 'ist.vendor_stdlib', 'version': ver, 'device_os_build': build, 'source': source, 'source_dir': manual_source_dir, 'source_glob': '*_cn.catalog.json', 'generator': 'scripts/maintenance/build_vendor_stdlib.py', 'projection_policy': None, 'stats': stats, 'headers': dict(sorted(headers.items())), 'manual_declarations': {}}
    from cex_core.engine.sync.command_tree_sync import projection_policy_identity, projection_xml_default_literal_count
    payload['projection_policy'] = projection_policy_identity()
    xml_default_hits = projection_xml_default_literal_count(payload, source_raw)
    if xml_default_hits:
        raise RuntimeError(f'vendor XML sensitive-literal final gate rejected projection (matched_literal_count={xml_default_hits})')
    _assert_payload_has_no_known_credential(payload, values)
    out_dir = output_dir or ROOT / 'knowledge' / 'data' / 'compile_ref'
    out = out_dir / f'vendor_stdlib_{ver}_{build}.json'
    _write_payload_atomic(out, payload)
    _sync_sibling_command_tree_xml(output_dir=out_dir, device_build=build, source_xml=source_xml, source_raw=source_raw)
    return {'path': out, 'payload': payload, 'manual_claims': manual_claims, 'stats': stats}

def manual_version_for_build(version: str, device_build: str) -> str:
    try:
        from cex_core.engine.case_compiler.vendor_stdlib import _product_platform_from_command_tree_partition
        from cex_core.engine.sync.command_tree_sync import parse_build_identity, resolve_active_command_tree
    except Exception:
        return ''
    try:
        product, platform = _product_platform_from_command_tree_partition(version, device_build)
        if not (product and platform):
            return ''
        active = resolve_active_command_tree(product=product, platform=platform, version=version, device_build=device_build)
        if active is None:
            return ''
        return str(parse_build_identity(active.full_version).release or '')
    except Exception:
        return ''

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--version', default='10.5')
    ap.add_argument('--xml', type=Path)
    ap.add_argument('--device-build', default='585')
    ap.add_argument('--manual-version', default='', help='手册 catalog 版本目录名（如 10.5.0）。不给就从该 build 的密封代际身份推导；推不出再回落 major.minor 的确定性解析（多候选即拒）。')
    ap.add_argument('--compare-with', type=Path, help='另一份 vendor_stdlib JSON；提供时同时产出 build diff')
    args = ap.parse_args()
    ver = args.version
    xml_path = args.xml or ROOT / 'knowledge' / 'data' / 'compile_ref' / f'cmdtree_{args.device_build}.xml'
    if not xml_path.is_file():
        raise SystemExit(f'vendor XML not found: {xml_path}; pass --xml pointing at the sealed generation cmdtree_{args.device_build}.xml (runtime/command_tree/.../generations/<id>/), not /tmp')
    try:
        generated = generate_vendor_stdlib_projection(version=ver, device_build=args.device_build, xml_path=xml_path, manual_version=str(args.manual_version or '').strip() or manual_version_for_build(ver, args.device_build) or None)
    except (RuntimeError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    out = generated['path']
    payload = generated['payload']
    stats = generated['stats']
    credential_values = mirror_credential_literals()
    result: dict = {'out': str(out.relative_to(ROOT)), **stats}
    if args.compare_with:
        try:
            previous = json.loads(args.compare_with.read_text(encoding='utf-8'))
        except Exception as exc:
            raise SystemExit(f'cannot read --compare-with payload: {exc}') from exc
        diff = diff_vendor_stdlibs(previous, payload)
        previous_build = str(previous.get('device_os_build') or 'unknown')
        diff_out = ROOT / 'knowledge' / 'data' / 'compile_ref' / f'vendor_stdlib_diff_{previous_build}_{args.device_build}.json'
        _assert_payload_has_no_known_credential(diff, credential_values)
        _write_payload_atomic(diff_out, diff)
        result['diff_out'] = str(diff_out.relative_to(ROOT))
        result['diff_stats'] = diff['stats']
    print(json.dumps(result, ensure_ascii=False))
if __name__ == '__main__':
    main()
