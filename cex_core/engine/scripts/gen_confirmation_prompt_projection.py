# 生成：tools/extract_engine.py ← InfoTest scripts/gen_confirmation_prompt_projection.py（sha256 db38b798f0b23cec）。不在这里手改。
from __future__ import annotations
from cex_core.engine._root import _cex_data_path
import ast
import json
import sys
from pathlib import Path
_ROOT = _cex_data_path('')
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from cex_core.engine.case_compiler.apv_lang import mirror_src
_MIRROR = _ROOT / 'knowledge/framework/mirror'
_OUT = _ROOT / 'knowledge/data/compile_ref/confirmation_prompt_patterns.json'

def _is_const_str(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str)

def _cmd_config_shape(node: ast.AST | None) -> dict | None:
    if not isinstance(node, ast.Call):
        return None
    f = node.func
    if not (isinstance(f, ast.Attribute) and f.attr == 'cmd_config'):
        return None
    args = node.args
    a0c = _is_const_str(args[0]) if len(args) > 0 else False
    a1c = _is_const_str(args[1]) if len(args) > 1 else False
    return {'nargs': len(args), 'a0_const': a0c, 'a0_val': args[0].value if a0c else None, 'a1_const': a1c, 'a1_val': args[1].value if a1c else None, 'node': node}

def _qualifying(shape: dict | None) -> bool:
    return shape is not None and shape['nargs'] == 2 and shape['a0_const'] and shape['a1_const']

def _stmt_shape(stmt: ast.stmt) -> dict | None:
    call = stmt.value if isinstance(stmt, (ast.Expr, ast.Assign)) else None
    return _cmd_config_shape(call) if call is not None else None

def _find_sequences(tree: ast.Module) -> list[dict]:
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        body = node.body
        n = len(body)
        i = 0
        while i < n:
            shape = _stmt_shape(body[i])
            if shape is not None and _qualifying(shape):
                j = i
                seq: list[dict] = []
                while j < n:
                    sh2 = _stmt_shape(body[j])
                    if sh2 is not None and _qualifying(sh2):
                        seq.append({'lineno': body[j].lineno, 'send': sh2['a0_val'], 'wait_for': sh2['a1_val']})
                        j += 1
                    else:
                        break
                if len(seq) >= 2:
                    prev_stmt = body[i - 1] if i > 0 else None
                    prev_call = (prev_stmt.value if isinstance(prev_stmt, (ast.Expr, ast.Assign)) else None) if prev_stmt is not None else None
                    next_stmt = body[j] if j < n else None
                    next_shape = _stmt_shape(next_stmt) if next_stmt is not None else None
                    out.append({'func': node.name, 'def_line': node.lineno, 'seq': seq, 'is_start_of_body': i == 0, 'trigger_src': ast.unparse(prev_call) if prev_call is not None else None, 'final_step_no_anchor': {'send': next_shape['a0_val']} if next_shape is not None and next_shape['nargs'] == 1 and next_shape['a0_const'] else None})
                i = j
            else:
                i += 1
    return out

def _final_step_fields(seq: list[dict], next_call: dict | None) -> dict:
    if next_call is not None:
        return {'final_step_no_anchor': 'no_anchor', 'final_step_value': next_call['send'], 'final_step_note': None}
    if len(seq) <= 2:
        return {'final_step_no_anchor': 'not_observed', 'final_step_value': None, 'final_step_note': f"序列仅 {len(seq)} 步(trigger+应答),函数体后续无任何 cmd_config 语句(如 apv.py::reboot 后接 time.sleep+ping 轮询)——'末步无锚收尾'这个概念对这条序列不适用,不是'检查过、确实没有'。"}
    last = seq[-1]
    return {'final_step_no_anchor': 'has_anchor', 'final_step_value': None, 'final_step_note': f"顶层序列末步仍带锚(send={last['send']!r}, wait_for={last['wait_for']!r}),不是本判据要求的顶层单参无锚调用——已检查、确认不是,不是没检查。(ssl_comm.py::sm2CsrVhost 的已知细节:函数体在 `if int(signature)==2:` 条件分支里还有一处裸 `cmd_config('No')`,与其余 10 条的收尾形态相同,只是被条件语句包住、不在顶层连续序列内——本生成器判据只看顶层连续调用,不下钻进条件分支,如实标注不代表该分支不存在。)"}

def _build_lib_entry(file_rel: str, found: dict) -> dict:
    seq = found['seq']
    if found['is_start_of_body']:
        trigger_command = f"cmd_config({seq[0]['send']!r}, {seq[0]['wait_for']!r})"
        steps = seq[1:]
    else:
        trigger_command = found['trigger_src']
        steps = seq
    anchors = sorted({s['wait_for'] for s in seq})
    return {'trigger_command': trigger_command, 'trigger_is_first_body_statement': found['is_start_of_body'], 'steps': [{'send': s['send'], 'wait_for': s['wait_for']} for s in steps], 'anchor_values_used': anchors, **_final_step_fields(seq, found['final_step_no_anchor']), 'provenance': {'file': file_rel, 'function': found['func'], 'def_line': found['def_line'], 'step_lines': [s['lineno'] for s in seq]}}

def build() -> dict:
    lib_entries: list[dict] = []
    smoke_seq_counter: dict[tuple, dict] = {}
    unreadable: list[str] = []
    for py in sorted(_MIRROR.rglob('*.py')):
        rel = str(py.relative_to(_ROOT))
        text = mirror_src(str(py.relative_to(_MIRROR)))
        if not text and py.stat().st_size > 0:
            unreadable.append(f'{rel}: mirror_src 读取失败(返回空串,文件非空)')
            continue
        try:
            tree = ast.parse(text)
        except Exception as exc:
            unreadable.append(f'{rel}: {exc}')
            continue
        found_list = _find_sequences(tree)
        is_lib = '/lib/' in rel
        for found in found_list:
            if is_lib:
                lib_entries.append(_build_lib_entry(rel, found))
            else:
                key = tuple(((s['send'], s['wait_for']) for s in found['seq']))
                bucket = smoke_seq_counter.setdefault(key, {'count': 0, 'example_file': rel, 'example_func': found['func']})
                bucket['count'] += 1
    lib_seq_keys = {tuple(((s['send'], s['wait_for']) for s in e['steps'])) for e in lib_entries}
    smoke_observations = []
    for key, bucket in sorted(smoke_seq_counter.items(), key=lambda kv: -kv[1]['count']):
        stripped = key[1:]
        matches_lib = stripped in lib_seq_keys or key in lib_seq_keys
        smoke_observations.append({'sequence': [{'send': a0, 'wait_for': a1} for a0, a1 in key], 'count': bucket['count'], 'example_provenance': {'file': bucket['example_file'], 'function': bucket['example_func']}, 'aligned_match_in_lib': matches_lib})
    return {'_meta': {'purpose': '框架自身已有的 confirmation-prompt 应答序列(内部任务 SPEC S1)——worker 沙箱够不到 mirror 源码、投影此前也没有这类知识(内部工单 §0.3 实测零命中),本投影补上这个缺口。', 'regenerate': 'python scripts/gen_confirmation_prompt_projection.py', 'scope_ruling': "只投 lib/ 为权威范式（内部评审裁定，数据独立支持:全 mirror 精确判据命中 1651 个函数,其中 trigger 形态干净的只有 10 个且全在 lib/;smoke_test 的 1640 个里 77% 提不出干净 trigger 候选,按字面全投会产出大量字段不全的条目)。smoke_test 的去重序列**只记计数,不投序列原文**（内部评审裁定：初版曾把夹具明文口令带进过 send 字段（内部事件，细节已脱敏）;compile_ref/ 是 agent 无限制读根,而 mirror 源码因含敏感内容只对引擎规则开放白名单（细节已脱敏）——投影不得绕过那道最小暴露边界。该字段当时零消费者,删原文零功能损失;计数不含内容,保留以支撑本条 scope 裁决)。", 'matching_criterion': '同一函数体内连续 >=2 次 self.cmd_config(<字符串常量>, <字符串常量>) 调用(AST 精确判据,非文本正则)——这是判据命中的门槛,不是每条 lib_patterns 条目 steps 字段的长度下限。当序列从函数体第一条语句开始(无前置语句可提升为 trigger_command,见trigger_command_note)时,序列自身第一个元素被提升为 trigger_command、从 steps 里排除,故该条目 steps 可能只有 N-1 条(如 apv.py::reboot,判据命中的连续序列长度是 2,steps 字段长度是 1)——按字面数 steps 条数会以为判据出错或数据缺失,实际是 trigger 提升规则的正常结果。', 'trigger_command_note': '取序列前一条语句(若是 cmd_config 调用)的源码;若序列从函数体第一条语句开始(无前置语句),trigger_command 取序列自身第一个元素(如实标注 trigger_is_first_body_statement=true,见 apv.py::reboot——这是真实存在的变体,不是异常,不代表判据出错)。', 'final_step_no_anchor_note': '三个互斥字符串,不是 true/false/null(内部评审裁定 + Theory 复核后改字符串——机械理由:`if not x:` 是最自然的消费写法,而 False/None 在这类写法下天然被当成同一件事收走,值分对了也保护不了消费者,同 内部工单 framework_result=None 承载多种成因那条)——"no_anchor"=顶层序列后紧跟单参无锚 cmd_config(9/11,选这条判据是因为全 mirror 1651 个候选里 87%/1435个 都跟着这种收尾调用,比trigger 判据更可靠);"has_anchor"=没有那种顶层调用,但序列自身末步观测到带锚收尾,已检查确认不是无锚形态(ssl_comm.py::sm2CsrVhost,见该条 final_step_note——它在条件分支里其实还有一处裸 cmd_config(\'No\'),本生成器不下钻进条件分支);"not_observed"=序列过短(≤2步)+函数体后续无任何 cmd_config 语句,\'末步收尾\'概念对它不适用(apv.py::reboot)。has_anchor 与not_observed 是两种不同的观测,不能都当成\'没有\'处理——这正是改成字符串哨兵要防的误读。', 'lib_entry_count': len(lib_entries), 'smoke_test_observation_count': len(smoke_observations), 'smoke_test_aligned_in_lib_count': sum((1 for o in smoke_observations if o['aligned_match_in_lib'])), 'unreadable_files': unreadable}, 'lib_patterns': lib_entries}

def main() -> None:
    data = build()
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    m = data['_meta']
    print(f"wrote {_OUT.relative_to(_ROOT)} — lib_patterns={m['lib_entry_count']} smoke_seqs_counted={m['smoke_test_observation_count']}(aligned={m['smoke_test_aligned_in_lib_count']},原文不投影) unreadable={len(m['unreadable_files'])}")
if __name__ == '__main__':
    main()
