# 生成：tools/extract_engine.py ← InfoTest main/common/engine_track_schema.py（sha256 2661096ae361d229）。不在这里手改。
from __future__ import annotations
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Literal
from cex_core.engine.common.schema_identity import accepts_schema, canonical_schema

@dataclass(frozen=True)
class SchemaDeclaration:
    wire: str
    read_policy: Literal['family', 'exact']
    reason_zh: str

    @property
    def family(self) -> str:
        return canonical_schema(self.wire)
ENGINE_TRACK_SCHEMAS = MappingProxyType({'required_carriers': SchemaDeclaration('ist.required-carriers.v1', 'family', '已绑定的承载需求记录；兼容族名不代替需求原件验证。'), 'criterion_requirements': SchemaDeclaration('ist.criterion-requirements.v1', 'family', '独立判据需求原件，后缀不改变义务语义。'), 'authoring_account': SchemaDeclaration('ist.authoring-account.v1', 'family', '模型可见证据自述；验证scope和原记录，族名不签责任。'), 'authoring_tool_budget': SchemaDeclaration('ist.authoring-tool-budget.v1', 'family', '真实模型响应的累计预算观察，仍重算顺序和内容。'), 'authoring_tool_budget_receipt': SchemaDeclaration('ist.authoring-tool-budget-receipt.v1', 'family', '预算日志重放收据，仍须绑定同一原始派发。'), 'engine_gap': SchemaDeclaration('ist.engine-gap.v1', 'family', '模型主张，不能借族名升级为已确认引擎缺陷。'), 'authoring_account_tool_result': SchemaDeclaration('ist.authoring-account-tool-result.v1', 'exact', '当前工具调用的结果信封，与配对ToolMessage精确绑定。'), 'engine_error': SchemaDeclaration('ist.engine-error.v2', 'exact', '新增owner、不变量与强证语义，旧通用错误kind不得借用。'), 'authoring_failure_receipt': SchemaDeclaration('ist.compile.authoring-failure-receipt.v2', 'exact', '三轮、三自查和自述的强凭据，不能借旧封顶收据。'), 'authoring_failure_proof': SchemaDeclaration('ist.authoring-failure-proof.v2', 'exact', '当前强证算法的完整证明，不将未知版本解释成同一证明。'), 'engine_evidence': SchemaDeclaration('ist.engine-evidence.v1', 'exact', '本次归因brief的闭集信封，不能替代同派发的证据身份。'), 'engine_history': SchemaDeclaration('ist.engine-history.v1', 'family', '历史事实的只读披露，状态与有效性另行重算。'), 'case_quarantine': SchemaDeclaration('ist.case-quarantine.v1', 'family', '持久隔离记录；保留旧字节，不把记录存在当作缺陷证明。'), 'engine_bug_release': SchemaDeclaration('ist.engine-bug-release.v1', 'family', '持久解除记录，仍须验证对应隔离和真实故障验证通过凭据。'), 'authoring_attempt_scope': SchemaDeclaration('ist.authoring-attempt-scope.v1', 'family', '冻结尝试范围；原件、规则、输入和先后顺序仍须复核。'), 'engine_run_observation': SchemaDeclaration('ist.engine-run-observation.v1', 'family', '运行存活观察；身份不全保留未确认。'), 'compile_entry_inputs': SchemaDeclaration('ist.compile-entry-inputs.v1', 'family', '入口引用的持久记录，必须对回实际输入字节。'), 'engine_debt_event': SchemaDeclaration('ist.engine-debt-event.v1', 'family', '追加式故障记录事实，读取不删除历史或推断责任。'), 'engine_debt_index': SchemaDeclaration('ist.engine-debt-index.v1', 'family', '可重建索引，不替代故障记录原始事实。'), 'engine_debt_replay_inputs': SchemaDeclaration('ist.engine-debt-replay-inputs.v1', 'family', '冻结回放输入清单；每个文件SHA仍独立验证。'), 'engine_debt_replay_result': SchemaDeclaration('ist.engine-debt-replay-result.v1', 'family', '真实回放结果，仍须覆盖绑定输入且实际通过。'), 'engine_debt_verification_background': SchemaDeclaration('ist.engine-debt-verification-background.v1', 'family', '通过收据的背景身份，不从文件存在推断验证成功。'), 'engine_debt_verification': SchemaDeclaration('ist.engine-debt-verification.v1', 'family', '守门与真实回放收据，绑定代码、资产、输入及执行结果。'), 'engine_condition_disclosure': SchemaDeclaration('ist.engine-condition-disclosure.v1', 'family', '无归责条件披露，族名匹配不提升责任置信度。'), 'engine_control_binding_proof': SchemaDeclaration('ist.engine-control-binding-proof.v1', 'exact', '当前检查点铸造的类型化不变量证明，语义必须精确。'), 'authoring_supplement_brief': SchemaDeclaration('ist.authoring-account-supplement-brief.v1', 'exact', '受限单次诊断派发的模型信封。'), 'authoring_supplement_result': SchemaDeclaration('ist.authoring-account-supplement-result.v1', 'exact', '单次补交的控制结果，不接受未知结果协议。')})

def engine_schema_id(key: str) -> str:
    return ENGINE_TRACK_SCHEMAS[key].wire

def accepts_engine_schema(actual: Any, key: str) -> bool:
    declaration = ENGINE_TRACK_SCHEMAS[key]
    if declaration.read_policy == 'exact':
        return isinstance(actual, str) and actual == declaration.wire
    return accepts_schema(actual, declaration.family)
