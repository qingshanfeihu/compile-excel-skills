const _CONTROL_RE = /[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/g;
const _URL_RE = /\b(?:https?|ftp):\/\/[^\s<>]+/gi;
const _WINDOWS_PATH_RE = /(?<!\w)[A-Za-z]:\\(?:[^\s\\]+\\)*[^\s\\]+/g;
const _UNIX_PATH_RE = /(?<![\w:])\/(?:[^\s/]+\/)+[^\s/]+/g;
const _REPO_PATH_RE = /\b(?:workspace|knowledge|runtime|main|tests)\/(?:[^\s/]+\/)*[^\s/]+/g;
const _PRIVATE_KEY_RE = /-----BEGIN [^-\r\n]*PRIVATE KEY-----.*?-----END [^-\r\n]*PRIVATE KEY-----/gis;
const _ENV_KEY_BODY = "[A-Za-z][A-Za-z0-9_]*(?:PASSWORD|PASSWD|PWD|SECRET|TOKEN|API_KEY|ACCESS_KEY|LICENSE_KEY)";
const _GENERIC_CREDENTIAL_KEY_BODY = `(?:${_ENV_KEY_BODY}|password|passwd|pwd|secret|api[_ -]?key|access[_ -]?token|authorization|cookie|license[_ -]?key)`;
const _CREDENTIAL_RE = /\b(?:password|passwd|pwd|secret|api[_ -]?key|access[_ -]?token|authorization|cookie|license[_ -]?key)\b\s*[:=]\s*[^\r\n]+/gim;
const _ENV_CREDENTIAL_RE = new RegExp(
  `(?<![A-Za-z0-9_])[\\"']?${_ENV_KEY_BODY}[\\"']?\\s*[:=]\\s*(?:[\\"'][^\\"'\\r\\n]*[\\"']|[^\\r\\n]+)`,
  "gim"
);
const _HTML_TAG_RE = /<\/?[A-Za-z][^>\r\n]*>/g;
const _HTML_BLOCK_TAG_RE = /<\/?(?:h[1-6]|p|div|li|br|tr|td|th|section|article)[^>\r\n]*>/gi;
const _ANSI_ESCAPE_RE = /\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))/g;
const _MARKDOWN_LINK_RE = /\[([^\]\r\n]+)\]\([^\)\r\n]*\)/g;
const _DECORATED_CREDENTIAL_KEY_RE = new RegExp(
  `(?<![A-Za-z0-9_])(?:\\*\\*|__|\`{1,3})?[\\"']?(?<key>${_GENERIC_CREDENTIAL_KEY_BODY})[\\"']?(?:\\*\\*|__|\`{1,3})?\\s*(?<sep>[:=])`,
  "gim"
);
const _YAML_CREDENTIAL_BLOCK_RE = new RegExp(
  `^[ \\t]*[\\"']?${_GENERIC_CREDENTIAL_KEY_BODY}[\\"']?\\s*[:=]\\s*[|>][+-]?[ \\t]*(?:\\r?\\n[ \\t]+[^\\r\\n]*)+`,
  "gim"
);
const _MARKDOWN_TABLE_CREDENTIAL_RE = new RegExp(
  `^[ \\t]*\\|[ \\t]*(?:\\*\\*|__|\`{1,3})?[\\"']?${_GENERIC_CREDENTIAL_KEY_BODY}[\\"']?(?:\\*\\*|__|\`{1,3})?[ \\t]*\\|[ \\t]*[^|\\r\\n]+(?:\\|[^\\r\\n]*)?$`,
  "gim"
);
const _ADJACENT_CREDENTIAL_VALUE_RE = new RegExp(
  `^[ \\t|]*(?:\\*\\*|__|\`{1,3})?[\\"']?${_GENERIC_CREDENTIAL_KEY_BODY}[\\"']?(?:\\*\\*|__|\`{1,3})?(?:[ \\t]*\\|[ \\t]*[^|\\r\\n]+|\\r?\\n[ \\t]*[^\\r\\n]+|[ \\t]+[^|\\r\\n]+)(?:\\|[^\\r\\n]*)?$`,
  "gim"
);
const _AUTH_SCHEME_CREDENTIAL_RE = /(?<![A-Za-z0-9_])authorization\s+(?:bearer|basic)\s+\S+/gim;
const _CLI_CREDENTIAL_RE = new RegExp(
  `(?<![A-Za-z0-9_])--(?:${_GENERIC_CREDENTIAL_KEY_BODY})(?:\\s*=\\s*|\\s+)(?:[\\"'][^\\"'\\r\\n]*[\\"']|\\S+)`,
  "gim"
);
const _SENSITIVE_CREDENTIAL_KEY_RE = new RegExp(`^(?:${_GENERIC_CREDENTIAL_KEY_BODY})$`, "i");
const _PROHIBITED_HEADING_RE =
  /(?:actual\s+(?:results?|behaviors?|outputs?)|observed\s+(?:results?|behaviors?|outputs?)|actual|log\s+(?:outputs?|entries?|history)|logs?|steps?\s+to\s+reproduce|reproduction(?:\s+steps?)?|repro(?:duction)?(?:\s+steps?)?|comment\s+history|comments?|how\s+to\s+reproduce|cli\s+output|notes?|remarks?|show\s+version|detail\s+information|实际结果|实际现象|当前结果|实际输出|复现步骤|复现过程|评论|备注|日志|复现|设备回显)/i;
const _PROHIBITED_LABEL_RE = new RegExp(
  `(?<![A-Za-z0-9_])(?:${_PROHIBITED_HEADING_RE.source})(?:\\s*(?:for|on|\\/|[-–—]|[\\[(（【])[^:：\\r\\n]*)?\\s*(?:[:：]|$)`,
  "i"
);
const _MARKDOWN_DECORATION_RE = /^[*_~`\s]+|[*_~`\s]+$/g;
const _ATX_OPEN_RE = /^#{1,6}\s+/;
const _ATX_CLOSE_RE = /\s+#{1,6}\s*$/;
const _BLOCKQUOTE_RE = /^>\s*/;
const _UNORDERED_LIST_RE = /^[-+*]\s+/;
const _ORDERED_LIST_RE = /^\d+[.)、．]\s*/;
const _CHINESE_ORDER_RE = /^(?:[（(][一二三四五六七八九十百千]+[）)]|[一二三四五六七八九十百千]+[、.)）．])\s*/;
const _TASK_LIST_RE = /^\[(?: |x|X)\]\s*/;
const _PROHIBITED_LABEL_RE_SEARCH = new RegExp(_PROHIBITED_LABEL_RE.source, "i");
const _PROHIBITED_HEADING_RE_MATCH = new RegExp(`^(?:${_PROHIBITED_HEADING_RE.source})`, "i");
const _QUALIFIER_RE = /^\s*(?:[\[(（【].*[\])）】]|[-–—]\s*.+)$/;

function htmlUnescape(text: string): string {
  return text
    .replace(/&#x([0-9A-Fa-f]+);?/g, (m, hex) => {
      const code = parseInt(hex, 16);
      try {
        return String.fromCodePoint(code);
      } catch {
        return m;
      }
    })
    .replace(/&#(\d+);?/g, (m, dec) => {
      const code = parseInt(dec, 10);
      try {
        return String.fromCodePoint(code);
      } catch {
        return m;
      }
    })
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&quot;/gi, '"')
    .replace(/&apos;/gi, "'");
}

function removeFormatChars(text: string): string {
  return text
    .split("")
    .filter((c) => !/[\u200B-\u200F\u202A-\u202E\u2060\u2061\u2062\u2063\u2064\uFEFF]/.test(c))
    .join("");
}

function _normalize_security_markup(value: unknown, opts: { preserve_blocks: boolean }): string {
  let text = removeFormatChars(htmlUnescape(String(value ?? "")).replace(_ANSI_ESCAPE_RE, ""));
  if (opts.preserve_blocks) {
    text = text.replace(_HTML_BLOCK_TAG_RE, "\n");
  }
  text = text.replace(_HTML_TAG_RE, " ");
  text = text.replace(_MARKDOWN_LINK_RE, (_m, label) => label);
  return text;
}

function _normalize_credential_markup(value: unknown): string {
  let text = _normalize_security_markup(value, { preserve_blocks: false });
  text = text.replace(_DECORATED_CREDENTIAL_KEY_RE, (_m, ...args) => {
    const groups = args[args.length - 1] as Record<string, string>;
    return `${groups["key"]}${groups["sep"]}`;
  });
  return text;
}

export function is_sensitive_credential_key(value: unknown): boolean {
  let normalized = _normalize_credential_markup(value).trim();
  normalized = normalized.replace(_MARKDOWN_DECORATION_RE, "").trim();
  normalized = normalized.replace(/^[|\[\](){}<>"' ]+|[|\[\](){}<>"' ]+$/g, "");
  normalized = normalized.replace(/^--/, "");
  return _SENSITIVE_CREDENTIAL_KEY_RE.test(normalized);
}

function _contains_credential_material(value: unknown): boolean {
  const normalized = _normalize_credential_markup(value);
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const { scrub_text } = require("../security_scrub") as typeof import("../security_scrub");
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

export function contains_credential_material(value: unknown): boolean {
  return _contains_credential_material(value);
}

export function _coverage(left: Set<string>, right: Set<string>): number {
  if (!left.size || !right.size) {
    return 0;
  }
  let intersection = 0;
  for (const v of left) {
    if (right.has(v)) {
      intersection++;
    }
  }
  return intersection / left.size;
}

export function _dice(left: Set<string>, right: Set<string>): number {
  if (!left.size || !right.size) {
    return 0;
  }
  let intersection = 0;
  for (const v of left) {
    if (right.has(v)) {
      intersection++;
    }
  }
  return (2 * intersection) / (left.size + right.size);
}

export function scrub_declaration_text(value: unknown, opts: { limit?: number } = {}): string {
  const limit = opts.limit ?? 8000;
  let text = _normalize_credential_markup(value).replace(_CONTROL_RE, "");
  if (_contains_credential_material(text)) {
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

export function contains_prohibited_declaration(value: unknown): boolean {
  const normalized = _normalize_security_markup(value, { preserve_blocks: true });
  for (const rawLine of normalized.split(/\r\n|\n|\r/)) {
    let line = rawLine.trim();
    for (let i = 0; i < 12; i++) {
      const previous = line;
      for (const pattern of [
        _BLOCKQUOTE_RE,
        _ATX_OPEN_RE,
        _UNORDERED_LIST_RE,
        _ORDERED_LIST_RE,
        _CHINESE_ORDER_RE,
        _TASK_LIST_RE,
      ]) {
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
    if (_PROHIBITED_LABEL_RE_SEARCH.test(line)) {
      return true;
    }
    let heading: string;
    if (line.startsWith("[") && line.includes("]")) {
      heading = line.slice(1, line.indexOf("]"));
    } else {
      heading = line.split(/[:：]/, 1)[0];
    }
    heading = heading.replace(_ATX_CLOSE_RE, "").trim();
    heading = heading.replace(_MARKDOWN_DECORATION_RE, "").trim();
    const match = _PROHIBITED_HEADING_RE_MATCH.exec(heading);
    const qualifier = match ? heading.slice(match[0].length) : "";
    if (match !== null && (!qualifier || _QUALIFIER_RE.test(qualifier))) {
      return true;
    }
  }
  return false;
}
