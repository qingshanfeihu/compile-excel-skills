import os from "node:os";
import path from "node:path";

const _SENSITIVE_KEY_RE = /(?:password|passwd|pwd|secret|token|authorization|cookie|api[_-]?key|apikey|access[_-]?key|private[_-]?key|credential|community|jumphost[_-]?pass|(?<![a-z])pin(?![a-z])|密码|口令|令牌|密钥|凭据)/i;
const _SHA256_HEX_RE = /^[0-9A-Fa-f]{64}$/;
const _AUTHORIZATION_SCHEME_RE = /(["']?Authorization["']?(?:\s*[:=]\s*|\s+)(["']?))(?:Bearer|Basic)\s+[A-Za-z0-9._~+/=-]+\2/gi;
const _QUOTED_SECRET_RE = /(["']?(?:OPENAI_API_KEY|DEEPSEEK_API_KEY|MINERU_TOKEN|IST_JUMPHOST_PASS|JUMPHOST_PASS|APV_PASSWORD|Authorization|password|passwd|pwd|secret|token|api[\s_-]?key|access[\s_-]?token|auth[\s_-]?token|credential|community|密码|口令|令牌|密钥|凭据)["']?\s*(?::|=)\s*)(["'])(.*?)\2/gi;
const _UNQUOTED_PHRASE_SECRET_RE = /(\b(?:password|passwd|pwd|secret|token|api[\s_-]?key|access[\s_-]?token|auth[\s_-]?token|credential|community)\s*(?::|=)\s*)(?!\s*(?:["']|\*{4}))(?=[^,\r\n;}\]]*\s)[^,\r\n;}\]]+?(?=\s+\b(?:password|passwd|pwd|secret|token|api[\s_-]?key|access[\s_-]?token|auth[\s_-]?token|credential|community)\b\s*(?::|=)|[,;\r\n}\]]|$)/gi;
const _NAMED_SECRET_RE = /(["']?(?:OPENAI_API_KEY|DEEPSEEK_API_KEY|MINERU_TOKEN|IST_JUMPHOST_PASS|JUMPHOST_PASS|APV_PASSWORD|Authorization|Bearer|password|passwd|pwd|secret|token|api[\s_-]?key|access[\s_-]?token|auth[\s_-]?token|credential|community)["']?\s*(?::|=)\s*)(["']?)(Bearer\s+[^,\s}\]]+|[^,\s}\]"']+)\2/gi;
const _SPACE_SECRET_RE = /\b(Authorization|password|passwd|pwd|secret|token|api[\s_-]?key|access[\s_-]?token|auth[\s_-]?token|credential|community)([^\S\r\n]+)(Bearer\s+\S+|\S+)/gi;
const _BEARER_RE = /\bBearer\s+[A-Za-z0-9._~+/=-]+/gi;
const _SSHPASS_RE = /\bsshpass\s+(?:-[A-Za-z]\s+\S+\s+)*?-p\s*(\S+)/g;
const _CURL_USER_RE = /\bcurl\b([^\r\n&|;]{0,200}?)(?<=\s)(--user[=\s]|-u\s*)(["']?)([^:\s"']{0,120}:)([^\s"']+)/gi;
const _SUDO_STDIN_RE = /\becho\s+(["'])([^\r\n]{0,200}?)\1(\s*\|\s*(?:\/usr\/bin\/)?sudo\b[^\r\n]{0,40}?-S\b)/gi;
const _SENDLINE_RE = /\bsendline\s*\(\s*(["'])([^\r\n]{0,200}?)\1(\s*\))/gi;
const _URL_USERINFO_RE = /([A-Za-z][A-Za-z0-9+.\-]*:\/\/[^\s/:@]{1,120}:)([^\s@/]{1,200})(@)/g;
const _SUDO_PROMPT_RE = /(\[sudo\]\s*(?:password|passwd|口令|密码)[^\r\n:：]{0,40}[:：]\s*)([^\r\n]+)/gi;
const _DEVICE_INTERNAL_PATH_RE = /(?<![\w.-])\/home\/test(?:\/[^\s`'\"<>|]*)?/g;
const _UNIX_INTERNAL_PATH_RE = /(?<![\w.-])\/(?:Users|private|var|tmp|opt|etc|home|root)(?:\/[^\s`'"<>|:;,)\]}]+)+/g;
const _WINDOWS_INTERNAL_PATH_RE = /\b[A-Z]:\\(?:Users|ProgramData|Windows|Temp)(?:\\[^\s`'"<>|:;,)\]}]+)+/gi;

const _CREDENTIAL_ENV_SUFFIXES = ["_KEY", "_TOKEN", "_PASS", "_PASSWORD", "_SECRET"];
const _NON_CREDENTIAL_ENV_SUFFIXES = ["_HOST_KEY", "_FIELD", "_TOKENS"];

function endsWithAny(name: string, suffixes: string[]): boolean {
  return suffixes.some((s) => name.endsWith(s));
}

function _is_credential_env_name(name: string): boolean {
  if (endsWithAny(name, _NON_CREDENTIAL_ENV_SUFFIXES)) {
    return false;
  }
  return _SENSITIVE_KEY_RE.test(name) || endsWithAny(name, _CREDENTIAL_ENV_SUFFIXES);
}

let _SENSITIVE_KEYS_CACHE_KEYS: ReadonlySet<string> | null = null;
let _SENSITIVE_KEYS_CACHE: string[] = [];

function _sensitive_env_keys(): string[] {
  const keys = new Set(Object.keys(process.env));
  if (_SENSITIVE_KEYS_CACHE_KEYS !== null) {
    const same =
      keys.size === _SENSITIVE_KEYS_CACHE_KEYS.size &&
      [...keys].every((k) => _SENSITIVE_KEYS_CACHE_KEYS!.has(k));
    if (same) {
      return _SENSITIVE_KEYS_CACHE;
    }
  }
  const found = [...keys].filter(_is_credential_env_name).sort();
  _SENSITIVE_KEYS_CACHE_KEYS = keys;
  _SENSITIVE_KEYS_CACHE = found;
  return found;
}

const _PERCENT_ESCAPE_RE = /%[0-9A-F]{2}/g;

function quotePython(candidate: string, safe: string): string | null {
  const buffer = Buffer.from(candidate, "utf8");
  const s = buffer.toString("utf8");
  if (s.includes("")) {
    return null;
  }
  try {
    let out = encodeURIComponent(candidate);
    for (const ch of "!()*") {
      if (safe.includes(ch)) {
        out = out.replace(
          new RegExp("%" + ch.charCodeAt(0).toString(16).toUpperCase().padStart(2, "0"), "g"),
          ch
        );
      }
    }
    return out;
  } catch {
    return null;
  }
}

function _encoded_twins(candidate: string): string[] {
  const twins: string[] = [];
  for (const safe of ["", "!'()*"]) {
    const encoded = quotePython(candidate, safe);
    if (encoded === null) {
      continue;
    }
    if (encoded === candidate) {
      continue;
    }
    twins.push(encoded);
    const lowered = encoded.replace(_PERCENT_ESCAPE_RE, (m) => m.toLowerCase());
    if (lowered !== encoded) {
      twins.push(lowered);
    }
  }
  return twins;
}

let _SECRET_VALUES_CACHE_KEYS: string[] | null = null;
let _SECRET_VALUES_CACHE_RAW: string[] | null = null;
let _SECRET_VALUES_CACHE: string[] = [];

function arraysEqual(a: string[], b: string[]): boolean {
  return a.length === b.length && a.every((v, i) => v === b[i]);
}

function _loaded_secret_values(): string[] {
  const keys = _sensitive_env_keys();
  const raw = keys.map((key) => String(process.env[key] ?? ""));
  if (
    _SECRET_VALUES_CACHE_KEYS !== null &&
    _SECRET_VALUES_CACHE_RAW !== null &&
    arraysEqual(keys, _SECRET_VALUES_CACHE_KEYS) &&
    arraysEqual(raw, _SECRET_VALUES_CACHE_RAW)
  ) {
    return _SECRET_VALUES_CACHE;
  }
  const values = new Set<string>();
  for (const value of raw) {
    for (const candidate of [value, value.trim()]) {
      if (candidate.length < 8) {
        continue;
      }
      values.add(candidate);
      for (const twin of _encoded_twins(candidate)) {
        values.add(twin);
      }
    }
  }
  const result = [...values].sort((a, b) => b.length - a.length);
  _SECRET_VALUES_CACHE_KEYS = keys;
  _SECRET_VALUES_CACHE_RAW = raw;
  _SECRET_VALUES_CACHE = result;
  return result;
}

const _SK_PREFIX_TOKEN_RE = /\bsk-[A-Za-z0-9_-]{16,}/gi;
const _URL_QUERY_SECRET_RE = /([?&](?:api[_-]?key|apikey|access[_-]?token|auth[_-]?token|key|token)=)([^&\s"'<>]+)/gi;
const _DISCLOSURE_NEAR_TOKEN_RE = /(\b(?:api[\s_-]?key|apikey|access[\s_-]?token|auth[\s_-]?token|token|secret|password|passwd|credential)\b|令牌|密钥|秘钥|口令|密码|凭据)([^\r\n]{0,40}?[\s:=,"'（(])((?=[A-Za-z0-9_-]*[A-Za-z])(?=[A-Za-z0-9_-]*\d)[A-Za-z0-9_-]{16,})/gi;

export function scrub_disclosure_text(text: unknown, opts: { scrub_paths?: boolean } = {}): string {
  const scrubPaths = opts.scrub_paths ?? true;
  let out = scrub_text(text, { scrub_paths: scrubPaths });
  if (!out) {
    return "";
  }
  out = out.replace(_URL_QUERY_SECRET_RE, (_m, prefix) => `${prefix}****`);
  out = out.replace(_SK_PREFIX_TOKEN_RE, "****");
  out = out.replace(_DISCLOSURE_NEAR_TOKEN_RE, (_m, prefix, gap) => `${prefix}${gap}****`);
  return out;
}

let _PROJECT_ROOT: string | null = null;
let _HOME_CACHE: [string, string] = ["\x00", ""];

function _replaceable_root(p: string): string {
  const parsed = path.parse(p);
  if (p === parsed.root) {
    return "";
  }
  const rel = path.relative(parsed.root, p);
  const parts = rel.split(/[\\/]+/).filter(Boolean);
  return parts.length >= 2 ? p : "";
}

function _path_roots(): [string, string] {
  if (_PROJECT_ROOT === null) {
    _PROJECT_ROOT = _replaceable_root(path.resolve(__dirname, ".."));
  }
  const homeEnv = process.env.HOME ?? "";
  if (_HOME_CACHE[0] !== homeEnv) {
    _HOME_CACHE = [homeEnv, _replaceable_root(os.homedir())];
  }
  return [_PROJECT_ROOT, _HOME_CACHE[1]];
}

export function scrub_text(text: unknown, opts: { scrub_paths?: boolean } = {}): string {
  const scrubPaths = opts.scrub_paths ?? true;
  let out = String(text ?? "");
  if (!out) {
    return "";
  }
  out = out.replace(_AUTHORIZATION_SCHEME_RE, (_m, prefix, quote) => `${prefix}****${quote}`);
  out = out.replace(_QUOTED_SECRET_RE, (_m, prefix, quote) => `${prefix}${quote}****${quote}`);
  out = out.replace(_UNQUOTED_PHRASE_SECRET_RE, (_m, prefix) => `${prefix}****`);
  out = out.replace(_NAMED_SECRET_RE, (_m, prefix, quote) => `${prefix}${quote}****${quote}`);
  out = out.replace(_SPACE_SECRET_RE, (_m, key, sep) => `${key}${sep}****`);
  out = out.replace(_BEARER_RE, "Bearer ****");
  out = out.replace(_SSHPASS_RE, (m, value) => {
    const valueOffset = m.lastIndexOf(value);
    return m.slice(0, valueOffset) + "****";
  });
  out = out.replace(
    _CURL_USER_RE,
    (_m, gap, flag, quote, user) => `curl${gap}${flag}${quote}${user}****${quote}`
  );
  out = out.replace(
    _SUDO_STDIN_RE,
    (_m, quote, _value, pipe) => `echo ${quote}****${quote}${pipe}`
  );
  out = out.replace(
    _SENDLINE_RE,
    (_m, quote, _value, tail) => `sendline(${quote}****${quote}${tail}`
  );
  out = out.replace(_SUDO_PROMPT_RE, (_m, prefix) => `${prefix}****`);
  out = out.replace(_URL_USERINFO_RE, (_m, prefix, _value, at) => `${prefix}****${at}`);
  for (const value of _loaded_secret_values()) {
    out = out.split(value).join("****");
  }
  if (scrubPaths) {
    const [project, home] = _path_roots();
    if (project) {
      out = out.split(project).join("<project-root>");
    }
    if (home) {
      out = out.split(home).join("<user-home>");
    }
    out = out.replace(_DEVICE_INTERNAL_PATH_RE, "<device-internal-path>");
    out = out.replace(_UNIX_INTERNAL_PATH_RE, "<internal-path>");
    out = out.replace(_WINDOWS_INTERNAL_PATH_RE, "<internal-path>");
  }
  return out;
}

export const _SHA256_HEX_RE_EXPORT = _SHA256_HEX_RE;
