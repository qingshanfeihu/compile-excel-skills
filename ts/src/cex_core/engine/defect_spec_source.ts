import crypto from "node:crypto";
import { htmlUnescape } from "./_html_unescape";
import { accepts_schema } from "./common/schema_identity";

export const RECEIPT_SCHEMA = "ist.defect-spec-receipt";
export const VALIDATION_SCHEMA = "ist.defect-spec-receipt-validation";
export const SOURCE_CONTEXT_SCHEMA = "ist.defect-spec-source-context";
const _SHA256_RE = /^[0-9a-f]{64}$/;
const _EXACT_TICKET_RE = /^(?:[A-Za-z][A-Za-z0-9_]*-)?(\d+)$/;
const _DOC_TYPE_RE = /^[a-z][a-z0-9_-]{0,31}$/;
const _ALLOWED_BACKENDS = new Set(["bugzilla", "zentao", "zentao_story"]);
const _PLACEHOLDER_TOKEN_RE = /^\[(?:步骤|步驟|结果|結果|期望|操作|重现步骤|重現步驟)\]$/;
const _WIPE_DESCRIPTION_REASONS = new Set(["description_contains_actual_or_logs", "declaration_contains_credential_material"]);
const _FIXED_BACKENDS = ["bugzilla", "zentao", "zentao_story"] as const;
const _CONTROL_RE = /[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/g;
const _URL_RE = /\b(?:https?|ftp):\/\/[^\s<>]+/gi;
const _WINDOWS_PATH_RE = /(?<!\w)[A-Za-z]:\\(?:[^\s\\]+\\)*[^\s\\]+/g;
const _UNIX_PATH_RE = /(?<![\w:])\/(?:[^\s/]+\/)+[^\s/]+/g;
const _REPO_PATH_RE = /\b(?:workspace|knowledge|runtime|main|tests)\/(?:[^\s/]+\/)*[^\s/]+/g;
const _PRIVATE_KEY_RE = /-----BEGIN [^-\r\n]*PRIVATE KEY-----.*?-----END [^-\r\n]*PRIVATE KEY-----/is;
const _ENV_KEY_BODY = "[A-Za-z][A-Za-z0-9_]*(?:PASSWORD|PASSWD|PWD|SECRET|TOKEN|API_KEY|ACCESS_KEY|LICENSE_KEY)";
const _GENERIC_CREDENTIAL_KEY_BODY = `(?:${_ENV_KEY_BODY}|password|passwd|pwd|secret|api[_ -]?key|access[_ -]?token|authorization|cookie|license[_ -]?key)`;
const _CREDENTIAL_RE = new RegExp("\\b(?:password|passwd|pwd|secret|api[_ -]?key|access[_ -]?token|authorization|cookie|license[_ -]?key)\\b\\s*[:=]\\s*[^\\r\\n]+", "gim");
const _ENV_CREDENTIAL_RE = new RegExp(`(?<![A-Za-z0-9_])[\\"']?${_ENV_KEY_BODY}[\\"']?\\s*[:=]\\s*(?:[\\"'][^\\"'\\r\\n]*[\\"']|[^\\r\\n]+)`, "gim");
const _HTML_TAG_RE = /<\/?[A-Za-z][^>\r\n]*>/g;
const _HTML_BLOCK_TAG_RE = /<\/?(?:h[1-6]|p|div|li|br|tr|td|th|section|article)[^>\r\n]*>/gi;
const _ANSI_ESCAPE_RE = /\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))/g;
const _MARKDOWN_LINK_RE = /\[([^\]\r\n]+)\]\([^\)\r\n]*\)/g;
const _DECORATED_CREDENTIAL_KEY_RE = new RegExp(`(?<![A-Za-z0-9_])(?:\\*\\*|__|\`{1,3})?[\\"']?(?<key>${_GENERIC_CREDENTIAL_KEY_BODY})[\\"']?(?:\\*\\*|__|\`{1,3})?\\s*(?<sep>[:=])`, "gim");
const _YAML_CREDENTIAL_BLOCK_RE = new RegExp(`^[ \\t]*[\\"']?${_GENERIC_CREDENTIAL_KEY_BODY}[\\"']?\\s*[:=]\\s*[|>][+-]?[ \\t]*(?:\\r?\\n[ \\t]+[^\\r\\n]*)+`, "im");
const _MARKDOWN_TABLE_CREDENTIAL_RE = new RegExp(`^[ \\t]*\\|[ \\t]*(?:\\*\\*|__|\`{1,3})?[\\"']?${_GENERIC_CREDENTIAL_KEY_BODY}[\\"']?(?:\\*\\*|__|\`{1,3})?[ \\t]*\\|[ \\t]*[^|\\r\\n]+(?:\\|[^\\r\\n]*)?$`, "im");
const _ADJACENT_CREDENTIAL_VALUE_RE = new RegExp(`^[ \\t|]*(?:\\*\\*|__|\`{1,3})?[\\"']?${_GENERIC_CREDENTIAL_KEY_BODY}[\\"']?(?:\\*\\*|__|\`{1,3})?(?:[ \\t]*\\|[ \\t]*[^|\\r\\n]+|\\r?\\n[ \\t]*[^\\r\\n]+|[ \\t]+[^|\\r\\n]+)(?:\\|[^\\r\\n]*)?$`, "im");
const _AUTH_SCHEME_CREDENTIAL_RE = /(?<![A-Za-z0-9_])authorization\s+(?:bearer|basic)\s+\S+/im;
const _CLI_CREDENTIAL_RE = new RegExp(`(?<![A-Za-z0-9_])--(?:${_GENERIC_CREDENTIAL_KEY_BODY})(?:\\s*=\\s*|\\s+)(?:[\\"'][^\\"'\\r\\n]*[\\"']|\\S+)`, "im");
const _SENSITIVE_CREDENTIAL_KEY_RE = new RegExp(`^(?:${_GENERIC_CREDENTIAL_KEY_BODY})$`, "i");
const _PROHIBITED_HEADING_RE = /(?:actual\s+(?:results?|behaviors?|outputs?)|observed\s+(?:results?|behaviors?|outputs?)|actual|log\s+(?:outputs?|entries?|history)|logs?|steps?\s+to\s+reproduce|reproduction(?:\s+steps?)?|repro(?:duction)?(?:\s+steps?)?|comment\s+history|comments?|how\s+to\s+reproduce|cli\s+output|notes?|remarks?|show\s+version|detail\s+information|实际结果|实际现象|当前结果|实际输出|复现步骤|复现过程|评论|备注|日志|复现|设备回显)/i;
const _PROHIBITED_LABEL_RE = new RegExp(`(?<![A-Za-z0-9_])(?:${_PROHIBITED_HEADING_RE.source})(?:\\s*(?:for|on|\\/|[-–—]|[\\[(（【])[^:：\\r\\n]*)?\\s*(?:[:：]|$)`, "i");
const _MARKDOWN_DECORATION_RE = /^[*_~`\s]+|[*_~`\s]+$/g;
const _ATX_OPEN_RE = /^#{1,6}\s+/;
const _ATX_CLOSE_RE = /\s+#{1,6}\s*$/g;
const _BLOCKQUOTE_RE = /^>\s*/;
const _UNORDERED_LIST_RE = /^[-+*]\s+/;
const _ORDERED_LIST_RE = /^\d+[.)、．]\s*/;
const _CHINESE_ORDER_RE = /^(?:[（(][一二三四五六七八九十百千]+[）)]|[一二三四五六七八九十百千]+[、.)）．])\s*/;
const _TASK_LIST_RE = /^\[(?: |x|X)\]\s*/;
const _MAX_SOURCE_SEMANTIC_CHARS = 1024 * 1024;
const _MAX_DEFECT_CANDIDATES = 64;
const _MAX_CANDIDATE_SEMANTIC_CHARS = 512 * 1024;
const _MAX_TOTAL_CANDIDATE_SEMANTIC_CHARS = 4 * 1024 * 1024;
const _MAX_CANDIDATE_JSON_BYTES = 2 * 1024 * 1024;
const _MAX_CANDIDATE_JSON_TOKENS = 100000;
const _MAX_CANDIDATE_JSON_DEPTH = 64;

function _isPlainObject(v: any): v is Record<string, any> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function _canonicalJsonBytes(value: any): Buffer {
  return Buffer.from(_canonicalJsonString(value), "utf8");
}

function _canonicalJsonString(value: any): string {
  if (value === null) return "null";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") return _jsonNumber(value);
  if (typeof value === "string") return _jsonString(value);
  if (Array.isArray(value)) return "[" + value.map(_canonicalJsonString).join(",") + "]";
  if (_isPlainObject(value)) {
    const keys = Object.keys(value).sort();
    return "{" + keys.map((k) => _jsonString(k) + ":" + _canonicalJsonString(value[k])).join(",") + "}";
  }
  return JSON.stringify(value);
}

function _jsonString(s: string): string {
  let out = '"';
  for (const ch of s) {
    const code = ch.codePointAt(0)!;
    if (ch === '"') out += '\\"';
    else if (ch === "\\") out += "\\\\";
    else if (ch === "\b") out += "\\b";
    else if (ch === "\f") out += "\\f";
    else if (ch === "\n") out += "\\n";
    else if (ch === "\r") out += "\\r";
    else if (ch === "\t") out += "\\t";
    else if (code < 0x20) out += "\\u" + code.toString(16).padStart(4, "0");
    else out += ch;
  }
  return out + '"';
}

function _jsonNumber(n: number): string {
  if (Number.isInteger(n)) {
    if (Object.is(n, -0)) return "-0.0";
    return String(n);
  }
  if (!Number.isFinite(n)) {
    return String(n);
  }
  let s = String(n);
  if (/e/i.test(s)) {
    s = s.replace(/e\+?/i, "e");
    s = s.replace(/e(-?)0+(\d)/, "e$1$2");
  }
  return s;
}

function _sha256Json(value: any): string {
  return crypto.createHash("sha256").update(_canonicalJsonBytes(value)).digest("hex");
}

function _sourceContextSha256(title: string, text: string): string {
  return _sha256Json({ title, text });
}

export function _build_source_context_binding(
  source_title: string,
  source_text: string,
  source_sha256: string
): [Record<string, any> | null, string] {
  let sourceBytes: Buffer;
  try {
    sourceBytes = Buffer.from(source_text, "utf8");
  } catch {
    return [null, "sealed_source_text_not_utf8"];
  }
  if (crypto.createHash("sha256").update(sourceBytes).digest("hex") !== source_sha256) {
    return [null, "sealed_source_text_sha256_mismatch"];
  }
  let titleLocator: Record<string, any>;
  if (source_title) {
    const titleStart = source_text.indexOf(source_title);
    if (titleStart < 0 || source_text.indexOf(source_title, titleStart + 1) >= 0) {
      return [null, "source_title_not_uniquely_located"];
    }
    titleLocator = { kind: "utf8_character_range", start: titleStart, end: titleStart + source_title.length };
  } else {
    titleLocator = { kind: "absent" };
  }
  return [
    { schema: SOURCE_CONTEXT_SCHEMA, encoding: "utf-8", text_locator: { kind: "whole_file" }, title_locator: titleLocator },
    "",
  ];
}

export function validate_source_context_binding(
  source_bytes: Buffer,
  source_sha256: string,
  source_context: Record<string, any>,
  source_content_sha256: string
): boolean {
  if (crypto.createHash("sha256").update(source_bytes).digest("hex") !== source_sha256) {
    return false;
  }
  let sourceText: string;
  try {
    sourceText = source_bytes.toString("utf8");
  } catch {
    return false;
  }
  if (sourceText.length > _MAX_SOURCE_SEMANTIC_CHARS) {
    return false;
  }
  if (!_isPlainObject(source_context) || Object.keys(source_context).sort().join(",") !== "encoding,schema,text_locator,title_locator") {
    return false;
  }
  if (
    source_context.schema !== SOURCE_CONTEXT_SCHEMA ||
    source_context.encoding !== "utf-8" ||
    JSON.stringify(source_context.text_locator) !== JSON.stringify({ kind: "whole_file" })
  ) {
    return false;
  }
  const titleLocator = source_context.title_locator;
  if (!_isPlainObject(titleLocator)) {
    return false;
  }
  let sourceTitle: string;
  if (JSON.stringify(titleLocator) === JSON.stringify({ kind: "absent" })) {
    sourceTitle = "";
  } else {
    if (Object.keys(titleLocator).sort().join(",") !== "end,kind,start") {
      return false;
    }
    const start = titleLocator.start;
    const end = titleLocator.end;
    if (
      titleLocator.kind !== "utf8_character_range" ||
      typeof start === "boolean" || typeof start !== "number" || !Number.isInteger(start) ||
      typeof end === "boolean" || typeof end !== "number" || !Number.isInteger(end) ||
      start < 0 || end <= start || end > sourceText.length
    ) {
      return false;
    }
    sourceTitle = sourceText.slice(start, end);
    if (sourceText.split(sourceTitle).length - 1 !== 1) {
      return false;
    }
  }
  return source_content_sha256 === _sourceContextSha256(sourceTitle, sourceText);
}

function _candidateJsonBytes(ticket: Record<string, any>): Buffer {
  const stack: Array<[any, number]> = [[ticket, 1]];
  const activeContainers = new Set<any>();
  let tokens = 0;
  let estimatedBytes = 0;
  while (stack.length) {
    const [value, depth] = stack.pop()!;
    if (depth > _MAX_CANDIDATE_JSON_DEPTH) {
      throw new Error("candidate JSON depth budget exceeded");
    }
    if (_isPlainObject(value)) {
      if (activeContainers.has(value)) {
        throw new Error("candidate JSON contains a container cycle");
      }
      activeContainers.add(value);
      tokens += 1 + Object.keys(value).length;
      if (tokens > _MAX_CANDIDATE_JSON_TOKENS) {
        throw new Error("candidate JSON token budget exceeded");
      }
      for (const key of Object.keys(value)) {
        if (typeof key !== "string") {
          throw new Error("candidate JSON object keys must be strings");
        }
        if (key.length > _MAX_CANDIDATE_JSON_BYTES) {
          throw new Error("candidate JSON byte budget exceeded");
        }
        estimatedBytes += Buffer.byteLength(key, "utf8") + 4;
        if (estimatedBytes > _MAX_CANDIDATE_JSON_BYTES) {
          throw new Error("candidate JSON byte budget exceeded");
        }
        stack.push([value[key], depth + 1]);
      }
      activeContainers.delete(value);
      continue;
    }
    if (Array.isArray(value)) {
      if (activeContainers.has(value)) {
        throw new Error("candidate JSON contains a container cycle");
      }
      activeContainers.add(value);
      tokens += 1 + value.length;
      if (tokens > _MAX_CANDIDATE_JSON_TOKENS) {
        throw new Error("candidate JSON token budget exceeded");
      }
      for (const child of value) {
        stack.push([child, depth + 1]);
      }
      activeContainers.delete(value);
      continue;
    }
    tokens += 1;
    if (tokens > _MAX_CANDIDATE_JSON_TOKENS) {
      throw new Error("candidate JSON token budget exceeded");
    }
    if (typeof value === "string") {
      if (value.length > _MAX_CANDIDATE_JSON_BYTES) {
        throw new Error("candidate JSON byte budget exceeded");
      }
      estimatedBytes += Buffer.byteLength(value, "utf8") + 2;
    } else if (value === null || typeof value === "boolean") {
      estimatedBytes += 5;
    } else if (typeof value === "number") {
      if (Number.isInteger(value)) {
        const bitLength = value === 0 ? 0 : Math.floor(Math.log2(Math.abs(value))) + 1;
        if (bitLength > 4096) {
          throw new Error("candidate JSON integer budget exceeded");
        }
        estimatedBytes += Math.max(1, Math.floor(bitLength / 3) + 2);
      } else {
        if (!Number.isFinite(value)) {
          throw new Error("candidate JSON number is not finite");
        }
        estimatedBytes += 32;
      }
    } else {
      throw new Error("candidate contains a non-JSON value");
    }
    if (estimatedBytes > _MAX_CANDIDATE_JSON_BYTES) {
      throw new Error("candidate JSON byte budget exceeded");
    }
  }
  let payload: Buffer;
  try {
    payload = _canonicalJsonBytes(ticket);
  } catch (exc) {
    throw new Error("candidate cannot be canonically serialized");
  }
  if (payload.length > _MAX_CANDIDATE_JSON_BYTES) {
    throw new Error("candidate JSON byte budget exceeded");
  }
  const { validate_json_budget } = require("./case_compiler/_sealed_io");
  validate_json_budget(payload, {
    errorType: Error,
    message: "candidate JSON structure budget exceeded",
    maxDepth: _MAX_CANDIDATE_JSON_DEPTH,
    maxTokens: _MAX_CANDIDATE_JSON_TOKENS,
  });
  return payload;
}

const _RUNTIME_TICKET_KEYS = new Set([
  "_resolver_backend_hint",
  "_ticket_file_sha256",
  "_ticket_file_sha256_verified",
  "_ticket_payload_sha256",
  "defect_spec_candidate",
]);

export function canonical_ticket_payload_sha256(ticket: Record<string, any>): string {
  _candidateJsonBytes(ticket);
  const filtered: Record<string, any> = {};
  for (const key of Object.keys(ticket)) {
    if (!_RUNTIME_TICKET_KEYS.has(String(key))) {
      filtered[String(key)] = ticket[key];
    }
  }
  const payload = _candidateJsonBytes(filtered);
  return crypto.createHash("sha256").update(payload).digest("hex");
}

function _exactTicketNumber(value: any): string | null {
  const match = _EXACT_TICKET_RE.exec(String(value ?? "").trim());
  return match ? match[1] : null;
}

function _safeTicketId(value: any): string {
  const raw = String(value ?? "").trim();
  if (!_EXACT_TICKET_RE.test(raw)) {
    return "";
  }
  return /^\d+$/.test(raw) ? raw : raw.toUpperCase();
}

function _semanticTokens(text: string): Set<string> {
  const tokens = new Set<string>();
  for (const m of (text || "").matchAll(/[A-Za-z][A-Za-z0-9_-]{1,}/g)) {
    tokens.add(m[0].toLowerCase());
  }
  for (const m of (text || "").matchAll(/[一-鿿]+/g)) {
    const segment = m[0];
    if (segment.length === 1) {
      tokens.add(segment);
    } else {
      for (let i = 0; i < segment.length - 1; i++) {
        tokens.add(segment.slice(i, i + 2));
      }
    }
  }
  return tokens;
}

function _stripCf(text: string): string {
  let out = "";
  for (const ch of text) {
    const code = ch.codePointAt(0)!;
    if (
      (code >= 0x00ad && code <= 0x00ad) ||
      (code >= 0x0600 && code <= 0x0605) ||
      (code >= 0x061c && code <= 0x061c) ||
      (code >= 0x06dd && code <= 0x06dd) ||
      (code >= 0x070f && code <= 0x070f) ||
      (code >= 0x0890 && code <= 0x0891) ||
      (code >= 0x08e2 && code <= 0x08e2) ||
      (code >= 0x180e && code <= 0x180e) ||
      (code >= 0x200b && code <= 0x200f) ||
      (code >= 0x202a && code <= 0x202e) ||
      (code >= 0x2060 && code <= 0x2064) ||
      (code >= 0x2066 && code <= 0x206f) ||
      (code >= 0xfeff && code <= 0xfeff) ||
      (code >= 0xfff9 && code <= 0xfffb) ||
      (code >= 0x110bd && code <= 0x110bd) ||
      (code >= 0x110cd && code <= 0x110cd) ||
      (code >= 0x13430 && code <= 0x13438) ||
      (code >= 0x1bca0 && code <= 0x1bca3) ||
      (code >= 0x1d173 && code <= 0x1d17a) ||
      (code >= 0xe0001 && code <= 0xe0001) ||
      (code >= 0xe0020 && code <= 0xe007f)
    ) {
      continue;
    }
    out += ch;
  }
  return out;
}

function _normalizeSecurityMarkup(value: any, preserveBlocks: boolean): string {
  let text = htmlUnescape(String(value ?? ""));
  text = _stripCf(_ANSI_ESCAPE_RE[Symbol.replace](text, ""));
  if (preserveBlocks) {
    text = text.replace(_HTML_BLOCK_TAG_RE, "\n");
  }
  text = text.replace(_HTML_TAG_RE, " ");
  text = text.replace(_MARKDOWN_LINK_RE, (_m, g1) => g1);
  return text;
}

function _normalizeCredentialMarkup(value: any): string {
  const text = _normalizeSecurityMarkup(value, false);
  return text.replace(_DECORATED_CREDENTIAL_KEY_RE, (_m, ...args) => {
    const groups = args[args.length - 1];
    return `${groups.key}${groups.sep}`;
  });
}

export function is_sensitive_credential_key(value: any): boolean {
  let normalized = _normalizeCredentialMarkup(value).trim();
  normalized = normalized.replace(_MARKDOWN_DECORATION_RE, "").trim();
  normalized = normalized.replace(/^[|\[\](){}<>"' ]+|[|\[\](){}<>"' ]+$/g, "");
  if (normalized.startsWith("--")) {
    normalized = normalized.slice(2);
  }
  return _SENSITIVE_CREDENTIAL_KEY_RE.test(normalized);
}

function _containsCredentialMaterial(value: any): boolean {
  const normalized = _normalizeCredentialMarkup(value);
  const { scrub_text } = require("./ist_core/security_scrub");
  return Boolean(
    scrub_text(normalized, { scrub_paths: false }) !== normalized ||
      _PRIVATE_KEY_RE.test(normalized) ||
      _YAML_CREDENTIAL_BLOCK_RE.test(normalized) ||
      _MARKDOWN_TABLE_CREDENTIAL_RE.test(normalized) ||
      _ADJACENT_CREDENTIAL_VALUE_RE.test(normalized) ||
      _AUTH_SCHEME_CREDENTIAL_RE.test(normalized) ||
      _CLI_CREDENTIAL_RE.test(normalized) ||
      _ENV_CREDENTIAL_RE.test(normalized) ||
      _CREDENTIAL_RE.test(normalized)
  );
}

export function contains_credential_material(value: any): boolean {
  return _containsCredentialMaterial(value);
}

function _coverage(left: Set<string>, right: Set<string>): number {
  if (left.size === 0 || right.size === 0) {
    return 0.0;
  }
  let inter = 0;
  for (const t of left) {
    if (right.has(t)) inter++;
  }
  return inter / left.size;
}

function _dice(left: Set<string>, right: Set<string>): number {
  if (left.size === 0 || right.size === 0) {
    return 0.0;
  }
  let inter = 0;
  for (const t of left) {
    if (right.has(t)) inter++;
  }
  return (2 * inter) / (left.size + right.size);
}

export function scrub_declaration_text(value: any, limit = 8000): string {
  let text = _normalizeCredentialMarkup(value).replace(_CONTROL_RE, "");
  if (_containsCredentialMaterial(text)) {
    return "[redacted-credential-field]".slice(0, limit);
  }
  text = text.replace(_PRIVATE_KEY_RE, "[redacted-private-key]");
  text = text.replace(_YAML_CREDENTIAL_BLOCK_RE, "[redacted-credential]");
  text = text.replace(_ENV_CREDENTIAL_RE, "[redacted-credential]");
  text = text.replace(_CREDENTIAL_RE, "[redacted-credential]");
  text = text.replace(_URL_RE, "[redacted-url]");
  text = text.replace(_WINDOWS_PATH_RE, "[redacted-path]");
  text = text.replace(_UNIX_PATH_RE, "[redacted-path]");
  text = text.replace(_REPO_PATH_RE, "[redacted-path]");
  text = text.replace(/[ \t]+/g, " ");
  text = text.replace(/\n{3,}/g, "\n\n").trim();
  return text.slice(0, limit);
}

export function contains_prohibited_declaration(value: any): boolean {
  const normalized = _normalizeSecurityMarkup(value, true);
  for (const rawLine of normalized.split(/\r?\n/)) {
    let line = rawLine.trim();
    for (let i = 0; i < 12; i++) {
      const previous = line;
      for (const pattern of [_BLOCKQUOTE_RE, _ATX_OPEN_RE, _UNORDERED_LIST_RE, _ORDERED_LIST_RE, _CHINESE_ORDER_RE, _TASK_LIST_RE]) {
        line = line.replace(pattern, "").trim();
      }
      if (line === previous) {
        break;
      }
    }
    line = line.replace(_ATX_CLOSE_RE, "").trim();
    line = line.replace(_MARKDOWN_DECORATION_RE, "").trim();
    if (!line) {
      continue;
    }
    if (_PROHIBITED_LABEL_RE.test(line)) {
      return true;
    }
    let heading: string;
    if (line.startsWith("[") && line.includes("]")) {
      heading = line.slice(1, line.indexOf("]"));
    } else {
      heading = line.split(/[:：]/, 2)[0];
    }
    heading = heading.replace(_ATX_CLOSE_RE, "").trim();
    heading = heading.replace(_MARKDOWN_DECORATION_RE, "").trim();
    const match = _PROHIBITED_HEADING_RE.exec(heading);
    const qualifier = match !== null && match.index === 0 ? heading.slice(match[0].length) : match !== null ? "" : "";
    const matched = match !== null && match.index === 0;
    if (matched && (!qualifier || /^\s*(?:[\[(（【].*[\])）】]|[-–—]\s*.+)$/.test(qualifier))) {
      return true;
    }
  }
  return false;
}

function _candidateSemanticSize(ticket: Record<string, any>, canonicalPayload?: Buffer | null): number {
  return (canonicalPayload || _candidateJsonBytes(ticket)).length;
}

function _metadata(ticket: Record<string, any>): Record<string, any> {
  const value = ticket.metadata;
  return _isPlainObject(value) ? value : {};
}

function _stringList(value: any): string[] {
  let items: any[];
  if (typeof value === "string") {
    items = [value];
  } else if (Array.isArray(value)) {
    items = value;
  } else {
    items = [];
  }
  const out = new Set<string>();
  for (const item of items) {
    if (String(item ?? "").trim()) {
      out.add(scrub_declaration_text(item, 256));
    }
  }
  return Array.from(out).sort();
}

function _rawTicketSha256(ticket: Record<string, any>): string {
  const supplied = String(ticket._ticket_file_sha256 || "").toLowerCase();
  const suppliedPayload = String(ticket._ticket_payload_sha256 || "").toLowerCase();
  if (
    ticket._ticket_file_sha256_verified === true &&
    _SHA256_RE.test(supplied) &&
    _SHA256_RE.test(suppliedPayload) &&
    suppliedPayload === canonical_ticket_payload_sha256(ticket)
  ) {
    return supplied;
  }
  const nested = ticket.defect_spec_candidate;
  if (_isPlainObject(nested)) {
    const nestedSha = String(nested.ticket_sha256 || "").toLowerCase();
    const nestedPayloadSha = String(nested.ticket_payload_sha256 || "").toLowerCase();
    if (nested.ticket_sha256_verified === true && _SHA256_RE.test(nestedSha) && _SHA256_RE.test(nestedPayloadSha)) {
      return nestedSha;
    }
  }
  return canonical_ticket_payload_sha256(ticket);
}

function _candidateFields(ticket: Record<string, any>, backendHint = ""): Record<string, any> {
  _candidateJsonBytes(ticket);
  const nested = ticket.defect_spec_candidate;
  let base: Record<string, any>;
  let md: Record<string, any>;
  if (_isPlainObject(nested)) {
    base = nested;
    md = nested;
  } else {
    base = ticket;
    md = _metadata(ticket);
  }
  const ticketId = _safeTicketId(base.ticket_id || ticket.ticket_id || "");
  const rawBackend = String(
    ticket._resolver_backend_hint || ticket.probe_backend || backendHint || base.backend || md.backend || ticket.backend || ""
  ).trim().toLowerCase();
  let backend = _ALLOWED_BACKENDS.has(rawBackend) ? rawBackend : "";
  if (ticketId.toUpperCase().startsWith("STORY-")) {
    backend = "zentao_story";
  }
  const title = String(base.title || ticket.title || "");
  const description = String(base.description || ticket.description || "");
  const metadata = _metadata(ticket);
  const rawDocType = String(base.doc_type || metadata.doc_type || "").trim().toLowerCase();
  const docType = _DOC_TYPE_RE.test(rawDocType) ? rawDocType : "";
  const product = String(base.product || metadata.product || "");
  const status = String(base.status || metadata.status || "");
  let affected = base.affected_versions;
  if (affected === undefined || affected === null) {
    affected = metadata.affected_versions;
  }
  let fixed = base.fixed_versions;
  if (fixed === undefined || fixed === null) {
    fixed = metadata.fixed_versions;
  }
  let semanticText: string;
  if (_isPlainObject(nested)) {
    semanticText = [title, description].join("\n");
  } else {
    const semanticParts = [title, description, ticket.fix_summary, ticket.page_content, ticket.steps_to_reproduce, metadata.module, metadata.product];
    semanticText = semanticParts.map((p) => String(p ?? "")).join("\n");
  }
  let declarationBlockReason = "";
  if (contains_prohibited_declaration(`${title}\n${description}`)) {
    declarationBlockReason = "description_contains_actual_or_logs";
  } else if (_containsCredentialMaterial(`${title}\n${description}`)) {
    declarationBlockReason = "declaration_contains_credential_material";
  } else if (!_ALLOWED_BACKENDS.has(backend) || !ticketId || !docType || !product.trim() || !status.trim()) {
    declarationBlockReason = "ticket_identity_metadata_incomplete";
  } else if (_declarationIsPlaceholderOnly(description)) {
    declarationBlockReason = "declaration_is_placeholder_only";
  } else if (!description.trim()) {
    declarationBlockReason = "description_declaration_unavailable";
  }
  return {
    backend,
    ticket_id: ticketId,
    ticket_number: _exactTicketNumber(ticketId),
    title,
    description,
    semantic_text: semanticText,
    doc_type: docType,
    product,
    status,
    affected_versions: _stringList(affected),
    fixed_versions: _stringList(fixed),
    ticket_sha256: _rawTicketSha256(ticket),
    declaration_block_reason: declarationBlockReason,
  };
}

function _declarationIsPlaceholderOnly(text: string): boolean {
  const compact = String(text ?? "").trim().replace(/\s+/g, "");
  if (!compact) {
    return false;
  }
  const tokens = compact.match(/\[[^\]\n]{1,12}\]/g) || [];
  if (!tokens.length || tokens.join("") !== compact) {
    return false;
  }
  return tokens.every((token) => _PLACEHOLDER_TOKEN_RE.test(token));
}

export function build_defect_spec_candidate(ticket: Record<string, any>, backendHint = ""): Record<string, any> {
  const fields = _candidateFields(ticket, backendHint);
  const wipe = _WIPE_DESCRIPTION_REASONS.has(fields.declaration_block_reason);
  const description = wipe ? "" : scrub_declaration_text(fields.description);
  return {
    backend: fields.backend,
    ticket_id: fields.ticket_id,
    doc_type: fields.doc_type,
    product: scrub_declaration_text(fields.product, 256),
    status: scrub_declaration_text(fields.status, 128),
    affected_versions: fields.affected_versions,
    fixed_versions: fields.fixed_versions,
    title: scrub_declaration_text(fields.title, 1000),
    description,
    claimable_declaration: !fields.declaration_block_reason,
    declaration_block_reason: fields.declaration_block_reason,
    ticket_sha256: fields.ticket_sha256,
    ticket_payload_sha256: canonical_ticket_payload_sha256(ticket),
    ticket_sha256_verified: ticket._ticket_file_sha256_verified === true,
  };
}

function _safeProjection(fields: Record<string, any>): Record<string, any> {
  let description = "";
  if (!fields.declaration_block_reason) {
    description = scrub_declaration_text(fields.description);
  }
  return {
    authority_group: "spec",
    backend: fields.backend ?? "",
    ticket_id: fields.ticket_id ?? "",
    doc_type: fields.doc_type ?? "",
    product: scrub_declaration_text(fields.product, 256),
    status: scrub_declaration_text(fields.status, 128),
    affected_versions: Array.from(fields.affected_versions ?? []),
    fixed_versions: Array.from(fields.fixed_versions ?? []),
    title: scrub_declaration_text(fields.title, 1000),
    description,
  };
}

function _invalidReceipt(opts: {
  ticket_number: string;
  source_sha256: string;
  source_content_sha256: string;
  source_context?: Record<string, any> | null;
  status: string;
  reason: string;
  candidates?: Array<Record<string, any>> | null;
  lookup?: Record<string, any> | null;
}): Record<string, any> {
  return {
    schema: RECEIPT_SCHEMA,
    status: opts.status,
    eligible: false,
    authority_group: "spec",
    reason: opts.reason,
    ticket_number: opts.ticket_number,
    source_sha256: opts.source_sha256,
    source_content_sha256: opts.source_content_sha256,
    source_context: opts.source_context ?? null,
    selection: null,
    ticket: null,
    projection: null,
    projection_sha256: null,
    candidates: opts.candidates ?? [],
    lookup: opts.lookup ?? {
      complete: false,
      errors: [{ backend: "", error_code: "lookup_unbound" }],
      backend_closure: {
        schema: "ist.defect-backend-closure",
        fixed_backends: [..._FIXED_BACKENDS],
        outcomes: [],
      },
      candidate_set_sha256: "",
    },
  };
}

function _lookupSummary(
  platformErrors: Array<Record<string, any>>,
  candidates: Array<Record<string, any>>,
  ticketNumber: string
): Record<string, any> {
  const hits: Record<string, Array<Record<string, any>>> = {};
  for (const b of _FIXED_BACKENDS) hits[b] = [];
  const closureErrors = new Set<string>();
  for (const raw of candidates) {
    if (!_isPlainObject(raw)) continue;
    let fields: Record<string, any>;
    try {
      fields = _candidateFields(raw);
    } catch {
      closureErrors.add(JSON.stringify(["", "candidate_unreadable"]));
      continue;
    }
    const probeBackend = String(raw._resolver_backend_hint || raw.probe_backend || fields.backend || "").trim().toLowerCase();
    if (!_FIXED_BACKENDS.includes(probeBackend as any)) {
      closureErrors.add(JSON.stringify([probeBackend, "unknown_backend"]));
      continue;
    }
    if (fields.ticket_number !== ticketNumber) {
      closureErrors.add(JSON.stringify([probeBackend, "ticket_identity_mismatch"]));
      continue;
    }
    const nested = _isPlainObject(raw.defect_spec_candidate) ? raw.defect_spec_candidate : {};
    const verified = raw._ticket_file_sha256_verified === true || nested.ticket_sha256_verified === true;
    const payloadSha = String(raw._ticket_payload_sha256 || nested.ticket_payload_sha256 || canonical_ticket_payload_sha256(raw)).trim().toLowerCase();
    const ticketSha = String(fields.ticket_sha256 || "").trim().toLowerCase();
    hits[probeBackend].push({
      backend: probeBackend,
      status: "hit",
      ticket_id: String(fields.ticket_id || ""),
      ticket_file_sha256: verified ? ticketSha : null,
      ticket_payload_sha256: payloadSha,
      ticket_sha256_verified: verified,
    });
  }
  const misses: Record<string, string[]> = {};
  for (const b of _FIXED_BACKENDS) misses[b] = [];
  for (const item of platformErrors) {
    if (!_isPlainObject(item)) continue;
    const backend = String(item.probe_backend || "").trim().toLowerCase();
    const code = String(item.error_code || "unknown").trim().toLowerCase();
    if (!_FIXED_BACKENDS.includes(backend as any)) {
      closureErrors.add(JSON.stringify([backend, "unknown_backend"]));
      continue;
    }
    misses[backend].push(code);
  }
  const outcomes: Array<Record<string, any>> = [];
  for (const backend of _FIXED_BACKENDS) {
    const backendHits = hits[backend];
    const backendMisses = misses[backend];
    if (backendHits.length === 1 && backendMisses.length === 0) {
      outcomes.push(backendHits[0]);
      continue;
    }
    if (backendHits.length === 0 && backendMisses.length === 1 && backendMisses[0] === "not_found") {
      outcomes.push({ backend, status: "not_found" });
      continue;
    }
    let code: string;
    if (backendHits.length > 1) {
      code = "duplicate_backend_hit";
    } else if (backendHits.length && backendMisses.length) {
      code = "conflicting_backend_outcome";
    } else if (backendMisses.length > 1) {
      code = "duplicate_backend_outcome";
    } else if (backendMisses.length) {
      code = backendMisses[0];
    } else {
      code = "backend_outcome_missing";
    }
    closureErrors.add(JSON.stringify([backend, code]));
    outcomes.push({ backend, status: "unavailable", error_code: code });
  }
  const closure = { schema: "ist.defect-backend-closure", fixed_backends: [..._FIXED_BACKENDS], outcomes };
  const errors = Array.from(closureErrors).map((s) => JSON.parse(s) as [string, string]).sort((a, b) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : a[1] < b[1] ? -1 : a[1] > b[1] ? 1 : 0));
  return {
    complete: errors.length === 0,
    errors: errors.map(([backend, code]) => ({ backend, error_code: code })),
    backend_closure: closure,
    candidate_set_sha256: _sha256Json(closure),
  };
}

export function build_defect_backend_lookup(opts: {
  ticket_id: string;
  candidates: Array<Record<string, any>>;
  platform_errors: Array<Record<string, any>>;
}): Record<string, any> {
  return _lookupSummary(opts.platform_errors, opts.candidates, _exactTicketNumber(opts.ticket_id) || "");
}

export function defect_backend_lookup_is_sealable(lookup: any, ticket_id = ""): boolean {
  if (
    !_isPlainObject(lookup) ||
    Object.keys(lookup).sort().join(",") !== "backend_closure,candidate_set_sha256,complete,errors"
  ) {
    return false;
  }
  const closure = lookup.backend_closure;
  if (
    lookup.complete !== true ||
    JSON.stringify(lookup.errors) !== "[]" ||
    !_isPlainObject(closure) ||
    Object.keys(closure).sort().join(",") !== "fixed_backends,outcomes,schema" ||
    !accepts_schema(closure.schema, "ist.defect-backend-closure") ||
    JSON.stringify(closure.fixed_backends) !== JSON.stringify([..._FIXED_BACKENDS]) ||
    String(lookup.candidate_set_sha256 || "") !== _sha256Json({ ...closure })
  ) {
    return false;
  }
  const expectedTicketNumber = String(ticket_id || "").trim() ? _exactTicketNumber(ticket_id) : null;
  if (String(ticket_id || "").trim() && expectedTicketNumber === null) {
    return false;
  }
  const outcomes = closure.outcomes;
  if (!Array.isArray(outcomes) || outcomes.length !== _FIXED_BACKENDS.length) {
    return false;
  }
  for (let i = 0; i < _FIXED_BACKENDS.length; i++) {
    const backend = _FIXED_BACKENDS[i];
    const outcome = outcomes[i];
    if (!_isPlainObject(outcome) || outcome.backend !== backend) {
      return false;
    }
    if (outcome.status === "not_found") {
      if (Object.keys(outcome).sort().join(",") !== "backend,status") {
        return false;
      }
      continue;
    }
    if (
      outcome.status !== "hit" ||
      Object.keys(outcome).sort().join(",") !== "backend,status,ticket_file_sha256,ticket_id,ticket_payload_sha256,ticket_sha256_verified"
    ) {
      return false;
    }
    if (
      outcome.ticket_sha256_verified !== true ||
      _exactTicketNumber(outcome.ticket_id) === null ||
      (expectedTicketNumber !== null && _exactTicketNumber(outcome.ticket_id) !== expectedTicketNumber) ||
      !_SHA256_RE.test(String(outcome.ticket_file_sha256 || "")) ||
      !_SHA256_RE.test(String(outcome.ticket_payload_sha256 || ""))
    ) {
      return false;
    }
  }
  return true;
}

export function resolve_defect_spec(opts: {
  ticket_id: string;
  source_title: string;
  source_text: string;
  source_sha256: string;
  candidates: Array<Record<string, any>>;
  platform_errors?: Array<Record<string, any>>;
  min_score?: number;
  min_margin?: number;
}): Record<string, any> {
  const {
    ticket_id,
    source_title,
    source_text,
    source_sha256,
    candidates,
    min_score = 0.08,
    min_margin = 0.04,
  } = opts;
  const platform_errors = opts.platform_errors ?? [];
  const ticketNumber = _exactTicketNumber(ticket_id) || "";
  const sourceSha = String(source_sha256 || "").trim().toLowerCase();
  const sourceSemanticChars = String(source_title || "").length + String(source_text || "").length;
  let sourceContentSha: string;
  if (sourceSemanticChars <= _MAX_SOURCE_SEMANTIC_CHARS) {
    sourceContentSha = _sourceContextSha256(String(source_title || ""), String(source_text || ""));
  } else {
    sourceContentSha = _sha256Json({ semantic_budget_exceeded: true, chars: sourceSemanticChars });
  }
  let sourceContext: Record<string, any> | null;
  let sourceContextError: string;
  if (_SHA256_RE.test(sourceSha) && (String(source_title || "").trim() || String(source_text || "").trim()) && sourceSemanticChars <= _MAX_SOURCE_SEMANTIC_CHARS) {
    [sourceContext, sourceContextError] = _build_source_context_binding(String(source_title || ""), String(source_text || ""), sourceSha);
  } else {
    sourceContext = null;
    sourceContextError = "";
  }
  const lookup = _lookupSummary(platform_errors, candidates, ticketNumber);
  if (!ticketNumber) {
    return _invalidReceipt({ ticket_number: "", source_sha256: sourceSha, source_content_sha256: sourceContentSha, status: "invalid_source", reason: "ticket_id_not_exact", lookup });
  }
  if (!_SHA256_RE.test(sourceSha)) {
    return _invalidReceipt({ ticket_number: ticketNumber, source_sha256: sourceSha, source_content_sha256: sourceContentSha, status: "invalid_source", reason: "sealed_source_sha256_required", lookup });
  }
  if (!String(source_title || "").trim() && !String(source_text || "").trim()) {
    return _invalidReceipt({ ticket_number: ticketNumber, source_sha256: sourceSha, source_content_sha256: sourceContentSha, status: "invalid_source", reason: "source_context_unavailable", lookup });
  }
  if (sourceSemanticChars > _MAX_SOURCE_SEMANTIC_CHARS) {
    return _invalidReceipt({ ticket_number: ticketNumber, source_sha256: sourceSha, source_content_sha256: sourceContentSha, status: "invalid_source", reason: "source_semantic_budget_exceeded", lookup });
  }
  if (sourceContextError) {
    return _invalidReceipt({ ticket_number: ticketNumber, source_sha256: sourceSha, source_content_sha256: sourceContentSha, source_context: null, status: "invalid_source", reason: sourceContextError, lookup });
  }
  if (candidates.length > _MAX_DEFECT_CANDIDATES) {
    return _invalidReceipt({ ticket_number: ticketNumber, source_sha256: sourceSha, source_content_sha256: sourceContentSha, status: "unavailable", reason: "candidate_count_budget_exceeded", lookup });
  }
  let totalCandidateChars = 0;
  for (const raw of candidates) {
    if (!_isPlainObject(raw)) continue;
    let candidatePayload: Buffer;
    try {
      candidatePayload = _candidateJsonBytes(raw);
    } catch {
      return _invalidReceipt({ ticket_number: ticketNumber, source_sha256: sourceSha, source_content_sha256: sourceContentSha, status: "unavailable", reason: "candidate_semantic_budget_exceeded", lookup });
    }
    const candidateChars = _candidateSemanticSize(raw, candidatePayload);
    totalCandidateChars += candidateChars;
    if (candidateChars > _MAX_CANDIDATE_SEMANTIC_CHARS || totalCandidateChars > _MAX_TOTAL_CANDIDATE_SEMANTIC_CHARS) {
      return _invalidReceipt({ ticket_number: ticketNumber, source_sha256: sourceSha, source_content_sha256: sourceContentSha, status: "unavailable", reason: "candidate_semantic_budget_exceeded", lookup });
    }
  }
  if (!lookup.complete) {
    return _invalidReceipt({ ticket_number: ticketNumber, source_sha256: sourceSha, source_content_sha256: sourceContentSha, status: "unavailable", reason: "backend_lookup_incomplete", lookup });
  }
  const sourceTitleTokens = _semanticTokens(source_title);
  const sourceFullTokens = _semanticTokens(`${source_title}\n${source_text}`);
  const rankedInternal: Array<Record<string, any>> = [];
  const seen = new Set<string>();
  for (const raw of candidates) {
    if (!_isPlainObject(raw)) continue;
    const fields = _candidateFields(raw);
    if (fields.ticket_number !== ticketNumber) continue;
    const identity = `${String(fields.backend)}${String(fields.ticket_id).toUpperCase()}${String(fields.ticket_sha256)}`;
    if (seen.has(identity)) continue;
    seen.add(identity);
    const titleScore = _coverage(sourceTitleTokens, _semanticTokens(String(fields.title)));
    const semanticScore = _dice(sourceFullTokens, _semanticTokens(String(fields.semantic_text)));
    let score: number;
    if (sourceTitleTokens.size) {
      score = 0.75 * titleScore + 0.25 * semanticScore;
    } else {
      score = semanticScore;
    }
    rankedInternal.push({
      fields,
      score: Math.round(score * 1e6) / 1e6,
      title_score: Math.round(titleScore * 1e6) / 1e6,
      semantic_score: Math.round(semanticScore * 1e6) / 1e6,
    });
  }
  rankedInternal.sort((a, b) => {
    if (b.score !== a.score) return b.score - a.score;
    if (b.title_score !== a.title_score) return b.title_score - a.title_score;
    if (b.semantic_score !== a.semantic_score) return b.semantic_score - a.semantic_score;
    const ab = String(a.fields.backend), bb = String(b.fields.backend);
    if (ab !== bb) return ab < bb ? -1 : 1;
    const at = String(a.fields.ticket_id), bt = String(b.fields.ticket_id);
    if (at !== bt) return at < bt ? -1 : 1;
    const as = String(a.fields.ticket_sha256), bs = String(b.fields.ticket_sha256);
    return as < bs ? -1 : as > bs ? 1 : 0;
  });
  const candidatesPublic = rankedInternal.map((row) => ({
    backend: row.fields.backend,
    ticket_id: row.fields.ticket_id,
    ticket_sha256: row.fields.ticket_sha256,
    title: scrub_declaration_text(row.fields.title, 1000),
    claimable_declaration: !row.fields.declaration_block_reason,
    declaration_block_reason: row.fields.declaration_block_reason,
    score: row.score,
    title_score: row.title_score,
    semantic_score: row.semantic_score,
  }));
  if (!rankedInternal.length) {
    return _invalidReceipt({ ticket_number: ticketNumber, source_sha256: sourceSha, source_content_sha256: sourceContentSha, status: "missing", reason: "exact_ticket_id_not_found", candidates: candidatesPublic, lookup });
  }
  const top = rankedInternal[0];
  const runnerScore = rankedInternal.length > 1 ? rankedInternal[1].score : 0.0;
  const margin = Math.round((top.score - runnerScore) * 1e6) / 1e6;
  if (top.score < min_score || (rankedInternal.length > 1 && margin < min_margin)) {
    return _invalidReceipt({ ticket_number: ticketNumber, source_sha256: sourceSha, source_content_sha256: sourceContentSha, status: "ambiguous", reason: "semantic_score_or_margin_below_threshold", candidates: candidatesPublic, lookup });
  }
  const fields = top.fields;
  const projection = _safeProjection(fields);
  let selectionReason = "unique_full_text_semantic_match";
  if (top.title_score > 0 && (rankedInternal.length === 1 || top.title_score > rankedInternal[1].title_score)) {
    selectionReason = "unique_source_title_match";
  }
  const selection = {
    reason: selectionReason,
    score: top.score,
    title_score: top.title_score,
    semantic_score: top.semantic_score,
    runner_up_score: runnerScore,
    margin,
  };
  const ticketBinding = {
    backend: fields.backend,
    ticket_id: fields.ticket_id,
    doc_type: fields.doc_type,
    product: scrub_declaration_text(fields.product, 256),
    status: scrub_declaration_text(fields.status, 128),
    affected_versions: fields.affected_versions,
    fixed_versions: fields.fixed_versions,
    ticket_sha256: fields.ticket_sha256,
  };
  const blockReason = String(fields.declaration_block_reason || "");
  return {
    schema: RECEIPT_SCHEMA,
    status: blockReason ? "candidate_only" : "resolved",
    eligible: !blockReason,
    authority_group: "spec",
    reason: blockReason ? `selected_ticket_${blockReason}` : selectionReason,
    ticket_number: ticketNumber,
    source_sha256: sourceSha,
    source_content_sha256: sourceContentSha,
    source_context: sourceContext,
    selection,
    ticket: ticketBinding,
    projection,
    projection_sha256: _sha256Json(projection),
    candidates: candidatesPublic,
    lookup,
  };
}

export function resolve_defect_spec_from_tool_result(opts: {
  tool_result: Record<string, any>;
  ticket_id: string;
  source_title: string;
  source_text: string;
  source_sha256: string;
}): Record<string, any> {
  const { tool_result, ticket_id, source_title, source_text, source_sha256 } = opts;
  const rows = tool_result.results;
  const candidates = Array.isArray(rows) ? rows : [];
  return resolve_defect_spec({
    ticket_id,
    source_title,
    source_text,
    source_sha256,
    candidates: candidates.filter((row) => _isPlainObject(row)),
    platform_errors: (Array.isArray(tool_result.platform_errors) ? tool_result.platform_errors : []).filter((row: any) => _isPlainObject(row)),
  });
}

export function validate_defect_spec_receipt(
  receipt: Record<string, any>,
  opts: {
    ticket_id: string;
    source_title: string;
    source_text: string;
    source_sha256: string;
    candidates: Array<Record<string, any>>;
    platform_errors?: Array<Record<string, any>>;
  }
): Record<string, any> {
  const expected = resolve_defect_spec({
    ticket_id: opts.ticket_id,
    source_title: opts.source_title,
    source_text: opts.source_text,
    source_sha256: opts.source_sha256,
    candidates: opts.candidates,
    platform_errors: opts.platform_errors ?? [],
  });
  const valid = _canonicalJsonString({ ...receipt }) === _canonicalJsonString(expected);
  return {
    schema: VALIDATION_SCHEMA,
    valid,
    reason: valid ? "receipt_current" : "source_or_ticket_drift",
    expected_receipt_sha256: _sha256Json(expected),
    provided_receipt_sha256: _sha256Json({ ...receipt }),
  };
}
