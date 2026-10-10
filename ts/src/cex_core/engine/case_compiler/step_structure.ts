// 生成：tools/extract_engine.py ← InfoTest main/case_compiler/step_structure.py（sha256 c3b6fc9549b1cc6d）。不在这里手改。
const logger = console;

export const STEP_STRUCTURE_KEY = "step_structure";
export const ENGINE_SLOTS_KEY = "engine_slots";
export const ADAPTED_STEPS_KEY = "adapted_steps";
export const ADAPTED_STEP_KEYS = new Set(["n", "text", "basis"]);
export const STRUCTURE_OBJECT_ROLES = ["created", "configured", "observed", "deleted", "referenced"] as const;
export const STRUCTURE_CONDITION_KINDS = ["algorithm", "type", "attribute", "count", "order", "weight", "other"] as const;
export const STRUCTURE_ENTRY_KEYS = new Set(["n", "objects", "operations", "stated_conditions", "free_slots"]);
export const ENGINE_SLOT_SOURCE = "engine_rule";
export const SAMPLING_DISCLOSURE_SLOT = "sampling_disclosure";
export const EFFECTIVE_WEIGHTS_SLOT = "effective_weights";
export const SLOT_REASON_CODES = ["ok", "pairing_ambiguous"] as const;
export const STEP_ORDER_UNAVAILABLE_BASIS = "engine_step_order_unavailable";
const _CONCRETIZATION_REF_RE = /^concretizations\[(\d{1,6})\]$/;
const _SLOT_REF_RE = new RegExp(`^${ENGINE_SLOTS_KEY}\\[(\\d{1,6})\\]$`);
const _VALUE_SPLIT_RE = /[\s,，、:：/]+/;
export const MAX_OBJECT_COUNT = 1000;
export const MAX_KIND_CHARS = 200;
export const MAX_VIOLATION_PAYLOAD_CHARS = 20000;
export const MAX_VALUE_CHARS = 400;
export const MAX_CONDITION_TEXT_CHARS = 2000;
export const MAX_COUNT_DIGITS = 9;
export const MAX_STRUCTURE_ENTRIES = 200;
export const MAX_ENTRY_ARRAY_ITEMS = 200;
const MAX_KNOWN_HEADS_SHOWN = 12;
const MAX_TRUNCATED_LOCI_SHOWN = 12;
const _OBJECT_KIND_CACHE = new Map<string, Set<string>>();
const MAX_ADAPTED_STEP_CHARS = 4000;
const MAX_ADAPTED_BASIS_CHARS = 2000;

function _isMapping(value: any): value is Record<string, any> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function _typeName(value: any): string {
  if (value === null) return "null";
  if (Array.isArray(value)) return "array";
  return typeof value;
}

class _SequenceMatcher {
  a: string[];
  b: string[];
  constructor(a: string[], b: string[]) {
    this.a = a;
    this.b = b;
  }

  get_opcodes(): [string, number, number, number, number][] {
    const { a, b } = this;
    const n = a.length;
    const m = b.length;
    const dp: number[][] = Array.from({ length: n + 1 }, () => new Array<number>(m + 1).fill(0));
    for (let i = n - 1; i >= 0; i--) {
      for (let j = m - 1; j >= 0; j--) {
        dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
      }
    }
    const opcodes: [string, number, number, number, number][] = [];
    let i = 0;
    let j = 0;
    while (i < n && j < m) {
      if (a[i] === b[j]) {
        const i0 = i;
        const j0 = j;
        while (i < n && j < m && a[i] === b[j]) {
          i++;
          j++;
        }
        opcodes.push(["equal", i0, i, j0, j]);
      } else if (dp[i + 1][j] >= dp[i][j + 1]) {
        opcodes.push(["delete", i, i + 1, j, j]);
        i++;
      } else {
        opcodes.push(["insert", i, i, j, j + 1]);
        j++;
      }
    }
    while (i < n) {
      opcodes.push(["delete", i, i + 1, j, j]);
      i++;
    }
    while (j < m) {
      opcodes.push(["insert", i, i, j, j + 1]);
      j++;
    }
    const merged: [string, number, number, number, number][] = [];
    for (const op of opcodes) {
      const last = merged[merged.length - 1];
      if (last && last[0] !== "equal" && op[0] !== "equal" && last[2] === op[1] && last[4] === op[3]) {
        last[2] = op[2];
        last[4] = op[4];
        if (op[0] === "insert" || last[0] === "insert") {
          if (last[0] !== op[0]) last[0] = "replace";
        }
      } else {
        merged.push([...op] as [string, number, number, number, number]);
      }
    }
    for (const op of merged) {
      if (op[0] !== "equal" && op[2] - op[1] > 0 && op[4] - op[3] > 0) {
        op[0] = "replace";
      } else if (op[0] !== "equal" && op[4] - op[3] === 0) {
        op[0] = "delete";
      } else if (op[0] !== "equal" && op[2] - op[1] === 0) {
        op[0] = "insert";
      }
    }
    return merged;
  }

  ratio(): number {
    const { a, b } = this;
    const n = a.length;
    const m = b.length;
    if (!n && !m) return 1.0;
    const dp: number[][] = Array.from({ length: n + 1 }, () => new Array<number>(m + 1).fill(0));
    for (let i = n - 1; i >= 0; i--) {
      for (let j = m - 1; j >= 0; j--) {
        dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
      }
    }
    return (2.0 * dp[0][0]) / (n + m);
  }
}

function _norm_head_tokens(command: any): string[] {
  const { norm_command_tokens } = require("./vendor_stdlib");
  return [...norm_command_tokens(String(command ?? ""))];
}

function _verbatim_forms(value: any): string[] {
  const { verbatim_candidates } = require("./mindmap_contract_projector");
  return verbatim_candidates(String(value ?? ""));
}

function _display_form(value: any, limit: number = MAX_CONDITION_TEXT_CHARS): string {
  const forms = _verbatim_forms(value);
  const form = forms.length ? forms[0] : "";
  return limit && form.length > limit ? form.slice(0, limit) : form;
}

function _grammar(): Record<string, any> | null {
  try {
    const { load_grammar } = require("./domain_grammar");
    const grammar = load_grammar();
    return _isMapping(grammar) ? grammar : null;
  } catch (exc) {
    logger.warn?.("domain grammar unavailable for step structure", exc);
    return null;
  }
}

function _grammar_verbs(classIds: string[]): Set<string> {
  const grammar = _grammar();
  const classes = (grammar ?? {})["verb_classes"] || {};
  const words = new Set<string>();
  for (const classId of classIds) {
    const spec = _isMapping(classes) ? classes[classId] : null;
    if (_isMapping(spec)) {
      for (const verb of spec["verbs"] || []) {
        const word = String(verb).trim().toLowerCase();
        if (word) words.add(word);
      }
    }
  }
  return words;
}

function _leading_operator_words(): Set<string> {
  return _grammar_verbs(["observe_leading", "mutating"]);
}

function _probe_verbs(): Set<string> {
  return _grammar_verbs(["behavior_probes"]);
}

export function object_kind_closed_set(): Set<string> | null {
  const { load_vendor_stdlib } = require("./vendor_stdlib");
  const inventory = load_vendor_stdlib();
  if (!_isMapping(inventory)) {
    return null;
  }
  const headers = inventory["headers"];
  if (!_isMapping(headers) || !Object.keys(headers).length) {
    return null;
  }
  const operators = _leading_operator_words();
  if (!operators.size) {
    return null;
  }
  const cacheKey = `${String(inventory["version"] || "")}:${String(inventory["device_os_build"] || "")}:${Object.keys(headers).length}:${operators.size}`;
  const cached = _OBJECT_KIND_CACHE.get(cacheKey);
  if (cached !== undefined) {
    return cached;
  }
  const kinds = new Set<string>();
  for (const entry of Object.values(headers)) {
    if (!_isMapping(entry)) continue;
    const src = String(entry["src"] || "");
    const pathParts = src.split(":");
    const path = src.split(":").length >= 3 ? pathParts.slice(2).join(":") : "";
    let segments = path.split("/").filter((part) => part);
    if (segments.length && segments[0] === "global") {
      segments = segments.slice(1);
    }
    while (segments.length && operators.has(segments[0].toLowerCase())) {
      segments = segments.slice(1);
    }
    if (segments.length >= 2) {
      kinds.add(segments.slice(0, -1).join("/"));
    }
  }
  if (!kinds.size) {
    return null;
  }
  _OBJECT_KIND_CACHE.set(cacheKey, kinds);
  return kinds;
}

export function clear_object_kind_cache(): void {
  _OBJECT_KIND_CACHE.clear();
  _COMMAND_ROLE_CACHE.clear();
  _nearKindsCache.clear();
}

export const ROLE_COMMAND_CLASSES: Record<string, Set<string>> = {
  created: new Set(["write"]),
  configured: new Set(["write"]),
  observed: new Set(["observation"]),
  deleted: new Set(["teardown"]),
  referenced: new Set(["write", "observation", "teardown"]),
};
const _COMMAND_ROLE_CACHE = new Map<string, CommandRoleAtlas>();

export class CommandRoleAtlas {
  _forward: Set<string>;
  _inverse_of: Map<string, Set<string>>;
  _operators: Set<string>;
  _observe: Set<string>;
  _max_head: number;

  constructor(forward: Set<string>, inverse_of: Map<string, Set<string>>, operators: Set<string>, observe: Set<string>) {
    const { _MAX_HEAD_TOKENS } = require("./vendor_stdlib");
    this._forward = forward;
    this._inverse_of = new Map(inverse_of);
    this._operators = operators;
    this._observe = observe;
    this._max_head = Number(_MAX_HEAD_TOKENS);
  }

  get teardown_operators(): Set<string> {
    return this._operators;
  }

  get observe_verbs(): Set<string> {
    return this._observe;
  }

  _known_head_length(tokens: string[]): number {
    const limit = Math.min(tokens.length, this._max_head);
    for (let size = limit; size > 0; size--) {
      const prefix = tokens.slice(0, size).join("\u0001");
      if (this._forward.has(prefix) || this._inverse_of.has(prefix)) {
        return size;
      }
    }
    return 0;
  }

  command_class(tokens: string[]): string {
    if (!tokens.length) {
      return "";
    }
    const lead = String(tokens[0]).toLowerCase();
    if (this._operators.has(lead)) {
      return "teardown";
    }
    const size = this._known_head_length(tokens);
    if (size && this._inverse_of.has(tokens.slice(0, size).join("\u0001"))) {
      return "teardown";
    }
    if (this._observe.has(lead)) {
      return "observation";
    }
    return "write";
  }

  undone_heads(tokens: string[]): string[][] {
    const size = this._known_head_length(tokens);
    if (!size) {
      return [];
    }
    const inverse = this._inverse_of.get(tokens.slice(0, size).join("\u0001"));
    return inverse ? [...inverse].map((key) => key.split("\u0001")) : [];
  }

  instance_name(tokens: string[], segments: string[], offset: number): string {
    let size = this._known_head_length(tokens);
    if (!size && tokens.length && this._operators.has(String(tokens[0]).toLowerCase())) {
      const inner = this._known_head_length(tokens.slice(1));
      size = inner ? inner + 1 : 0;
    }
    if (!size) {
      size = offset >= 0 ? offset + segments.length : 0;
    }
    if (size > 0 && size < tokens.length) {
      return String(tokens[size]);
    }
    return "";
  }
}

export function command_role_atlas(): CommandRoleAtlas | null {
  let atlas: any;
  let fingerprint: string;
  try {
    const { configured_device_os_build, device_os_build_suffix } = require("./vendor_stdlib");
    const { load_command_teardown_atlas, verify_atlas_source_identity } = require("../scripts/gen_command_teardown_atlas");
    let build = String(configured_device_os_build() || "").trim();
    build = device_os_build_suffix(build) || build;
    if (!build) {
      throw new Error("device build is unavailable for the command role atlas");
    }
    atlas = load_command_teardown_atlas({ expected_build: build });
    verify_atlas_source_identity(atlas);
    const identity = _isMapping(atlas) ? atlas["identity"] : null;
    fingerprint = String((_isMapping(identity) ? identity["sha256"] : "") || "").trim();
    if (!fingerprint) {
      throw new Error("the command role atlas carries no source identity");
    }
  } catch (exc) {
    logger.warn?.("command teardown atlas unavailable for step structure", exc);
    return null;
  }
  const commands = _isMapping(atlas) ? atlas["commands"] : null;
  if (!_isMapping(commands) || !Object.keys(commands).length) {
    return null;
  }
  const observe = _grammar_verbs(["observe_leading"]);
  if (!observe.size) {
    return null;
  }
  const cacheKey = `${fingerprint}:${[...observe].sort().join(",")}`;
  const cached = _COMMAND_ROLE_CACHE.get(cacheKey);
  if (cached !== undefined) {
    return cached;
  }
  const policy = _isMapping(atlas["policy"]) ? atlas["policy"] : {};
  const selection = policy["configuration_write_selection"];
  const excluded = new Set<string>(((selection || {})["excluded_roots"] || []).map((root: any) => String(root).trim().toLowerCase()).filter((root: string) => root));
  const forward = new Set<string>();
  const inverseOf = new Map<string, Set<string>>();
  const inverseLeading = new Set<string>();
  for (const [head, record] of Object.entries(commands)) {
    const tokens = _norm_head_tokens(head);
    if (!tokens.length) continue;
    forward.add(tokens.join("\u0001"));
    const teardown = _isMapping(record) ? record["teardown"] : null;
    for (const form of (_isMapping(teardown) ? teardown["suggested_inverses"] : null) || []) {
      const inverse = _norm_head_tokens(form);
      if (!inverse.length) continue;
      const key = inverse.join("\u0001");
      if (!inverseOf.has(key)) inverseOf.set(key, new Set());
      inverseOf.get(key)!.add(tokens.join("\u0001"));
      inverseLeading.add(inverse[0]);
    }
  }
  const operators = new Set([...excluded].filter((root) => inverseLeading.has(root)));
  if (!operators.size || !forward.size) {
    return null;
  }
  const built = new CommandRoleAtlas(forward, inverseOf, operators, observe);
  _COMMAND_ROLE_CACHE.set(cacheKey, built);
  return built;
}

const _LEGAL_FORM_ENTRY = 'step_structure: [{"n": "<the step number, byte-for-byte from steps[].n>", "objects": [{"kind": "<command-tree object path>", "role": "created|configured|observed|deleted|referenced", "count": <int or null>}], "operations": [{"head": "<a command head already in this case\'s command_check>", "ref": "step:<n>"}], "stated_conditions": [{"text": "<verbatim substring of steps[n].text>", "kind": "algorithm|type|attribute|count|order|weight|other", "value": "<the literal the author wrote>"}], "free_slots": [{"slot": "<name>", "ref": "concretizations[<i>]"}]}]';
export const LEGAL_FORM_ENTRY = _LEGAL_FORM_ENTRY;
const _LEGAL_FORM_CONDITION = '{"text": "<a substring of the adapted step text (of steps[n].text when the case carries no adaptation)", "kind": "algorithm|type|attribute|count|order|weight|other", "value": "<the literal the adaptation states, e.g. rr, 3, or the bucket weights 3 2 1>", "author_text": "<the span of the author\'s original text this condition corresponds to; required when the step was adapted, may be omitted when the step is unchanged; the engine grounds it against the sealed steps[n].text with whitespace runs normalized>"}';
const _LEGAL_FORM_OPERATION = '{"head": "<one of the command heads this case already carries in command_check[].command>", "ref": "step:<n>"}';
const _LEGAL_FORM_OBJECT = `{"kind": "<a command-tree object path such as the path segments of the head that creates or configures it>", "role": "created|configured|observed|deleted|referenced", "count": <int or null, at most ${MAX_OBJECT_COUNT}>}`;
const _LEGAL_FORM_SLOT = '{"slot": "<name>", "ref": "concretizations[<i>]"} — the ref must resolve to an entry that already exists in this case; the value lives there once and is never duplicated into the slot.';
export const VIOLATION_CODES = ["step_structure_missing", "step_structure_condition_not_verbatim", "step_structure_operation_head_unknown", "step_structure_object_kind_unknown", "step_structure_slot_ref_unresolved", "step_structure_count_out_of_range", "step_structure_adaptation_invalid"] as const;

function _violation(code: string, locus: string, detail: string, legal_form: string): Record<string, string> {
  return { code, locus, detail, legal_form };
}

function _locus_list(loci: string[]): string {
  const shown = loci.slice(0, MAX_TRUNCATED_LOCI_SHOWN);
  const rest = loci.length - shown.length;
  return shown.join(", ") + (rest ? `, and ${rest} more` : "");
}

function _budget_cut_note(kind: string, loci: string[]): string {
  return `${loci.length} further ${kind}s are not rendered; the rejection payload reached its budget. They are at: ${_locus_list(loci)}. Repair the ones above and submit again; the rest are reported then.`;
}

function _budget_stop_note(kind: string, opts: { rendered: number; stopped_at: string; unjudged: string[] }): string {
  return `${opts.rendered} ${kind}s are rendered above, and the rejection payload reached its budget at ${opts.stopped_at}: judging stopped there. These ${opts.unjudged.length} loci are not covered by this payload: ${_locus_list(opts.unjudged)}. Repair the ones above and submit again; whatever is left is judged and reported then.`;
}

export function budget_violations(violations: Record<string, string>[], opts: { max_chars?: number } = {}): Record<string, string>[] {
  const maxChars = opts.max_chars ?? MAX_VIOLATION_PAYLOAD_CHARS;
  const emittedCodes = new Set<string>();
  const out: Record<string, string>[] = [];
  const cut = new Map<string, string[]>();
  const noticeSlot = new Map<string, number>();
  let spent = 0;
  for (const item of violations) {
    const row: Record<string, string> = Object.fromEntries(Object.entries({ ...item }).map(([k, v]) => [String(k), String(v)]));
    const code = row["code"] ?? "";
    const legalForm = row["legal_form"] ?? "";
    if (emittedCodes.has(code)) {
      row["legal_form"] = `see the first ${code} violation above`;
    }
    const size = Object.entries(row).reduce((sum, [key, value]) => sum + key.length + value.length, 0);
    if (spent + size > maxChars && out.length) {
      if (!cut.has(code)) {
        noticeSlot.set(code, out.length);
        out.push({ code, locus: row["locus"] ?? "", detail: "", legal_form: emittedCodes.has(code) ? `see the first ${code} violation above` : legalForm });
        emittedCodes.add(code);
      }
      if (!cut.has(code)) cut.set(code, []);
      cut.get(code)!.push(row["locus"] ?? "");
      continue;
    }
    emittedCodes.add(code);
    spent += size;
    out.push(row);
  }
  for (const [code, loci] of cut) {
    out[noticeSlot.get(code)!]["detail"] = _budget_cut_note(`${code} violation`, loci);
  }
  return out;
}

function _step_index(caseData: Record<string, any>): Record<string, string> {
  const out: Record<string, string> = {};
  for (const item of caseData["steps"] || []) {
    if (!_isMapping(item)) continue;
    const number = String(item["n"] || "").trim();
    if (number) {
      out[number] = String(item["text"] || "");
    }
  }
  return out;
}

const _IP_LITERAL_RE = /(?<![0-9A-Za-z:.])((?:\d{1,3}\.){3}\d{1,3}|(?=[0-9A-Fa-f]*:)[0-9A-Fa-f:]{2,39})(%[\w.-]+)?(\/\d{1,3})?(?![0-9A-Za-z:.])/g;
const _IP_LITERAL_FULL_RE = /^(?:(?:\d{1,3}\.){3}\d{1,3}|(?=[0-9A-Fa-f]*:)[0-9A-Fa-f:]{2,39})(%[\w.-]+)?(\/\d{1,3})?$/;

function _parseIp(text: string): { version: number; normalized: string } | null {
  const v4 = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/.exec(text);
  if (v4) {
    const parts = v4.slice(1).map(Number);
    if (parts.some((part) => part > 255)) return null;
    return { version: 4, normalized: parts.join(".") };
  }
  if (!text.includes(":")) return null;
  if (!/^[0-9A-Fa-f:]+$/.test(text)) return null;
  const hasDouble = text.includes("::");
  const groups = text.split(":").filter((g, i, arr) => !(hasDouble && g === "" && i > 0 && arr[i - 1] === ""));
  const pieces = text.split("::");
  if (pieces.length > 2) return null;
  const left = pieces[0] ? pieces[0].split(":") : [];
  const right = pieces.length === 2 && pieces[1] ? pieces[1].split(":") : [];
  if (pieces.length === 1 && left.length !== 8) return null;
  if (pieces.length === 2 && left.length + right.length > 8) return null;
  const all = [...left, ...right];
  if (all.some((g) => !/^[0-9A-Fa-f]{1,4}$/.test(g))) return null;
  const missing = 8 - left.length - right.length;
  const expanded = pieces.length === 2 ? [...left, ...new Array(missing).fill("0"), ...right] : left;
  const normalized = expanded.map((g) => parseInt(g || "0", 16).toString(16)).join(":");
  return { version: 6, normalized };
}

function _ip_address(token: any): { version: number; normalized: string } | null {
  const text = String(token ?? "").trim();
  if (!_IP_LITERAL_FULL_RE.test(text)) {
    return null;
  }
  const core = text.replace(/(%[\w.-]+)?(\/\d{1,3})?$/, "");
  return _parseIp(core);
}

function _ip_key(token: any): string | null {
  const address = _ip_address(token);
  return address === null ? null : address.normalized;
}

function _ip_literals(text: any): Set<string> {
  const out = new Set<string>();
  const re = new RegExp(_IP_LITERAL_RE.source, "g");
  let match: RegExpExecArray | null;
  while ((match = re.exec(String(text ?? ""))) !== null) {
    const key = _ip_key(match[0]);
    if (key) out.add(key);
  }
  return out;
}

function _adaptation_tokens(text: string): string[] {
  const out: string[] = [];
  let pos = 0;
  const re = new RegExp(_IP_LITERAL_RE.source, "g");
  let match: RegExpExecArray | null;
  while ((match = re.exec(text)) !== null) {
    if (_ip_key(match[0]) === null) {
      continue;
    }
    out.push(...text.slice(pos, match.index).split(""));
    out.push(match[0]);
    pos = match.index + match[0].length;
  }
  out.push(...text.slice(pos).split(""));
  return out;
}

function _adaptation_literal_map(authored: string, adapted: string): [Map<string, Set<string>>, boolean] {
  const aTokens = _adaptation_tokens(authored);
  const bTokens = _adaptation_tokens(adapted);
  const matcher = new _SequenceMatcher(aTokens, bTokens);
  const mapping = new Map<string, Set<string>>();
  let aligned = true;
  for (const [tag, i1, i2, j1, j2] of matcher.get_opcodes()) {
    if (tag === "equal") {
      for (const token of aTokens.slice(i1, i2)) {
        const key = _ip_key(token);
        if (key) {
          if (!mapping.has(key)) mapping.set(key, new Set());
          mapping.get(key)!.add(key);
        }
      }
    } else if (tag === "replace") {
      const gone = aTokens.slice(i1, i2).map(_ip_key).filter((k): k is string => k !== null);
      const came = bTokens.slice(j1, j2).map(_ip_key).filter((k): k is string => k !== null);
      if (!gone.length) continue;
      gone.forEach((old, index) => {
        if (index < came.length) {
          if (!mapping.has(old)) mapping.set(old, new Set());
          mapping.get(old)!.add(came[index]);
        }
      });
      if (gone.length > came.length) {
        aligned = false;
      }
    } else if (tag === "delete") {
      if (aTokens.slice(i1, i2).some((t) => _ip_key(t))) {
        aligned = false;
      }
    }
  }
  return [mapping, aligned];
}

export const SUBSTITUTION_BASIS_UNREACHABLE_ADDRESS = "unreachable_address";
export const SUBSTITUTION_BASIS_BED_ROLE = "bed_role";
const _CONDITION_ATOM_RE = /[A-Za-z0-9_][A-Za-z0-9_.:%-]*/g;

function _condition_atoms(text: any): string[] {
  const out: string[] = [];
  const re = new RegExp(_CONDITION_ATOM_RE.source, "g");
  let match: RegExpExecArray | null;
  while ((match = re.exec(String(text ?? ""))) !== null) {
    out.push(match[0]);
  }
  return out;
}

function _atom_in_text(atom: string, text: any): boolean {
  if (!atom) {
    return false;
  }
  const escaped = atom.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const pattern = new RegExp(`(?<![A-Za-z0-9_])${escaped}(?![A-Za-z0-9_])`, "i");
  return pattern.test(String(text ?? ""));
}

const _ORDINAL_MARKER_RE = /^\d{1,3}\.(?=.)/;

function _atom_is_head_token(atom: string, token: string): boolean {
  if (atom === token) {
    return true;
  }
  const stripped = atom.replace(_ORDINAL_MARKER_RE, "");
  return stripped !== atom && stripped === token;
}

function _argument_atoms(text: any, groundedHeads: [string, string[]][]): Set<string> {
  const atoms = _condition_atoms(text).map((atom) => atom.toLowerCase());
  const out = new Set<string>();
  for (const [, head] of groundedHeads) {
    const tokens = head.map((token) => String(token).toLowerCase());
    if (!tokens.length || tokens.length > atoms.length) {
      continue;
    }
    const width = tokens.length;
    for (let start = 0; start + width <= atoms.length; start++) {
      const window = atoms.slice(start, start + width);
      if (!_atom_is_head_token(window[0], tokens[0])) {
        continue;
      }
      if (JSON.stringify(window.slice(1)) === JSON.stringify(tokens.slice(1))) {
        atoms.slice(start + width).forEach((atom) => out.add(atom));
      }
    }
  }
  return out;
}

function _atom_replacements(before: any, after: any): [string, string][] {
  const a = _condition_atoms(before).map((atom) => atom.toLowerCase());
  const b = _condition_atoms(after).map((atom) => atom.toLowerCase());
  const out: [string, string][] = [];
  const matcher = new _SequenceMatcher(a, b);
  for (const [tag, i1, i2, j1, j2] of matcher.get_opcodes()) {
    if (tag === "replace" && i2 - i1 === j2 - j1) {
      for (let k = 0; k < i2 - i1; k++) {
        out.push([a[i1 + k], b[j1 + k]]);
      }
    }
  }
  return out;
}

export function adaptation_value_substitutions(opts: { author_text: any; text: any; value: any; sealed_step: any; adapted_step: any; grounded_heads: [string, string[]][] }): [string, string][] {
  const valueAtoms = new Set(stated_value_tokens(opts.value).filter((token) => token).map((token) => token.toLowerCase()));
  if (!valueAtoms.size) {
    return [];
  }
  const sealedArgs = _argument_atoms(opts.sealed_step, opts.grounded_heads);
  const adaptedArgs = _argument_atoms(opts.adapted_step, opts.grounded_heads);
  if (!sealedArgs.size || !adaptedArgs.size) {
    return [];
  }
  const out: [string, string][] = [];
  for (const [oldAtom, newAtom] of _atom_replacements(opts.author_text, opts.text)) {
    if (!valueAtoms.has(newAtom) || valueAtoms.has(oldAtom)) {
      continue;
    }
    if (_atom_in_text(oldAtom, opts.adapted_step)) {
      continue;
    }
    if (!sealedArgs.has(oldAtom) || !adaptedArgs.has(newAtom)) {
      continue;
    }
    if (!out.some(([o, n]) => o === oldAtom && n === newAtom)) {
      out.push([oldAtom, newAtom]);
    }
  }
  return out;
}

function _bed_facts(): any {
  const { require_env_facts } = require("../ist_core/tools/_shared/env_facts");
  return require_env_facts();
}

function _address_unreachable_on_bed(facts: any, literal: string): boolean | null {
  if (_ip_key(literal) === null) {
    return null;
  }
  try {
    return Boolean(facts.unreachable_ipv4s(literal) || facts.unreachable_ipv6s(literal));
  } catch (exc) {
    logger.warn?.("bed reachability unavailable for %r", literal, exc);
    return null;
  }
}

function _address_family(literal: any): number | null {
  const address = _ip_address(literal);
  return address === null ? null : address.version;
}

export function recomputable_substitution_basis(old_atom: string, new_atom: string): string | null {
  const facts = _bed_facts();
  const oldUnreachable = _address_unreachable_on_bed(facts, old_atom);
  const newUnreachable = _address_unreachable_on_bed(facts, new_atom);
  if (oldUnreachable === true && newUnreachable === false && _address_family(old_atom) === _address_family(new_atom)) {
    return SUBSTITUTION_BASIS_UNREACHABLE_ADDRESS;
  }
  if (_ip_key(old_atom) !== null) {
    return null;
  }
  if (newUnreachable === false) {
    return SUBSTITUTION_BASIS_BED_ROLE;
  }
  const names = new Set((facts.devices as any[]).filter((device) => _isMapping(device)).map((device) => String(device["name"] || "").trim().toLowerCase()));
  names.delete("");
  if (names.has(String(new_atom || "").trim().toLowerCase())) {
    return SUBSTITUTION_BASIS_BED_ROLE;
  }
  return null;
}

function _normalized_step_text(text: any): string {
  return String(text ?? "").replace(/ /g, " ").replace(/\s+/g, " ").trim();
}

export function step_is_adapted(authored_text: any, adapted_text: any): boolean {
  return _normalized_step_text(authored_text) !== _normalized_step_text(adapted_text);
}

export function adapted_step_texts(caseData: Record<string, any>): Record<string, string> | null {
  const raw = caseData[ADAPTED_STEPS_KEY];
  if (!Array.isArray(raw)) {
    return null;
  }
  const out: Record<string, string> = {};
  for (const item of raw) {
    if (!_isMapping(item)) {
      return null;
    }
    const number = String(item["n"] || "").trim();
    const text = String(item["text"] || "");
    if (!number || !text.trim()) {
      return null;
    }
    out[number] = text;
  }
  return Object.keys(out).length ? out : null;
}

export function case_has_adaptation(caseData: Record<string, any>): boolean {
  const adapted = adapted_step_texts(caseData);
  if (adapted === null) {
    return false;
  }
  const steps = _step_index(caseData);
  const adaptedKeys = new Set(Object.keys(adapted));
  const stepKeys = new Set(Object.keys(steps));
  if (adaptedKeys.size !== stepKeys.size || ![...adaptedKeys].every((k) => stepKeys.has(k))) {
    return true;
  }
  return Object.entries(steps).some(([number, text]) => step_is_adapted(text, adapted[number]));
}

const _LEGAL_FORM_ADAPTED = '[{"n": "<step number, same set and order as steps[]>", "text": "<the adapted step text>", "basis": "<why this adaptation preserves the authored scenario; may be empty when a step needed no change>"}] — one entry per authored step, same order; steps[] stays sealed and the author\'s original text stays in it.';

export function adapted_steps_violations(caseData: Record<string, any>, opts: { autoid: string; index: number }): Record<string, string>[] {
  const { autoid, index } = opts;
  const raw = caseData[ADAPTED_STEPS_KEY];
  if (raw === null || raw === undefined) {
    return [];
  }
  const steps = _step_index(caseData);
  const fieldRoot = `cases[${index}].${ADAPTED_STEPS_KEY}`;
  if (!Array.isArray(raw)) {
    return [_violation("step_structure_adaptation_invalid", fieldRoot, `case ${autoid} ${ADAPTED_STEPS_KEY} must be an array beside the sealed steps; got a JSON ${_typeName(raw)}.`, _LEGAL_FORM_ADAPTED)];
  }
  if (raw.length > MAX_STRUCTURE_ENTRIES) {
    return [_violation("step_structure_count_out_of_range", fieldRoot, `case ${autoid} carries ${raw.length} adapted steps; at most ${MAX_STRUCTURE_ENTRIES} are judged. There is one entry per authored step, and no authored procedure has that many.`, _LEGAL_FORM_ADAPTED)];
  }
  const stepOrder = Object.keys(steps);
  const violations: Record<string, string>[] = [];
  const adaptedOrder: string[] = [];
  let spent = 0;
  for (let position = 0; position < raw.length; position++) {
    const item = raw[position];
    if (spent > MAX_VIOLATION_PAYLOAD_CHARS) {
      violations.push(_violation("step_structure_adaptation_invalid", fieldRoot, `case ${autoid}: ` + _budget_stop_note("adapted-step violation", { rendered: violations.length, stopped_at: `${fieldRoot}[${position}]`, unjudged: Array.from({ length: raw.length - position }, (_, k) => `${fieldRoot}[${position + k}]`) }), _LEGAL_FORM_ADAPTED));
      break;
    }
    const before = violations.length;
    const field = `${fieldRoot}[${position}]`;
    if (!_isMapping(item) || JSON.stringify(Object.keys(item).sort()) !== JSON.stringify([...ADAPTED_STEP_KEYS].sort())) {
      violations.push(_violation("step_structure_adaptation_invalid", field, `case ${autoid}: each adapted step is exactly \`n\`, \`text\` and \`basis\`; got ` + (_isMapping(item) ? Object.keys(item).map((k) => String(k).slice(0, 80)).sort().join(", ").slice(0, 24) : `a JSON ${_typeName(item)}`) + ".", _LEGAL_FORM_ADAPTED));
    } else {
      const number = String(item["n"] || "").trim();
      const text = item["text"];
      const basis = item["basis"];
      if (typeof text !== "string" || !text.trim()) {
        violations.push(_violation("step_structure_adaptation_invalid", `${field}.text`, `case ${autoid}: adapted step ${JSON.stringify(number)} carries no text.`, _LEGAL_FORM_ADAPTED));
      } else if (text.length > MAX_ADAPTED_STEP_CHARS) {
        violations.push(_violation("step_structure_adaptation_invalid", `${field}.text`, `case ${autoid}: adapted step ${JSON.stringify(number)} text is ${text.length} characters; at most ${MAX_ADAPTED_STEP_CHARS} are judged. It is the step in executable form, not an explanation of it.`, _LEGAL_FORM_ADAPTED));
      } else if (basis !== null && basis !== undefined && typeof basis !== "string") {
        violations.push(_violation("step_structure_adaptation_invalid", `${field}.basis`, `case ${autoid}: adapted step ${JSON.stringify(number)} \`basis\` must be a string; got a JSON ${_typeName(basis)}.`, _LEGAL_FORM_ADAPTED));
      } else if (typeof basis === "string" && basis.length > MAX_ADAPTED_BASIS_CHARS) {
        violations.push(_violation("step_structure_adaptation_invalid", `${field}.basis`, `case ${autoid}: adapted step ${JSON.stringify(number)} \`basis\` is ${basis.length} characters; at most ${MAX_ADAPTED_BASIS_CHARS} are judged.`, _LEGAL_FORM_ADAPTED));
      } else if (!(number in steps)) {
        violations.push(_violation("step_structure_adaptation_invalid", `${field}.n`, `case ${autoid}: adapted step ${JSON.stringify(number)} is not one of the authored step numbers (${stepOrder.join(", ") || "none"}).`, _LEGAL_FORM_ADAPTED));
      } else {
        adaptedOrder.push(number);
      }
    }
    for (const row of violations.slice(before)) {
      spent += Object.values(row).reduce((sum, value) => sum + String(value).length, 0);
    }
  }
  if (violations.length) {
    return violations;
  }
  if (JSON.stringify(adaptedOrder) !== JSON.stringify(stepOrder)) {
    return [_violation("step_structure_adaptation_invalid", fieldRoot, `case ${autoid}: ${ADAPTED_STEPS_KEY} must carry one entry per authored step in the same order as steps[]; got ${JSON.stringify(adaptedOrder)} where steps[] reads ${JSON.stringify(stepOrder)}.`, _LEGAL_FORM_ADAPTED)];
  }
  const adapted = adapted_step_texts(caseData) || {};
  const loadBearing = new Set<string>();
  for (const license_ of caseData["rebind_licenses"] || []) {
    if (!_isMapping(license_)) continue;
    if (String(license_["verdict"] || "") !== "load_bearing") continue;
    const key = _ip_key(String(license_["author_literal"] || "").trim());
    if (key) {
      loadBearing.add(key);
    }
  }
  const mapping = new Map<string, Set<string>>();
  for (const [number, authoredText] of Object.entries(steps)) {
    const adaptedText = adapted[number] ?? "";
    const [stepMap, aligned] = _adaptation_literal_map(authoredText, adaptedText);
    for (const [key, values] of stepMap) {
      if (!mapping.has(key)) mapping.set(key, new Set());
      values.forEach((value) => mapping.get(key)!.add(value));
    }
    if (aligned) {
      continue;
    }
    const authoredKeys = _ip_literals(authoredText);
    const adaptedKeys = _ip_literals(adaptedText);
    const gone = new Set([...authoredKeys].filter((k) => !adaptedKeys.has(k)));
    const fresh = new Set([...adaptedKeys].filter((k) => !authoredKeys.has(k)));
    if (gone.size >= 2 && fresh.size < gone.size) {
      violations.push(_violation("step_structure_adaptation_invalid", `${fieldRoot}[${stepOrder.indexOf(number)}].text`, `case ${autoid} step ${number}: ${gone.size} distinct author address literals were replaced but only ${fresh.size} fresh address literal(s) appeared. Distinct author literals must not collapse onto one setup value; keep each authored address on its own adapted value.`, _LEGAL_FORM_ADAPTED));
    }
  }
  for (const key of [...mapping.keys()].sort()) {
    const values = mapping.get(key)!;
    if (values.size > 1) {
      violations.push(_violation("step_structure_adaptation_invalid", fieldRoot, `case ${autoid}: the author literal ${key} is adapted to ${values.size} different values (${[...values].sort().join(", ")}). The same author literal keeps one value everywhere (same-literal equality).`, _LEGAL_FORM_ADAPTED));
    }
  }
  const byValue = new Map<string, Set<string>>();
  for (const [key, values] of mapping) {
    for (const value of values) {
      if (!byValue.has(value)) byValue.set(value, new Set());
      byValue.get(value)!.add(key);
    }
  }
  for (const value of [...byValue.keys()].sort()) {
    const sources = byValue.get(value)!;
    if (sources.size > 1) {
      violations.push(_violation("step_structure_adaptation_invalid", fieldRoot, `case ${autoid}: distinct author literals ${[...sources].sort().join(", ")} are adapted onto the same value ${value}. Different author literals stay different (different-literal inequality); collapsing them changes the test point.`, _LEGAL_FORM_ADAPTED));
    }
  }
  const adaptedAll = _ip_literals(Object.values(adapted).join("\n"));
  for (const key of [...loadBearing].sort()) {
    if (!adaptedAll.has(key)) {
      violations.push(_violation("step_structure_adaptation_invalid", fieldRoot, `case ${autoid}: the load-bearing author literal ${key} is missing from the adapted steps. A load_bearing license means the literal itself is the test point; adaptation keeps it and the unreachability is disclosed, not rewritten.`, _LEGAL_FORM_ADAPTED));
    }
  }
  violations.push(..._stated_value_substitution_violations(caseData, { autoid, index, steps, adapted }));
  return violations;
}

function _stated_value_substitution_violations(caseData: Record<string, any>, opts: { autoid: string; index: number; steps: Record<string, string>; adapted: Record<string, string> }): Record<string, string>[] {
  const { autoid, index, steps, adapted } = opts;
  const structure = caseData[STEP_STRUCTURE_KEY];
  if (!Array.isArray(structure) || !structure.length) {
    return [];
  }
  const grounded = _grounded_heads(caseData);
  if (!grounded.length) {
    return [];
  }
  const out: Record<string, string>[] = [];
  let spent = 0;
  for (let position = 0; position < Math.min(structure.length, MAX_STRUCTURE_ENTRIES); position++) {
    const entry = structure[position];
    if (!_isMapping(entry)) continue;
    const number = String(entry["n"] || "").trim();
    const sealedStep = steps[number];
    if (sealedStep === undefined) continue;
    const adaptedStep = adapted[number] || sealedStep;
    const conditions = entry["stated_conditions"];
    if (!Array.isArray(conditions)) continue;
    for (let slot = 0; slot < Math.min(conditions.length, MAX_ENTRY_ARRAY_ITEMS); slot++) {
      const condition = conditions[slot];
      if (!_isMapping(condition)) continue;
      const authorText = condition["author_text"];
      const text = condition["text"];
      if (typeof authorText !== "string" || typeof text !== "string") continue;
      const substitutions = adaptation_value_substitutions({ author_text: authorText, text, value: condition["value"], sealed_step: sealedStep, adapted_step: adaptedStep, grounded_heads: grounded });
      for (const [oldAtom, newAtom] of substitutions) {
        const basis = recomputable_substitution_basis(oldAtom, newAtom);
        if (basis !== null) {
          continue;
        }
        if (spent > MAX_VIOLATION_PAYLOAD_CHARS) {
          const judged = structure.slice(0, MAX_STRUCTURE_ENTRIES);
          out.push(_violation("step_structure_adaptation_invalid", `cases[${index}].${STEP_STRUCTURE_KEY}`, `case ${autoid}: ` + _budget_stop_note("adapted-value violation", { rendered: out.length, stopped_at: `cases[${index}].${STEP_STRUCTURE_KEY}[${position}].stated_conditions[${slot}]`, unjudged: Array.from({ length: judged.length - position }, (_, k) => `cases[${index}].${STEP_STRUCTURE_KEY}[${position + k}]`) }), _LEGAL_FORM_ADAPTED));
          return out;
        }
        out.push(_violation("step_structure_adaptation_invalid", `cases[${index}].${STEP_STRUCTURE_KEY}[${position}].stated_conditions[${slot}]`, `case ${autoid} step ${number}: the adapted step states ${JSON.stringify(newAtom)} in the same command argument slot where the author's own words state ${JSON.stringify(oldAtom)}, and ${JSON.stringify(oldAtom)} occurs nowhere in the adapted step. This condition's \`value\` therefore carries ${JSON.stringify(newAtom)} downstream as the author's stated value, which it is not. An adaptation may re-word a condition, and it may fill a value the author left open; replacing a value the author did state needs a basis the engine can recompute — an address this bed cannot reach, or a role the bed facts resolve to a machine on it. Neither holds here. If the author's own surfaces disagree (a title or grouping naming one behaviour while a step configures another, and the authored expectation following from only one), that contradiction is the author's to settle: deciding which side is the slip is an authority call this stage does not hold. Leave the authored words in the adapted step and declare it under \`consistency.authored_conflict\`, quoting each authored surface verbatim by its own locator.`, _LEGAL_FORM_ADAPTED));
        spent += Object.values(out[out.length - 1]).reduce((sum, value) => sum + String(value).length, 0);
      }
    }
  }
  return out;
}

function _grounded_heads(caseData: Record<string, any>): [string, string[]][] {
  const out: [string, string[]][] = [];
  for (const item of caseData["command_check"] || []) {
    if (!_isMapping(item)) continue;
    const command = String(item["command"] || "").trim();
    const tokens = _norm_head_tokens(command);
    if (command && tokens.length) {
      out.push([command, tokens]);
    }
  }
  return out;
}

function _head_is_grounded(head: string, grounded: [string, string[]][]): boolean {
  const tokens = _norm_head_tokens(head);
  if (!tokens.length) {
    return false;
  }
  for (const [, candidate] of grounded) {
    if (JSON.stringify(tokens) === JSON.stringify(candidate)) {
      return true;
    }
    if (tokens.length < candidate.length && JSON.stringify(candidate.slice(0, tokens.length)) === JSON.stringify(tokens)) {
      return true;
    }
  }
  return false;
}

function _ref_index(ref: string, pattern: RegExp): number | null {
  const match = pattern.exec(ref);
  if (match === null) {
    return null;
  }
  const digits = match[1];
  if (!/^\d+$/.test(digits)) {
    return null;
  }
  return parseInt(digits, 10);
}

export function step_structure_violations(caseData: Record<string, any>, opts: { index: number; object_kinds: Set<string> | null }): Record<string, string>[] {
  const { index, object_kinds } = opts;
  const autoid = String(caseData["autoid"] || "");
  const steps = _step_index(caseData);
  const structure = caseData[STEP_STRUCTURE_KEY];
  if (!Object.keys(steps).length) {
    return [];
  }
  const adapted = adapted_step_texts(caseData);
  const violations: Record<string, string>[] = [];
  violations.push(...adapted_steps_violations(caseData, { autoid, index }));
  if (!Array.isArray(structure)) {
    const observed = !(STEP_STRUCTURE_KEY in caseData) ? "the key is absent" : `got a JSON ${_typeName(structure)}`;
    violations.push(_violation("step_structure_missing", `cases[${index}].${STEP_STRUCTURE_KEY}`, `case ${autoid} must carry \`${STEP_STRUCTURE_KEY}\`, one entry per authored step, beside the verbatim steps; ${observed}. The verbatim steps stay the authority — the structure is the projection next to them, and the engine does not derive it.`, _LEGAL_FORM_ENTRY));
    return violations;
  }
  if (structure.length > MAX_STRUCTURE_ENTRIES) {
    violations.push(_violation("step_structure_count_out_of_range", `cases[${index}].${STEP_STRUCTURE_KEY}`, `case ${autoid} carries ${structure.length} structure entries; at most ${MAX_STRUCTURE_ENTRIES} are judged. There is one entry per authored step, and no authored procedure has that many.`, _LEGAL_FORM_ENTRY));
    return violations;
  }
  const seen: Record<string, number> = {};
  const concretizations = caseData["concretizations"];
  const concretizationCount = Array.isArray(concretizations) ? concretizations.length : 0;
  const grounded = _grounded_heads(caseData);
  const knownHeads = _known_heads_note(grounded);
  let spent = 0;
  let stoppedEarly = false;
  for (let position = 0; position < structure.length; position++) {
    const entry = structure[position];
    if (spent > MAX_VIOLATION_PAYLOAD_CHARS) {
      stoppedEarly = true;
      violations.push(_violation("step_structure_missing", `cases[${index}].${STEP_STRUCTURE_KEY}`, `case ${autoid}: ` + _budget_stop_note("structure-entry violation", { rendered: violations.length, stopped_at: `cases[${index}].${STEP_STRUCTURE_KEY}[${position}]`, unjudged: Array.from({ length: structure.length - position }, (_, k) => `cases[${index}].${STEP_STRUCTURE_KEY}[${position + k}]`) }), _LEGAL_FORM_ENTRY));
      break;
    }
    const before = violations.length;
    const locus = `cases[${index}].${STEP_STRUCTURE_KEY}[${position}]`;
    if (!_isMapping(entry)) {
      violations.push(_violation("step_structure_missing", locus, `case ${autoid} ${STEP_STRUCTURE_KEY}[${position}] must be a JSON object keyed by the authored step number; got a JSON ${_typeName(entry)}.`, _LEGAL_FORM_ENTRY));
      continue;
    }
    const number = String(entry["n"] || "").trim();
    if (!(number in steps)) {
      violations.push(_violation("step_structure_missing", `${locus}.n`, `case ${autoid} ${STEP_STRUCTURE_KEY}[${position}] names step ${JSON.stringify(number)}, which is not one of the authored step numbers (${Object.keys(steps).sort().join(", ") || "none"}). One entry per authored step, and the step number is copied from steps[].n.`, _LEGAL_FORM_ENTRY));
      continue;
    }
    if (number in seen) {
      violations.push(_violation("step_structure_missing", `${locus}.n`, `case ${autoid} declares step ${number} twice in ${STEP_STRUCTURE_KEY} (first at ${STEP_STRUCTURE_KEY}[${seen[number]}]). One entry per authored step; merge the two entries.`, _LEGAL_FORM_ENTRY));
      continue;
    }
    seen[number] = position;
    const unknownKeys = Object.keys(entry).filter((k) => !STRUCTURE_ENTRY_KEYS.has(k)).sort();
    if (unknownKeys.length) {
      violations.push(_violation("step_structure_missing", locus, `case ${autoid} structure entry for step ${number} carries fields outside the closed set: ${unknownKeys.join(", ")}.`, _LEGAL_FORM_ENTRY));
      continue;
    }
    violations.push(..._object_violations(entry, { autoid, locus, number, object_kinds }));
    violations.push(..._operation_violations(entry, { autoid, locus, number, grounded, known_heads: knownHeads }));
    violations.push(..._condition_violations(entry, { autoid, locus, number, step_text: steps[number], adapted_text: adapted !== null ? adapted[number] : null }));
    violations.push(..._slot_violations(entry, { autoid, locus, number, concretization_count: concretizationCount }));
    spent += violations.slice(before).reduce((sum, row) => sum + (row["code"] ?? "").length + (row["locus"] ?? "").length + (row["detail"] ?? "").length, 0);
  }
  const missing = stoppedEarly ? [] : Object.keys(steps).filter((k) => !(k in seen)).sort();
  if (missing.length) {
    violations.push(_violation("step_structure_missing", `cases[${index}].${STEP_STRUCTURE_KEY}`, `case ${autoid} has no structure entry for authored step${missing.length > 1 ? "s" : ""} ${missing.join(", ")}. Every authored step needs one entry; a step whose structure you cannot state still needs its entry with empty arrays, so the gap is visible instead of silent.`, _LEGAL_FORM_ENTRY));
  }
  return violations;
}

export function sealed_structure_failures(caseData: Record<string, any>, opts: { object_kinds: Set<string> | null }): string[] {
  const structure = caseData[STEP_STRUCTURE_KEY];
  let rows: Record<string, string>[];
  if (!Array.isArray(structure) || !structure.length) {
    if (caseData[ADAPTED_STEPS_KEY] === null || caseData[ADAPTED_STEPS_KEY] === undefined) {
      return [];
    }
    rows = adapted_steps_violations(caseData, { autoid: String(caseData["autoid"] || ""), index: 0 });
  } else {
    rows = step_structure_violations(caseData, { index: 0, object_kinds: opts.object_kinds });
  }
  const codes: string[] = [];
  for (const item of rows) {
    const code = String(item["code"] || "");
    if (code && !codes.includes(code)) {
      codes.push(code);
    }
  }
  return codes;
}

function _object_violations(entry: Record<string, any>, opts: { autoid: string; locus: string; number: string; object_kinds: Set<string> | null }): Record<string, string>[] {
  const { autoid, locus, number, object_kinds } = opts;
  let objects = entry["objects"];
  if (objects === null || objects === undefined) {
    objects = [];
  }
  if (!Array.isArray(objects)) {
    return [_violation("step_structure_object_kind_unknown", `${locus}.objects`, `case ${autoid} step ${number}: \`objects\` must be an array; got a JSON ${_typeName(objects)}.`, _LEGAL_FORM_OBJECT)];
  }
  const capped = _array_over_cap(objects, { autoid, field: `${locus}.objects`, number, legal_form: _LEGAL_FORM_OBJECT });
  if (capped !== null) {
    return [capped];
  }
  const out: Record<string, string>[] = [];
  objects.forEach((item, position) => {
    const field = `${locus}.objects[${position}]`;
    if (!_isMapping(item) || JSON.stringify(Object.keys(item).sort()) !== JSON.stringify(["count", "kind", "role"])) {
      out.push(_violation("step_structure_object_kind_unknown", field, `case ${autoid} step ${number}: each object is exactly \`kind\`, \`role\` and \`count\`; got ` + (_isMapping(item) ? Object.keys(item).sort().join(", ") : `a JSON ${_typeName(item)}`) + ".", _LEGAL_FORM_OBJECT));
      return;
    }
    const role = item["role"];
    if (!(STRUCTURE_OBJECT_ROLES as readonly string[]).includes(role)) {
      out.push(_violation("step_structure_object_kind_unknown", `${field}.role`, `case ${autoid} step ${number}: \`role\` is one of ${STRUCTURE_OBJECT_ROLES.join(", ")}; got ${JSON.stringify(role)}.`, _LEGAL_FORM_OBJECT));
      return;
    }
    const count = item["count"];
    if (count !== null && count !== undefined && (typeof count !== "number" || !Number.isInteger(count) || count < 0)) {
      out.push(_violation("step_structure_object_kind_unknown", `${field}.count`, `case ${autoid} step ${number}: \`count\` is a non-negative integer or null; got ${JSON.stringify(count)}.`, _LEGAL_FORM_OBJECT));
      return;
    }
    if (typeof count === "number" && Number.isInteger(count) && count > MAX_OBJECT_COUNT) {
      out.push(_violation("step_structure_count_out_of_range", `${field}.count`, `case ${autoid} step ${number}: \`count\` is at most ${MAX_OBJECT_COUNT}; got ${count}. The engine carries this number into the records, disclosures and reports it builds from the structure, so a value beyond the bound is refused instead of being materialized. State the number the authored step actually names.`, _LEGAL_FORM_OBJECT));
      return;
    }
    const kind = item["kind"];
    if (typeof kind !== "string" || !kind.trim()) {
      out.push(_violation("step_structure_object_kind_unknown", `${field}.kind`, `case ${autoid} step ${number}: \`kind\` must be a non-empty command-tree object path; got ${JSON.stringify(kind)}.`, _LEGAL_FORM_OBJECT));
      return;
    }
    if (kind.length > MAX_KIND_CHARS) {
      out.push(_violation("step_structure_count_out_of_range", `${field}.kind`, `case ${autoid} step ${number}: \`kind\` is at most ${MAX_KIND_CHARS} characters; got ${kind.length}. An object path is a few command-tree segments, not a sentence.`, _LEGAL_FORM_OBJECT));
      return;
    }
    if (object_kinds === null) {
      return;
    }
    if (!object_kinds.has(kind)) {
      const near = _near_kinds(kind, object_kinds);
      out.push(_violation("step_structure_object_kind_unknown", `${field}.kind`, `case ${autoid} step ${number}: ${JSON.stringify(kind)} is not an object path in this build's command tree. The path is the command-tree location of the head that creates or configures the object, with the leading operator word and the trailing action segment removed` + (near.length ? `; near paths in this tree: ${near.join(", ")}` : "") + ".", _LEGAL_FORM_OBJECT));
    }
  });
  return out;
}

const _nearKindsCache = new Map<string, string[]>();

function _near_kinds(kind: string, objectKinds: Set<string>): string[] {
  const target = String(kind || "").toLowerCase().slice(0, MAX_KIND_CHARS);
  if (!target) {
    return [];
  }
  const cacheKey = target + "|" + [...objectKinds].sort().join(",");
  const cached = _nearKindsCache.get(cacheKey);
  if (cached !== undefined) {
    return cached;
  }
  const scored = [...objectKinds]
    .map((candidate): [number, string] => [-new _SequenceMatcher(target.split(""), candidate.toLowerCase().split("")).ratio(), candidate])
    .sort((a, b) => a[0] - b[0] || a[1].localeCompare(b[1]));
  const result = scored.slice(0, 5).map(([, candidate]) => candidate);
  if (_nearKindsCache.size >= 256) {
    _nearKindsCache.delete(_nearKindsCache.keys().next().value!);
  }
  _nearKindsCache.set(cacheKey, result);
  return result;
}

function _known_heads_note(grounded: [string, string[]][]): string {
  if (!grounded.length) {
    return "none";
  }
  const shown = grounded.slice(0, MAX_KNOWN_HEADS_SHOWN).map(([command]) => command);
  const rest = grounded.length - shown.length;
  return shown.join(", ") + (rest > 0 ? `, and ${rest} more this case already grounded` : "");
}

function _array_over_cap(items: any[], opts: { autoid: string; field: string; number: string; legal_form: string }): Record<string, string> | null {
  if (items.length <= MAX_ENTRY_ARRAY_ITEMS) {
    return null;
  }
  return _violation("step_structure_count_out_of_range", opts.field, `case ${opts.autoid} step ${opts.number}: this array carries ${items.length} entries; at most ${MAX_ENTRY_ARRAY_ITEMS} are judged. State what the authored step names, not every form it could take.`, opts.legal_form);
}

function _operation_violations(entry: Record<string, any>, opts: { autoid: string; locus: string; number: string; grounded: [string, string[]][]; known_heads?: string }): Record<string, string>[] {
  const { autoid, locus, number, grounded } = opts;
  const knownHeads = opts.known_heads ?? "";
  let operations = entry["operations"];
  if (operations === null || operations === undefined) {
    operations = [];
  }
  if (!Array.isArray(operations)) {
    return [_violation("step_structure_operation_head_unknown", `${locus}.operations`, `case ${autoid} step ${number}: \`operations\` must be an array; got a JSON ${_typeName(operations)}.`, _LEGAL_FORM_OPERATION)];
  }
  const capped = _array_over_cap(operations, { autoid, field: `${locus}.operations`, number, legal_form: _LEGAL_FORM_OPERATION });
  if (capped !== null) {
    return [capped];
  }
  const out: Record<string, string>[] = [];
  operations.forEach((item, position) => {
    const field = `${locus}.operations[${position}]`;
    if (!_isMapping(item) || JSON.stringify(Object.keys(item).sort()) !== JSON.stringify(["head", "ref"])) {
      out.push(_violation("step_structure_operation_head_unknown", field, `case ${autoid} step ${number}: each operation is exactly \`head\` and \`ref\`; got ` + (_isMapping(item) ? Object.keys(item).sort().join(", ") : `a JSON ${_typeName(item)}`) + ".", _LEGAL_FORM_OPERATION));
      return;
    }
    const head = item["head"];
    if (typeof head !== "string" || !_head_is_grounded(head, grounded)) {
      const known = knownHeads || _known_heads_note(grounded);
      out.push(_violation("step_structure_operation_head_unknown", `${field}.head`, `case ${autoid} step ${number}: ${JSON.stringify(_display_form(head, MAX_KIND_CHARS))} is not one of the command heads this case already grounded in command_check (${known}). Reuse a head you checked; inventing one here would put an unchecked command into the structure.`, _LEGAL_FORM_OPERATION));
      return;
    }
    const ref = item["ref"];
    if (typeof ref !== "string" || !ref.trim()) {
      out.push(_violation("step_structure_operation_head_unknown", `${field}.ref`, `case ${autoid} step ${number}: \`ref\` names where this operation comes from; got ${JSON.stringify(ref)}.`, _LEGAL_FORM_OPERATION));
    }
  });
  return out;
}

function _condition_violations(entry: Record<string, any>, opts: { autoid: string; locus: string; number: string; step_text: string; adapted_text: string | null }): Record<string, string>[] {
  const { autoid, locus, number, step_text, adapted_text } = opts;
  let conditions = entry["stated_conditions"];
  if (conditions === null || conditions === undefined) {
    conditions = [];
  }
  if (!Array.isArray(conditions)) {
    return [_violation("step_structure_condition_not_verbatim", `${locus}.stated_conditions`, `case ${autoid} step ${number}: \`stated_conditions\` must be an array; got a JSON ${_typeName(conditions)}.`, _LEGAL_FORM_CONDITION)];
  }
  const capped = _array_over_cap(conditions, { autoid, field: `${locus}.stated_conditions`, number, legal_form: _LEGAL_FORM_CONDITION });
  if (capped !== null) {
    return [capped];
  }
  const { ground_condition_author_text } = require("./mindmap_contract_projector");
  const basisText = adapted_text !== null ? adapted_text : step_text;
  const basisForms = _verbatim_forms(basisText);
  const out: Record<string, string>[] = [];
  conditions.forEach((item, position) => {
    const field = `${locus}.stated_conditions[${position}]`;
    const keySet = _isMapping(item) ? new Set(Object.keys(item)) : new Set<string>();
    const withAuthor = JSON.stringify([...keySet].sort()) === JSON.stringify(["author_text", "kind", "text", "value"]);
    const withoutAuthor = JSON.stringify([...keySet].sort()) === JSON.stringify(["kind", "text", "value"]);
    if (!_isMapping(item) || (!withAuthor && !withoutAuthor)) {
      out.push(_violation("step_structure_condition_not_verbatim", field, `case ${autoid} step ${number}: each stated condition is exactly \`text\`, \`kind\`, \`value\` and \`author_text\` (\`author_text\` may be omitted only for a step that needed no adaptation, where \`text\` already is the author's words); got ` + (_isMapping(item) ? Object.keys(item).sort().join(", ") : `a JSON ${_typeName(item)}`) + ".", _LEGAL_FORM_CONDITION));
      return;
    }
    const kind = item["kind"];
    if (!(STRUCTURE_CONDITION_KINDS as readonly string[]).includes(kind)) {
      out.push(_violation("step_structure_condition_not_verbatim", `${field}.kind`, `case ${autoid} step ${number}: \`kind\` is one of ${STRUCTURE_CONDITION_KINDS.join(", ")}; got ${JSON.stringify(kind)}.`, _LEGAL_FORM_CONDITION));
      return;
    }
    const text = item["text"];
    if (typeof text !== "string" || !text.trim()) {
      out.push(_violation("step_structure_condition_not_verbatim", `${field}.text`, `case ${autoid} step ${number}: \`text\` must be a non-empty substring of the adapted step; got ${JSON.stringify(_display_form(text, 200))}.`, _LEGAL_FORM_CONDITION));
      return;
    }
    if (text.length > MAX_CONDITION_TEXT_CHARS) {
      out.push(_violation("step_structure_count_out_of_range", `${field}.text`, `case ${autoid} step ${number}: \`text\` is at most ${MAX_CONDITION_TEXT_CHARS} characters; got ${text.length}. It is the clause the adaptation states, not the step itself.`, _LEGAL_FORM_CONDITION));
      return;
    }
    if (!_verbatim_forms(text).some((form) => basisForms.some((stepForm) => stepForm.includes(form)))) {
      out.push(_violation("step_structure_condition_not_verbatim", `${field}.text`, `case ${autoid} step ${number}: ${JSON.stringify(_display_form(text))} does not occur in the adapted step. The adapted step reads ${JSON.stringify(_display_form(basisText))}. State the condition out of the adapted text; the author's original words belong in \`author_text\`.`, _LEGAL_FORM_CONDITION));
      return;
    }
    let authorText = item["author_text"];
    const stepAdapted = adapted_text !== null && step_is_adapted(step_text, adapted_text);
    if (!("author_text" in item) && !stepAdapted) {
      authorText = text;
    }
    if (typeof authorText !== "string" || !authorText.trim()) {
      out.push(_violation("step_structure_condition_not_verbatim", `${field}.author_text`, `case ${autoid} step ${number}: this step was adapted, so \`author_text\` must name the span of the author's original text this condition corresponds to; got ${JSON.stringify(_display_form(authorText, 200))}.`, _LEGAL_FORM_CONDITION));
      return;
    }
    if (authorText.length > MAX_CONDITION_TEXT_CHARS) {
      out.push(_violation("step_structure_count_out_of_range", `${field}.author_text`, `case ${autoid} step ${number}: \`author_text\` is at most ${MAX_CONDITION_TEXT_CHARS} characters; got ${authorText.length}. It points at a clause of one authored step, not a passage.`, _LEGAL_FORM_CONDITION));
      return;
    }
    const span = ground_condition_author_text(authorText, step_text);
    if (span === null || span === undefined) {
      out.push(_violation("step_structure_condition_not_verbatim", `${field}.author_text`, `case ${autoid} step ${number}: \`author_text\` ${JSON.stringify(_display_form(authorText))} does not occur in the sealed author step, even with whitespace runs normalized. The authored step reads ${JSON.stringify(_display_form(step_text))}. Point at the author's actual words, not a retelling of them; the engine grounds this span, so small whitespace differences are corrected rather than rejected.`, _LEGAL_FORM_CONDITION));
      return;
    }
    const value = item["value"];
    if (value !== null && value !== undefined && !(typeof value === "string" || typeof value === "number")) {
      out.push(_violation("step_structure_condition_not_verbatim", `${field}.value`, `case ${autoid} step ${number}: \`value\` is the literal the adaptation states, as a JSON string or number; got a JSON ${_typeName(value)}.`, _LEGAL_FORM_CONDITION));
      return;
    }
    if (typeof value === "string" && value.length > MAX_VALUE_CHARS) {
      out.push(_violation("step_structure_count_out_of_range", `${field}.value`, `case ${autoid} step ${number}: \`value\` is at most ${MAX_VALUE_CHARS} characters; got ${value.length}. It is the literal the adaptation states — an algorithm name, a number, a bucket ratio — not a passage.`, _LEGAL_FORM_CONDITION));
    }
  });
  return out;
}

function _slot_violations(entry: Record<string, any>, opts: { autoid: string; locus: string; number: string; concretization_count: number }): Record<string, string>[] {
  const { autoid, locus, number, concretization_count } = opts;
  let slots = entry["free_slots"];
  if (slots === null || slots === undefined) {
    slots = [];
  }
  if (!Array.isArray(slots)) {
    return [_violation("step_structure_slot_ref_unresolved", `${locus}.free_slots`, `case ${autoid} step ${number}: \`free_slots\` must be an array; got a JSON ${_typeName(slots)}.`, _LEGAL_FORM_SLOT)];
  }
  const capped = _array_over_cap(slots, { autoid, field: `${locus}.free_slots`, number, legal_form: _LEGAL_FORM_SLOT });
  if (capped !== null) {
    return [capped];
  }
  const out: Record<string, string>[] = [];
  slots.forEach((item, position) => {
    const field = `${locus}.free_slots[${position}]`;
    if (!_isMapping(item) || JSON.stringify(Object.keys(item).sort()) !== JSON.stringify(["ref", "slot"])) {
      out.push(_violation("step_structure_slot_ref_unresolved", field, `case ${autoid} step ${number}: each free slot is exactly \`slot\` and \`ref\`; got ` + (_isMapping(item) ? Object.keys(item).sort().join(", ") : `a JSON ${_typeName(item)}`) + ". The value itself lives once at the target of `ref`.", _LEGAL_FORM_SLOT));
      return;
    }
    const slot = item["slot"];
    if (typeof slot !== "string" || !slot.trim()) {
      out.push(_violation("step_structure_slot_ref_unresolved", `${field}.slot`, `case ${autoid} step ${number}: \`slot\` names the free variable; got ${JSON.stringify(slot)}.`, _LEGAL_FORM_SLOT));
      return;
    }
    const ref = String(item["ref"] || "");
    const resolved = _ref_index(ref, _CONCRETIZATION_REF_RE);
    if (resolved !== null) {
      if (resolved < concretization_count) {
        return;
      }
      out.push(_violation("step_structure_slot_ref_unresolved", `${field}.ref`, `case ${autoid} step ${number}: ${ref} points past the end of \`concretizations\`, which has ${concretization_count} entries. Record the witness there first, then point at its index.`, _LEGAL_FORM_SLOT));
      return;
    }
    out.push(_violation("step_structure_slot_ref_unresolved", `${field}.ref`, `case ${autoid} step ${number}: ${JSON.stringify(ref)} is not a resolvable reference. Use \`concretizations[<i>]\` for a witness you recorded. \`${ENGINE_SLOTS_KEY}\` is engine-owned and carries no value a slot could point at.`, _LEGAL_FORM_SLOT));
  });
  return out;
}

export function stated_value_tokens(value: any): string[] {
  const { strip_token_quotes } = require("./vendor_stdlib");
  return String(value ?? "").split(_VALUE_SPLIT_RE).filter((token) => token).map((token) => strip_token_quotes(token));
}

export function stated_count_integers(value: any): number[] {
  const tokens = stated_value_tokens(value);
  if (!tokens.length || !tokens.every((token) => /^\d+$/.test(token) && token.length <= MAX_COUNT_DIGITS)) {
    return [];
  }
  return tokens.map((token) => parseInt(token, 10));
}

export function is_observation_step_entry(entry: Record<string, any>): boolean {
  const roles = new Set(((entry["objects"] || []) as any[]).filter((item) => _isMapping(item)).map((item) => String(item["role"] || "")));
  if (roles.has("observed") && !roles.has("created") && !roles.has("configured")) {
    return true;
  }
  const probes = _probe_verbs();
  if (!probes.size) {
    return false;
  }
  for (const item of entry["operations"] || []) {
    if (!_isMapping(item)) continue;
    const tokens = _norm_head_tokens(item["head"]);
    if (tokens.length && probes.has(tokens[0].toLowerCase())) {
      return true;
    }
  }
  return false;
}

export function engine_step_order(caseData: Record<string, any>): string[] {
  const out: string[] = [];
  for (const item of caseData["steps"] || []) {
    if (!_isMapping(item)) continue;
    const number = String(item["n"] || "").trim();
    if (number && !out.includes(number)) {
      out.push(number);
    }
  }
  return out;
}

export function order_structure_entries(structure: Record<string, any>[], order: string[] = []): Record<string, any>[] {
  const entries = structure.filter((entry) => _isMapping(entry));
  if (!order.length) {
    return entries;
  }
  const rank = new Map(order.map((number, index) => [number, index] as [string, number]));
  const tail = rank.size;
  return entries
    .map((entry, position): [number, number, Record<string, any>] => [rank.get(String(entry["n"] || "").trim()) ?? tail, position, entry])
    .sort((a, b) => a[0] - b[0] || a[1] - b[1])
    .map(([, , entry]) => entry);
}

export function observation_step_numbers(structure: Record<string, any>[], opts: { order?: string[] } = {}): string[] {
  return order_structure_entries(structure, opts.order ?? [])
    .filter((entry) => String(entry["n"] || "").trim() && is_observation_step_entry(entry))
    .map((entry) => String(entry["n"] || "").trim());
}

export function concretized_weights(caseData: Record<string, any>, entry: Record<string, any>): number[] {
  const concretizations = caseData["concretizations"];
  if (!Array.isArray(concretizations)) {
    return [];
  }
  for (const slot of entry["free_slots"] || []) {
    if (!_isMapping(slot)) continue;
    if (String(slot["slot"] || "") !== EFFECTIVE_WEIGHTS_SLOT) continue;
    const position = _ref_index(String(slot["ref"] || ""), _CONCRETIZATION_REF_RE);
    if (position === null || position >= concretizations.length) continue;
    const record = concretizations[position];
    if (!_isMapping(record)) continue;
    if (String(record["slot"] || "") !== EFFECTIVE_WEIGHTS_SLOT) continue;
    const weights = stated_count_integers(record["value"]);
    if (weights.length) {
      return weights;
    }
  }
  return [];
}

export function stated_weights(entry: Record<string, any>): number[] {
  for (const item of entry["stated_conditions"] || []) {
    if (!_isMapping(item) || item["kind"] !== "weight") continue;
    const weights = stated_count_integers(item["value"]);
    if (weights.length) {
      return weights;
    }
  }
  return [];
}

export function distribution_criterion_bindings(expectations: Record<string, any>[]): Record<string, string>[] {
  const out: Record<string, string>[] = [];
  for (const item of expectations || []) {
    if (!_isMapping(item)) continue;
    const claim = item["normalized_claim"];
    if (!_isMapping(claim)) continue;
    if (String(claim["criterion_type"] || "") !== "distribution") continue;
    out.push({ expectation_id: String(claim["expectation_id"] || ""), semantic_key: String(claim["semantic_key"] || ""), criterion_type: "distribution", criterion_rule_id: String(claim["rule_id"] || ""), shape_key: String(claim["shape_key"] || "") });
  }
  return out;
}

function _slot_reason(opts: { paired: boolean; ordered?: boolean }): string {
  if (!(opts.ordered ?? true) || !opts.paired) {
    return "pairing_ambiguous";
  }
  return "ok";
}

export function apply_engine_slots(caseData: Record<string, any>, bindings: Record<string, string>[]): Record<string, any> {
  const structure = caseData[STEP_STRUCTURE_KEY];
  if (!Array.isArray(structure) || !bindings.length) {
    return caseData;
  }
  const order = engine_step_order(caseData);
  const listed = structure.filter((item: any) => _isMapping(item));
  const ordered = Boolean(order.length) || !listed.length;
  const entries = ordered ? order_structure_entries(listed, order).filter((entry) => _isMapping(entry)) : [];
  let records = caseData[ENGINE_SLOTS_KEY];
  if (!Array.isArray(records)) {
    records = [];
  }
  const signed = new Set(records.filter((record: any) => _isMapping(record)).map((record: any) => `${String(record["slot"] || "")}|${String((_isMapping(record["claim"]) ? record["claim"] : {})["expectation_id"] || "")}`));
  const observations = observation_step_numbers(entries);
  const paired = observations.length === bindings.length;
  bindings.forEach((binding, position) => {
    const key = `${SAMPLING_DISCLOSURE_SLOT}|${String(binding["expectation_id"] || "")}`;
    if (signed.has(key)) {
      return;
    }
    signed.add(key);
    const observationStep = paired ? observations[position] : "";
    let basis: string;
    if (!ordered) {
      basis = STEP_ORDER_UNAVAILABLE_BASIS;
    } else if (paired && observationStep) {
      basis = `observation_pairing@step:${observationStep}`;
    } else {
      basis = "observation_pairing_unavailable";
    }
    records.push({ slot: SAMPLING_DISCLOSURE_SLOT, source: ENGINE_SLOT_SOURCE, claim: { ...binding }, reason_code: _slot_reason({ paired, ordered }), basis, applies_to_steps: paired && observationStep ? [observationStep] : [] });
  });
  if (records.length) {
    caseData[ENGINE_SLOTS_KEY] = records;
  }
  return caseData;
}

export function strip_engine_slots(caseData: Record<string, any>): Record<string, any> {
  delete caseData[ENGINE_SLOTS_KEY];
  for (const entry of caseData[STEP_STRUCTURE_KEY] || []) {
    if (!_isMapping(entry)) continue;
    const slots = entry["free_slots"];
    if (!Array.isArray(slots)) continue;
    entry["free_slots"] = slots.filter((slot: any) => !(_isMapping(slot) && _SLOT_REF_RE.test(String(slot["ref"] || ""))));
  }
  return caseData;
}

export function engine_sampling_records(caseData: Record<string, any>): Record<string, any>[] {
  return ((caseData[ENGINE_SLOTS_KEY] || []) as any[]).filter((record) => _isMapping(record) && String(record["slot"] || "") === SAMPLING_DISCLOSURE_SLOT).map((record) => ({ ...record }));
}

export function normalized_expectations_for_case(caseData: Record<string, any>, opts: { mindmap_text: string; mindmap_source_sha256?: string; defect_spec_receipt?: Record<string, any> | null; projection?: Record<string, any> | null }): Record<string, any>[] {
  try {
    const { normalize_case_expectations } = require("./criterion_normalization");
    const { _expectations } = require("./mindmap_contract_projector");
    const projected = _expectations(caseData, { mindmap_source_sha256: String(opts.mindmap_source_sha256 || ""), defect_spec_receipt: opts.defect_spec_receipt ? { ...opts.defect_spec_receipt } : null });
    const result = normalize_case_expectations({ case: caseData, expectations: projected, mindmap_text: String(opts.mindmap_text || ""), projection: opts.projection ?? null });
    return result.expectations.map((item: any) => ({ ...item }));
  } catch (exc) {
    logger.warn?.("criterion normalization unavailable for engine slots", exc);
    return [];
  }
}
