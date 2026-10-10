import crypto from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { _cex_data_path, _cex_identity_set, _cex_set_caller } from "../_root";

_cex_set_caller("cex_core.engine.case_compiler.package_advisories");

export const HISTORICAL_TARGET_COUNT = 325;
export const POISON_RULE_ID = "PKG-POISON-001";
export const USER_DENY_RULE_ID = "PKG-RULING-DENY-001";
const _DENY_RULINGS_RELATIVE = "scripts/data/package_deny_rulings.json";
const _POISON_RULINGS_RELATIVE = "scripts/data/package_poison_rulings.json";
export const PACKAGE_REFERENCE_ERROR = "E_PACKAGE_REFERENCE_DENIED";
export const DENIED_668_AUTOIDS = _cex_identity_set("main/case_compiler/package_advisories.py:DENIED_668_AUTOIDS");
const _GRADE_ORDER: Record<string, number> = { A: 0, B: 1, C: 2 };
export const PACKAGE_ADVISORIES_PATH = path.join(_cex_data_path(""), "knowledge/data/compile_ref/package_advisories_10.5.json");

function _sha256(p: string): string {
  return crypto.createHash("sha256").update(fs.readFileSync(p)).digest("hex");
}

function _autoids(p: string): string[] {
  const { steps_from_xlsx } = require("../ist_core/tools/device/structural_gate");
  const [aid] = steps_from_xlsx(p);
  return aid ? [aid] : [];
}

export function package_asset_autoid(asset_id: string): string {
  const stem = path.basename(asset_id, path.extname(asset_id));
  return stem.startsWith("verified_") ? stem.slice("verified_".length) : "";
}

export function classify_package(p: string, provenance: Record<string, any>, opts: { poison_confirmed?: boolean; retro_grade?: string } = {}): Record<string, any> {
  const { lint_xlsx_case } = require("../ist_core/tools/device/structural_gate");
  const digest = _sha256(p);
  const name = path.basename(p);
  let entry = provenance[name];
  const reasons: string[] = [];
  const { coverage_reason_code } = require("./claim_coverage");
  const lint = lint_xlsx_case(p);
  if (!lint.ok) {
    reasons.push("structural_lint_failed");
  }
  const certification = typeof entry === "object" && entry !== null ? entry.certification : null;
  const coverageReason = coverage_reason_code(certification);
  if (typeof certification === "object" && certification !== null && Object.keys(certification).length) {
    if (coverageReason) {
      reasons.push(coverageReason);
    }
  } else if (lint.advisories && lint.advisories.length) {
    reasons.push("lint_advisory_present");
  }
  if (typeof entry !== "object" || entry === null || !("result" in entry)) {
    reasons.push("structured_delivery_receipt_missing");
    entry = {};
  } else {
    if (entry.ctx !== "delivery" || entry.result !== "pass") {
      reasons.push("delivery_pass_missing");
    }
    if (!entry.build) {
      reasons.push("device_build_missing");
    }
    const artifact = String(entry.artifact || "");
    if (!artifact) {
      reasons.push("artifact_fingerprint_missing");
    } else if (artifact.slice(artifact.lastIndexOf(":") + 1).toLowerCase() !== digest) {
      reasons.push("artifact_fingerprint_mismatch");
    }
  }
  const autoids = _autoids(p);
  const filenameAutoid = package_asset_autoid(p);
  if (filenameAutoid && !autoids.includes(filenameAutoid)) {
    autoids.push(filenameAutoid);
  }
  const identityDenied = (opts.poison_confirmed ?? false) || autoids.some((a) => (DENIED_668_AUTOIDS as Set<string>).has(a));
  let status: string;
  let certificationBasis: string;
  let certificationReasons: string[];
  if (opts.retro_grade === "A") {
    status = "certified";
    certificationBasis = "retro_replay_clean";
    certificationReasons = [];
  } else if (opts.retro_grade === "B" || opts.retro_grade === "C") {
    status = "unverified";
    certificationBasis = "retro_replay";
    certificationReasons = [`retro_replay_grade_${opts.retro_grade.toLowerCase()}`];
  } else {
    status = reasons.length === 0 ? "certified" : "unverified";
    certificationBasis = "artifact_receipt_replay";
    certificationReasons = reasons;
  }
  const flags: string[] = [];
  if (opts.poison_confirmed) {
    flags.push("poison_confirmed");
  }
  if (opts.retro_grade && opts.retro_grade in _GRADE_ORDER) {
    flags.push(`retro_grade_${opts.retro_grade.toLowerCase()}`);
  }
  return {
    status,
    certification_basis: certificationBasis,
    asset_id: name,
    sha256: digest,
    sha256_aliases: [digest],
    autoids,
    reason_codes: certificationReasons,
    flags,
    deny_rules: identityDenied ? [POISON_RULE_ID] : [],
    lint: {
      violations: (lint.violations || []).map((v: any) => v.code),
      advisories: (lint.advisories || []).map((v: any) => v.code),
      disabled: (lint.disabled || []).map((v: any) => v.code),
    },
    claim_coverage:
      typeof certification === "object" && certification !== null && Object.keys(certification).length
        ? {
            status: String(certification.status || ""),
            fidelity: String(certification.fidelity || ""),
            uncovered_expectation_ids: (certification.uncovered_expectation_ids || []).map((v: any) => String(v)),
          }
        : null,
    receipt: Object.fromEntries(["ctx", "result", "build", "artifact", "run_id"].filter((key) => entry[key]).map((key) => [key, entry[key]])),
  };
}

function _repoRelative(p: string): string {
  const { PROJECT_ROOT } = require("../knowledge_paths");
  const rel = path.relative(path.resolve(PROJECT_ROOT), path.resolve(p));
  if (!rel.startsWith("..")) {
    return rel.split(path.sep).join("/");
  }
  return p.split(path.sep).join("/");
}

export class PackageAdvisorySourceMissing extends Error {}

function _denyRulings(p: string | null, opts: { require_sha_scope?: boolean } = {}): Array<Record<string, any>> {
  if (p === null) {
    return [];
  }
  if (!fs.existsSync(p) || !fs.statSync(p).isFile()) {
    throw new PackageAdvisorySourceMissing(
      `先例包封禁裁决来源不在：${p}。缺它重算会让用户按 sha 封禁的卷静默放行；要么把文件恢复到位，要么显式传 deny_rulings_path=None。`
    );
  }
  const payload = JSON.parse(fs.readFileSync(p, "utf8"));
  const rows = typeof payload === "object" && payload !== null ? payload.rulings : null;
  const out: Array<Record<string, any>> = [];
  for (const row of rows || []) {
    if (typeof row !== "object" || row === null) continue;
    const digest = String(row.sha256 || "").trim().toLowerCase();
    const assetId = String(row.asset_id || "").trim();
    if (digest.length !== 64 || !assetId.endsWith(".xlsx") || ((opts.require_sha_scope ?? false) && row.scope !== "sha256")) {
      throw new PackageAdvisorySourceMissing(`先例包封禁裁决条目不闭合：${JSON.stringify(row.ruling_id)}`);
    }
    out.push({
      ruling_id: String(row.ruling_id || ""),
      ruled_at: String(row.ruled_at || ""),
      asset_id: assetId,
      autoid: String(row.autoid || ""),
      sha256: digest,
      reason_code: String(row.reason_code || ""),
    });
  }
  return out;
}

function _applyDenyRulings(records: Record<string, any>, rulings: Array<Record<string, any>>, opts: { rule_id?: string } = {}): void {
  const ruleId = opts.rule_id ?? USER_DENY_RULE_ID;
  const shaField = ruleId === POISON_RULE_ID ? "poison_sha256s" : "denied_sha256s";
  const flag = ruleId === POISON_RULE_ID ? "poison_confirmed" : "user_ruling_denied";
  for (const ruling of rulings) {
    const name = ruling.asset_id;
    let record = records[name];
    if (typeof record !== "object" || record === null) {
      record = {
        status: "unverified",
        certification_basis: "user_ruling_deny",
        asset_id: name,
        asset_state: "quarantined",
        sha256: "",
        sha256_aliases: [],
        autoids: ruling.autoid ? [ruling.autoid] : [],
        reason_codes: ["user_ruling_deny"],
        flags: [flag],
        deny_rules: [],
        lint: { violations: [], advisories: [], disabled: [] },
        claim_coverage: null,
        receipt: {},
      };
      records[name] = record;
    }
    record.deny_rules = [...new Set([...(record.deny_rules || []), ruleId])].sort();
    record.flags = [...new Set([...(record.flags || []), flag])].sort();
    record[shaField] = [...new Set([...(record[shaField] || []), ruling.sha256])].sort();
    record.deny_rulings = record.deny_rulings || [];
    record.deny_rulings = [...new Set([...record.deny_rulings, ruling.ruling_id])].sort();
    if (String(record.sha256 || "").toLowerCase() === ruling.sha256) {
      record.status = "unverified";
      if (!(record.reason_codes || []).includes("user_ruling_deny")) {
        record.reason_codes = [...(record.reason_codes || []), "user_ruling_deny"];
      }
    }
  }
}

function _retroGrades(retroScanPath: string | null): Record<string, string> {
  if (retroScanPath === null) {
    return {};
  }
  if (!fs.existsSync(retroScanPath) || !fs.statSync(retroScanPath).isFile()) {
    throw new PackageAdvisorySourceMissing(
      `retro 分级来源不在：${retroScanPath}。缺它重算会让 133 卷的 retro_grade_* 标记整体消失、并改变认证判定；要么把来源恢复到位，要么显式传 retro_scan_path=None 并在 source 块如实标注未合入。`
    );
  }
  const payload = JSON.parse(fs.readFileSync(retroScanPath, "utf8"));
  const grades: Record<string, string> = {};
  const library = typeof payload === "object" && payload !== null ? payload.library || [] : [];
  for (const row of library) {
    if (typeof row !== "object" || row === null) continue;
    const name = String(row.file || "");
    const grade = String(row.grade || "");
    if (!name || !(grade in _GRADE_ORDER)) continue;
    const previous = grades[name] || "A";
    grades[name] = _GRADE_ORDER[grade] >= _GRADE_ORDER[previous] ? grade : previous;
  }
  return grades;
}

const _DENY_RULINGS_DEFAULT = Symbol("default");

function _defaultDenyRulingsPath(): string {
  const { PROJECT_ROOT } = require("../knowledge_paths");
  return path.join(PROJECT_ROOT, _DENY_RULINGS_RELATIVE);
}

export function build_package_advisories(
  mirror_root: string,
  provenance_path: string,
  opts: {
    poison_root?: string | null;
    retro_scan_path?: string | null;
    historical_target_count?: number;
    deny_rulings_path?: string | null;
  } = {}
): Record<string, any> {
  let provenance: Record<string, any> = {};
  if (fs.existsSync(provenance_path) && fs.statSync(provenance_path).isFile()) {
    const loaded = JSON.parse(fs.readFileSync(provenance_path, "utf8"));
    if (typeof loaded === "object" && loaded !== null) {
      provenance = loaded;
    }
  }
  const files = fs.readdirSync(mirror_root).filter((f) => f.startsWith("verified_") && f.endsWith(".xlsx")).sort().map((f) => path.join(mirror_root, f));
  const grades = _retroGrades(opts.retro_scan_path ?? null);
  const records: Record<string, any> = {};
  for (const p of files) {
    records[path.basename(p)] = classify_package(p, provenance, { retro_grade: grades[path.basename(p)] || "" });
  }
  if (opts.poison_root !== null && opts.poison_root !== undefined && (!fs.existsSync(opts.poison_root) || !fs.statSync(opts.poison_root).isDirectory())) {
    throw new PackageAdvisorySourceMissing(
      `隔离资产目录不在：${opts.poison_root}。缺它重算会把确认中毒的先例包静默放行；要么把目录恢复到位，要么显式传 poison_root=None。`
    );
  }
  const rulingsPath = opts.deny_rulings_path === undefined ? _defaultDenyRulingsPath() : opts.deny_rulings_path;
  const rulings = rulingsPath !== null ? _denyRulings(rulingsPath) : [];
  const { PROJECT_ROOT } = require("../knowledge_paths");
  const poisonRulings = _denyRulings(path.join(PROJECT_ROOT, _POISON_RULINGS_RELATIVE), { require_sha_scope: true });
  const quarantineFiles = opts.poison_root ? fs.readdirSync(opts.poison_root).filter((f) => f.startsWith("verified_") && f.endsWith(".xlsx")).sort().map((f) => path.join(opts.poison_root!, f)) : [];
  for (const p of quarantineFiles) {
    const quarantined = classify_package(p, provenance, { poison_confirmed: true, retro_grade: grades[path.basename(p)] || "" });
    const existing = records[path.basename(p)];
    quarantined.poison_sha256s = [quarantined.sha256];
    if (existing === undefined) {
      quarantined.asset_state = "quarantined";
      records[path.basename(p)] = quarantined;
      continue;
    }
    existing.flags = [...new Set([...existing.flags, "poison_confirmed"])].sort();
    existing.deny_rules = [...new Set([...existing.deny_rules, POISON_RULE_ID])].sort();
    existing.sha256_aliases = [...new Set([...existing.sha256_aliases, quarantined.sha256])].sort();
    existing.poison_sha256s = [...new Set([...(existing.poison_sha256s || []), quarantined.sha256])].sort();
  }
  _applyDenyRulings(records, poisonRulings, { rule_id: POISON_RULE_ID });
  _applyDenyRulings(records, rulings);
  for (const autoid of [...(DENIED_668_AUTOIDS as Set<string>)].sort()) {
    const name = `verified_${autoid}.xlsx`;
    if (name in records) continue;
    records[name] = {
      status: "unverified",
      certification_basis: "mandatory_deny_identity",
      asset_id: name,
      asset_state: "quarantined",
      sha256: "",
      sha256_aliases: [],
      autoids: [autoid],
      reason_codes: ["mandatory_deny_identity"],
      flags: ["identity_deny_tombstone"],
      deny_rules: [POISON_RULE_ID],
      lint: { violations: [], advisories: [], disabled: [] },
      receipt: {},
    };
  }
  const activeNames = new Set(files.map((p) => path.basename(p)));
  const certified = [...activeNames].filter((name) => records[name].status === "certified").length;
  const activeUnverified = [...activeNames].filter((name) => records[name].status !== "certified").length;
  const current = files.length;
  const target = Number(opts.historical_target_count ?? HISTORICAL_TARGET_COUNT);
  return {
    schema_version: 3,
    classification: "certified|unverified",
    source: {
      kind: "package_registry_projection",
      path: "knowledge/framework/verified/verified_*.xlsx",
      quarantine_path: opts.poison_root && quarantineFiles.length ? `${_repoRelative(opts.poison_root)}/verified_*.xlsx` : "",
      current_manifest_count: current,
      quarantined_manifest_count: quarantineFiles.length,
      record_count: Object.keys(records).length,
      historical_target_count: target,
      historical_manifest_available: current === target,
      population_complete: current === target,
      population_note: current === target
        ? "current manifest equals the historical target"
        : "the historical 325-volume member manifest is not present; current files were fully replayed, but they must not be reported as all 325",
    },
    baseline: {
      certified,
      unverified: activeUnverified,
      current_population_coverage: current ? certified / current : 0.0,
      historical_target_lower_bound: target ? certified / target : 0.0,
    },
    records,
  };
}

export function package_rejection(opts: { autoid?: string; sha256?: string; asset_id?: string; projection: Record<string, any> }): string {
  const aid = String(opts.autoid || "").trim();
  const digest = String(opts.sha256 || "").trim().toLowerCase();
  const asset = String(opts.asset_id || "").trim();
  if ((DENIED_668_AUTOIDS as Set<string>).has(aid)) {
    return `${PACKAGE_REFERENCE_ERROR} asset_id=${asset || aid} rule_id=${POISON_RULE_ID}`;
  }
  const records = typeof opts.projection === "object" && opts.projection !== null ? (opts.projection as any).records || {} : {};
  for (const [name, record] of Object.entries(records)) {
    if (typeof record !== "object" || record === null) continue;
    const rules = (record as any).deny_rules || [];
    if (rules.includes(POISON_RULE_ID)) {
      const aliases = new Set<string>(((record as any).poison_sha256s || (record as any).sha256_aliases || []).map((v: any) => String(v).toLowerCase()));
      const identities = new Set<string>(((record as any).autoids || []).map((v: any) => String(v)));
      const identityDenied = [...identities].some((v) => (DENIED_668_AUTOIDS as Set<string>).has(v));
      let matched: boolean;
      if (identityDenied) {
        for (const v of (record as any).sha256_aliases || []) {
          aliases.add(String(v).toLowerCase());
        }
        matched = asset === name || Boolean(aid && identities.has(aid)) || Boolean(digest && aliases.has(digest));
      } else {
        matched = Boolean(digest && aliases.has(digest));
      }
      if (matched) {
        return `${PACKAGE_REFERENCE_ERROR} asset_id=${name} rule_id=${POISON_RULE_ID}`;
      }
    }
    if (rules.includes(USER_DENY_RULE_ID)) {
      const denied = new Set<string>(((record as any).denied_sha256s || []).map((v: any) => String(v).toLowerCase()));
      if (digest && denied.has(digest)) {
        return `${PACKAGE_REFERENCE_ERROR} asset_id=${name} rule_id=${USER_DENY_RULE_ID}`;
      }
    }
  }
  return "";
}

export function read_package_projection(p?: string | null): Record<string, any> {
  const source = p || PACKAGE_ADVISORIES_PATH;
  const payload = JSON.parse(fs.readFileSync(source, "utf8"));
  if (typeof payload !== "object" || payload === null || typeof payload.records !== "object" || payload.records === null) {
    throw new Error("package advisory projection has no records object");
  }
  return payload;
}

export function validate_package_expect_reference(asset_id: string, expect_source: string): string {
  if (String(expect_source || "").trim() !== "poison_confirmed") {
    return "";
  }
  return `${PACKAGE_REFERENCE_ERROR} asset_id=${(String(asset_id || "-").trim() || "-")} rule_id=${POISON_RULE_ID}`;
}

export function write_json_atomic(p: string, payload: Record<string, any>): void {
  fs.mkdirSync(path.dirname(p), { recursive: true });
  const tmp = path.join(path.dirname(p), `.${path.basename(p)}.${process.pid}.${crypto.randomBytes(6).toString("hex")}.tmp`);
  try {
    fs.writeFileSync(tmp, JSON.stringify(payload, null, 2) + "\n", "utf8");
    const fd = fs.openSync(tmp, "r+");
    try {
      fs.fsyncSync(fd);
    } finally {
      fs.closeSync(fd);
    }
    fs.renameSync(tmp, p);
  } catch (exc) {
    try {
      fs.unlinkSync(tmp);
    } catch {}
    throw exc;
  }
}
