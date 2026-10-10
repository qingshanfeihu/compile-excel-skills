import path from "node:path";
import { ClientError } from "./errors.js";
import { compile_excel, CompileError } from "../skills_scripts/compile_excel.js";
import { verifyBatch } from "../skills_scripts/verify_batch.js";

export async function compileWorkbook(casesPath: string, outDir: string): Promise<Record<string, unknown>> {
  let stats: Record<string, unknown>;
  try {
    stats = await compile_excel(casesPath, outDir);
  } catch (e: any) {
    if (e instanceof CompileError) {
      throw new ClientError(`compile_excel refused the cases: ${e.message || e}`);
    }
    throw e;
  }
  const batch = String(stats.batch ?? "");
  return { ...stats, path: path.resolve(outDir, batch, "case.xlsx") };
}

export async function verifyWorkbook(xlsx: string): Promise<Record<string, unknown>> {
  return verifyBatch(path.resolve(xlsx));
}

export const compile_workbook = compileWorkbook;
export const verify_workbook = verifyWorkbook;
