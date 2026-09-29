# 生成：tools/extract_engine.py ← InfoTest scripts/gen_rule_registry.py（sha256 b2efe0c8ab25d765）。不在这里手改。
from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
SCHEMA = 'ist.ide.rule-registry'
OUT = Path('knowledge/data/compile_ref/rule_registry.json')
_CURATED_RULES = [{'rule_id': 'R-anchor-literal', 'status': 'verified', 'name_zh': '字面锚定验证', 'zh_template': '配置后用只读查看命令确认目标对象/记录按配置值出现，期望值逐字来自配置入参或手册原文', 'applicability': {'capability_families': ['algo_deterministic', 'lastresort_fallback', 'record_types', 'listener', 'multi_object'], 'verification_shapes': ['found', 'not_found']}, 'family_status': {'algo_deterministic': 'verified', 'lastresort_fallback': 'hypothesis', 'record_types': 'hypothesis', 'listener': 'hypothesis', 'multi_object': 'hypothesis'}, 'authority_refs': ['内部取证文档（已脱敏）#algo_deterministic', '内部取证文档（已脱敏）'], 'evidence': {'build': 'sample', 'note': '试点 ga 2/2 带翻转凭据'}}, {'rule_id': 'R-block-stats-format', 'status': 'verified', 'name_zh': '统计块格式验证', 'zh_template': '读取统计输出的块格式字段并按行为预期核对计数方向；精确计数在共享床受外来命中干扰，只验方向或区间', 'applicability': {'capability_families': ['stats_counters'], 'verification_shapes': ['found', 'dist']}, 'authority_refs': ['内部取证文档（已脱敏）#stats_counters', '内部取证文档（已脱敏）'], 'evidence': {'build': 'sample', 'note': '块格式随 build 漂移实证'}}, {'rule_id': 'R-dist-interval', 'status': 'hypothesis', 'name_zh': '分布区间验证', 'zh_template': '对算法类行为发起 N 次探测，断言命中分布落在权重推导的区间内；不写精确序位（多核调度非确定，一律豁免）', 'applicability': {'capability_families': ['algo_rr', 'algo_distribution'], 'verification_shapes': ['dist', 'member']}, 'authority_refs': ['内部取证文档（已脱敏）#algo_rr', '内部取证文档（已脱敏）#序位'], 'evidence': {'build': 'sample', 'note': '受控形态 3,3,2/6,4,2 实证'}}, {'rule_id': 'R-time-window', 'status': 'hypothesis', 'name_zh': '时序窗口状态对验证', 'zh_template': 'H 捕获三步式：先捕获基准观测，等待/触发时序条件后再次观测，断言两次观测的关系（同/异）而非绝对值', 'applicability': {'capability_families': ['session_persistence'], 'verification_shapes': ['relation_same', 'relation_diff']}, 'authority_refs': ['内部取证文档（已脱敏）#session_persistence'], 'evidence': {'build': '', 'note': '形态在仓，本轮未上机'}}, {'rule_id': 'R-state-pair', 'status': 'hypothesis', 'name_zh': '状态对翻转验证', 'zh_template': '操作前先确认对象存在（或不存在），执行删除/恢复后断言状态翻转；两态都要观测，单态断言在干净床是恒真', 'applicability': {'capability_families': ['delete_verify', 'persist_save_restore'], 'verification_shapes': ['found', 'not_found']}, 'authority_refs': ['内部取证文档（已脱敏）#delete_verify'], 'evidence': {'build': '', 'note': '668 方向教训在案，正确方向未重验'}}, {'rule_id': 'R-health-transition', 'status': 'hypothesis', 'name_zh': '健康态迁移验证', 'zh_template': '构造健康检查条件变化，观测目标状态在预期方向迁移（UP→DOWN 或反向），断言迁移后的状态词', 'applicability': {'capability_families': ['health_updown'], 'verification_shapes': ['found']}, 'authority_refs': ['内部取证文档（已脱敏）#health_updown'], 'evidence': {'build': '', 'note': '未验证'}}, {'rule_id': 'R-ssl-import-activate', 'status': 'draft-usable', 'name_zh': '证书导入激活验证', 'zh_template': '按框架方法族导入密钥/证书并确认自动激活语义，用只读查看命令确认证书槽位与激活状态；参数位数按方法签名闭集', 'applicability': {'capability_families': ['cert_ssl'], 'verification_shapes': ['found']}, 'authority_refs': ['内部取证文档（已脱敏）#C1'], 'evidence': {'build': '', 'note': 'C1 草案可用；C3-C5 待探针补证'}}, {'rule_id': 'R-ssl-ca-role', 'status': 'draft-usable', 'name_zh': 'CA 角色槽验证', 'zh_template': 'CA 证书按三角色分别导入并逐槽确认——角色装错不报错不崩卷，只有槽位查看能暴露（选择点错误后面不会自己现形）', 'applicability': {'capability_families': ['cert_ssl'], 'verification_shapes': ['found']}, 'authority_refs': ['内部取证文档（已脱敏）#C2'], 'evidence': {'build': '', 'note': 'C2 草案可用；双证装反同族静默错'}}]

def build_registry() -> dict:
    rules = sorted(_CURATED_RULES, key=lambda r: r['rule_id'])
    body = {'schema': SCHEMA, 'rules': rules}
    content_sha = hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()
    return {**body, '_meta': {'generated_by': 'scripts/gen_rule_registry.py', 'generated_at': datetime.now(timezone.utc).isoformat(), 'curated_parts': ['rules'], 'generated_parts': [], 'rule_count': len(rules), 'content_sha256': content_sha, 'sources': ['内部取证文档（已脱敏）', '内部取证文档（已脱敏）'], 'exclusions': {'cert_ssl_C3_C5': '待探针补证据，不进本版', 'cert_ssl_C6': '须另行裁决'}}}

def main() -> None:
    payload = build_registry()
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"wrote {OUT} rules={payload['_meta']['rule_count']}")
if __name__ == '__main__':
    main()
