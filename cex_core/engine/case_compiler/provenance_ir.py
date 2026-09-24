# 生成：tools/extract_engine.py ← InfoTest main/case_compiler/provenance_ir.py（sha256 c7d4bd2c9535b6d6）。不在这里手改。
"""三层 Provenance IR（V3 步骤1，论文 §3.5 定义3.6/3.7 的带来源 G⊔E⊔V 分解）。

draft 产出 steps 的同时，为**每一步**标注它属于哪一层、来源是什么：
- G 层（骨架/文法）：source = footprint feature_id / 先例 xlsx 名
- E 层（环境常量）：source = env_facts 拓扑行（可达子网/服务 IP）
- V 层（业务语义）：source = 先例链 / 手册行号 / 作者意图

这是 draft↔grade↔verify↔writeback 的公共契约：
- grade（步骤2）验 provenance 而非重新 grep；
- verify（步骤5）按 layer 把 fail 路由到 G/E/V；
- writeback（步骤4）只把已验证的 G/E 段事实写回 footprint。

设计红线（§3.7ter）：provenance 只**记录** draft 已做的来源决策，
不替代骨架选择——layer/source 是 draft 自己标的语义注解，不是确定性规则。
"""
from __future__ import annotations
from cex_core.engine._root import _cex_data_path
import ast
import builtins
import copy
import hashlib
import json
import logging
import os
import re
import stat
import symtable
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal
from cex_core.engine.case_compiler._sealed_io import open_directory_nofollow, read_regular_at_nofollow, read_regular_nofollow, validate_json_budget
from cex_core.engine.case_compiler.excel_contract import ExcelContractError, contract_sha256, enabled_fs_by_e, load_excel_contract
from cex_core.engine.defect_spec_source import contains_prohibited_declaration, validate_source_context_binding
from cex_core.engine.knowledge_paths import KNOWLEDGE_AUTO_ENV, KNOWLEDGE_DATA_ROOT, KNOWLEDGE_FOOTPRINTS, KNOWLEDGE_FOOTPRINTS_NODES, KNOWLEDGE_FRAMEWORK_MIRROR, KNOWLEDGE_VERIFIED_PACKAGES, KNOWLEDGE_MANUAL, KNOWLEDGE_MARKDOWN, PROJECT_ROOT, SpecGenerationUnavailable, WORKSPACE_DEFECTS, WORKSPACE_INPUTS, WORKSPACE_OUTPUTS, output_scope, resolve_active_spec_generation, scope_bucket
from cex_core.engine.common.schema_identity import accepts_schema

def _scoped_outputs_root() -> Path:
    """当前作用域的 outputs 根，用**本模块的** ``WORKSPACE_OUTPUTS`` 拼。

    与下面 DefectSpec 那段的 inputs 侧同一个 `scope_bucket()`。
    不调 `knowledge_paths.scoped_outputs_root()`：那个函数读的是 knowledge_paths
    自己的模块全局，而本模块的 ``PROJECT_ROOT`` / ``WORKSPACE_INPUTS`` /
    ``WORKSPACE_DEFECTS`` / ``WORKSPACE_OUTPUTS`` 是可被替换的模块级名字（隔离根、
    测试树都靠替换它们生效）。四个根里只有 outputs 例外，就会在同一次调用里一半
    指隔离根、一半指真仓——而且是静默的。桶根当参数传，拼法仍是单源那一份。
    """
    return scope_bucket(WORKSPACE_OUTPUTS)
_CODE_ROOT = _cex_data_path('')
_logger = logging.getLogger(__name__)
Layer = Literal['G', 'E', 'V']
_VALID_LAYERS = ('G', 'E', 'V')
MUTATION_ROLE_CONTROL = 'control'
_VALID_MUTATION_ROLES = ('', MUTATION_ROLE_CONTROL)
ASSERTION_TYPE_SCHEMA = 'ist.ide.assertion'
_EXPECT_KINDS = frozenset({'Author', 'Manual', 'ConfigBinding', 'Spec', 'DefectSpec', 'CapabilityXml'})
_CLAIM_ORIGIN: dict[str, tuple[str, str]] = {'intent': ('Author', ''), 'author': ('Author', ''), 'spec': ('Spec', ''), 'defect_spec': ('DefectSpec', ''), 'manual': ('Manual', ''), 'capability_xml': ('CapabilityXml', ''), 'config_derived': ('ConfigBinding', 'config_derived'), 'captured_relation': ('ConfigBinding', 'captured_relation'), 'distribution_derived': ('ConfigBinding', 'distribution_derived'), 'membership_derived': ('ConfigBinding', 'membership_derived'), 'status_derived': ('Author', 'status_derived')}

def claim_authority_source(source_kind: str) -> str:
    """source.kind → 签发该 claim 的权威组（六源闭集名）；未知来源返回空串，不猜。"""
    return _CLAIM_ORIGIN.get(str(source_kind or '').strip(), ('', ''))[0]

def claim_derivation(source_kind: str) -> str:
    """source.kind → 派生配方名；非派生来源返回空串。"""
    return _CLAIM_ORIGIN.get(str(source_kind or '').strip(), ('', ''))[1]
_RUNTIME_ONLY_KINDS = frozenset({'DeviceRuntime', 'Probe', 'Observed', 'CurrentRun', 'Precedent', 'Footprint'})
_FLIP_KINDS = frozenset({'Flipped', 'Exempt'})
ORDERING_EXEMPT_REASON = 'multicore_nondeterministic_order'
FLIP_CONTROL_UNCONSTRUCTIBLE_REASON = 'flip_control_unconstructible'
EXEMPT_REASON_CODES = frozenset({'shared_bed_hidden_vars', ORDERING_EXEMPT_REASON, 'device_default_row', 'non_readonly_probe', 'direction_review_pending', FLIP_CONTROL_UNCONSTRUCTIBLE_REASON})
COMPILER_ISSUED_EXEMPT_CODES = frozenset({FLIP_CONTROL_UNCONSTRUCTIBLE_REASON})
EMIT_ACCEPTED_EXEMPT_CODES = EXEMPT_REASON_CODES - {'direction_review_pending'}
AUTHOR_DECLARABLE_EXEMPT_CODES = EXEMPT_REASON_CODES - COMPILER_ISSUED_EXEMPT_CODES
_FORM_KIND = 'GatesPass'
_VALID_SOURCE_KINDS = ('footprint', 'emit_auto', 'precedent', 'env_facts', 'test_env_dispatch', 'manual', 'spec', 'defect_spec', 'capability_xml', 'intent', 'config_derived', 'captured_relation', 'distribution_derived', 'membership_derived', 'status_derived', 'skeleton', 'device_runtime', 'unknown')
RUNTIME_PLACEHOLDER = '<RUNTIME>'
KNOWN_PROVENANCE_CLAIM_LIMIT = 12
_SOURCE_LOCATOR_REQUIRED = frozenset({'footprint', 'manual', 'spec', 'defect_spec', 'capability_xml', 'precedent', 'env_facts', 'intent', 'skeleton'})

def known_provenance_facts(autoid: str, *, outputs_root: Path) -> list[str]:
    """渲染引擎已盖章的出处身份和固定 source-kind 路由，不参与判定。"""
    lines = ['<known_provenance_facts>', 'The following values are engine-read facts, not suggestions and not a credential.']
    aid = str(autoid or '').strip()
    if re.fullmatch('\\d{18}', aid):
        from cex_core.engine.case_compiler.contract_entry import ContractError, read_intent_json
        root = Path(outputs_root)
        try:
            payload, _raw = read_intent_json(root / aid / 'intent.json', trusted_root=root)
        except ContractError:
            payload = {}
        claims = payload.get('author_claims')
        pairs: list[tuple[str, str]] = []
        if isinstance(claims, dict):
            for key, claim in sorted(claims.items()):
                if not isinstance(claim, dict):
                    continue
                expectation_id = str(claim.get('expectation_id') or key).strip()
                semantic_key = str(claim.get('semantic_key') or '').strip()
                if expectation_id and semantic_key:
                    pairs.append((expectation_id, semantic_key))
        if pairs:
            lines.append("Stamped Author assertion identities (copy both fields onto each assertion that redeems that claim, and use source.kind='intent' with source.ref equal to the expectation_id):")
            for expectation_id, semantic_key in pairs[:KNOWN_PROVENANCE_CLAIM_LIMIT]:
                lines.append(f"  - expectation_id={expectation_id!r}; semantic_key={semantic_key!r}; source={{'kind': 'intent', 'ref': {expectation_id!r}}}")
            if len(pairs) > KNOWN_PROVENANCE_CLAIM_LIMIT:
                lines.append(f'  - ... {len(pairs) - KNOWN_PROVENANCE_CLAIM_LIMIT} more stamped pairs remain in the same intent.json')
    lines.extend(['Source-kind routing already enforced by the engine:', '  - intent redeems a stamped expected assertion; it does not source an APV CONFIG command or a test-environment action.', "  - E='test_env' actions use source.kind='test_env_dispatch' and the compiler-derived source.ref 'lib/env.py#Env.<lowercase F>'.", "  - APV commands/configuration and other actions cite the real source actually consulted (for example an existing manual or footprint locator); source.kind 'emit_auto' is accepted only for the time/sleep language primitive.", '  - Field routing is part of the contract: put product-command provenance in CONFIG.ref (kind:locator), observation-command provenance in OBSERVE_ASSERT.cmd_ref, and expected-value authority in each asserts[].ref. Do not invent a nested provenance/source object. Commands with different sources belong in separate CONFIG blocks.', "  - A manual locator must identify one exact file. Copy the project-relative or manual-root-relative path exposed by the retrieval result; a bare basename such as 'cli_cn.md' is invalid when more than one version/root carries it. An ambiguity rejection lists the exact candidate paths; copy one of those paths instead of retrying another bare stem.", '</known_provenance_facts>'])
    return lines

@dataclass
class StepSource:
    """一步的来源。kind 决定路由类型，ref 是具体定位（feature_id/行号/xlsx名）。"""
    kind: str = 'unknown'
    ref: str = ''
    receipt: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.kind not in _VALID_SOURCE_KINDS:
            self.kind = 'unknown'

@dataclass
class StepIR:
    """一个编译步骤 + 三层来源标注。E/F/G 与 xlsx 列语义一致（见 compile_emit）。"""
    E: str
    F: str
    G: str
    layer: Layer = 'V'
    source: StepSource = field(default_factory=StepSource)
    assertion_type: dict[str, Any] | None = None
    spec_gap: str = ''
    observation_id: str = ''
    result_channel: str = ''
    observation_ref: str = ''
    expectation_id: str = ''
    semantic_key: str = ''
    mutation_role: str = ''

    def __post_init__(self):
        if self.layer not in _VALID_LAYERS:
            self.layer = 'V'
        if self.mutation_role not in _VALID_MUTATION_ROLES:
            self.mutation_role = ''

@dataclass
class CaseProvenance:
    """一个 case 的完整 provenance：autoid + 逐步来源 + 族骨架引用（步骤3）。"""
    autoid: str
    steps: list[StepIR] = field(default_factory=list)
    skeleton_ref: str = ''
    assertion_schema: str = ''
    provisional_at_emit: bool = True

    def to_dict(self) -> dict:
        return {'autoid': self.autoid, 'skeleton_ref': self.skeleton_ref, **({'assertion_schema': self.assertion_schema} if self.assertion_schema else {}), 'provisional_at_emit': self.provisional_at_emit, 'steps': [{'E': s.E, 'F': s.F, 'G': s.G, 'layer': s.layer, 'source': {'kind': s.source.kind, 'ref': s.source.ref, **({'receipt': s.source.receipt} if s.source.receipt else {})}, **({'assertion_type': s.assertion_type} if s.assertion_type is not None else {}), **({'spec_gap': s.spec_gap} if s.spec_gap else {}), **({'observation_id': s.observation_id} if s.observation_id else {}), **({'result_channel': s.result_channel} if s.result_channel else {}), **({'observation_ref': s.observation_ref} if s.observation_ref else {})} | ({'expectation_id': s.expectation_id} if s.expectation_id else {}) | ({'semantic_key': s.semantic_key} if s.semantic_key else {}) | ({'mutation_role': s.mutation_role} if s.mutation_role else {}) for s in self.steps]}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def layer_steps(self, layer: Layer) -> list[StepIR]:
        return [s for s in self.steps if s.layer == layer]

    @classmethod
    def from_dict(cls, d: dict) -> 'CaseProvenance':
        steps = []
        for raw in d.get('steps', []):
            src = raw.get('source') or {}
            steps.append(StepIR(E=str(raw.get('E', '')), F=str(raw.get('F', '')), G=str(raw.get('G', '')), layer=raw.get('layer', 'V'), source=StepSource(kind=src.get('kind', 'unknown'), ref=str(src.get('ref', '')), receipt=dict(src.get('receipt')) if isinstance(src.get('receipt'), dict) else {}), assertion_type=raw.get('assertion_type') if 'assertion_type' in raw else None, spec_gap=str(raw.get('spec_gap') or ''), observation_id=str(raw.get('observation_id') or ''), result_channel=str(raw.get('result_channel') or ''), observation_ref=str(raw.get('observation_ref') or ''), expectation_id=str(raw.get('expectation_id') or ''), semantic_key=str(raw.get('semantic_key') or ''), mutation_role=str(raw.get('mutation_role') or '')))
        if 'provisional_at_emit' in d:
            _prov_at_emit = bool(d.get('provisional_at_emit', True))
        else:
            _prov_at_emit = bool(d.get('provisional', True))
        return cls(autoid=str(d.get('autoid', '')), steps=steps, skeleton_ref=str(d.get('skeleton_ref', '')), assertion_schema=str(d.get('assertion_schema', '') or ''), provisional_at_emit=_prov_at_emit)

    @classmethod
    def from_json(cls, text: str) -> 'CaseProvenance':
        return cls.from_dict(json.loads(text))
_EXTERNAL_SOURCE_KINDS = frozenset({'footprint', 'manual', 'spec', 'defect_spec', 'capability_xml', 'precedent', 'env_facts', 'intent', 'skeleton'})
_DERIVED_SOURCE_KINDS = frozenset({'config_derived', 'captured_relation', 'distribution_derived', 'membership_derived', 'status_derived'})
_CONFIG_BINDING_DERIVATION_SCHEMA = 'ist.config-binding.derivation'
_CONFIG_BINDING_RULES = {'config_derived': frozenset({'config.literal-copy', 'config.fixture-literal-backref'}), 'captured_relation': frozenset({'capture.static-relation', 'capture.static-reference'}), 'distribution_derived': frozenset({'distribution.interval'}), 'membership_derived': frozenset({'membership.literal-set'}), 'status_derived': frozenset({'status.exit-code'})}
_CONFIG_BINDING_GENERATORS = {'config.literal-copy': 'main/case_compiler/provenance_ir.py', 'config.fixture-literal-backref': 'main/case_compiler/provenance_ir.py', 'capture.static-relation': 'main/case_compiler/provenance_ir.py', 'capture.static-reference': 'main/case_compiler/provenance_ir.py', 'distribution.interval': 'main/case_compiler/distribution_assertion.py', 'membership.literal-set': 'main/case_compiler/membership_assertion.py', 'status.exit-code': 'main/case_compiler/provenance_ir.py'}
_EXIT_STATUS_EXPECTATIONS: dict[str, str] = {'success': '(?m)^IST_EXIT_STATUS=0\\r?$'}

def _transport_failure_pattern(codes: tuple[int, ...]) -> str:
    """退出码类 → 单条 found 正则；多码用交替，单码也带括号，形态统一可机读。"""
    alternation = '|'.join((str(code) for code in sorted(set((int(c) for c in codes)))))
    return f'(?m)^IST_EXIT_STATUS=({alternation})\\r?$'

def exit_status_assertion(expect: str, probe: str='', codes: tuple[int, ...] | list[int]=()) -> tuple[dict[str, str] | None, str]:
    """把结构化成功/失败极性派生为固定 check_point 三元组。

    规则是纯函数：失败极性的退出码类 ``codes`` 由 blocks 展开器按探针工具名
    ``probe`` 查文法数据（`domain_grammar.probe_tool_transport_failure_codes`）后
    随 source_input 传入，收据材料因此同时钉住工具名与当时的码类；表变即新收据，
    旧收据仍按当时的码类复算成立（历史事实不改写）。
    """
    from cex_core.engine.case_compiler.blocks import _EXIT_STATUS_EXPECTS
    value = str(expect or '').strip().lower()
    if value not in _EXIT_STATUS_EXPECTS:
        return (None, 'exit-status expect must be exactly success or failure')
    if value == 'success':
        return ({'E': 'check_point', 'F': 'found', 'G': _EXIT_STATUS_EXPECTATIONS['success']}, '')
    tool = str(probe or '').strip().lower()
    cleaned = tuple(sorted({int(c) for c in codes or () if isinstance(c, int) and (not isinstance(c, bool)) and (c > 0)}))
    if not tool or not cleaned:
        return (None, "expect=failure asserts a transport-level failure of the probe tool, so it needs the probe tool name and that tool's documented transport-failure exit codes (grammar section probe_tools); a bare non-zero exit code is not accepted because it also matches client-side errors and misses answered refusals")
    return ({'E': 'check_point', 'F': 'found', 'G': _transport_failure_pattern(cleaned)}, '')
_TEST_ENV_DISPATCH_SOURCES = ('lib/env.py', 'lib/test_xlsx.py')
_LINE_LOCATOR_RE = re.compile('^(.*?)(?::([1-9]\\d*)(?:-([1-9]\\d*))?)?$')
_MANUAL_LOCATOR_SHAPE = 'manual:<source-file-or-unique-stem>[:<line>|:<line-start>-<line-end>]'
_CAPABILITY_XML_EXPECT_RECEIPT_SCHEMA = 'ist.capability-xml-expected'
_DEFECT_SPEC_RECEIPT_SCHEMA = 'ist.defect-spec-receipt'
_DEFECT_SPEC_MAX_SOURCE_BYTES = 64 * 1024 * 1024
_DEFECT_SPEC_MAX_TICKET_BYTES = 64 * 1024 * 1024
_DEFECT_SPEC_MAX_SOURCE_CANDIDATES = 4096
_DEFECT_SPEC_MAX_SOURCE_TOTAL_BYTES = 256 * 1024 * 1024
_DEFECT_SPEC_MAX_TICKET_JSON_DEPTH = 64
_DEFECT_SPEC_MAX_TICKET_JSON_TOKENS = 131072
_DEFECT_SPEC_LOCATOR_RE = re.compile('^defect:(bugzilla|zentao|zentao_story):([A-Za-z][A-Za-z0-9_]*-\\d+):(title|description)$')

def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()

def _safe_file_under(path: Path, root: Path) -> Path | None:
    """只接受真实存在、解析后仍位于显式只读根内的普通文件。"""
    try:
        resolved_root = root.resolve(strict=True)
        resolved = path.resolve(strict=True)
        resolved.relative_to(resolved_root)
    except (OSError, RuntimeError, ValueError):
        return None
    return resolved if resolved.is_file() else None

def _line_locator(locator: str) -> tuple[str, int | None, int | None]:
    match = _LINE_LOCATOR_RE.fullmatch(locator.strip())
    if not match:
        return (locator.strip(), None, None)
    start = int(match.group(2)) if match.group(2) else None
    end = int(match.group(3)) if match.group(3) else start
    return (match.group(1).strip(), start, end)
_LOCATOR_ERROR_AMBIGUOUS = 'ambiguous_locator'

class _LocatorResolutionError(str):
    """保留人读散文，同时给内部 wrapper 一个不依赖措辞的机读码。"""

    def __new__(cls, message: str, *, code: str=''):
        instance = super().__new__(cls, message)
        instance.code = str(code or '')
        return instance

def _ambiguous_locator_error(message: str) -> _LocatorResolutionError:
    return _LocatorResolutionError(message, code=_LOCATOR_ERROR_AMBIGUOUS)

def _is_ambiguous_locator_error(error: str) -> bool:
    return isinstance(error, _LocatorResolutionError) and error.code == _LOCATOR_ERROR_AMBIGUOUS

def _narrow_to_bound_manual_version(candidates: list[Path], root: Path) -> list[Path]:
    """把候选收窄到本次编译绑定的手册版本；拿不到版本或收窄后为空就原样退回。"""
    try:
        from cex_core.engine.case_compiler.criterion_author_rules import resolve_compile_manual_version
        version = str(resolve_compile_manual_version() or '')
    except Exception:
        return []
    if not version:
        return []
    resolved_root = root.resolve()
    narrowed = []
    for candidate in candidates:
        try:
            parts = candidate.relative_to(resolved_root).parts
        except ValueError:
            continue
        if version in parts:
            narrowed.append(candidate)
    return narrowed

def _unique_named_file(root: Path, locator: str, *, suffix: str='') -> tuple[Path | None, str]:
    """把项目相对路径、根内相对路径或唯一 basename/stem 解析为真实文件。"""
    raw = locator.strip()
    if not raw:
        return (None, 'empty locator')
    if Path(raw).is_absolute() or '..' in Path(raw).parts:
        return (None, "absolute paths and '..' are not allowed")
    variants = [raw]
    if suffix and (not raw.endswith(suffix)):
        variants.append(raw + suffix)
    direct_candidates: list[Path] = []
    for item in variants:
        direct_project = _safe_file_under(PROJECT_ROOT / item, root)
        if direct_project is not None:
            direct_candidates.append(direct_project)
        direct_root = _safe_file_under(root / item, root)
        if direct_root is not None:
            direct_candidates.append(direct_root)
    direct_unique = sorted(set(direct_candidates), key=lambda item: item.as_posix())
    if len(direct_unique) == 1:
        return (direct_unique[0], '')
    if len(direct_unique) > 1:
        return (None, _ambiguous_locator_error(f'source locator {raw!r} resolves to multiple explicit paths inside {root}'))
    if Path(raw).name != raw:
        return (None, f'no real source file matches explicit path {raw!r}')
    candidates: list[Path] = []
    wanted = Path(raw).name
    wanted_names = {wanted}
    if suffix and (not wanted.endswith(suffix)):
        wanted_names.add(wanted + suffix)
    try:
        for wanted_name in wanted_names:
            for candidate in root.rglob(wanted_name):
                safe = _safe_file_under(candidate, root)
                if safe is None:
                    continue
                candidates.append(safe)
        if suffix and (not wanted.endswith(suffix)):
            for candidate in root.rglob('*'):
                if candidate.is_file() and candidate.stem == wanted:
                    safe = _safe_file_under(candidate, root)
                    if safe is not None:
                        candidates.append(safe)
    except OSError:
        return (None, f'source root is unreadable: {root}')
    unique = sorted(set(candidates), key=lambda item: item.as_posix())
    if not unique:
        return (None, f'no real source file matches {raw!r}')
    if len(unique) > 1:
        unique = _narrow_to_bound_manual_version(unique, root) or unique
    if len(unique) == 1:
        return (unique[0], '')
    if len(unique) > 1:
        shown = []
        for candidate in unique[:6]:
            try:
                shown.append(candidate.relative_to(root.resolve()).as_posix())
            except ValueError:
                shown.append(candidate.name)
        tail = '' if len(unique) <= 6 else f' (+{len(unique) - 6} more)'
        return (None, _ambiguous_locator_error(f"source locator {raw!r} is ambiguous; use one exact root-relative path ({len(unique)} matches: {', '.join(shown)}{tail})"))
    return (unique[0], '')

def _unique_named_file_across_roots(roots: tuple[Path, ...], locator: str, *, suffix: str='') -> tuple[Path | None, Path | None, str]:
    """在多个显式只读根中解析一个文件，跨根同名时失败关闭。

    ``knowledge/data/manual`` 是 WebDAV 同步后的现役手册；
    ``knowledge/data/markdown`` 保留历史分章与其它 KMS 文档。两根都能签发
    ``manual`` receipt，但检索顺序不表示权威度，因此不能取第一个命中。
    """
    matches: list[tuple[Path, Path]] = []
    for root in roots:
        path, error = _unique_named_file(root, locator, suffix=suffix)
        if path is not None:
            matches.append((path, root))
            continue
        if _is_ambiguous_locator_error(error):
            return (None, None, error)
    unique = sorted({(path.resolve(), root.resolve()) for path, root in matches}, key=lambda item: item[0].as_posix())
    if not unique:
        head, _, tail = locator.strip().rpartition(':')
        if head and tail and (_line_locator(locator.strip())[1] is None):
            for root in roots:
                if _unique_named_file(root, head, suffix=suffix)[0] is not None:
                    return (None, None, f'source file {head!r} exists, but {tail!r} is not a line locator; manual refs use {_MANUAL_LOCATOR_SHAPE} — give a line number or a line range, not a section name')
        searched = ' | '.join((str(root) for root in roots))
        return (None, None, f'no real source file matches {locator.strip()!r}; searched manual roots: {searched}')
    if len(unique) > 1:
        return (None, None, f'source locator {locator.strip()!r} is ambiguous across manual roots; use a project-relative path (hits: ' + ' | '.join((path.as_posix() for path, _ in unique)) + ')')
    return (unique[0][0], unique[0][1], '')

def _file_receipt(*, kind: str, locator: str, path: Path, root: Path, line_start: int | None=None, line_end: int | None=None, selector: str='') -> tuple[dict[str, Any] | None, str]:
    try:
        relative = path.relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        relative = path.relative_to(root.resolve()).as_posix()
    receipt: dict[str, Any] = {'kind': kind, 'locator': locator, 'path': relative, 'sha256': _sha256_file(path), 'size': path.stat().st_size}
    if line_start is not None:
        try:
            line_count = sum((1 for _ in path.open('r', encoding='utf-8', errors='replace')))
        except OSError as exc:
            return (None, f'cannot read source lines: {exc}')
        assert line_end is not None
        if line_end < line_start:
            return (None, f'invalid descending line range {line_start}-{line_end}')
        if line_end > line_count:
            return (None, f'line locator {line_start}-{line_end} exceeds source length {line_count}')
        receipt['line_start'] = line_start
        receipt['line_end'] = line_end
    if selector:
        receipt['selector'] = selector
    return (receipt, '')

def _canonical_json_sha256(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()

def _defect_spec_resolution_seal(receipt: dict[str, Any], *, create: bool, project_root: Path | None=None) -> str:
    """要求 DefectSpec 收据来自引擎完成的三后端检索。

    resolver 收据本身是普通 JSON，worker 能删掉同号候选再重算一份语义上自洽的
    收据。引擎在内部 ``kb_bug_search`` 完成固定三后端探测后，把完整收据字节以
    O_EXCL 密封到 worker 不可写的 runtime；消费端只接受逐字节命中的密封收据。
    """
    from cex_core.engine.defect_spec_source import defect_backend_lookup_is_sealable
    if not defect_backend_lookup_is_sealable(receipt.get('lookup'), ticket_id=str(receipt.get('ticket_number') or '')):
        return 'DefectSpec resolution seal backend closure is incomplete'
    try:
        encoded = json.dumps(receipt, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    except (TypeError, ValueError, UnicodeError):
        return 'DefectSpec resolution seal receipt is not canonical JSON'
    if not encoded or len(encoded) > 8 * 1024 * 1024:
        return 'DefectSpec resolution seal receipt exceeds its size boundary'
    receipt_sha = hashlib.sha256(encoded).hexdigest()
    seal_dir = (project_root or PROJECT_ROOT) / 'runtime' / 'compiler_seals' / 'defect_spec_resolution'
    seal_name = f'{receipt_sha}.json'
    directory_fd: int | None = None
    try:
        directory_fd = open_directory_nofollow(seal_dir, error_type=OSError, invalid_message='DefectSpec resolution seal path is invalid', unavailable_message='DefectSpec resolution seal directory is unavailable', preserve_missing=not create, create_missing=create, create_mode=448)
        try:
            observed = read_regular_at_nofollow(directory_fd, seal_name, error_type=OSError, open_message='DefectSpec resolution seal is unavailable', bounds_message='DefectSpec resolution seal is not a bounded regular file', changed_message='DefectSpec resolution seal changed while being read', max_bytes=8 * 1024 * 1024, min_bytes=1, preserve_missing=True, require_current_uid=True)
        except FileNotFoundError:
            if not create:
                return 'DefectSpec resolution seal is unavailable'
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_CLOEXEC', 0)
            if not getattr(os, 'O_NOFOLLOW', 0):
                return 'DefectSpec resolution seal is unavailable'
            file_fd: int | None = None
            try:
                file_fd = os.open(seal_name, flags, 384, dir_fd=directory_fd)
                os.fchmod(file_fd, 384)
                view = memoryview(encoded)
                while view:
                    written = os.write(file_fd, view)
                    if written <= 0:
                        raise OSError('short DefectSpec resolution seal write')
                    view = view[written:]
                os.fsync(file_fd)
                info = os.fstat(file_fd)
                if not stat.S_ISREG(info.st_mode) or int(info.st_nlink) != 1:
                    raise OSError('DefectSpec resolution seal inode is invalid')
            except FileExistsError:
                pass
            finally:
                if file_fd is not None:
                    os.close(file_fd)
            os.fsync(directory_fd)
            observed = read_regular_at_nofollow(directory_fd, seal_name, error_type=OSError, open_message='DefectSpec resolution seal is unavailable', bounds_message='DefectSpec resolution seal is not a bounded regular file', changed_message='DefectSpec resolution seal changed while being read', max_bytes=8 * 1024 * 1024, min_bytes=1, require_current_uid=True)
        assert isinstance(observed, bytes)
        if observed != encoded:
            return 'DefectSpec resolution seal identity drift'
        return ''
    except FileNotFoundError:
        return 'DefectSpec resolution seal is unavailable'
    except (OSError, ValueError) as exc:
        return str(exc) or 'DefectSpec resolution seal is unavailable'
    finally:
        if directory_fd is not None:
            os.close(directory_fd)

def seal_defect_spec_resolution_receipt(receipt: dict[str, Any], *, project_root: Path | None=None) -> str:
    """由引擎在三后端检索完成后首次密封 resolver 收据。"""
    return _defect_spec_resolution_seal(receipt, create=True, project_root=project_root)

def _immutable_seal(*, family: str, scope_key: str, item_key: str, payload: dict[str, Any], label: str, create: bool, allow_missing: bool=False, observed_sink: dict[str, Any] | None=None, observation_sink: dict[str, Any] | None=None, project_root: Path | None=None) -> str:
    """首次落盘即冻结的身份封印：同一 key 上出现第二份不同内容一律判漂移。

    seal 落在 worker 不可写的 ``runtime/``，文件名只使用身份摘要；既有 seal
    只读不覆盖。这样设备 actual 即使被回填，也不能凭同一身份再铸一张
    ``compiled_pre_device`` 收据。``label`` 只进错误文本、不进封印内容——同一份
    I/O 纪律服务多个封印族，消息仍各自指向自己的域。漂移时把既有封印内容
    回填 ``observed_sink``，供调用方把「原来封的是什么」写进拒绝理由。
    """
    root = Path(project_root) if project_root is not None else PROJECT_ROOT
    seal_dir = root / 'runtime' / 'compiler_seals' / family / scope_key
    seal_name = f'{item_key}.json'
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    subject = {'kind': 'compiler_seal', 'family': family, 'scope_key': scope_key, 'item_key': item_key, 'expected_sha256': hashlib.sha256(encoded).hexdigest()}
    if observation_sink is not None:
        observation_sink.update(check='immutable_seal_access', outcome='unavailable', subject=subject)
    directory_fd: int | None = None
    try:
        directory_fd = open_directory_nofollow(seal_dir, error_type=OSError, invalid_message=f'{label} seal path is invalid', unavailable_message=f'{label} seal directory is unavailable', preserve_missing=not create, create_missing=create, create_mode=448)
        try:
            observed = read_regular_at_nofollow(directory_fd, seal_name, error_type=OSError, open_message=f'{label} seal is unavailable', bounds_message=f'{label} seal is not a bounded regular file', changed_message=f'{label} seal changed while being read', max_bytes=64 * 1024, min_bytes=1, preserve_missing=True, require_current_uid=True)
        except FileNotFoundError:
            if not create:
                return '' if allow_missing else f'{label} seal is unavailable'
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_CLOEXEC', 0)
            if not getattr(os, 'O_NOFOLLOW', 0):
                return f'{label} seal is unavailable'
            file_fd: int | None = None
            try:
                file_fd = os.open(seal_name, flags, 384, dir_fd=directory_fd)
                os.fchmod(file_fd, 384)
                view = memoryview(encoded)
                while view:
                    written = os.write(file_fd, view)
                    if written <= 0:
                        raise OSError(f'short {label} seal write')
                    view = view[written:]
                os.fsync(file_fd)
                info = os.fstat(file_fd)
                if not stat.S_ISREG(info.st_mode) or int(info.st_nlink) != 1:
                    raise OSError(f'{label} seal inode is invalid')
            except FileExistsError:
                pass
            finally:
                if file_fd is not None:
                    os.close(file_fd)
            os.fsync(directory_fd)
            observed = read_regular_at_nofollow(directory_fd, seal_name, error_type=OSError, open_message=f'{label} seal is unavailable', bounds_message=f'{label} seal is not a bounded regular file', changed_message=f'{label} seal changed while being read', max_bytes=64 * 1024, min_bytes=1, require_current_uid=True)
        assert isinstance(observed, bytes)
        subject['stored_sha256'] = hashlib.sha256(observed).hexdigest()
        if observed != encoded:
            if observation_sink is not None:
                observation_sink.update(check='immutable_seal_identity', outcome='different_bytes')
            if observed_sink is not None:
                from cex_core.engine.case_compiler.mechanical_case import _reject_constant, _reject_duplicate_keys
                try:
                    existing = json.loads(observed.decode('utf-8'), object_pairs_hook=_reject_duplicate_keys, parse_constant=_reject_constant)
                except (ValueError, UnicodeDecodeError, RecursionError) as exc:
                    if observation_sink is not None:
                        observation_sink.update(check='immutable_seal_json', outcome='invalid')
                        subject['error_type'] = type(exc).__name__
                    return f'{label} seal JSON is invalid: {exc}'
                if not isinstance(existing, dict):
                    if observation_sink is not None:
                        observation_sink.update(check='immutable_seal_json', outcome='not_object')
                    return f'{label} seal JSON must be an object'
                observed_sink.update(existing)
            return f'{label} seal identity drift'
        return ''
    except FileNotFoundError:
        return '' if allow_missing else f'{label} seal is unavailable'
    except (OSError, ValueError) as exc:
        return str(exc) or f'{label} seal is unavailable'
    finally:
        if directory_fd is not None:
            os.close(directory_fd)

def _defect_spec_compilation_seal(compilation: dict[str, Any], *, create: bool, allow_missing: bool=False) -> str:
    """固定同一缺陷声明首次编译出的 F/G，阻断删收据后重铸 expected。

    新 claim 有新 ``claim_sha256``，不与旧声明混用；I/O 纪律见 ``_immutable_seal``。
    """
    autoid = str(compilation.get('autoid') or '').strip()
    expectation_id = str(compilation.get('expectation_id') or '').strip()
    claim_sha256 = str(compilation.get('claim_sha256') or '').strip()
    if not autoid or Path(autoid).name != autoid or (not expectation_id) or (not re.fullmatch('[0-9a-f]{64}', claim_sha256)):
        return 'DefectSpec compilation seal identity is invalid'
    return _immutable_seal(family='defect_spec', scope_key=hashlib.sha256(autoid.encode('utf-8')).hexdigest(), item_key=hashlib.sha256(f'{expectation_id}\x00{claim_sha256}'.encode('utf-8')).hexdigest(), payload=compilation, label='DefectSpec compilation', create=create, allow_missing=allow_missing)

def _validate_defect_spec_expected_receipt(step: StepIR, *, resolver_receipt: dict[str, Any] | None=None, require_value_match: bool=True) -> tuple[dict[str, Any] | None, str]:
    """复验逐案 DefectSpec 收据与当前 ticket/source 身份。

    ``kb_bug_search`` 的原始命中只是候选。这里只接受引擎已解析的
    ``ist.defect-spec-receipt``，并把 locator 限制到收据安全投影的
    ``title``/``description`` 字段。设备 actual、复现步骤、日志和评论既不在
    投影闭集中，也不可通过 locator 引用。
    """
    supplied = resolver_receipt if resolver_receipt is not None else step.source.receipt
    if not isinstance(supplied, dict) or not supplied:
        return (None, 'DefectSpec requires the complete engine-resolved receipt')
    match = _DEFECT_SPEC_LOCATOR_RE.fullmatch(str(step.source.ref or '').strip())
    if match is None:
        return (None, 'DefectSpec source.ref must be defect:<backend>:<ticket-id>:<title|description>')
    locator_backend, locator_ticket_id, field = match.groups()
    top_keys = {'schema', 'status', 'eligible', 'authority_group', 'reason', 'ticket_number', 'source_sha256', 'source_content_sha256', 'source_context', 'selection', 'ticket', 'projection', 'projection_sha256', 'candidates', 'lookup'}
    if set(supplied) != top_keys:
        return (None, 'DefectSpec resolver receipt fields are not closed')
    ticket = supplied.get('ticket')
    projection = supplied.get('projection')
    lookup = supplied.get('lookup')
    selection = supplied.get('selection')
    ticket_keys = {'backend', 'ticket_id', 'doc_type', 'product', 'status', 'affected_versions', 'fixed_versions', 'ticket_sha256'}
    projection_keys = {'authority_group', 'backend', 'ticket_id', 'doc_type', 'product', 'status', 'affected_versions', 'fixed_versions', 'title', 'description'}
    selection_keys = {'reason', 'score', 'title_score', 'semantic_score', 'runner_up_score', 'margin'}
    if supplied.get('schema') != _DEFECT_SPEC_RECEIPT_SCHEMA or supplied.get('status') != 'resolved' or supplied.get('eligible') is not True or (supplied.get('authority_group') != 'spec') or (not isinstance(ticket, dict)) or (set(ticket) != ticket_keys) or (not isinstance(projection, dict)) or (set(projection) != projection_keys) or (not isinstance(selection, dict)) or (set(selection) != selection_keys) or (not isinstance(lookup, dict)) or (not isinstance(supplied.get('candidates'), list)):
        return (None, 'DefectSpec resolver receipt is not an eligible resolved declaration')
    from cex_core.engine.defect_spec_source import defect_backend_lookup_is_sealable
    if not defect_backend_lookup_is_sealable(lookup, ticket_id=str(supplied.get('ticket_number') or '')):
        return (None, 'DefectSpec resolver backend closure is incomplete')
    ticket_backend = str(ticket.get('backend') or '').strip().lower()
    ticket_id = str(ticket.get('ticket_id') or '').strip()
    ticket_sha = str(ticket.get('ticket_sha256') or '')
    source_sha = str(supplied.get('source_sha256') or '')
    source_content_sha = str(supplied.get('source_content_sha256') or '')
    source_context = supplied.get('source_context')
    if ticket_backend != locator_backend or ticket_id != locator_ticket_id or str(projection.get('backend') or '').strip().lower() != ticket_backend or (str(projection.get('ticket_id') or '').strip() != ticket_id) or (projection.get('authority_group') != 'spec') or any((projection.get(key) != ticket.get(key) for key in ('doc_type', 'product', 'status', 'affected_versions', 'fixed_versions'))) or (re.fullmatch('[0-9a-f]{64}', ticket_sha) is None) or (re.fullmatch('[0-9a-f]{64}', source_sha) is None) or (re.fullmatch('[0-9a-f]{64}', source_content_sha) is None) or (not isinstance(source_context, dict)) or (str(supplied.get('projection_sha256') or '') != _canonical_json_sha256(projection)):
        return (None, 'DefectSpec locator or resolver identity drift')
    declared = projection.get(field)
    if not isinstance(declared, str) or not declared.strip():
        return (None, 'DefectSpec selected declaration field is empty')
    if contains_prohibited_declaration(declared):
        return (None, 'DefectSpec actual/reproduction/log/comment text cannot sign expected')
    if require_value_match and step.G != declared:
        return (None, 'DefectSpec expected value must byte-match the selected safe projection field')
    try:
        source_scope = output_scope()
    except PermissionError:
        return (None, 'DefectSpec source scope is unavailable')
    source_root = scope_bucket(WORKSPACE_INPUTS, scope=source_scope)
    source_current = False
    source_budget_exceeded = False
    source_candidates_seen = 0
    source_bytes_seen = 0
    try:
        for candidate_path in source_root.rglob('*'):
            source_candidates_seen += 1
            if source_candidates_seen > _DEFECT_SPEC_MAX_SOURCE_CANDIDATES:
                source_budget_exceeded = True
                break
            try:
                candidate_bytes = read_regular_nofollow(candidate_path, error_type=OSError, invalid_message='DefectSpec source path is invalid', directory_message='DefectSpec source directory is unavailable', open_message='DefectSpec source is unavailable or is a symlink', bounds_message='DefectSpec source is not a bounded regular file', changed_message='DefectSpec source changed while being read', max_bytes=_DEFECT_SPEC_MAX_SOURCE_BYTES, min_bytes=1, trusted_root=source_root, require_current_uid=True)
            except OSError:
                continue
            assert isinstance(candidate_bytes, bytes)
            source_bytes_seen += len(candidate_bytes)
            if source_bytes_seen > _DEFECT_SPEC_MAX_SOURCE_TOTAL_BYTES:
                source_budget_exceeded = True
                break
            if hashlib.sha256(candidate_bytes).hexdigest() == source_sha:
                if not validate_source_context_binding(source_bytes=candidate_bytes, source_sha256=source_sha, source_context=source_context, source_content_sha256=source_content_sha):
                    return (None, 'DefectSpec sealed source context drift')
                source_current = True
                break
    except OSError:
        source_current = False
    if source_budget_exceeded:
        return (None, 'DefectSpec sealed source search budget exceeded')
    if not source_current:
        return (None, 'DefectSpec sealed source identity drift')
    defect_dir = 'zentao' if ticket_backend == 'zentao_story' else ticket_backend
    ticket_path = WORKSPACE_DEFECTS / defect_dir / f'{ticket_id}.json'
    try:
        ticket_bytes = read_regular_nofollow(ticket_path, error_type=OSError, invalid_message='DefectSpec ticket path is invalid', directory_message='DefectSpec ticket directory is unavailable', open_message='DefectSpec ticket is unavailable or is a symlink', bounds_message='DefectSpec ticket is not a bounded regular file', changed_message='DefectSpec ticket changed while being read', max_bytes=_DEFECT_SPEC_MAX_TICKET_BYTES, min_bytes=2, trusted_root=WORKSPACE_DEFECTS, require_current_uid=True)
        assert isinstance(ticket_bytes, bytes)
        validate_json_budget(ticket_bytes, error_type=OSError, message='DefectSpec current ticket exceeds JSON structure budget', max_depth=_DEFECT_SPEC_MAX_TICKET_JSON_DEPTH, max_tokens=_DEFECT_SPEC_MAX_TICKET_JSON_TOKENS)
        current_ticket = json.loads(ticket_bytes.decode('utf-8'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return (None, 'DefectSpec current ticket is unreadable')
    if not isinstance(current_ticket, dict):
        return (None, 'DefectSpec current ticket is malformed')
    from cex_core.engine.defect_spec_source import build_defect_spec_candidate, canonical_ticket_payload_sha256, scrub_declaration_text
    candidate_keys = {'backend', 'ticket_id', 'ticket_sha256', 'title', 'claimable_declaration', 'declaration_block_reason', 'score', 'title_score', 'semantic_score'}
    selected_candidates = 0
    for candidate in supplied['candidates']:
        if not isinstance(candidate, dict) or set(candidate) != candidate_keys:
            return (None, 'DefectSpec resolver candidate projection is not closed')
        scores = (candidate.get('score'), candidate.get('title_score'), candidate.get('semantic_score'))
        if str(candidate.get('backend') or '').strip().lower() not in {'bugzilla', 'zentao', 'zentao_story'} or not str(candidate.get('ticket_id') or '').strip() or re.fullmatch('[0-9a-f]{64}', str(candidate.get('ticket_sha256') or '')) is None or (not isinstance(candidate.get('claimable_declaration'), bool)) or any((isinstance(score, bool) or not isinstance(score, (int, float)) or score < 0 or (score > 1) for score in scores)) or (scrub_declaration_text(candidate.get('title'), limit=1000) != candidate.get('title')) or (scrub_declaration_text(candidate.get('declaration_block_reason'), limit=256) != candidate.get('declaration_block_reason')):
            return (None, 'DefectSpec resolver candidate projection is invalid')
        if candidate.get('backend') == ticket_backend and candidate.get('ticket_id') == ticket_id and (candidate.get('ticket_sha256') == ticket_sha):
            selected_candidates += 1
            if candidate.get('claimable_declaration') is not True:
                return (None, 'DefectSpec selected candidate is not claimable')
    if selected_candidates != 1:
        return (None, 'DefectSpec selected ticket is absent or duplicated in candidates')
    untrusted_runtime_keys = {'_resolver_backend_hint', '_ticket_file_sha256', '_ticket_file_sha256_verified', '_ticket_payload_sha256', 'defect_spec_candidate'}
    current_ticket_untrusted_fields_removed = {str(key): value for key, value in current_ticket.items() if str(key) not in untrusted_runtime_keys}
    current_canonical = build_defect_spec_candidate(current_ticket_untrusted_fields_removed, backend_hint=ticket_backend)
    current_with_file_identity = dict(current_ticket_untrusted_fields_removed)
    current_with_file_identity['_ticket_file_sha256'] = hashlib.sha256(ticket_bytes).hexdigest()
    current_with_file_identity['_ticket_payload_sha256'] = canonical_ticket_payload_sha256(current_ticket)
    current_with_file_identity['_ticket_file_sha256_verified'] = True
    current_file_bound = build_defect_spec_candidate(current_with_file_identity, backend_hint=ticket_backend)
    current = current_file_bound if current_file_bound.get('ticket_sha256') == ticket_sha else current_canonical
    if current.get('claimable_declaration') is not True or current.get('declaration_block_reason') or current.get('ticket_sha256') != ticket_sha or any((current.get(key) != ticket.get(key) for key in ('backend', 'ticket_id', 'doc_type', 'product', 'status', 'affected_versions', 'fixed_versions'))) or any((current.get(key) != projection.get(key) for key in ('backend', 'ticket_id', 'doc_type', 'product', 'status', 'affected_versions', 'fixed_versions', 'title', 'description'))):
        return (None, 'DefectSpec current ticket identity or declaration drift')
    from cex_core.engine.ist_core.tools.knowledge.kb_bug_search import _current_local_defect_lookup
    current_lookup = _current_local_defect_lookup(str(supplied.get('ticket_number') or ''))
    if json.dumps(current_lookup, ensure_ascii=False, sort_keys=True, separators=(',', ':')) != json.dumps(lookup, ensure_ascii=False, sort_keys=True, separators=(',', ':')):
        return (None, 'DefectSpec candidate inventory drift')
    resolution_seal_error = _defect_spec_resolution_seal(supplied, create=False)
    if resolution_seal_error:
        return (None, resolution_seal_error)
    return (dict(supplied), '')

def validate_defect_spec_claim(claim: Any, *, autoid: str='', expectation_id: str='', semantic_key: str='') -> tuple[dict[str, Any] | None, str]:
    """验证 pending DefectSpec 自然语言声明。

    claim 只保留 resolver 安全投影的已选字段；后续 F/G 可以是
    编译后的可执行形态，但权威类型始终是 DefectSpec。
    """
    if not isinstance(claim, dict):
        return (None, 'DefectSpec claim must be an object')
    body_keys = {'schema', 'kind', 'autoid', 'expectation_id', 'semantic_key', 'origin', 'source_text', 'locator', 'resolver_receipt', 'resolver_receipt_sha256'}
    if set(claim) != body_keys | {'claim_sha256'}:
        return (None, 'DefectSpec claim fields are not closed')
    body = {key: claim[key] for key in body_keys}
    claim_sha = str(claim.get('claim_sha256') or '')
    resolver = claim.get('resolver_receipt')
    resolver_sha = str(claim.get('resolver_receipt_sha256') or '')
    if not accepts_schema(claim.get('schema'), 'ist.defect-spec-claim') or claim.get('kind') != 'DefectSpec' or (not str(claim.get('autoid') or '').strip()) or (not str(claim.get('expectation_id') or '').strip()) or (not str(claim.get('semantic_key') or '').strip()) or (not str(claim.get('origin') or '').strip()) or (not str(claim.get('source_text') or '').strip()) or (not str(claim.get('locator') or '').strip()) or (not isinstance(resolver, dict)) or (re.fullmatch('[0-9a-f]{64}', resolver_sha) is None) or (_canonical_json_sha256(resolver) != resolver_sha) or (re.fullmatch('[0-9a-f]{64}', claim_sha) is None) or (_canonical_json_sha256(body) != claim_sha) or (autoid and str(claim.get('autoid')) != autoid) or (expectation_id and str(claim.get('expectation_id')) != expectation_id) or (semantic_key and str(claim.get('semantic_key')) != semantic_key):
        return (None, 'DefectSpec claim identity drift')
    probe = StepIR(E='check_point', F='found', G=str(claim['source_text']), layer='V', source=StepSource(kind='defect_spec', ref=str(claim['locator']), receipt=dict(resolver)), expectation_id=str(claim['expectation_id']), semantic_key=str(claim['semantic_key']))
    rebuilt, error = _validate_defect_spec_expected_receipt(probe)
    if rebuilt is None:
        return (None, error)
    return (dict(claim), '')

def _validate_capability_xml_expected_receipt(step: StepIR) -> tuple[dict[str, Any] | None, str]:
    """在真实 G6 生成器落地前拒绝所有 CapabilityXml expected。

    当前命令树及其公开投影只声明命令和参数能力，不能证明某个断言的
    operator/value。调用方自报 ``producer/status`` 再给自身字段做摘要不构成
    权威收据；即使 XML 字节里碰巧出现相同文本，也不能替代按 locator 机械解析
    声明结构。未来接入引擎独占生成器时，应由生成器直接重建 claim 并验证其
    不可变代际，而不是恢复这里对调用方自报收据的信任。
    """
    return (None, 'CapabilityXml expected generation is unavailable; the current command-tree projection proves capability only and caller-supplied receipts are not authority')

def _derive_rule_config_literal_copy(source_input: dict[str, Any]) -> tuple[list[dict[str, str]] | None, str]:
    """config.literal-copy：配置字面值直拷为一条 check_point。"""
    if set(source_input) != {'operator', 'value'}:
        return (None, 'config literal-copy input requires exactly operator/value')
    operator = str(source_input.get('operator') or '').strip()
    value = source_input.get('value')
    if not operator or not isinstance(value, str):
        return (None, 'config literal-copy input is incomplete')
    return ([{'E': 'check_point', 'F': operator, 'G': value}], '')

def _derive_rule_config_fixture_literal_backref(source_input: dict[str, Any]) -> tuple[list[dict[str, str]] | None, str]:
    """config.fixture-literal-backref：回指前序 CONFIG 字面值的断言直拷。"""
    required = {'operator', 'value', 'fixture_kind', 'config_block_index', 'config_command_index'}
    if set(source_input) != required:
        return (None, 'fixture literal back-reference input fields are not closed')
    operator = str(source_input.get('operator') or '').strip()
    value = source_input.get('value')
    fixture_kind = str(source_input.get('fixture_kind') or '').strip()
    block_index = source_input.get('config_block_index')
    command_index = source_input.get('config_command_index')
    if not operator or not isinstance(value, str) or (not value) or (fixture_kind not in {'domain_name', 'text_value'}) or (not isinstance(block_index, int)) or isinstance(block_index, bool) or (block_index < 0) or (not isinstance(command_index, int)) or isinstance(command_index, bool) or (command_index < 0):
        return (None, 'fixture literal back-reference input is incomplete')
    return ([{'E': 'check_point', 'F': operator, 'G': value}], '')

def _derive_rule_capture_static_relation(source_input: dict[str, Any]) -> tuple[list[dict[str, str]] | None, str]:
    """capture.static-relation：两次观测的同/异关系 → found/not_found。"""
    if set(source_input) != {'relation'}:
        return (None, 'capture relation input requires exactly relation')
    relation = str(source_input.get('relation') or '').strip()
    operator = {'same': 'found', 'differs': 'not_found'}.get(relation)
    if operator is None:
        return (None, 'capture relation is outside the compiler grammar')
    return ([{'E': 'check_point', 'F': operator, 'G': ''}], '')

def _derive_rule_capture_static_reference(source_input: dict[str, Any]) -> tuple[list[dict[str, str]] | None, str]:
    """capture.static-reference：H 寄存器引用断言的算子直拷。"""
    if set(source_input) != {'operator', 'register'}:
        return (None, 'capture reference input requires exactly operator/register')
    operator = str(source_input.get('operator') or '').strip()
    register = str(source_input.get('register') or '').strip()
    if not operator or not register:
        return (None, 'capture reference input is incomplete')
    return ([{'E': 'check_point', 'F': operator, 'G': ''}], '')

def _derive_rule_membership_literal_set(source_input: dict[str, Any]) -> tuple[list[dict[str, str]] | None, str]:
    """membership.literal-set：成员集合声明 → 锚定集合正则的 found/not_found。"""
    from cex_core.engine.case_compiler.membership_assertion import expand_membership_step
    expanded, error = expand_membership_step({'E': 'check_point', 'F': 'member', 'member': source_input})
    if error or not isinstance(expanded, dict):
        return (None, error or 'membership derivation did not produce an output')
    return ([{'E': str(expanded.get('E') or ''), 'F': str(expanded.get('F') or ''), 'G': str(expanded.get('G') or '')}], '')

def _derive_rule_status_exit_code(source_input: dict[str, Any]) -> tuple[list[dict[str, str]] | None, str]:
    """status.exit-code：成功极性 → 退出码 0；失败极性 → 探针工具的传输层失败退出码类。"""
    keys = set(source_input)
    if keys not in ({'expect'}, {'expect', 'probe', 'codes'}):
        return (None, 'exit-status input requires exactly expect, or expect+probe+codes for failure')
    codes = source_input.get('codes') or ()
    if 'codes' in keys and (not isinstance(codes, list)):
        return (None, 'exit-status codes must be a list of positive integers')
    output, error = exit_status_assertion(str(source_input.get('expect') or ''), probe=str(source_input.get('probe') or ''), codes=tuple(codes))
    return ([output] if output is not None else None, error)

def _derive_rule_distribution_interval(source_input: dict[str, Any]) -> tuple[list[dict[str, str]] | None, str]:
    """distribution.interval：分布声明 → 每桶一条锚定区间正则的 found。"""
    from cex_core.engine.case_compiler.distribution_assertion import expand_distribution_step
    expanded, error = expand_distribution_step({'E': 'check_point', 'F': 'dist', 'dist': source_input})
    if error or not isinstance(expanded, list):
        return (None, error or 'distribution derivation did not produce outputs')
    return ([{'E': str(item.get('E') or ''), 'F': str(item.get('F') or ''), 'G': str(item.get('G') or '')} for item in expanded], '')
_CONFIG_BINDING_RULE_HANDLERS = {'config.literal-copy': _derive_rule_config_literal_copy, 'config.fixture-literal-backref': _derive_rule_config_fixture_literal_backref, 'capture.static-relation': _derive_rule_capture_static_relation, 'capture.static-reference': _derive_rule_capture_static_reference, 'distribution.interval': _derive_rule_distribution_interval, 'membership.literal-set': _derive_rule_membership_literal_set, 'status.exit-code': _derive_rule_status_exit_code}

def _derive_config_binding_outputs(*, source_kind: str, rule_id: str, source_input: dict[str, Any]) -> tuple[list[dict[str, str]] | None, str]:
    """只从独立结构化输入复算 expected tuple，不读取设备 actual。"""
    if rule_id not in _CONFIG_BINDING_RULES.get(source_kind, frozenset()):
        return (None, 'derivation rule is not registered for source.kind')
    handler = _CONFIG_BINDING_RULE_HANDLERS.get(rule_id)
    if handler is None:
        return (None, 'derivation rule has no compiler implementation')
    return handler(source_input)
_GENERATOR_BINDING = 'rule-logic-ast-v1'
_CONFIG_BINDING_RULE_LOGIC = {'config.literal-copy': (('main/case_compiler/provenance_ir.py', ('_derive_rule_config_literal_copy',)),), 'config.fixture-literal-backref': (('main/case_compiler/provenance_ir.py', ('_derive_rule_config_fixture_literal_backref',)),), 'capture.static-relation': (('main/case_compiler/provenance_ir.py', ('_derive_rule_capture_static_relation',)),), 'capture.static-reference': (('main/case_compiler/provenance_ir.py', ('_derive_rule_capture_static_reference',)),), 'distribution.interval': (('main/case_compiler/provenance_ir.py', ('_derive_rule_distribution_interval',)), ('main/case_compiler/distribution_assertion.py', ('expand_distribution_step',)), ('main/case_compiler/regex_anchor_proof.py', ('analyze_regex_anchors',))), 'membership.literal-set': (('main/case_compiler/provenance_ir.py', ('_derive_rule_membership_literal_set',)), ('main/case_compiler/membership_assertion.py', ('expand_membership_step',))), 'status.exit-code': (('main/case_compiler/provenance_ir.py', ('_derive_rule_status_exit_code',)), ('main/case_compiler/blocks.py', ('_EXIT_STATUS_EXPECTS',)))}

def _strip_docstrings(tree: ast.AST) -> None:
    """就地剥掉 docstring：文档串与注释同属非逻辑改动，不得影响语义指纹。"""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
                del body[0]

def _module_top_level(tree: ast.Module) -> dict[str, ast.AST]:
    """模块顶层名字 → 定义节点（函数/类/赋值）；import 语句不算逻辑单元。"""
    names: dict[str, ast.AST] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names[node.name] = node
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names[target.id] = node
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names[node.target.id] = node
    return names

def _referenced_names(node: ast.AST) -> set[str]:
    return {child.id for child in ast.walk(node) if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load)}

def _logic_closure(top_level: dict[str, ast.AST], entries: tuple[str, ...]) -> dict[str, ast.AST] | None:
    """从入口名字出发，沿模块内名字引用走到不动点——规则的完整逻辑闭包。

    闭包内的模块级定义全部进指纹；局部变量/内建名不在模块顶层，自然被排除。
    入口名字缺任何一个都失败关闭（返回 None），宁可拒铸也不签一份漏算的指纹。
    """
    if any((entry not in top_level for entry in entries)):
        return None
    closure: dict[str, ast.AST] = {}
    worklist = list(entries)
    while worklist:
        name = worklist.pop()
        if name in closure:
            continue
        node = top_level.get(name)
        if node is None:
            continue
        closure[name] = node
        worklist.extend(_referenced_names(node) - closure.keys())
    return closure

def _config_binding_generator_fingerprint(rule_id: str) -> tuple[str | None, str]:
    """从引擎当前源码现算规则逻辑指纹；任何一环缺失都失败关闭。

    外部引用账里出现未登记的**项目内**引用（``main.*``）或无法归类的引用，
    说明规则把逻辑缝进了指纹材料之外的模块——拒绝铸造/复验，迫使作者先把
    该模块登记进 ``_CONFIG_BINDING_RULE_LOGIC``。
    """
    analysis, error = _config_binding_logic_analysis(rule_id)
    if analysis is None:
        return (None, error)
    blocked = sorted((ref for ref in analysis['externals'] if ref.startswith('main.') or ref.startswith('::')))
    if blocked:
        return (None, 'derivation rule logic reaches unregistered external reference: ' + ', '.join(blocked))
    material: list[dict[str, str]] = []
    for path, closure in analysis['closures'].items():
        for name in sorted(closure):
            material.append({'path': path, 'name': name, 'ast': ast.dump(closure[name])})
    return (_canonical_json_sha256(material), '')
_BUILTIN_NAMES = frozenset(dir(builtins))

def _package_for_path(path: str) -> str:
    """单元文件路径 → 它所属包的 dotted 名（main/case_compiler/x.py → main.case_compiler）。"""
    parts = path[:-3].split('/') if path.endswith('.py') else path.split('/')
    return '.'.join(parts[:-1])

def _resolve_relative_import(package: str, level: int, module: str) -> str | None:
    """相对 import 归一化为绝对模块路径；超出包树根返回 None（下游失败关闭）。

    Python 语义：level=1 是当前包，level=2 上溯一层，依此类推；上溯超出顶层
    包在运行时本就是 ImportError，账上按无法归类处理。
    """
    parts = package.split('.') if package else []
    if level < 1 or level - 1 > len(parts) - 1:
        return None
    base = parts[:len(parts) - (level - 1)]
    if module:
        base = base + module.split('.')
    return '.'.join(base) if base else None

def _importfrom_module(node: ast.ImportFrom, package: str) -> str | None:
    """ImportFrom 来源模块的绝对形式；归一化不了的一律 None（下游按 ``::name`` 失败关闭）。

    ``from . import x``（module=None）的名字指向包属性/子模块，形态歧义，
    同样返回 None——不记账则下游查无来源，按 ``::name`` 失败关闭，方向安全。
    """
    if node.level == 0:
        return node.module
    if node.module is None:
        return None
    return _resolve_relative_import(package, node.level, node.module)

def _module_import_bindings(tree: ast.Module, package: str) -> dict[str, str]:
    """模块顶层 import 绑定：本地名 → 来源（``re`` 或 ``pkg.mod::name``）。

    相对 import（``from .mod import y``）先按单元包归一化成绝对形式再记账——
    它只是绝对拼写的另一种写法：指向已登记模块的相对拼写同样算已解析，
    指向未登记项目模块的相对拼写归一化后照旧以 ``main.`` 开头进运行时闸。
    """
    bindings: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname or alias.name.split('.')[0]
                bindings[local] = alias.name
        elif isinstance(node, ast.ImportFrom):
            module = _importfrom_module(node, package)
            if module is None:
                continue
            for alias in node.names:
                bindings[alias.asname or alias.name] = f'{module}::{alias.name}'
    return bindings

def _function_import_bindings(node: ast.AST, package: str) -> dict[str, str]:
    """函数/闭包节点体内 import 绑定（局部）：本地名 → 来源（相对拼写已归一化）。"""
    bindings: dict[str, str] = {}
    for child in ast.walk(node):
        if isinstance(child, ast.Import):
            for alias in child.names:
                local = alias.asname or alias.name.split('.')[0]
                bindings[local] = alias.name
        elif isinstance(child, ast.ImportFrom):
            module = _importfrom_module(child, package)
            if module is None:
                continue
            for alias in child.names:
                bindings[alias.asname or alias.name] = f'{module}::{alias.name}'
    return bindings

def _assign_referenced_names(node: ast.AST) -> set[str]:
    """模块级赋值节点内 Load 的名字，剔除节点内部绑定的名（推导式变量等）。"""
    loads = {child.id for child in ast.walk(node) if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load)}
    bound = {child.id for child in ast.walk(node) if isinstance(child, ast.Name) and isinstance(child.ctx, (ast.Store, ast.Del))}
    bound |= {child.arg for child in ast.walk(node) if isinstance(child, ast.arg)}
    return loads - bound

def _child_table(table: symtable.SymbolTable, name: str) -> symtable.SymbolTable | None:
    for child in table.get_children():
        if child.get_name() == name and child.get_type() in ('function', 'class'):
            return child
    return None

def _walk_tables(table: symtable.SymbolTable) -> list[symtable.SymbolTable]:
    """该表与全部后代表（lambda/嵌套 def 的全局引用也要分类）。"""
    tables = [table]
    for child in table.get_children():
        tables.extend(_walk_tables(child))
    return tables

def _config_binding_logic_analysis(rule_id: str) -> tuple[dict[str, Any] | None, str]:
    """解析一条规则的全部登记单元：模块内逻辑闭包 + 未解析外部引用账。

    外部引用＝闭包代码 Load 到、但既不在闭包内也不是内建名的名字（函数内
    from-import 的名字、模块顶层 import 别名都算进来；``from __future__
    import annotations`` 下注解名不被 symtable 记为引用，天然除外）。相对
    import 先按单元包归一化为绝对形式再记账——``from .mod import y`` 与
    绝对拼写同判。指向**已登记单元闭包成员**的 import 算已解析——它的
    实现已在指纹材料里；解析依据是 import 的来源模块，来源被改指未登记
    模块照样进账。返回
    ``{"closures": {path: {name: node}}, "externals": frozenset(qualified)}``；
    分类覆盖现役形态（函数 + 简单模块级常量），拿不准的一律按 ``::name``
    进账失败关闭，宁可误拦也不漏账。覆盖面边界：``exec``/``__import__``/
    ``getattr`` 字符串这类**动态**引用在静态分析里根本不产生名字，不在
    本闸覆盖面—— ``::name`` 兜底只盖得住「有名字但归不了类」的形态。
    """
    units = _CONFIG_BINDING_RULE_LOGIC.get(rule_id)
    if units is None:
        return (None, 'derivation rule has no registered logic units')
    per_unit: dict[str, dict[str, Any]] = {}
    for path, entries in units:
        source_file = _CODE_ROOT / path
        try:
            text = source_file.read_text(encoding='utf-8')
            tree = ast.parse(text)
            table = symtable.symtable(text, path, 'exec')
        except (OSError, SyntaxError, UnicodeDecodeError):
            return (None, 'derivation generator source is unavailable')
        _strip_docstrings(tree)
        closure = _logic_closure(_module_top_level(tree), entries)
        if closure is None:
            return (None, 'derivation generator logic unit is missing')
        per_unit[path] = {'tree': tree, 'closure': closure, 'table': table, 'package': _package_for_path(path), 'module_imports': _module_import_bindings(tree, _package_for_path(path))}

    def _resolve_import(source: str) -> bool:
        """from-import 来源 ``pkg.mod::name`` 指向任一登记单元的闭包成员 ⇒ 已解析。"""
        if '::' not in source:
            return False
        module, _, name = source.rpartition('::')
        unit = per_unit.get(module.replace('.', '/') + '.py')
        return unit is not None and name in unit['closure']
    externals: set[str] = set()
    for path, unit in per_unit.items():
        closure = unit['closure']
        module_imports = unit['module_imports']
        for name, node in closure.items():
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                function_table = _child_table(unit['table'], name)
                if function_table is None:
                    externals.add(f'::{name}')
                    continue
                import_bindings = _function_import_bindings(node, unit['package'])
                for table in _walk_tables(function_table):
                    for symbol in table.get_symbols():
                        symbol_name = symbol.get_name()
                        if symbol.is_imported():
                            if not symbol.is_referenced():
                                continue
                            source = import_bindings.get(symbol_name, '')
                            if not source:
                                externals.add(f'::{symbol_name}')
                            elif not _resolve_import(source):
                                externals.add(source)
                        elif symbol.is_global() and symbol.is_referenced():
                            if symbol_name in closure:
                                continue
                            if symbol_name in module_imports:
                                source = module_imports[symbol_name]
                                if not _resolve_import(source):
                                    externals.add(source)
                            elif symbol_name not in _BUILTIN_NAMES:
                                externals.add(f'::{symbol_name}')
            else:
                for ref in _assign_referenced_names(node):
                    if ref in closure:
                        continue
                    if ref in module_imports:
                        source = module_imports[ref]
                        if not _resolve_import(source):
                            externals.add(source)
                    elif ref not in _BUILTIN_NAMES:
                        externals.add(f'::{ref}')
    return ({'closures': {path: unit['closure'] for path, unit in per_unit.items()}, 'externals': frozenset(externals)}, '')

def derivation_output_count(*, source_kind: str, rule_id: str, source_input: dict[str, Any]) -> tuple[int | None, str]:
    """按注册生成器复算该派生输入会产出几行断言（= 扇出组的大小）。

    规则侧要把 ``OBSERVE_DIST`` 扇出的 N 行归回**一个** claim，组大小必须由
    ``source_input`` 重跑生成器算出，不能读调用方自报的行数：同一个
    ``expectation_id`` 写在两条参数逐字节相同的 dist 上会得到 6 行、ordinal 序列
    ``[0,1,2,0,1,2]``，按自报行数就成了一个"合法的 6 行组"。

    只暴露条数，不返回派生内容——内容的权威仍是
    ``build_config_binding_derivation_receipt`` 的逐字节重建。
    """
    if not isinstance(source_input, dict):
        return (None, 'config binding source_input must be an object')
    outputs, error = _derive_config_binding_outputs(source_kind=str(source_kind or '').strip(), rule_id=str(rule_id or '').strip(), source_input=source_input)
    if outputs is None:
        return (None, error)
    return (len(outputs), '')
_CAPTURE_REGISTER_RULES = frozenset({'capture.static-relation', 'capture.static-reference'})

def _capture_register_final_form_matches(actual: Mapping[str, Any], derived: Mapping[str, Any], rule_id: str) -> bool:
    """H 寄存器引用断言的卷面终形等价：derived=found ≡ actual=abs_found。

    emit_xlsx_tool 在 check_point 引用 H 寄存器时把 found 归一成 abs_found 并写回
    steps（内部工单：backfill_efg 从同一列表回填 E/F/G，卷面与 provenance 必须同形）。
    框架 found 把期望值当正则、abs_found 当字面；寄存器捕获值含正则元字符，
    只有字面匹配语义成立——所以这是同一条断言的机械形（收据铸造时）与终形
    （emit 归一化后）两种形态，不是身份漂移。

    闭集只有 capture.static-* 两条规则：它们的输出按构造恒为 H 寄存器引用，
    等价可以从规则结构机械得出。反方向不外溢——裸 abs_found（无寄存器）是
    字面匹配语义、config/distribution/membership/status 派生的 found 是 G 列
    正则锚定，两者与 found 都不是同一断言，不进本等价。
    """
    if rule_id not in _CAPTURE_REGISTER_RULES:
        return False
    return actual.get('E') == derived.get('E') and actual.get('G') == derived.get('G') and (str(actual.get('F') or '') == 'abs_found') and (str(derived.get('F') or '') == 'found')

def build_config_binding_derivation_receipt(*, source_kind: str, recipe_id: str, rule_id: str, source_input: dict[str, Any], output_step: dict[str, Any], output_ordinal: int=0) -> tuple[dict[str, Any] | None, str]:
    """由结构化输入和注册规则铸造可独立复算的 ConfigBinding receipt。

    ``generator.sha256`` 锚的是规则逻辑的语义指纹（``_GENERATOR_BINDING``），
    由引擎从自己的源码现算——收据只是声明，复验时重新现算比对，调用方自报的
    hash 不能给自己背书。
    """
    kind = str(source_kind or '').strip()
    rule = str(rule_id or '').strip()
    if kind not in _DERIVED_SOURCE_KINDS:
        return (None, 'source.kind is not a ConfigBinding derivation kind')
    if not isinstance(source_input, dict):
        return (None, 'config binding source_input must be an object')
    outputs, error = _derive_config_binding_outputs(source_kind=kind, rule_id=rule, source_input=source_input)
    if outputs is None:
        return (None, error)
    if not isinstance(output_ordinal, int) or isinstance(output_ordinal, bool) or output_ordinal < 0 or (output_ordinal >= len(outputs)):
        return (None, 'derivation output ordinal is invalid')
    derived = outputs[output_ordinal]
    actual_output = {'E': str(output_step.get('E') or ''), 'F': str(output_step.get('F') or ''), 'G': str(output_step.get('G') or '')}
    if actual_output != derived and (not _capture_register_final_form_matches(actual_output, derived, rule)):
        return (None, 'derived output tuple does not match the final assertion')
    source_input_sha = _canonical_json_sha256(source_input)
    stable_recipe_id = str(recipe_id or '').strip() or f'{rule}:{source_input_sha[:24]}'
    generator_path = _CONFIG_BINDING_GENERATORS[rule]
    generator_sha, fingerprint_error = _config_binding_generator_fingerprint(rule)
    if generator_sha is None:
        return (None, fingerprint_error)
    output_sha = _canonical_json_sha256(derived)
    material = {'schema': _CONFIG_BINDING_DERIVATION_SCHEMA, 'source_kind': kind, 'recipe_id': stable_recipe_id, 'rule_id': rule, 'generator': {'path': generator_path, 'sha256': generator_sha, 'schema': _CONFIG_BINDING_DERIVATION_SCHEMA, 'binding': _GENERATOR_BINDING}, 'source_input': source_input, 'source_input_sha256': source_input_sha, 'output_ordinal': output_ordinal, 'derived_output': derived, 'derived_output_sha256': output_sha}
    return ({**material, 'receipt_sha256': _canonical_json_sha256(material), 'status': 'compiler_recomputed'}, '')
_LEGACY_GENERATOR_KEYS = frozenset({'path', 'sha256', 'schema'})
_DERIVATION_RECEIPT_DRIFT = 'ConfigBinding derivation receipt identity drift'
_DERIVATION_ANCHOR_KEYS = ('schema', 'source_kind', 'recipe_id', 'rule_id', 'source_input', 'source_input_sha256', 'output_ordinal', 'derived_output', 'derived_output_sha256', 'status')

def reconcile_config_binding_derivation_receipt(supplied: Any, rebuilt: dict[str, Any] | None) -> tuple[dict[str, Any] | None, str]:
    """派生收据复验的唯一入口：新形态逐字节相等才直接通过。

    不一致时只给旧 file-bytes 形态一条显式迁移通道（语义重算一致则按新绑定
    重铸，不一致则显式退役）；其余任何不一致都是 identity drift，失败关闭。
    返回的收据以引擎重建值为准——调用方自报的 receipt 永远只是待核对的输入。
    """
    if not isinstance(supplied, dict) or not isinstance(rebuilt, dict):
        return (None, _DERIVATION_RECEIPT_DRIFT)
    if supplied == rebuilt:
        return (rebuilt, '')
    return _migrate_legacy_derivation_receipt(supplied, rebuilt)

def _migrate_legacy_derivation_receipt(supplied: dict[str, Any], rebuilt: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    """旧形态（generator.sha256 = 生成器文件字节）收据的显式迁移判定。

    迁移判据＝语义重算：旧收据除 generator.sha256/receipt_sha256/binding 外的
    全部语义锚必须逐字节等于引擎当前重建值——即同一 rule_id + source_input 在
    现役规则逻辑下仍派生出同一 derived_output；且旧收据自身的 receipt_sha256
    必须与其 material 自洽（证明它确由铸造算法产出，不是手工拼的）。通过则按
    新绑定形态重铸返回（惰性迁移，落盘即完成换绑）；不通过则显式退役——返回
    带 retired 字样的可见错误，绝不静默放行。旧收据里的文件字节 hash 无从复得，
    不作为判据参与任何一边的判定。
    """
    generator = supplied.get('generator')
    if not isinstance(generator, dict) or set(generator) != _LEGACY_GENERATOR_KEYS:
        return (None, _DERIVATION_RECEIPT_DRIFT)
    rebuilt_generator = rebuilt.get('generator')
    if not isinstance(rebuilt_generator, dict):
        return (None, _DERIVATION_RECEIPT_DRIFT)
    if set(supplied) != set(rebuilt):
        return (None, _DERIVATION_RECEIPT_DRIFT)
    if generator.get('path') != rebuilt_generator.get('path') or generator.get('schema') != rebuilt_generator.get('schema'):
        return (None, _DERIVATION_RECEIPT_DRIFT)
    for key in _DERIVATION_ANCHOR_KEYS:
        if supplied.get(key) != rebuilt.get(key):
            return (None, 'ConfigBinding derivation receipt retired: the legacy file-bytes receipt no longer reproduces under the current rule logic (semantic anchors differ); recompile to mint a new receipt')
    material = {key: value for key, value in supplied.items() if key not in ('receipt_sha256', 'status')}
    if supplied.get('receipt_sha256') != _canonical_json_sha256(material):
        return (None, 'ConfigBinding derivation receipt retired: the legacy receipt self-hash does not match its own material')
    _logger.info('ConfigBinding derivation receipt migrated from file-bytes binding to %s: rule_id=%s recipe_id=%s', _GENERATOR_BINDING, supplied.get('rule_id'), supplied.get('recipe_id'))
    return (rebuilt, '')
_INTENT_SELECTOR_RE = re.compile('^u\\d+:\\d{18}:\\d+:\\d+$')

def _intent_selectors(payload: Any) -> list[str]:
    """intent.json 里实际可当 selector 用的键（expectation_id 形态），去重按序。"""
    found: list[str] = []
    stack = [payload]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            for key, value in item.items():
                if isinstance(key, str) and _INTENT_SELECTOR_RE.fullmatch(key):
                    if key not in found:
                        found.append(key)
                stack.append(value)
        elif isinstance(item, list):
            stack.extend(item)
    return sorted(found)

def _step_redeems_author_claim(step: 'StepIR') -> bool:
    """这一步能不能兑现 pending Author claim：只有断言步能。

    intent 是 Author 期望值的签发通道，盖了章的 expectation_id 经 pending Author
    claim 落到带 expectation_id/semantic_key 的 check_point 断言上。命令步（配置、
    观测、test_env 派发）没有期望值可签，出处要指它自己真查过的那份材料。
    """
    return step.E.strip() == 'check_point'

def _intent_on_non_assertion(step: 'StepIR', locator: str, *, selector_resolves: bool) -> str:
    """命令步想拿盖章身份当出处时的拒绝文案：说清该改哪一步、该换成什么。

    用错来源类别 ≠ 断言缺字段（2026-09-03 slb5_pipeline4 案 <case> 实证）：旧代码
    把这条判在身份分支之后，配置步本来就没有 semantic_key，于是回「this assertion
    carries no expectation_id」，worker 照着去改断言身份，越改越不对——单批 49 次
    拒收里 28 次是这一条。

    ``selector_resolves=False`` 那一支同源（<batch>/4/5 + ipo 四批实证）：
    `intent:step:1` 这种自造 selector 此前命中的是「selector 不存在，可选的是
    u1:<autoid>:…」，而该步是命令步——把「换个 selector」当修法，下一轮换成真
    expectation_id 再撞上面那条。四批里落在命令步上的 selector 拒绝 280 次（占该子
    因 87%）。所以命令步上 selector 解析不出来时，主句先说命令步这件事，并且不列
    候选 selector：列出来就是引擎自己把写手指回同一个错位置。
    """
    if selector_resolves:
        lead = f'E={step.E!r} is a command step, not an assertion, so it cannot take source.kind=intent to redeem an Author claim (locator {locator})'
    else:
        missing = 'source.kind=intent carries no locator' if not locator else f'intent selector {locator!r} does not exist in intent.json'
        lead = f'{missing}, and E={step.E!r} is a command step, not an assertion, so it cannot take source.kind=intent to redeem an Author claim either'
    return f'{lead}: a stamped expectation_id resolves only through the pending Author claim, which compiles onto the check_point assertion that carries the minted expectation_id/semantic_key. Reaching for a different stamped selector does not fix this step. Give this command its own source — the locator of the material you actually consulted for it (for example the manual line or the footprint node that documents this command) — and keep the intent locator on the assertion that redeems the claim.'

def _json_contains_key(value: Any, key: str) -> bool:
    if isinstance(value, dict):
        return key in value or any((_json_contains_key(v, key) for v in value.values()))
    if isinstance(value, list):
        return any((_json_contains_key(v, key) for v in value))
    return False

def _json_values_for_key(value: Any, key: str) -> list[Any]:
    """返回 JSON 树中精确键名对应的值，不做文本或模糊匹配。"""
    matches: list[Any] = []
    if isinstance(value, dict):
        for current_key, current_value in value.items():
            if current_key == key:
                matches.append(current_value)
            matches.extend(_json_values_for_key(current_value, key))
    elif isinstance(value, list):
        for item in value:
            matches.extend(_json_values_for_key(item, key))
    return matches

def resolve_source_receipt(case: CaseProvenance, step: StepIR, *, outputs_root: Path | None=None) -> tuple[dict[str, Any] | None, str]:
    """把 provenance 指针解析成真实、带 SHA-256 的来源凭据。

    外部来源必须落到现有只读资产；内部确定性推导则绑定本案 E/F/G 快照。
    该函数不依据调用方自带 receipt 放行。
    """
    kind = str(step.source.kind or '')
    locator = str(step.source.ref or '').strip()
    if kind == 'manual':
        name, line_start, line_end = _line_locator(locator)
        path, source_root, error = _unique_named_file_across_roots((KNOWLEDGE_MANUAL, KNOWLEDGE_MARKDOWN), name, suffix='.md')
        if path is None:
            return (None, f'{error}. Manual refs use {_MANUAL_LOCATOR_SHAPE}; line ranges use a hyphen, comma-separated line lists are not supported, and distinct source locations must be split across steps')
        return _file_receipt(kind=kind, locator=locator, path=path, root=source_root or KNOWLEDGE_MARKDOWN, line_start=line_start, line_end=line_end)
    if kind == 'spec':
        name, line_start, line_end = _line_locator(locator)
        try:
            generation = resolve_active_spec_generation()
        except SpecGenerationUnavailable as exc:
            return (None, f'active spec generation is unavailable: {exc}')
        path, error = _unique_named_file(generation.docs, name, suffix='.md')
        if path is None:
            return (None, f'{error}. Spec refs use spec:<file-or-unique-stem>[:<line>|:<line-start>-<line-end>] against the active spec generation')
        receipt, receipt_error = _file_receipt(kind=kind, locator=locator, path=path, root=generation.docs, line_start=line_start, line_end=line_end)
        if receipt is None:
            return (None, receipt_error)
        receipt['generation_id'] = generation.generation_id
        receipt['manifest_sha256'] = generation.manifest_sha256
        return (receipt, '')
    if kind == 'defect_spec':
        supplied = step.source.receipt
        if not isinstance(supplied, dict):
            return (None, 'DefectSpec resolver receipt is unavailable')
        supplied_compilation = supplied.get('defect_spec_compilation')
        resolver_receipt = {key: value for key, value in supplied.items() if key != 'defect_spec_compilation'}
        root = Path(outputs_root) if outputs_root is not None else _scoped_outputs_root()
        autoid = str(case.autoid or '').strip()
        intent_candidate = root / autoid / 'intent.json'
        intent_path = _safe_file_under(intent_candidate, root) if autoid and Path(autoid).name == autoid else None
        payload: dict[str, Any] = {}
        if intent_path is not None:
            from cex_core.engine.case_compiler.contract_entry import ContractError, read_intent_json
            try:
                payload, _intent_bytes = read_intent_json(intent_candidate, trusted_root=root)
            except ContractError:
                return (None, 'DefectSpec stamped intent is unreadable')
        claims = payload.get('defect_spec_claims')
        claim = claims.get(step.expectation_id) if isinstance(claims, dict) and step.expectation_id else None
        if claim is None:
            if supplied_compilation is not None:
                return (None, 'DefectSpec compilation has no stamped claim')
            return _validate_defect_spec_expected_receipt(step, resolver_receipt=resolver_receipt)
        verified_claim, claim_error = validate_defect_spec_claim(claim, autoid=autoid, expectation_id=step.expectation_id, semantic_key=step.semantic_key)
        if verified_claim is None:
            return (None, claim_error)
        claim_resolver = verified_claim['resolver_receipt']
        if resolver_receipt != claim_resolver:
            return (None, 'DefectSpec resolver receipt drifted from stamped claim')
        rebuilt, resolver_error = _validate_defect_spec_expected_receipt(step, resolver_receipt=resolver_receipt, require_value_match=False)
        if rebuilt is None:
            return (None, resolver_error)
        if step.E.strip() != 'check_point' or not step.F.strip() or (not step.G):
            return (None, 'pending DefectSpec claim has no compiled F/G assertion')
        material = {'schema': 'ist.defect-spec-compilation', 'autoid': autoid, 'claim_sha256': str(verified_claim['claim_sha256']), 'resolver_receipt_sha256': str(verified_claim['resolver_receipt_sha256']), 'expectation_id': step.expectation_id, 'semantic_key': step.semantic_key, 'operator': step.F, 'value_sha256': hashlib.sha256(step.G.encode('utf-8')).hexdigest(), 'source_kind': 'defect_spec', 'source_ref': str(step.source.ref or '').strip(), 'status': 'compiled_pre_device'}
        compilation = {**material, 'receipt_sha256': _canonical_json_sha256(material)}
        if supplied_compilation is not None and supplied_compilation != compilation:
            return (None, 'DefectSpec compilation receipt identity drift')
        seal_error = _defect_spec_compilation_seal(compilation, create=False, allow_missing=True)
        if seal_error:
            return (None, seal_error)
        return ({**rebuilt, 'defect_spec_compilation': compilation}, '')
    if kind == 'capability_xml':
        return _validate_capability_xml_expected_receipt(step)
    if kind == 'footprint':
        name = locator.split('#', 1)[0].strip()
        if not name.endswith('.json'):
            name += '.json'
        path, error = _unique_named_file(KNOWLEDGE_FOOTPRINTS_NODES, name)
        if path is None:
            return (None, error)
        return _file_receipt(kind=kind, locator=locator, path=path, root=KNOWLEDGE_FOOTPRINTS)
    if kind == 'precedent':
        name = locator.split('#', 1)[0].strip()
        path, source_root, error = _unique_named_file_across_roots((KNOWLEDGE_VERIFIED_PACKAGES, KNOWLEDGE_FRAMEWORK_MIRROR), name, suffix='.xlsx')
        if path is None:
            return (None, error)
        return _file_receipt(kind=kind, locator=locator, path=path, root=source_root or KNOWLEDGE_VERIFIED_PACKAGES)
    if kind == 'env_facts':
        file_part, separator, selector = locator.partition('#')
        if separator:
            path, error = _unique_named_file(KNOWLEDGE_AUTO_ENV, file_part, suffix='.json')
        else:
            selector = file_part
            path, error = _unique_named_file(KNOWLEDGE_AUTO_ENV, 'network_topology.json')
        if path is None:
            return (None, error)
        if selector:
            try:
                payload = json.loads(path.read_text(encoding='utf-8'))
            except (OSError, json.JSONDecodeError) as exc:
                return (None, f'environment fact source is unreadable: {exc}')
            if not _json_contains_key(payload, selector):
                return (None, f'environment fact selector {selector!r} does not exist in {path.name}')
        return _file_receipt(kind=kind, locator=locator, path=path, root=KNOWLEDGE_AUTO_ENV, selector=selector)
    if kind == 'test_env_dispatch':
        if step.E.strip() != 'test_env':
            return (None, "test_env_dispatch is valid only for E='test_env'")
        dispatch_method = step.F.strip().lower()
        try:
            contract = load_excel_contract()
            allowed = enabled_fs_by_e(contract).get('test_env', frozenset())
            contract_digest = contract_sha256(contract)
        except ExcelContractError as exc:
            return (None, f'enabled Excel function contract is unavailable for test_env dispatch: {exc}')
        if not allowed:
            return (None, 'enabled Excel function contract has no test_env dispatch methods')
        if dispatch_method not in allowed:
            return (None, f'F={step.F!r} is not an enabled Excel-contract test_env dispatch method')
        canonical_locator = f'lib/env.py#Env.{dispatch_method}'
        if locator != canonical_locator:
            return (None, f'test_env_dispatch source.ref must equal the compiler-derived locator {canonical_locator!r}')
        dispatch_sources: list[dict[str, str]] = []
        for rel in _TEST_ENV_DISPATCH_SOURCES:
            source_digest = str(contract['source_hashes'].get(rel) or '')
            if not re.fullmatch('[0-9a-f]{64}', source_digest):
                return (None, f'enabled Excel function contract does not close dispatch source {rel!r}')
            dispatch_sources.append({'path': rel, 'sha256': source_digest})
        material = json.dumps({'E': 'test_env', 'F': dispatch_method, 'G': step.G, 'locator': canonical_locator, 'excel_contract_sha256': contract_digest, 'sources': dispatch_sources}, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
        return ({'kind': kind, 'locator': canonical_locator, 'excel_contract_sha256': contract_digest, 'dispatch_sources': dispatch_sources, 'step_sha256': hashlib.sha256(material).hexdigest(), 'status': 'mechanical_language_primitive'}, '')
    if kind == 'intent':
        root = Path(outputs_root) if outputs_root is not None else _scoped_outputs_root()
        autoid = str(case.autoid or '').strip()
        if not autoid or Path(autoid).name != autoid:
            return (None, 'case autoid cannot identify a safe intent source')
        intent_candidate = root / autoid / 'intent.json'
        path = _safe_file_under(intent_candidate, root)
        if path is None:
            return (None, f'no durable intent.json exists for autoid {autoid!r}')
        from cex_core.engine.case_compiler.contract_entry import ContractError, read_intent_json
        try:
            payload, intent_bytes = read_intent_json(intent_candidate, trusted_root=root)
        except ContractError:
            return (None, 'intent source is unreadable')
        if not locator or not _json_contains_key(payload, locator):
            if not _step_redeems_author_claim(step):
                return (None, _intent_on_non_assertion(step, locator, selector_resolves=False))
            offered = _intent_selectors(payload)
            hint = f"; intent.json offers {', '.join((repr(key) for key in offered[:4]))}" + (f' (+{len(offered) - 4} more)' if len(offered) > 4 else '') if offered else ''
            return (None, f'intent selector {locator!r} does not exist in intent.json{hint}')
        try:
            relative = path.relative_to(PROJECT_ROOT.resolve()).as_posix()
        except ValueError:
            relative = path.relative_to(root.resolve()).as_posix()
        receipt: dict[str, Any] = {'kind': kind, 'locator': locator, 'path': relative, 'sha256': hashlib.sha256(intent_bytes).hexdigest(), 'size': len(intent_bytes), 'selector': locator}
        author_claims = payload.get('author_claims')
        claim = author_claims.get(locator) if isinstance(author_claims, dict) else None
        if claim is None:
            return (receipt, '')
        if not isinstance(claim, dict):
            return (None, 'pending Author claim in intent.json is malformed')
        if not _step_redeems_author_claim(step):
            return (None, _intent_on_non_assertion(step, locator, selector_resolves=True))
        body_keys = {'schema', 'kind', 'autoid', 'expectation_id', 'semantic_key', 'origin', 'source_text', 'source_sha256'}
        if set(claim) != body_keys | {'claim_sha256'}:
            return (None, 'pending Author claim shape drifted in intent.json')
        body = {key: claim[key] for key in body_keys}
        claim_sha256 = str(claim.get('claim_sha256') or '')
        if not accepts_schema(claim.get('schema'), 'ist.author-claim') or claim.get('kind') != 'Author' or str(claim.get('autoid') or '') != autoid or (str(claim.get('expectation_id') or '') != locator) or (str(claim.get('semantic_key') or '') != step.semantic_key) or (not str(claim.get('origin') or '').strip()) or (not str(claim.get('source_text') or '').strip()) or (re.fullmatch('[0-9a-f]{64}', str(claim.get('source_sha256') or '')) is None) or (re.fullmatch('[0-9a-f]{64}', claim_sha256) is None) or (_canonical_json_sha256(body) != claim_sha256):
            if not step.semantic_key.strip():
                problem = 'this assertion carries no expectation_id/semantic_key — write the pair minted by the typed expectation contract onto the assertion itself (the asserts[] entry, or the E=check_point combinator); the pending Author claim stamped in intent.json is the authority to copy from'
            else:
                problem = "this assertion's identity does not match the pending Author claim stamped in intent.json — copy expectation_id and semantic_key from that claim byte-for-byte"
            return (None, problem)
        if not step.F.strip() or not step.G:
            return (None, 'pending Author claim has no compiled F/G assertion')
        material = {'schema': 'ist.author-compilation', 'claim_sha256': claim_sha256, 'expectation_id': locator, 'semantic_key': step.semantic_key, 'operator': step.F, 'value_sha256': hashlib.sha256(step.G.encode('utf-8')).hexdigest(), 'source_kind': kind, 'source_ref': locator, 'intent_sha256': str(receipt.get('sha256') or ''), 'status': 'compiled_pre_device'}
        receipt['author_compilation'] = {**material, 'receipt_sha256': _canonical_json_sha256(material)}
        return (receipt, '')
    if kind == 'skeleton':
        compile_ref = KNOWLEDGE_DATA_ROOT / 'compile_ref'
        name, line_start, line_end = _line_locator(locator)
        path, error = _unique_named_file(compile_ref, name)
        if path is None:
            return (None, error)
        return _file_receipt(kind=kind, locator=locator, path=path, root=compile_ref, line_start=line_start, line_end=line_end)
    if kind in _DERIVED_SOURCE_KINDS:
        supplied = step.source.receipt
        if not isinstance(supplied, dict) or not supplied:
            return (None, 'ConfigBinding derivation receipt is required')
        source_input = supplied.get('source_input')
        if not isinstance(source_input, dict):
            return (None, 'ConfigBinding derivation source_input is missing')
        rebuilt, error = build_config_binding_derivation_receipt(source_kind=kind, recipe_id=locator, rule_id=str(supplied.get('rule_id') or ''), source_input=source_input, output_step={'E': step.E, 'F': step.F, 'G': step.G}, output_ordinal=supplied.get('output_ordinal', 0))
        if rebuilt is None:
            return (None, error)
        return reconcile_config_binding_derivation_receipt(supplied, rebuilt)
    if kind == 'device_runtime':
        return ({'kind': kind, 'locator': locator, 'status': 'pending_on_device_fill'}, '')
    if kind == 'emit_auto' and step.E.strip() == 'time' and (step.F.strip() == 'sleep'):
        return ({'kind': kind, 'status': 'mechanical_language_primitive'}, '')
    return (None, f"source.kind={kind or 'unknown'} has no resolvable receipt")

def seal_defect_spec_compilations(case: CaseProvenance, *, outputs_root: Path | None=None) -> list[str]:
    """在成功编译终点发布 DefectSpec 的首次 F/G seal。

    调用前不信任旁挂 receipt，而是再次从盖章 intent、当前缺陷票与当前 F/G
    重建 compilation；ready（直接逐字声明）没有 compilation，故无需此 seal。
    """
    problems: list[str] = []
    for index, step in enumerate(case.steps):
        if str(step.source.kind or '') != 'defect_spec':
            continue
        receipt, error = resolve_source_receipt(case, step, outputs_root=outputs_root)
        if receipt is None:
            problems.append(f'step {index}: {error}')
            continue
        compilation = receipt.get('defect_spec_compilation')
        if compilation is None:
            step.source.receipt = receipt
            continue
        if not isinstance(compilation, dict):
            problems.append(f'step {index}: DefectSpec compilation receipt is malformed')
            continue
        seal_error = _defect_spec_compilation_seal(compilation, create=True)
        if seal_error:
            problems.append(f'step {index}: {seal_error}')
            continue
        step.source.receipt = receipt
    return problems
_DIRECTION_INPUT_KEYS: dict[str, str] = {'status.exit-code': 'expect', 'capture.static-relation': 'relation'}
_ASSERT_OPERATORS = frozenset({'found', 'not_found', 'abs_found', 'found_times'})
_NEGATIVE_ASSERT_OPERATORS = frozenset({'not_found'})
_EXPECTATION_DIRECTION_SEAL_SCHEMA = 'ist.expectation-direction-seal'

def direction_family(token: str) -> str:
    """方向令牌的载体族：``status.exit-code`` / ``capture.static-relation`` / ``operator``。

    同一判词换承载（退出码类 ↔ 框架算子）时两个令牌不同族，族间的极性没有可比的
    定义（`found "timed out"` 与 `expect=failure` 都能兑现「访问失败」），所以封印只在
    同族之内比对，跨族只是方法重编（11 章「冻结的只是方向，不是 F/G」）。
    """
    return str(token or '').split(':', 1)[0]

def _directions_by_family(tokens) -> dict[str, set[str]]:
    grouped: dict[str, set[str]] = {}
    for token in tokens or ():
        token = str(token or '').strip()
        if token:
            grouped.setdefault(direction_family(token), set()).add(token)
    return grouped

def direction_flip_families(sealed_tokens, current_tokens) -> list[str]:
    """首轮封印与本轮方向集之间真正翻面的载体族；空列表即无翻面。

    只有两侧都出现的族才可比：同族令牌集不同即翻面；只在一侧出现的族是换承载。
    """
    sealed = _directions_by_family(sealed_tokens)
    current = _directions_by_family(current_tokens)
    return sorted((family for family in sealed.keys() & current.keys() if sealed[family] != current[family]))

def expectation_direction(step: StepIR) -> str:
    """把一条已编译断言投影成方向令牌；读不出方向返回空串。

    令牌只有身份意义、不参与取值，唯一用途是与首轮封印比对。
    """
    if str(step.E or '').strip() != 'check_point':
        return ''
    receipt = step.source.receipt
    if isinstance(receipt, dict):
        rule_id = str(receipt.get('rule_id') or '').strip()
        key = _DIRECTION_INPUT_KEYS.get(rule_id)
        source_input = receipt.get('source_input')
        if key and isinstance(source_input, dict):
            token = str(source_input.get(key) or '').strip()
            if token:
                return f'{rule_id}:{key}={token}'
    operator = str(step.F or '').strip()
    if operator in _ASSERT_OPERATORS:
        return 'operator:negative' if operator in _NEGATIVE_ASSERT_OPERATORS else 'operator:positive'
    return ''

def _direction_token_shape_valid(token: str) -> bool:
    """复核封印令牌是否属于现有产者文法；只判记录形态，不签预期语义。"""
    operator_tokens = {'operator:negative' if operator in _NEGATIVE_ASSERT_OPERATORS else 'operator:positive' for operator in _ASSERT_OPERATORS}
    if token in operator_tokens:
        return True
    for rule_id, key in _DIRECTION_INPUT_KEYS.items():
        prefix = f'{rule_id}:{key}='
        if not token.startswith(prefix):
            continue
        value = token.removeprefix(prefix)
        if value != value.strip():
            return False
        if rule_id == 'capture.static-relation':
            return not _derive_rule_capture_static_relation({key: value})[1]
        if rule_id == 'status.exit-code':
            from cex_core.engine.case_compiler.blocks import _EXIT_STATUS_EXPECTS
            return value in _EXIT_STATUS_EXPECTS
    return False

def _contract_author_claim_shas(contract: Any, *, autoid: str) -> dict[str, str]:
    """冻结契约卡的 ``expectations[].author_claim`` → claim_sha256。

    身份复核复用 ``vk_derivation._author_claim``（卡来自受信路径不等于身份本身），
    不在这里写第二套判据。
    """
    expectations = contract.get('expectations') if isinstance(contract, dict) else None
    if not isinstance(expectations, list):
        return {}
    from cex_core.engine.case_compiler.vk_derivation import _author_claim
    shas: dict[str, str] = {}
    for item in expectations:
        if not isinstance(item, dict):
            continue
        claim = _author_claim(item, str(autoid or ''))
        if not isinstance(claim, dict):
            continue
        expectation_id = str(claim.get('expectation_id') or '').strip()
        claim_sha = str(claim.get('claim_sha256') or '').strip()
        if expectation_id and re.fullmatch('[0-9a-f]{64}', claim_sha):
            shas[expectation_id] = claim_sha
    return shas

def author_claim_shas(autoid: str, *, outputs_root: Path | None=None, contract: Any=None) -> dict[str, str]:
    """expectation_id → 已盖章 Author claim 的 claim_sha256；读不到返回空表。

    两个供给面并取：冻结契约卡（现役批的正本——`workspace/outputs/<批>/contracts/
    <autoid>.json`，由调用方读好传进来）与 ``<autoid>/intent.json``（`intent` 源类
    断言复验读的那份）。两处都读不到就返回空表——本闸不因读不到而冒签「这条判词
    没被签发过」，也不因此拒绝。
    """
    shas = _contract_author_claim_shas(contract, autoid=autoid)
    aid = str(autoid or '').strip()
    if not aid or Path(aid).name != aid:
        return shas
    root = Path(outputs_root) if outputs_root is not None else _scoped_outputs_root()
    candidate = root / aid / 'intent.json'
    if _safe_file_under(candidate, root) is None:
        return shas
    from cex_core.engine.case_compiler.contract_entry import ContractError, read_intent_json
    try:
        payload, _raw = read_intent_json(candidate, trusted_root=root)
    except ContractError:
        return shas
    claims = payload.get('author_claims') if isinstance(payload, dict) else None
    if not isinstance(claims, dict):
        return shas
    for key, claim in claims.items():
        if not isinstance(claim, dict):
            continue
        expectation_id = str(claim.get('expectation_id') or key).strip()
        claim_sha = str(claim.get('claim_sha256') or '').strip()
        if expectation_id and re.fullmatch('[0-9a-f]{64}', claim_sha):
            shas[expectation_id] = claim_sha
    return shas
EXPECTATION_DIRECTION_FLIP_EXITS = "A signed expectation's direction is frozen at its first compile: the method may be recompiled (probe tool, observation command, host, exit-code class, operator form) but the asserted outcome may not be flipped. If this run showed the product behaving the other way, keep the assertion and attribute the case as disposition=defect_candidate with a signed expected_with_source receipt. If another signed source (spec/manual/capability_xml) states the opposite, that is a source conflict for the upstream conflict graph to reconcile, never a rewrite here."

def seal_expectation_directions(case: CaseProvenance, *, outputs_root: Path | None=None, project_root: Path | None=None, contract: Any=None, disclosures: list[dict[str, Any]] | None=None, failure_observations: list[dict[str, Any]] | None=None) -> list[str]:
    """封印每条已签发 Author 判词首次编译出的方向，并在重编轮复核它没被翻面。

    按 claim 分组而不是按断言行：一条判词被 N 条命令兑现（<case> 三条 curl）或被
    ``OBSERVE_DIST`` 扇出成 N 桶时，方向是这一组的集合，集合稳定即未翻面。案内
    序列化对照行由编译器铸造、沿用同一 expectation_id 且必然反极性，在此排除——
    它是规则产物，不是作者的第二条声明。

    集合比较保留两类未核披露：封印令牌全部保留、只新增对侧
    令牌的**纯扩张**（如 {negative}→{negative,positive}）机械上证不出翻面——作者
    在同一判词下补正向前置是否合法属相位/语义解读，按披露处理不硬拒
    （``disclosures`` 出参，调用方绑定当前卷面落披露）。旧 capture 封印只存同/异
    令牌，没有操作数、观测和阶段；同族令牌替换也不能证明作者预期翻面，故同样披露。
    其余族的令牌消失仍保留既有限制，本次不证明 status/operator 规则的语义健全性。

    封印按 ``claim_sha256`` 入 key：作者改了脑图即新 claim、新 key、重新封印，
    本闸只管「同一句话被编成了相反的断言」。
    """
    claim_shas = author_claim_shas(case.autoid, outputs_root=outputs_root, contract=contract)
    if not claim_shas:
        return []
    autoid = str(case.autoid or '').strip()
    grouped: dict[str, set[str]] = {}
    unreadable: set[str] = set()
    for step in case.steps:
        expectation_id = str(step.expectation_id or '').strip()
        if expectation_id not in claim_shas:
            continue
        if str(step.E or '').strip() != 'check_point':
            continue
        if str(getattr(step, 'mutation_role', '') or '') == MUTATION_ROLE_CONTROL:
            continue
        direction = expectation_direction(step)
        if direction:
            grouped.setdefault(expectation_id, set()).add(direction)
        else:
            unreadable.add(expectation_id)
    problems: list[str] = []
    for expectation_id, directions in sorted(grouped.items()):
        if expectation_id in unreadable:
            continue
        record = {'schema': _EXPECTATION_DIRECTION_SEAL_SCHEMA, 'autoid': autoid, 'expectation_id': expectation_id, 'claim_sha256': claim_shas[expectation_id], 'directions': sorted(directions)}
        sealed: dict[str, Any] = {}
        observation: dict[str, Any] = {}

        def reject(message: str, check: str='', outcome: str='', *, assertion: bool=False) -> None:
            problems.append(message)
            if failure_observations is not None:
                item = copy.deepcopy(observation)
                if check:
                    item['check'] = check
                if outcome:
                    item['outcome'] = outcome
                item.setdefault('subject', {}).update(expectation_id=expectation_id, claim_sha256=claim_shas[expectation_id])
                if assertion:
                    item['subject'].update(kind='compiled_assertion', sealed_directions=sealed.get('directions'), current_directions=sorted(directions))
                failure_observations.append(item)
        error = _immutable_seal(family='expectation_direction', scope_key=hashlib.sha256(autoid.encode('utf-8')).hexdigest(), item_key=hashlib.sha256(f'{expectation_id}\x00{claim_shas[expectation_id]}'.encode('utf-8')).hexdigest(), payload=record, label='Author expectation direction', create=True, observed_sink=sealed, observation_sink=observation, project_root=project_root)
        if not error:
            continue
        if error == 'Author expectation direction seal identity drift':
            was = sealed.get('directions')
            if set(sealed) != set(record):
                reject('Author expectation direction seal field set is invalid', 'direction_seal_fields', 'invalid')
                continue
            if not accepts_schema(sealed.get('schema'), _EXPECTATION_DIRECTION_SEAL_SCHEMA):
                reject('Author expectation direction seal schema is unsupported', 'direction_seal_schema', 'unsupported')
                continue
            mismatched = [key for key in ('autoid', 'expectation_id', 'claim_sha256') if sealed.get(key) != record[key]]
            if mismatched:
                observation.setdefault('subject', {})['mismatched_fields'] = mismatched
                reject('Author expectation direction seal identity mismatch: ' + ', '.join(mismatched), 'direction_seal_identity', 'mismatch')
                continue
            if not isinstance(was, list) or not was or any((not isinstance(token, str) or not token.strip() or token != token.strip() or (not _direction_token_shape_valid(token)) for token in was)) or (was != sorted(set(was))):
                reject('Author expectation direction seal directions shape is invalid', 'direction_seal_tokens', 'invalid')
                continue
            changed_families = direction_flip_families(was, directions)
            if not changed_families:
                continue
            _sealed_by_family = _directions_by_family(was)
            _current_by_family = _directions_by_family(sorted(directions))
            capture_family = 'capture.static-relation'
            capture_changed = capture_family in changed_families
            if capture_changed:
                if not all((_direction_token_shape_valid(token) for token in _current_by_family[capture_family])):
                    reject('Author expectation direction seal capture relation token is invalid', 'capture_relation_token', 'invalid', assertion=True)
                    continue
            remaining_families = set(changed_families) - ({capture_family} if capture_changed else set())
            _pure_extension = all((not _sealed_by_family.get(family, set()) - _current_by_family.get(family, set()) for family in remaining_families))
            if capture_changed or _pure_extension:
                if disclosures is not None:
                    disclosures.append({'expectation_id': expectation_id, 'claim_sha256': claim_shas[expectation_id], 'sealed_directions': list(was), 'current_directions': sorted(directions)})
                if _pure_extension:
                    continue
            rejected_families = {family for family in remaining_families if _sealed_by_family[family] - _current_by_family[family]}
            was_text = '/'.join((item for item in was if direction_family(item) in rejected_families)) if was else 'a different direction'
            error = f"expectation {expectation_id} is now compiled asserting {'/'.join((token for token in sorted(directions) if direction_family(token) in rejected_families))}, but this claim was first compiled asserting {was_text}. " + EXPECTATION_DIRECTION_FLIP_EXITS
            reject(error, 'direction_restriction', 'violated', assertion=True)
        else:
            reject(error)
    return problems

def _step_g_snippet(step: StepIR) -> str:
    """G 原文首行截断，供违例文本定位载体。观测命令与配置命令展开后同为
    F='cmd_config'，只报 E/F 会把排障指向错误的块类（<case> 实证约 20 轮，
    见 内部取证文档（已脱敏）"""
    lines = str(step.G or '').strip().splitlines()
    text = lines[0].strip() if lines else ''
    return text[:60] + ('…' if len(text) > 60 else '')

def check_source_locators(case: CaseProvenance, *, outputs_root: Path | None=None) -> list[str]:
    """验证每个来源确实可复查，并为通过项重铸当前 SHA receipt。"""
    problems: list[str] = []
    for index, step in enumerate(case.steps):
        kind = str(step.source.kind or '')
        locator = str(step.source.ref or '').strip()
        locus = f'step {index} (G={_step_g_snippet(step)!r})'
        if kind == 'intent' and (not locator) and (not _step_redeems_author_claim(step)):
            problems.append(f'{locus}: ' + _intent_on_non_assertion(step, locator, selector_resolves=False))
            step.source.receipt = {}
            continue
        if kind in _SOURCE_LOCATOR_REQUIRED and (not locator):
            problems.append(f'{locus}: source.kind={kind} requires a non-empty source.ref locator')
            step.source.receipt = {}
            continue
        is_language_primitive = step.E.strip() == 'time' and step.F.strip() == 'sleep'
        if kind in {'emit_auto', 'unknown'} and (not is_language_primitive):
            problems.append(f'{locus}: E={step.E!r} F={step.F!r} cannot use source.kind={kind}; every command/method/action and expected value needs a resolvable source receipt')
            step.source.receipt = {}
            continue
        receipt, error = resolve_source_receipt(case, step, outputs_root=outputs_root)
        if receipt is None:
            problems.append(f'{locus}: source {kind}:{locator} does not resolve: {error}')
            step.source.receipt = {}
        elif kind == 'spec' and step.source.receipt and (step.source.receipt != receipt):
            problems.append(f'{locus}: source spec:{locator} generation identity drift')
        else:
            step.source.receipt = receipt
    return problems

def validate_expected_with_source(value: Any) -> tuple[dict[str, Any] | None, str]:
    """验证产品缺陷候选的“预期 + 静态签发来源”结构。

    自由文本 ``"手册:应当..."`` 无法证明手册或行号存在，不能把产品候选从
    engine 责任升级到 product。Author/CapabilityXml 必须带已铸造
    receipt；DefectSpec 必须带逐案 resolver 收据；Spec/Manual 仍由引擎就地解析。运行回显、probe、先例与
    footprint 都不是 expected 签发者。
    """
    if not isinstance(value, dict):
        return (None, 'expected_with_source must be an object with `expected` and `source:{kind,ref}`; free text is not a source receipt')
    expected = str(value.get('expected') or '').strip()
    source = value.get('source')
    if not expected:
        return (None, 'expected_with_source.expected is required')
    if not isinstance(source, dict):
        return (None, 'expected_with_source.source must be an object')
    kind = str(source.get('kind') or '').strip().lower()
    locator = str(source.get('ref') or '').strip()
    public_to_raw = {'author': 'intent', 'intent': 'intent', 'capabilityxml': 'capability_xml', 'capability_xml': 'capability_xml', 'defectspec': 'defect_spec', 'defect_spec': 'defect_spec', 'spec': 'spec', 'manual': 'manual', **{item: item for item in _DERIVED_SOURCE_KINDS}}
    raw_kind = public_to_raw.get(kind, '')
    if not raw_kind:
        return (None, 'product expectation source.kind must be author, spec, defect_spec, capability_xml, manual, or a verified ConfigBinding derivation; runtime/probe/observed/precedent/footprint cannot sign expected')
    supplied_receipt = source.get('receipt')
    if raw_kind == 'intent':
        if not isinstance(supplied_receipt, dict):
            return (None, 'Author expected source requires its stamped intent receipt')
        if supplied_receipt.get('kind') != 'intent' or str(supplied_receipt.get('locator') or '') != locator or str(supplied_receipt.get('selector') or '') != locator:
            return (None, 'Author expected source receipt identity drift')
        source_path = str(supplied_receipt.get('path') or '').strip()
        path = None
        if source_path and (not Path(source_path).is_absolute()) and ('..' not in Path(source_path).parts):
            path = _safe_file_under(PROJECT_ROOT / source_path, _scoped_outputs_root())
        source_sha = str(supplied_receipt.get('sha256') or '')
        if path is None or not re.fullmatch('[0-9a-f]{64}', source_sha) or _sha256_file(path) != source_sha or (path.stat().st_size != supplied_receipt.get('size')):
            return (None, 'Author expected source receipt does not match stamped intent')
        try:
            payload = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            return (None, 'Author expected source intent is unreadable')
        rebuilt, rebuild_error = _file_receipt(kind='intent', locator=locator, path=path, root=_scoped_outputs_root(), selector=locator)
        if rebuilt is None:
            return (None, rebuild_error)
        supplied_base = {key: item for key, item in supplied_receipt.items() if key != 'author_compilation'}
        if supplied_base != rebuilt:
            return (None, 'Author expected source receipt identity drift')
        compilation = supplied_receipt.get('author_compilation')
        if isinstance(compilation, dict):
            claims = payload.get('author_claims')
            claim = claims.get(locator) if isinstance(claims, dict) else None
            if not isinstance(claim, dict):
                return (None, 'Author compilation has no stamped claim')
            claim_body_keys = {'schema', 'kind', 'autoid', 'expectation_id', 'semantic_key', 'origin', 'source_text', 'source_sha256'}
            claim_body = {key: claim.get(key) for key in claim_body_keys}
            claim_sha = str(claim.get('claim_sha256') or '')
            if set(claim) != claim_body_keys | {'claim_sha256'} or not accepts_schema(claim.get('schema'), 'ist.author-claim') or claim.get('kind') != 'Author' or (str(claim.get('expectation_id') or '') != locator) or (re.fullmatch('[0-9a-f]{64}', claim_sha) is None) or (_canonical_json_sha256(claim_body) != claim_sha):
                return (None, 'Author compilation claim identity drift')
            material_keys = {'schema', 'claim_sha256', 'expectation_id', 'semantic_key', 'operator', 'value_sha256', 'source_kind', 'source_ref', 'intent_sha256', 'status'}
            material = {key: compilation.get(key) for key in material_keys}
            if set(compilation) != material_keys | {'receipt_sha256'} or not accepts_schema(compilation.get('schema'), 'ist.author-compilation') or compilation.get('claim_sha256') != claim_sha or (compilation.get('expectation_id') != locator) or (compilation.get('semantic_key') != claim.get('semantic_key')) or (not str(compilation.get('operator') or '').strip()) or (compilation.get('value_sha256') != hashlib.sha256(expected.encode('utf-8')).hexdigest()) or (compilation.get('source_kind') != 'intent') or (compilation.get('source_ref') != locator) or (compilation.get('intent_sha256') != rebuilt.get('sha256')) or (compilation.get('status') != 'compiled_pre_device') or (compilation.get('receipt_sha256') != _canonical_json_sha256(material)):
                return (None, 'Author compilation receipt identity drift')
        else:
            selected = _json_values_for_key(payload, locator)
            if not selected:
                return (None, 'Author expected selector is absent from stamped intent')
            declared_values = {str(item.get('value') or '') if isinstance(item, dict) else str(item or '') for item in selected}
            if expected not in declared_values:
                return (None, 'Author expected value differs from stamped intent')
        return ({'expected': expected, 'source': {'kind': 'author', 'ref': locator, 'receipt': dict(supplied_receipt)}}, '')
    if raw_kind == 'defect_spec' and isinstance(supplied_receipt, dict):
        compilation = supplied_receipt.get('defect_spec_compilation')
        if isinstance(compilation, dict):
            resolver_receipt = {key: item for key, item in supplied_receipt.items() if key != 'defect_spec_compilation'}
            material_keys = {'schema', 'autoid', 'claim_sha256', 'resolver_receipt_sha256', 'expectation_id', 'semantic_key', 'operator', 'value_sha256', 'source_kind', 'source_ref', 'status'}
            material = {key: compilation.get(key) for key in material_keys}
            autoid = str(compilation.get('autoid') or '').strip()
            expectation_id = str(compilation.get('expectation_id') or '').strip()
            semantic_key = str(compilation.get('semantic_key') or '').strip()
            if set(compilation) != material_keys | {'receipt_sha256'} or not accepts_schema(compilation.get('schema'), 'ist.defect-spec-compilation') or (not autoid) or (Path(autoid).name != autoid) or (not expectation_id) or (not semantic_key) or (not str(compilation.get('operator') or '').strip()) or (compilation.get('value_sha256') != hashlib.sha256(expected.encode('utf-8')).hexdigest()) or (compilation.get('source_kind') != 'defect_spec') or (compilation.get('source_ref') != locator) or (compilation.get('status') != 'compiled_pre_device') or (compilation.get('receipt_sha256') != _canonical_json_sha256(material)):
                return (None, 'DefectSpec compilation receipt identity drift')
            seal_error = _defect_spec_compilation_seal(compilation, create=False)
            if seal_error:
                return (None, seal_error)
            outputs = _scoped_outputs_root()
            intent_path = _safe_file_under(outputs / autoid / 'intent.json', outputs)
            if intent_path is None:
                return (None, 'DefectSpec compilation has no stamped intent')
            from cex_core.engine.case_compiler.contract_entry import ContractError, read_intent_json
            try:
                payload, _intent_bytes = read_intent_json(outputs / autoid / 'intent.json', trusted_root=outputs)
            except ContractError:
                return (None, 'DefectSpec compilation stamped intent is unreadable')
            claims = payload.get('defect_spec_claims') if isinstance(payload, dict) else None
            claim = claims.get(expectation_id) if isinstance(claims, dict) else None
            verified_claim, claim_error = validate_defect_spec_claim(claim, autoid=autoid, expectation_id=expectation_id, semantic_key=semantic_key)
            if verified_claim is None:
                return (None, claim_error)
            if resolver_receipt != verified_claim.get('resolver_receipt') or compilation.get('claim_sha256') != verified_claim.get('claim_sha256') or compilation.get('resolver_receipt_sha256') != verified_claim.get('resolver_receipt_sha256'):
                return (None, 'DefectSpec compilation claim or resolver receipt drift')
            probe_step = StepIR(E='check_point', F=str(compilation['operator']), G=expected, layer='V', source=StepSource(kind='defect_spec', ref=locator, receipt=dict(resolver_receipt)), expectation_id=expectation_id, semantic_key=semantic_key)
            rebuilt, rebuild_error = _validate_defect_spec_expected_receipt(probe_step, resolver_receipt=resolver_receipt, require_value_match=False)
            if rebuilt is None:
                return (None, rebuild_error)
            return ({'expected': expected, 'source': {'kind': 'defect_spec', 'ref': locator, 'receipt': dict(supplied_receipt)}}, '')
    probe = CaseProvenance(autoid='product-defect-source', steps=[StepIR(E='check_point', F='found', G=expected, layer='V', source=StepSource(kind=raw_kind, ref=locator, receipt=dict(supplied_receipt) if isinstance(supplied_receipt, dict) else {}))])
    problems = check_source_locators(probe)
    if problems:
        return (None, problems[0])
    resolved = probe.steps[0].source
    return ({'expected': expected, 'source': {'kind': 'capability_xml' if resolved.kind == 'capability_xml' else resolved.kind, 'ref': resolved.ref, 'receipt': resolved.receipt}}, '')

def product_expected_source_is_valid(value: Any) -> bool:
    """产品候选资格消费点共用的纯布尔入口。"""
    resolved, _error = validate_expected_with_source(value)
    return resolved is not None

def _nested_text_values(value: Any) -> list[str]:
    """展开机读对象里的字符串值，供精确身份谓词复用。"""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        result: list[str] = []
        for item in value.values():
            result.extend(_nested_text_values(item))
        return result
    if isinstance(value, list):
        result = []
        for item in value:
            result.extend(_nested_text_values(item))
        return result
    return []

def _expect_derivation_kind(expect: Mapping[str, Any]) -> str | None:
    """expect 是否派生形态；是则返回归一后的派生配方名（可能是非法值）。

    现役写法是配方名本身（== 断言步的 ``source.kind``）；2026-09-03 前的盘上
    形态是散文 ``compiler-derived:<kind>``——读侧归一兼容，写侧只有现役一种
    形态（单源读写纪律，不留双写漂移）。没有 ``derivation`` 键时返回
    ``None``（非派生形态），交由各权威组自己的形态分支判；键存在但值非法
    （空串/未知配方）仍按派生形态走，由校验分支给出明确拒绝。
    """
    if 'derivation' not in expect:
        return None
    raw = str(expect.get('derivation') or '').strip()
    if raw.startswith('compiler-derived:'):
        raw = raw[len('compiler-derived:'):].strip()
    return raw

def compile_assertion_types(case: CaseProvenance, *, current_run_ids: tuple[str, ...]=(), required: bool | None=None) -> list[str]:
    """检查 IDE 断言三元组的凭据形态，不判断凭据内容是否正确。

    读取边界：历史归档 provenance 可能没有 ``assertion_schema``，也没有
    ``assertion_type``；本函数仍能只读解析这类记录。现役 ``compile_emit`` 不接受
    调用方提交的 raw untyped provenance；只有 blocks 编译器可从受约束的结构化
    输入机械派生类型。一旦声明新 schema 或任一断言带型，所有
    ``check_point`` 都必须完整带型，禁止新旧形态在同一案内混排。
    """
    assertions = [(index, step) for index, step in enumerate(case.steps) if step.E.strip() == 'check_point']
    typed = any((step.assertion_type is not None for step in case.steps))
    if required is None:
        required = bool(case.assertion_schema or typed)
    if not required:
        return []
    problems: list[str] = []
    if case.assertion_schema != ASSERTION_TYPE_SCHEMA:
        problems.append(f'assertion_schema must equal {ASSERTION_TYPE_SCHEMA!r} when IDE assertion types are present')
    for index, step in enumerate(case.steps):
        if step.E.strip() != 'check_point' and step.assertion_type is not None:
            problems.append(f'step {index}: assertion_type is only valid on check_point')
    active_run_ids = tuple((value for value in (str(item or '').strip() for item in current_run_ids) if value))
    for index, step in assertions:
        assertion = step.assertion_type
        if not isinstance(assertion, dict):
            problems.append(f'step {index}: assertion_type is required')
            continue
        if set(assertion) != {'expect', 'flip', 'form'}:
            problems.append(f'step {index}: assertion_type must contain exactly expect/flip/form')
            continue
        expect = assertion.get('expect')
        if not isinstance(expect, dict):
            problems.append(f'step {index}: assertion_type.expect must be an object')
        else:
            kind = str(expect.get('kind') or '')
            derivation = _expect_derivation_kind(expect)
            if kind not in _EXPECT_KINDS:
                problems.append(f'step {index}: expect.kind must be Author/Manual/ConfigBinding/Spec/DefectSpec/CapabilityXml')
            elif derivation is not None:
                if set(expect) != {'kind', 'recipe_id', 'derivation'}:
                    problems.append(f'step {index}: derived expect requires exactly kind/recipe_id/derivation')
                if not str(expect.get('recipe_id') or '').strip():
                    problems.append(f'step {index}: expect.recipe_id is required')
                if not derivation:
                    problems.append(f'step {index}: expect.derivation must name a registered derivation recipe')
                else:
                    authority = claim_authority_source(derivation)
                    if kind != authority:
                        problems.append(f'step {index}: expect.kind must be {authority} for derivation {derivation} — the authority group and the derivation recipe are orthogonal fields')
                    if step.source.kind != derivation:
                        problems.append(f'step {index}: expect.derivation must equal source.kind')
                    elif str(expect.get('recipe_id') or '').strip() != str(step.source.ref or '').strip():
                        problems.append(f'step {index}: expect.recipe_id must equal source.ref')
            elif kind == 'ConfigBinding':
                problems.append(f'step {index}: ConfigBinding expect requires a derivation recipe')
            elif kind == 'Author':
                if set(expect) != {'kind', 'text_hash'}:
                    problems.append(f'step {index}: Author requires exactly kind/text_hash')
                text_hash = str(expect.get('text_hash') or '')
                if not re.fullmatch('[0-9a-f]{64}', text_hash):
                    problems.append(f'step {index}: Author.text_hash must be a lowercase SHA-256')
                if step.source.kind != 'intent':
                    problems.append(f'step {index}: Author expect requires source.kind=intent')
            elif kind == 'Manual':
                if set(expect) not in ({'kind', 'locator'}, {'kind', 'locator', 'spec_gap'}):
                    problems.append(f'step {index}: Manual requires exactly kind/locator[/spec_gap]')
                locator = str(expect.get('locator') or '').strip()
                if not locator:
                    problems.append(f'step {index}: Manual.locator is required')
                if 'spec_gap' in expect and (not str(expect.get('spec_gap') or '').strip()):
                    problems.append(f'step {index}: Manual.spec_gap, when given, must state in one line why the governing spec lacks this criterion')
                if step.source.kind != 'manual':
                    problems.append(f'step {index}: Manual expect requires source.kind=manual')
                elif locator and locator != str(step.source.ref or '').strip():
                    problems.append(f'step {index}: Manual.locator must equal source.ref')
            elif kind == 'Spec':
                if set(expect) != {'kind', 'locator'}:
                    problems.append(f'step {index}: Spec requires exactly kind/locator')
                locator = str(expect.get('locator') or '').strip()
                if not locator:
                    problems.append(f'step {index}: Spec.locator is required')
                if step.source.kind != 'spec':
                    problems.append(f'step {index}: Spec expect requires source.kind=spec')
                elif locator and locator != str(step.source.ref or '').strip():
                    problems.append(f'step {index}: Spec.locator must equal source.ref')
            elif kind == 'DefectSpec':
                if set(expect) != {'kind', 'locator', 'receipt_sha256'}:
                    problems.append(f'step {index}: DefectSpec requires exactly kind/locator/receipt_sha256')
                locator = str(expect.get('locator') or '').strip()
                receipt_sha = str(expect.get('receipt_sha256') or '')
                if not locator:
                    problems.append(f'step {index}: DefectSpec.locator is required')
                if not re.fullmatch('[0-9a-f]{64}', receipt_sha):
                    problems.append(f'step {index}: DefectSpec.receipt_sha256 must be a lowercase SHA-256')
                if step.source.kind != 'defect_spec':
                    problems.append(f'step {index}: DefectSpec expect requires source.kind=defect_spec')
                elif locator and locator != str(step.source.ref or '').strip():
                    problems.append(f'step {index}: DefectSpec.locator must equal source.ref')
                receipt = step.source.receipt
                if not isinstance(receipt, dict) or not receipt:
                    problems.append(f'step {index}: DefectSpec resolver receipt is unavailable')
                elif receipt_sha and receipt_sha != _canonical_json_sha256({key: value for key, value in receipt.items() if key != 'defect_spec_compilation'}):
                    problems.append(f'step {index}: DefectSpec.receipt_sha256 receipt drift')
            elif kind == 'CapabilityXml':
                if set(expect) != {'kind', 'locator', 'device_os_build', 'source_sha256', 'claim_receipt_sha256'}:
                    problems.append(f'step {index}: CapabilityXml requires exactly kind/locator/device_os_build/source_sha256/claim_receipt_sha256')
                locator = str(expect.get('locator') or '').strip()
                build = str(expect.get('device_os_build') or '').strip()
                source_sha = str(expect.get('source_sha256') or '')
                claim_sha = str(expect.get('claim_receipt_sha256') or '')
                if not locator:
                    problems.append(f'step {index}: CapabilityXml.locator is required')
                if not build:
                    problems.append(f'step {index}: CapabilityXml.device_os_build is required')
                if not re.fullmatch('[0-9a-f]{64}', source_sha):
                    problems.append(f'step {index}: CapabilityXml.source_sha256 must be a lowercase SHA-256')
                if not re.fullmatch('[0-9a-f]{64}', claim_sha):
                    problems.append(f'step {index}: CapabilityXml.claim_receipt_sha256 must be a lowercase SHA-256')
                if step.source.kind != 'capability_xml':
                    problems.append(f'step {index}: CapabilityXml expect requires source.kind=capability_xml')
                elif locator and locator != str(step.source.ref or '').strip():
                    problems.append(f'step {index}: CapabilityXml.locator must equal source.ref')
                receipt = step.source.receipt
                if not isinstance(receipt, dict) or not receipt:
                    problems.append(f'step {index}: CapabilityXml expected receipt is unavailable; generation is pending G6')
                else:
                    if build and build != str(receipt.get('device_os_build') or ''):
                        problems.append(f'step {index}: CapabilityXml.device_os_build receipt drift')
                    if source_sha and source_sha != str(receipt.get('sha256') or ''):
                        problems.append(f'step {index}: CapabilityXml.source_sha256 receipt drift')
                    if claim_sha and claim_sha != str(receipt.get('receipt_sha256') or ''):
                        problems.append(f'step {index}: CapabilityXml.claim_receipt_sha256 receipt drift')
            expect_texts = [str(step.source.ref or ''), *_nested_text_values(expect)]
            for run_id in active_run_ids:
                if any((run_id in text for text in expect_texts)):
                    problems.append(f'step {index}: expect references the current case run_id')
                    break
        flip = assertion.get('flip')
        if not isinstance(flip, dict):
            problems.append(f'step {index}: assertion_type.flip must be an object')
        else:
            kind = str(flip.get('kind') or '')
            if kind not in _FLIP_KINDS:
                problems.append(f'step {index}: flip.kind must be Flipped/Exempt')
            elif kind == 'Flipped':
                if set(flip) != {'kind', 'evidence_ref'}:
                    problems.append(f'step {index}: Flipped requires exactly kind/evidence_ref')
                if not str(flip.get('evidence_ref') or '').strip():
                    problems.append(f'step {index}: Flipped.evidence_ref is required')
            elif kind == 'Exempt':
                if set(flip) != {'kind', 'reason_code'}:
                    problems.append(f'step {index}: Exempt requires exactly kind/reason_code')
                reason_code = str(flip.get('reason_code') or '').strip()
                if reason_code not in EXEMPT_REASON_CODES:
                    problems.append(f'step {index}: Exempt.reason_code must be one of {sorted(EXEMPT_REASON_CODES)}')
                elif reason_code == 'direction_review_pending':
                    problems.append(f"step {index}: Exempt.reason_code 'direction_review_pending' is a deferral, not a justification — finish the direction review first, or provide real flip evidence")
        form = assertion.get('form')
        if not isinstance(form, dict) or form != {'kind': _FORM_KIND}:
            problems.append(f"step {index}: form must equal {{'kind': '{_FORM_KIND}'}}")
    return problems

def synthesize_assertion_types(case: CaseProvenance) -> list[str]:
    """为尚未带型的新案机械生成 IDE 断言类型。

    这里只把已经存在于步骤 IR 的来源投影成固定形态，不判断来源内容是否
    正确：来源真实性仍由 ``check_source_locators`` / receipt 规则负责。显式
    带型的断言不被改写，随后仍由 ``compile_assertion_types`` 校验。
    """
    problems: list[str] = []
    for index, step in enumerate(case.steps):
        if step.E.strip() != 'check_point' or step.assertion_type is not None:
            continue
        source_kind = step.source.kind
        source_ref = str(step.source.ref or '').strip()
        if source_kind == 'intent':
            expect = {'kind': 'Author', 'text_hash': hashlib.sha256(str(step.G or '').encode('utf-8')).hexdigest()}
        elif source_kind == 'manual':
            if not source_ref:
                problems.append(f'step {index}: Manual expect cannot be derived without source.ref')
                continue
            expect = {'kind': 'Manual', 'locator': source_ref}
            if str(step.spec_gap or '').strip():
                expect['spec_gap'] = str(step.spec_gap).strip()
        elif source_kind == 'spec':
            if not source_ref:
                problems.append(f'step {index}: Spec expect cannot be derived without source.ref')
                continue
            expect = {'kind': 'Spec', 'locator': source_ref}
        elif source_kind == 'defect_spec':
            if not source_ref or not isinstance(step.source.receipt, dict) or (not step.source.receipt):
                problems.append(f'step {index}: DefectSpec expect cannot be derived without source.ref and the engine-resolved receipt')
                continue
            expect = {'kind': 'DefectSpec', 'locator': source_ref, 'receipt_sha256': _canonical_json_sha256({key: value for key, value in step.source.receipt.items() if key != 'defect_spec_compilation'})}
        elif source_kind == 'capability_xml':
            problems.append(f'step {index}: CapabilityXml expect generation is pending G6; provide a typed, XML-bound expected claim instead of deriving a value from command existence')
            continue
        elif source_kind in _DERIVED_SOURCE_KINDS:
            authority = claim_authority_source(source_kind)
            if not source_ref:
                problems.append(f'step {index}: {authority} derivation cannot be derived without source.ref')
                continue
            expect = {'kind': authority, 'recipe_id': source_ref, 'derivation': source_kind}
        else:
            problems.append(f"step {index}: expect authority cannot be mechanically derived from source.kind={source_kind or 'unknown'}")
            continue
        step.assertion_type = {'expect': expect, 'flip': {'kind': 'Flipped', 'evidence_ref': 'compiler:mutation-pending'}, 'form': {'kind': _FORM_KIND}}
    if not problems:
        case.assertion_schema = ASSERTION_TYPE_SCHEMA
    return problems

def compile_expect_authority(case: CaseProvenance) -> list[str]:
    """编译入口只接受静态声明或确定性绑定提供的 expected。"""
    problems: list[str] = []
    for index, step in enumerate(case.steps):
        if step.source.kind == 'precedent':
            try:
                from cex_core.engine.case_compiler.package_advisories import package_asset_autoid, package_rejection, read_package_projection
                receipt = step.source.receipt or {}
                asset_id = Path(str(receipt.get('path') or '')).name or str(step.source.ref or '').split('#', 1)[0].strip()
                rejection = package_rejection(autoid=package_asset_autoid(asset_id), asset_id=asset_id, sha256=str(receipt.get('sha256') or ''), projection=read_package_projection())
            except Exception:
                rejection = 'E_PACKAGE_INDEX_UNAVAILABLE asset_id=package-registry rule_id=PKG-ASSET-001'
            if rejection:
                problems.append(rejection)
    return problems
check_emit_source_authority = compile_expect_authority

def parse_provenance(provenance_json: str) -> CaseProvenance | None:
    """容错解析 provenance_json；空/坏返回 None（调用方据此回退 V2 行为）。"""
    if not provenance_json or not provenance_json.strip():
        return None
    try:
        return CaseProvenance.from_json(provenance_json)
    except Exception:
        return None

def steps_match(provenance: CaseProvenance, steps: list[dict]) -> bool:
    """校验 provenance 的步骤与实际 emit 的 steps 在 E/F/G 上一致（防 draft 标注与产物脱节）。"""
    if len(provenance.steps) != len(steps):
        return False
    for ps, st in zip(provenance.steps, steps):
        if ps.E != str(st.get('E', '')) or ps.F != str(st.get('F', '')) or ps.G != str(st.get('G', '')):
            return False
    return True

def backfill_efg(provenance: CaseProvenance, steps: list[dict]) -> bool:
    """按位置把 emit steps 的 E/F/G 回填进 provenance——draft 只标 layer/source、不必手抄 E/F/G。
    （手抄一长串 E/F/G 极易错位，一错位 steps_match 就失败、旁挂跳过、draft 就重 emit 空转。）
    步骤数一致即逐位回填并返回 True；数目对不上才返回 False（旁挂跳过）。"""
    if len(provenance.steps) != len(steps):
        return False
    for ps, st in zip(provenance.steps, steps):
        ps.E = str(st.get('E', ''))
        ps.F = str(st.get('F', ''))
        ps.G = str(st.get('G', ''))
    return True

def check_runtime_consistency(provenance: CaseProvenance) -> list[str]:
    """不瞎写硬契约：device_runtime 来源 ⟺ G 值是 <RUNTIME> 占位，双向自洽。

    抓三类骗通过规则的写法（纯结构自洽，不判值对错——离线本就判不了对错）：
    - 标了 device_runtime 却填了具体值（假装弃权、实则编数）；
    - 填了 <RUNTIME> 占位却把来源标成 footprint/precedent 等（占位却谎称有源）；
    含 <RUNTIME> 子串即视为占位，不只看整串相等。设备观察永远不能成为
    expected 来源，因此不存在 device_verified 晋升态。
    返回违规说明列表（空＝自洽）。只看 check_point（断言点）步骤——占位只对期望值有意义。
    """
    problems: list[str] = []
    for i, s in enumerate(provenance.steps):
        if s.E.strip() != 'check_point':
            continue
        has_placeholder = RUNTIME_PLACEHOLDER in s.G
        is_runtime_kind = s.source.kind == 'device_runtime'
        if is_runtime_kind and (not has_placeholder):
            problems.append(f'step[{i}] source is marked device_runtime (unknowable offline) yet a concrete value {s.G!r} was filled in — if the value is unknowable offline, fabricating one is forbidden; the expected value should contain the {RUNTIME_PLACEHOLDER} placeholder.')
        elif has_placeholder and (not is_runtime_kind):
            problems.append(f'step[{i}] expected value contains the {RUNTIME_PLACEHOLDER} placeholder yet its source is marked {s.source.kind!r} — a placeholder declares the value unknowable offline, so the source must be marked device_runtime.')
    return problems
