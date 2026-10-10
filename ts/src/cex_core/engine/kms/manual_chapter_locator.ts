// 生成：tools/extract_engine.py ← InfoTest main/kms/manual_chapter_locator.py（sha256 5bdd1b2a586d7c5d）。不在这里手改。
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import * as manual_catalog_store from "./manual_catalog_store";

const _MANUAL_PATH_RE = /(?:^|\/)manual\/(?<version>[^/]+)\/(?<family>cli|app)_cn\.md$/;

export class ManualChapterLocatorError extends Error {}

function _heading_starts(mdText: string, prefix: string): number[] {
  const starts: number[] = [];
  let offset = 0;
  for (const line of mdText.split(/(?<=\n)/)) {
    if (line.startsWith(prefix)) {
      starts.push(offset);
    }
    offset += line.length;
  }
  return starts;
}

function _line_at(mdText: string, start: number): string {
  const end = mdText.indexOf("\n", start);
  return mdText.slice(start, end >= 0 ? end : mdText.length).trim();
}

export function section_boundaries(mdText: string): [number[], number[]] {
  const chapters = _heading_starts(mdText, "# ");
  const subsections = _heading_starts(mdText, "## ");
  return [[...new Set([...chapters, ...subsections])].sort((a, b) => a - b), chapters];
}

function _bisectRight(arr: number[], x: number): number {
  let lo = 0;
  let hi = arr.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (x < arr[mid]) {
      hi = mid;
    } else {
      lo = mid + 1;
    }
  }
  return lo;
}

export function locate_quote(mdText: string, anchor: Record<string, any>): number {
  const quote = String(anchor.quote ?? "");
  if (!quote) {
    throw new ManualChapterLocatorError("anchor has no quote");
  }
  const span = anchor.source_span;
  if (typeof span === "object" && span !== null) {
    let start: number;
    let end: number;
    try {
      start = parseInt(String(span.start ?? "0"), 10);
      end = parseInt(String(span.end ?? "0"), 10);
    } catch {
      start = end = -1;
    }
    if (0 <= start && start < end && end <= mdText.length && mdText.slice(start, end) === quote) {
      return start;
    }
  }
  const hits = mdText.split(quote).length - 1;
  if (hits === 1) {
    return mdText.indexOf(quote);
  }
  throw new ManualChapterLocatorError(`anchor quote is not uniquely locatable in the current manual (matches=${hits})`);
}

export function section_pin(mdText: string, pos: number): Record<string, string> {
  const [boundaries, chapters] = section_boundaries(mdText);
  if (!boundaries.length) {
    throw new ManualChapterLocatorError("manual has no level-1/2 headings");
  }
  const index = _bisectRight(boundaries, pos) - 1;
  let secStart: number;
  let secEnd: number;
  let chapterLine: string;
  if (index < 0) {
    secStart = 0;
    secEnd = boundaries[0];
    chapterLine = "";
  } else {
    secStart = boundaries[index];
    secEnd = index + 1 < boundaries.length ? boundaries[index + 1] : mdText.length;
    const chapterIndex = _bisectRight(chapters, pos) - 1;
    chapterLine = chapterIndex >= 0 ? _line_at(mdText, chapters[chapterIndex]) : "";
  }
  const material = chapterLine + "\n" + mdText.slice(secStart, secEnd);
  return {
    chapter: chapterLine,
    section: index >= 0 ? _line_at(mdText, secStart) : "",
    section_sha256: crypto.createHash("sha256").update(material, "utf8").digest("hex"),
  };
}

function _family_version_from_source_path(sourcePath: string): [string, string] {
  const normalized = String(sourcePath ?? "").replace(/\\/g, "/");
  const match = _MANUAL_PATH_RE.exec(normalized);
  if (!match || !match.groups) {
    return ["", ""];
  }
  return [String(match.groups.version ?? ""), String(match.groups.family ?? "")];
}

const _MANUAL_TEXT_CACHE = new Map<string, [unknown, string]>();
const _PINS_CACHE = new Map<string, [Record<string, Record<string, string>>, Array<Record<string, string>>]>();
const _MANUAL_TEXT_CACHE_MAX = 8;
const _PINS_CACHE_MAX = 256;

export function clear_locator_cache(): void {
  manual_catalog_store.clear_bounded(_MANUAL_TEXT_CACHE, _PINS_CACHE);
}

function _load_manual_text(version: string, family: string, root: string | undefined): string {
  const base = root ?? manual_catalog_store.manual_root();
  const key = `${base}\0${version}\0${family}`;
  const identity = manual_catalog_store.manual_identity(version, family, base);
  const cached = _MANUAL_TEXT_CACHE.get(key);
  if (cached !== undefined && JSON.stringify(cached[0]) === JSON.stringify(identity)) {
    return cached[1];
  }
  const [catalog, verdict] = manual_catalog_store.load_coupled_catalog(version, family, root);
  if (catalog === null || verdict.status !== "ok") {
    throw new ManualChapterLocatorError(`coupled catalog not in effect for ${version}/${family}: ${verdict.status}`);
  }
  const md = manual_catalog_store.md_path(version, family, root);
  let text: string;
  try {
    text = fs.readFileSync(md, "utf8");
  } catch (exc) {
    throw new ManualChapterLocatorError(`manual md unreadable: ${md}`, { cause: exc });
  }
  if (JSON.stringify(manual_catalog_store.manual_identity(version, family, base)) === JSON.stringify(identity)) {
    manual_catalog_store.remember_bounded(_MANUAL_TEXT_CACHE, key, [identity, text], _MANUAL_TEXT_CACHE_MAX);
  }
  return text;
}

function _resolve_target(anchor: Record<string, any>, manualVersion: string): [string, string] {
  const sourcePath = String(anchor.source_path ?? "");
  const [pathVersion, pathFamily] = _family_version_from_source_path(sourcePath);
  const version = String(manualVersion || pathVersion || "").trim();
  const family = String(pathFamily || "").trim();
  if (!version || !["cli", "app"].includes(family)) {
    throw new ManualChapterLocatorError(`cannot resolve manual version/family for anchor path ${JSON.stringify(sourcePath)}`);
  }
  return [version, family];
}

function _anchor_key(anchor: Record<string, any>): string {
  const anchorId = String(anchor.anchor_id ?? "");
  if (!anchorId) {
    throw new ManualChapterLocatorError("anchor has no anchor_id");
  }
  return anchorId;
}

export function anchor_chapter_pins(anchors: Array<Record<string, any>>, manualVersion: string, root?: string): Record<string, Record<string, string>> {
  const [pins, failures] = anchor_chapter_pins_partial(anchors, manualVersion, root);
  if (failures.length) {
    throw new ManualChapterLocatorError(failures.slice(0, 3).map((row) => `${row.anchor_id}: ${row.reason}`).join("; "));
  }
  return pins;
}

export function anchor_chapter_pins_partial(anchors: Array<Record<string, any>>, manualVersion: string, root?: string): [Record<string, Record<string, string>>, Array<Record<string, string>>] {
  const anchorsList = [...anchors];
  const cacheKey = _pins_cache_key(anchorsList, manualVersion, root);
  const cached = _PINS_CACHE.get(cacheKey);
  if (cached !== undefined) {
    const [pinsHit, failuresHit] = cached;
    return [
      Object.fromEntries(Object.entries(pinsHit).map(([k, v]) => [k, { ...v }])),
      failuresHit.map((row) => ({ ...row })),
    ];
  }
  const texts = new Map<string, string>();
  const pins: Record<string, Record<string, string>> = {};
  const failures: Array<Record<string, string>> = [];
  for (const anchor of anchorsList) {
    if (typeof anchor !== "object" || anchor === null) {
      continue;
    }
    let anchorId: string;
    try {
      anchorId = _anchor_key(anchor);
    } catch (exc) {
      if (exc instanceof ManualChapterLocatorError) {
        failures.push({ anchor_id: "(无 anchor_id)", reason: String(exc.message) });
        continue;
      }
      throw exc;
    }
    try {
      const [version, family] = _resolve_target(anchor, manualVersion);
      const key = `${version}\0${family}`;
      if (!texts.has(key)) {
        texts.set(key, _load_manual_text(version, family, root));
      }
      const mdText = texts.get(key)!;
      pins[anchorId] = section_pin(mdText, locate_quote(mdText, anchor));
    } catch (exc) {
      if (exc instanceof ManualChapterLocatorError) {
        failures.push({ anchor_id: anchorId, reason: String(exc.message) });
      } else {
        throw exc;
      }
    }
  }
  manual_catalog_store.remember_bounded(_PINS_CACHE, cacheKey, [pins, failures], _PINS_CACHE_MAX);
  return [
    Object.fromEntries(Object.entries(pins).map(([k, v]) => [k, { ...v }])),
    failures.map((row) => ({ ...row })),
  ];
}

function _pins_cache_key(anchors: Array<Record<string, any>>, manualVersion: string, root: string | undefined): string {
  const base = root ?? manual_catalog_store.manual_root();
  const signature: unknown[] = [];
  const targets = new Set<string>();
  for (const anchor of anchors) {
    if (typeof anchor !== "object" || anchor === null) {
      signature.push(["not-a-mapping"]);
      continue;
    }
    const span = anchor.source_span;
    signature.push([
      String(anchor.anchor_id ?? ""),
      String(anchor.source_path ?? ""),
      String(anchor.source_sha256 ?? ""),
      typeof span === "object" && span !== null ? String(span.start) : "",
      typeof span === "object" && span !== null ? String(span.end) : "",
      crypto.createHash("sha256").update(String(anchor.quote ?? ""), "utf8").digest("hex"),
    ]);
    try {
      const [version, family] = _resolve_target(anchor, manualVersion);
      targets.add(`${version}\0${family}`);
    } catch {
      // ignore
    }
  }
  const identities = [...targets].sort().map((target) => {
    const [version, family] = target.split("\0");
    return [version, family, manual_catalog_store.manual_identity(version, family, base)];
  });
  return JSON.stringify([String(base), String(manualVersion ?? ""), signature, identities]);
}
