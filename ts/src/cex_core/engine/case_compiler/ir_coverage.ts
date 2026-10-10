import fs from "node:fs";
import path from "node:path";
import { _cex_data_path, _cex_set_caller } from "../_root";

_cex_set_caller("cex_core.engine.case_compiler.ir_coverage");

const _ATLAS_PATH = path.join(_cex_data_path(""), "knowledge/data/compile_ref/capability_atlas.json");
const _VALIDATION_GAP_FAMILIES: Set<string> = new Set();

function _isDisabled(info: any): boolean {
  return typeof info === "object" && info !== null && Boolean(info.disabled);
}

export function load_atlas(): Record<string, any> {
  return JSON.parse(fs.readFileSync(_ATLAS_PATH, "utf8"));
}

function _contract(contract?: any): Record<string, any> {
  const { ValidatedExcelContract, load_excel_contract } = require("./excel_contract");
  if (contract === null || contract === undefined) {
    return load_excel_contract();
  }
  if (!(contract instanceof ValidatedExcelContract)) {
    throw new TypeError("ir_coverage expects a ValidatedExcelContract; the legacy raw atlas dict is no longer accepted");
  }
  return contract;
}

function _enabledEntries(contract: Record<string, any>): Array<Record<string, any>> {
  return (contract.entries || []).filter((entry: any) => entry.status === "enabled");
}

export function all_capability_names(atlas?: any): Set<string> {
  const contract = _contract(atlas);
  const names = new Set<string>();
  for (const entry of _enabledEntries(contract)) {
    names.add(String(entry.f));
  }
  for (const item of contract.execute_actions || []) {
    if (item.status === "enabled") {
      names.add(`execute:${item.dispatcher}:${item.normalized}`);
    }
  }
  return names;
}

export function all_enabled_entry_capability_names(contract?: any): Set<string> {
  const source = _contract(contract);
  const out = new Set<string>();
  for (const entry of _enabledEntries(source)) {
    out.add(`${entry.e}::${entry.f}`);
  }
  return out;
}

function _executeCapabilityInfo(name: string, contract: Record<string, any>): Record<string, any> | null {
  if (!name.startsWith("execute:")) {
    return null;
  }
  const tail = name.slice("execute:".length);
  const sep = tail.indexOf(":");
  if (sep < 0) {
    return null;
  }
  const dispatcher = tail.slice(0, sep);
  const normalized = tail.slice(sep + 1);
  const matches = (contract.execute_actions || []).filter(
    (item: any) => item.status === "enabled" && item.dispatcher === dispatcher && item.normalized === normalized
  );
  return matches.length === 1 ? matches[0] : null;
}

function _entryForName(name: string, contract: Record<string, any>): Record<string, any> | null {
  const candidates = _enabledEntries(contract).filter((entry) => entry.f === name);
  if (!candidates.length) {
    return null;
  }
  const priority: Record<string, number> = { check_point: 0, time: 1, APV_0: 2, test_env: 3 };
  candidates.sort((a, b) => {
    const pa = priority[a.e] ?? 9;
    const pb = priority[b.e] ?? 9;
    if (pa !== pb) return pa - pb;
    return a.e < b.e ? -1 : a.e > b.e ? 1 : 0;
  });
  return candidates[0];
}

function _argumentsForEntry(entry: Record<string, any>, contract: Record<string, any>): string {
  const e = entry.e;
  const f = entry.f;
  if (e === "check_point") {
    return "expected";
  }
  if (e === "time" && f === "sleep") {
    return "1";
  }
  if (f === "cmds_config") {
    return "probe\nprobe_second";
  }
  if (f === "cmd" || f === "cmd_enable" || f === "cmd_config" || f === "array_config") {
    return "probe";
  }
  if (f === "execute") {
    const action = (contract.execute_actions || []).find(
      (item: any) => item.status === "enabled" && (item.allowed_es || []).includes(e)
    );
    if (!action) {
      return "";
    }
    let value = String(action.name);
    if ((action.signature || {}).required && (action.signature || {}).required.length) {
      value += "：payload";
    }
    return value;
  }
  const parts: string[] = [];
  let index = 0;
  for (const parameter of entry.signature?.parameters || []) {
    index++;
    if (!parameter.required) {
      continue;
    }
    let value = `arg_${index}`;
    if (parameter.kind === "keyword_only") {
      value = `${parameter.name}=${value}`;
    }
    parts.push(value);
  }
  return parts.join(", ");
}

function _blockForEntry(entry: Record<string, any>, contract: Record<string, any>): Record<string, any> {
  const block: Record<string, any> = {
    kind: "STEP",
    E: entry.e,
    F: entry.f,
    G: _argumentsForEntry(entry, contract),
    ref: "precedent:excel_contract",
  };
  if (entry.e === "check_point" && entry.f === "found_times") {
    block.I = "1";
  }
  if (entry.e === "check_point") {
    block.observation_ref = "obs_excel_contract_probe";
  }
  return block;
}

function _expressionBlocks(block: Record<string, any>): Array<Record<string, any>> {
  if (block.E !== "check_point") {
    return [block];
  }
  return [
    {
      kind: "STEP",
      E: "APV_0",
      F: "cmd_config",
      G: "probe",
      ref: "precedent:excel_contract",
      observation_id: "obs_excel_contract_probe",
      result_channel: "result_excel_contract_probe",
    },
    block,
  ];
}

function _capabilityBlock(name: string, atlas: any): Record<string, any> | null {
  const contract = _contract(atlas);
  const action = _executeCapabilityInfo(name, contract);
  if (action !== null) {
    if (!action.allowed_es || !action.allowed_es.length) {
      return null;
    }
    let g = String(action.name);
    if ((action.signature || {}).required && (action.signature || {}).required.length) {
      g += "：payload";
    }
    return { kind: "STEP", E: action.allowed_es[0], F: "execute", G: g, ref: "precedent:excel_contract" };
  }
  const entry = _entryForName(name, contract);
  if (entry === null) {
    return null;
  }
  return _blockForEntry(entry, contract);
}

export function enabled_entry_expression_evidence(identity: string, contract?: any): Record<string, any> {
  const source = _contract(contract);
  const sep = String(identity).indexOf("::");
  const eValue = sep < 0 ? "" : String(identity).slice(0, sep);
  const fValue = sep < 0 ? "" : String(identity).slice(sep + 2);
  if (sep < 0 || !eValue || !fValue) {
    return { name: identity, valid: false, block: null, steps: [], validated_by: "", error: "entry identity must use E::F" };
  }
  const entries = _enabledEntries(source).filter((entry) => entry.e === eValue && entry.f === fValue);
  if (entries.length !== 1) {
    return { name: identity, valid: false, block: null, steps: [], validated_by: "", error: "E::F is not one exact enabled contract entry" };
  }
  const block = _blockForEntry(entries[0], source);
  const blocks = _expressionBlocks(block);
  const { expand_blocks } = require("./blocks");
  const [steps, provenance, error] = expand_blocks(blocks);
  const bound = Boolean(steps) && (steps || []).some((step: any) => step.E === eValue && step.F === fValue);
  const bindingError = bound ? "" : `expanded steps do not contain exact ${identity}`;
  const valid = error === null && bound && Boolean(provenance);
  return {
    name: identity,
    valid,
    block,
    steps: steps || [],
    provenance: provenance || [],
    validated_by: valid ? "blocks.STEP:excel_contract+signature+exact_EF_binding" : "",
    error: error || bindingError,
  };
}

function _bindingError(name: string, steps: Array<Record<string, any>>, atlas: any): string {
  const contract = _contract(atlas);
  const action = _executeCapabilityInfo(name, contract);
  if (action !== null) {
    const { ExcelContractError, validate_execute_action } = require("./excel_contract");
    for (const step of steps) {
      if (step.F !== "execute") continue;
      let actual: any;
      try {
        actual = validate_execute_action(String(step.E || ""), String(step.G || ""), contract);
      } catch {
        continue;
      }
      if (actual.dispatcher === action.dispatcher && actual.normalized === action.normalized) {
        return "";
      }
    }
    return `queried execute action ${JSON.stringify(name)} is absent from expanded E/F/G`;
  }
  const entry = _entryForName(name, contract);
  if (entry === null) {
    return `${JSON.stringify(name)} is not an enabled contract capability`;
  }
  if (steps.some((step) => step.E === entry.e && step.F === entry.f)) {
    return "";
  }
  const label = entry.e === "check_point" ? "check_point" : "contract method";
  return `queried ${label} ${JSON.stringify(name)} expected E=${JSON.stringify(entry.e)}, F=${JSON.stringify(entry.f)}, but expanded steps do not contain it`;
}

export function capability_expression_evidence(name: string, atlas?: any): Record<string, any> {
  const source = _contract(atlas);
  const block = _capabilityBlock(name, source);
  if (block === null) {
    return { name, valid: false, block: null, steps: [], validated_by: "", error: "no blocks construction path" };
  }
  const { expand_blocks } = require("./blocks");
  const blocks = _expressionBlocks(block);
  const [steps, provenance, error] = expand_blocks(blocks);
  const bindingError = error === null ? _bindingError(name, steps || [], source) : "";
  const valid = error === null && !bindingError && Boolean(steps) && Boolean(provenance);
  return {
    name,
    valid,
    block,
    steps: steps || [],
    provenance: provenance || [],
    validated_by: valid ? "blocks.STEP:excel_contract+signature+execute_action+H/I+independent_EFG_binding" : "",
    error: error || bindingError,
  };
}

export function classify_capability(name: string, atlas?: any): string {
  if (!all_capability_names(atlas).has(name)) {
    return "out_of_range";
  }
  return capability_expression_evidence(name, atlas).valid ? "covered" : "todo";
}

export function coverage_partition(atlas?: any): [Set<string>, Set<string>] {
  const source = _contract(atlas);
  const names = all_capability_names(source);
  const covered = new Set<string>();
  for (const n of names) {
    if (classify_capability(n, source) === "covered") {
      covered.add(n);
    }
  }
  const todo = new Set([...names].filter((n) => !covered.has(n)));
  return [covered, todo];
}

export const IR_GAP_FACT_EVENTS = new Set(["ir_gap", "step_escape"]);

export function select_ir_gap_facts(facts: Array<Record<string, any>>): Array<Record<string, any>> {
  return facts.filter(
    (fact) => typeof fact === "object" && fact !== null && IR_GAP_FACT_EVENTS.has(String(fact.ev || ""))
  );
}

export function ir_gap_unresolved(todo_set: Set<string>, ir_gap_facts: Array<Record<string, any>>): Set<string> {
  const touched = new Set<string>();
  for (const fact of ir_gap_facts) {
    for (const c of fact.capabilities_touched || []) {
      touched.add(c);
    }
  }
  return new Set([...todo_set].filter((n) => touched.has(n)));
}

const _PRODUCER_EVENTS_WITH_CAPABILITIES = new Set(["composed", "mechanical_case_repaired"]);

export function production_covered(facts: Array<Record<string, any>>): Set<string> {
  const used = new Set<string>();
  for (const fact of facts) {
    if (typeof fact !== "object" || fact === null || !_PRODUCER_EVENTS_WITH_CAPABILITIES.has(fact.ev)) {
      continue;
    }
    for (const name of fact.capabilities_used || []) {
      if (String(name)) {
        used.add(String(name));
      }
    }
  }
  return used;
}
