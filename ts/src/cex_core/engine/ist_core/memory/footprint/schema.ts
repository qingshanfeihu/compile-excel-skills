export type FactKind = "cli_command" | "decision_rule" | "behavior" | "known_issue";
export type Level = "leaf" | "trunk" | "branch" | "root";

export interface RawFact {
  fact_kind: FactKind;
  feature_path: string[];
  fact_key: string;
  cli_commands: string[][];
  cli_syntax: string;
  parameters: Record<string, any>[];
  condition: string;
  decision: string;
  content: string;
  issue_id: string;
  issue_title: string;
  affected_versions: string[];
  evidence_file: string;
  evidence_quote: string;
  device_evidence: Record<string, any>;
  raw_invocation: string;
  validity: string;
  observed_under: string;
  valid_for: string[];
  superseded_by: string;
  catalog_head: string;
  catalog_identity: Record<string, any>;
  source_thread: string;
}

export function makeRawFact(init: Partial<RawFact> & Pick<RawFact, "fact_kind" | "feature_path" | "fact_key">): RawFact {
  return {
    cli_commands: [],
    cli_syntax: "",
    parameters: [],
    condition: "",
    decision: "",
    content: "",
    issue_id: "",
    issue_title: "",
    affected_versions: [],
    evidence_file: "",
    evidence_quote: "",
    device_evidence: {},
    raw_invocation: "",
    validity: "verified",
    observed_under: "",
    valid_for: [],
    superseded_by: "",
    catalog_head: "",
    catalog_identity: {},
    source_thread: "",
    ...init,
  };
}

export interface RoutedFact {
  fact: RawFact;
  level: Level;
  target_file: string;
}

export interface MergeResult {
  action: string;
  target_file: string;
  detail: string;
}

export function makeMergeResult(init: Partial<MergeResult> = {}): MergeResult {
  return { action: "skip", target_file: "", detail: "", ...init };
}

export function longest_common_prefix(seqs: string[][]): string[] {
  if (seqs.length === 0) {
    return [];
  }
  let prefix = seqs[0].slice();
  for (const seq of seqs.slice(1)) {
    let i = 0;
    while (i < prefix.length && i < seq.length && prefix[i] === seq[i]) {
      i += 1;
    }
    prefix = prefix.slice(0, i);
    if (prefix.length === 0) {
      break;
    }
  }
  return prefix;
}

export function anchor_paths(cli_commands: string[][], fallback?: string[] | null): string[][] {
  const cleaned = (cli_commands || []).filter((c) => c && c.length > 0).map((c) => c.slice());
  if (cleaned.length === 0) {
    return fallback ? [fallback.slice()] : [];
  }
  const unique: string[][] = [];
  for (const c of cleaned) {
    if (!unique.some((u) => JSON.stringify(u) === JSON.stringify(c))) {
      unique.push(c);
    }
  }
  if (unique.length === 1) {
    return [unique[0]];
  }
  const prefix = longest_common_prefix(unique);
  if (prefix.length > 0) {
    return [prefix];
  }
  const modules: string[][] = [];
  for (const c of unique) {
    const head = [c[0]];
    if (!modules.some((m) => m[0] === head[0])) {
      modules.push(head);
    }
  }
  return modules;
}

function _meta_template(): Record<string, any> {
  return { created_at: null, verified_count: 0, source_threads: [] };
}

export function node_template(feature_id: string, level: string = "leaf"): Record<string, any> {
  return {
    schema_version: 3,
    feature_id,
    level,
    cli: { commands: [] },
    decision_rules: [],
    behaviors: [],
    known_issues: [],
    children: [],
    version_scope: {},
    footprint_meta: _meta_template(),
  };
}

export function leaf_template(feature_id: string): Record<string, any> {
  return node_template(feature_id, "leaf");
}

export function trunk_template(feature_id: string): Record<string, any> {
  return node_template(feature_id, "trunk");
}

export function branch_template(feature_id: string): Record<string, any> {
  return node_template(feature_id, "branch");
}

export function root_template(feature_id: string): Record<string, any> {
  return node_template(feature_id, "root");
}

export const TEMPLATE_MAP: Record<string, (feature_id: string) => Record<string, any>> = {
  leaf: leaf_template,
  trunk: trunk_template,
  branch: branch_template,
  root: root_template,
};

export const LEVEL_KINDS: Record<string, Set<FactKind>> = {
  leaf: new Set(["cli_command", "decision_rule", "behavior", "known_issue"]),
  trunk: new Set(["cli_command", "decision_rule", "behavior", "known_issue"]),
  branch: new Set(["cli_command", "decision_rule", "behavior", "known_issue"]),
  root: new Set(["cli_command", "decision_rule", "behavior", "known_issue"]),
};
