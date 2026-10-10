import fs from "node:fs";
import path from "node:path";

const logger = {
  warning: (...args: any[]) => console.warn(...args),
  debug: (...args: any[]) => {},
  info: (...args: any[]) => {},
};

const _TOKEN_SPLIT_RE = /[^\w一-鿿]+/;
const _BUG_RE = /BUG-\d+/gi;
const _OP_PREFIXES = ["no", "show", "clear"];

function _command_pattern_matches(pattern: string, concrete: string): boolean {
  const ptoks = pattern.toLowerCase().split(/\s+/).filter((t) => t);
  const ctoks = concrete.toLowerCase().split(/\s+/).filter((t) => t);
  if (ptoks.length === 0 || ctoks.length === 0 || ctoks.length > ptoks.length) {
    return false;
  }
  for (let i = 0; i < ctoks.length; i++) {
    const p = ptoks[i];
    const c = ctoks[i];
    if (p.startsWith("{") && p.endsWith("}")) {
      const alts = p.slice(1, -1).split("|").map((a) => a.trim());
      if (!alts.includes(c)) {
        return false;
      }
    } else if (p !== c) {
      return false;
    }
  }
  return true;
}

function _format_footprint(data: Record<string, any>): string {
  const lines: string[] = [];
  const fid = data.feature_id ?? "?";
  const level = data.level ?? "?";
  const meta = data.footprint_meta ?? {};
  lines.push(`[${fid}] (${level}, verified ${meta.verified_count ?? 0}x)`);
  const cli = (data.cli ?? {}).commands ?? [];
  for (const cmd of cli.slice(0, 5)) {
    if (cmd !== null && typeof cmd === "object" && String(cmd.catalog_head || "").trim()) {
      const { join_catalog_entry, join_miss_label, join_miss_reason } = require("./catalog_join");
      const joined = join_catalog_entry(cmd);
      if (joined !== null && joined !== undefined) {
        const ident = joined.identity;
        lines.push(`  cmd: ${joined.verbatim || joined.head}  [catalog ${ident.family}@${ident.version}]`);
      } else {
        const label = join_miss_label(join_miss_reason(cmd));
        lines.push(`  cmd: ${String(cmd.catalog_head).trim()}  [${label}]`);
      }
      continue;
    }
    lines.push(`  cmd: ${(cmd || {}).command ?? ""}`);
  }
  const _obs_tag = (e: Record<string, any>): string => {
    const v = e.validity ?? "";
    const ou = e.observed_under ?? "";
    const parts = [v, ou ? `语境:${String(ou).slice(0, 60)}` : ""].filter((x) => x);
    const tag = parts.join("|");
    return tag ? `[${tag}] ` : "";
  };
  for (const r of (data.decision_rules ?? []).slice(0, 4)) {
    const cond = String(r.condition ?? "").slice(0, 120);
    const dec = r.decision ?? "";
    if (dec) {
      lines.push(`  rule: ${_obs_tag(r)}${cond} → ${dec}`);
    } else {
      lines.push(`  rule: ${_obs_tag(r)}${cond}`);
    }
  }
  for (const b of (data.behaviors ?? []).slice(0, 3)) {
    lines.push(`  behavior: ${_obs_tag(b)}${String(b.content ?? "").slice(0, 120)}`);
  }
  for (const iss of (data.known_issues ?? []).slice(0, 4)) {
    lines.push(`  issue: ${iss.issue_id ?? ""} ${String(iss.title ?? "").slice(0, 80)}`);
  }
  const vs = data.version_scope ?? {};
  if (vs.product_versions) {
    lines.push(`  versions: ${vs.product_versions.slice(0, 5).join(", ")}`);
  }
  return lines.join("\n");
}

function _sequenceMatcherRatio(a: string, b: string): number {
  if (a === b) {
    return 1.0;
  }
  if (a.length === 0 || b.length === 0) {
    return 0.0;
  }
  const matches = _matchingBlocks(a, b);
  const total = matches.reduce((acc, [, , size]) => acc + size, 0);
  return (2.0 * total) / (a.length + b.length);
}

function _matchingBlocks(a: string, b: string): Array<[number, number, number]> {
  const m = a.length;
  const n = b.length;
  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0));
  for (let i = m - 1; i >= 0; i--) {
    for (let j = n - 1; j >= 0; j--) {
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : 0;
    }
  }
  const blocks: Array<[number, number, number]> = [];
  const collect = (i0: number, i1: number, j0: number, j1: number) => {
    let best = 0;
    let bi = i0;
    let bj = j0;
    for (let i = i0; i < i1; i++) {
      for (let j = j0; j < j1; j++) {
        const k = dp[i][j];
        if (k > best) {
          best = k;
          bi = i;
          bj = j;
        }
      }
    }
    if (best === 0) {
      return;
    }
    collect(i0, bi, j0, bj);
    blocks.push([bi, bj, best]);
    collect(bi + best, i1, bj + best, j1);
  };
  collect(0, m, 0, n);
  return blocks;
}

function _rglobJson(dir: string): string[] {
  const out: string[] = [];
  const walk = (d: string) => {
    let entries: fs.Dirent[];
    try {
      entries = fs.readdirSync(d, { withFileTypes: true });
    } catch {
      return;
    }
    for (const e of entries) {
      const full = path.join(d, e.name);
      if (e.isDirectory()) {
        walk(full);
      } else if (e.isFile() && e.name.endsWith(".json")) {
        out.push(full);
      }
    }
  };
  walk(dir);
  return out;
}

export class FootprintIndex {
  private _dir: string;
  private _nodes: Record<string, Record<string, any>> = {};
  private _bug_index: Record<string, string> = {};
  private _token_index: Record<string, Set<string>> = {};
  private _loaded = false;
  private _load_attempts = 0;
  private static _MAX_LOAD_RETRY = 3;

  constructor(footprint_dir: string) {
    this._dir = footprint_dir;
  }

  private _ensure_loaded(): void {
    if (this._loaded) {
      return;
    }
    if (!fs.existsSync(this._dir)) {
      this._loaded = true;
      return;
    }
    this._load_attempts += 1;
    let transient_skipped = 0;
    for (const f of _rglobJson(this._dir)) {
      let data: Record<string, any>;
      try {
        data = JSON.parse(fs.readFileSync(f, "utf8"));
      } catch (exc: any) {
        if (exc instanceof SyntaxError) {
          logger.warning(`footprint 节点 JSON 损坏(永久跳过)${f}: ${exc}`);
        } else {
          transient_skipped += 1;
          logger.debug(`footprint 读失败(瞬态)${f}: ${exc}`);
        }
        continue;
      }
      const fid = data.feature_id;
      if (!fid) {
        continue;
      }
      this._nodes[fid] = data;
      for (const issue of data.known_issues ?? []) {
        const bug = issue.issue_id;
        if (bug) {
          this._bug_index[String(bug).toUpperCase()] = fid;
        }
      }
      const tokens_to_index = new Set<string>();
      for (const tok of String(fid).split(".")) {
        if (tok) {
          tokens_to_index.add(tok.toLowerCase());
        }
      }
      const content_str = JSON.stringify(data).toLowerCase();
      for (const tok of content_str.split(_TOKEN_SPLIT_RE)) {
        if (tok.length >= 2) {
          tokens_to_index.add(tok);
        }
      }
      for (const tok of tokens_to_index) {
        (this._token_index[tok] ??= new Set()).add(fid);
      }
    }
    if (transient_skipped > 0 && this._load_attempts < FootprintIndex._MAX_LOAD_RETRY) {
      logger.warning(
        `FootprintIndex 偏载:${Object.keys(this._nodes).length} 节点、${transient_skipped} 个瞬态读失败跳过——不缓存,第 ${this._load_attempts} 次重试`
      );
      this._nodes = {};
      this._bug_index = {};
      this._token_index = {};
      return;
    }
    this._loaded = true;
    if (transient_skipped > 0) {
      logger.warning(
        `FootprintIndex 载入 ${Object.keys(this._nodes).length} 节点、${transient_skipped} 个瞬态读失败仍跳过(重试达上限 ${FootprintIndex._MAX_LOAD_RETRY})`
      );
    } else {
      logger.info(
        `FootprintIndex loaded: ${Object.keys(this._nodes).length} nodes, ${Object.keys(this._bug_index).length} BUG, ${Object.keys(this._token_index).length} tokens`
      );
    }
  }

  lookup(command: string): Record<string, any> | null {
    this._ensure_loaded();
    if (!command) {
      return null;
    }
    let result = this._lookup_key(command);
    if (result !== null) {
      return result;
    }
    const completed = this._complete_token_prefixes(command);
    if (completed !== null) {
      result = this._lookup_key(completed);
      if (result !== null) {
        return result;
      }
    }
    const toks = command.toLowerCase().split(/\s+/).filter((t) => t);
    let j = 0;
    while (j < toks.length && _OP_PREFIXES.includes(toks[j])) {
      j += 1;
    }
    if (j > 0 && j < toks.length) {
      const bare = toks.slice(j).join(" ");
      result = this._lookup_key(bare);
      if (result !== null) {
        return result;
      }
      const completed2 = this._complete_token_prefixes(bare);
      if (completed2 !== null) {
        return this._lookup_key(completed2);
      }
    }
    return null;
  }

  private _complete_token_prefixes(command: string): string | null {
    const toks = command.toLowerCase().split(/\s+/).filter((t) => t);
    if (toks.length < 2) {
      return null;
    }
    let prefix = "";
    const out: string[] = [];
    let changed = false;
    for (const t of toks) {
      const base = prefix ? prefix + "." : "";
      const segs = new Set<string>();
      for (const k of Object.keys(this._nodes)) {
        if (k.startsWith(base)) {
          segs.add(k.slice(base.length).split(".", 1)[0]);
        }
      }
      if (segs.has(t)) {
        out.push(t);
      } else {
        const cands = [...segs].filter((s) => s.startsWith(t));
        if (cands.length !== 1) {
          return null;
        }
        out.push(cands[0]);
        changed = true;
      }
      prefix = out.join(".");
    }
    return changed ? out.join(" ") : null;
  }

  private _lookup_key(command: string): Record<string, any> | null {
    const key = command.toLowerCase().split(/\s+/).filter((t) => t).join(".");
    if (key in this._nodes) {
      const result = { ...this._nodes[key] };
      if (!result.children || result.children.length === 0) {
        const prefix_matches = Object.entries(this._nodes)
          .filter(([k]) => k.startsWith(key + "."))
          .map(([, m]) => m.feature_id)
          .sort();
        if (prefix_matches.length > 0) {
          result.children = prefix_matches;
        }
      }
      return result;
    }
    const prefix_matches = Object.entries(this._nodes)
      .filter(([k]) => k.startsWith(key + "."))
      .map(([, m]) => m.feature_id)
      .sort();
    if (prefix_matches.length > 0) {
      return { feature_id: key, level: "branch", children: prefix_matches, summary: `找到 ${prefix_matches.length} 个子节点` };
    }
    return this._alternation_lookup(command);
  }

  private _alternation_lookup(command: string): Record<string, any> | null {
    const toks = command.toLowerCase().split(/\s+/).filter((t) => t);
    for (let i = toks.length - 1; i > 0; i--) {
      const parent_key = toks.slice(0, i).join(".");
      const node = this._nodes[parent_key];
      if (!node) {
        continue;
      }
      for (const cmd of ((node.cli ?? {}) || {}).commands ?? []) {
        if (_command_pattern_matches(cmd.command ?? "", command)) {
          return this.lookup(parent_key);
        }
      }
    }
    return null;
  }

  search(query: string, opts: { top_k?: number } = {}): Array<[string, string]> {
    const top_k = opts.top_k ?? 3;
    this._ensure_loaded();
    if (!query || Object.keys(this._nodes).length === 0) {
      return [];
    }
    const scores: Record<string, number> = {};
    const bugMatches = query.match(_BUG_RE) || [];
    for (const bug of bugMatches) {
      const fid = this._bug_index[bug.toUpperCase()];
      if (fid) {
        scores[fid] = (scores[fid] ?? 0) + 100;
      }
    }
    const query_tokens = query.toLowerCase().split(_TOKEN_SPLIT_RE).filter((t) => t);
    for (const tok of query_tokens) {
      for (const fid of this._token_index[tok] ?? []) {
        scores[fid] = (scores[fid] ?? 0) + 5;
      }
    }
    if (Object.keys(scores).length === 0) {
      for (const [fid, data] of Object.entries(this._nodes)) {
        const content_str = JSON.stringify(data).toLowerCase();
        const hits = query_tokens.filter((tok) => content_str.includes(tok)).length;
        if (hits > 0) {
          scores[fid] = hits;
        }
      }
    }
    const q_low = query.toLowerCase();
    const q_compact = q_low.replace(/ /g, "");

    const _subseq_depth = (node_compact: string): number => {
      let qi = 0;
      let depth = -1;
      for (const c of node_compact) {
        let found = false;
        while (qi < q_compact.length) {
          if (q_compact[qi] === c) {
            depth = qi;
            qi += 1;
            found = true;
            break;
          }
          qi += 1;
        }
        if (!found) {
          return -1;
        }
      }
      return depth;
    };

    const _tiebreak = (fid: string): [number, number, number] => {
      const node = fid.replace(/\./g, " ").toLowerCase();
      const depth = _subseq_depth(node.replace(/ /g, ""));
      if (depth >= 0) {
        return [1, depth, -node.length];
      }
      return [0, _sequenceMatcherRatio(q_low, node), 0];
    };

    const cmpTuple = (a: [number, number, number], b: [number, number, number]): number => {
      for (let i = 0; i < 3; i++) {
        if (a[i] !== b[i]) {
          return a[i] - b[i];
        }
      }
      return 0;
    };

    const ranked = Object.entries(scores)
      .sort((x, y) => {
        if (x[1] !== y[1]) {
          return y[1] - x[1];
        }
        return cmpTuple(_tiebreak(y[0]), _tiebreak(x[0]));
      })
      .slice(0, top_k);
    return ranked.map(([fid]) => [fid, _format_footprint(this._nodes[fid])] as [string, string]);
  }

  stats(): Record<string, any> {
    this._ensure_loaded();
    const by_level: Record<string, number> = {};
    let total_facts = 0;
    const most_verified: Array<[string, number, number]> = [];
    for (const [fid, data] of Object.entries(this._nodes)) {
      const level = data.level ?? "?";
      by_level[level] = (by_level[level] ?? 0) + 1;
      const facts =
        ((data.cli ?? {}).commands ?? []).length +
        (data.decision_rules ?? []).length +
        (data.behaviors ?? []).length +
        (data.known_issues ?? []).length;
      total_facts += facts;
      const verified = (data.footprint_meta ?? {}).verified_count ?? 0;
      most_verified.push([fid, verified, facts]);
    }
    most_verified.sort((a, b) => b[1] - a[1]);
    return {
      total_nodes: Object.keys(this._nodes).length,
      by_level,
      total_facts,
      total_bugs: Object.keys(this._bug_index).length,
      top_nodes: most_verified.slice(0, 5),
    };
  }

  list_nodes(level?: string | null): string[] {
    this._ensure_loaded();
    if (level === null || level === undefined) {
      return Object.keys(this._nodes).sort();
    }
    return Object.entries(this._nodes)
      .filter(([, data]) => data.level === level)
      .map(([fid]) => fid)
      .sort();
  }

  invalidate(): void {
    this._loaded = false;
    this._nodes = {};
    this._bug_index = {};
    this._token_index = {};
  }
}

const _FOOTPRINT_INDEX_SINGLETONS: Record<string, FootprintIndex> = {};

export function get_footprint_index(nodes_subdir: string = "nodes"): FootprintIndex {
  let idx = _FOOTPRINT_INDEX_SINGLETONS[nodes_subdir];
  if (idx === undefined) {
    const kp = require("../../../knowledge_paths");
    const fp_dir = path.join(String(kp.KNOWLEDGE_FOOTPRINTS), nodes_subdir);
    if (nodes_subdir !== "nodes" && !fs.existsSync(fp_dir)) {
      logger.info(`footprint 版本分区 ${nodes_subdir} 不存在，回退默认 nodes/（优雅降级）`);
      return get_footprint_index("nodes");
    }
    idx = new FootprintIndex(fp_dir);
    _FOOTPRINT_INDEX_SINGLETONS[nodes_subdir] = idx;
  }
  return idx;
}

export function invalidate_footprint_index(nodes_subdir?: string | null): void {
  if (nodes_subdir !== null && nodes_subdir !== undefined) {
    const idx = _FOOTPRINT_INDEX_SINGLETONS[nodes_subdir];
    if (idx !== undefined) {
      delete _FOOTPRINT_INDEX_SINGLETONS[nodes_subdir];
      idx.invalidate();
    }
  } else {
    for (const idx of Object.values(_FOOTPRINT_INDEX_SINGLETONS)) {
      idx.invalidate();
    }
    for (const key of Object.keys(_FOOTPRINT_INDEX_SINGLETONS)) {
      delete _FOOTPRINT_INDEX_SINGLETONS[key];
    }
  }
}

export { RawFact, RoutedFact, MergeResult } from "./schema";
export { extract_facts } from "./extractor";
export { route_facts } from "./router";
export { merge_fact } from "./merger";
export { reconcile } from "./reconcile";
