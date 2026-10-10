import { z } from "zod";
import { restore_endpoint_encodings } from "../../common/nullable_scalar";

export const SCHEMA = "ist.mindmap-recompose-result";
const _MAX_BYTES = 64 * 1024;

export const MindmapRecomposeBucketCounts = z.object({
  exp_recipe: z.number().int().min(0),
  step_recipe: z.number().int().min(0),
  true_gap: z.number().int().min(0),
}).strict();

export type MindmapRecomposeBucketCounts = z.infer<typeof MindmapRecomposeBucketCounts>;

export const MindmapRecomposeSummary = z.object({
  case_count: z.number().int().min(0),
  bucket_counts: MindmapRecomposeBucketCounts,
  message_zh: z.string().min(1).max(16384),
}).strict();

export type MindmapRecomposeSummary = z.infer<typeof MindmapRecomposeSummary>;

export const MindmapRecomposeResult = z.object({
  schema: z.literal("ist.mindmap-recompose-result"),
  status: z.enum(["produced", "failed"]),
  artifact: z.string().nullable(),
  summary: MindmapRecomposeSummary.nullable(),
  error_code: z.string().nullable(),
  reason_zh: z.string().nullable(),
}).strict().superRefine((val, ctx) => {
  if (val.status === "produced") {
    if (typeof val.artifact !== "string" || !val.artifact.trim()) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: "produced result requires an artifact path" });
    }
    if (val.summary === null || val.error_code !== null || val.reason_zh !== null) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: "produced result fields are inconsistent" });
    }
  } else {
    if (val.artifact !== null || val.summary !== null || typeof val.error_code !== "string" || !val.error_code.trim() || typeof val.reason_zh !== "string" || !val.reason_zh.trim()) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: "failed result fields are inconsistent" });
    }
  }
});

export type MindmapRecomposeResult = z.infer<typeof MindmapRecomposeResult>;

function _reject_duplicate_keys(pairs: [string, any][]): Record<string, any> {
  const result: Record<string, any> = {};
  for (const [key, value] of pairs) {
    if (key in result) {
      throw new Error(`duplicate JSON key: ${key}`);
    }
    result[key] = value;
  }
  return result;
}

function _reject_constant(value: string): never {
  throw new Error(`non-finite JSON constant: ${value}`);
}

export function parse_mindmap_recompose_result(raw: string): Record<string, any> {
  if (typeof raw !== "string") {
    throw new Error("mindmap recompose result must be text");
  }
  if (!raw.trim() || Buffer.byteLength(raw, "utf8") > _MAX_BYTES) {
    throw new Error("mindmap recompose result is empty or exceeds its byte budget");
  }
  try {
    const payload = JSON.parse(raw);
    const result = MindmapRecomposeResult.parse(payload);
    return result;
  } catch (exc) {
    throw new Error("invalid mindmap recompose structured response");
  }
}

export function render_mindmap_recompose_result(payload: Record<string, any>): string {
  const result = MindmapRecomposeResult.parse(payload);
  return JSON.stringify(result, null, 2);
}

export function invalid_mindmap_recompose_result(failure_note: string = ""): string {
  const note = String(failure_note ?? "").trim().slice(0, 200);
  return render_mindmap_recompose_result({
    schema: SCHEMA,
    status: "failed",
    artifact: null,
    summary: null,
    error_code: "invalid_structured_response",
    reason_zh: "重组结果未通过 LangChain 结构化返回校验" + (note ? `；${note}` : ""),
  });
}
