import { RawFact, RoutedFact, anchor_paths } from "./schema";

export const NODES_DIR = "nodes";
const _SAFE_FEATURE_SEG = /^[A-Za-z0-9_\-]+$/;
const _OP_PREFIXES = ["no", "show", "clear"];
const _MD_ESCAPE_RE = /\\([_*~\[\]{}<>|])/g;
const _CLEAN_TOKEN_RE = /^[a-z0-9][a-z0-9_\-]*$/;

export function catalog_head_tokens_clean(head_tokens: any, opts: { strip_verbs?: boolean } = {}): string[] {
  const toks: string[] = [];
  for (const raw of head_tokens || []) {
    const tok = String(raw).replace(_MD_ESCAPE_RE, "$1").trim().toLowerCase();
    if (_CLEAN_TOKEN_RE.test(tok)) {
      toks.push(tok);
    }
  }
  if (opts.strip_verbs) {
    while (toks.length > 0 && _OP_PREFIXES.includes(toks[0])) {
      toks.shift();
    }
  }
  return toks;
}

export function catalog_feature_path(head_tokens: any): string[] {
  return catalog_head_tokens_clean(head_tokens, { strip_verbs: true });
}

function _feature_id_safe(feature_id: string): boolean {
  if (!feature_id || feature_id.startsWith(".") || feature_id.includes("..")) {
    return false;
  }
  return feature_id.split(".").every((seg) => _SAFE_FEATURE_SEG.test(seg));
}

export function route_facts(facts: RawFact[], footprint_dir?: any, nodes_subdir: string = "nodes"): RoutedFact[] {
  const results: RoutedFact[] = [];
  for (const fact of facts) {
    const targets = anchor_paths(fact.cli_commands, fact.feature_path);
    for (const path of targets) {
      const feature_id = path.join(".");
      if (!feature_id) {
        continue;
      }
      if (!_feature_id_safe(feature_id)) {
        continue;
      }
      const bound: RawFact =
        JSON.stringify(path) === JSON.stringify(fact.feature_path)
          ? fact
          : { ...fact, feature_path: path.slice() };
      results.push({ fact: bound, level: "leaf", target_file: `${nodes_subdir}/${feature_id}.json` });
    }
  }
  return results;
}
