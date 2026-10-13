"""交付面台账：批目录里那套"谁没进卷、为什么"的产物（issue #6 的客户端补齐）。

InfoTest 的交付契约（docs/engine/07_display_contract.md §11.9）要求批目录一处齐全：
case.xlsx、unsuccessful_cases.md、delivery_report.md、engine_report.json、facts.jsonl、
manifest.json。编排层（nodes.py 的 `_archive_unsuccessful`、terminal_outcomes、events 等）
在转换时划出了边界，客户端此前一件都不产：提交被拒的理由只活在会话返回文本里，会话一压缩
或关闭就永久丢失；丢件在磁盘上零留痕。引擎的渲染函数（render.py::render_unsuccessful_md）
虽然被抽进了 cex_core，但它的输入是引擎编排层的 facts/queues/panels 形状，客户端数据凑不出
 faithful 的调用，所以这里的叙事由本模块按同一种三段式（时间线/机理引文/修复方案）在客户端
数据上重建，文件名词表照抄抽取来的 display_lexicon（内嵌一份，测试钉住与抽取表一致；
假引擎环境里真模块 import 不到，运行时不依赖它）。

产出的最小交付集（都在 compile_outputs/<批>/，与 case.xlsx 同目录）：

- `manifest.json`   批身份：来源哈希、契约卡哈希表、written/abandoned 名单（schema
  `cex.batch-manifest`）；
- `engine_report.json` 机读真理源：逐案状态（delivered / not_sealed / sealed_file_replaced /
  abandoned / not_submitted / rejected / needs_user_decision）与最后一次提交的 violations、
  总计、核验结果（schema `cex.engine-report`）；
- `unsuccessful_cases.md` 未进卷案的三段式叙事（只有存在未进卷案时产出——与原版"判定式渲染"
  一致）；
- `delivery_report.md`  交付总报告：硬校验行（contracted == delivered?）与逐文件点名；
- `facts.jsonl`      最小事实台账：写侧判据（闭集校验、幂等去重键）全部取自抽取来的
  `fact_events`/`facts` 模块（引擎的 `append_facts` 本体在客户端调不动，见其函数说明），
  只用登记表里已有的事件名：投影发布追加本批的
  `recompose_done` 回执行（抽取来的 `consistency_requirement` 读的就是这条流，客户端此前
  不产它，自带引擎的审计输入自洽性被破坏）；提交被拒追加 `mechanical_case_submission_rejected`
  （与原版同字段：aid/attempt/violations/occurrence_id，抽取来的 `authoring_checks` 逐字读
  它）；待用户裁决追加 `needs_decision`。封存成功与出件不写 facts 事件（登记表里没有语义
  相符的名字，`authored`/`run_closed` 都背着引擎侧别的读者的期待，不冒领）：它们的真理在
  `sealed` 状态与 `engine_report.json` 里。

刻意不产的（理由都写进 docs/engine-parity.md 的交付台账一节）：`unsuccessful_cases.xlsx`
（原版只收"有卷面的非交付案"，客户端未进卷案没有通过闸的卷面可并）、`engine_errors.md` /
`metrics.md` / `defect_candidates.*`（编排层边界内，客户端没有输入）。
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Any

from .errors import ClientError
from .workspace import Workspace, write_file_safely

MANIFEST_SCHEMA = "cex.batch-manifest"
REPORT_SCHEMA = "cex.engine-report"
# 事件名只用引擎登记表（cex_core fact_events.FACT_EVENTS）里已有的：写侧是闭集，未登记的
# 名字会被 append_facts 当场拒掉，而抽取件不许手改。`recompose_done` 是抽取来的
# consistency_requirement 找投影回执的键；`mechanical_case_submission_rejected` 是原版
# 拒收事件（authoring_checks 逐字读它），occurrence_id 让同一案的多次拒收各占一行。
EV_RECOMPOSE_DONE = "recompose_done"
EV_SUBMISSION_REJECTED = "mechanical_case_submission_rejected"
EV_NEEDS_DECISION = "needs_decision"

# 交付文件名的中文标签，内容与抽取来的 display_lexicon.DELIVERY_FILE_LABEL_CN 一致
# （tests/client/test_delivery.py 钉住这张表对得上那份抽取表）。不在运行时 import 它：
# 胶水测试的假引擎把 cex_core.engine.ist_core 装成空路径包，真模块在那种环境里 import 不到。
DELIVERY_FILE_LABELS = {
    "case.xlsx": "case.xlsx",
    "delivery_report.md": "交付报告",
    "unsuccessful_cases.md": "未通过详报",
    "engine_report.json": "机读报告",
    "facts.jsonl": "事实流",
}


def delivery_file_label(name: object) -> str:
    text = str(name or "").strip()
    return DELIVERY_FILE_LABELS.get(text, text)


FACTS_NAME = "facts.jsonl"
MANIFEST_NAME = "manifest.json"
ENGINE_REPORT_NAME = "engine_report.json"
UNSUCCESSFUL_NAME = "unsuccessful_cases.md"
DELIVERY_REPORT_NAME = "delivery_report.md"

# 常见拒收码的出路；闸的硬拒码是开放集，落到兜底一句
_CODE_GUIDANCE: dict[str, str] = {
    "consistency_stage_unavailable": "本案绑定了管辖规格书：用 spec='none' 重新 prepare，或在支持"
                                     "规格判定的环境编译（issue #10）。",
    "frozen_contract_drift": "契约卡在发布后变了：重跑 cex_author_prepare 读新卡，按新卡重提交本案。",
    "contracts_republished": "提交期间卡被重发布：读新卡重提交本案。",
    "autoid_not_dispatched": "该案号不在本批契约名单里：核对批名，或先 cex_author_prepare。",
    "self_reported_seal": "去掉自带 seal 字段重提交：封印由引擎在闸后铸造。",
    "payload_invalid_json": "按契约卡语言重写机械用例 JSON 后重提交。",
    "not_an_object": "mechanical_case 必须是一个 JSON 对象，修正后重提交。",
    "ssl_cert_load_invalid": "块规范化失败：按 references/authoring.md 的块语言修正后重提交。",
    "gate_uncomputable": "机械用例无法过闸（结构问题）：按 detail 修正主体后重提交。",
}
_DEFAULT_GUIDANCE = "按上面逐条 violations 修正机械用例，用 cex_author_submit_case 重提交本案。"


def timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


# ── 事实台账 ────────────────────────────────────────────────────────────


def append_facts(ws: Workspace, batch: Path, events: list[dict[str, Any]]) -> None:
    """向批目录的 facts.jsonl 幂等追加事件行。引擎的 `facts.append_facts` 在客户端调不动：
    它惰性 import 的 `routing_closed_sets`（decision 轴盖章）是转换边界外的模块，一调就
    ModuleNotFoundError——又一处"纯函数搬来、编排留在岸上"。这里用同一批可调用件拼出同样
    的写侧纪律：闭集校验 `require_registered`、去重键 `idem_key`、快照读 `load_facts` 全
    取自抽取件；追加用 O_NOFOLLOW|O_APPEND 单文件打开。`stamp_decision_axis` 只作用于
    decision 轴事件，本客户端写的三种事件（recompose_done / mechanical_case_submission_rejected /
    needs_decision）都不落那条轴，缺这一步不改语义（写进 engine-parity 备案）。"""
    import os

    from cex_core.engine.ist_core.compile_engine.fact_events import require_registered
    from cex_core.engine.ist_core.compile_engine.facts import idem_key, load_facts

    root = ws.outputs_dir.resolve()
    resolved = batch.resolve()
    if resolved != root and root not in resolved.parents:
        raise ClientError(f"the fact ledger stays under the workspace outputs: {batch}")
    path = batch / FACTS_NAME
    batch.mkdir(parents=True, exist_ok=True)
    require_registered(events, where=str(path))
    existing: set = set()
    if path.is_file() and not path.is_symlink():
        try:
            existing = {idem_key(fact) for fact in load_facts(path)}
        except (OSError, RuntimeError, ValueError):
            existing = set()  # 读不出旧账不挡新账（原版会拒；客户端宁可多记一条也不静默）
    # recompose_done 不走去重：引擎把它记在通用键 (ev, aid) 上、按"一批一条"设计，而客户端
    # 的判据裁定会重发布；`consistency_requirement._latest_recompose` 是从尾往前找最新一条，
    # 被旧回执顶住就是错账——所以投影发布在这里总是放行。
    fresh = [event for event in events
             if event.get("ev") == EV_RECOMPOSE_DONE or idem_key(event) not in existing]
    if not fresh:
        return
    flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, mode=0o600)
    try:
        for event in fresh:
            os.write(fd, (json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n").encode())
    finally:
        os.fsync(fd)
        os.close(fd)


def rejection_event(out_name: str, aid: str, attempt: int,
                    violations: list[dict[str, Any]]) -> dict[str, Any]:
    """原版拒收事实的字段形状（occurrence_id 防幂等吞行；violations 逐条照抄闸的产物）。"""
    return {"ev": EV_SUBMISSION_REJECTED, "ts": timestamp(), "out_name": out_name,
            "aid": aid, "dispatch_id": "cex_client", "attempt": int(attempt),
            "occurrence_id": uuid.uuid4().hex,
            "violations": [dict(v) for v in violations if isinstance(v, dict)]}


def decision_event(out_name: str, aid: str, claims: list[str]) -> dict[str, Any]:
    return {"ev": EV_NEEDS_DECISION, "ts": timestamp(), "out_name": out_name, "aid": aid,
            "claims": [str(c) for c in claims]}


def recompose_done_event(out_name: str, receipt: dict[str, Any]) -> dict[str, Any]:
    """投影发布回执：`author._receipt()` 的字典本身就是原版的 recompose_done 形状
    （ev/reentry_round/written/abandoned/...），补 ts 与 out_name 两个身份字段再落账。"""
    return {**receipt, "ts": timestamp(), "out_name": out_name}


# ── 构建 ───────────────────────────────────────────────────────────────


def build_manifest(state: dict[str, Any],
                   batch_manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    """批身份源：投影回执（哈希与契约卡表）+ 重组台账 batch_manifest.json（桶计数、案数、
    放弃表）。键名对齐原版身份（`name`、`source_sha256`、`total`、`bucket_counts`…），
    schema 用客户端名 `cex.batch-manifest`——它不是引擎投影身份清单的复刻，逐案的桶与
    source_status 真相仍在那份 `batch_manifest.json` 与 `machine_mindmap.json` 里。"""
    receipt = state.get("receipt") or {}
    bm = batch_manifest or {}
    manifest: dict[str, Any] = {
        "schema": MANIFEST_SCHEMA,
        "name": state.get("out_name"),
        "batch": state.get("out_name"),
        "generated_by": "cex_client",
        "source_sha256": receipt.get("mindmap_source_sha256"),
        "machine_mindmap_sha256": receipt.get("machine_mindmap_sha256"),
        "governing_spec_status": receipt.get("governing_spec_status"),
        "governing_spec": receipt.get("governing_spec"),
        "governing_spec_sha256": receipt.get("governing_spec_sha256"),
        "defect_spec_status": receipt.get("defect_spec_status"),
        "written_autoids": list(receipt.get("written_autoids") or []),
        "abandoned_autoids": list(receipt.get("abandoned_autoids") or []),
        "contract_sha256_by_autoid": dict(receipt.get("contract_sha256_by_autoid") or {}),
        "disclosure_sha256": receipt.get("disclosure_sha256"),
    }
    for key in ("total", "bucket_counts", "source_status_counts",
                "typed_pending", "typed_ready", "groups"):
        if key in bm:
            manifest[key] = bm[key]
    return manifest


def build_engine_report(state: dict[str, Any], emit_out: dict[str, Any],
                        artifact_shas: dict[str, str]) -> dict[str, Any]:
    """逐案状态：delivered 进卷；not_sealed 未封存（含契约变了要重提交的）；
    sealed_file_replaced 封存文件被换；abandoned 投影放弃；rejected/needs_user_decision/
    not_submitted 是未封存案按最后提交记录细分。"""
    receipt = state.get("receipt") or {}
    sealed = state.get("sealed") or {}
    submissions = state.get("submissions") or {}
    written = [str(a) for a in receipt.get("written_autoids") or []]
    emitted = [str(a) for a in emit_out.get("emitted_autoids") or []]
    missing = {str(a) for a in emit_out.get("not_sealed_autoids") or []}
    drifted = {str(d.get("autoid")): str(d.get("reason"))
               for d in emit_out.get("not_emitted") or []}
    abandoned = [str(a) for a in receipt.get("abandoned_autoids") or []]
    cases: dict[str, dict[str, Any]] = {}
    for aid in written:
        last = submissions.get(aid) or {}
        entry: dict[str, Any] = {
            "contract_sha256": (receipt.get("contract_sha256_by_autoid") or {}).get(aid),
            "status": "delivered" if aid in emitted else "not_sealed",
        }
        if last:
            entry["last_submission"] = {k: last.get(k) for k in ("at", "status", "violations")}
        if aid in emitted:
            record = sealed.get(aid) or {}
            entry["mechanical_case_sha256"] = record.get("mechanical_case_sha256")
        elif aid in drifted:
            entry["status"] = "sealed_file_replaced"
            entry["reason"] = drifted[aid]
        elif aid in missing:
            status = str(last.get("status") or "")
            entry["status"] = status if status in ("rejected", "needs_user_decision") \
                else "not_submitted"
        cases[aid] = entry
    for aid in abandoned:
        cases[aid] = {"status": "abandoned"}
    not_delivered = [aid for aid, c in cases.items() if c["status"] != "delivered"
                     and aid in written]
    totals = {
        "contracted": len(written),
        "delivered": len(emitted),
        "not_sealed": len(missing),
        "sealed_file_replaced": len(drifted),
        "abandoned": len(abandoned),
        "rejected_last": len([c for c in cases.values() if c.get("status") == "rejected"]),
        "needs_user_decision": len([c for c in cases.values()
                                    if c.get("status") == "needs_user_decision"]),
        "not_submitted": len([c for c in cases.values() if c.get("status") == "not_submitted"]),
    }
    return {
        "schema": REPORT_SCHEMA,
        "batch": state.get("out_name"),
        "at": timestamp(),
        "generated_by": "cex_client",
        "totals": totals,
        "hard_check_contracted_equals_delivered": totals["contracted"] == totals["delivered"],
        "cases": cases,
        "not_delivered_autoids": sorted(not_delivered),
        "verify": emit_out.get("verify"),
        "artifacts": {"case.xlsx": emit_out.get("xlsx"),
                      "cases.json": emit_out.get("cases_json"), **artifact_shas},
    }


# ── 叙事渲染（三段式：时间线 / 机理引文 / 修复方案）────────────────────


def _violations_lines(violations: Any) -> list[str]:
    lines: list[str] = []
    for item in violations or []:
        if not isinstance(item, dict):
            continue
        gate = str(item.get("gate") or "")
        code = str(item.get("code") or "")
        locus = str(item.get("locus") or "")
        detail = str(item.get("detail") or "")
        lines.append(f"- 闸 `{gate}` · 码 `{code}` · 位 `{locus}`：{detail}")
    return lines


def render_unsuccessful_md(report: dict[str, Any], manifest: dict[str, Any],
                           titles: dict[str, str]) -> str:
    batch = str(report.get("batch") or "")
    bad = [aid for aid in sorted(report.get("not_delivered_autoids") or [])]
    lines = [f"# 未通过用例详报 — {batch}",
             f"> 生成 {time.strftime('%Y-%m-%d %H:%M', time.localtime())} · 共 {len(bad)} 个 · "
             "客户端交付台账（机读真理源见 "
             f"`{delivery_file_label(ENGINE_REPORT_NAME)}` `{ENGINE_REPORT_NAME}`）",
             ""]
    cases = report.get("cases") or {}
    contracts = manifest.get("contract_sha256_by_autoid") or {}
    for aid in bad:
        entry = cases.get(aid) or {}
        status = str(entry.get("status") or "")
        lines.append(f"## {aid} — {titles.get(aid, '(无标题)')}")
        lines.append(f"\n**状态**：{status}")
        lines.append("\n### 时间线")
        lines.append(f"- 投影发布：契约卡 `contracts/{aid}.json`"
                     + (f"（sha256 `{str(contracts.get(aid) or '')[:16]}…`）"
                        if contracts.get(aid) else ""))
        last = entry.get("last_submission") or {}
        if last.get("at"):
            lines.append(f"- 最后一次提交 {last['at']}：{last.get('status') or '?'}")
        else:
            lines.append("- 最后一次提交：无记录（本案从未提交过机械用例）")
        if status == "sealed_file_replaced":
            lines.append(f"- 出件核对：{entry.get('reason') or '封存文件与封存记录不符'}")
        lines.append("\n### 机理引文")
        cited = _violations_lines(last.get("violations"))
        if cited:
            lines.extend(cited)
        elif status == "abandoned":
            lines.append("- 投影期放弃（recompose abandon），本批不编写此案。")
        elif entry.get("reason"):
            lines.append(f"- {entry['reason']}")
        else:
            lines.append("- 无提交违规记录：案还没封进来（未提交或提交从未到过闸）。")
        lines.append("\n### 修复方案")
        codes = {str(v.get("code") or "") for v in (last.get("violations") or [])
                 if isinstance(v, dict)}
        if status == "sealed_file_replaced":
            lines.append("- 封存文件被别的批覆盖或手改过：按当前契约卡重新提交本案，再 cex_author_emit。")
        elif status == "abandoned":
            lines.append("- 无需修复：这是投影阶段的放弃案；要收编它得回到重组阶段。")
        else:
            guidance = [_CODE_GUIDANCE[code] for code in sorted(codes) if code in _CODE_GUIDANCE]
            if guidance:
                lines.extend([f"- {g}" for g in guidance])
            else:
                lines.append(f"- {_DEFAULT_GUIDANCE}")
        lines.append("")
    return "\n".join(lines) + "\n"


def render_delivery_md(report: dict[str, Any], manifest: dict[str, Any],
                       produced: dict[str, str]) -> str:
    totals = report.get("totals") or {}
    passed = bool(report.get("hard_check_contracted_equals_delivered"))
    lines = [f"# 交付报告 — {report.get('batch')}",
             f"> 生成 {report.get('at')} · 客户端交付台账（编排层在转换边界之外，本报告的"
             "判定与点名以状态与提交台账为准）",
             "",
             "## 硬校验",
             f"- contracted {totals.get('contracted', 0)} == delivered "
             f"{totals.get('delivered', 0)} → **{'通过' if passed else '不通过'}**",
             ""]
    if not passed:
        lines.append("**本卷不可作为完整交付使用**：以下案没有进卷，逐案叙事见 "
                     f"`{delivery_file_label(UNSUCCESSFUL_NAME)}` `{UNSUCCESSFUL_NAME}`。")
        for aid in report.get("not_delivered_autoids") or []:
            status = str(((report.get("cases") or {}).get(aid) or {}).get("status") or "?")
            lines.append(f"- `{aid}`：{status}")
        lines.append("")
    lines += ["## 计数",
              f"- 契约案 {totals.get('contracted', 0)} · 进卷 {totals.get('delivered', 0)} · "
              f"未封存 {totals.get('not_sealed', 0)} · 封存文件被换 {totals.get('sealed_file_replaced', 0)} · "
              f"拒收 {totals.get('rejected_last', 0)} · 待裁决 {totals.get('needs_user_decision', 0)} · "
              f"未提交 {totals.get('not_submitted', 0)} · 放弃 {totals.get('abandoned', 0)}", "",
              "## 交付文件"]
    for name in ("case.xlsx", "cases.json", ENGINE_REPORT_NAME, MANIFEST_NAME,
                 UNSUCCESSFUL_NAME, DELIVERY_REPORT_NAME, FACTS_NAME):
        if name in produced:
            lines.append(f"- `{name}` — {delivery_file_label(name)}")
    verify = report.get("verify") or {}
    lines += ["", "## 卷面核验",
              f"- verify_batch：pass {verify.get('pass', 0)} / fail {verify.get('fail', 0)}"]
    for failure in (verify.get("failures") or [])[:10]:
        lines.append(f"  - {failure}")
    lines.append("")
    return "\n".join(lines) + "\n"


# ── 落盘 ───────────────────────────────────────────────────────────────


def write_reports(ws: Workspace, state: dict[str, Any], batch: Path,
                  emit_out: dict[str, Any]) -> dict[str, str]:
    """出件时（成功与部分成功都算）写交付台账；返回产出的文件名→路径。
    cases.json 与 case.xlsx 已由 emit 落盘，这里核它们的哈希进机读报告。"""
    artifact_shas: dict[str, str] = {}
    for name, key in (("case.xlsx", "xlsx"), ("cases.json", "cases_json")):
        path = emit_out.get(key)
        if isinstance(path, str) and Path(path).is_file():
            artifact_shas[f"{name}.sha256"] = _sha256_bytes(Path(path).read_bytes())
    batch_manifest: dict[str, Any] | None = None
    bm_path = batch / "batch_manifest.json"
    if bm_path.is_file():
        try:
            batch_manifest = json.loads(bm_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            batch_manifest = None  # 重组台账读不动：批身份少几行计数，不缺交付真理
    manifest = build_manifest(state, batch_manifest)
    report = build_engine_report(state, emit_out, artifact_shas)
    # 交付文件清单按磁盘实况点（emit 可能只走到一半：全批出不了卷时没有 xlsx）
    produced: dict[str, str] = {}
    for name in ("case.xlsx", "cases.json", FACTS_NAME):
        if (batch / name).is_file():
            produced[name] = str(batch / name)
    titles: dict[str, str] = {}
    case_root = batch / "cases"
    for aid in report.get("not_delivered_autoids") or []:
        intent = case_root / str(aid) / "intent.json"
        if intent.is_file():
            try:
                titles[str(aid)] = str(json.loads(intent.read_text(encoding="utf-8"))
                                       .get("title") or "")
            except (OSError, ValueError):
                pass
    writes: list[tuple[str, str]] = []
    if report.get("not_delivered_autoids"):
        writes.append((UNSUCCESSFUL_NAME, render_unsuccessful_md(report, manifest, titles)))
    writes.append((ENGINE_REPORT_NAME,
                   json.dumps(report, ensure_ascii=False, indent=1, sort_keys=True)))
    writes.append((MANIFEST_NAME,
                   json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=True)))
    for name, text in writes:
        target = batch / name
        write_file_safely(ws.root, target, text.encode("utf-8"))
        produced[name] = str(target)
    # delivery_report 引用的文件清单要在它自己落盘前定稿：先算好内容再写
    produced[DELIVERY_REPORT_NAME] = str(batch / DELIVERY_REPORT_NAME)
    write_file_safely(ws.root, batch / DELIVERY_REPORT_NAME,
                      render_delivery_md(report, manifest, produced).encode("utf-8"))
    return produced


__all__ = ["MANIFEST_SCHEMA", "REPORT_SCHEMA", "EV_RECOMPOSE_DONE", "EV_SUBMISSION_REJECTED",
           "EV_NEEDS_DECISION", "append_facts", "build_engine_report", "build_manifest",
           "decision_event", "recompose_done_event", "rejection_event", "render_delivery_md",
           "render_unsuccessful_md", "timestamp", "write_reports"]
