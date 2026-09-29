# 生成：tools/extract_engine.py ← InfoTest scripts/gen_capability_usage_index.py（sha256 21ed7a23c7bf7a03）。不在这里手改。
from __future__ import annotations
from cex_core.engine._root import _cex_data_path
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
_ROOT = _cex_data_path('')
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from cex_core.engine.case_compiler.apv_lang import LIFECYCLE_FS, host_slot_es, public_methods
from cex_core.engine.case_compiler.credential_literals import matching_credential_literal_count, mirror_credential_literals
from cex_core.engine.case_compiler.excel_contract import execute_action_name
from cex_core.engine.ist_core.tools.device.structural_gate import steps_from_xlsx
_OUT = _ROOT / 'knowledge/data/compile_ref/capability_usage_index.json'
_CORPUS_GLOBS = ('knowledge/framework/verified/verified_*.xlsx',)
_AUTHORED_CORPUS_UNAVAILABLE_REASON = 'The engine-owned device-verified workbook corpus is not present. Legacy mirror-local workbooks are not trusted unless the compile-entry migration proves their workbook, delivery, and deny-list identities. No authored zero-hit or usage conclusion may be drawn until a certified corpus is present.'
_VENDOR_CORPUS_GLOBS = ('knowledge/framework/mirror/smoke_test/**/*.xlsx',)
_HOST_KEY_SPACE_SOURCES = ('lib/env.py', 'lib/test_xlsx.py', 'smoke_test/conftest.py')
_VENDOR_COMMANDS_PER_TOKEN = 40
_VENDOR_COMMAND_TEXT_MAX = 600
_VENDOR_DESC_MAX = 160
_REDACTED_TOKEN = '<redacted:credential-literal>'

def _corpus_files() -> list[Path]:
    files: list[Path] = []
    for pat in _CORPUS_GLOBS:
        files.extend(sorted(_ROOT.glob(pat)))
    return files

def _vendor_corpus_files() -> list[Path]:
    files: list[Path] = []
    for pat in _VENDOR_CORPUS_GLOBS:
        files.extend(sorted(_ROOT.glob(pat)))
    return files

def _source_manifest_sha256(files: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in files:
        rel = path.relative_to(_ROOT).as_posix()
        digest.update(rel.encode('utf-8'))
        digest.update(b'\x00')
        digest.update(hashlib.sha256(path.read_bytes()).digest())
        digest.update(b'\x00')
    return digest.hexdigest()

def _vendor_manifest_sha256(files: list[Path]) -> str:
    digest = hashlib.sha256(_source_manifest_sha256(files).encode('utf-8'))
    mirror = _ROOT / 'knowledge/framework/mirror'
    for rel in _HOST_KEY_SPACE_SOURCES:
        digest.update(rel.encode('utf-8'))
        digest.update(b'\x00')
        try:
            digest.update(hashlib.sha256((mirror / rel).read_bytes()).digest())
        except OSError:
            digest.update(b'<unreadable>')
        digest.update(b'\x00')
    return digest.hexdigest()

def _host_key_space() -> tuple[frozenset[str], frozenset[str]]:
    env_slots = frozenset(public_methods('lib/env.py', 'Env')) - LIFECYCLE_FS
    direct_slots = frozenset(host_slot_es())
    if not env_slots and (not direct_slots):
        raise RuntimeError('vendor host key space is empty; the framework mirror and the devices table are both unreadable, so no vendor row could be attributed')
    return (env_slots, direct_slots)

def _host_of_step(step: dict, env_slots: frozenset[str], direct_slots: frozenset[str]) -> str:
    e = str(step.get('E') or '').strip()
    f = str(step.get('F') or '').strip()
    if e == 'test_env':
        return f if f in env_slots else ''
    return e if e in direct_slots else ''

def _first_token(text: str) -> str:
    parts = str(text or '').strip().split()
    return parts[0] if parts else ''

def _record_step(step: dict, rel: str, autoid: str, by_f: dict[str, dict], by_action: dict[str, dict]) -> None:
    f_val = step.get('F') or ''
    if not f_val:
        return
    bucket = by_f.setdefault(f_val, {'count': 0, '_files': set(), 'usages': []})
    bucket['count'] += 1
    bucket['_files'].add(rel)
    bucket['usages'].append({'file': rel, 'autoid': autoid, 'desc': step.get('D', ''), 'g': (step.get('G') or '')[:200]})
    if f_val == 'execute':
        action = execute_action_name(step.get('G') or '')
        if action:
            abucket = by_action.setdefault(action, {'count': 0, '_files': set(), 'usages': []})
            abucket['count'] += 1
            abucket['_files'].add(rel)
            abucket['usages'].append({'file': rel, 'autoid': autoid, 'desc': step.get('D', ''), 'g': (step.get('G') or '')[:200]})

def _record_host_step(step: dict, rel: str, autoid: str, host: str, hosts: dict[str, dict], credentials) -> None:
    g_raw = str(step.get('G') or '')
    desc_raw = str(step.get('D') or '')
    f_val = str(step.get('F') or '')
    bucket = hosts.setdefault(host, {'rows': 0, 'redacted_rows': 0, '_files': set(), '_tokens': {}, '_commands': {}})
    bucket['rows'] += 1
    bucket['_files'].add(rel)
    redacted = bool(credentials and matching_credential_literal_count(f'{g_raw}\n{desc_raw}', credentials))
    if redacted:
        bucket['redacted_rows'] += 1
        token = _REDACTED_TOKEN
        command = _REDACTED_TOKEN
        desc = _REDACTED_TOKEN
        truncated = 0
    else:
        token = _first_token(g_raw)
        command = g_raw[:_VENDOR_COMMAND_TEXT_MAX]
        truncated = max(0, len(g_raw) - _VENDOR_COMMAND_TEXT_MAX)
        desc = desc_raw[:_VENDOR_DESC_MAX]
    tok_bucket = bucket['_tokens'].setdefault(token, {'rows': 0, '_files': set()})
    tok_bucket['rows'] += 1
    tok_bucket['_files'].add(rel)
    key = (token, f_val, command)
    entry = bucket['_commands'].setdefault(key, {'first_token': token, 'f': f_val, 'command': command, 'command_truncated_chars': truncated, 'redacted': redacted, 'rows': 0, '_files': set(), 'first_seen_file': rel, 'first_seen_autoid': autoid, 'first_seen_desc': desc})
    entry['rows'] += 1
    entry['_files'].add(rel)

def _finalize_host_bucket(bucket: dict) -> dict:
    tokens = [{'token': name, 'rows': info['rows'], 'distinct_files': len(info['_files'])} for name, info in bucket['_tokens'].items()]
    tokens.sort(key=lambda item: (-item['rows'], item['token']))
    by_token: dict[str, list[dict]] = {}
    for entry in bucket['_commands'].values():
        by_token.setdefault(entry['first_token'], []).append(entry)
    commands: list[dict] = []
    omitted = 0
    for entries in by_token.values():
        entries.sort(key=lambda item: (-item['rows'], item['f'], item['command']))
        kept = entries[:_VENDOR_COMMANDS_PER_TOKEN]
        omitted += len(entries) - len(kept)
        for entry in kept:
            entry['distinct_files'] = len(entry.pop('_files'))
            commands.append(entry)
    commands.sort(key=lambda item: (-item['rows'], item['first_token'], item['f'], item['command']))
    return {'rows': bucket['rows'], 'redacted_rows': bucket['redacted_rows'], 'distinct_files': len(bucket['_files']), 'distinct_first_tokens': len(tokens), 'distinct_commands': len(bucket['_commands']), 'commands_recorded': len(commands), 'commands_omitted': omitted, 'first_tokens': tokens, 'commands': commands}

def _record_authored_host_step(step: dict, rel: str, host: str, hosts: dict[str, dict]) -> None:
    bucket = hosts.setdefault(host, {'rows': 0, '_files': set(), '_tokens': {}})
    bucket['rows'] += 1
    bucket['_files'].add(rel)
    token = _first_token(str(step.get('G') or ''))
    tok_bucket = bucket['_tokens'].setdefault(token, {'rows': 0, '_files': set()})
    tok_bucket['rows'] += 1
    tok_bucket['_files'].add(rel)

def _finalize_authored_host_bucket(bucket: dict) -> dict:
    tokens = [{'token': name, 'rows': info['rows'], 'distinct_files': len(info['_files'])} for name, info in bucket['_tokens'].items()]
    tokens.sort(key=lambda item: (-item['rows'], item['token']))
    return {'rows': bucket['rows'], 'distinct_files': len(bucket['_files']), 'distinct_first_tokens': len(tokens), 'first_tokens': tokens}

def build_vendor_host_observations() -> dict:
    files = _vendor_corpus_files()
    if not files:
        raise RuntimeError('vendor host observation corpus is empty')
    if any((path.is_symlink() for path in files)):
        raise RuntimeError('vendor host observation corpus contains a symbolic-link source')
    manifest = _vendor_manifest_sha256(files)
    env_slots, direct_slots = _host_key_space()
    credentials = mirror_credential_literals()
    hosts: dict[str, dict] = {}
    unreadable: list[str] = []
    total_rows = 0
    host_rows = 0
    scanned = 0
    for fp in files:
        rel = fp.relative_to(_ROOT).as_posix()
        try:
            autoid, steps = steps_from_xlsx(fp)
        except Exception as exc:
            unreadable.append(f'{rel}: {type(exc).__name__}')
            continue
        scanned += 1
        for step in steps:
            total_rows += 1
            host = _host_of_step(step, env_slots, direct_slots)
            if not host:
                continue
            host_rows += 1
            _record_host_step(step, rel, str(autoid or ''), host, hosts, credentials)
    post_files = _vendor_corpus_files()
    if post_files != files or any((path.is_symlink() for path in post_files)):
        raise RuntimeError('vendor host observation corpus changed while it was being scanned')
    if _vendor_manifest_sha256(post_files) != manifest:
        raise RuntimeError('vendor host observation corpus changed while it was being scanned')
    observations = {host: _finalize_host_bucket(bucket) for host, bucket in sorted(hosts.items())}
    meta = {'vendor_corpus_definition': 'knowledge/framework/mirror/smoke_test/**/*.xlsx —— 厂商随框架发布的冒烟用例卷。它记的是「厂商在那张床上做过什么」,与 verified 语料的「我方整卷 PASS 后的稳定回写」是两种性质的证据,故分列不合桶。', 'vendor_corpus_globs': list(_VENDOR_CORPUS_GLOBS), 'vendor_corpus_file_count': len(files), 'vendor_scanned_file_count': scanned, 'vendor_unreadable_files': unreadable, 'vendor_unreadable_files_reason': '这些卷不是 A–I 执行模板(staging 中间产物/框架自测卷),读不出步骤行。逐份记名跳过而不是整批 fail-closed——否则这份投影永远生不出来。它们的内容因此不在本列里,不能读成「这些卷里没有主机行」。', 'vendor_total_rows_scanned': total_rows, 'vendor_host_rows': host_rows, 'vendor_source_manifest_sha256': manifest, 'vendor_redacted_rows': sum((bucket['redacted_rows'] for bucket in observations.values())), 'vendor_redaction_reason': f'命中 mirror 明文凭据字面闭集的行,原文与首 token 换成 {_REDACTED_TOKEN};行本身照常计数,遮蔽条数逐主机与全局各报一次。', 'vendor_commands_cap_per_first_token': _VENDOR_COMMANDS_PER_TOKEN, 'vendor_command_text_max_chars': _VENDOR_COMMAND_TEXT_MAX, 'vendor_storage_note': f'命令原文按 (首 token, F, 原文) 去重存储,每条带出现行数/去重文件数/一处出处;每个首 token 最多留 {_VENDOR_COMMANDS_PER_TOKEN} 条不同原文,截掉多少落在该主机的 commands_omitted。行计数与首 token 直方图是全量的,不受这个上限影响。', 'host_key_space': sorted(env_slots | direct_slots), 'host_key_space_sources': list(_HOST_KEY_SPACE_SOURCES), 'host_key_space_note': '主机名单从 mirror 机械解析,不手抄:test_env 的 F 面 = lib/env.py 的 Env 方法名;直连槽 E 面 = smoke_test/conftest.py 里经 ssh_server(...) 构造的 fixture ∩ lib/test_xlsx.py 的 devices 表。两种寻址形态 (E=test_env,F=主机 / E=主机) 都归到同一个主机键下。', 'host_observation_reading': 'Every number here is a past observation of what the vendor suite ran, not a statement about what the machine offers today. Zero rows for a host or a token means no precedent was recorded, not that the action is unsupported.'}
    return {'meta': meta, 'observations': observations}

def build() -> dict:
    files = _corpus_files()
    if any((path.is_symlink() for path in files)):
        raise RuntimeError('capability usage corpus contains a symbolic-link source')
    source_manifest = _source_manifest_sha256(files)
    env_slots, direct_slots = _host_key_space()
    by_f: dict[str, dict] = {}
    by_action: dict[str, dict] = {}
    authored_hosts: dict[str, dict] = {}
    total_rows = 0
    unreadable: list[str] = []
    for fp in files:
        rel = fp.relative_to(_ROOT).as_posix()
        try:
            autoid, steps = steps_from_xlsx(fp)
            expected_autoid = fp.stem.removeprefix('verified_')
            if str(autoid or '') != expected_autoid:
                raise ValueError('workbook autoid does not match verified filename')
        except Exception as exc:
            unreadable.append(f'{rel}: {type(exc).__name__}')
            continue
        for step in steps:
            total_rows += 1
            _record_step(step, rel, autoid, by_f, by_action)
            host = _host_of_step(step, env_slots, direct_slots)
            if host:
                _record_authored_host_step(step, rel, host, authored_hosts)
    for bucket in list(by_f.values()) + list(by_action.values()):
        bucket['distinct_files'] = len(bucket.pop('_files'))
    authored_host_usage = {host: _finalize_authored_host_bucket(bucket) for host, bucket in sorted(authored_hosts.items())}
    if unreadable:
        raise RuntimeError(f'capability usage corpus is incomplete; {len(unreadable)} source file(s) were unreadable')
    post_files = _corpus_files()
    if post_files != files or any((path.is_symlink() for path in post_files)):
        raise RuntimeError('capability usage corpus changed while it was being scanned')
    if _source_manifest_sha256(post_files) != source_manifest:
        raise RuntimeError('capability usage corpus changed while it was being scanned')
    vendor = build_vendor_host_observations()
    corpus_status = 'ready' if files else 'absent'
    execute_empty_reason = "本轮 corpus 下 by_execute_action 为空字典——已用合成 step(见 test_capability_usage_index.py 的正例验证)证明抽取器找得到 execute 用法,不是抽取缺陷;空是因为当前 device-verified 语料里确实一次都没用过 F=execute,与内部调研文档（已脱敏）的独立人工审计结论('execute机制:0次使用')一致。" if files else _AUTHORED_CORPUS_UNAVAILABLE_REASON
    return {'_meta': {'purpose': "device-verified 案例的能力键(F 值/execute 动作名)真实用法倒排——回答'有没有人这样用过、真实样子长什么样',与 capability_atlas.json的'框架能不能这样用'互补,不重复。", 'regenerate': 'python scripts/gen_capability_usage_index.py', 'corpus_definition': 'knowledge/framework/verified/verified_*.xlsx (独立整卷 PASS 后的引擎自有稳定回写；排除远端 framework mirror 与会被 closing 清理的 workspace 路径)', 'corpus_globs': list(_CORPUS_GLOBS), 'corpus_status': corpus_status, 'corpus_absence_reason': _AUTHORED_CORPUS_UNAVAILABLE_REASON if not files else '', 'corpus_file_count': len(files), 'total_rows_scanned': total_rows, 'source_manifest_sha256': source_manifest, 'unreadable_files': [], 'intended_consumption': 'M2 检索通道(工具进程内 load,不是 worker fs_read 直读)。本文件全量收录、不截断(见下 by_execute_action_empty_reason 同款纪律),完整体积远超 worker 默认 200 行读窗——若 M2 决定改为让 worker 直接 fs_read 本文件,必须先按能力键分文件,否则 worker 一次读只能看到排在最前的那个能力键的一小段,看不到其余能力键(内部工单 的实物例证)。', 'by_execute_action_empty_reason': execute_empty_reason, 'authored_corpus_empty_reason': _AUTHORED_CORPUS_UNAVAILABLE_REASON if not files else '', 'column_separation_reason': 'by_f_value / by_execute_action / authored_host_usage 三个桶的语料是我方 verified 卷(整卷 PASS 后的引擎自有回写＝我们自己验证过的先例);vendor_host_observations 的语料是厂商 smoke_test 卷(厂商在那张床上做过什么)。两者性质不同,合成一个计数就分不清「谁验过」,故分列。', 'authored_host_usage_has_no_verbatim_reason': '我方那一列只给计数,不给命令原文——它没经过那张床上厂商那套长期运行,不构成「这台机器容得下这条命令」的先例;与厂商原文并排摆出来会让读者分不清哪一份是被那台机器长期证明过的。', **vendor['meta']}, 'by_f_value': by_f, 'by_execute_action': by_action, 'authored_host_usage': authored_host_usage, 'vendor_host_observations': vendor['observations']}

def write_projection(data: dict, path: Path=_OUT) -> None:
    payload = json.dumps(data, ensure_ascii=False, indent=2) + '\n'
    credential_values = mirror_credential_literals()
    if matching_credential_literal_count(payload, credential_values):
        raise RuntimeError('capability usage projection rejected: serialized payload contains one or more protected mirror credential literals')
    if path.is_symlink():
        raise RuntimeError('capability usage projection path must not be a symlink')
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f'.{path.name}.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            Path(tmp_name).unlink(missing_ok=True)
        except OSError:
            pass
        raise

def converge_projection(path: Path=_OUT) -> tuple[dict, bool]:
    data = build()
    try:
        current = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError):
        current = None
    changed = current != data
    if changed:
        write_projection(data, path)
    return (data, changed)

def main() -> None:
    data, _changed = converge_projection()
    m = data['_meta']
    print(f"wrote {_OUT} — status={m['corpus_status']} files={m['corpus_file_count']} rows={m['total_rows_scanned']} f_values={len(data['by_f_value'])} execute_actions={len(data['by_execute_action'])}")
    print(f"  vendor column — files={m['vendor_scanned_file_count']}/{m['vendor_corpus_file_count']} (skipped {len(m['vendor_unreadable_files'])}) host_rows={m['vendor_host_rows']} hosts={len(data['vendor_host_observations'])} redacted_rows={m['vendor_redacted_rows']}")
    print(f"  authored column — hosts={len(data['authored_host_usage'])} (counts only, no verbatim)")
    payload_bytes = len((json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    print(f'  payload bytes={payload_bytes}')
if __name__ == '__main__':
    main()
