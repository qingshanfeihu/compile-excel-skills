import { createHash } from "node:crypto";
import * as cheerio from "cheerio";
import type { Element as DomElement } from "domhandler";

import {
  extract_ticket_id,
  load_selectors,
  make_soup,
  normalize_resolution,
  normalize_severity,
  normalize_status,
  parse_int,
  select_attrs,
  select_text,
  select_texts,
  type Soup,
} from "./_common";
import { fold_zh_label } from "./_zh_fold";
import { DefectTicket, type Attachment } from "./schema";

function _resolve_zentao_cfg(): Record<string, any> {
  const cfg = load_selectors() ?? {};
  return cfg["zentao"] ?? {};
}

function _textOf(soup: Soup, el: unknown): string {
  return soup(el as any)
    .text()
    .replace(/\s+/g, " ")
    .trim();
}

function _nextSiblingTd(soup: Soup, el: unknown): DomElement | null {
  const nxt = soup(el as any).nextAll("td").first();
  return nxt.length ? (nxt.get(0) as DomElement) : null;
}

function _findNextTd(soup: Soup, el: unknown): DomElement | null {
  const rootNode = soup.root().get(0);
  const found = soup(rootNode as any)
    .find("td")
    .toArray();
  const self = el as DomElement;
  for (const td of found) {
    if (td !== self) {
      return td as DomElement;
    }
  }
  return null;
}

export function select_by_th_label(soup: Soup, labels: string[]): string {
  if (!labels.length) {
    return "";
  }
  const labelSet = new Set(labels.filter((l) => l).map((l) => fold_zh_label(l.trim())));
  for (const sel of ["th", "td.w-80px", "label", "strong"]) {
    for (const el of soup(sel).toArray()) {
      const text = fold_zh_label(_textOf(soup, el).replace(/[：:]+$/, ""));
      if (text && labelSet.has(text)) {
        const sib = _nextSiblingTd(soup, el);
        if (sib !== null) {
          const val = _textOf(soup, sib);
          if (val) {
            return val;
          }
        }
        const nxt = _findNextTd(soup, el);
        if (nxt !== null && nxt !== el) {
          const val = _textOf(soup, nxt);
          if (val) {
            return val;
          }
        }
      }
    }
  }
  return "";
}

export function select_all_by_th_label(soup: Soup, labels: string[]): string[] {
  const out: string[] = [];
  const seen = new Set<string>();
  if (!labels.length) {
    return out;
  }
  const labelSet = new Set(labels.filter((l) => l).map((l) => fold_zh_label(l.trim())));
  for (const el of soup("th, td.w-80px, label, strong").toArray()) {
    const text = fold_zh_label(_textOf(soup, el).replace(/[：:]+$/, ""));
    if (text && labelSet.has(text)) {
      const sib = _nextSiblingTd(soup, el);
      if (sib === null) {
        continue;
      }
      const lis = soup(sib).find("li");
      let items: string[];
      if (lis.length) {
        items = lis.toArray().map((li) => _textOf(soup, li));
      } else {
        const raw = _textOf(soup, sib);
        items = raw.split(/[\s,，、;；/]+/).filter((s) => s.trim());
      }
      for (const it of items) {
        if (it && !seen.has(it)) {
          seen.add(it);
          out.push(it);
        }
      }
    }
  }
  return out;
}

function _zentao_severity_map(raw: string): string {
  if (!raw) {
    return "low";
  }
  const s = String(raw).trim();
  const m = /^(\d)/.exec(s);
  if (m) {
    const n = parseInt(m[1], 10);
    return { 1: "low", 2: "mid", 3: "high", 4: "critical" }[n as 1 | 2 | 3 | 4] ?? "low";
  }
  return normalize_severity(s);
}

function _zentao_status_map(raw: string): string {
  const s = fold_zh_label((raw ?? "").trim()).toLowerCase();
  if (!s) {
    return "";
  }
  if (["已解决", "已关闭", "已修复", "closed", "resolved", "fixed"].some((k) => s.includes(k))) {
    return "fixed";
  }
  if (["激活", "新建", "new", "active", "triage"].some((k) => s.includes(k))) {
    return "triage";
  }
  return normalize_status(s);
}

const _NUM_RE = /#?(\d{2,6})/g;

const _INVALID_ZENTAO_SIGNALS = [
  "没有匹配的结果",
  "无搜索结果",
  "未找到匹配",
  "no results",
  "您没有访问权限",
  "无访问权限",
  "您无权",
  "page not found",
  "404 - 找不到页面",
  "bug 不存在",
  "需求不存在",
  "story not exist",
];

function _detect_zentao_invalid(soup: Soup): string {
  const bodyText = soup.root().text().replace(/\s+/g, " ").trim().toLowerCase();
  for (const sig of _INVALID_ZENTAO_SIGNALS) {
    if (bodyText.includes(sig)) {
      return `zentao_signal:${sig}`;
    }
  }
  const titleEl = soup("title").first();
  if (titleEl.length > 0) {
    const title = titleEl.text().trim().toLowerCase();
    if (["404", "not found", "无权", "无搜索结果"].some((t) => title.includes(t))) {
      return `zentao_title:${title.slice(0, 60)}`;
    }
  }
  return "";
}

function _extract_id_list(text: string, prefix: string): string[] {
  if (!text) {
    return [];
  }
  const out: string[] = [];
  const seen = new Set<string>();
  const re = new RegExp(_NUM_RE.source, "g");
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    const key = `${prefix}-${m[1]}`;
    if (!seen.has(key)) {
      seen.add(key);
      out.push(key);
    }
  }
  return out;
}

export class ZentaoExtractor {
  backend = "zentao";
  version = "v2";
  doc_type_hint: string;

  constructor(opts: { doc_type?: string } = {}) {
    this.doc_type_hint = opts.doc_type ?? "bug";
  }

  extract(html: string): DefectTicket {
    if (!html) {
      return new DefectTicket({ ticket_id: "UNKNOWN", backend: this.backend });
    }

    const cfg = _resolve_zentao_cfg();
    this.version = cfg["version"] ?? this.version;
    const soup = make_soup(html);

    let invalidReason = _detect_zentao_invalid(soup);

    const thLabels = cfg["th_labels"] ?? {};

    const rawId = select_text(soup, cfg["ticket_id"] ?? []);
    const ticketId = extract_ticket_id(rawId) || rawId || "UNKNOWN";

    let title = select_by_th_label(soup, thLabels["title"] ?? []);
    if (!title && rawId) {
      title = rawId.replace(/^Bug\s*#?\d+[\s:：]*/, "").trim() || rawId;
    }

    if (!invalidReason && ticketId === "UNKNOWN" && !title) {
      invalidReason = "zentao_no_detail_data";
    }

    const product = select_by_th_label(soup, thLabels["product"] ?? []);
    const module_ = select_by_th_label(soup, thLabels["module"] ?? []);
    const severityRaw = select_by_th_label(soup, thLabels["severity"] ?? []);
    const severity = _zentao_severity_map(severityRaw);
    const priority = select_by_th_label(soup, thLabels["priority"] ?? []);
    const statusRaw = select_by_th_label(soup, thLabels["status"] ?? []);
    const status = _zentao_status_map(statusRaw);
    const resolution = normalize_resolution(select_by_th_label(soup, thLabels["resolution"] ?? []));

    let description = select_by_th_label(soup, thLabels["description"] ?? []);
    if (!description) {
      description = select_text(soup, cfg["description_blocks"] ?? []);
    }
    const steps = select_by_th_label(soup, thLabels["steps_to_reproduce"] ?? []);
    const fixSummary = select_by_th_label(soup, thLabels["fix_summary"] ?? []);

    const reportedBy = select_by_th_label(soup, thLabels["reported_by"] ?? []);
    const reportedAt = select_by_th_label(soup, thLabels["reported_at"] ?? []);
    const resolvedBy = select_by_th_label(soup, thLabels["resolved_by"] ?? []);
    const resolvedAt = select_by_th_label(soup, thLabels["resolved_at"] ?? []);

    const affected = select_all_by_th_label(soup, thLabels["affected_versions"] ?? []).map((item) =>
      fold_zh_label(item)
    );
    const fixedVersions = select_all_by_th_label(soup, thLabels["fixed_versions"] ?? []).map((item) =>
      fold_zh_label(item)
    );
    const fixedCommit = select_by_th_label(soup, thLabels["fixed_commit"] ?? []);

    const relatedStory = select_by_th_label(soup, thLabels["related_story"] ?? []);
    const relatedCase = select_by_th_label(soup, thLabels["related_case_ids"] ?? []);
    const relatedTask = select_by_th_label(soup, thLabels["related_task_ids"] ?? []);
    const relatedBug = select_by_th_label(soup, thLabels["related_bug_ids"] ?? []);

    const relatedStoryIds = _extract_id_list(relatedStory, "STORY");
    const relatedCaseIds = _extract_id_list(relatedCase, "TC");
    const relatedTaskIds = _extract_id_list(relatedTask, "TASK");
    const relatedBugIds = _extract_id_list(relatedBug, "ZT");

    const relatedFeatureIds: string[] = [];
    for (const sid of relatedStoryIds) {
      const m = new RegExp(_NUM_RE.source).exec(sid);
      if (m) {
        relatedFeatureIds.push(m[1]);
      }
    }

    const activatedRaw = select_by_th_label(soup, thLabels["activated_count"] ?? []);
    const activatedCount = parse_int(activatedRaw, 0);

    const attachmentUrls = select_attrs(soup, cfg["attachments"] ?? [], "href");
    const attachmentNames = select_texts(soup, cfg["attachments"] ?? []);
    const attachments: Attachment[] = attachmentUrls.map((url, i) => ({
      url,
      filename: i < attachmentNames.length ? attachmentNames[i] : "",
    }));

    let docType = this.doc_type_hint || "bug";
    if (/^(STORY|REQ|PLM)/i.test(ticketId)) {
      docType = "plm_ticket";
    }

    const htmlSha = createHash("sha256").update(html, "utf8").digest("hex").slice(0, 16);

    return new DefectTicket({
      ticket_id: ticketId,
      title,
      product,
      module: module_,
      severity,
      priority,
      status,
      resolution,
      description,
      steps_to_reproduce: steps,
      fix_summary: fixSummary,
      reported_by: reportedBy,
      reported_at: reportedAt,
      resolved_by: resolvedBy,
      resolved_at: resolvedAt,
      affected_versions: affected,
      fixed_versions: fixedVersions,
      fixed_commit: fixedCommit,
      related_feature_ids: relatedFeatureIds,
      related_case_ids: relatedCaseIds,
      related_story_ids: relatedStoryIds,
      related_task_ids: relatedTaskIds,
      related_bug_ids: relatedBugIds,
      activated_count: activatedCount,
      attachments,
      backend: this.backend,
      doc_type: docType,
      html_sha256: htmlSha,
      invalid_reason: invalidReason,
    });
  }
}

export class ZentaoStoryExtractor extends ZentaoExtractor {
  constructor() {
    super({ doc_type: "plm_ticket" });
  }
}

