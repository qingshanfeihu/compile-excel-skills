import fs from "node:fs";
import path from "node:path";
import { parse as parseYaml } from "yaml";
import * as cheerio from "cheerio";

import { fold_zh_label } from "./_zh_fold";

type AnyNode = cheerio.Cheerio<any>;
export type Soup = cheerio.CheerioAPI;

const _SELECTORS_YAML = path.join(__dirname, "selectors.yaml");

let _SELECTORS_CACHE: Record<string, any> | null = null;

export function load_selectors(): Record<string, any> {
  if (_SELECTORS_CACHE !== null) {
    return _SELECTORS_CACHE;
  }
  if (!fs.existsSync(_SELECTORS_YAML)) {
    _SELECTORS_CACHE = {};
    return _SELECTORS_CACHE;
  }
  _SELECTORS_CACHE = (parseYaml(fs.readFileSync(_SELECTORS_YAML, "utf8")) as Record<string, any>) ?? {};
  return _SELECTORS_CACHE;
}

function nodeText(node: unknown): string {
  const n = node as { type?: string; data?: string; children?: unknown[] };
  if (n.type === "text") {
    return n.data ?? "";
  }
  if (!n.children) {
    return "";
  }
  return n.children.map((c: unknown) => nodeText(c)).join("");
}

function getText(el: AnyNode, sep: string): string {
  void sep;
  const parts = el
    .toArray()
    .map((n) => nodeText(n))
    .join("");
  return parts.replace(/\s+/g, " ").trim();
}

export function make_soup(html: string): Soup {
  const soup = cheerio.load(html);
  soup("script, style, nav, header, footer, noscript").remove();
  return soup;
}

export function select_text(soup: Soup, selectors: string[]): string {
  for (const sel of selectors ?? []) {
    let el: AnyNode;
    try {
      el = soup(sel).first();
    } catch {
      continue;
    }
    if (el.length === 0) {
      continue;
    }
    const text = getText(el, " ");
    if (text) {
      return text;
    }
  }
  return "";
}

export function select_texts(soup: Soup, selectors: string[]): string[] {
  const out: string[] = [];
  const seen = new Set<string>();
  for (const sel of selectors ?? []) {
    try {
      soup(sel).each((_i, el) => {
        const t = getText(soup(el), " ");
        if (t && !seen.has(t)) {
          out.push(t);
          seen.add(t);
        }
      });
    } catch {
      continue;
    }
  }
  return out;
}

export function select_attrs(soup: Soup, selectors: string[], attr: string): string[] {
  const out: string[] = [];
  for (const sel of selectors ?? []) {
    try {
      soup(sel).each((_i, el) => {
        const v = soup(el).attr(attr);
        if (v) {
          out.push(String(v));
        }
      });
    } catch {
      continue;
    }
  }
  return out;
}

const _TICKET_ID_RE = /(BUG|BZ|PLM|TICKET|REQ|STORY|ZT|ZENTAO)[-_ #]*(\d+)/i;

export function extract_ticket_id(text: string): string {
  if (!text) {
    return "";
  }
  const m = _TICKET_ID_RE.exec(text);
  if (!m) {
    return text.trim() ? text.trim().split(/\s+/)[0] : "";
  }
  let prefix = m[1].toUpperCase();
  if (prefix === "BZ") {
    prefix = "BUG";
  }
  if (prefix === "ZENTAO") {
    prefix = "ZT";
  }
  return `${prefix}-${m[2]}`;
}

export function normalize_severity(raw: string): string {
  const s = (raw ?? "").trim().toLowerCase();
  if (!s) {
    return "low";
  }
  if (["critical", "blocker", "p0", "urgent", "s1", "crash"].includes(s)) {
    return "critical";
  }
  if (["high", "major", "p1", "s2"].includes(s)) {
    return "high";
  }
  if (["medium", "mid", "normal", "p2", "s3"].includes(s)) {
    return "mid";
  }
  return "low";
}

export function normalize_status(raw: string): string {
  const s = fold_zh_label((raw ?? "").trim()).toLowerCase();
  if (!s) {
    return "open";
  }
  if (["已关闭", "关闭", "closed"].some((k) => s.includes(k))) {
    return "fixed";
  }
  if (["已解决", "已修复", "fixed", "resolved", "done"].some((k) => s.includes(k))) {
    return "fixed";
  }
  if (
    ["激活", "新建", "new", "active", "triage", "unconfirmed", "open", "待办", "待修复", "待处理"].some((k) => s.includes(k))
  ) {
    return ["激活", "triage", "unconfirmed"].some((k) => s.includes(k)) ? "triage" : "open";
  }
  return "open";
}

export function normalize_resolution(raw: string | null | undefined): string {
  if (raw === null || raw === undefined) {
    return "";
  }
  const s = fold_zh_label(String(raw).trim()).toLowerCase();
  if (!s || s === "---" || s === "none") {
    return "";
  }
  const mapping: Array<[string[], string]> = [
    [["fixed", "已解决", "修复", "resolved"], "fixed"],
    [["duplicate", "重复", "重复 bug", "重复问题"], "duplicate"],
    [["not_repro", "无法重现", "无法复现", "worksforme", "works for me", "不能重现"], "not_repro"],
    [["by design", "by_design", "设计如此", "按设计", "设计"], "by_design"],
    [["wontfix", "wont_fix", "won't fix", "不予解决", "不解决"], "wont_fix"],
    [["external", "外部原因", "第三方"], "external"],
    [["postponed", "延期", "推迟"], "postponed"],
    [["转为需求", "transferred", "转需求"], "transferred"],
  ];
  for (const [keys, label] of mapping) {
    if (keys.some((k) => s.includes(k))) {
      return label;
    }
  }
  return s;
}

export function parse_int(raw: string | number | null | undefined, default_: number = 0): number {
  if (raw === null || raw === undefined) {
    return default_;
  }
  try {
    const n = parseInt(String(raw).trim(), 10);
    if (Number.isNaN(n)) {
      return default_;
    }
    return n;
  } catch {
    return default_;
  }
}
