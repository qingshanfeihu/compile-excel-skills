# 生成：tools/extract_engine.py ← InfoTest scripts/maintenance/build_package_advisories.py（sha256 feba41498e6e6f19）。不在这里手改。
from __future__ import annotations
from cex_core.engine._root import _cex_data_path
import argparse
from pathlib import Path
from cex_core.engine.case_compiler.package_advisories import HISTORICAL_TARGET_COUNT, build_package_advisories, write_json_atomic

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--historical-target', type=int, default=HISTORICAL_TARGET_COUNT)
    parser.add_argument('--output', type=Path, default=Path('knowledge/data/compile_ref/package_advisories_10.5.json'))
    args = parser.parse_args()
    root = _cex_data_path('')
    payload = build_package_advisories(root / 'knowledge/framework/verified', root / 'knowledge/framework/mirror_precedent_provenance.json', poison_root=root / 'tests/fixtures/precedents/poisoned', retro_scan_path=None, historical_target_count=args.historical_target)
    output = args.output if args.output.is_absolute() else root / args.output
    write_json_atomic(output, payload)
    baseline = payload['baseline']
    source = payload['source']
    print(f"wrote {output}: certified={baseline['certified']} unverified={baseline['unverified']} current={source['current_manifest_count']} historical_target={source['historical_target_count']} population_complete={source['population_complete']}")
    return 0
if __name__ == '__main__':
    raise SystemExit(main())
