# 生成：tools/extract_engine.py ← InfoTest main/ist_core/compile_engine/engine_errors.py（sha256 c387b97e18b17fdf）。不在这里手改。
from __future__ import annotations
from typing import Mapping
E_WORKER_TIMEOUT = '0001'
E_COLLECT_SETUP = '0002'
E_CONTRACT_STAMP = '0003'
E_ENVIRONMENT = '0004'
E_NO_LEDGER_CHANNEL = '0005'
E_MECHANICAL_CASE_IDENTITY = '0006'
E_ENGINE_INSERTED_ROW_INVALID = '0007'
E_COMMAND_TREE_UNAVAILABLE = '0008'
E_INVENTORY_RECEIPT_REDACTED = '0009'
E_WORKER_RESULT_ENVELOPE = '0010'
E_DELIVERY_BINDING_UNAVAILABLE = '0011'
E_FORK_CHANNEL_FAULT = '0012'
E_MECHANICAL_CASE_UNPRODUCIBLE = '0013'
E_RECOMPOSE_CHANNEL_FAULT = '0014'
E_ROUND_CAP_EXHAUSTED = '0015'
E_LLM_QUOTA_EXHAUSTED = '0016'
E_LLM_TRANSIENT_EXHAUSTED = '0017'
E_API_REQUEST_REJECTED = '0018'
E_API_AUTH_REJECTED = '0019'
E_ENTRY_INPUT_REFERENCES = '0031'
ENGINE_ERROR_CODES: tuple[str, ...] = (E_WORKER_TIMEOUT, E_COLLECT_SETUP, E_CONTRACT_STAMP, E_ENVIRONMENT, E_NO_LEDGER_CHANNEL, E_MECHANICAL_CASE_IDENTITY, E_ENGINE_INSERTED_ROW_INVALID, E_COMMAND_TREE_UNAVAILABLE, E_INVENTORY_RECEIPT_REDACTED, E_WORKER_RESULT_ENVELOPE, E_DELIVERY_BINDING_UNAVAILABLE, E_FORK_CHANNEL_FAULT, E_MECHANICAL_CASE_UNPRODUCIBLE, E_RECOMPOSE_CHANNEL_FAULT, E_ROUND_CAP_EXHAUSTED, E_LLM_QUOTA_EXHAUSTED, E_LLM_TRANSIENT_EXHAUSTED, E_API_REQUEST_REJECTED, E_API_AUTH_REJECTED, E_ENTRY_INPUT_REFERENCES)
CHECKPOINT_RESERVED_CODES: dict[str, str] = {'manifest_identity': '0020', 'volume_population': '0021', 'artifact_handoff': '0022', 'projection_receipt': '0023', 'closing_state': '0024', 'runtime_envelope': '0025', 'dispatch_settlement': '0026', 'window_binding': '0027', 'fact_vocabulary': '0028', 'supply_identity': '0029', 'rule_supply_disagreement': '0030'}
_CODE_SPACE = sorted((*ENGINE_ERROR_CODES, *CHECKPOINT_RESERVED_CODES.values()))
if _CODE_SPACE != [f'{_n:04d}' for _n in range(1, len(_CODE_SPACE) + 1)]:
    raise ValueError(f'engine four-digit code space must stay collision-free and contiguous: {_CODE_SPACE}')
CASE_SCOPED_CODES: frozenset[str] = frozenset({E_WORKER_TIMEOUT, E_ENVIRONMENT, E_CONTRACT_STAMP, E_NO_LEDGER_CHANNEL, E_MECHANICAL_CASE_IDENTITY, E_INVENTORY_RECEIPT_REDACTED, E_WORKER_RESULT_ENVELOPE, E_DELIVERY_BINDING_UNAVAILABLE, E_FORK_CHANNEL_FAULT, E_MECHANICAL_CASE_UNPRODUCIBLE, E_ROUND_CAP_EXHAUSTED, E_LLM_TRANSIENT_EXHAUSTED, E_API_REQUEST_REJECTED, E_ENTRY_INPUT_REFERENCES})
API_CAUSE_CODES: dict[str, str] = {'LLM_QUOTA_EXHAUSTED': E_LLM_QUOTA_EXHAUSTED, 'TRANSIENT_ERROR': E_LLM_TRANSIENT_EXHAUSTED, 'API_REQUEST_REJECTED': E_API_REQUEST_REJECTED, 'API_AUTH_REJECTED': E_API_AUTH_REJECTED}
API_SIDE_CODES: frozenset[str] = frozenset(API_CAUSE_CODES.values())
_UNSET = object()

def condition_from_legacy_code(aid: str, code: str, detail: str='', *, identity: Mapping | None=None, source_location: Mapping | None=None, observed: object=_UNSET, site: str='', inputs: Mapping | None=None, scope: str='') -> dict:
    from cex_core.engine.ist_core.compile_engine import engine_checkpoints as C
    if str(code) not in ENGINE_ERROR_CODES:
        raise ValueError(f'unknown legacy engine code: {code!r}')
    location = dict(source_location or C._location())
    location_site = f"{location.get('file', '')}:{location.get('function', '')}".strip(':')
    return C.condition_disclosure(site or location_site or 'legacy_code_observation', str(detail) if observed is _UNSET else observed, identity=identity, aid=str(aid or ''), legacy_code=str(code), inputs=inputs, source_location=location, scope=scope, detail=str(detail))

def is_batch_scoped(code: str, aid: str='') -> bool:
    if str(code or '') not in CASE_SCOPED_CODES:
        return True
    return not str(aid or '').strip()
ENGINE_ERROR_EVENT = 'engine_error'
CODE_TITLE_CN: dict[str, str] = {E_WORKER_TIMEOUT: 'worker 空转无产出', E_COLLECT_SETUP: '测试收集/初始化或批次人口账不可用', E_CONTRACT_STAMP: '机械脑图用例无法生成', E_ENVIRONMENT: '环境错误', E_NO_LEDGER_CHANNEL: '欠定判据无落账通道', E_MECHANICAL_CASE_IDENTITY: '机械用例身份不符', E_ENGINE_INSERTED_ROW_INVALID: '引擎插入的对照行不合法', E_COMMAND_TREE_UNAVAILABLE: '命令树投影不可用', E_INVENTORY_RECEIPT_REDACTED: '命令清单凭证被遮蔽破坏', E_WORKER_RESULT_ENVELOPE: '编写孔返回信封不合协议', E_DELIVERY_BINDING_UNAVAILABLE: '交付期权威绑定不可用', E_FORK_CHANNEL_FAULT: '编写孔进程被引擎自身通道中止', E_MECHANICAL_CASE_UNPRODUCIBLE: '机械用例产不出来且不该再问人', E_RECOMPOSE_CHANNEL_FAULT: '机器脑图产不出来（重组段引擎侧故障）', E_ROUND_CAP_EXHAUSTED: '重编轮次用尽仍未收敛', E_LLM_QUOTA_EXHAUSTED: 'LLM 端点账户配额/余额不足', E_LLM_TRANSIENT_EXHAUSTED: 'LLM 端点瞬态压力耗尽引擎重试', E_API_REQUEST_REJECTED: 'API错误：请求被拒（400）', E_API_AUTH_REJECTED: 'API错误：鉴权或权限被拒（401/403）', E_ENTRY_INPUT_REFERENCES: '编译入口引用侧车不可用'}
CODE_CAUSE_CN: dict[str, str] = {E_WORKER_TIMEOUT: '旧码登记未获可采信编写产物。无产出或预算结束本身不证明模型或引擎责任。', E_COLLECT_SETUP: '旧码登记 collect/setup 失败或批次 manifest 人口账不可用；具体观察以本条 detail 为准，编号不区分这两条来源。', E_CONTRACT_STAMP: '旧码登记机械脑图用例或身份章不可用；是否缺材料、读取失败或内部故障须看本条原始记录。', E_ENVIRONMENT: '旧码登记环境相关结算；是否已有明确确认以及观察范围须回查本条原始记录。', E_NO_LEDGER_CHANNEL: '旧码曾用于一致性账初始化、冲突结算或组题通道条件；不能只凭同一码断言共同根因。', E_MECHANICAL_CASE_IDENTITY: '旧码登记机械用例读取或身份不一致；变化由谁造成、是否为软件缺陷未由编号证明。', E_ENGINE_INSERTED_ROW_INVALID: '登记契约为引擎插入控制观测的 U3 绑定。新签发必须带真实检查器可复算的证明；原始用例整体是否正确不在此证明范围。', E_COMMAND_TREE_UNAVAILABLE: '旧码登记命令树投影不可用；缺失、不可读和来源不符不能单独证明软件根因或设备不支持。', E_INVENTORY_RECEIPT_REDACTED: '旧码登记命令清单凭据的遮蔽相关条件；具体差异及处理责任须由前后原始凭据证明。', E_WORKER_RESULT_ENVELOPE: '旧码登记编写结果信封未获受理；没有输出、解析失败和传输中止须按实际原始记录区分。', E_DELIVERY_BINDING_UNAVAILABLE: '旧码登记交付权威绑定不可用；编号不证明卷未变、设备已通过或用例没有问题。', E_FORK_CHANNEL_FAULT: '旧码登记编写通道中止或未完成；裸异常名称不能证明是引擎软件故障。', E_MECHANICAL_CASE_UNPRODUCIBLE: '旧码登记编写/回修未形成可用产物的旧结算；新运行不得据此省略模型失败的独立凭据条件。', E_RECOMPOSE_CHANNEL_FAULT: '旧码登记重组阶段未获可用机械脑图；来源或责任未闭合时只披露实际停点。', E_ROUND_CAP_EXHAUSTED: '旧码登记轮次预算用尽。预算结束不单独证明能力不足或引擎缺陷。', E_LLM_QUOTA_EXHAUSTED: '旧码表示上游配额类分类；实际返回、适用账户及限制条件以原始 API 记录为准。', E_LLM_TRANSIENT_EXHAUSTED: '旧码表示上游瞬态重试结束分类；具体调用结果与重试记录分别保留，不由编号推断其他组件健康。', E_API_REQUEST_REJECTED: '旧码登记 API 请求被拒的分类；原始状态码和响应内容保留，拒绝本身不证明请求构造或引擎没有问题。', E_API_AUTH_REJECTED: '旧码登记 API 身份/权限类拒绝；401/403 本身不区分密钥、权限、区域、配额等具体限制。', E_ENTRY_INPUT_REFERENCES: '旧码登记编译入口引用侧车不可用；收据与侧车必须同生，缺失不证明用例稿不合格。'}
CODE_TITLE_CN.update({E_WORKER_TIMEOUT: '编写未获可采信产物', E_WORKER_RESULT_ENVELOPE: '编写结果信封未获受理', E_FORK_CHANNEL_FAULT: '编写通道未完成（历史分类）', E_RECOMPOSE_CHANNEL_FAULT: '重组未获可用机械脑图', E_LLM_QUOTA_EXHAUSTED: 'API配额类响应记录', E_LLM_TRANSIENT_EXHAUSTED: 'API瞬态类响应记录', E_API_REQUEST_REJECTED: 'API请求拒绝记录', E_API_AUTH_REJECTED: 'API身份/权限类响应记录'})

class CommandTreeUnavailable(RuntimeError):

    def __init__(self, detail: str, *, device_build: str='') -> None:
        self.detail = str(detail or 'command-tree projection is unavailable')
        self.device_build = str(device_build or '')
        super().__init__(self.detail)

class EntryInputReferencesUnavailable(ValueError):

    def __init__(self, detail: str='') -> None:
        self.detail = str(detail or 'compile entry input references unavailable')
        self.engine_error_code = E_ENTRY_INPUT_REFERENCES
        super().__init__(self.detail)
ENTRY_INPUT_FORK_CAUSES: frozenset[str] = frozenset({EntryInputReferencesUnavailable.__name__})

def is_engine_error_code(code: str) -> bool:
    return str(code or '') in ENGINE_ERROR_CODES

def engine_error_fact(aid: str, code: str, detail: str='') -> dict:
    if not is_engine_error_code(code):
        raise ValueError(f'unknown engine error code: {code!r}')
    fact = {'ev': ENGINE_ERROR_EVENT, 'aid': str(aid or ''), 'code': str(code)}
    if detail:
        fact['detail'] = str(detail)[:400]
    return fact

def engine_errors(facts: list[dict]) -> list[dict]:
    return [f for f in facts if f.get('ev') == ENGINE_ERROR_EVENT]

def active_engine_errors(facts: list[dict]) -> list[dict]:
    from cex_core.engine.ist_core.compile_engine import facts as _F
    return engine_errors(_F.this_run_slice(facts))

def case_scoped_engine_errors(facts: list[dict]) -> list[dict]:
    return [fact for fact in active_engine_errors(facts) if ('owner' not in fact or fact['owner'] == 'engine') and error_halts_batch(fact) is False]
UNVERIFIABLE_ERROR_EVENT = 'engine_error_unverifiable_disclosure'

def _interpret_error(fact: dict) -> tuple[bool | None, dict | None]:
    from cex_core.engine.ist_core.compile_engine import engine_checkpoints as C
    from cex_core.engine.common.schema_identity import write_schema
    from cex_core.engine.ist_core.security_scrub import scrub_value
    from cex_core.engine.ist_core.compile_engine.terminal_credentials import _fact_sha256
    try:
        if any((key in fact for key in ('schema', 'error_id', 'owner'))):
            C.validate_error(fact)
            return (fact.get('mode') == 'halt' or (fact.get('mode') == 'pause' and fact.get('scope') == 'batch'), None)
        if not is_engine_error_code(fact.get('code')):
            raise ValueError('legacy error code is not registered')
        return (is_batch_scoped(str(fact.get('code') or ''), str(fact.get('aid') or '')), None)
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        source_sha = _fact_sha256(fact)
        failure = scrub_value({'exception': type(exc).__name__, 'reason': str(exc)}, scrub_paths=False)
        diagnostic_id = 'error-read:' + C.digest({'source': source_sha, 'failure': failure})
        disclosure = scrub_value({'schema': write_schema('ist.engine-error-unverifiable-disclosure'), 'ev': UNVERIFIABLE_ERROR_EVENT, 'aid': str(fact.get('aid') or ''), 'diagnostic_id': diagnostic_id, 'original_error_id': str(fact.get('error_id') or ''), 'original_code': str(fact.get('code') or ''), 'source_record_sha256': source_sha, 'validation_exception': failure['exception'], 'validation_error': failure['reason'], 'decision_status': 'unverified'}, scrub_paths=False)
        return (None, disclosure)

def error_halts_batch(fact: dict) -> bool | None:
    return _interpret_error(fact)[0]

def unverifiable_error_disclosures(facts: list[dict]) -> list[dict]:
    return [disclosure for fact in active_engine_errors(facts) if (disclosure := _interpret_error(fact)[1]) is not None]

def batch_aborted(facts: list[dict]) -> bool:
    return any((error_halts_batch(fact) is True for fact in active_engine_errors(facts)))
