import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { test } from "node:test";

import zlib from "node:zlib";
import { compile_excel } from "../skills_scripts/compile_excel";
import { verifyBatch } from "../skills_scripts/verify_batch";

const TS_ROOT = path.resolve(__dirname, "..", "..");
const EXAMPLE = path.join(TS_ROOT, "skills", "compile-excel", "examples", "slb_cases.json");

function readZipEntry(file: string, name: string): string {
  const buf = fs.readFileSync(file);
  let eocd = -1;
  for (let i = buf.length - 22; i >= 0; i--) {
    if (buf.readUInt32LE(i) === 0x06054b50) {
      eocd = i;
      break;
    }
  }
  assert.notEqual(eocd, -1, "zip EOCD not found");
  const count = buf.readUInt16LE(eocd + 10);
  let offset = buf.readUInt32LE(eocd + 16);
  for (let n = 0; n < count; n++) {
    assert.equal(buf.readUInt32LE(offset), 0x02014b50, "central directory signature");
    const method = buf.readUInt16LE(offset + 10);
    const compSize = buf.readUInt32LE(offset + 20);
    const nameLen = buf.readUInt16LE(offset + 28);
    const extraLen = buf.readUInt16LE(offset + 30);
    const commentLen = buf.readUInt16LE(offset + 32);
    const localOffset = buf.readUInt32LE(offset + 42);
    const entryName = buf.subarray(offset + 46, offset + 46 + nameLen).toString("utf8");
    if (entryName === name) {
      assert.equal(buf.readUInt32LE(localOffset), 0x04034b50, "local header signature");
      const lNameLen = buf.readUInt16LE(localOffset + 26);
      const lExtraLen = buf.readUInt16LE(localOffset + 28);
      const dataStart = localOffset + 30 + lNameLen + lExtraLen;
      const data = buf.subarray(dataStart, dataStart + compSize);
      if (method === 0) return data.toString("utf8");
      assert.equal(method, 8, "unexpected compression method");
      return zlib.inflateRawSync(data).toString("utf8");
    }
    offset += 46 + nameLen + extraLen + commentLen;
  }
  throw new Error(`zip entry not found: ${name}`);
}

function dataValidationRanges(xlsx: string): { sqref: string; formula: string }[] {
  const xml = readZipEntry(xlsx, "xl/worksheets/sheet1.xml");
  const block = /<dataValidations\b[^>]*>([\s\S]*?)<\/dataValidations>/.exec(xml);
  if (!block) return [];
  const out: { sqref: string; formula: string }[] = [];
  for (const m of block[1].matchAll(/<dataValidation\b[^>]*sqref="([^"]+)"[^>]*>[\s\S]*?<formula1>([^<]*)<\/formula1>/g)) {
    out.push({ sqref: m[1], formula: m[2] });
  }
  return out;
}

test("compile→verify roundtrip on the shipped example", async () => {
  const out = fs.mkdtempSync(path.join(os.tmpdir(), "cex-roundtrip-"));
  const stats = await compile_excel(EXAMPLE, out);
  assert.equal(stats.ok, true);
  assert.equal(stats.batch, "slb_smoke");
  assert.equal(stats.case_count, 3);
  assert.equal(stats.check_point_count, 4);
  const xlsx = path.join(stats.batch_dir as string, "case.xlsx");
  const verdict = await verifyBatch(xlsx);
  const failures = (verdict.checks ?? []).filter((c: any) => c && c.ok === false);
  assert.deepEqual(failures, []);
  fs.rmSync(out, { recursive: true, force: true });
});

test("emitted workbook keeps the template's data validations exactly once", async () => {
  const out = fs.mkdtempSync(path.join(os.tmpdir(), "cex-dv-"));
  const stats = await compile_excel(EXAMPLE, out);
  const xlsx = path.join(stats.batch_dir as string, "case.xlsx");
  const ranges = dataValidationRanges(xlsx);
  assert.deepEqual(
    ranges.map((r) => `${r.sqref}|${r.formula}`).sort(),
    ["E30:E5000|IST_E_VALUES", "F30:F5000|INDIRECT(E30)"],
    "data validations must match the template with no duplicated overlapping ranges",
  );
  fs.rmSync(out, { recursive: true, force: true });
});
