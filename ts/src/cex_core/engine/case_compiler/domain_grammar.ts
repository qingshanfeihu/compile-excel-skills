import fs from "node:fs";
import path from "node:path";
import { KNOWLEDGE_DATA_ROOT } from "../knowledge_paths";
import { pyRepr } from "../_py";

export const GRAMMAR_PATH = path.join(KNOWLEDGE_DATA_ROOT, "compile_ref", "domain_grammar.json");
const _cache: Record<string, any> = {};

export class CleanupFamily {
  rule_order: number;
  matched_prefix: string;
  module: string;
  constructor(rule_order: number, matched_prefix: string, module: string) {
    this.rule_order = rule_order;
    this.matched_prefix = matched_prefix;
    this.module = module;
    Object.freeze(this);
  }
}

export class RestoreGateGrammar {
  observe_leading: Set<string>;
  mutating: Set<string>;
  local_disk_patterns: RegExp[];
  cleanup_rules: Array<Record<string, any>>;
  constructor(observe_leading: Set<string>, mutating: Set<string>, local_disk_patterns: RegExp[], cleanup_rules: Array<Record<string, any>>) {
    this.observe_leading = observe_leading;
    this.mutating = mutating;
    this.local_disk_patterns = local_disk_patterns;
    this.cleanup_rules = cleanup_rules;
    Object.freeze(this);
  }
}

export function load_grammar(): Record<string, any> {
  let mtime: number;
  try {
    mtime = Number(fs.statSync(GRAMMAR_PATH).mtimeMs);
  } catch (exc) {
    throw new Error(`领域文法数据缺失: ${GRAMMAR_PATH}`);
  }
  if (_cache.mtime === mtime) {
    return _cache.data;
  }
  const data = JSON.parse(fs.readFileSync(GRAMMAR_PATH, "utf8"));
  const compiled: Record<string, RegExp> = {};
  for (const [sid, s] of Object.entries<any>(data.statements || {})) {
    compiled[sid] = new RegExp(s.pattern, "i");
  }
  _cache.mtime = mtime;
  _cache.data = data;
  _cache.compiled = compiled;
  return data;
}

export function stmt_re(stmt_id: string): RegExp {
  load_grammar();
  return _cache.compiled[stmt_id];
}

export function verbs(class_name: string): string[] {
  const vc = load_grammar().verb_classes[class_name];
  return [...(vc.verbs || vc.words || [])];
}

export function restore_gate_grammar(): RestoreGateGrammar {
  const data = load_grammar();
  const verbClasses = data.verb_classes;
  const persistence = data.persistence_channels;
  const framework = data.framework_cleanup_rules;
  if (![verbClasses, persistence, framework].every((v) => typeof v === "object" && v !== null && !Array.isArray(v))) {
    throw new Error("restore-gate grammar sections are missing");
  }

  const _verbs = (name: string): Set<string> => {
    const section = verbClasses[name];
    const values = typeof section === "object" && section !== null ? section.verbs : null;
    if (!Array.isArray(values) || !values.length) {
      throw new Error(`restore-gate verb class is missing: ${name}`);
    }
    const normalized = new Set(values.filter((v) => String(v).trim()).map((v) => String(v).trim().toLowerCase()));
    if (normalized.size === 0) {
      throw new Error(`restore-gate verb class is empty: ${name}`);
    }
    return normalized;
  };
  const localDisk = persistence.local_disk;
  const rawPatterns = typeof localDisk === "object" && localDisk !== null ? localDisk.patterns : null;
  if (!Array.isArray(rawPatterns) || !rawPatterns.length) {
    throw new Error("restore-gate local_disk patterns are missing");
  }
  const patterns = rawPatterns.map((p) => new RegExp(String(p), "i"));
  const rawRules = framework.rules;
  if (!Array.isArray(rawRules) || !rawRules.length) {
    throw new Error("restore-gate framework cleanup rules are missing");
  }
  const rules: Array<Record<string, any>> = [];
  for (let index = 0; index < rawRules.length; index++) {
    const rule = rawRules[index];
    if (typeof rule !== "object" || rule === null || Array.isArray(rule)) {
      throw new Error("restore-gate cleanup rule must be an object");
    }
    const prefixes = rule.prefixes;
    const order = rule.order;
    if (
      typeof order === "boolean" ||
      typeof order !== "number" ||
      !Number.isInteger(order) ||
      !Array.isArray(prefixes) ||
      !prefixes.length ||
      prefixes.some((prefix) => typeof prefix !== "string" || !prefix)
    ) {
      throw new Error(`restore-gate cleanup rule is invalid: ${index}`);
    }
    rules.push({ order, prefixes: [...prefixes] });
  }
  return new RestoreGateGrammar(_verbs("observe_leading"), _verbs("mutating"), patterns, rules);
}

export function cleanup_family(command: string, grammar: RestoreGateGrammar, strip_mutating_verb = false): CleanupFamily | null {
  let normalized = String(command || "").trim().toLowerCase();
  if (!normalized) {
    return null;
  }
  if (strip_mutating_verb) {
    const sp = normalized.indexOf(" ");
    const first = sp < 0 ? normalized : normalized.slice(0, sp);
    const remainder = sp < 0 ? "" : normalized.slice(sp + 1);
    if (!grammar.mutating.has(first) || sp < 0 || !remainder.trim()) {
      return null;
    }
    normalized = remainder.trim();
  }
  for (const rule of grammar.cleanup_rules) {
    for (const prefix of rule.prefixes) {
      const folded = prefix.toLowerCase();
      if (normalized.startsWith(folded)) {
        return new CleanupFamily(Number(rule.order), prefix, folded.split(/\s+/)[0]);
      }
    }
  }
  return null;
}

export function is_object_config_command(command: string, grammar: RestoreGateGrammar): boolean {
  const normalized = String(command || "").trim();
  const first = normalized ? normalized.split(/\s+/, 2)[0].toLowerCase() : "";
  if (!first || grammar.observe_leading.has(first) || grammar.mutating.has(first)) {
    return false;
  }
  return !grammar.local_disk_patterns.some((pattern) => pattern.test(normalized));
}

export function probe_tool_transport_failure_codes(): Record<string, number[]> {
  const table = (load_grammar().probe_tools || {}).transport_failure_exit_codes || {};
  const out: Record<string, number[]> = {};
  for (const [tool, row] of Object.entries<any>(table)) {
    const codes = typeof row === "object" && row !== null ? row.codes : null;
    if (!Array.isArray(codes)) continue;
    const cleaned = [...new Set(codes.filter((c) => typeof c === "number" && Number.isInteger(c) && c > 0))].sort((a, b) => a - b);
    if (cleaned.length) {
      out[String(tool).trim().toLowerCase()] = cleaned;
    }
  }
  return out;
}

export function distribution_methods(): string[] {
  return [...load_grammar().algorithm_classes.distribution.methods];
}

export function uniform_rotation_methods(): string[] {
  return [...(((load_grammar().algorithm_classes || {}).uniform_rotation || {}).methods || [])];
}

export function vk_derivation_grammar(): Record<string, any> {
  const section = load_grammar().vk_derivation || {};
  return typeof section === "object" && section !== null && !Array.isArray(section) ? { ...section } : {};
}

export function deterministic_mapping_methods(): string[] {
  return [...(((load_grammar().algorithm_classes || {}).deterministic_mapping || {}).methods || [])];
}

export function count_field_words(): string[] {
  return [...load_grammar().count_field_words.words];
}

export function rejection_hints(): string[] {
  return [...load_grammar().rejection_semantics.hints];
}

export function dns_record_types(): string[] {
  return [...load_grammar().dns_record_types.words];
}

export function persistence_patterns(): string[] {
  const chans = load_grammar().persistence_channels || {};
  const out: string[] = [];
  for (const [key, ch] of Object.entries<any>(chans)) {
    if (key.startsWith("_") || typeof ch !== "object" || ch === null) continue;
    out.push(...(ch.patterns || []).map((p: any) => String(p)));
  }
  return out;
}

export function l23_write_patterns(): string[] {
  return [...((load_grammar().bed_l23_write_forms || {}).patterns || [])];
}

export function occupancy_semantics(): [string[], string[]] {
  const oc = load_grammar().occupancy_semantics || {};
  return [[...(oc.patterns || [])], [...(oc.negations || [])]];
}

export function forbidden_mechanism_intents(): Array<[string, string[]]> {
  const fm = load_grammar().forbidden_mechanism_intents || {};
  return (fm.families || []).map((f: any) => [String(f.family || ""), [...(f.patterns || [])]]);
}

export function reference_closures(): Array<Record<string, any>> {
  return [...(load_grammar().reference_closures || [])];
}

export function anchoring_chains(): Array<Record<string, any>> {
  return [...(load_grammar().anchoring_chains || [])];
}

export function co_required_params(): Array<Record<string, any>> {
  return [...((load_grammar().co_required_params || {}).rules || [])];
}

export function missing_co_required(rules: Array<Record<string, any>>, lines: string[]): Array<Record<string, any>> {
  const out: Array<Record<string, any>> = [];
  for (const rule of rules || []) {
    const reqPat = String(rule.requires_pattern || "");
    if (!reqPat) continue;
    let trig: RegExp;
    let req: RegExp;
    try {
      trig = stmt_re(String(rule.trigger_statement || ""));
      req = new RegExp(reqPat, "i");
    } catch {
      continue;
    }
    const cond = rule.condition || {};
    const values = new Set((cond.values || []).map((v: any) => String(v).toLowerCase()));
    const param = String(cond.param || "");
    for (const line of lines) {
      const m = trig.exec(line);
      if (!m) continue;
      const gd = m.groups || {};
      const val = String(gd[param] || gd.name || "").toLowerCase();
      if (values.size && !values.has(val)) continue;
      if (!req.test(line)) {
        out.push({ rule_id: String(rule.id || ""), line, provenance: rule.provenance || {} });
      }
    }
  }
  return out;
}

function _leadingVerb(line: string): string {
  const toks = (line || "").trim().split(/\s+/);
  return toks.length ? toks[0].trim().replace(/^["']+|["']+$/g, "").toLowerCase() : "";
}

function _normName(name: string, how: string): string {
  if (how === "dns_name") {
    return name.replace(/\.+$/, "").toLowerCase();
  }
  return name;
}

export function dangling_references(closure: Record<string, any>, lines: string[]): string[] {
  const skip = new Set(closure.skip_leading_verbs || []);
  const defRes = (closure.defines || []).map((sid: string) => stmt_re(sid));
  const refRes = (closure.references || []).map((sid: string) => stmt_re(sid));
  const norm = closure.normalize || "";
  const defined = new Set<string>();
  const referenced: string[] = [];
  for (const line of lines) {
    if (skip.size && skip.has(_leadingVerb(line))) continue;
    let matched = false;
    for (const r of defRes) {
      const m = r.exec(line);
      if (m) {
        defined.add(_normName((m.groups || {}).name, norm));
        matched = true;
        break;
      }
    }
    if (matched) continue;
    for (const r of refRes) {
      const m = r.exec(line);
      if (m) {
        referenced.push((m.groups || {}).name);
        break;
      }
    }
  }
  const out: string[] = [];
  const seen = new Set<string>();
  for (const name of referenced) {
    const n = _normName(name, norm);
    if (!defined.has(n) && !seen.has(n)) {
      seen.add(n);
      out.push(name);
    }
  }
  return out;
}

export function unanchored_bound_objects(
  chain: Record<string, any>,
  lines: string[],
  line_rows: number[],
  first_cp_row: number | null,
  expects: string[],
  value_pattern: (v: string) => string
): string[] {
  if (first_cp_row === null) {
    return [];
  }
  const bindRe = stmt_re(chain.bind);
  const memberRe = stmt_re(chain.member_edge);
  const resolveRe = stmt_re(chain.resolve);
  const members: Record<string, string[]> = {};
  const values: Record<string, string> = {};
  const firstBindRow: Record<string, number> = {};
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const rowIdx = line_rows[i];
    let m = memberRe.exec(line);
    if (m) {
      (members[(m.groups || {}).from] = members[(m.groups || {}).from] || []).push((m.groups || {}).to);
      continue;
    }
    m = resolveRe.exec(line);
    if (m) {
      const gd = m.groups || {};
      if (!(gd.name in values)) values[gd.name] = gd.value;
      continue;
    }
    m = bindRe.exec(line);
    if (m) {
      const name = (m.groups || {}).name;
      if (!(name in firstBindRow)) {
        firstBindRow[name] = rowIdx;
      }
    }
  }
  const unanchored: string[] = [];
  for (const obj of Object.keys(firstBindRow)) {
    const bindRow = firstBindRow[obj];
    if (bindRow <= first_cp_row) continue;
    const vals = (members[obj] || []).filter((mm) => mm in values).map((mm) => values[mm]);
    if (!vals.length) continue;
    const anchored = vals.some((v) => expects.some((expect) => new RegExp(value_pattern(v)).test(expect)));
    if (!anchored) {
      unanchored.push(obj);
    }
  }
  return unanchored;
}
