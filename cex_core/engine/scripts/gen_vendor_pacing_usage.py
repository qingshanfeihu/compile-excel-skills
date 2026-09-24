# 生成：tools/extract_engine.py ← InfoTest scripts/gen_vendor_pacing_usage.py（sha256 e9c6edcfb9aa0a85）。不在这里手改。
"""从框架镜像工作簿统计显式读窗/等待用法；记录出现次数，不签命令需求或合法上限。"""
from __future__ import annotations
from cex_core.engine._root import _cex_data_path
import argparse
from collections import Counter
import hashlib
import io
import json
import sys
from pathlib import Path
import openpyxl
ROOT = _cex_data_path('')
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from cex_core.engine.case_compiler.excel_contract import parse_g_arguments, strip_apv_command_kwargs, ExcelContractError
from cex_core.engine.case_compiler.vendor_stdlib import norm_command_tokens, vendor_stdlib_path
DEFAULT_OUTPUT = ROOT / 'knowledge/data/compile_ref/vendor_pacing_usage.json'
ENGINE_STAGING_PREFIX = 'ist_staging_'

def build_usage(*, mirror_root: Path | None=None, projection_path: Path | None=None, version: str='10.5', device_build: str='585') -> dict:
    mirror = mirror_root or ROOT / 'knowledge/framework/mirror'
    projection = projection_path or vendor_stdlib_path(version, device_build)
    source_bytes = projection.read_bytes()
    source = json.loads(source_bytes)
    headers = source.get('headers')
    if not isinstance(headers, dict) or not headers:
        raise ValueError('command-tree projection has no headers')
    heads = {tuple(norm_command_tokens(head)): head for head in headers}
    max_head = max(map(len, heads))
    manifest, by_head = ({}, {})
    sleeps, prompts = (Counter(), Counter())
    unresolved = 0
    unreadable = []
    timeout_argument_rows = 0
    unmapped_timeout_rows = 0
    engine_staging_excluded = 0
    for path in sorted(mirror.rglob('*.xlsx')):
        rel = path.relative_to(mirror).as_posix()
        if any((part.startswith(ENGINE_STAGING_PREFIX) for part in path.relative_to(mirror).parts)):
            engine_staging_excluded += 1
            continue
        if path.is_symlink() or not path.is_file():
            raise ValueError('pacing source must be a regular workbook')
        raw = path.read_bytes()
        manifest[rel] = hashlib.sha256(raw).hexdigest()
        try:
            book = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
        except Exception as exc:
            unreadable.append({'file': rel, 'error_type': type(exc).__name__})
            continue
        try:
            for sheet in book.worksheets:
                previous_method = ''
                previous_case = ''
                for row in sheet.iter_rows(values_only=True):
                    if len(row) < 7:
                        continue
                    e, method, g = (str(row[n] or '').strip() for n in (4, 5, 6))
                    if row[0] is not None and str(row[0]) != previous_case:
                        previous_method = ''
                        previous_case = str(row[0])
                    if e == 'time' and method == 'sleep':
                        if previous_method:
                            sleeps[previous_method] += 1
                        previous_method = method
                        continue
                    if not e or not method:
                        previous_method = ''
                        continue
                    if e.startswith('APV') and method in {'cmd_config', 'cmd_enable', 'cmd'}:
                        try:
                            _args, kwargs = parse_g_arguments(g, method)
                            command = strip_apv_command_kwargs(g, method)
                        except ExcelContractError:
                            unresolved += 1
                            previous_method = method
                            continue
                        if 'prompt' in kwargs:
                            prompts[method] += 1
                        if 'timeout' in kwargs:
                            timeout_argument_rows += 1
                            tokens = tuple(norm_command_tokens(command))
                            head = next((heads[tokens[:size]] for size in range(min(max_head, len(tokens)), 0, -1) if tokens[:size] in heads), None)
                            if head is None:
                                unresolved += 1
                                unmapped_timeout_rows += 1
                            else:
                                item = by_head.setdefault(head, {'values': Counter(), 'files': set()})
                                value = kwargs['timeout']
                                if isinstance(value, int) and (not isinstance(value, bool)):
                                    item['values'][str(value)] += 1
                                    item['files'].add(rel)
                                else:
                                    unresolved += 1
                    previous_method = method
        finally:
            book.close()
    return {'schema': 'ist.vendor-pacing-usage', 'version': version, 'device_build': device_build, 'policy': 'Observed workbook usage only; counts are not recommendations, default values or legal timeout limits.', 'by_head': [{'head': head, 'timeout_count': sum(item['values'].values()), 'timeout_values': dict(sorted(item['values'].items(), key=lambda pair: int(pair[0]))), 'files': sorted(item['files'])} for head, item in sorted(by_head.items()) if item['values']], 'sleep_after': [{'prev_method': method, 'count': count} for method, count in sorted(sleeps.items())], 'prompt_usage': [{'method': method, 'count': count} for method, count in sorted(prompts.items())], 'unresolved_rows': unresolved, 'timeout_argument_rows': timeout_argument_rows, 'unmapped_timeout_rows': unmapped_timeout_rows, 'source': {'files': len(manifest), 'present': bool(manifest), 'engine_staging_excluded': engine_staging_excluded, 'unreadable_files': unreadable, 'sha256_manifest': manifest, 'command_tree_sha256': hashlib.sha256(source_bytes).hexdigest(), 'generated_from': 'framework_mirror_workbooks', 'generator': 'scripts/gen_vendor_pacing_usage.py'}}

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--version', default='10.5')
    parser.add_argument('--device-build', default='585')
    args = parser.parse_args(argv)
    rendered = json.dumps(build_usage(version=args.version, device_build=args.device_build), ensure_ascii=False, indent=2) + '\n'
    if args.check:
        if not args.output.is_file() or args.output.read_text(encoding='utf-8') != rendered:
            print('vendor pacing usage projection is stale')
            return 1
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        if not args.output.is_file() or args.output.read_text(encoding='utf-8') != rendered:
            args.output.write_text(rendered, encoding='utf-8')
    return 0
if __name__ == '__main__':
    raise SystemExit(main())
