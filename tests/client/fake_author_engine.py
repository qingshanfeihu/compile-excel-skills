"""编写阶段胶水测试用的假引擎：只替 cex_client.author 在提交与出件里调到的那几个引擎函数，
行为按真引擎的约定（封印 = 去掉 seal 的用例体的规范摘要，读回时核封印）。胶水自己的路径、
加锁、核对逻辑照原样跑。子进程里也能用（install 不依赖 pytest）。"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import types
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

GATE_ROOTS: list[str] = []
STAMPED_ROOTS: list[str] = []


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def seal_document(body: dict[str, Any]) -> dict[str, Any]:
    plain = {k: v for k, v in body.items() if k != "seal"}
    return {**plain, "seal": {"mechanical_case_sha256": _digest(plain)}}


def _mint(body: dict[str, Any], target, **_kw):
    document = seal_document(body)
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(document, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return SimpleNamespace(document=document, code="", detail="")


def _load(path):
    raw = Path(path).read_bytes()
    document = json.loads(raw)
    plain = {k: v for k, v in document.items() if k != "seal"}
    if (document.get("seal") or {}).get("mechanical_case_sha256") != _digest(plain):
        raise ValueError("mechanical case seal does not match its body")
    return SimpleNamespace(model_dump=lambda **_kw: document), hashlib.sha256(raw).hexdigest()


def _gate(body, contract, *, outputs_root=None, **_kw):
    GATE_ROOTS.append(str(outputs_root))
    time.sleep(float(os.environ.get("FAKE_GATE_DELAY") or 0))
    return True, {"measurements": {"capabilities_used": [], "expanded_step_count": 1,
                                   "check_point_count": 1}, "advisories": [], "hard_rejects": []}


def _expand(blocks):
    steps = [{"E": b.get("E"), "F": b.get("F"), "G": b.get("G")} for b in blocks]
    prov = []
    for block in blocks:
        head, _, tail = str(block.get("ref") or "").partition(":")
        prov.append({"source": {"kind": head, "ref": tail}} if block.get("ref") else {})
    return steps, prov, None


_PACKAGES = ("cex_core.engine.case_compiler", "cex_core.engine.ist_core",
             "cex_core.engine.ist_core.tools", "cex_core.engine.ist_core.tools.device",
             "cex_core.engine.ist_core.compile_engine")
_MODULES: dict[str, dict[str, Any]] = {
    "cex_core.engine.ist_core.tools.device.mechanical_case_submit_tool": {
        "_violations_with_legal_forms": lambda v: list(v),
        "_canonicalize_submission_blocks": lambda body: (body, ""),
        "_stamp_engine_binding": lambda body, **kw: (
            {**body, "binding": {"contract_sha256": kw["contract_sha256"]}}, []),
        "unique_exempt_blocks_submit": lambda body: None,
    },
    "cex_core.engine.ist_core.compile_engine.consistency_requirement": {
        "NOT_APPLICABLE": "not_applicable"},
    "cex_core.engine.case_compiler.mechanical_case": {
        "mint_and_land_mechanical_case": _mint, "load_mechanical_case": _load},
    "cex_core.engine.case_compiler.mechanical_case_gate": {
        "AUDIENCE_WORKER": "worker", "gate_report_digest": lambda report: "0" * 64,
        "run_mechanical_case_gate": _gate},
    "cex_core.engine.case_compiler.vendor_stdlib": {"configured_device_os_build": lambda: "585"},
    "cex_core.engine.engine_managed_outputs": {"MECHANICAL_CASE_SIDECAR_NAME": "mechanical_case.json"},
    "cex_core.engine.case_compiler.blocks": {
        "expand_blocks": _expand,
        "lower_derived_assertions": lambda steps, prov: (steps, prov, None)},
}


def install(setitem: Callable[[Any, str, Any], None] | None = None,
            setattr_: Callable[[Any, str, Any], None] | None = None) -> None:
    """装假引擎。setitem / setattr_ 传 pytest 的 monkeypatch 版本就会在用例结束时复原。"""
    setitem = setitem or (lambda mapping, key, value: mapping.__setitem__(key, value))
    setattr_ = setattr_ or setattr
    for name in _PACKAGES:
        package = types.ModuleType(name)
        package.__path__ = []
        setitem(sys.modules, name, package)
    for name, members in _MODULES.items():
        module = types.ModuleType(name)
        for key, value in members.items():
            setattr(module, key, value)
        setitem(sys.modules, name, module)

    from cex_client import author, skill_scripts

    setattr_(author.engine_env, "prepare",
             lambda ws, pinned=None: (ws.state_dir / "engine" / "fake", {}))
    setattr_(author, "_require_current_seal", lambda ws, state: None)
    setattr_(author, "_manifest_cases", lambda text: {aid: {"autoid": aid}
                                                      for aid in json.loads(text)["autoids"]})
    setattr_(author, "source_case_slice", lambda case, aid: ({}, "0" * 64))

    def stamp(ws, root, batch, case_root, aid, receipt, case):
        STAMPED_ROOTS.append(str(case_root))
        (case_root / aid).mkdir(parents=True, exist_ok=True)
        (case_root / aid / "intent.json").write_text(json.dumps({"autoid": aid}), encoding="utf-8")
        return {"requirement": "not_applicable"}

    setattr_(author, "_stamp_intent", stamp)

    def compile_workbook(cases_path, out_dir):
        doc = json.loads(Path(cases_path).read_text(encoding="utf-8"))
        xlsx = Path(out_dir) / doc["batch"] / "case.xlsx"
        xlsx.write_bytes(b"xlsx")
        return {"ok": True, "path": str(xlsx), "batch": doc["batch"]}

    setattr_(skill_scripts, "compile_workbook", compile_workbook)
    setattr_(skill_scripts, "verify_workbook", lambda xlsx: {"pass": 1, "fail": 0, "failures": []})


def published_batch(ws, name: str, autoids: list[str], *, legacy: bool = False) -> None:
    """一个已发布契约卡的批：contracts/、脑图快照、编写状态（legacy=True 时是旧版状态：
    没有 cases_root，每案目录在 compile_outputs/<autoid>/）。"""
    from cex_client import author

    batch = ws.outputs_dir / name
    (batch / "contracts").mkdir(parents=True, exist_ok=True)
    (batch / "mindmap_source.json").write_text(json.dumps({"autoids": autoids}), encoding="utf-8")
    contracts = {}
    for aid in autoids:
        raw = json.dumps({"autoid": aid, "batch": name, "expectations": []}).encode("utf-8")
        (batch / "contracts" / f"{aid}.json").write_bytes(raw)
        contracts[aid] = hashlib.sha256(raw).hexdigest()
    state = {"out_name": name, "phase": "published", "sealed": {}, "pending": {},
             "cases": {aid: {"consistency_requirement": "not_applicable"} for aid in autoids},
             "receipt": {"written_autoids": list(autoids), "contract_sha256_by_autoid": contracts,
                         "machine_mindmap_sha256": "a" * 64},
             "projected_machine_mindmap_sha256": "a" * 64,
             "data_root": ".compile-excel/engine/fake"}
    if not legacy:
        state["cases_root"] = f"compile_outputs/{name}/cases"
    author._save_state(ws, state)


def body(aid: str, text: str) -> dict[str, Any]:
    return {"schema": "ist.mechanical-case", "autoid": aid,
            "description": {"intent_verbatim": text}, "binding": {}, "init_commands": [],
            "blocks": [{"E": "APV_0", "F": "cmd", "G": text}], "expectation_binding": [],
            "escape_hatches": []}
