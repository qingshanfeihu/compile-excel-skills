import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { KNOWLEDGE_FRAMEWORK_MIRROR } from "../knowledge_paths";

export class MirrorCredentialLiteralError extends Error {}

const _CREDENTIAL_SLOT_SEGMENTS = new Set(["password", "passwd", "pwd", "secret", "token", "passphrase"]);

function _isCredentialSlot(name: string | null | undefined): boolean {
  if (!name) {
    return false;
  }
  const segments = name.toLowerCase().split(/[_\W]+/).filter(Boolean);
  return segments.some((s) => _CREDENTIAL_SLOT_SEGMENTS.has(s));
}

function _isMapping(v: any): v is Record<string, any> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

// Minimal Python-source credential literal scanner: walks assignment-like lines.
function _scanSource(source: string, values: Set<string>): void {
  const assignRe = /(?:^|\n)\s*(?:[\w.[\]'"]+\s*[,=:]?\s*)*([A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)?|\[[^\]]*\]|\{[^}]*\})\s*[:=]\s*("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/g;
  let m: RegExpExecArray | null;
  while ((m = assignRe.exec(source)) !== null) {
    const target = m[1];
    const litRaw = m[2];
    const name = target.replace(/^.*[.[\]]\s*/, "").replace(/["']/g, "");
    let literal: string;
    try {
      literal = JSON.parse(litRaw.startsWith("'") ? '"' + litRaw.slice(1, -1).replace(/\\'/g, "'").replace(/"/g, '\\"') + '"' : litRaw);
    } catch {
      literal = litRaw.slice(1, -1);
    }
    if (literal && _isCredentialSlot(name)) {
      values.add(literal);
    }
  }
  // dict entries  "password": "value"
  const dictRe = /["']([^"']*(?:password|passwd|pwd|secret|token|passphrase)[^"']*)["']\s*:\s*("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/gi;
  while ((m = dictRe.exec(source)) !== null) {
    const key = m[1];
    if (!_isCredentialSlot(key)) continue;
    const litRaw = m[2];
    let literal: string;
    try {
      literal = JSON.parse(litRaw.startsWith("'") ? '"' + litRaw.slice(1, -1).replace(/\\'/g, "'").replace(/"/g, '\\"') + '"' : litRaw);
    } catch {
      literal = litRaw.slice(1, -1);
    }
    if (literal) values.add(literal);
  }
  // keyword call args password="..."
  const kwRe = /\b(password|passwd|pwd|secret|token|passphrase)\s*=\s*("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/gi;
  while ((m = kwRe.exec(source)) !== null) {
    const litRaw = m[2];
    let literal: string;
    try {
      literal = JSON.parse(litRaw.startsWith("'") ? '"' + litRaw.slice(1, -1).replace(/\\'/g, "'").replace(/"/g, '\\"') + '"' : litRaw);
    } catch {
      literal = litRaw.slice(1, -1);
    }
    if (literal) values.add(literal);
  }
  // os.environ.get("NAME", "default") / os.getenv("NAME", "default")
  const envRe = /os\.(?:environ\.get|getenv)\(\s*("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')\s*,\s*("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/g;
  while ((m = envRe.exec(source)) !== null) {
    const nameRaw = m[1].slice(1, -1);
    if (!_isCredentialSlot(nameRaw)) continue;
    const litRaw = m[2];
    let literal: string;
    try {
      literal = JSON.parse(litRaw.startsWith("'") ? '"' + litRaw.slice(1, -1).replace(/\\'/g, "'").replace(/"/g, '\\"') + '"' : litRaw);
    } catch {
      literal = litRaw.slice(1, -1);
    }
    if (literal) values.add(literal);
  }
}

const _CACHE = new Map<string, Set<string>>();

export function clear_credential_literal_cache(): void {
  _CACHE.clear();
}

function _loadPythonSources(root: string, overlays: Record<string, Buffer | Uint8Array>): Array<[string, Buffer]> {
  const paths: string[] = [];
  const walk = (dir: string): void => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) walk(full);
      else if (entry.name.endsWith(".py")) paths.push(full);
    }
  };
  walk(root);
  paths.sort();
  if (!paths.length) {
    throw new MirrorCredentialLiteralError("framework mirror contains no Python sources");
  }
  const pythonRelatives = new Set(paths.map((p) => path.relative(root, p).split(path.sep).join("/")));
  const unknown = Object.keys(overlays).filter((k) => !pythonRelatives.has(k));
  if (unknown.length) {
    throw new MirrorCredentialLiteralError(`credential overlay contains unknown Python sources (count=${unknown.length})`);
  }
  for (const value of Object.values(overlays)) {
    if (!Buffer.isBuffer(value) && !(value instanceof Uint8Array)) {
      throw new MirrorCredentialLiteralError("credential overlays must be sealed bytes");
    }
  }
  const entries: Array<[string, Buffer]> = [];
  for (const p of paths) {
    const relative = path.relative(root, p).split(path.sep).join("/");
    let raw: Buffer;
    try {
      raw = relative in overlays ? Buffer.from(overlays[relative]) : fs.readFileSync(p);
    } catch (exc: any) {
      throw new MirrorCredentialLiteralError(`cannot read mirror source: ${relative} (${exc?.constructor?.name || "Error"})`);
    }
    entries.push([relative, raw]);
  }
  return entries;
}

function _pythonSourceIdentity(entries: Array<[string, Buffer]>): string {
  const digest = crypto.createHash("sha256");
  for (const [relative, raw] of entries) {
    const name = Buffer.from(relative, "utf8");
    const lenBuf = Buffer.alloc(8);
    lenBuf.writeBigUInt64BE(BigInt(name.length));
    digest.update(lenBuf);
    digest.update(name);
    const rawLenBuf = Buffer.alloc(8);
    rawLenBuf.writeBigUInt64BE(BigInt(raw.length));
    digest.update(rawLenBuf);
    digest.update(raw);
  }
  return digest.digest("hex");
}

function _parseCredentialLiterals(entries: Array<[string, Buffer]>): Set<string> {
  const values = new Set<string>();
  for (const [relative, raw] of entries) {
    let source: string;
    try {
      source = raw.toString("utf8");
    } catch (exc: any) {
      throw new MirrorCredentialLiteralError(`cannot read mirror source: ${relative} (${exc?.constructor?.name || "Error"})`);
    }
    _scanSource(source, values);
  }
  return values;
}

function _extractCredentialLiterals(root: string, overlays: Record<string, Buffer | Uint8Array>): Set<string> {
  return _parseCredentialLiterals(_loadPythonSources(root, overlays));
}

export function mirror_credential_literals_with_overlays(
  source_overlays: Record<string, Buffer | Uint8Array> | null = null,
  mirror_root: string | null = null
): Set<string> {
  const root = path.resolve(mirror_root || KNOWLEDGE_FRAMEWORK_MIRROR);
  if (!fs.existsSync(root) || !fs.statSync(root).isDirectory()) {
    throw new MirrorCredentialLiteralError("framework mirror directory is unavailable");
  }
  const overlays = { ...(source_overlays || {}) };
  if (Object.keys(overlays).length) {
    return _extractCredentialLiterals(root, overlays);
  }
  const entries = _loadPythonSources(root, overlays);
  const key = root + "" + _pythonSourceIdentity(entries);
  const hit = _CACHE.get(key);
  if (hit !== undefined) {
    return hit;
  }
  const values = _parseCredentialLiterals(entries);
  _CACHE.set(key, values);
  return values;
}

export function mirror_credential_literals(mirror_root: string | null = null): Set<string> {
  return mirror_credential_literals_with_overlays({}, mirror_root);
}

export function matching_credential_literal_count(text: string, values: Set<string> | ReadonlySet<string>): number {
  const folded = (text || "").toLowerCase();
  let count = 0;
  for (const value of values) {
    if (value && folded.includes(value.toLowerCase())) count++;
  }
  return count;
}

const _CREDENTIAL_HEAD_NOUNS = new Set([
  "password", "passwords", "passwd", "passwds", "pwd", "pwds", "passphrase", "passphrases",
  "secret", "secrets", "key", "keys", "credential", "credentials", "token", "tokens",
  "community", "communities", "pin", "pins",
]);
const _TRANSPARENT_HEAD_NOUNS = new Set(["value", "values", "string", "strings", "literal", "literals", "content", "contents", "text", "data"]);
const _HEAD_TAIL_MODIFIER_RE = /\b(?:for|of|in|on|to|with|from|by|used|use|which|that|who|whose|when|where|ranging|range|enclosed|required|optional|containing|contains|specified|generated|imported|exported|associated|about|as|per|via)\b.*$/i;
const _COORDINATOR_SPLIT_RE = /\b(?:and|or)\b/i;
const _HEAD_WORD_RE = /[A-Za-z][A-Za-z0-9_-]*/g;
const _HEAD_SUBWORD_SPLIT_RE = /[-_]+/;
const _XML_ENTITIES: Array<[string, string]> = [["&quot;", '"'], ["&apos;", "'"], ["&lt;", "<"], ["&gt;", ">"], ["&amp;", "&"]];
const _STRUCTURAL_NON_CREDENTIAL_TYPES = new Set(["U16", "U32", "IPADDR", "DOTTEDIP", "IPMASK"]);
const _PLACEHOLDER_DEFAULT_LITERALS = new Set(["null", "none", "nil", "n/a", "na"]);

function _unescapeXmlText(value: string | null | undefined): string {
  let text = String(value || "");
  for (const [entity, char] of _XML_ENTITIES) {
    text = text.split(entity).join(char);
  }
  return text;
}

function _branchHead(branch: string): string {
  let segment = branch.replace(_HEAD_TAIL_MODIFIER_RE, "");
  segment = segment.replace(/'s/g, " ").replace(/’s/g, " ");
  const words: string[] = [];
  for (const word of segment.match(_HEAD_WORD_RE) || []) {
    for (const subword of word.split(_HEAD_SUBWORD_SPLIT_RE)) {
      if (subword) words.push(subword.toLowerCase());
    }
  }
  while (words.length && _TRANSPARENT_HEAD_NOUNS.has(words[words.length - 1])) {
    words.pop();
  }
  return words.length ? words[words.length - 1] : "";
}

export function credential_declaration_heads(help_string: string | null | undefined): string[] {
  let text = _unescapeXmlText(help_string);
  for (const [token, char] of [["\\n", "\n"], ["\\t", "\t"], ["\\r", "\n"]] as Array<[string, string]>) {
    text = text.split(token).join(char);
  }
  const segment = text.split(/[.;:,\n\r()[\]]/, 2)[0];
  const heads = segment.split(_COORDINATOR_SPLIT_RE).map(_branchHead);
  return heads.filter(Boolean);
}

export function credential_declaration_head(help_string: string | null | undefined): string {
  const heads = credential_declaration_heads(help_string);
  return heads.length ? heads[0] : "";
}

export function is_credential_argument(opts: { name?: string | null; arg_type?: string | null; help_string?: string | null }): boolean {
  if (_STRUCTURAL_NON_CREDENTIAL_TYPES.has(String(opts.arg_type || "").trim().toUpperCase())) {
    return false;
  }
  if (_isCredentialSlot(opts.name)) {
    return true;
  }
  return credential_declaration_heads(opts.help_string).some((head) => _CREDENTIAL_HEAD_NOUNS.has(head));
}

export function is_placeholder_default_literal(value: string | null | undefined): boolean {
  const text = _unescapeXmlText(value).trim().replace(/^["']+|["']+$/g, "").trim();
  if (!text) {
    return true;
  }
  return _PLACEHOLDER_DEFAULT_LITERALS.has(text.toLowerCase());
}
