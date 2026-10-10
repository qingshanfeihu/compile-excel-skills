import nodePath from "node:path";

import { PyValueError } from "../../../_py";
import { config_existence_check, observe_kind } from "../../../case_compiler/observe_ops";
import { IInjectionSyntaxError, parse_found_times_cells, validate_i_injection_syntax } from "../../../case_compiler/case_ir";
import {
  ExcelContractError,
  contract_entry,
  load_excel_contract,
  resolve_execution_sheet,
  validate_execute_action,
  validate_g_for_entry,
} from "../../../case_compiler/excel_contract";
import { pyRepr, reFindall } from "../../../_py";

const logger = { debug: (..._args: any[]) => {} };

const _OP_PREFIXES = ["no", "show", "clear"];
const _VALUE_TOK_RE = /^([<[{].*|.*[|].*|\d.*|["'].*|.*\.\d+.*)$/;

function _candidate_signature_hint(e: string, name: string, contract: Record<string, any>): string {
  const entry = contract_entry(e, name, contract);
  if (entry === null || entry === undefined) return "";
  const sig = entry.signature ?? {};
  const req = (sig.required ?? []).join(", ") || "(none)";
  const opt = (sig.optional ?? []).join(", ") || "(none)";
  return `${name}(required=[${req}], optional=[${opt}])`;
}

function _loadContractForGate(result: StructuralResult | null = null): Record<string, any> | null {
  try {
    return load_excel_contract();
  } catch (exc) {
    if (exc instanceof ExcelContractError) {
      if (result !== null && !result.violations.some((item) => item.code === "excel_contract_unavailable")) {
        result.add("excel_contract_unavailable", `Excel function contract is unavailable or stale: ${exc.message}; no E/F/G row in any case can be certified. This is NOT an authoring defect and no edit to this case's steps can clear it — the contract is a generated projection and has to be regenerated engine-side from the mirror. Do not reshape the case around this error; report the blocked state.`);
      }
      return null;
    }
    throw exc;
  }
}

function _contractHostSlotEs(contract: Record<string, any>): Set<string> {
  return new Set<string>(contract.objects.filter((item: any) => item.status === "enabled" && item.python_type === "ssh_server").map((item: any) => String(item.e)));
}

const _executeReturningCache = new Map<string, Set<string>>();

function _executeReturningActions(srcRel: string, sourceSha256 = ""): Set<string> {
  const key = `${srcRel} ${sourceSha256}`;
  const cached = _executeReturningCache.get(key);
  if (cached !== undefined) return cached;
  const { mirror_src } = require("../../../case_compiler/apv_lang");
  const src: string = mirror_src(srcRel);
  if (!src) {
    const empty = new Set<string>();
    _executeReturningCache.set(key, empty);
    return empty;
  }
  const mapping = new Map<string, string>();
  for (const m of src.matchAll(/'([^']+)':\s*self\.(func_\d+)/g)) {
    mapping.set(m[1], m[2]);
  }
  const returning = new Set<string>();
  for (const m of src.matchAll(/\n    def (func_\d+)\(self[^)]*\):([\s\S]*?)(?=\n    def |$)/g)) {
    if (/\n\s+return\s+\S/.test(m[2])) {
      returning.add(m[1]);
    }
  }
  const result = new Set<string>([...mapping.entries()].filter(([, fn]) => returning.has(fn)).map(([name]) => name));
  if (_executeReturningCache.size >= 4) {
    const firstKey = _executeReturningCache.keys().next().value;
    if (firstKey !== undefined) _executeReturningCache.delete(firstKey);
  }
  _executeReturningCache.set(key, result);
  return result;
}

export class StructuralViolation {
  code: string;
  detail: string;
  step_index: number;
  constructor(code: string, detail: string, step_index = -1) {
    this.code = code;
    this.detail = detail;
    this.step_index = step_index;
  }
}

export class StructuralResult {
  ok = true;
  violations: StructuralViolation[] = [];
  disabled: StructuralViolation[] = [];
  advisories: StructuralViolation[] = [];

  add(code: string, detail: string, step_index = -1): void {
    this.ok = false;
    this.violations.push(new StructuralViolation(code, detail, step_index));
  }

  disable(code: string, detail: string, step_index = -1): void {
    const { STRUCTURAL_DISABLED_CODES } = require("../../../case_compiler/gate_advisories");
    if (!STRUCTURAL_DISABLED_CODES.has(code)) {
      throw new PyValueError(`unregistered structural disabled code: ${code}`);
    }
    this.disabled.push(new StructuralViolation(code, detail, step_index));
  }

  advise(code: string, detail: string, step_index = -1): void {
    const { STRUCTURAL_ADVISORY_CODES } = require("../../../case_compiler/gate_advisories");
    if (!STRUCTURAL_ADVISORY_CODES.has(code)) {
      throw new PyValueError(`unregistered structural advisory: ${code}`);
    }
    this.advisories.push(new StructuralViolation(code, detail, step_index));
  }

  render(autoid: string): string {
    const lines = [`case ${autoid} violates structural constraints (correct-by-construction gate, independent of grade):`];
    for (const v of this.violations) {
      const loc = v.step_index >= 0 ? `step[${v.step_index}] ` : "";
      lines.push(`  - [${v.code}] ${loc}${v.detail}`);
    }
    lines.push("\nThese are intent-independent **structural** errors (command legality / whether an assertion is dangling) — deterministically decidable and they must be fixed; they are not skeleton-choice issues. Fix them and emit again.");
    return lines.join("\n");
  }
}

const _NO_PATH_LESSON_TAIL = "On the real bed such a query returns 'network unreachable' or an empty reply and every assertion consuming it is bound to fail, so the case is falsified at compile time instead of burning a device round. Move the query to an executor that has a declared leg in the target's segment (the topology supply lists the pairing) — the exemption for an address the Author wrote covers the value, never the choice of executor, so this code still fires while another executor shares that segment. When the Author's own text names this target and no bed executor has a declared leg in its segment, the blocker is a bed prerequisite rather than a case defect: do not force-emit, report it with compile_report_underdetermined(reason_code=\"environment_prerequisite_gap\") and state the missing prerequisite — intent is not mechanically visible on this surface.";

export const GATE_LESSON_TEXT: Record<string, string> = {
  found_times_invalid_shape: "found_times takes its three arguments from the row itself: G contains the static expected regex, H stays blank, I is a positive integer occurrence count, and the previous unregistered result is the actual text. Fix G/H/I instead of replacing the assertion with a weaker operator.",
  excel_contract_unavailable: "the generated Excel function contract is missing, stale, or incomplete, so no E/F/G row in any case can be certified. This is NOT an authoring defect and nothing in the steps can fix it — rewriting E/F/G, switching dispatchers, or retrying the same case all hit the same wall. The contract is a generated projection; it has to be regenerated engine-side from the mirror before compilation can continue. Report the blocked state instead of reshaping the case around the error.",
  disabled_dispatch_method: "the E/F pair exists in the generated contract but is disabled for this runtime; do not emit it until its implementation and runtime version are enabled together.",
  invalid_function_arguments: "G must bind to the exact generated Python signature. Fix missing or extra arguments, duplicate keywords, unbalanced quotes, or an invalid zero-argument call.",
  dangling_assertion: "an assertion with I empty reads the framework's last result buffer — that buffer is only set by the nearest preceding step WITHOUT H that is itself an observation (dig/show), not a config step and not a step that saved its output with H. Put a plain (no-H) observation step immediately before the assertion.",
  manual_ip_cleanup: "do not add/delete IPs or routes on test_env or host-slot steps — the framework books every add and restores by delete at the next case's start; manual del or repeated add across cases collides with that restore and crashes or pollutes later cases' echoes.",
  empty_command_payload: 'a command step\'s G must not be None/empty-ish — the framework sends it verbatim and the device rejects a literal "None" with ^. Fill the command or delete the step.',
  cmd_config_multiline: "cmd_config cannot take multiple commands in one cell — the framework strips newlines and concatenates them. Use cmds_config, one command per line.",
  literal_backslash_n: "G contains a literal backslash-n (two characters), not a newline — the framework sends it verbatim and the device rejects it. Use real newlines.",
  dead_capture: "H saves a value nobody reads. Reference it from a later assertion's G/H/I, or remove the H.",
  no_assertion_in_case: "a case with zero check_point steps verifies nothing and cannot carry a verdict. Add at least one check_point.",
  empty_assertion_pattern: "a check_point whose G/H/I are all empty always fails on the device. Write the expected value in G (the pattern), or capture with H and reference in I.",
  undefined_capture_ref: "I or G references a register no earlier step captured with H. Capture it first with H=<name>.",
  injection_without_placeholder: "I is set but G has no {} placeholder — the injected value is silently ignored. Put {} in G where the injected value belongs.",
  injection_placeholder_scope: "G's {} placeholder must be in its first positional argument; later positions and keyword arguments do not receive I.",
  injection_format_crash: "G/I injection crashes Python's .format() — the literal-brace syntax in G is invalid for the bound runtime.",
  register_shadows_framework_name: "H names a register after a framework runtime object, which the v2 runner refuses before any step executes. Rename the register (e.g. v1/ip1).",
  driver_no_declared_path: "no test-driver on this bed has a declared path from the executor to the query target — the query can never reach it. " + _NO_PATH_LESSON_TAIL,
  executor_networks_undeclared: "the executor's networks are not declared in the topology, so reachability cannot be established. " + _NO_PATH_LESSON_TAIL,
  mutation_control_after_config: "a mutation-control (observe) step sits after a config step on the same object — it observes already-mutated state and cannot serve as the mutation baseline. Move the control before the config.",
  execute_payload_required: "this execute action requires a non-empty payload after the full-width separator '：' — without it the action has nothing to act on.",
  execute_action_not_in_registry: "this execute action is not in the enabled registry for its E — the runner cannot resolve it.",
  unknown_dispatch_target: "E is not an object the framework knows — the whole step is silently skipped at runtime.",
  unknown_dispatch_method: "F is not a method of E — getattr crashes the whole pytest file.",
  assertion_regex_invalid: "the assertion regex fails to compile — the framework raises at re.compile and the entire file crashes. Fix the regex syntax.",
  line_anchor_never_matches: "static assertion regex cannot match any actual.",
  assertion_matches_command_echo: "the assertion pattern matches the command text itself, which the echo always starts with — it can never verify anything.",
  destructive_command: "a banned destructive command may not appear in a case sheet. Clean up only what this case created, with an object-scoped clear or the paired `no` form.",
  cmd_not_in_allowlist: "the command's first-level module is in no module of the verified-command footprint index — normally an out-of-scope or invented command.",
  comma_splits_parameters: "an unquoted comma in G splits the parameter into two positional arguments and mispasses it.",
  short_mode_status_assertion: "the assertion matches status/HEADER/SECTION text that +short output does not carry.",
  xlsx_unreadable: "the sheet is unreadable.",
  autoid_malformed: "the autoid row is malformed.",
  autoid_row_not_runnable: "the autoid row has an empty column E and cannot start a case.",
};

function _gateLessonSentence(code: string): string {
  const lesson = GATE_LESSON_TEXT[code] ?? "";
  return lesson.slice(0, 1).toUpperCase() + lesson.slice(1);
}

function _commandHeadTokens(cmd: string): string[] {
  let toks = cmd.trim().split(/\s+/).filter((t) => t);
  while (toks.length && _OP_PREFIXES.includes(toks[0].toLowerCase())) {
    toks = toks.slice(1);
  }
  const out: string[] = [];
  for (const t of toks) {
    const tl = t.trim().toLowerCase();
    if (!tl) continue;
    if (!/^[a-z][a-z0-9_-]*$/.test(tl) || _VALUE_TOK_RE.test(tl)) break;
    out.push(tl);
  }
  return out;
}

function _loadAllowlistPrefixes(): [Set<string>, Set<string>] {
  const full = new Set<string>();
  const roots = new Set<string>();
  try {
    const { get_footprint_index } = require("../../memory/footprint");
    const idx = get_footprint_index();
    for (const fid of idx.list_nodes()) {
      const data = idx._nodes.get(fid) ?? {};
      const behaviors = data.behaviors ?? [];
      if (!data.cli?.commands && !data.decision_rules && behaviors.length && behaviors.every((b: any) => b.validity === "uncertain")) {
        continue;
      }
      full.add(fid);
      roots.add(String(fid).split(".")[0]);
    }
  } catch (exc) {
    logger.debug("structural_gate 读 footprint 失败:", exc);
  }
  return [full, roots];
}

function _checkCommandAllowlist(steps: any[], init: string, result: StructuralResult): void {
  const [, roots] = _loadAllowlistPrefixes();
  if (roots.size === 0) {
    result.disable("command_allowlist_footprint_unavailable", "footprint 命令前缀集为空,本次未做命令头越界检查(判据缺供给,非案的问题)");
    return;
  }
  const _checkOne = (cmd: string, idx: number): void => {
    const head = _commandHeadTokens(cmd);
    if (!head.length) return;
    const module_ = head[0];
    if (!roots.has(module_)) {
      result.add("cmd_not_in_allowlist", `command ${pyRepr(cmd)}: its first-level module ${pyRepr(module_)} is in no module of the verified-command footprint index (modules on record: ${[...roots].sort().join(", ")}) — normally an out-of-scope or invented command. This gate judges the module root only (unknown sub-commands are logged, not refused) and the footprint index is NOT the authority on whether a command exists — the build-bound XML command tree is. Check the module name against that tree; if this command really does exist in this build, report that instead of quietly swapping in a different command.`, idx);
    }
  };
  const { _ordered_apv_command_refs } = require("./emit_xlsx_tool");
  for (const ref of _ordered_apv_command_refs(steps, init)) {
    _checkOne(String(ref.command ?? ""), Number(ref.step_index ?? -1));
  }
}

function _checkCommandExistenceSameSource(steps: any[], init: string, result: StructuralResult, opts: { device_build?: string } = {}): void {
  const deviceBuild = opts.device_build ?? "";
  const { CommandTreeUnavailable } = require("../compile_engine/engine_errors");
  const {
    COMMAND_PARAMETER_CONTRACT_CODE,
    COMMAND_NOT_IN_TREE_CODE,
    _command_tree_context,
    _looks_like_shell,
    _ordered_apv_command_refs,
    command_existence_verdict,
  } = require("./emit_xlsx_tool");
  const commandRefs = _ordered_apv_command_refs(steps, init);
  if (!commandRefs.length) return;
  const loadedContext = _command_tree_context({ device_build: deviceBuild });
  for (const commandRef of commandRefs) {
    const command = commandRef.command;
    const verdict = command_existence_verdict(command, { device_build: deviceBuild, _loaded_context: loadedContext });
    if (verdict.kind === "tree_unavailable") {
      throw new CommandTreeUnavailable(verdict.detail, { device_build: verdict.device_build || deviceBuild });
    }
    if (verdict.kind === "hit" && !verdict.parameters_valid) {
      result.add(COMMAND_PARAMETER_CONTRACT_CODE, `command ${pyRepr(command)}: its head exists in build ${verdict.device_build || "?"} but the supplied arguments violate the build-bound XML parameter contract; head=${pyRepr(verdict.head)}, parameter_error=${pyRepr(verdict.parameter_error)}. Re-read the exact XML-backed signature and correct this command before sealing.`, commandRef.step_index);
      continue;
    }
    if (verdict.kind !== "missing") continue;
    let detail: string;
    if (_looks_like_shell(command)) {
      detail = `command ${pyRepr(command)} is not a CLI command in this build. E=APV_* G may contain only build-bound product CLI commands (DESIGN §26.7); use an equivalent CLI observation or report that the case cannot be compiled.`;
    } else {
      const missingHead = String(verdict.head ?? command);
      detail = `command head ${pyRepr(missingHead)} is absent from build ${verdict.device_build || "?"} XML command tree` + (missingHead !== command ? ` (full command ${pyRepr(command)})` : "") + ". E=APV_* G may contain only commands from that tree (DESIGN §2.2/§26.7).";
    }
    result.add(COMMAND_NOT_IN_TREE_CODE, detail, commandRef.step_index);
  }
}

function _isObservationStep(step: Record<string, any>): boolean {
  const e = String(step.E ?? "").trim();
  const f = String(step.F ?? "").trim();
  let contract: any;
  try {
    contract = load_excel_contract();
  } catch (exc) {
    if (exc instanceof ExcelContractError) return false;
    throw exc;
  }
  const entry = contract_entry(e, e === "test_env" ? f.toLowerCase() : f, contract);
  if (entry === null || entry === undefined || entry.status !== "enabled") return false;
  if (e === "test_env") return true;
  if (f === "cmd" || f === "cmd_config") return true;
  if (f !== "execute") return false;
  const g = String(step.G ?? "").trim();
  let actionContract: Record<string, any>;
  try {
    actionContract = validate_execute_action(e, g, contract);
  } catch (exc) {
    if (exc instanceof ExcelContractError) return false;
    throw exc;
  }
  const { APV_ACTION_SRC, CLIENT_ACTION_SRC } = require("../../../case_compiler/apv_lang");
  const src = actionContract.dispatcher === "client" ? CLIENT_ACTION_SRC : APV_ACTION_SRC;
  return _executeReturningActions(src, String(contract.source_hashes[src] ?? "")).has(actionContract.name);
}

function _checkDanglingAssertions(steps: any[], result: StructuralResult): void {
  let resultIsObserve = false;
  let observeBoundTo: [number, string] | null = null;
  let consecutiveObserves: Array<[number, string]> = [];
  for (let i = 0; i < steps.length; i++) {
    const s = steps[i];
    if (typeof s !== "object" || s === null || Array.isArray(s)) continue;
    const e = String(s.E ?? "").trim();
    const f = String(s.F ?? "").trim();
    const h = String(s.H ?? "").trim();
    const iCol = String(s.I ?? "").trim();
    if (e === "check_point") {
      const readsResult = f === "found_times" || !iCol;
      if (readsResult && resultIsObserve && consecutiveObserves.length >= 2) {
        const earlier = consecutiveObserves.slice(0, -1).map(([n, c]) => `step[${n}] ${pyRepr(c.slice(0, 30))}`).join("、");
        const [boundN, boundC] = consecutiveObserves[consecutiveObserves.length - 1];
        result.advise("ambiguous_observation_binding", `this assertion consumes only the echo of step[${boundN}] (${pyRepr(boundC.slice(0, 40))}); the earlier consecutive observation(s) ${earlier} produced echoes nothing reads — either dead observations, or the assertion was meant to read one of them (mis-binding). Put each assertion immediately after the observation it verifies, or capture earlier echoes with H and reference them explicitly.`, i);
      }
      if (readsResult) {
        consecutiveObserves = [];
      }
      if (readsResult && !resultIsObserve) {
        result.add("dangling_assertion", "this assertion reads the framework result but no valid observation echo is held there → framework result=None, found(None) raises TypeError and **crashes the entire file** (no case after this one runs). Cause: the nearest preceding step without H is a config step (cmds_config returns None), or every earlier observation step carries H (save_as does not update result). Fix: put an observation step **without H** (dig/show) **immediately before** the assertion so its echo becomes result; for capture-compare use the three-step form dig(H=v1) → dig(no H) → check_point(H=v1).", i);
      }
    } else if (!h) {
      if (_isObservationStep(s)) {
        resultIsObserve = true;
        observeBoundTo = [i, String(s.G ?? "")];
        consecutiveObserves.push(observeBoundTo);
      } else {
        resultIsObserve = false;
        observeBoundTo = null;
        consecutiveObserves = [];
      }
    }
  }
}

function _checkDeadCapture(steps: any[], result: StructuralResult): void {
  const captured = new Map<string, number>();
  const referenced = new Set<string>();
  for (let i = 0; i < steps.length; i++) {
    const s = steps[i];
    if (typeof s !== "object" || s === null || Array.isArray(s)) continue;
    const e = String(s.E ?? "").trim();
    const h = String(s.H ?? "").trim();
    const iCol = String(s.I ?? "").trim();
    if (iCol && !(e === "check_point" && String(s.F ?? "").trim() === "found_times")) {
      referenced.add(iCol);
    }
    if (e === "check_point") {
      if (h) referenced.add(h);
    } else if (h) {
      captured.set(h, i);
    }
  }
  for (const [reg, idx] of captured) {
    if (!referenced.has(reg)) {
      result.add("dead_capture", `register '${reg}' is captured via save_as but is **never referenced by any check_point** (neither as the H for expect nor as the I for the text under test) = a register written but never read — a dead action / incomplete assertion. Typical: dig captures into '${reg}' with H yet the check_point reads result via found (the immediately preceding step is often a show config echo → asserting against the wrong buffer), with no abs_found(H='${reg}') consuming it → the dig behavior is never verified and the assertion reads the wrong buffer. Fix: reference '${reg}' with check_point abs_found (three-step form dig(H=${reg})→dig(no H)→check_point(H=${reg})), or delete the useless capture.`, idx);
    }
  }
}

export function check_structural_constraints(autoid: string, steps: any, init = ""): StructuralResult {
  const result = new StructuralResult();
  if (!Array.isArray(steps)) return result;
  _checkCommandAllowlist(steps, init, result);
  _checkDanglingAssertions(steps, result);
  _checkFoundTimesShape(steps, result);
  _checkDispatchTargets(steps, result);
  _checkContractGSyntax(steps, result);
  _checkDeadCapture(steps, result);
  return result;
}

function _checkFoundTimesShape(steps: any[], result: StructuralResult): void {
  for (let i = 0; i < steps.length; i++) {
    const s = steps[i];
    if (typeof s !== "object" || s === null || Array.isArray(s)) continue;
    if (String(s.E ?? "").trim() === "check_point" && String(s.F ?? "").trim() === "found_times") {
      try {
        parse_found_times_cells(s.G, s.H, s.I);
      } catch (exc) {
        if (exc instanceof PyValueError) {
          result.add("found_times_invalid_shape", `${exc.message}; G supplies the static expected regex, H stays blank, and the previous unregistered result is the actual text under test.`, i);
        } else {
          throw exc;
        }
      }
    }
  }
}

function _destructivePatterns(): [RegExp[], string | null] {
  let pats: any[];
  try {
    const { load_grammar } = require("../../../case_compiler/domain_grammar");
    pats = (load_grammar().destructive_commands ?? {}).patterns ?? [];
  } catch (exc) {
    console.warn("destructive_commands 文法读取失败——自毁命令规则本次未检查", exc);
    return [[], `grammar unreadable (${(exc as any)?.constructor?.name ?? "Error"}: ${exc})`];
  }
  if (!pats.length) {
    return [[], "grammar carries no destructive_commands.patterns entries"];
  }
  try {
    return [pats.map((p) => new RegExp(String(p), "i")), null];
  } catch (exc) {
    console.warn("destructive_commands 正则编译失败——自毁命令规则本次未检查", exc);
    return [[], `pattern compile failed (${(exc as any)?.constructor?.name ?? "Error"}: ${exc})`];
  }
}

function _checkNoDestructiveCommands(steps: any[], result: StructuralResult): void {
  const { _apv_command_lines_for_step, is_apv_command_step } = require("./emit_xlsx_tool");
  const [pats, unavailable] = _destructivePatterns();
  if (unavailable !== null) {
    result.disable("destructive_command", `destructive-command gate did not run: ${unavailable}. Commands that wipe the whole device configuration (management IP included) were NOT screened in this volume — the bed-killing class this rule exists for is unguarded here.`);
    return;
  }
  for (let i = 0; i < (steps ?? []).length; i++) {
    const s = steps[i];
    if (typeof s !== "object" || s === null || Array.isArray(s)) continue;
    if (!is_apv_command_step(s, { methods: null })) continue;
    for (let line of _apv_command_lines_for_step(steps, i)) {
      line = line.trim();
      if (!line) continue;
      const matched = pats.find((p) => p.test(line));
      if (matched !== undefined) {
        result.add("destructive_command", `step ${i + 1}: ${pyRepr(line)} matches banned destructive-command rule ${pyRepr(matched.source)} (grammar \`destructive_commands.patterns\`, the single source this rule and the emit rules both read). Two kinds live in that set and a case sheet may carry neither: whole-device config wipes, which take the management IP down with everything else (two beds were killed this way on 2026-07-13 and needed console recovery), and device lifecycle commands, which really restart or power down a bed other runs are sharing. Framework capability is not the limit — the framework does ship a reboot helper that waits the device back up — but that helper is declared disabled in the Excel contract as a device-wide lifecycle helper, so no step can reach it: the ban is bed-sharing discipline, not a missing capability. Clean up only what this case created, with an object-scoped clear or the paired \`no\` form of what it configured. If the case objective genuinely needs the device to restart, it cannot be compiled for a shared bed — report it as not compilable instead of force-emitting.`);
      }
    }
  }
}

function _checkNoManualIpCleanup(steps: any[], result: StructuralResult): void {
  const contract = _loadContractForGate(result);
  if (contract === null) return;
  const hostSlots = _contractHostSlotEs(contract);
  for (let i = 0; i < steps.length; i++) {
    const s = steps[i];
    if (typeof s !== "object" || s === null || Array.isArray(s)) continue;
    const e = String(s.E ?? "").trim();
    const g = String(s.G ?? "").split(/\s+/).filter((x) => x).join(" ");
    if ((e === "test_env" || hostSlots.has(e)) && (g.includes("ip addr ") || g.includes("ip address ") || g.includes("ip route ") || g.includes("ip -6 route ")) && (g.includes(" add") || g.includes(" del"))) {
      result.add("manual_ip_cleanup", "this step changes test-env host IPs/routes (add/del via ip addr / ip route) — the framework auto-books every add (without dedup) and restores by delete at the start of the next case: deleting on your own, or repeating the same add across cases, makes that restore fail, **crashing the entire file or polluting later cases' echo with RTNETLINK residue (batches of fake fails)**. Delete this step — host network state is managed by the framework; for multiple sources use the topology's existing trigger hosts, and for a new path check the topology's existing reachability first.", i);
    }
  }
}

function _checkDispatchTargets(steps: any[], result: StructuralResult): void {
  const contract = _loadContractForGate(result);
  if (contract === null) return;
  const objectNames = new Set<string>(contract.objects.map((item: any) => String(item.e)));
  for (let i = 0; i < steps.length; i++) {
    const s = steps[i];
    if (typeof s !== "object" || s === null || Array.isArray(s)) continue;
    const e = String(s.E ?? "").trim();
    const f = String(s.F ?? "").trim();
    if (!e) continue;
    if (!objectNames.has(e)) {
      result.add("unknown_dispatch_target", `E=${pyRepr(e)} is not in the framework devices table (valid: ${[...objectNames].sort().join(", ")}) — for an unknown E the framework **silently skips the whole step** (not executed, no log, no exception), and later assertions run against the wrong buffer. Fix it against excel_contract.json.`, i);
      continue;
    }
    const fNorm = e === "test_env" ? f.toLowerCase() : f;
    const entry = contract_entry(e, fNorm, contract);
    if (entry === null || entry === undefined) {
      const allowed = new Set<string>(contract.entries.filter((item: any) => item.e === e && item.status === "enabled").map((item: any) => String(item.f)));
      const { nearest_candidates } = require("../../../case_compiler/apv_lang");
      const ranked: string[] = nearest_candidates(fNorm, allowed, { top_n: 5 });
      const hinted = ranked.map((c) => _candidate_signature_hint(e, c, contract) || c);
      result.add("unknown_dispatch_method", `F=${pyRepr(f)} is not a valid method of the E=${e} object — the framework getattr has no default, so a misspelled method name raises **AttributeError and crashes the entire file**. Nearest candidates (ranked by similarity, for reference only — confirm deliberately, this rule never auto-rewrites; signature shown inline where known): ${hinted.join("、")}. Full enabled set (${allowed.size}): ${[...allowed].sort().join(", ")}. Fix it against the E/F entry in excel_contract.json.`, i);
      continue;
    }
    if (entry.status !== "enabled") {
      result.add("disabled_dispatch_method", `E=${pyRepr(e)}, F=${pyRepr(fNorm)} is declared but ${entry.status}: ${entry.reason} (minimum runtime ${entry.minimum_runtime}).`, i);
    }
  }
}

function _checkContractGSyntax(steps: any[], result: StructuralResult): void {
  const contract = _loadContractForGate(result);
  if (contract === null) return;
  for (let i = 0; i < steps.length; i++) {
    const step = steps[i];
    if (typeof step !== "object" || step === null || Array.isArray(step)) continue;
    const e = String(step.E ?? "").trim();
    const f = String(step.F ?? "").trim();
    const fNorm = e === "test_env" ? f.toLowerCase() : f;
    const entry = contract_entry(e, fNorm, contract);
    if (entry === null || entry === undefined || entry.status !== "enabled") continue;
    if (entry.dispatch === "execute_registry") continue;
    const g = String(step.G ?? "");
    if (f === "cmd_config" && (g.includes("\n") || g.includes("\r"))) continue;
    try {
      validate_g_for_entry(entry, g, contract);
    } catch (exc) {
      if (exc instanceof ExcelContractError) {
        result.add("invalid_function_arguments", `E=${pyRepr(e)}, F=${pyRepr(fNorm)} cannot bind G to ${entry.signature.text}: ${exc.message}`, i);
      } else {
        throw exc;
      }
    }
  }
}

function _checkCommandPayloadSanity(steps: any[], result: StructuralResult): void {
  const contract = _loadContractForGate(result);
  if (contract === null) return;
  for (let i = 0; i < steps.length; i++) {
    const s = steps[i];
    if (typeof s !== "object" || s === null || Array.isArray(s)) continue;
    const e = String(s.E ?? "").trim();
    const f = String(s.F ?? "").trim();
    const entry = contract_entry(e, e === "test_env" ? f.toLowerCase() : f, contract);
    if (entry === null || entry === undefined || !["cmd_primitive", "direct_method_call", "execute_registry"].includes(entry.dispatch)) continue;
    const gRaw = s.G;
    const g = gRaw !== null && gRaw !== undefined ? String(gRaw) : "";
    if (gRaw === null || gRaw === undefined || g.trim().toLowerCase() === "none") {
      result.add("empty_command_payload", 'command step column G is None/literal "None" — the framework str()-ifies it and sends it as-is; the device receives "None" and always rejects it with ^. Fill in a real command or delete the step (a pure empty-string placeholder step is harmless and not covered here).', i);
    } else if (f === "cmd_config" && (g.trim().includes("\n") || g.trim().includes("\r"))) {
      result.add("cmd_config_multiline", "cmd_config's G contains newlines — the framework first replace()-strips all newlines for cmd_config （框架执行器出处已脱敏）, so multiple commands get **concatenated with no separator** and sent as one line; the device always rejects it with ^. Use cmds_config for multiple commands (sent line by line).", i);
    } else if (g.includes("\\n")) {
      result.add("literal_backslash_n", "command column G contains a **literal** \\\\n (backslash + n, two characters, not a newline) — multiple commands get joined into one line and sent; the device always rejects at the second command with ^. Separate multiple commands with **real newlines** (the \\n escape written in JSON is restored to a newline by parsing; if you wrote \\\\\\\\n in the string it became a literal backslash — fix it).", i);
    }
  }
}

function _checkExecuteActionRegistry(steps: any[], result: StructuralResult): void {
  const contract = _loadContractForGate(result);
  if (contract === null) return;
  for (let i = 0; i < steps.length; i++) {
    const s = steps[i];
    if (typeof s !== "object" || s === null || Array.isArray(s)) continue;
    if (String(s.F ?? "").trim() !== "execute") continue;
    const eValue = String(s.E ?? "").trim();
    const raw = String(s.G ?? "");
    try {
      validate_execute_action(eValue, raw, contract);
    } catch (exc) {
      if (exc instanceof ExcelContractError) {
        const detail = String(exc.message);
        const code = detail.includes("requires a non-empty payload") ? "execute_payload_required" : "execute_action_not_in_registry";
        result.add(code, `${detail}. execute uses the whole G cell as one action argument and must match the E-bound generated contract exactly; this rule covers only F=execute action routing and never rewrites it. Direct Python methods belong in F and are declared by their E/F pair in excel_contract.json. Distribution and membership assertions use the compiler combinators OBSERVE_DIST and OBSERVE_MEMBER; neither is an execute action.`, i);
      } else {
        throw exc;
      }
    }
  }
}

const _DEST_ANCHOR_RE = /(?:@|:\/\/)\[?([0-9A-Fa-f:.]+)\]?/g;

function _isIpAddress(tok: string): boolean {
  if (/^\d{1,3}(\.\d{1,3}){3}$/.test(tok)) return true;
  return tok.includes(":") && /^[0-9A-Fa-f:.]+$/.test(tok);
}

function _extractQueryDestinations(g: string): string[] {
  const out: string[] = [];
  for (const m of String(g ?? "").matchAll(_DEST_ANCHOR_RE)) {
    let tok = m[1].trim().replace(/\.+$/, "");
    if (tok.split(":").length === 2 && tok.includes(".")) {
      const idx = tok.lastIndexOf(":");
      const host = tok.slice(0, idx);
      const port = tok.slice(idx + 1);
      if (/^\d+$/.test(port)) tok = host;
    }
    if (!_isIpAddress(tok.split("%")[0])) continue;
    if (!out.includes(tok)) out.push(tok);
  }
  return out;
}

function _checkDriverNoDeclaredPath(steps: any[], result: StructuralResult, opts: { author_ip_literals?: Iterable<string> | null; author_hits?: Array<Record<string, any>> | null } = {}): void {
  const { normalize_ip_literal, require_env_facts } = require("../_shared/env_facts");
  const facts = require_env_facts();
  const authorSet = new Set<string>([...(opts.author_ip_literals ?? [])].map((value) => normalize_ip_literal(value)).filter((v: string) => v));
  const contract = _loadContractForGate(null);
  let teHosts = new Set<string>();
  let slotHosts = new Set<string>();
  if (contract !== null) {
    teHosts = new Set<string>(contract.entries.filter((item: any) => item.e === "test_env" && item.status === "enabled").map((item: any) => String(item.f ?? "").trim().toLowerCase()));
    slotHosts = new Set<string>([..._contractHostSlotEs(contract)].map((s) => s.toLowerCase()));
  }
  const driverRows = new Map<number, [string, string[]]>();
  const saveVar = new Map<number, string>();
  for (let i = 0; i < steps.length; i++) {
    const s = steps[i];
    if (typeof s !== "object" || s === null || Array.isArray(s)) continue;
    const e = String(s.E ?? "").trim();
    const f = String(s.F ?? "").trim();
    if (e === "check_point") continue;
    let executor = "";
    if (e === "test_env" && f) {
      const fl = f.toLowerCase();
      if ((contract !== null && teHosts.has(fl)) || (contract === null && facts.is_driver_device(fl))) {
        executor = fl;
      }
    } else if ((contract !== null && slotHosts.has(e.toLowerCase())) || (contract === null && facts.is_driver_device(e))) {
      executor = e.toLowerCase();
    }
    if (!executor) continue;
    const dests = _extractQueryDestinations(String(s.G ?? ""));
    if (!dests.length) continue;
    driverRows.set(i, [executor, dests]);
    const h = String(s.H ?? "").trim();
    if (h) saveVar.set(i, h);
  }
  if (driverRows.size === 0) return;
  const consuming = new Map<number, number>();
  let lastNoHIdx = -1;
  for (let i = 0; i < steps.length; i++) {
    const s = steps[i];
    if (typeof s !== "object" || s === null || Array.isArray(s)) continue;
    const e = String(s.E ?? "").trim();
    const f = String(s.F ?? "").trim();
    const h = String(s.H ?? "").trim();
    const iCol = String(s.I ?? "").trim();
    if (e === "check_point") {
      const readsResult = f === "found_times" || !iCol;
      if (readsResult && driverRows.has(lastNoHIdx)) {
        if (!consuming.has(lastNoHIdx)) consuming.set(lastNoHIdx, i);
      }
      for (const ref of [iCol, h]) {
        if (!ref) continue;
        const cands = [...saveVar.entries()].filter(([j, v]) => v === ref && j < i).map(([j]) => j);
        if (cands.length) {
          const mx = Math.max(...cands);
          if (!consuming.has(mx)) consuming.set(mx, i);
        }
      }
    } else if (!h) {
      lastNoHIdx = i;
    }
  }
  const { normalize_ip_literal: normalizeIpLiteral } = require("../_shared/env_facts");
  const js = [...consuming.keys()].filter((j) => driverRows.has(j)).sort((a, b) => a - b);
  for (const j of js) {
    const [executor, dests] = driverRows.get(j)!;
    for (const dest of dests) {
      const verdict = facts.executor_path_verdict(executor, dest);
      if (verdict === null || verdict === undefined) continue;
      const segs = verdict.dest_segments.join(", ") || "none — this IP is in no declared segment of the bed";
      const peers = verdict.reachable_drivers;
      const peerNote = peers.length ? `Test-drivers that do share the target's declared segment: ${peers.join(", ")}` : "No test-driver shares the target's declared segment — no driver can reach it at all";
      if (authorSet.size && !peers.length && authorSet.has(normalizeIpLiteral(dest))) {
        result.advise("driver_no_declared_path_author_sourced", `this step queries ${dest} from executor '${verdict.executor}', and step[${consuming.get(j)}]'s assertion consumes that reply; no test-driver on this bed has a declared path to that target (target's declared segment(s): [${segs}]). The address is written verbatim in the sealed Author case, so this is an execution-environment disclosure, not a case rejection: the case proceeds and the limitation is reported; expected is not rewritten.`, j);
        if (opts.author_hits !== null && opts.author_hits !== undefined) {
          opts.author_hits.push({ step_index: j, consuming_step_index: consuming.get(j), executor: String(verdict.executor), target: String(dest), dest_segments: [...verdict.dest_segments], executor_networks: [...(verdict.executor_networks ?? [])], networks_undeclared: Boolean(verdict.networks_undeclared) });
        }
        continue;
      }
      if (verdict.networks_undeclared) {
        result.add("executor_networks_undeclared", `this step queries ${dest} from executor '${verdict.executor}', and step[${consuming.get(j)}]'s assertion consumes that reply. Target's declared segment(s) on this bed: [${segs}]. ${peerNote} (derived from the topology fact source). ` + _gateLessonSentence("executor_networks_undeclared"), j);
        continue;
      }
      const nets = verdict.executor_networks.join(", ") || "none declared";
      result.add("driver_no_declared_path", `this step queries ${dest} from executor '${verdict.executor}', and step[${consuming.get(j)}]'s assertion consumes that reply. Executor's declared segments: [${nets}]; target's declared segment(s) on this bed: [${segs}]; no explicit route declaration covers it either. ${peerNote} (derived from the topology fact source). ` + _gateLessonSentence("driver_no_declared_path"), j);
    }
  }
}

function _checkMutationControlOrder(steps: any[], result: StructuralResult): void {
  const { mutation_control_order_failure } = require("../../../case_compiler/mutation_testing");
  const failure: string = mutation_control_order_failure(steps);
  if (failure) {
    result.add("mutation_control_after_config", failure);
  }
}

export function check_crash_gates_mandatory(steps: any): StructuralResult {
  const result = new StructuralResult();
  if (Array.isArray(steps)) {
    _checkFoundTimesShape(steps, result);
    _checkDanglingAssertions(steps, result);
    _checkNoManualIpCleanup(steps, result);
    _checkCommandPayloadSanity(steps, result);
    _checkDispatchTargets(steps, result);
    _checkContractGSyntax(steps, result);
    _checkExecuteActionRegistry(steps, result);
    _checkAssertionRegexCompiles(steps, result);
    _checkLineAnchorAssertions(steps, result);
    _checkAssertionMatchesCommandEcho(steps, result);
    _checkHasAssertion(steps, result);
    _checkEmptyAssertionPattern(steps, result);
    _checkCaptureRefsDefined(steps, result);
    _checkNoDestructiveCommands(steps, result);
    _checkMutationControlOrder(steps, result);
  }
  return result;
}

export function lint_draft(steps: any, opts: { init?: string; final?: boolean; device_build?: string; author_ip_literals?: Iterable<string> | null; author_driver_hits?: Array<Record<string, any>> | null } = {}): StructuralResult {
  const final = opts.final ?? false;
  const result = check_crash_gates_mandatory(steps);
  if (!final) {
    const kept: StructuralViolation[] = [];
    for (const v of result.violations) {
      if (v.code === "no_assertion_in_case") {
        result.advise(v.code, "draft not finished yet — no check_point step written so far in this prefix; this is informational, not a violation (you may simply not have reached the assertion step). It becomes a real block once you call compile_lint(final=True) before emit, or reach compile_emit with the case still missing an assertion.", v.step_index);
      } else {
        kept.push(v);
      }
    }
    result.violations = kept;
    result.ok = result.violations.length === 0;
  }
  const dcProbe = new StructuralResult();
  _checkDeadCapture(steps, dcProbe);
  for (const v of dcProbe.violations) {
    result.advise(v.code, v.detail, v.step_index);
  }
  _checkCommandAllowlist(steps, opts.init ?? "", result);
  _checkCommandExistenceSameSource(steps, opts.init ?? "", result, { device_build: opts.device_build ?? "" });
  _checkDriverNoDeclaredPath(steps, result, { author_ip_literals: opts.author_ip_literals ?? null, author_hits: opts.author_driver_hits ?? null });
  _checkConfigExistenceAdvisories(steps, result);
  return result;
}

const _AUTOID_RE = /^\d{18}$/;
const _SHORT_INCOMPATIBLE_RE = /status:|->>HEADER<<-|ANSWER SECTION|QUESTION SECTION/;
const _WORKBOOK_MODEL_CAP = 1536;
const _workbookModelCache = new Map<string, [string, Array<Record<string, string>>, string[]]>();

function _parseWorkbookModel(xlsxPath: string, opts: { allow_legacy: boolean }): [string, Array<Record<string, string>>, string[]] {
  const { load_workbook } = require("../../../case_compiler/_openpyxl_compat");
  const wb = load_workbook(xlsxPath);
  const [ws, layout] = resolve_execution_sheet(wb, { allow_legacy: opts.allow_legacy });
  let autoid = "";
  const steps: Array<Record<string, string>> = [];
  const emptyEAutoids: string[] = [];
  for (let rowNo = layout.data_start; rowNo <= ws.rowCount; rowNo++) {
    const row = ws.getRow(rowNo);
    const cellText = (col: number): string => String(row.getCell(col).value ?? "").trim();
    const a = cellText(1);
    const e = cellText(5);
    const isAutoidRow = /^\d+$/.test(a) && a.length >= 12 && a !== "999999999999999";
    if (isAutoidRow) {
      if (!autoid) autoid = a;
      if (!e) emptyEAutoids.push(a);
    }
    if (!e) continue;
    steps.push({ D: String(row.getCell(4).value ?? ""), E: e, F: String(row.getCell(6).value ?? ""), G: String(row.getCell(7).value ?? ""), H: String(row.getCell(8).value ?? ""), I: row.getCell(9).value !== undefined && row.getCell(9).value !== null ? String(row.getCell(9).value) : "" });
  }
  return [autoid, steps, emptyEAutoids];
}

function _workbookModel(xlsxPath: string, opts: { allow_legacy?: boolean } = {}): [string, Array<Record<string, string>>, string[]] {
  const allowLegacy = opts.allow_legacy ?? true;
  const { file_identity } = require("../../common/file_identity");
  let identity: any;
  try {
    identity = file_identity(nodePath.resolve(xlsxPath));
  } catch (exc) {
    if (exc instanceof TypeError || (exc as any)?.code) {
      const [autoid, steps, emptyEAutoids] = _parseWorkbookModel(xlsxPath, { allow_legacy: allowLegacy });
      return [autoid, steps.map((s) => ({ ...s })), [...emptyEAutoids]];
    }
    const [autoid, steps, emptyEAutoids] = _parseWorkbookModel(xlsxPath, { allow_legacy: allowLegacy });
    return [autoid, steps.map((s) => ({ ...s })), [...emptyEAutoids]];
  }
  const [resolved, size, mtimeNs, digest] = identity;
  const key = JSON.stringify([resolved, size, mtimeNs, digest, Boolean(allowLegacy)]);
  let hit = _workbookModelCache.get(key);
  if (hit !== undefined) {
    _workbookModelCache.delete(key);
    _workbookModelCache.set(key, hit);
  }
  if (hit === undefined) {
    const model = _parseWorkbookModel(xlsxPath, { allow_legacy: allowLegacy });
    let after: any = null;
    try {
      after = file_identity(nodePath.resolve(xlsxPath));
    } catch {
      after = null;
    }
    if (after !== null && JSON.stringify(after) === JSON.stringify(identity)) {
      _workbookModelCache.set(key, model);
      while (_workbookModelCache.size > _WORKBOOK_MODEL_CAP) {
        const firstKey = _workbookModelCache.keys().next().value;
        if (firstKey === undefined) break;
        _workbookModelCache.delete(firstKey);
      }
    }
    hit = model;
  }
  const [autoid, steps, emptyEAutoids] = hit;
  return [autoid, steps.map((s) => ({ ...s })), [...emptyEAutoids]];
}

export function clear_workbook_model_cache(): void {
  _workbookModelCache.clear();
}

export function steps_from_xlsx(xlsxPath: string, opts: { allow_legacy?: boolean } = {}): [string, Array<Record<string, string>>] {
  const [autoid, steps] = _workbookModel(xlsxPath, { allow_legacy: opts.allow_legacy ?? true });
  return [autoid, steps];
}

function _checkLineAnchorAssertions(steps: any[], result: StructuralResult): void {
  const { RegexAnchorAnalysisUnavailable, analyze_regex_anchors } = require("../../../case_compiler/regex_anchor_proof");
  for (let i = 0; i < steps.length; i++) {
    const s = steps[i];
    if (typeof s !== "object" || s === null || Array.isArray(s)) continue;
    if (String(s.E ?? "").trim() !== "check_point") continue;
    const f = String(s.F ?? "").trim();
    const g = String(s.G ?? "");
    if (!["found", "not_found"].includes(f) || !g || String(s.H ?? "").trim()) continue;
    let analysis: any;
    try {
      analysis = analyze_regex_anchors(g);
    } catch (exc) {
      if (exc instanceof RegexAnchorAnalysisUnavailable) {
        result.disable("regex_anchor_analysis_unavailable", String(exc instanceof Error ? exc.message : exc), i);
        continue;
      }
      throw exc;
    }
    if (analysis.contradiction) {
      result.add("line_anchor_never_matches", `static assertion regex cannot match any actual: ${analysis.contradiction}. ` + (f === "not_found" ? "The not_found assertion therefore always passes." : "The found assertion therefore always fails."), i);
    } else if (analysis.window_boundary_dependent && !String(s.I ?? "").trim()) {
      result.advise("line_anchor_window_unverified", "this pattern anchors on the start/end boundary of the whole output window; whether the expected data sits on that boundary depends on the live echo layout, so no pass/fail was decided from it this time", i);
    }
  }
}

function _isMapping(v: any): v is Record<string, any> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function _echoSrcCmd(e: string, f: string, hostSlots: Set<string>, contract: any = null): boolean {
  if (e === "test_env") return true;
  if (hostSlots.has(e) && f === "cmd") return true;
  if (contract !== null) {
    const entry = contract_entry(e, f, contract);
    if (_isMapping(entry) && entry.dispatch === "cmd_primitive") {
      const required = _isMapping(entry.signature) ? entry.signature.required : null;
      const first = String((required ?? [""])[0] ?? "");
      return first === "cmd";
    }
  }
  return e.startsWith("APV") && f === "cmd_config";
}

function _checkAssertionMatchesCommandEcho(steps: any[], result: StructuralResult): void {
  const contract = _loadContractForGate(result);
  if (contract === null) return;
  const hostSlots = _contractHostSlotEs(contract);
  let lastSrcG: string | null = null;
  const regSrc = new Map<string, string>();
  for (let i = 0; i < steps.length; i++) {
    const s = steps[i];
    if (typeof s !== "object" || s === null || Array.isArray(s)) continue;
    const e = String(s.E ?? "").trim();
    const f = String(s.F ?? "").trim();
    const g = String(s.G ?? "");
    const h = String(s.H ?? "").trim();
    const iCol = String(s.I ?? "").trim();
    if (e === "check_point") {
      if (h || !g.trim() || !["found", "not_found", "abs_found"].includes(f)) continue;
      const src = iCol ? regSrc.get(iCol) : lastSrcG;
      if (!src) continue;
      let hit: boolean;
      try {
        hit = f === "abs_found" ? src.includes(g) : new RegExp(g, "s").test(src);
      } catch {
        continue;
      }
      if (hit) {
        result.add("assertion_matches_command_echo", `assertion ${f}'s pattern already matches the **command text itself** of the step sourcing its window (${pyRepr(src.slice(0, 60))}…) — the window always starts with the command echo, so this assertion is ` + (f === "not_found" ? '**always-fail** (it tries to verify "output contains no X" but X is in the command).' : "**always-true fake PASS** (it passes no matter what the device outputs, verifying nothing).") + " Rewrite it to match a data line, distinguishable from the command text.", i);
      }
      continue;
    }
    if (h) {
      if (_echoSrcCmd(e, f, hostSlots, contract)) {
        regSrc.set(h, g);
      } else {
        regSrc.delete(h);
      }
    } else {
      lastSrcG = _echoSrcCmd(e, f, hostSlots, contract) ? g : null;
    }
  }
}

function _checkHasAssertion(steps: any[], result: StructuralResult): void {
  for (const s of steps) {
    if (typeof s === "object" && s !== null && !Array.isArray(s) && String(s.E ?? "").trim() === "check_point") {
      return;
    }
  }
  if (steps.length) {
    result.add("no_assertion_in_case", "this case has no check_point step at all — framework settlement judges success==0 as FAIL (check_point.py:126), so a config-only/observation-only sheet is always-fail on the device. Add at least one assertion; steps that only execute without verifying do not constitute a test case.", 0);
  }
}

function _checkEmptyAssertionPattern(steps: any[], result: StructuralResult): void {
  for (let i = 0; i < steps.length; i++) {
    const s = steps[i];
    if (typeof s !== "object" || s === null || Array.isArray(s) || String(s.E ?? "").trim() !== "check_point") continue;
    if (String(s.G ?? "").trim() || String(s.H ?? "").trim() || String(s.I ?? "").trim()) continue;
    result.add("empty_assertion_pattern", "check_point has G/H/I all empty — no pattern, no register reference, the framework has nothing to compare (it falls back to searching with the observation command text; <case> evidence: one on-device round wasted). Write a pattern in G, or reference an already-captured H register. If expected is not independently known, write <RUNTIME> only as an underdetermined marker; device actuals may be registered as digests but never backfilled into expected. An identity-bound Author, Spec, DefectSpec, Manual, ConfigBinding, or CapabilityXml claim must supply expected before delivery.", i);
  }
}

function _checkAssertionRegexCompiles(steps: any[], result: StructuralResult): void {
  for (let i = 0; i < steps.length; i++) {
    const s = steps[i];
    if (typeof s !== "object" || s === null || Array.isArray(s) || String(s.E ?? "").trim() !== "check_point") continue;
    const f = String(s.F ?? "").trim();
    const g = String(s.G ?? "");
    const h = String(s.H ?? "").trim();
    if (!["found", "not_found", "found_times"].includes(f) || !g) continue;
    if (h && f !== "found_times") continue;
    try {
      new RegExp(g);
    } catch (exc) {
      result.add("assertion_regex_invalid", `assertion regex fails to compile (${exc instanceof Error ? exc.message : String(exc)}): ${pyRepr(g.slice(0, 80))} — the framework raises at re.compile and the entire file crashes. Fix the regex syntax (common: an unclosed character class, [^ should be [^\\n]).`, i);
    }
  }
}

function _checkShortModeAssertions(steps: any[], result: StructuralResult): void {
  let lastObsShort = false;
  for (let i = 0; i < steps.length; i++) {
    const s = steps[i];
    if (typeof s !== "object" || s === null || Array.isArray(s)) continue;
    const e = String(s.E ?? "").trim();
    if (e === "check_point") {
      const g = String(s.G ?? "");
      if (lastObsShort && _SHORT_INCOMPATIBLE_RE.test(g)) {
        result.add("short_mode_status_assertion", "the assertion matches dig status/HEADER/SECTION text, but the observation step it consumes used +short (output has only record values, none of those sections) — always-fail. Remove +short from that dig, or rewrite the assertion in record-value form.", i);
      }
      continue;
    }
    const h = String(s.H ?? "").trim();
    if (!h) {
      const g = String(s.G ?? "");
      lastObsShort = g.includes("dig") && g.includes("+short");
    }
  }
}

function _checkCaptureRefsDefined(steps: any[], result: StructuralResult): void {
  const contract = _loadContractForGate(result);
  const objectNames = contract !== null ? new Set<string>(contract.objects.map((item: any) => String(item.e))) : new Set<string>();
  const defined = new Set<string>();
  for (let i = 0; i < steps.length; i++) {
    const s = steps[i];
    if (typeof s !== "object" || s === null || Array.isArray(s)) continue;
    const e = String(s.E ?? "").trim();
    const f = String(s.F ?? "").trim();
    const h = String(s.H ?? "").trim();
    const iCol = String(s.I ?? "").trim();
    if (e === "check_point") {
      const refs = f === "found_times" ? [] : [h, iCol];
      for (const ref of refs) {
        if (ref && !defined.has(ref)) {
          result.add("undefined_capture_ref", `the assertion references register ${pyRepr(ref)}, but no earlier step captured it with H=${ref} — the framework reads None and the assertion is distorted. Add a capture step or fix the reference name.`, i);
        }
      }
    } else {
      if (iCol) {
        const base = iCol.split(".", 1)[0];
        if (!defined.has(base) && !objectNames.has(base)) {
          result.add("undefined_capture_ref", `step I=${pyRepr(iCol)} references a variable that no earlier step captured with H — for an undefined I on a non-assertion step the framework **raises NameError and crashes the entire file**. Capture it with H first, or fix the reference name.`, i);
        }
      }
      const g = String(s.G ?? "");
      if (!iCol && _curlWriteOutHasDoubledVariable(g)) {
        result.add("injection_format_crash", "curl -w/--write-out contains a doubled-brace variable such as '%{{name}}'. With column I blank the framework validates G but never calls .format(), so the doubled braces reach curl unchanged; curl then treats the variable name as invalid. Use curl's exact single-brace syntax only if the F/G carrier can represent it, otherwise use an equivalent observation without write-out variables or report the carrier-language gap.", i);
      }
      try {
        validate_i_injection_syntax(g, iCol, f);
      } catch (exc) {
        if (exc instanceof ExcelContractError) {
        } else if (exc instanceof IInjectionSyntaxError) {
          const codeMap: Record<string, string> = { missing: "injection_without_placeholder", scope: "injection_placeholder_scope", format: "injection_format_crash" };
          const code = codeMap[exc.code] ?? exc.code;
          let repair: string;
          if (exc.code === "scope") {
            repair = " Accepted shapes: static — remove every placeholder from G and leave I blank; injected — capture an earlier H register (or use a declared runtime object attribute), put exactly one {} or {0} in G's first parsed positional argument, and set I to that register/attribute. No later positional argument or keyword argument may contain a placeholder.";
          } else if (exc.code === "format") {
            repair = !iCol
              ? " The currently bound runner still validates static G through Python's Formatter grammar even with I blank; this literal-brace feature is not certified on that runtime. Use an equivalent observation with no named braces, or complete the runner certification/deployment first."
              : " Python placeholder grammar applies because I is present and the runtime will call .format() on G's first positional argument. Keep downstream literal braces out of that formatted argument, or use a static row with blank I when no injection is required.";
          } else {
            repair = "";
          }
          result.add(code, `E=${pyRepr(e)}, F=${pyRepr(f)}, I=${pyRepr(iCol)}: ${exc.message}. The runtime parses G first and formats only positional argument 1.${repair}`, i);
        } else {
          throw exc;
        }
      }
      if (h) {
        if (contract !== null && _frameworkReservedNames(contract).has(h)) {
          result.add("register_shadows_framework_name", `H=${pyRepr(h)} collides with a v2 runner **runtime object name** (a contract device slot, or a runner built-in parsed from the mirror source). The v2 preflight rejects it before any step executes (NameError, verbatim runner message: 'H 不能覆盖运行时对象') and _store_register raises the same at runtime — either way the whole pytest file crashes. Registers are a separate dict in v2, so ordinary frame-local names are legal register names; pick one that is not a runtime object (like v1/ip1).`, i);
        }
        defined.add(h);
      }
    }
  }
}

function _shlexSplit(text: string): string[] {
  const tokens: string[] = [];
  let current = "";
  let quote: string | null = null;
  let escaped = false;
  for (const char of text) {
    if (escaped) {
      current += char;
      escaped = false;
      continue;
    }
    if (char === "\\" && quote !== "'") {
      escaped = true;
      continue;
    }
    if (quote !== null) {
      if (char === quote) {
        quote = null;
      } else {
        current += char;
      }
      continue;
    }
    if (char === '"' || char === "'") {
      quote = char;
      continue;
    }
    if (/\s/.test(char)) {
      if (current) tokens.push(current);
      current = "";
      continue;
    }
    current += char;
  }
  if (escaped) throw new PyValueError("No escaped character");
  if (quote !== null) throw new PyValueError("No closing quotation");
  if (current) tokens.push(current);
  return tokens;
}

function _curlWriteOutHasDoubledVariable(g: string): boolean {
  let tokens: string[];
  try {
    tokens = _shlexSplit(String(g ?? ""));
  } catch {
    return false;
  }
  const curlIndexes = tokens.map((token, index) => [token, index] as [string, number]).filter(([token]) => token.split("/").pop() === "curl").map(([, index]) => index);
  if (!curlIndexes.length) return false;
  const start = curlIndexes[curlIndexes.length - 1] + 1;
  const doubled = /%\{\{[^{}\s]+\}\}/;
  const args = tokens.slice(start);
  for (let index = 0; index < args.length; index++) {
    const token = args[index];
    if (token === "-w" || token === "--write-out") {
      if (index + 1 < args.length && doubled.test(args[index + 1])) return true;
      continue;
    }
    if (token.startsWith("--write-out=") && doubled.test(token.split("=", 2)[1])) return true;
    if (token.startsWith("-w") && token !== "-w" && doubled.test(token.slice(2))) return true;
  }
  return false;
}

function _frameworkReservedNames(contract: any = null): Set<string> {
  const active = contract !== null ? contract : load_excel_contract();
  const names = new Set<string>(active.objects.map((item: any) => String(item.e)));
  for (const builtin of _v2RunnerBuiltinNames()) {
    names.add(builtin);
  }
  names.delete("");
  return names;
}

function _v2RunnerBuiltinNames(): Set<string> {
  const { mirror_src } = require("../../../case_compiler/apv_lang");
  const src: string = mirror_src("lib/test_xlsx.py");
  if (!src) return new Set<string>();
  const names = new Set<string>();
  const dictRe = /runtime_objects\s*=\s*\{([\s\S]*?)\}/;
  const dm = dictRe.exec(src);
  if (dm) {
    for (const m of dm[1].matchAll(/["']([^"']+)["']\s*:/g)) {
      names.add(m[1]);
    }
  }
  const updateRe = /(?:runtime_names|runtime_objects)\.update\(([\s\S]*?)\)/g;
  for (const m of src.matchAll(updateRe)) {
    for (const s of m[1].matchAll(/["']([^"']+)["']/g)) {
      names.add(s[1]);
    }
  }
  return names;
}

const _KWARG_SEG_RE = /^\s*(timeout|prompt)\s*=/;

function _checkParameterSplitting(steps: any[], result: StructuralResult): void {
  const contract = _loadContractForGate(result);
  if (contract === null) return;
  const hostSlots = _contractHostSlotEs(contract);
  const { _PARAM_SPLIT_RE } = require("../../../case_compiler/apv_lang");
  for (let i = 0; i < steps.length; i++) {
    const s = steps[i];
    if (typeof s !== "object" || s === null || Array.isArray(s)) continue;
    const e = String(s.E ?? "").trim();
    if (!(e === "test_env" || hostSlots.has(e))) continue;
    const f = String(s.F ?? "").trim();
    if (f === "execute") continue;
    const g = String(s.G ?? "");
    if (g.includes("\n") || !g.includes(",")) continue;
    const segs = reFindall(_PARAM_SPLIT_RE, g).map((p: any) => String(Array.isArray(p) ? p[0] : p).trim()).filter((p: string) => p);
    const stray = segs.slice(1).filter((p: string) => !_KWARG_SEG_RE.test(p));
    if (stray.length) {
      result.add("comma_splits_parameters", `G contains an unquoted comma, so the framework splits it into ${segs.length} positional parameters — ${pyRepr(stray[0])} gets mispassed to the host method's prompt/timeout parameter; the step always waits out the full timeout and the output is distorted. If the comma is part of the command, quote that segment, or rewrite the command to avoid commas; to pass a timeout use the timeout=N form (framework named parameter).`, i);
    }
  }
}

function _checkConfigExistenceAdvisories(steps: any[], result: StructuralResult): void {
  let configContext: string[] = [];
  let lastObserve = "";
  for (let i = 0; i < (Array.isArray(steps) ? steps.length : 0); i++) {
    const step = steps[i];
    if (typeof step !== "object" || step === null || Array.isArray(step)) continue;
    const e = String(step.E ?? "").trim();
    const f = String(step.F ?? "").trim();
    const g = String(step.G ?? "").trim();
    if (e === "check_point") {
      const [isEcho] = config_existence_check(lastObserve, g, configContext, f || "found");
      if (isEcho) {
        result.advise("config_existence_only", "the assertion only confirms that a configuration written earlier is present in a read-only configuration query; it does not demonstrate the target runtime behavior. Keep it only when configuration existence is the stated test objective, otherwise add an independently sourced behavior observation.", i);
      }
      continue;
    }
    if (["cmd_config", "cmds_config"].includes(f)) {
      configContext.push(...g.split(/\r?\n/).map((line: string) => line.trim()).filter((line: string) => line));
    }
    if (observe_kind(g)) {
      lastObserve = g;
    }
  }
}

export function lint_xlsx_case(xlsxPath: string): StructuralResult {
  const result = new StructuralResult();
  let autoid: string;
  let steps: Array<Record<string, string>>;
  try {
    [autoid, steps] = steps_from_xlsx(xlsxPath, { allow_legacy: true });
  } catch (exc) {
    result.add("xlsx_unreadable", `sheet is unreadable: ${exc instanceof Error ? exc.message : String(exc)}`);
    return result;
  }
  if (autoid && !_AUTOID_RE.test(autoid)) {
    result.add("autoid_malformed", `sheet autoid ${pyRepr(autoid)} is not an 18-digit number — a hand-copied truncated id silently creates a junk directory and sneaks into the final sheet (evidence: once produced a 35-case final sheet). Use the machine-readable full id from last_run.json/manifest.`);
  }
  const mand = check_crash_gates_mandatory(steps);
  if (!mand.ok) {
    result.ok = false;
    result.violations.push(...mand.violations);
  }
  result.disabled.push(...mand.disabled);
  _checkAssertionRegexCompiles(steps, result);
  _checkShortModeAssertions(steps, result);
  _checkParameterSplitting(steps, result);
  _checkAutoidRowsRunnable(xlsxPath, result);
  _checkConfigExistenceAdvisories(steps, result);
  return result;
}

function _checkAutoidRowsRunnable(xlsxPath: string, result: StructuralResult): void {
  let emptyEAutoids: string[];
  try {
    [, , emptyEAutoids] = _workbookModel(xlsxPath, { allow_legacy: true });
  } catch {
    return;
  }
  for (const a of emptyEAutoids) {
    result.add("autoid_row_not_runnable", `autoid row (${a}) has an empty column E — the deployed runner cannot start a case from it: the v1 framework silently skipped the whole case (not executed, no fail counted, no log), and the v2 scheduler skips the row before the new-case boundary, so this case's steps execute inside the previous case (verdicts attributed to the wrong case, device state carried across). The autoid must share its row with the first step (column E non-empty).`);
  }
}
