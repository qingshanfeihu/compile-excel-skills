// 生成：tools/extract_engine.py ← InfoTest main/kms/manual_locator.py（sha256 e5405f327e813db9）。不在这里手改。
import * as manual_catalog_store from "./manual_catalog_store";

const _ADOC_SRC_RE = /^(?:manual:)?(?<src>(?:Chapter|Appendix)[^/\s:]+\.adoc:\d+)\s*$/i;
const _CACHE_CAP = 8;
const _CACHE = new Map<string, Record<string, any>>();
const _CACHE_ORDER: string[] = [];

export interface ManualLocatorResolution {
  ok: boolean;
  display: string;
  adoc_src?: string;
  version?: string;
  family?: string;
  md_line?: number;
  reason?: string;
}

export function parse_adoc_style_src(locator: string): string | null {
  const text = String(locator ?? "").trim();
  if (!text) {
    return null;
  }
  const match = _ADOC_SRC_RE.exec(text);
  if (!match || !match.groups) {
    return null;
  }
  return match.groups.src;
}

function _line_at(mdText: string, pos: number): number {
  return mdText.slice(0, pos).split("\n").length;
}

function _build_forward_index(catalog: Record<string, any>, mdText: string): Record<string, any> {
  const bySrc: Record<string, number> = {};
  const bySrcVerbatim = new Map<string, number>();
  const byHead: Record<string, number> = {};
  let cursor = 0;
  for (const sig of catalog.signatures ?? []) {
    if (typeof sig !== "object" || sig === null) {
      continue;
    }
    const verbatim = String(sig.signature_verbatim ?? "");
    const src = String(sig.src ?? "").trim();
    const head = (sig.head_tokens ?? []).map((t: any) => String(t)).join(" ").trim();
    if (!verbatim) {
      continue;
    }
    const pos = mdText.indexOf(verbatim, cursor);
    if (pos < 0) {
      continue;
    }
    const line = _line_at(mdText, pos);
    cursor = pos + verbatim.length;
    if (src) {
      const key = `${src}\0${verbatim}`;
      if (!bySrcVerbatim.has(key)) {
        bySrcVerbatim.set(key, line);
      }
      if (!(src in bySrc)) {
        bySrc[src] = line;
      }
    }
    if (head && !(head in byHead)) {
      byHead[head] = line;
    }
  }
  const headByVdSrc: Record<string, string> = {};
  for (const vd of catalog.value_domains ?? []) {
    if (typeof vd !== "object" || vd === null) {
      continue;
    }
    const src = String(vd.src ?? "").trim();
    const head = String(vd.head ?? "").trim();
    if (src && head && !(src in bySrc) && !(src in headByVdSrc)) {
      headByVdSrc[src] = head;
    }
  }
  return { by_src: bySrc, by_src_verbatim: bySrcVerbatim, by_head: byHead, head_by_vd_src: headByVdSrc };
}

function _cached_index(version: string, family: string, root?: string): Record<string, any> | null {
  let catalog: Record<string, any> | null;
  let verdict: Record<string, any>;
  try {
    [catalog, verdict] = manual_catalog_store.load_coupled_catalog(version, family, root);
  } catch {
    return null;
  }
  if (catalog === null || verdict.status !== "ok") {
    return null;
  }
  const sha = String(verdict.catalog_sha256 ?? "");
  const key = `${version}\0${family}\0${sha}`;
  const cached = _CACHE.get(key);
  if (cached !== undefined) {
    return cached;
  }
  const md = manual_catalog_store.md_path(version, family, root ?? manual_catalog_store.manual_root());
  let mdText: string;
  try {
    mdText = require("node:fs").readFileSync(md, "utf8");
  } catch {
    return null;
  }
  const index = _build_forward_index(catalog, mdText);
  index.identity = { version: String(version), family: String(family), sha256: sha };
  if (!_CACHE.has(key)) {
    _CACHE.set(key, index);
    _CACHE_ORDER.push(key);
    while (_CACHE_ORDER.length > _CACHE_CAP) {
      const oldest = _CACHE_ORDER.shift();
      if (oldest !== undefined) {
        _CACHE.delete(oldest);
      }
    }
  }
  return index;
}

function _lookup_line(index: Record<string, any>, adocSrc: string, verbatim?: string): [number, string] | null {
  const bySrc = index.by_src as Record<string, number>;
  const bySrcVerbatim = index.by_src_verbatim as Map<string, number>;
  const byHead = index.by_head as Record<string, number>;
  const headByVdSrc = index.head_by_vd_src as Record<string, string>;
  if (verbatim) {
    const key = `${adocSrc}\0${verbatim}`;
    if (bySrcVerbatim.has(key)) {
      return [bySrcVerbatim.get(key)!, "signature_verbatim"];
    }
  }
  if (adocSrc in bySrc) {
    return [bySrc[adocSrc], "signature_src"];
  }
  const head = headByVdSrc[adocSrc];
  if (head && head in byHead) {
    return [byHead[head], "same_head_signature"];
  }
  return null;
}

function _fail(adocSrc: string, reason: string, locator = ""): ManualLocatorResolution {
  const shown = adocSrc || String(locator ?? "").trim() || "(empty)";
  const display = `${shown} (unresolved — adoc source is not on disk locally; could not map to a manual md line: ${reason})`;
  return { ok: false, display, adoc_src: adocSrc, reason };
}

export function resolve_manual_locator(locator: string, version: string, family?: string, verbatim?: string, root?: string): ManualLocatorResolution {
  const raw = String(locator ?? "").trim();
  const adocSrc = parse_adoc_style_src(raw);
  if (adocSrc === null) {
    if (!raw) {
      return _fail("", "empty locator");
    }
    return { ok: true, display: raw, reason: "passthrough" };
  }
  const ver = String(version ?? "").trim();
  if (!ver) {
    return _fail(adocSrc, "manual version unknown");
  }
  const families = family ? [String(family)] : ["cli", "app"];
  let lastReason = "coupled catalog not in effect";
  for (const fam of families) {
    const famStr = String(fam ?? "").trim();
    if (!["cli", "app"].includes(famStr)) {
      continue;
    }
    const index = _cached_index(ver, famStr, root);
    if (index === null) {
      lastReason = `coupled catalog not in effect for ${ver}/${famStr}`;
      continue;
    }
    const hit = _lookup_line(index, adocSrc, verbatim);
    if (hit === null) {
      lastReason = `src ${JSON.stringify(adocSrc)} not mapped in ${ver}/${famStr} catalog cursor`;
      continue;
    }
    const [line, via] = hit;
    const display = `manual:${ver}/${famStr}_cn.md:${line}`;
    return { ok: true, display, adoc_src: adocSrc, version: ver, family: famStr, md_line: line, reason: via };
  }
  return _fail(adocSrc, lastReason);
}

export function display_manual_locator(locator: string, version: string, family?: string, verbatim?: string, root?: string): string {
  return resolve_manual_locator(locator, version, family, verbatim, root).display;
}

export function clear_manual_locator_cache(): void {
  _CACHE.clear();
  _CACHE_ORDER.length = 0;
}
