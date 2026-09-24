# 生成：tools/extract_engine.py ← InfoTest main/case_compiler/gate_advisories.py（sha256 6a5e7e8a43d88495）。不在这里手改。
from cex_core.engine.case_compiler.step_graph import GP_CODES
STRUCTURAL_ADVISORY_CODES = frozenset({'ambiguous_observation_binding', 'driver_no_declared_path_author_sourced', 'line_anchor_window_unverified', 'config_existence_only', 'no_assertion_in_case', 'dead_capture'})
STRUCTURAL_DISABLED_CODES = frozenset({'command_allowlist_footprint_unavailable', 'destructive_command', 'regex_anchor_analysis_unavailable'})
MECHANICAL_ADVISORY_CODES = frozenset({'authored_argument_descriptive', 'author_sourced_driver_target', 'author_sourced_unreachable_setup', 'author_sourced_trigger_target', 'residual_config_disclosed', 'criterion_binding_declared', 'scope_ref_absent', 'adaptation_dropped_authored_command'})
ADVISE_CODE_CONSUMERS = {code: 'gate_advisory' for code in STRUCTURAL_ADVISORY_CODES | MECHANICAL_ADVISORY_CODES | GP_CODES | {f'gate_disabled:{code}' for code in STRUCTURAL_DISABLED_CODES}}

def advisory_check_status(code: str) -> str:
    if code not in ADVISE_CODE_CONSUMERS:
        return 'unknown'
    if code.startswith('gate_disabled:'):
        return 'not_checked'
    return 'checked_limitation'
