import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { accepts_schema } from "../../../common/schema_identity";

const logger = {
  warning: (...args: any[]) => console.warn(...args),
  info: (...args: any[]) => {},
  debug: (...args: any[]) => {},
  exception: (...args: any[]) => console.error(...args),
};

export const TIMEOUT_MARK = "User did not answer within the timeout window (no answer).";
export const CANCEL_MARK = "User cancelled the question (no answer).";

const _PENDING: Record<string, Record<string, any>> = {};
const _LIFECYCLE_PHASES: Record<string, Set<string>> = {};
const _LIFECYCLE_SCHEMA = "ist.ask_user.lifecycle";
const _REASK_REQUESTED_PHASE = "reask_requested";
const _ANSWER_REPLAYED_PHASE = "answer_replayed";
const _REASK_REASON_CODES = new Set(["answer_token_unmapped", "signer_invalid", "run_window_unavailable", "answer_credential_mismatch"]);
const _RENDER_VERSION = "ask_user";
const _QID_RESERVATIONS = new Set<string>();
const _HIL_ID_RE = /^[A-Za-z0-9_.@+:-]{1,256}$/;

let _HIL_OWNER = "";
let _HIL_THREAD_ID = "";
let _WAIT_TIMEOUT_OVERRIDE_DEADLINE: number | null = null;
let _POSITIONAL_ANSWERS: any[] | null = null;
let _ENGINE_PANEL_ORIGIN = false;

class _Event {
  private _flag = false;
  private _waiters: Array<() => void> = [];

  set(): void {
    this._flag = true;
    for (const w of this._waiters.splice(0)) {
      w();
    }
  }

  wait(timeout_s?: number | null): boolean {
    if (this._flag) {
      return true;
    }
    if (timeout_s === null || timeout_s === undefined) {
      return this._flag;
    }
    const deadline = Date.now() + timeout_s * 1000;
    while (!this._flag && Date.now() < deadline) {
      break;
    }
    return this._flag;
  }

  is_set(): boolean {
    return this._flag;
  }
}

export function _publish_positional_answers(values: any[]): void {
  _POSITIONAL_ANSWERS = values.slice();
}

export function reset_positional_answers(): void {
  _POSITIONAL_ANSWERS = null;
}

export function positional_answers(): any[] | null {
  return _POSITIONAL_ANSWERS;
}

function _validated_hil_identity(value: any, opts: { field: string }): string {
  const text = String(value || "").trim();
  if (["", ".", ".."].includes(text) || !_HIL_ID_RE.test(text)) {
    throw new Error(`HIL ${opts.field} identity is invalid`);
  }
  return text;
}

export function hil_identity<T>(owner: string, thread_id: string, fn: () => T): T {
  const safe_owner = _validated_hil_identity(owner, { field: "owner" });
  const safe_thread = _validated_hil_identity(thread_id, { field: "thread" });
  const prev_owner = _HIL_OWNER;
  const prev_thread = _HIL_THREAD_ID;
  _HIL_OWNER = safe_owner;
  _HIL_THREAD_ID = safe_thread;
  try {
    return fn();
  } finally {
    _HIL_THREAD_ID = prev_thread;
    _HIL_OWNER = prev_owner;
  }
}

function _current_hil_identity(): [string, string] {
  const owner = _HIL_OWNER;
  const thread_id = _HIL_THREAD_ID;
  if (Boolean(owner) !== Boolean(thread_id)) {
    throw new Error("HIL owner/thread binding is incomplete");
  }
  return [owner, thread_id];
}

export function current_hil_identity(): [string, string] {
  return _current_hil_identity();
}

export function hil_identity_sha256(owner: string = "", thread_id: string = ""): string {
  const safe_owner = String(owner || "");
  const safe_thread = String(thread_id || "");
  if (Boolean(safe_owner) !== Boolean(safe_thread)) {
    throw new Error("HIL owner/thread binding is incomplete");
  }
  const payload = Buffer.from(JSON.stringify({ owner: safe_owner, thread_id: safe_thread }), "utf8");
  return crypto.createHash("sha256").update(payload).digest("hex");
}

export function current_hil_identity_sha256(): string {
  const [owner, thread_id] = _current_hil_identity();
  return hil_identity_sha256(owner, thread_id);
}

export function hil_identity_digest_is_current(value: any, opts: { allow_legacy_unbound?: boolean } = {}): boolean {
  const allow_legacy_unbound = opts.allow_legacy_unbound ?? true;
  const [owner, thread_id] = _current_hil_identity();
  const expected = hil_identity_sha256(owner, thread_id);
  const actual = String(value || "");
  if (owner || thread_id) {
    return actual === expected;
  }
  return actual === expected || (allow_legacy_unbound && !actual);
}

function _pending_authorized(pending: Record<string, any>, opts: { owner?: string; thread_id?: string } = {}): boolean {
  const requested_owner = String(opts.owner || "").trim();
  const requested_thread = String(opts.thread_id || "").trim();
  if (Boolean(requested_owner) !== Boolean(requested_thread)) {
    return false;
  }
  const bound_owner = String(pending.owner || "");
  const bound_thread = String(pending.thread_id || "");
  if (Boolean(bound_owner) !== Boolean(bound_thread)) {
    return false;
  }
  if (bound_owner) {
    return requested_owner === bound_owner && requested_thread === bound_thread;
  }
  return !requested_owner && !requested_thread;
}

function _json_safe(value: any): any {
  return JSON.parse(JSON.stringify(value, (_k, v) => (v === undefined ? undefined : typeof v === "bigint" ? String(v) : v)));
}

function _persist_safe(value: any): any {
  const { scrub_value } = require("../../security_scrub");
  return _json_safe(scrub_value(_json_safe(value)));
}

function _render_digest(questions: Record<string, any>[]): string {
  const raw = Buffer.from(JSON.stringify(_persist_safe(questions)), "utf8");
  return crypto.createHash("sha256").update(raw).digest("hex");
}

function _normalize_questions(questions: any): [Record<string, any>[] | null, string] {
  if (!Array.isArray(questions) || questions.length === 0) {
    return [null, "'questions' must be a non-empty list"];
  }
  const normalized: Record<string, any>[] = [];
  for (let index = 0; index < questions.length; index++) {
    const raw = questions[index];
    if (raw === null || typeof raw !== "object" || Array.isArray(raw)) {
      return [null, `question[${index}] must be a dict`];
    }
    const question = String(raw.question || "").trim();
    if (!question) {
      return [null, `question[${index}].question must not be empty`];
    }
    const header = String(raw.header || `问题${index + 1}`).trim();
    if (!header) {
      return [null, `question[${index}].header must not be empty`];
    }
    const multi_select = raw.multiSelect ?? false;
    if (typeof multi_select !== "boolean") {
      return [null, `question[${index}].multiSelect must be a bool`];
    }
    const accepts_file = raw.accepts_file ?? false;
    if (typeof accepts_file !== "boolean") {
      return [null, `question[${index}].accepts_file must be a bool`];
    }
    const options = raw.options;
    if (!Array.isArray(options) || options.length === 0) {
      return [null, `question[${index}].options must be a non-empty list`];
    }
    const normalized_options: Record<string, any>[] = [];
    const labels = new Set<string>();
    for (let option_index = 0; option_index < options.length; option_index++) {
      const option = options[option_index];
      if (option === null || typeof option !== "object" || Array.isArray(option)) {
        return [null, `question[${index}].options[${option_index}] must be a dict`];
      }
      const label = String(option.label || "").trim();
      const description = option.description;
      if (!label || labels.has(label)) {
        return [null, `question[${index}].options[${option_index}].label must be unique and non-empty`];
      }
      if (typeof description !== "string") {
        return [null, `question[${index}].options[${option_index}].description must be a string`];
      }
      if ("preview" in option && !["string", "object"].includes(typeof option.preview) && option.preview !== null) {
        return [null, `question[${index}].options[${option_index}].preview has an unsupported type`];
      }
      labels.add(label);
      normalized_options.push({ ...option, label });
    }
    const normalized_q: Record<string, any> = { ...raw, question, header, options: normalized_options, multiSelect: multi_select };
    if ("accepts_file" in raw) {
      normalized_q.accepts_file = accepts_file;
    }
    normalized.push(normalized_q);
  }
  return [normalized, ""];
}

function _engine_visible_question(question: Record<string, any>): Record<string, any> {
  const rendered: Record<string, any> = {};
  for (const [key, value] of Object.entries(question)) {
    if (!String(key).startsWith("_")) {
      rendered[key] = value;
    }
  }
  const answer_key = String(question._answer_key || "").trim();
  if (answer_key) {
    rendered.answer_key = answer_key;
  }
  if (question._allow_other === false) {
    rendered.allow_other = false;
  }
  return rendered;
}

export function _normalize_engine_question(question: Record<string, any>): [Record<string, any> | null, string] {
  if (question === null || typeof question !== "object" || Array.isArray(question)) {
    return [null, "engine question must be a dict"];
  }
  const rendered = _engine_visible_question(question);
  const [normalized, error] = _normalize_questions([rendered]);
  if (normalized === null || error) {
    return [null, error];
  }
  return [normalized[0], ""];
}

export function _engine_question_digest(question: Record<string, any>): string {
  const [normalized, error] = _normalize_engine_question(question);
  if (normalized === null || error) {
    return "";
  }
  return _render_digest([normalized]);
}

function _lifecycle_records(): Record<string, any>[] {
  const { runtime_path } = require("../../../common/runtime_paths");
  const p = runtime_path("ask_user_lifecycle.jsonl");
  let lines: string[];
  try {
    lines = fs.readFileSync(p, "utf8").split(/\r?\n/);
  } catch {
    return [];
  }
  const records: Record<string, any>[] = [];
  for (const line of lines) {
    let item: any;
    try {
      item = JSON.parse(line);
    } catch {
      continue;
    }
    if (item !== null && typeof item === "object" && !Array.isArray(item) && item.schema === _LIFECYCLE_SCHEMA) {
      records.push(item);
    }
  }
  return records;
}

function _allocate_question_id(questions: Record<string, any>[], opts: { owner?: string; thread_id?: string } = {}): [string, Set<string>, Record<string, any> | null] {
  const owner = opts.owner ?? "";
  const thread_id = opts.thread_id ?? "";
  const { current_username, multi_tenant, output_scope } = require("../../../knowledge_paths");
  if (Boolean(owner) !== Boolean(thread_id)) {
    throw new Error("HIL owner/thread binding is incomplete");
  }
  let namespace_parts: string[];
  if (owner) {
    namespace_parts = [owner, thread_id, _render_digest(questions)];
  } else {
    const ident = multi_tenant() ? output_scope() : String(current_username() || "");
    namespace_parts = [ident, (process.env.IST_CONVERSATION_ID || "").trim(), (process.env.IST_SESSION_ID || "").trim(), _render_digest(questions)];
  }
  const namespace = namespace_parts.join("|");
  const prefix = crypto.createHash("sha256").update(Buffer.from(namespace, "utf8")).digest("hex").slice(0, 24);
  const by_qid: Record<string, Set<string>> = {};
  const terminal_by_qid: Record<string, Record<string, any>> = {};
  const reask_requested_qids = new Set<string>();
  const answer_replayed_qids = new Set<string>();
  for (const record of _lifecycle_records()) {
    const qid = String(record.question_id || "");
    const record_owner = String(record.owner || "");
    const record_thread = String(record.thread_id || "");
    const binding_matches = owner ? record_owner === owner && record_thread === thread_id : !record_owner && !record_thread;
    if (qid.startsWith(prefix + "-") && binding_matches) {
      const phase = String(record.phase || "");
      (by_qid[qid] ??= new Set()).add(phase);
      if (record.phase === "resolved") {
        terminal_by_qid[qid] = record;
      } else if (phase === _REASK_REQUESTED_PHASE) {
        reask_requested_qids.add(qid);
      } else if (phase === _ANSWER_REPLAYED_PHASE) {
        answer_replayed_qids.add(qid);
      }
    }
  }
  const sequences = Object.keys(by_qid)
    .map((qid) => qid.substring(qid.lastIndexOf("-") + 1))
    .filter((s) => /^\d+$/.test(s))
    .map((s) => parseInt(s, 10))
    .sort((a, b) => a - b);
  let sequence = sequences.length > 0 ? sequences[sequences.length - 1] : 1;
  let qid = `${prefix}-${String(sequence).padStart(8, "0")}`;
  let phases = new Set(by_qid[qid] ?? []);
  if (phases.has("resolved")) {
    const terminal = terminal_by_qid[qid];
    if (String((terminal || {}).outcome || "") === "answered" && !reask_requested_qids.has(qid) && answer_replayed_qids.size === 0) {
      return [qid, phases, terminal];
    }
    sequence += 1;
    qid = `${prefix}-${String(sequence).padStart(8, "0")}`;
    phases = new Set(by_qid[qid] ?? []);
  }
  if (_QID_RESERVATIONS.has(qid)) {
    return ["", phases, null];
  }
  _QID_RESERVATIONS.add(qid);
  _LIFECYCLE_PHASES[qid] = new Set(phases);
  return [qid, phases, null];
}

function _option_tokens(questions: Record<string, any>[]): string[][] {
  return _persist_safe(
    questions.map((q) => {
      const opts = (q.options || []).map((opt: any) => String(opt.label || ""));
      if (q.allow_other !== false) {
        opts.push("Other");
      }
      return opts;
    })
  );
}

function _append_lifecycle_record(record: Record<string, any>): void {
  const { runtime_path } = require("../../../common/runtime_paths");
  const p = runtime_path("ask_user_lifecycle.jsonl");
  fs.mkdirSync(path.dirname(p), { recursive: true });
  const existed = fs.existsSync(p);
  const safe_record = _persist_safe(record);
  const fd = fs.openSync(p, "a");
  try {
    fs.writeSync(fd, JSON.stringify(safe_record) + "\n");
    fs.fsyncSync(fd);
  } finally {
    fs.closeSync(fd);
  }
  if (!existed && process.platform !== "win32") {
    try {
      const dirFd = fs.openSync(path.dirname(p), "r");
      try {
        fs.fsyncSync(dirFd);
      } finally {
        fs.closeSync(dirFd);
      }
    } catch {}
  }
}

export function request_reask_after_rejection(answer_key: string, opts: { question_digest?: string; reason_code: string }): boolean {
  const key = String(answer_key || "").trim();
  const digest = String(opts.question_digest || "").trim();
  const reason = String(opts.reason_code || "").trim();
  if (!key || !_REASK_REASON_CODES.has(reason)) {
    return false;
  }
  const [owner, thread_id] = _current_hil_identity();
  const records = _lifecycle_records();
  const scheduled_by_qid: Record<string, Record<string, any>> = {};
  const answered_by_qid: Record<string, Record<string, any>> = {};
  const already_requested = new Set<string>();
  for (const record of records) {
    const record_owner = String(record.owner || "");
    const record_thread = String(record.thread_id || "");
    const binding_matches = owner ? record_owner === owner && record_thread === thread_id : !record_owner && !record_thread;
    if (!binding_matches) {
      continue;
    }
    const qid = String(record.question_id || "");
    const phase = String(record.phase || "");
    if (!qid) {
      continue;
    }
    if (phase === "scheduled") {
      scheduled_by_qid[qid] = record;
    } else if (phase === "resolved" && record.outcome === "answered") {
      answered_by_qid[qid] = record;
    } else if (phase === _REASK_REQUESTED_PHASE) {
      already_requested.add(qid);
    }
  }
  const candidates: Array<[number, string, string, string, string]> = [];
  for (const qid of Object.keys(scheduled_by_qid).filter((q) => q in answered_by_qid)) {
    const scheduled = scheduled_by_qid[qid];
    for (const question of scheduled.render_input || []) {
      if (question === null || typeof question !== "object") {
        continue;
      }
      const recorded_key = String(question.answer_key || "").trim();
      const recorded_digest = _render_digest([question]);
      if (recorded_key !== key && !(digest && recorded_digest === digest)) {
        continue;
      }
      let terminal_ts = 0.0;
      try {
        terminal_ts = parseFloat(answered_by_qid[qid].ts ?? 0.0) || 0.0;
      } catch {
        terminal_ts = 0.0;
      }
      candidates.push([terminal_ts, qid, recorded_key, recorded_digest, String(scheduled.owner || "")]);
    }
  }
  if (candidates.length === 0) {
    return false;
  }
  candidates.sort((a, b) => a[0] - b[0] || a[1].localeCompare(b[1]));
  const [, qid, recorded_key, recorded_digest] = candidates[candidates.length - 1];
  if (already_requested.has(qid)) {
    return true;
  }
  const record: Record<string, any> = {
    schema: _LIFECYCLE_SCHEMA,
    phase: _REASK_REQUESTED_PHASE,
    question_id: qid,
    owner,
    thread_id,
    ts: Date.now() / 1000,
    render_version: _RENDER_VERSION,
    reason_code: reason,
    answer_key: recorded_key || key,
    rejected_question_digest: digest,
    recorded_question_digest: recorded_digest,
    digest_matched: Boolean(digest && digest === recorded_digest),
  };
  _append_lifecycle_record(record);
  (_LIFECYCLE_PHASES[qid] ??= new Set()).add(_REASK_REQUESTED_PHASE);
  _QID_RESERVATIONS.delete(qid);
  _emit_lifecycle("ask_user_reask_requested", record);
  return true;
}

function _append_answer_credential(question_id: string, questions: Record<string, any>[], answers: Record<string, string>, opts: { owner?: string; thread_id?: string } = {}): void {
  const { runtime_path } = require("../../../common/runtime_paths");
  const p = runtime_path("ask_user_answers.jsonl");
  fs.mkdirSync(path.dirname(p), { recursive: true });
  const existed = fs.existsSync(p);
  const answer_bindings: Record<string, any>[] = [];
  for (const question of questions) {
    const answer_key = String(question.answer_key || "").trim();
    if (!answer_key) {
      continue;
    }
    const question_text = String(question.question || "");
    const header = String(question.header || "");
    const matched_key = [question_text, header, answer_key].find((k) => k && k in answers) || "";
    if (!matched_key) {
      continue;
    }
    answer_bindings.push({ answer_key, question_digest: _render_digest([question]), answer: String(answers[matched_key]).slice(0, 500) });
  }
  const folded_members = new Set<string>();
  for (const question of questions) {
    for (const aid of question.folded_members || []) {
      folded_members.add(String(aid));
    }
  }
  const answersOut: Record<string, string> = {};
  for (const [key, value] of Object.entries(answers)) {
    const v = Array.isArray(value) ? value.map((x) => String(x)).join(", ") : String(value);
    answersOut[String(key).slice(0, 500)] = v.slice(0, 500);
  }
  const record = _persist_safe({
    schema: "ist.ask_user.answer",
    question_id: String(question_id || ""),
    owner: String(opts.owner || ""),
    thread_id: String(opts.thread_id || ""),
    ts: Date.now() / 1000,
    questions: questions.map((q) => String(q.question || "").slice(0, 500)),
    folded_members: [...folded_members].sort(),
    answers: answersOut,
    answer_bindings,
  });
  const fd = fs.openSync(p, "a");
  try {
    fs.writeSync(fd, JSON.stringify(record) + "\n");
    fs.fsyncSync(fd);
  } finally {
    fs.closeSync(fd);
  }
  if (!existed && process.platform !== "win32") {
    try {
      const dirFd = fs.openSync(path.dirname(p), "r");
      try {
        fs.fsyncSync(dirFd);
      } finally {
        fs.closeSync(dirFd);
      }
    } catch {}
  }
}

export function operator_answer_credential_binding(answer_key: string, opts: { question_digest: string; not_before: number }): Record<string, any> | null {
  const { runtime_path } = require("../../../common/runtime_paths");
  const key = String(answer_key || "").trim();
  const digest = String(opts.question_digest || "").trim();
  let lower_bound: number;
  try {
    lower_bound = Number(opts.not_before);
  } catch {
    return null;
  }
  if (!key || !digest || !Number.isFinite(lower_bound) || lower_bound <= 0.0) {
    return null;
  }
  const p = runtime_path("ask_user_answers.jsonl");
  const [expected_owner, expected_thread] = _current_hil_identity();
  let newest: [number, Record<string, any>] | null = null;
  let raw: Buffer;
  try {
    raw = fs.readFileSync(p);
  } catch {
    return null;
  }
  for (const rawLine of raw.toString("utf8").split(/\r?\n/)) {
    if (!rawLine.includes("ist.ask_user.answer")) {
      continue;
    }
    let item: any;
    let recorded_at = 0.0;
    try {
      item = JSON.parse(rawLine);
      recorded_at = parseFloat(item.ts ?? 0.0) || 0.0;
    } catch {
      continue;
    }
    if (item === null || typeof item !== "object" || !accepts_schema(item.schema, "ist.ask_user.answer") || recorded_at < lower_bound) {
      continue;
    }
    const recorded_owner = String(item.owner || "");
    const recorded_thread = String(item.thread_id || "");
    if (recorded_owner !== expected_owner || recorded_thread !== expected_thread) {
      continue;
    }
    for (const binding of item.answer_bindings || []) {
      if (binding === null || typeof binding !== "object") {
        continue;
      }
      if (String(binding.answer_key || "") !== key || String(binding.question_digest || "") !== digest) {
        continue;
      }
      const answer = String(binding.answer || "");
      if (!answer) {
        continue;
      }
      const candidate = {
        answer_key: key,
        question_digest: digest,
        answer,
        question_id: String(item.question_id || ""),
        owner: recorded_owner,
        thread_id: recorded_thread,
        recorded_at,
        provenance_channel: "operator",
      };
      if (newest === null || recorded_at >= newest[0]) {
        newest = [recorded_at, candidate];
      }
    }
  }
  return newest === null ? null : newest[1];
}

export function answer_credential_recorded(answer_key: string, opts: { question_digest?: string; not_before?: number | null; accept_answered_replay?: boolean } = {}): boolean {
  const { runtime_path } = require("../../../common/runtime_paths");
  const question_digest = opts.question_digest ?? "";
  const not_before = opts.not_before ?? null;
  const accept_answered_replay = opts.accept_answered_replay ?? false;
  const key = String(answer_key || "").trim();
  if (!key) {
    return false;
  }
  const p = runtime_path("ask_user_answers.jsonl");
  const replayed = new Set<string>();
  if (accept_answered_replay && not_before !== null) {
    for (const record of _lifecycle_records()) {
      if (record.phase !== _ANSWER_REPLAYED_PHASE) {
        continue;
      }
      let replayed_at: number;
      try {
        replayed_at = parseFloat(record.ts ?? 0.0) || 0.0;
      } catch {
        continue;
      }
      if (replayed_at < not_before) {
        continue;
      }
      const qid = String(record.question_id || "");
      for (const binding of record.answer_bindings || []) {
        if (binding === null || typeof binding !== "object") {
          continue;
        }
        replayed.add(`${qid}|${String(binding.answer_key || "")}|${String(binding.question_digest || "")}`);
      }
    }
  }
  let raw: Buffer;
  try {
    raw = fs.readFileSync(p);
  } catch {
    return false;
  }
  for (const rawLine of raw.toString("utf8").split(/\r?\n/)) {
    if (!rawLine.includes("ist.ask_user.answer")) {
      continue;
    }
    let item: any;
    try {
      item = JSON.parse(rawLine);
    } catch {
      continue;
    }
    if (item === null || typeof item !== "object") {
      continue;
    }
    if (item.schema !== "ist.ask_user.answer") {
      continue;
    }
    let outside_run_window = false;
    if (not_before !== null) {
      let recorded_at: number;
      try {
        recorded_at = parseFloat(item.ts ?? 0.0) || 0.0;
      } catch {
        continue;
      }
      if (recorded_at < not_before) {
        outside_run_window = true;
      }
    }
    for (const binding of item.answer_bindings || []) {
      if (binding === null || typeof binding !== "object") {
        continue;
      }
      if (String(binding.answer_key || "") !== key) {
        continue;
      }
      if (question_digest && String(binding.question_digest || "") !== question_digest) {
        continue;
      }
      if (outside_run_window && !replayed.has(`${String(item.question_id || "")}|${key}|${String(binding.question_digest || "")}`)) {
        continue;
      }
      return true;
    }
  }
  return false;
}

function _record_lifecycle(
  question_id: string,
  phase: string,
  opts: {
    questions?: Record<string, any>[] | null;
    channel?: string;
    outcome?: string;
    answers?: Record<string, string> | null;
    reason?: string;
    wait_budget_s?: number | null;
    deadline_at?: number | null;
    owner?: string;
    thread_id?: string;
  } = {}
): [boolean, Record<string, any>] {
  const qid = String(question_id || "");
  if (!qid || !["scheduled", "presented", "resolved"].includes(phase)) {
    return [false, {}];
  }
  const owner = opts.owner ?? "";
  const thread_id = opts.thread_id ?? "";
  if (Boolean(owner) !== Boolean(thread_id)) {
    return [false, {}];
  }
  const safe_questions = _persist_safe(opts.questions ?? []);
  const phases = (_LIFECYCLE_PHASES[qid] ??= new Set());
  if (phases.has(phase) || phases.has("resolved")) {
    return [false, {}];
  }
  if (phase === "presented" && !phases.has("scheduled")) {
    return [false, {}];
  }
  const record: Record<string, any> = {
    schema: _LIFECYCLE_SCHEMA,
    phase,
    question_id: qid,
    owner: String(owner || ""),
    thread_id: String(thread_id || ""),
    ts: Date.now() / 1000,
    render_version: _RENDER_VERSION,
  };
  if (phase === "scheduled") {
    Object.assign(record, {
      render_input: safe_questions,
      redacted_render_digest: _render_digest(safe_questions),
      option_tokens: _option_tokens(safe_questions),
      wait_budget_s: opts.wait_budget_s ?? null,
      deadline_at: opts.deadline_at ?? null,
    });
  } else if (phase === "presented") {
    Object.assign(record, {
      channel: String(opts.channel || "unknown"),
      redacted_render_digest: _render_digest(safe_questions),
      option_tokens: _option_tokens(safe_questions),
    });
  } else {
    Object.assign(record, {
      outcome: String(opts.outcome || ""),
      accepted_answers: _persist_safe({ ...(opts.answers ?? {}) }),
      reason: _persist_safe(String(opts.reason || "")),
      presented: phases.has("presented"),
    });
  }
  try {
    _append_lifecycle_record(record);
  } catch (exc) {
    logger.exception(`ask_user 生命周期账写入失败: question_id=${qid} phase=${phase}`);
    if (phases.size === 0) {
      delete _LIFECYCLE_PHASES[qid];
    }
    return [false, { question_id: qid, phase, persistence_error: true }];
  }
  phases.add(phase);
  return [true, record];
}

function _render_terminal_replay(questions: Record<string, any>[], record: Record<string, any>): string {
  const outcome = String(record.outcome || "");
  if (outcome === "answered") {
    const answers = record.accepted_answers || {};
    if (answers === null || typeof answers !== "object" || Array.isArray(answers)) {
      return "error: persisted ask_user answer is invalid";
    }
    const positional: any[] = [];
    for (const question of questions) {
      const keys = [String(question.question || ""), String(question.header || ""), String(question.answer_key || "")];
      positional.push(keys.reduce((acc, k) => (acc !== undefined ? acc : k && k in answers ? answers[k] : undefined), undefined) ?? null);
    }
    const answer_bindings = questions
      .map((question, i) => ({ question, answer: positional[i] }))
      .filter(({ question, answer }) => String(question.answer_key || "") && answer !== null && answer !== "")
      .map(({ question }) => ({ answer_key: String(question.answer_key || ""), question_digest: _render_digest([question]) }));
    if (answer_bindings.length > 0) {
      const replay_record = {
        schema: _LIFECYCLE_SCHEMA,
        phase: _ANSWER_REPLAYED_PHASE,
        question_id: String(record.question_id || ""),
        owner: String(record.owner || ""),
        thread_id: String(record.thread_id || ""),
        ts: Date.now() / 1000,
        render_version: _RENDER_VERSION,
        answer_bindings,
      };
      try {
        _append_lifecycle_record(replay_record);
      } catch {
        logger.exception(`ask_user answered 重放收据写入失败: question_id=${replay_record.question_id}`);
        return "error: persisted ask_user answer replay could not be recorded";
      }
      (_LIFECYCLE_PHASES[replay_record.question_id] ??= new Set()).add(_ANSWER_REPLAYED_PHASE);
      _emit_lifecycle("ask_user_answer_replayed", replay_record);
    }
    _publish_positional_answers(positional);
    const header_by_q: Record<string, string> = {};
    for (const q of questions) {
      header_by_q[String(q.question ?? "")] = String(q.header ?? "") || "";
    }
    const parts: string[] = [];
    for (const [q_text, answerRaw] of Object.entries(answers)) {
      let answer = answerRaw;
      if (Array.isArray(answer)) {
        answer = answer.map((item) => String(item)).join(", ");
      }
      const header = header_by_q[String(q_text)] ?? "";
      const qs = String(q_text);
      const key = header || qs.slice(0, 40) + (qs.length > 40 ? "…" : "");
      parts.push(`"${key}"="${answer}"`);
    }
    return "User has answered your questions: " + parts.join(". ");
  }
  if (outcome === "timeout") {
    return TIMEOUT_MARK;
  }
  if (["cancelled", "teardown"].includes(outcome)) {
    return CANCEL_MARK;
  }
  if (outcome === "non_interactive") {
    return "error: ask_user previously resolved without an interactive channel";
  }
  return "error: persisted ask_user terminal outcome is unknown";
}

function _emit_lifecycle(kind: string, payload: Record<string, any>): void {
  try {
    const { get_default_bus } = require("../events");
    get_default_bus().emit(kind, { payload: _persist_safe(payload), tags: { name: "ask_user" } });
  } catch (exc) {
    logger.debug(`ask_user 生命周期事件发射失败: ${kind}`);
  }
}

export function mark_presented(question_id: string, rendered_questions: Record<string, any>[], opts: { channel?: string; owner?: string; thread_id?: string } = {}): boolean {
  const channel = opts.channel ?? "ink_tui";
  const owner = opts.owner ?? "";
  const thread_id = opts.thread_id ?? "";
  const [normalized] = _normalize_questions(rendered_questions);
  if (normalized === null) {
    return false;
  }
  rendered_questions = normalized;
  let payload: Record<string, any> = {};
  const pending = _PENDING[question_id];
  if (pending === undefined || pending.outcome !== null && pending.outcome !== undefined) {
    return false;
  }
  if (!_pending_authorized(pending, { owner, thread_id })) {
    return false;
  }
  if (_render_digest(rendered_questions) !== _render_digest(pending.questions || [])) {
    return false;
  }
  if (pending.presented === true) {
    return false;
  }
  const [accepted, record] = _record_lifecycle(question_id, "presented", {
    questions: rendered_questions,
    channel,
    owner: String(pending.owner || ""),
    thread_id: String(pending.thread_id || ""),
  });
  let recordOut = record;
  if (!accepted) {
    if (!(pending.recovered && (_LIFECYCLE_PHASES[question_id] ?? new Set()).has("presented"))) {
      return false;
    }
    recordOut = {
      channel,
      redacted_render_digest: _render_digest(rendered_questions),
      option_tokens: _option_tokens(rendered_questions),
      ts: Date.now() / 1000,
      recovered: true,
    };
  }
  pending.presented = true;
  payload = {
    question_id,
    owner: String(pending.owner || ""),
    thread_id: String(pending.thread_id || ""),
    channel: recordOut.channel ?? channel,
    redacted_render_digest: recordOut.redacted_render_digest ?? "",
    option_tokens: recordOut.option_tokens ?? [],
    ts: recordOut.ts,
    recovered: Boolean(recordOut.recovered),
  };
  _emit_lifecycle("ask_user_presented", payload);
  return true;
}

function _emit_resolved(question_id: string, outcome: string, opts: { answers?: Record<string, string> | null; reason?: string; owner?: string; thread_id?: string } = {}): boolean {
  const answers = opts.answers ?? null;
  const reason = opts.reason ?? "";
  const owner = opts.owner ?? "";
  const thread_id = opts.thread_id ?? "";
  const [accepted, record] = _record_lifecycle(question_id, "resolved", { outcome, answers, reason, owner, thread_id });
  if (!accepted) {
    return false;
  }
  _emit_lifecycle("ask_user_resolved", {
    question_id,
    owner,
    thread_id,
    outcome,
    answers: { ...(answers ?? {}) },
    reason,
    presented: Boolean(record.presented),
    ts: record.ts,
  });
  _QID_RESERVATIONS.delete(question_id);
  return true;
}

function _configured_timeout_s(): number {
  const raw = process.env.IST_ASK_TIMEOUT_S;
  let value: number;
  try {
    value = raw !== undefined && raw !== "" ? parseFloat(raw) : 0;
    if (Number.isNaN(value)) {
      throw new Error("nan");
    }
  } catch {
    logger.warning(`IST_ASK_TIMEOUT_S='${raw}' 非法，回落缺省（不超时）`);
    return 0.0;
  }
  if (!Number.isFinite(value)) {
    logger.warning(`IST_ASK_TIMEOUT_S='${raw}' 非有限值，回落缺省（不超时）`);
    return 0.0;
  }
  return value;
}

export function ask_user_with_timeout(questions: Record<string, any>[], opts: { timeout_s: number }): string {
  const previous = _WAIT_TIMEOUT_OVERRIDE_DEADLINE;
  _WAIT_TIMEOUT_OVERRIDE_DEADLINE = Date.now() + Math.max(0.0, Number(opts.timeout_s)) * 1000;
  try {
    return ask_user(questions);
  } finally {
    _WAIT_TIMEOUT_OVERRIDE_DEADLINE = previous;
  }
}

export function get_pending_question(question_id: string, opts: { owner?: string; thread_id?: string } = {}): Record<string, any> | null {
  const pending = _PENDING[question_id];
  if (pending === undefined || !_pending_authorized(pending, opts)) {
    return null;
  }
  return pending;
}

export function pending_question_access(question_id: string, opts: { owner: string; thread_id: string }): string {
  const pending = _PENDING[String(question_id || "")];
  if (pending === undefined) {
    return "missing";
  }
  if (_pending_authorized(pending, opts)) {
    return "authorized";
  }
  return "foreign";
}

export function list_pending_questions(opts: { owner?: string; thread_id?: string } = {}): Record<string, any>[] {
  const out: Record<string, any>[] = [];
  for (const [qid, q] of Object.entries(_PENDING)) {
    if (_pending_authorized(q, opts)) {
      const { _event, ...rest } = q;
      out.push({ question_id: qid, ...rest });
    }
  }
  return out;
}

export function has_live_pending_questions(): boolean {
  return Object.keys(_PENDING).length > 0;
}

export function cancel_all_pending(reason: string = "", opts: { owner?: string; thread_id?: string } = {}): number {
  const resolved: Array<[string, _Event]> = [];
  for (const [qid, pending] of Object.entries(_PENDING)) {
    if (!_pending_authorized(pending, opts)) {
      continue;
    }
    const evt = pending._event;
    if ((pending.outcome === null || pending.outcome === undefined) && evt !== undefined && evt !== null) {
      pending.answers = {};
      pending.outcome = "teardown";
      pending.reason = reason || "session teardown";
      resolved.push([qid, evt]);
    }
  }
  for (const [qid, evt] of resolved) {
    const pending = _PENDING[qid] ?? {};
    _emit_resolved(qid, "teardown", {
      reason: reason || "session teardown",
      owner: String(pending.owner || ""),
      thread_id: String(pending.thread_id || ""),
    });
    evt.set();
  }
  const n = resolved.length;
  if (n > 0) {
    logger.info(`ask_user teardown:取消 ${n} 个挂起问询${reason ? `(${reason})` : ""}`);
  }
  return n;
}

export function submit_answers(question_id: string, answers: Record<string, string>, opts: { owner?: string; thread_id?: string } = {}): boolean {
  const owner = opts.owner ?? "";
  const thread_id = opts.thread_id ?? "";
  let expired = false;
  let resolved_record: Record<string, any> = {};
  let evt: _Event | null = null;
  let bound_owner = "";
  let bound_thread = "";
  let outcome = "";
  let accepted: Record<string, any> = {};
  let reason = "";
  const pending = _PENDING[question_id];
  if (pending === undefined || (pending.outcome !== null && pending.outcome !== undefined) || (pending.answers !== null && pending.answers !== undefined)) {
    return false;
  }
  if (!_pending_authorized(pending, { owner, thread_id })) {
    return false;
  }
  bound_owner = String(pending.owner || "");
  bound_thread = String(pending.thread_id || "");
  const deadline = pending.deadline_monotonic;
  if (deadline !== null && deadline !== undefined && Date.now() >= Number(deadline)) {
    pending.answers = {};
    pending.outcome = "timeout";
    pending.reason = "wait deadline reached before answer submission";
    pending.terminal_event_emitted = true;
    evt = pending._event ?? null;
    expired = true;
  } else {
    accepted = { ...(answers || {}) };
    outcome = Object.values(accepted).some((v) => String(v)) ? "answered" : "cancelled";
    reason = outcome === "answered" ? "user submitted answers" : "user cancelled";
    const questions = (pending.questions || []).slice();
    if (outcome === "answered") {
      try {
        _append_answer_credential(question_id, questions, accepted, { owner: bound_owner, thread_id: bound_thread });
      } catch {
        logger.exception(`ask_user 答案凭证写入失败: question_id=${question_id}`);
        return false;
      }
    }
    const [recorded, rec] = _record_lifecycle(question_id, "resolved", { outcome, answers: accepted, reason, owner: bound_owner, thread_id: bound_thread });
    if (!recorded) {
      return false;
    }
    resolved_record = rec;
    pending.answers = accepted;
    pending.outcome = outcome;
    pending.reason = reason;
    evt = pending._event ?? null;
  }
  if (expired) {
    _emit_resolved(question_id, "timeout", { reason: "wait deadline reached before answer submission", owner: bound_owner, thread_id: bound_thread });
    if (evt !== null) {
      evt.set();
    }
    return false;
  }
  _emit_lifecycle("ask_user_resolved", {
    question_id,
    owner: bound_owner,
    thread_id: bound_thread,
    outcome,
    answers: accepted,
    reason,
    presented: Boolean(resolved_record.presented),
    ts: resolved_record.ts,
  });
  if (evt !== null) {
    evt.set();
  }
  return true;
}

const _REDECIDE_LOOKBACK_S = 6 * 3600.0;

export function engine_panel_origin<T>(fn: () => T): T {
  const prev = _ENGINE_PANEL_ORIGIN;
  _ENGINE_PANEL_ORIGIN = true;
  try {
    return fn();
  } finally {
    _ENGINE_PANEL_ORIGIN = prev;
  }
}

function _recently_decided_autoids(): Record<string, string> {
  try {
    const { WORKSPACE_OUTPUTS } = require("../../../knowledge_paths");
    const root = String(WORKSPACE_OUTPUTS);
    const { active_batch_fact_paths } = require("../compile_engine/batch_storage");
    const cands = (active_batch_fact_paths(root) as string[])
      .map((p) => ({ p, mtime: fs.statSync(p).mtimeMs }))
      .sort((a, b) => b.mtime - a.mtime)
      .map((x) => x.p);
    const now = Date.now() / 1000;
    for (const fj of cands.slice(0, 1)) {
      try {
        if (now - fs.statSync(fj).mtimeMs / 1000 > _REDECIDE_LOOKBACK_S) {
          break;
        }
        const decided = new Set<string>();
        const terminal = new Set<string>();
        for (const line of fs.readFileSync(fj, "utf8").split(/\r?\n/)) {
          if (!line.trim()) {
            continue;
          }
          let d: any;
          try {
            d = JSON.parse(line);
          } catch {
            continue;
          }
          const ev = d.ev;
          if (ev === "run_start") {
            decided.clear();
            terminal.clear();
          } else if (ev === "decision" && d.aid) {
            decided.add(String(d.aid));
          } else if (ev === "case_terminal_outcome" && d.aid) {
            terminal.add(String(d.aid));
          }
        }
        const both = [...decided].filter((a) => terminal.has(a));
        if (both.length > 0) {
          let rel: string;
          try {
            rel = path.relative(path.dirname(path.dirname(root)), fj);
            if (rel.startsWith("..")) {
              rel = fj;
            }
          } catch {
            rel = fj;
          }
          const out: Record<string, string> = {};
          for (const aid of both) {
            out[aid] = rel;
          }
          return out;
        }
      } catch {
        continue;
      }
    }
  } catch {
    return {};
  }
  return {};
}

function _redecide_guard(questions: Record<string, any>[]): string | null {
  if (_ENGINE_PANEL_ORIGIN) {
    return null;
  }
  const text = questions
    .filter((q) => q !== null && typeof q === "object")
    .map((q) => String(q.question || "") + " " + String(q.header || ""))
    .join(" ");
  const aids = new Set(text.match(/(?<!\d)\d{18}(?!\d)/g) || []);
  const tails = new Set([...text.matchAll(/尾号\s*[:：]?\s*(\d{4,18})/g)].map((m) => m[1]));
  if (aids.size === 0 && tails.size === 0) {
    return null;
  }
  const decided = _recently_decided_autoids();
  const hit = [
    ...new Set([
      ...Object.keys(decided).filter((a) => aids.has(a)),
      ...Object.keys(decided).filter((a) => [...tails].some((t) => a.endsWith(t))),
    ]),
  ].sort();
  if (hit.length === 0) {
    return null;
  }
  const ref = decided[hit[0]];
  return (
    "error: re-ask blocked — case(s) " +
    hit.map((a) => `…${a.slice(-6)}`).join(", ") +
    ` were already decided AND reached terminal outcome in the batch that just closed (see \`${ref}\`: decision + case_terminal_outcome facts). The user's answers are final for that batch; read them from the facts instead of re-opening a panel. Drop those questions, or re-dispatch the batch if a genuinely new decision is needed.`
  );
}

export function ask_user(questions: Record<string, any>[]): string {
  const [normalized, validation_error] = _normalize_questions(questions);
  if (normalized === null) {
    return `error: ${validation_error}`;
  }
  questions = normalized;
  const blocked = _redecide_guard(questions);
  if (blocked) {
    return blocked;
  }
  const [hil_owner, hil_thread_id] = _current_hil_identity();
  const [question_id, restored_phases, terminal_record] = _allocate_question_id(questions, { owner: hil_owner, thread_id: hil_thread_id });
  if (terminal_record !== null) {
    return _render_terminal_replay(questions, terminal_record);
  }
  if (!question_id) {
    return "error: an identical ask_user request is already pending";
  }
  const event = new _Event();
  const _timeout_s = _configured_timeout_s();
  const _override_deadline = _WAIT_TIMEOUT_OVERRIDE_DEADLINE;
  const _now = Date.now();
  const _wall_now = Date.now() / 1000;
  let _effective_timeout_s: number | null;
  if (_override_deadline !== null) {
    const _override_remaining_s = Math.max(0.0, (_override_deadline - _now) / 1000);
    _effective_timeout_s = _timeout_s > 0 ? Math.min(_timeout_s, _override_remaining_s) : _override_remaining_s;
  } else {
    _effective_timeout_s = _timeout_s > 0 ? _timeout_s : null;
  }
  const _restored_schedule = [..._lifecycle_records()]
    .reverse()
    .find(
      (record) =>
        record.question_id === question_id &&
        record.phase === "scheduled" &&
        String(record.owner || "") === hil_owner &&
        String(record.thread_id || "") === hil_thread_id
    ) ?? null;
  let _restored_deadline_at: number | null = null;
  if (_restored_schedule !== null && typeof _restored_schedule === "object") {
    try {
      _restored_deadline_at = parseFloat(_restored_schedule.deadline_at);
      if (Number.isNaN(_restored_deadline_at)) {
        throw new Error("nan");
      }
    } catch {
      try {
        const budget = parseFloat(_restored_schedule.wait_budget_s);
        _restored_deadline_at = parseFloat(_restored_schedule.ts) + budget;
        if (Number.isNaN(_restored_deadline_at)) {
          _restored_deadline_at = null;
        }
      } catch {
        _restored_deadline_at = null;
      }
    }
  }
  let _deadline_at: number | null;
  if (_restored_deadline_at !== null && _effective_timeout_s !== null) {
    _effective_timeout_s = Math.max(0.0, _restored_deadline_at - _wall_now);
    _deadline_at = _restored_deadline_at;
  } else {
    _deadline_at = _effective_timeout_s !== null ? _wall_now + Math.max(0.0, _effective_timeout_s) : null;
  }
  const _deadline = _effective_timeout_s !== null ? _now + Math.max(0.0, _effective_timeout_s) * 1000 : null;
  const pending: Record<string, any> = {
    question_id,
    owner: hil_owner,
    thread_id: hil_thread_id,
    questions,
    answers: null,
    outcome: null,
    reason: "",
    presented: false,
    terminal_event_emitted: false,
    recovered: restored_phases.size > 0,
    deadline_monotonic: _deadline,
    _event: event,
  };
  let scheduled_ok: boolean;
  let scheduled: Record<string, any>;
  if (restored_phases.has("scheduled") && !restored_phases.has("resolved")) {
    scheduled_ok = true;
    scheduled = {
      question_id,
      render_version: _RENDER_VERSION,
      redacted_render_digest: _render_digest(questions),
      option_tokens: _option_tokens(questions),
      wait_budget_s: _effective_timeout_s,
      deadline_at: _deadline_at,
      ts: Date.now() / 1000,
      recovered: true,
    };
  } else {
    [scheduled_ok, scheduled] = _record_lifecycle(question_id, "scheduled", {
      questions,
      wait_budget_s: _effective_timeout_s,
      deadline_at: _deadline_at,
      owner: hil_owner,
      thread_id: hil_thread_id,
    });
  }
  if (!scheduled_ok) {
    _QID_RESERVATIONS.delete(question_id);
    return "error: ask_user request could not be durably scheduled; no question was presented";
  }
  _PENDING[question_id] = pending;
  _emit_lifecycle("ask_user_scheduled", {
    question_id,
    owner: hil_owner,
    thread_id: hil_thread_id,
    questions: _json_safe(questions),
    render_version: scheduled.render_version ?? _RENDER_VERSION,
    redacted_render_digest: scheduled.redacted_render_digest ?? "",
    option_tokens: scheduled.option_tokens ?? [],
    wait_budget_s: _effective_timeout_s,
    ts: scheduled.ts,
    recovered: Boolean(scheduled.recovered),
  });
  const _non_interactive = ["1", "true", "True"].includes((process.env.IST_NON_INTERACTIVE || "").trim());
  const _wecom_bot = ["1", "true", "True"].includes((process.env.IST_WECOM_BOT || "").trim());
  if (_non_interactive && !_wecom_bot) {
    pending.answers = {};
    pending.outcome = "non_interactive";
    pending.reason = "no interactive channel";
    delete _PENDING[question_id];
    _emit_resolved(question_id, "non_interactive", { reason: "no interactive channel", owner: hil_owner, thread_id: hil_thread_id });
    const _q_summary = questions.map((q) => String(q.question ?? "")).join(" | ");
    return `error: 当前为非交互模式（无 TUI，无法向用户提问），ask_user 不可用。请改为：从用户请求原文中提取该信息；若请求确实未提供该必要信息，请停止并明确报告『缺少哪项信息、为何无法在不询问用户的情况下继续』，不要臆测或自行选默认值。 你本想问的是：${_q_summary}`;
  }
  if (_deadline !== null && Date.now() >= _deadline) {
    pending.answers = {};
    pending.outcome = "timeout";
    pending.reason = "wait budget exhausted before presentation";
    pending.terminal_event_emitted = true;
    delete _PENDING[question_id];
    _emit_resolved(question_id, "timeout", { reason: "wait budget exhausted before presentation", owner: hil_owner, thread_id: hil_thread_id });
    return TIMEOUT_MARK;
  }
  _emit_lifecycle("ask_user_request", { question_id, owner: hil_owner, thread_id: hil_thread_id, questions: _json_safe(questions) });
  try {
    const { scrub_text } = require("../../security_scrub");
    const _qs = questions
      .map((q) => String(q.question ?? "") + " [" + (q.options || []).map((o: any) => String(o.label ?? "")).join("/") + "]")
      .join("; ");
    process.stderr.write(`[ask_user] agent 提问: ${scrub_text(_qs)}\n`);
  } catch {}
  const _wait_s = _deadline === null ? null : Math.max(0.0, (_deadline - Date.now()) / 1000);
  const _answered_in_time = event.wait(_wait_s);
  let emit_timeout = false;
  let outcome2 = String(pending.outcome || "");
  if (!outcome2) {
    outcome2 = !_answered_in_time ? "timeout" : "cancelled";
    pending.answers = {};
    pending.outcome = outcome2;
    pending.reason = outcome2 === "timeout" ? "wait deadline reached" : "question ended without answer";
  }
  const answers2 = { ...(pending.answers || {}) };
  const reason2 = String(pending.reason || "");
  if (outcome2 === "timeout" && !pending.terminal_event_emitted) {
    pending.terminal_event_emitted = true;
    emit_timeout = true;
  }
  delete _PENDING[question_id];
  if (outcome2 !== "answered") {
    if (outcome2 === "timeout") {
      if (emit_timeout) {
        _emit_resolved(question_id, "timeout", { reason: reason2, owner: hil_owner, thread_id: hil_thread_id });
      }
      return TIMEOUT_MARK;
    }
    return CANCEL_MARK;
  }
  const header_by_q: Record<string, string> = {};
  for (const q of questions) {
    header_by_q[String(q.question ?? "")] = String(q.header ?? "") || "";
  }
  _publish_positional_answers(questions.map((q) => answers2[String(q.question ?? "")] ?? null));
  const parts: string[] = [];
  for (const [q_text, aRaw] of Object.entries(answers2)) {
    let a: any = aRaw;
    if (Array.isArray(a)) {
      a = a.map((x) => String(x)).join(", ");
    }
    const h = header_by_q[String(q_text)] ?? "";
    const qs = String(q_text);
    const key = h || qs.slice(0, 40) + (qs.length > 40 ? "…" : "");
    parts.push(`"${key}"="${a}"`);
  }
  return "User has answered your questions: " + parts.join(". ");
}
