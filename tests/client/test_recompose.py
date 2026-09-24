"""脑图重组在客户端走通：从已同步的数据包摆出引擎数据根 → 准备派发（快照、定位规格书、
回执）→ 按案提交（引擎同一套逐字闭集判据，违例结构化拒绝）→ 密封出 machine_mindmap.json。

需要同级 InfoTest 检出与它的 venv：数据包里的规格书代际由 InfoTest 自己的发布器生成（与
导入器取数同源），projections 用 InfoTest 入库的那几份。整个流程在子进程里跑，每个用例
一个独立的引擎数据根。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import INFOTEST_ROOT, REPO_ROOT

INFOTEST_PYTHON = Path(os.environ.get("INFOTEST_PYTHON")
                       or Path.home() / ".venvs" / "infotest-engine" / "bin" / "python")
pytestmark = pytest.mark.skipif(
    not (INFOTEST_ROOT / "main" / "kms" / "spec_generation.py").is_file()
    or not INFOTEST_PYTHON.is_file(),
    reason="需要 InfoTest 检出和它的 venv（INFOTEST_ROOT / INFOTEST_PYTHON）")

A1, A2 = "203600000000000001", "203600000000000002"
TITLE = "1.配置port 为53.执行write mem后重启设备\n2.查看sdns listener  [check1]"
SPEC_NAME = "12345_Listener_Spec.md"
SPEC_TEXT = "# 监听器配置指南\n\n3、监听器端口修改后需执行 write mem 才落盘\n4、重启设备后未保存的监听器配置回退为出厂值\n"


def _case_node(autoid: str) -> dict:
    return {"data": {"text": TITLE, "autoid": autoid}, "children": [
        {"data": {"text": "2.查看sdns listener"},
         "children": [{"data": {"text": "[check1]配置未被保存"}, "children": []}]}]}


def _mindmap(root_title: str, second: dict | None = None) -> list:
    return [{"data": {"text": root_title}, "children": [
        {"data": {"text": "配置保存"}, "children": [_case_node(A1), second or _case_node(A2)]}]}]


def _contract_case(autoid: str, expectation: str = "配置未被保存",
                   origin: str = "expectation:check1") -> dict:
    return {
        "autoid": autoid, "group_path": ["配置保存"], "title": TITLE, "bucket": "exp_recipe",
        "contract": {"intent": TITLE, "verification_method": "查看sdns listener",
                     "expectation": expectation},
        "origin": {"intent": "title", "verification_method": "step:2", "expectation": origin},
        "steps": [{"n": "2", "text": "2.查看sdns listener"}],
        "expectations_by_step": [{"n": "2", "text": "[check1]配置未被保存",
                                  "origin": "expectation:check1",
                                  "assertion": None}],
        "command_check": [], "depends_on": None, "adaptation_notes": [], "proposal": [],
        "step_structure": [{"n": "2", "objects": [], "operations": [], "stated_conditions": [],
                            "free_slots": []}],
    }


def _bundle(tmp_path: Path, specs: dict[str, str] | None = None) -> Path:
    """用 InfoTest 自己的发布器生成一代规格书，再和入库 projections 一起摆成数据包。"""
    specs = specs or {SPEC_NAME: SPEC_TEXT}
    store = tmp_path / "it" / "knowledge" / "data" / "spec"
    script = f'''
import sys; sys.path.insert(0, {str(INFOTEST_ROOT)!r})
from pathlib import Path
from main.kms import spec_generation as g
store = Path({str(store)!r})
gid, staging = g._new_staging_generation(store)
for name, text in {specs!r}.items():
    (staging / "docs" / name).write_text(text, encoding="utf-8")
g.save_state(staging / "state.tsv", {{}})
g._publish_generation(staging, gid)
print(gid)
'''
    proc = subprocess.run([str(INFOTEST_PYTHON), "-c", script], capture_output=True, text=True,
                          timeout=120)
    assert proc.returncode == 0, proc.stderr[-1500:]
    gid = proc.stdout.strip().splitlines()[-1]
    generation = store / "generations" / gid
    files: dict[str, bytes] = {
        "spec/manifest.json": (generation / "manifest.json").read_bytes(),
        "spec/index.json": (generation / "index.json").read_bytes(),
        "spec/state.tsv": (generation / "state.tsv").read_bytes(),
    }
    for name in specs:
        files[f"spec/docs/{name}"] = (generation / "docs" / name).read_bytes()
    tracked = subprocess.run(["git", "ls-files", "knowledge/data/compile_ref"], cwd=INFOTEST_ROOT,
                             capture_output=True, text=True, check=True).stdout.split()
    for rel in tracked:
        files["projections/" + rel.split("compile_ref/", 1)[1]] = (INFOTEST_ROOT / rel).read_bytes()
    out = tmp_path / "bundle_files.json"
    out.write_text(json.dumps({k: v.hex() for k, v in files.items()}), encoding="utf-8")
    return out


def _run(tmp_path: Path, steps: str, root_title: str = "12345 监听器改造",
         specs: dict[str, str] | None = None, second: dict | None = None) -> list[dict]:
    """在子进程里：建工作区、落数据包、写脑图，然后按 steps 调工具，每步输出一行 JSON。"""
    bundle_files = _bundle(tmp_path, specs)
    ws_root = tmp_path / "ws"
    script = f'''
import hashlib, json, sys
from pathlib import Path
sys.path.insert(0, {str(REPO_ROOT)!r})
from cex_client import workspace as wsmod, tools
ws = wsmod.init(Path({str(ws_root)!r}), server="https://ces.example.test", device_build="B_1")
files = {{k: bytes.fromhex(v) for k, v in json.loads(Path({str(bundle_files)!r}).read_text()).items()}}
root = ws.bundle_dir()
entries = []
for rel, data in files.items():
    (root / rel).parent.mkdir(parents=True, exist_ok=True)
    (root / rel).write_bytes(data)
    entries.append({{"kind": rel.split("/", 1)[0], "path": rel,
                     "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}})
(root / "manifest.json").write_text(json.dumps({{"bundle_id": "f" * 64, "build": "B_1",
    "entries": entries}}), encoding="utf-8")
Path(ws.root / "mm.json").write_text(json.dumps({_mindmap(root_title, second)!r}, ensure_ascii=False),
                                     encoding="utf-8")
def call(name, **args):
    print(json.dumps(tools.call(name, {{"workspace": str(ws.root), **args}}), ensure_ascii=False))
{steps}
'''
    proc = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True,
                          timeout=300, env={**os.environ, "CEX_ENGINE_DATA_ROOT": ""})
    assert proc.returncode == 0, proc.stderr[-3000:]
    return [json.loads(line) for line in proc.stdout.splitlines() if line.startswith("{")]


def test_prepare_binds_the_matched_spec_and_submissions_are_judged_by_the_engine(tmp_path):
    good = _contract_case(A1)
    bad = _contract_case(A2, expectation="配置已被保存")  # 不是脑图或规格书里的原文
    results = _run(tmp_path, f'''
call("cex_recompose_prepare", mindmap="mm.json")
call("cex_recompose_submit_cases", out_name="mm", cases={[bad]!r})
call("cex_recompose_submit_cases", out_name="mm", cases={[good]!r})
call("cex_recompose_seal", out_name="mm")
''')
    prepared, rejected, accepted, sealed = results
    assert prepared["ok"] and prepared["case_autoids"] == [A1, A2]
    assert prepared["governing_spec"]["status"] == "bound"
    assert prepared["governing_spec"]["name"] == SPEC_NAME
    assert Path(prepared["governing_spec"]["path"]).read_text(encoding="utf-8") == SPEC_TEXT
    assert prepared["defect_spec_status"] == "not_queried"
    batch = tmp_path / "ws" / "compile_outputs" / "mm"
    spec_status = json.loads((batch / "governing_spec_status.json").read_text(encoding="utf-8"))
    assert spec_status["schema"] == "ist.governing-spec-status" and spec_status["name"] == SPEC_NAME
    assert rejected["ok"] is False and rejected["status"] == "rejected"
    assert rejected["violations"], rejected
    assert accepted["ok"] is True and A1 not in accepted.get("outstanding_autoids", [A1])
    assert sealed["ok"] and sealed["sealed_case_count"] == 1 and sealed["missing_autoids"] == [A2]
    artifact = json.loads(Path(sealed["artifact"]).read_text(encoding="utf-8"))
    assert artifact["governing_spec"] == SPEC_NAME
    assert [c["autoid"] for c in artifact["cases"]] == [A1]
    assert artifact["cases"][0]["contract"]["expectation"] == "配置未被保存"


def test_a_title_without_a_spec_proceeds_with_no_governing_spec(tmp_path):
    (prepared,) = _run(tmp_path, 'call("cex_recompose_prepare", mindmap="mm.json")',
                       root_title="监听器改造")
    assert prepared["ok"] and prepared["governing_spec"]["status"] == "no_governing_spec"
    assert prepared["defect_spec_status"] == "no_ticket_reference"
    assert "defect_spec_note" not in prepared


def test_a_ticket_title_without_a_spec_is_resolved_absent_and_says_why(tmp_path):
    """根标题带单号：引擎会去查单；客户端没有签发通道，结论与引擎查单不可用时相同。"""
    (prepared,) = _run(tmp_path, 'call("cex_recompose_prepare", mindmap="mm.json")',
                       root_title="67890 监听器改造")
    assert prepared["ok"] and prepared["governing_spec"]["status"] == "no_governing_spec"
    assert prepared["defect_spec_status"] == "resolved_absent"
    assert "cex_bug_get" in prepared["defect_spec_note"]


def test_several_matching_specs_proceed_as_ambiguous_with_reference_slices(tmp_path):
    """与引擎一致：多个候选不停下，状态 ambiguous，候选切片只作参考（零签发权）。"""
    other = "12345_Listener_Old_Spec.md"
    (prepared,) = _run(tmp_path, 'call("cex_recompose_prepare", mindmap="mm.json")',
                       specs={SPEC_NAME: SPEC_TEXT, other: "# 旧版\n\n监听器\n"})
    assert prepared["ok"] and prepared["governing_spec"]["status"] == "ambiguous"
    assert prepared["defect_spec_status"] == "not_queried"
    refs = {ref["name"]: ref for ref in prepared["governing_spec"]["references"]}
    assert set(refs) == {SPEC_NAME, other}
    head = Path(refs[SPEC_NAME]["path"]).read_text(encoding="utf-8").splitlines()[0]
    assert "signing_power=none" in head


def test_pinning_none_or_an_unknown_spec(tmp_path):
    declined, unknown = _run(tmp_path, '''
call("cex_recompose_prepare", mindmap="mm.json", spec="none")
call("cex_recompose_prepare", mindmap="mm.json", spec="nope.md")
''')
    assert declined["ok"] and declined["governing_spec"]["resolution"] == "user_declined_retry"
    assert declined["defect_spec_status"] == "resolved_absent"
    assert unknown["ok"] is False and "not in the synced spec generation" in unknown["error"]


def test_defect_spec_status_matches_the_engine_helpers():
    """缺陷单状态逐字段对拍 InfoTest nodes.py 的构造函数。查单那一路：InfoTest 用一个
    查单必抛的替身（异常类名即客户端写的原因），再按引擎的"未知→resolved_absent"收口。"""
    titles = ["12345 监听器改造", "BUG-67890 端口", "BUG#1234", "监听器改造",
              "v1.2.3456 版本说明", "21.2.3456 回归", "对比 12345 与 67890", "Bug：4321 回归"]
    script = f'''
import json, sys
sys.path.insert(0, {str(INFOTEST_ROOT)!r})
from main.ist_core.compile_engine import nodes as n
class client_has_no_defect_spec_channel(Exception):
    pass
def _raise(**_kw):
    raise client_has_no_defect_spec_channel()
n._BUG_SEARCH_OVERRIDE = _raise
out = {{"bound": n._defect_spec_not_queried(),
        "ambiguous": n._defect_spec_not_queried(reason="openkm_ambiguous"),
        "declined": n._defect_spec_resolved_absent(reason="user_declined_retry")}}
for t in {titles!r}:
    st = n._resolve_recompose_defect_spec(root_titles=[t], mindmap_text="", source_sha256="0" * 64)
    if n._defect_spec_is_unknown(st):
        st = n._defect_spec_resolved_absent(reason=n._spec_retry_exhausted_reason(False),
                                            raw_status=str(st.get("status") or ""),
                                            unresolved=n._defect_spec_lookup_unresolved(st))
    out[t] = st
print(json.dumps(out, ensure_ascii=False))
'''
    proc = subprocess.run([str(INFOTEST_PYTHON), "-c", script], capture_output=True, text=True,
                          timeout=300)
    assert proc.returncode == 0, proc.stderr[-3000:]
    engine = json.loads(proc.stdout.strip().splitlines()[-1])
    from cex_client import recompose

    absent = {"status": "no_governing_spec"}
    assert recompose._defect_spec({"status": "bound"}, "x", False) == engine["bound"]
    assert recompose._defect_spec({"status": "ambiguous"}, "x", False) == engine["ambiguous"]
    assert recompose._defect_spec(absent, "12345 x", True) == engine["declined"]
    for title in titles:
        assert recompose._defect_spec(absent, title, False) == engine[title], title


def test_submitting_before_prepare_is_refused(tmp_path):
    (result,) = _run(tmp_path, 'call("cex_recompose_submit_cases", out_name="mm", cases=[])')
    assert result["ok"] is False and "cex_recompose_prepare" in result["error"]


def test_the_client_flow_matches_infotest_modules_on_the_same_inputs(tmp_path):
    """同一份脑图、绑定、规格书代际与案：客户端这层胶水的结果与直接调 InfoTest 原模块一致。"""
    good, bad = _contract_case(A1), _contract_case(A2, expectation="配置已被保存")
    client = _run(tmp_path, f'''
call("cex_recompose_prepare", mindmap="mm.json")
call("cex_recompose_submit_cases", out_name="mm", cases={[bad]!r})
call("cex_recompose_submit_cases", out_name="mm", cases={[good]!r})
call("cex_recompose_seal", out_name="mm")
''')
    ws_root = tmp_path / "ws"
    state = json.loads((ws_root / ".compile-excel" / "recompose" / "mm.json").read_text(encoding="utf-8"))
    script = f'''
import json, sys
from pathlib import Path
sys.path.insert(0, {str(INFOTEST_ROOT)!r})
from main.ist_core.compile_engine import _shared as sh
from main.case_compiler.mindmap_contract_projector import closed_mindmap_case_autoids, fill_mechanical_fields
from main.ist_core.tools.device.recompose_parts import read_machine_mindmap_parts
from main.ist_core.tools.device.recompose_submission import (
    initialize_machine_mindmap_submission, recompose_dispatch_scope, submit_machine_mindmap_payload,
    machine_mindmap_artifact_path)
from main.ist_core.tools.device.recompose_submit_tool import submit_machine_mindmap_cases
data_root = Path({state["data_root"]!r})
sh.project_root = lambda: data_root
outputs = Path({str(tmp_path / "it_outputs")!r})
(outputs / "mm").mkdir(parents=True)
raw = Path({str(ws_root / "mm.json")!r}).read_bytes()
(outputs / "mm" / "mindmap_source.json").write_bytes(raw)
text = raw.decode("utf-8")
binding = {state["binding"]!r}
dispatch = {state["dispatch_id"]!r}
initialize_machine_mindmap_submission(outputs, "mm", dispatch, binding=binding,
    case_autoids=tuple(closed_mindmap_case_autoids(text)), source_sha256={state["source_sha256"]!r})
with recompose_dispatch_scope(outputs, "mm", dispatch):
    print(submit_machine_mindmap_cases.func(cases={[bad]!r}).replace("\\n", " "))
    print(submit_machine_mindmap_cases.func(cases={[good]!r}).replace("\\n", " "))
snap = read_machine_mindmap_parts(outputs, "mm", binding_sha256=None, source_sha256={state["source_sha256"]!r})
doc = {{"cases": [dict(snap.cases[a]) for a in snap.case_autoids if a in snap.cases]}}
fill_mechanical_fields(doc, text)
submit_machine_mindmap_payload(outputs, "mm", dispatch, {{"schema": "ist.machine-mindmap",
    "source": binding["source"], "governing_spec": binding["governing_spec"],
    "defect_spec_status": binding["defect_spec_status"],
    "defect_spec_receipt_sha256": binding["defect_spec_receipt_sha256"],
    "cases": doc["cases"], "case_count": len(doc["cases"])}})
print(machine_mindmap_artifact_path(outputs, "mm").read_text(encoding="utf-8").replace("\\n", " "))
'''
    proc = subprocess.run([str(INFOTEST_PYTHON), "-c", script], capture_output=True, text=True,
                          timeout=300)
    assert proc.returncode == 0, proc.stderr[-3000:]
    it_bad, it_good, it_artifact = [json.loads(line) for line in proc.stdout.splitlines()
                                    if line.startswith("{")]
    _prepared, cl_bad, cl_good, cl_sealed = client
    strip = lambda r: {k: v for k, v in r.items() if k != "ok"}  # noqa: E731
    assert strip(cl_bad) == it_bad
    assert strip(cl_good) == it_good
    assert json.loads(Path(cl_sealed["artifact"]).read_text(encoding="utf-8")) == it_artifact


def test_preparing_again_resumes_and_a_different_spec_outcome_starts_over(tmp_path):
    """同一结论重来：已落盘的案保留；规格书结论变了：案是对着旧规格书判的，全部重来。"""
    good = _contract_case(A1)
    _first, _accepted, resumed, other = _run(tmp_path, f'''
call("cex_recompose_prepare", mindmap="mm.json")
call("cex_recompose_submit_cases", out_name="mm", cases={[good]!r})
call("cex_recompose_prepare", mindmap="mm.json")
call("cex_recompose_prepare", mindmap="mm.json", spec="none")
''')
    assert resumed["already_recorded"] == [A1] and resumed["outstanding_autoids"] == [A2]
    assert other["already_recorded"] == [] and other["outstanding_autoids"] == [A1, A2]


def test_a_defect_origin_is_refused_without_an_engine_receipt(tmp_path):
    """客户端不签 DefectSpec：缺陷单原文（cex_bug_get 查到的）不能当出处进契约。"""
    case = _contract_case(A1)
    case["expectations_by_step"].append({"n": "2", "text": "监听器端口修改后配置丢失",
                                         "origin": "defect:bugzilla:67890:title",
                                         "assertion": None})
    _prepared, rejected = _run(tmp_path, f'''
call("cex_recompose_prepare", mindmap="mm.json")
call("cex_recompose_submit_cases", out_name="mm", cases={[case]!r})
''', root_title="67890 监听器改造")
    assert rejected["ok"] is False and rejected["status"] == "rejected"
    assert [v["code"] for v in rejected["violations"]] == ["case_verbatim_mismatch"]
    assert "DefectSpec projection" in rejected["violations"][0]["detail"]


def test_the_documented_scenario2_shape_is_accepted_for_an_incomplete_case(tmp_path):
    """skill 文档（references/output-shape.md）给的 Scenario 2 形状，配客户端 prepare 给的
    两个 SPEC 通道状态，能过引擎的提交检查——文档与客户端状态值没有各说各话。"""
    # 两个步骤子节点、都没有预期孙节点：缺预期（只有一个叶子子节点会被认成叶子预期布局）
    incomplete = {"data": {"text": "配置端口", "autoid": A2}, "children": [
        {"data": {"text": "1.配置port 为53"}, "children": []},
        {"data": {"text": "2.查看sdns listener"}, "children": []}]}
    case = {
        "autoid": A2, "group_path": ["配置保存"], "title": "配置端口", "bucket": "true_gap",
        "source_status": "incomplete", "typed_assertion_status": "pending",
        "contract": {"intent": "配置端口", "verification_method": "查看sdns listener",
                     "expectation": None},
        "origin": {"intent": "title", "verification_method": "step:2", "expectation": None},
        "steps": [{"n": "1", "text": "1.配置port 为53"}, {"n": "2", "text": "2.查看sdns listener"}],
        "step_structure": [{"n": n, "objects": [], "operations": [], "stated_conditions": [],
                            "free_slots": []} for n in ("1", "2")],
        "expectations_by_step": [], "command_check": [], "depends_on": None,
        "rebind_licenses": [], "concretizations": [], "adaptation_notes": [],
        "proposal": ["作者没有写出查看结果应当是什么样。"],
        "scenario2": {"reason_code": "missing_case_description_steps_or_expectation",
                      "missing_fields": ["expectation"], "spec_status": "no_governing_spec",
                      "defect_spec_status": "no_ticket_reference",
                      "defect_spec_receipt_sha256": None},
        "consistency": None,
    }
    prepared, recorded = _run(tmp_path, f'''
call("cex_recompose_prepare", mindmap="mm.json")
call("cex_recompose_submit_cases", out_name="mm", cases={[case]!r})
''', root_title="监听器改造", second=incomplete)
    assert prepared["defect_spec_status"] == "no_ticket_reference"
    assert recorded["ok"] is True, json.dumps(recorded["violations"], ensure_ascii=False)
    assert recorded["outstanding_autoids"] == [A1]
