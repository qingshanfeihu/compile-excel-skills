import * as _dg from "./domain_grammar";

export const MUTATING_VERBS: string[] = _dg.verbs("mutating");
const _LEADING_OPS = MUTATING_VERBS.concat(_dg.verbs("observe_leading"));
const _BEHAVIOR_PROBES_RE = new RegExp("\\b(" + _dg.verbs("behavior_probes").join("|") + ")\\b");
const _CONFIG_QUERY_RE = new RegExp("\\b(" + _dg.verbs("config_query_probes").join("|") + ")\\b");
const _RUNTIME_STATE_RE = new RegExp("\\b(" + _dg.verbs("runtime_state_words").join("|") + ")\\b");

export function object_tokens(text: string): string[] {
  const toks = (text || "").trim().split(/\s+/).filter(Boolean);
  const objs: string[] = [];
  let leading = true;
  for (const t of toks) {
    if (t === "|" || t === "||" || t === "&&" || t === ";") {
      break;
    }
    const tl = t.trim().replace(/^["']+|["']+$/g, "").toLowerCase();
    if (!/^[a-z][a-z0-9_-]*$/.test(tl)) {
      leading = false;
      continue;
    }
    if (leading && _LEADING_OPS.includes(tl)) {
      continue;
    }
    leading = false;
    objs.push(tl);
  }
  return objs;
}

export function observe_kind(cmd: string): string {
  const c = (cmd || "").toLowerCase();
  if (!c.trim()) {
    return "";
  }
  if (_BEHAVIOR_PROBES_RE.test(c)) {
    return "behavior";
  }
  if (_CONFIG_QUERY_RE.test(c)) {
    if (_RUNTIME_STATE_RE.test(c)) {
      return "behavior";
    }
    return "config_query";
  }
  return "";
}

export function is_observe_command(cmd: string): boolean {
  return Boolean(observe_kind(cmd));
}

export function config_existence_check(
  observe_cmd: string,
  expect: string,
  config_context: string[],
  method = "found"
): [boolean, string] {
  const qset = new Set(object_tokens(expect));
  if (qset.size === 0 || observe_kind(observe_cmd) !== "config_query") {
    return [false, ""];
  }
  let matched = "";
  for (const c of config_context) {
    const tokens = new Set(object_tokens(c));
    let all = true;
    for (const q of qset) {
      if (!tokens.has(q)) {
        all = false;
        break;
      }
    }
    if (all) {
      matched = c;
      break;
    }
  }
  if (!matched) {
    return [false, ""];
  }
  if ((method || "found").trim().toLowerCase() !== "found") {
    return [false, matched];
  }
  return [true, matched];
}
