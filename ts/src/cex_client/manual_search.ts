import { ClientError } from "./errors.js";
import { Workspace, NO_DEVICE_BUILD, safeComponent } from "./workspace.js";
import { cachedManifest, _checkManifest, locked, verifiedFile } from "./bundle.js";

const _TERM_RE = /[A-Za-z0-9_]+|[\u4e00-\u9fff]/g;
const _MAX_QUERY_CHARS = 512;
const _MAX_QUERY_TERMS = 32;
const _CONTEXT_LINES = 2;
const _SNIPPET_CHARS = 600;

function _fold(text: string): string {
  return text.toLowerCase();
}

function _terms(text: string): string[] {
  const folded = _fold(text.slice(0, _MAX_QUERY_CHARS));
  const found = folded.match(_TERM_RE) ?? [];
  return [...new Set(found)].slice(0, _MAX_QUERY_TERMS);
}

function _clip(line: string, terms: string[]): string {
  if (line.length <= _SNIPPET_CHARS) return line;
  const folded = _fold(line);
  let first = 0;
  for (const term of terms) {
    const pos = folded.indexOf(term);
    if (pos >= 0 && (first === 0 || pos < first)) first = pos;
  }
  const start = Math.max(0, first - 100);
  const end = Math.min(line.length, start + _SNIPPET_CHARS);
  return (start ? "…" : "") + line.slice(start, end) + (end < line.length ? "…" : "");
}

function _searchFile(filePath: string, terms: string[]): [string[], [number[], number][]] {
  const raw = require("node:fs").readFileSync(filePath, "utf8");
  const lines = raw.split("\n");
  const folded = lines.map(_fold);
  const hits = folded.map((line: string) => terms.map((t: string) => line.includes(t)));
  const found: [number[], number][] = [];
  for (let index = 0; index < hits.length; index++) {
    const flags = hits[index];
    const lineHits = flags.filter(Boolean).length;
    if (!lineHits) continue;
    const lo = Math.max(0, index - _CONTEXT_LINES);
    const hi = Math.min(lines.length, index + _CONTEXT_LINES + 1);
    const windowHits = terms.filter((_, ti: number) => hits.slice(lo, hi).some((row: boolean[]) => row[ti])).length;
    const occurrences = terms.reduce((sum, term) => sum + (folded[index].split(term).length - 1), 0);
    const score = [lineHits, windowHits, occurrences];
    found.push([score, index]);
  }
  return [lines, found];
}

export function query(ws: Workspace, text: string, limit: number): Record<string, unknown> {
  const terms = _terms(text);
  if (!terms.length) throw new ClientError("q is required");
  const build = ws.selectedBuild;
  if (!build) {
    return {
      ok: false,
      build: null,
      error: NO_DEVICE_BUILD,
      next: "Log in (cex_login_start / cex_login_wait picks the device build) or set it with cex_init device_build, then call cex_sync.",
    };
  }
  const lock = locked(ws, build, true);
  try {
    const manifest = cachedManifest(ws, build);
    if (manifest === null) {
      return { ok: false, build, error: "no synced bundle for this build", next: "Call cex_sync to download the compile data bundle first." };
    }
    let entries: Record<string, unknown>[];
    try {
      entries = _checkManifest(manifest, build);
    } catch (exc) {
      if (exc instanceof ClientError) {
        return { ok: false, build, bundle_id: manifest.bundle_id, error: `${exc}; call cex_sync`, next: "Call cex_sync and retry." };
      }
      throw exc;
    }
    const source = manifest.source as Record<string, unknown> | undefined;
    const boundVersion = source?.manual_version;
    const manualRoot = boundVersion !== undefined && boundVersion !== null
      ? `manual/${safeComponent(boundVersion, "manual_version")}/`
      : "manual/";
    const matches: [number[], string, number][] = [];
    const sources: Record<string, string[]> = {};
    const skipped: { path: string; reason: string }[] = [];
    let searched = 0;
    for (const entry of entries) {
      const rel = String(entry.path);
      if (!rel.startsWith(manualRoot) || !rel.endsWith(".md")) continue;
      const manualRel = rel.slice("manual/".length);
      if (!manualRel) continue;
      let p: string;
      try {
        p = verifiedFile(ws, entry, build);
      } catch (exc) {
        return { ok: false, build, bundle_id: manifest.bundle_id, error: String(exc), next: "Call cex_sync and retry." };
      }
      let lines: string[], found: [number[], number][];
      try {
        [lines, found] = _searchFile(p, terms);
      } catch (exc) {
        skipped.push({ path: manualRel, reason: exc instanceof Error && exc.message.includes("UTF-8") ? "invalid UTF-8" : "could not read" });
        continue;
      }
      sources[manualRel] = lines;
      for (const [score, index] of found) matches.push([score, manualRel, index]);
      searched++;
    }
    matches.sort((a, b) => {
      for (let i = 0; i < 3; i++) {
        if (a[0][i] !== b[0][i]) return b[0][i] - a[0][i];
      }
      if (a[1] !== b[1]) return a[1].localeCompare(b[1]);
      return a[2] - b[2];
    });
    const results = matches.slice(0, limit).map(([score, rel, index]) => {
      const lines = sources[rel];
      const lo = Math.max(0, index - _CONTEXT_LINES);
      const hi = Math.min(lines.length, index + _CONTEXT_LINES + 1);
      const snippet = Array.from({ length: hi - lo }, (_, i) => `${lo + i + 1}: ${_clip(lines[lo + i], terms)}`).join("\n");
      const lineNumber = index + 1;
      return { path: rel, line: lineNumber, snippet, ref: `manual:${rel}:${lineNumber}`, all_terms: score[1] === terms.length };
    });
    return {
      ok: true,
      query: text,
      build,
      bundle_id: manifest.bundle_id,
      bundle: ws.bundleDir(build),
      manuals_searched: searched,
      manuals_skipped: skipped,
      results,
    };
  } finally {
    lock.release();
  }
}
