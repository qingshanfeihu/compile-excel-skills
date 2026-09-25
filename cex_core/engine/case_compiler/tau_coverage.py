# 生成：tools/extract_engine.py ← InfoTest main/case_compiler/tau_coverage.py（sha256 e87d81db53bff719）。不在这里手改。
from __future__ import annotations
import hashlib
import json
import re
import shlex
import threading
from dataclasses import dataclass, field
from pathlib import Path
from cex_core.engine.engine_managed_outputs import RESIDUAL_CONFIG_DISCLOSURE_SIDECAR_NAME

class TauAtlasUnavailableError(RuntimeError):
    code = 'tau_atlas_unavailable'

    def __init__(self, device_build: str):
        self.device_build = str(device_build or 'unknown')
        super().__init__(f'{self.code}: build-bound command teardown atlas is unavailable for device build {self.device_build}')

@dataclass
class TauReport:
    missing: list[dict] = field(default_factory=list)
    covered: list[dict] = field(default_factory=list)
    out_of_scope: list[str] = field(default_factory=list)
    residual_config: list[dict] = field(default_factory=list)
    device_build: str = ''
    atlas_identity: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.missing

def _persist_res() -> list:
    try:
        from cex_core.engine.case_compiler.domain_grammar import load_grammar
        ld = (load_grammar().get('persistence_channels') or {}).get('local_disk') or {}
        pats = ld.get('patterns') or []
        if pats:
            return [re.compile(p, re.IGNORECASE) for p in pats]
    except Exception:
        import logging
        logging.getLogger(__name__).warning('persistence_channels 文法读取失败——τ 持久面分流回落硬编集', exc_info=True)
    return [re.compile('^\\s*(?:write|config)\\s+(?:all|file|memory|net|segment)\\b', re.IGNORECASE)]
_PERSIST_RES = _persist_res()

def _is_persist(line: str) -> bool:
    return any((r.match(line) for r in _PERSIST_RES))

def _apv_config_lines(steps: list, init: str='') -> list[str]:
    out: list[str] = []
    for line in (init or '').splitlines():
        if line.strip():
            out.append(line.strip())
    for s in steps or []:
        if not isinstance(s, dict):
            continue
        if not str(s.get('E', '')).startswith('APV'):
            continue
        method = str(s.get('F', ''))
        raw = str(s.get('G', '') or '')
        if method == 'cmd_config':
            try:
                from cex_core.engine.case_compiler.excel_contract import parse_g_arguments
                args, _kwargs = parse_g_arguments(raw, method)
                values = [str(args[0])] if args else []
            except Exception:
                values = [raw]
        elif method == 'cmds_config':
            values = raw.splitlines()
        else:
            continue
        for line in values:
            if line.strip():
                out.append(line.strip())
    return out

def _derivation_data(device_build: str='') -> tuple[dict, dict]:
    pairs: dict = {}
    try:
        from cex_core.engine.case_compiler.vendor_stdlib import derive_inverse_pairs
        pairs = dict(derive_inverse_pairs(device_build=device_build))
    except Exception:
        import logging
        logging.getLogger(__name__).warning('inverse_forms 现算不可用——τ 仍按 atlas 分类,但实体逆元配对收窄', exc_info=True)
    requested_build = str(device_build).strip()
    try:
        from cex_core.engine.scripts.gen_command_teardown_atlas import load_command_teardown_atlas, verify_atlas_source_identity
        from cex_core.engine.case_compiler.vendor_stdlib import configured_device_os_build, device_os_build_suffix
        if not requested_build:
            requested_build = str(configured_device_os_build() or '').strip()
        if not requested_build:
            raise ValueError('device build is unavailable for teardown atlas binding')
        requested_build = device_os_build_suffix(requested_build) or requested_build
        atlas = load_command_teardown_atlas(expected_build=requested_build)
        verify_atlas_source_identity(atlas)
        return (pairs, atlas)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning('command_teardown_atlas 不可用或身份失配——τ 必须失败关闭', exc_info=True)
        raise TauAtlasUnavailableError(requested_build) from exc

def _head_match(line: str, pairs: dict) -> str | None:
    ws = line.split()
    for k in range(min(len(ws), 5), 0, -1):
        cand = ' '.join(ws[:k]).lower()
        if cand in pairs:
            return cand
    return None

def _atlas_head_match(line: str, commands: dict) -> str | None:
    ws = line.lower().split()
    for k in range(len(ws), 0, -1):
        candidate = ' '.join(ws[:k])
        if candidate in commands:
            return candidate
    return None

def _entities(line: str) -> set:
    return {t for t in re.findall('[\\w.-]+', line) if any((c.isdigit() for c in t)) and (not t.replace('.', '').isdigit()) and (not all((seg in {'0', '128', '192', '224', '240', '248', '252', '254', '255'} for seg in t.split('.')))) or re.fullmatch('\\d+\\.\\d+\\.\\d+\\.\\d+', t)}

def _inverse_scope_of(head: str, teardown: dict, suggested: str | None) -> str:
    text = str(suggested or '').strip()
    if not text:
        return 'object'
    if str(teardown.get('matched_form') or '') == 'clear_prefix_all':
        return 'module_wide'
    tokens = text.split()
    if tokens and tokens[-1].lower() == 'all':
        return 'module_wide'
    verb = tokens[0].lower() if tokens else ''
    if verb not in {'clear', 'no'}:
        return 'object'
    scope_tokens = tokens[1:]
    head_tokens = str(head or '').split()
    if not scope_tokens or not head_tokens:
        return 'object'
    return 'module_wide' if len(scope_tokens) < len(head_tokens) else 'object'

def _derived_tau(lines: list[str], pairs: dict, atlas: dict, rep: 'TauReport') -> None:
    pairs_lc = {k.lower(): v for k, v in pairs.items()}
    commands = dict(atlas.get('commands') or {})
    rep.device_build = str(atlas.get('device_build') or '')
    rep.atlas_identity = dict(atlas.get('identity') or {})
    lo = [l.lower() for l in lines]
    transition_coverage: dict[str, str] = {}
    try:
        from cex_core.engine.case_compiler.ssl_lifecycle_contract import load_ssl_lifecycle_contract
        lifecycle = load_ssl_lifecycle_contract(rep.device_build, verify_command_tree_receipts=False)
        transition_coverage = {str(head).strip(): str(cover).strip() for head, cover in dict(lifecycle.get('preflight_transition_coverage') or {}).items() if str(head).strip() and str(cover).strip()}
    except Exception:
        transition_coverage = {}

    def _object_token(command: str, command_head: str) -> str:
        try:
            tokens = shlex.split(command)
        except ValueError:
            return ''
        offset = len(str(command_head or '').split())
        return str(tokens[offset]).casefold() if len(tokens) > offset else ''
    for i, line in enumerate(lines):
        ll = lo[i]
        if ll.startswith(('no ', 'clear ', 'show ')):
            continue
        if _is_persist(line):
            rep.out_of_scope.append(line)
            continue
        head = _atlas_head_match(line, commands)
        if head is None:
            continue
        record = commands.get(head) or {}
        class_name = str(record.get('class') or '')
        covering_head = transition_coverage.get(head)
        if covering_head:
            transition_object = _object_token(line, head)
            covered_by_prior_object = any((_atlas_head_match(lines[prior], commands) == covering_head and _object_token(lines[prior], covering_head) == transition_object for prior in range(i)))
            if transition_object and covered_by_prior_object:
                rep.covered.append({'cmd': line, 'head': head, 'class': class_name or 'C2', 'coverage': 'same_object_lifecycle_transition', 'entity': transition_object, 'covered_by_head': covering_head, 'suggested_inverse': None, 'atlas_provenance': dict(record.get('provenance') or {})})
                continue
        if head in {'ssl host virtual', 'ssl host real'}:
            try:
                forward_tokens = shlex.split(line)
                host_name = forward_tokens[len(head.split())]
            except (ValueError, IndexError):
                host_name = ''
            cleared_at = None
            for later in range(i + 1, len(lines)):
                try:
                    tokens = shlex.split(lines[later])
                except ValueError:
                    continue
                if len(tokens) >= 4 and [token.lower() for token in tokens[:3]] == ['clear', 'ssl', 'host'] and (not host_name or tokens[3] == host_name):
                    cleared_at = later
                    break
            if cleared_at is not None and cleared_at + 1 < len(lines) and (lines[cleared_at + 1].strip().upper() == 'YES'):
                rep.covered.append({'cmd': line, 'head': head, 'class': class_name or 'C2', 'coverage': 'reference_interactive_object_teardown', 'entity': host_name, 'suggested_inverse': None, 'atlas_provenance': dict(record.get('provenance') or {})})
                continue
        if class_name == 'C1':
            rep.covered.append({'cmd': line, 'head': head, 'class': 'C1', 'coverage': 'framework_per_case_cleanup', 'entity': '', 'suggested_inverse': None, 'atlas_provenance': dict(record.get('provenance') or {})})
            continue
        if class_name == 'C3':
            residual = {'command': line, 'head': head, 'class': 'C3', 'provenance': dict(record.get('provenance') or {}), 'xml_src': list((record.get('xml') or {}).get('src') or [])}
            if not any((item.get('command') == line and item.get('head') == head for item in rep.residual_config)):
                rep.residual_config.append(residual)
            continue
        if class_name not in {'C2', 'C2b'}:
            continue
        pair = pairs_lc.get(head) or {}
        inv_no = str(pair.get('no') or '').lower()
        inv_clear = str(pair.get('clear') or '').lower()
        teardown = dict(record.get('teardown') or {})
        atlas_suggestion = str(teardown.get('suggested_inverse') or '').strip()
        atlas_suggestion_lc = atlas_suggestion.lower()
        atlas_coverage_lc = atlas_suggestion_lc if teardown.get('suggested_inverse_executable') is not False else ''
        ents = _entities(line)
        if inv_no and ents and any((lo[j].startswith(inv_no) and ents & _entities(lines[j]) for j in range(i))):
            rep.covered.append({'cmd': line, 'entity': ', '.join(sorted(ents)[:2]), 'suggested_inverse': '(restore write, itself part of τ)'})
            continue

        def _atlas_covers(index: int) -> bool:
            if not atlas_coverage_lc or not lo[index].startswith(atlas_coverage_lc):
                return False
            if atlas_coverage_lc.startswith('no '):
                return not ents or bool(ents & _entities(lines[index]))
            return True
        covered = any((inv_no and lo[j].startswith(inv_no) and (not ents or ents & _entities(lines[j])) or (inv_clear and lo[j].startswith(inv_clear)) or _atlas_covers(j) for j in range(i + 1, len(lines))))
        ordered = [t for t in re.findall('[\\w.-]+', line) if t in ents]
        named = [t for t in ordered if not re.fullmatch('\\d+\\.\\d+\\.\\d+\\.\\d+', t)]
        ent = named[-1] if named else ordered[-1] if ordered else ''
        suggested_inverse: str | None = atlas_suggestion or None
        if suggested_inverse and inv_no and (atlas_suggestion_lc == inv_no) and ent:
            suggested_inverse = f'{atlas_suggestion} {ent}'.strip()
        inverse_scope = _inverse_scope_of(head, teardown, suggested_inverse)
        if inverse_scope == 'module_wide':
            suggested_inverse = None
        item = {'cmd': line, 'head': head, 'class': class_name, 'entity': ent, 'suggested_inverse': suggested_inverse, 'atlas_suggested_inverse': atlas_suggestion or None, 'inverse_scope': inverse_scope, 'suggestion_status': str(teardown.get('status') or ''), 'suggested_inverse_executable': teardown.get('suggested_inverse_executable'), 'src': str(pair.get('src') or ''), 'atlas_provenance': dict(record.get('provenance') or {})}
        (rep.covered if covered else rep.missing).append(item)
RESIDUAL_DISCLOSURE_SIDECAR = RESIDUAL_CONFIG_DISCLOSURE_SIDECAR_NAME
RESIDUAL_DISCLOSURE_SCHEMA = 'ist.residual-config-disclosure'
_RESIDUAL_DISCLOSURE_LOCK = threading.Lock()

def _residual_disclosure_payload(autoid: str, report: 'TauReport', *, discovery_stages: list[str], existing_commands: list[dict] | None=None) -> dict | None:
    if not report.residual_config:
        return None
    command_rows: dict[tuple[str, str], dict] = {}
    for raw in [*(existing_commands or []), *report.residual_config]:
        if not isinstance(raw, dict):
            continue
        command = str(raw.get('command') or '').strip()
        head = str(raw.get('head') or '').strip()
        if not command or not head:
            continue
        command_rows[head, command] = {'command': command, 'head': head, 'class': 'C3', 'provenance': dict(raw.get('provenance') or {}), 'xml_src': sorted((str(value) for value in raw.get('xml_src') or []))}
    commands = [command_rows[key] for key in sorted(command_rows)]
    if not commands:
        return None
    identity = dict(report.atlas_identity or {})
    identity_sha = str(identity.get('sha256') or '')
    core = {'code': 'residual_config_disclosure', 'autoid': str(autoid), 'device_build': str(report.device_build), 'atlas_identity_sha256': identity_sha, 'commands': commands}
    disclosure_id = hashlib.sha256(json.dumps(core, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()
    return {'schema': RESIDUAL_DISCLOSURE_SCHEMA, 'autoid': str(autoid), 'disclosure': {**core, 'disclosure_id': disclosure_id, 'message_zh': '本案配置无机械收回途径，会留残留', 'atlas_identity': identity, 'discovery_stages': sorted({str(stage) for stage in discovery_stages if str(stage)})}}

def persist_residual_config_disclosure(case_dir: Path, autoid: str, report: 'TauReport', *, discovery_stage: str) -> dict | None:
    if not report.residual_config:
        return None
    path = Path(case_dir) / RESIDUAL_DISCLOSURE_SIDECAR
    with _RESIDUAL_DISCLOSURE_LOCK:
        existing_commands: list[dict] = []
        stages = [discovery_stage]
        if path.exists() or path.is_symlink():
            if path.is_symlink() or not path.is_file():
                raise OSError('residual disclosure sidecar path is invalid')
            try:
                old = json.loads(path.read_text(encoding='utf-8'))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise OSError('residual disclosure sidecar is unreadable') from exc
            old_disclosure = old.get('disclosure') if isinstance(old, dict) else None
            same_identity = isinstance(old_disclosure, dict) and old.get('schema') == RESIDUAL_DISCLOSURE_SCHEMA and (str(old.get('autoid') or '') == str(autoid)) and (str(old_disclosure.get('device_build') or '') == report.device_build) and (str(old_disclosure.get('atlas_identity_sha256') or '') == str((report.atlas_identity or {}).get('sha256') or ''))
            if not same_identity:
                raise OSError('residual disclosure sidecar identity/schema does not match this case')
            existing_commands = list(old_disclosure.get('commands') or [])
            stages.extend(old_disclosure.get('discovery_stages') or [])
        payload = _residual_disclosure_payload(autoid, report, discovery_stages=stages, existing_commands=existing_commands)
        if payload is None:
            return None
        raw = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode('utf-8')
        from cex_core.engine.case_compiler._sealed_io import atomic_write_bytes_nofollow
        digest = atomic_write_bytes_nofollow(path, raw, error_type=OSError, invalid_message='residual disclosure sidecar path is invalid', unavailable_message='residual disclosure sidecar write failed', create_parents=True, mode=384)
        return {'path': str(path), 'sha256': digest, 'payload': payload}

def inverse_line(item: dict, *, audience: str='machine') -> str:
    suggested = item.get('suggested_inverse')
    if suggested:
        return str(suggested)
    if str(item.get('inverse_scope') or '') == 'module_wide':
        if audience == 'user':
            return f"[module-wide] {item.get('head')}:XML 只提供模块级复位，作用域大于本案对象，需自行给出对象级恢复步"
        return f"[module-wide] {item.get('head')}: the XML only offers a module-wide reset, whose scope exceeds the object this case created — derive an object-scoped teardown yourself (lang_query kind='heads'/'param')."
    if audience == 'user':
        return f"[unknown] {item.get('head')}:默认方向表无记录，不得机械翻转"
    return f"[unknown] {item.get('head')}: no default-direction record exists; do not mechanically invert."

def tau_ledger_mutator(report: 'TauReport'):
    inv_seq = [inverse_line(m, audience='user') for m in reversed(report.missing)]
    inv_seq_en = [inverse_line(m) for m in reversed(report.missing)]
    commands = [m['cmd'] for m in report.missing]
    from cex_core.engine.ist_core.compile_engine.conflict_chain import conflict_chain_id
    chain_id = conflict_chain_id({'scenario': 'missing_teardown', 'commands': commands, 'teardown_axis': [{'head': str(item.get('head') or ''), 'scope': str(item.get('inverse_scope') or 'object'), 'inverse': item.get('suggested_inverse') or None} for item in reversed(report.missing)]})

    def _mutate(claims: list) -> list:
        kept = [c for c in claims if c.get('claim_kind') != 'missing_teardown']
        kept.append({'claim_kind': 'missing_teardown', 'conflict_chain_id': chain_id, 'commands': commands, 'suggested_tau': inv_seq, 'suggested_tau_en': inv_seq_en, 'teardown_evidence': [{'command': str(item.get('cmd') or ''), 'head': str(item.get('head') or ''), 'class': str(item.get('class') or ''), 'suggested_inverse': item.get('suggested_inverse'), 'inverse_scope': str(item.get('inverse_scope') or 'object'), 'suggestion_status': str(item.get('suggestion_status') or ''), 'suggested_inverse_executable': item.get('suggested_inverse_executable'), 'atlas_provenance': dict(item.get('atlas_provenance') or {})} for item in report.missing], 'atlas_identity': dict(report.atlas_identity or {}), 'device_build': str(report.device_build or ''), 'reason': f'卷面有 {len(report.missing)} 条配置写不属于框架 C1 自动清理面,且没有案尾恢复步——会污染同批后续用例。atlas 建议序列:' + '；'.join(inv_seq), 'suggested_fix': '按 atlas 已知逆元在案尾追加恢复序列；unknown 默认方向须先补来源/实测，不得机械翻转；或确认该写是被测行为本身需保留', 'min_requests': 0, 'ordering_sensitive': False})
        return kept
    return _mutate

def check_tau_coverage_lines(lines: list[str], *, device_build: str='') -> TauReport:
    rep = TauReport()
    normalized = [str(line or '').strip().lower() for line in lines]
    if all((not line or line.startswith(('show ', 'no ', 'clear ')) for line in normalized)):
        rep.device_build = str(device_build or '')
        return rep
    pairs, atlas = _derivation_data(device_build)
    _derived_tau(lines, pairs, atlas, rep)
    return rep

def check_tau_coverage(steps: list, init: str='', *, device_build: str='') -> TauReport:
    return check_tau_coverage_lines(_apv_config_lines(steps, init), device_build=device_build)
