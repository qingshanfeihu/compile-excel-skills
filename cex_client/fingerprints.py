"""用例卷面指纹：返工闸比对"上一轮真上机的卷面"与"这一轮要投的卷面"用的同一份算法。

每案一个指纹：它的全部步骤（不只 check_point）规范化成 {"e","f","g","h","i"[, "source"]}
（大写、小写键都认，缺的记 ""；source 只留 kind 与 ref，没有就不写这一键），按
sort_keys、ensure_ascii=False、separators=(",", ":") 序列化后取 SHA-256。
另有 "__init__"：文件级共享前置 init_commands（没有就是 []）的同一种摘要。

device.submit 投递时按工作簿旁的 cases.json 算一份记进任务记录，取结果时写进
run_results.json 的 case_fingerprints；技能脚本 rework_gate.py 也调这里，不各写一份。
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

INIT_KEY = "__init__"
_FIELDS = ("e", "f", "g", "h", "i")


def _canonical_sha256(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _field(step: dict[str, Any], key: str) -> str:
    for name in (key.upper(), key):
        if name in step and step[name] is not None:
            return str(step[name])
    return ""


def normalize_step(step: Any) -> dict[str, Any]:
    if not isinstance(step, dict):
        return {key: "" for key in _FIELDS}
    out: dict[str, Any] = {key: _field(step, key) for key in _FIELDS}
    source = step.get("source")
    if isinstance(source, dict) and ("kind" in source or "ref" in source):
        out["source"] = {"kind": str(source.get("kind") or ""), "ref": str(source.get("ref") or "")}
    return out


def case_fingerprints(cases_doc: dict[str, Any]) -> dict[str, str]:
    """cases.json 文档 → {autoid: 指纹, "__init__": 共享前置指纹}。"""
    doc = cases_doc if isinstance(cases_doc, dict) else {}
    out: dict[str, str] = {}
    for case in doc.get("cases") or []:
        if not isinstance(case, dict):
            continue
        autoid = str(case.get("autoid") or "").strip()
        if autoid:
            out[autoid] = _canonical_sha256([normalize_step(s) for s in case.get("steps") or []])
    out[INIT_KEY] = _canonical_sha256(doc.get("init_commands") or [])
    return out


__all__ = ["INIT_KEY", "case_fingerprints", "normalize_step"]
