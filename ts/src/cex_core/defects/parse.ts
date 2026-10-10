import { createHash } from "node:crypto";

import { get_extractor } from "./html_extractors";
import { scrub_declaration_text } from "./scrub";

const _BACKEND_DIRS: Record<string, string> = {
  bugzilla: "bugzilla",
  zentao: "zentao",
  zentao_story: "zentao",
};
const _RAW_ID_RE = /(?:(BUG|BZ|PLM|ZT|STORY|REQ)-)?(\d+)/i;
const _CLEAN_BUG_ID_RE = /^BUG-[1-9]\d*$/;
const _CLEAN_STORY_ID_RE = /^STORY-[1-9]\d*$/;
export const MAX_HTML_BYTES = 32 * 1024 * 1024;

const _FREE_TEXT_FIELDS = [
  "title",
  "description",
  "steps_to_reproduce",
  "fix_summary",
  "module",
  "product",
  "resolution",
] as const;
const _DROPPED_FIELDS = ["reported_by", "resolved_by", "attachments", "source_html_path"] as const;

export class DefectParseError extends Error {}

function _backend_dir(backend: string): string {
  const key = (backend ?? "").trim().toLowerCase();
  if (key in _BACKEND_DIRS) {
    return _BACKEND_DIRS[key];
  }
  throw new Error("unsupported defect backend");
}

function _canonical_requested_ticket(backendDir: string, rawStem: string): string {
  const match = new RegExp(`^${_RAW_ID_RE.source}$`, "i").exec(rawStem);
  if (match === null) {
    throw new Error("raw defect filename has an invalid ticket id");
  }
  const prefix = (match[1] ?? "").toUpperCase();
  const numberValue = parseInt(match[2], 10);
  if (numberValue < 1) {
    throw new Error("raw defect filename has an invalid ticket id");
  }
  const number = String(numberValue);
  if (backendDir === "bugzilla") {
    if (!["", "BUG", "BZ"].includes(prefix)) {
      throw new Error("raw defect filename does not match backend");
    }
    return `BUG-${number}`;
  }
  if (["STORY", "REQ"].includes(prefix)) {
    return `STORY-${number}`;
  }
  if (["", "BUG", "PLM", "ZT"].includes(prefix)) {
    return `BUG-${number}`;
  }
  throw new Error("raw defect filename does not match backend");
}

function _validate_extracted_ticket(backendDir: string, rawStem: string, ticketId: unknown): string {
  const value = String(ticketId ?? "").trim().toUpperCase();
  const allowed =
    backendDir === "bugzilla"
      ? _CLEAN_BUG_ID_RE.test(value)
      : _CLEAN_BUG_ID_RE.test(value) || _CLEAN_STORY_ID_RE.test(value);
  if (!allowed) {
    throw new Error("extracted defect ticket id is outside the closed set");
  }
  if (value !== _canonical_requested_ticket(backendDir, rawStem)) {
    throw new Error("extracted defect ticket id does not match raw request");
  }
  return value;
}

export function canonical_ticket(backend: string, requested: string): string {
  try {
    return _canonical_requested_ticket(_backend_dir(backend), String(requested ?? "").trim());
  } catch (e) {
    throw new DefectParseError((e as Error).message);
  }
}

export function parse_ticket_html(
  backend: string,
  requested: string,
  html: Buffer | string
): Record<string, any> {
  const raw = typeof html === "string" ? Buffer.from(html, "utf8") : Buffer.from(html);
  if (!raw.length || raw.length > MAX_HTML_BYTES) {
    throw new DefectParseError("defect HTML is empty or too large");
  }
  let backendDir: string;
  let ticket;
  let ticketId: string;
  try {
    backendDir = _backend_dir(backend);
    ticket = get_extractor(backend).extract(raw.toString("utf8"));
    ticketId = _validate_extracted_ticket(backendDir, String(requested ?? "").trim(), ticket.ticket_id);
  } catch (e) {
    if (e instanceof DefectParseError) {
      throw e;
    }
    throw new DefectParseError((e as Error).message);
  }
  if (!ticket.is_valid_detail()) {
    throw new DefectParseError(ticket.invalid_reason || "page is not a valid ticket detail");
  }
  const data: Record<string, any> = ticket.to_dict();
  data["ticket_id"] = ticketId;
  for (const key of _FREE_TEXT_FIELDS) {
    data[key] = scrub_declaration_text(data[key] ?? "");
  }
  for (const key of _DROPPED_FIELDS) {
    delete data[key];
  }
  data["backend"] = (backend ?? "").trim().toLowerCase();
  data["html_sha256"] = createHash("sha256").update(raw).digest("hex");
  return data;
}

export const canonicalTicket = canonical_ticket;
export const parseTicketHtml = parse_ticket_html;
