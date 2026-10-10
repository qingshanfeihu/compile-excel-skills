#!/usr/bin/env node
// 生成：tools/extract_engine.py ← InfoTest scripts/gen_confirmation_prompt_projection.py（sha256 db38b798f0b23cec）。不在这里手改。
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { _cex_data_path } from "../_root";

const ROOT = _cex_data_path("");
const DEFAULT_OUTPUT = path.join(ROOT, "knowledge", "data", "compile_ref", "confirmation_prompt_projection.json");
const SCHEMA = "ist.confirmation-prompt-projection";

interface PromptRule {
  id: string;
  pattern: string;
  kind: string;
  description: string;
}

const _PROMPT_RULES: PromptRule[] = [
  { id: "y-n", pattern: "请输入[Yy]/[Nn]", kind: "binary", description: "Y/N 确认提示" },
  { id: "yes-no", pattern: "[Yy]es/[Nn]o", kind: "binary", description: "Yes/No 确认提示" },
  { id: "continue", pattern: "是否继续", kind: "confirm", description: "继续确认" },
  { id: "press-key", pattern: "按任意键", kind: "ack", description: "按键确认" },
  { id: "password", pattern: "请输入密码", kind: "credential", description: "密码输入提示" },
];

export function build_projection(): Record<string, any> {
  return {
    schema: SCHEMA,
    prompts: _PROMPT_RULES,
    prompt_count: _PROMPT_RULES.length,
    generated_from: "scripts/gen_confirmation_prompt_projection.py",
  };
}

export function main(): number {
  const payload = build_projection();
  const rendered = JSON.stringify(payload, null, 2) + "\n";
  fs.mkdirSync(path.dirname(DEFAULT_OUTPUT), { recursive: true });
  fs.writeFileSync(DEFAULT_OUTPUT, rendered, "utf8");
  console.log(`wrote ${path.relative(ROOT, DEFAULT_OUTPUT)}`);
  return 0;
}

if (require.main === module) {
  process.exit(main());
}
