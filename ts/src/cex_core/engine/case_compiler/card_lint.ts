import fs from "node:fs";
import path from "node:path";
import { _cex_data_path, _cex_set_caller } from "../_root";

_cex_set_caller("cex_core.engine.case_compiler.card_lint");

const _AUTOID18_RE = /(?<!\d)\d{18}(?!\d)/g;
const _REGEX_LEAK_RE = /\\[dswb]|\[\^|\(\?:|\.\*|\.\+/g;
const _HINTS: Record<string, string> = {
  card_internal_token: "internal enum/path token must not reach the signed card face",
  card_bare_autoid:
    "render tail digits (…XXXXXX) on the card face; full autoids stay in the machine-readable cases[] payload",
  card_regex_leak:
    "move the regex into the credential attachment; describe the expectation in plain Chinese on the card face",
  card_build_identity: "reference the build via the environment fact source instead of inlining the literal",
};

function _fullBuildLiteral(): string {
  const p = path.join(_cex_data_path(""), "knowledge", "data", "auto_env", "env_capabilities.json");
  try {
    const payload = JSON.parse(fs.readFileSync(p, "utf8"));
    return String(payload.build || "").trim();
  } catch {
    return "";
  }
}

export function card_lint_findings(text: string, internal_text: string | null = null): Array<Record<string, any>> {
  const source = String(text || "");
  const findings: Array<Record<string, any>> = [];
  const seen = new Set<string>();

  const _add = (code: string, token: string): void => {
    const key = `${code}${token}`;
    if (seen.has(key)) return;
    seen.add(key);
    findings.push({ code, token, hint: _HINTS[code] });
  };
  const { validate_user_facing_text } = require("../ist_core/compile_engine/user_text_contract");
  const validation = validate_user_facing_text({ card_face: internal_text === null ? source : internal_text });
  for (const violation of validation.violations) {
    for (const token of violation.terms) {
      _add("card_internal_token", token);
    }
  }
  const autoidSurface = source.replace(/^签约哈希：[0-9A-Fa-f]{64}\s*$/gm, "");
  for (const match of autoidSurface.matchAll(_AUTOID18_RE)) {
    _add("card_bare_autoid", match[0]);
  }
  for (const match of source.matchAll(_REGEX_LEAK_RE)) {
    _add("card_regex_leak", match[0]);
  }
  const buildLiteral = _fullBuildLiteral();
  if (buildLiteral && source.includes(buildLiteral)) {
    _add("card_build_identity", buildLiteral);
  }
  return findings;
}
