import { createHash } from "node:crypto";

import {
  extract_ticket_id,
  load_selectors,
  make_soup,
  normalize_resolution,
  normalize_severity,
  normalize_status,
  select_attrs,
  select_text,
  select_texts,
  type Soup,
} from "./_common";
import { DefectTicket, type Attachment } from "./schema";

const _DESCRIPTION_MIN_CHARS = 40;
const _DESCRIPTION_COMMENT_LIMIT = 3;

const _VERSION_LINE_KEYWORDS: Record<string, string[]> = {
  affected: ["Affected Release", "Affected Version", "Affected in", "影响版本", "影响范围"],
  fixed: ["Fixed in", "Fixed Release", "Fixed Version", "修复版本", "已修复版本"],
};

function _extract_versions_from_text(text: string, keys: string[]): string[] {
  if (!text) {
    return [];
  }
  for (const kw of keys) {
    const re = new RegExp(`${kw.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\s*[:：]\\s*([^\\n\\r]+)`, "i");
    const m = re.exec(text);
    if (m) {
      const parts = m[1].trim().split(/[\s,;、，；]+/);
      return parts.filter((p) => p && p.length <= 40);
    }
  }
  return [];
}

const _INVALID_BUGZILLA_SIGNALS = [
  "you are not authorized to access bug",
  "there is no bug with the id",
  "bug not found",
  "invalid bug id",
  "access denied",
];

function _detect_bugzilla_invalid(soup: Soup): string {
  const bodyText = soup.root().text().replace(/\s+/g, " ").trim().toLowerCase();
  for (const sig of _INVALID_BUGZILLA_SIGNALS) {
    if (bodyText.includes(sig)) {
      return `bugzilla_signal:${sig}`;
    }
  }
  const titleEl = soup("title").first();
  if (titleEl.length > 0) {
    const title = titleEl.text().trim().toLowerCase();
    if (["not found", "invalid", "access denied"].some((t) => title.includes(t))) {
      return `bugzilla_title:${title.slice(0, 60)}`;
    }
  }
  return "";
}

function _bugzilla_description_fallback(soup: Soup, sel: Record<string, any>): string {
  const primary = select_text(soup, sel["description"] ?? []);
  if (primary && primary.length >= _DESCRIPTION_MIN_CHARS) {
    return primary;
  }
  const commentSelectors: string[] = sel["description_comments"] ?? ["pre.bz_comment_text"];
  const comments: string[] = [];
  for (const css of commentSelectors) {
    for (const el of soup(css).toArray()) {
      const text = soup(el).text().replace(/\s+/g, " ").trim();
      if (text && !comments.includes(text)) {
        comments.push(text);
      }
      if (comments.length >= _DESCRIPTION_COMMENT_LIMIT) {
        break;
      }
    }
    if (comments.length >= _DESCRIPTION_COMMENT_LIMIT) {
      break;
    }
  }
  const merged = comments.join("\n\n");
  if (primary && merged.length > primary.length) {
    return merged;
  }
  return primary || merged;
}

const _FIX_TEMPLATE_KEY_GROUPS: string[][] = [
  ["fixed details:", "fix details:", "修复详情", "修复方案", "solution:"],
  ["root cause:", "根本原因", "根因:", "根因："],
  ["condition of occurrence", "发生条件", "复现条件"],
  ["affected release", "affected version", "影响版本", "影响范围"],
  ["testing suggestions", "测试建议", "验证建议"],
];
const _FIX_TEMPLATE_MIN_SCORE = 2;

function _score_fix_template(text: string): number {
  const lower = text.toLowerCase();
  let score = 0;
  for (const group of _FIX_TEMPLATE_KEY_GROUPS) {
    if (group.some((variant) => lower.includes(variant))) {
      score++;
    }
  }
  return score;
}

function _comment_texts(soup: Soup): string[] {
  const texts: string[] = [];
  soup("pre.bz_comment_text, div.bz_comment_text").each((_i, el) => {
    const text = soup(el).text().replace(/\s+/g, " ").trim();
    if (text) {
      texts.push(text);
    }
  });
  return texts;
}

function _bugzilla_fix_summary_fallback(soup: Soup, sel: Record<string, any>): string {
  const primary = select_text(soup, sel["fix_summary"] ?? []);
  if (primary) {
    return primary;
  }

  const candidates: Array<[number, number, string]> = [];
  for (const text of _comment_texts(soup)) {
    const score = _score_fix_template(text);
    if (score >= _FIX_TEMPLATE_MIN_SCORE) {
      candidates.push([score, text.length, text]);
    }
  }
  if (candidates.length) {
    candidates.sort((a, b) => b[0] - a[0] || b[1] - a[1]);
    return candidates[0][2];
  }

  const keywords = (sel["fix_summary_keywords"] ?? []).map((k: string) => k.toLowerCase());
  if (!keywords.length) {
    return primary || "";
  }
  for (const text of _comment_texts(soup)) {
    const lower = text.toLowerCase();
    if (keywords.some((kw: string) => lower.includes(kw))) {
      return text;
    }
  }
  return primary || "";
}

const _RELATED_BUG_RE = /(?:bug|show_bug\.cgi\?id=)\s*#?(\d{3,6})/i;

function _bugzilla_related_bug_ids(soup: Soup, sel: Record<string, any>): string[] {
  const texts = select_texts(soup, sel["related_bug_ids"] ?? []);
  const ids: string[] = [];
  const seen = new Set<string>();
  for (const t of texts) {
    const m = _RELATED_BUG_RE.exec(t);
    if (m) {
      const val = `BUG-${m[1]}`;
      if (!seen.has(val)) {
        seen.add(val);
        ids.push(val);
      }
    }
  }
  for (const linkSel of sel["related_bug_ids"] ?? []) {
    soup(linkSel).each((_i, el) => {
      const href = soup(el).attr("href") ?? "";
      const m = _RELATED_BUG_RE.exec(href);
      if (m) {
        const val = `BUG-${m[1]}`;
        if (!seen.has(val)) {
          seen.add(val);
          ids.push(val);
        }
      }
    });
  }
  return ids;
}

function _bugzilla_comments_count(soup: Soup): number {
  return soup("pre.bz_comment_text").length || soup("div.bz_comment_text").length;
}

export class BugzillaExtractor {
  backend = "bugzilla";
  version = "v3";

  extract(html: string): DefectTicket {
    if (!html) {
      return new DefectTicket({ ticket_id: "UNKNOWN", backend: this.backend });
    }

    const sel = load_selectors()["bugzilla"] ?? {};
    this.version = sel["version"] ?? this.version;
    const soup = make_soup(html);

    const invalidReason = _detect_bugzilla_invalid(soup);

    const rawId = select_text(soup, sel["ticket_id"] ?? []);
    const ticketId = extract_ticket_id(rawId) || rawId || "UNKNOWN";

    const title = select_text(soup, sel["title"] ?? []);
    const product = select_text(soup, sel["product"] ?? []);
    const module_ = select_text(soup, sel["module"] ?? []);
    const severity = normalize_severity(select_text(soup, sel["severity"] ?? []));
    const priority = select_text(soup, sel["priority"] ?? []);
    const status = normalize_status(select_text(soup, sel["status"] ?? []));
    const resolution = normalize_resolution(select_text(soup, sel["resolution"] ?? []));

    const reportedBy = select_text(soup, sel["reported_by"] ?? []);
    const reportedAt = select_text(soup, sel["reported_at"] ?? []);
    const resolvedBy = select_text(soup, sel["resolved_by"] ?? []);
    const resolvedAt = select_text(soup, sel["resolved_at"] ?? []);

    const description = _bugzilla_description_fallback(soup, sel);
    const steps = select_text(soup, sel["steps_to_reproduce"] ?? []);
    const fixSummary = _bugzilla_fix_summary_fallback(soup, sel);

    let affected = select_texts(soup, sel["affected_versions"] ?? []);
    let fixedVersions = select_texts(soup, sel["fixed_versions"] ?? []);
    const fixedCommit = select_text(soup, sel["fixed_commit"] ?? []);

    if (!affected.length) {
      affected = _extract_versions_from_text(`${description}\n${fixSummary}`, _VERSION_LINE_KEYWORDS["affected"]);
    }
    if (!fixedVersions.length) {
      fixedVersions = _extract_versions_from_text(`${description}\n${fixSummary}`, _VERSION_LINE_KEYWORDS["fixed"]);
    }

    const relatedBugs = _bugzilla_related_bug_ids(soup, sel);

    const attachmentUrls = select_attrs(soup, sel["attachments"] ?? [], "href");
    const attachmentNames = select_texts(soup, sel["attachments"] ?? []);
    const attachments: Attachment[] = attachmentUrls.map((url, i) => ({
      url,
      filename: i < attachmentNames.length ? attachmentNames[i] : "",
    }));

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
      reported_by: reportedBy,
      reported_at: reportedAt,
      resolved_by: resolvedBy,
      resolved_at: resolvedAt,
      description,
      steps_to_reproduce: steps,
      fix_summary: fixSummary,
      affected_versions: affected,
      fixed_versions: fixedVersions,
      fixed_commit: fixedCommit,
      related_bug_ids: relatedBugs,
      comments_count: _bugzilla_comments_count(soup),
      attachments,
      backend: this.backend,
      doc_type: "bug",
      html_sha256: htmlSha,
      invalid_reason: invalidReason,
    });
  }
}
