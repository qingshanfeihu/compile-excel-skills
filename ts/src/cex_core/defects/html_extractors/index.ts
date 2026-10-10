import { DefectTicket } from "./schema";

export interface DefectExtractor {
  backend: string;
  version: string;
  extract(html: string): DefectTicket;
}

export function canonical_backend(backend: string): string {
  return (backend ?? "").trim().toLowerCase();
}

export function get_extractor(backend: string): DefectExtractor {
  const b = (backend ?? "").trim().toLowerCase();
  if (b === "bugzilla") {
    const { BugzillaExtractor } = require("./bugzilla");
    return new BugzillaExtractor();
  }
  if (b === "zentao") {
    const { ZentaoExtractor } = require("./zentao");
    return new ZentaoExtractor();
  }
  if (b === "zentao_story") {
    const { ZentaoStoryExtractor } = require("./zentao");
    return new ZentaoStoryExtractor();
  }
  throw new Error(`未知 backend: ${backend}`);
}

export { DefectTicket } from "./schema";
export type { Attachment } from "./schema";
export { BugzillaExtractor } from "./bugzilla";
export { ZentaoExtractor, ZentaoStoryExtractor } from "./zentao";
export { fold_zh_label } from "./_zh_fold";
export {
  load_selectors,
  make_soup,
  select_text,
  select_texts,
  select_attrs,
  extract_ticket_id,
  normalize_severity,
  normalize_status,
  normalize_resolution,
  parse_int,
  type Soup,
} from "./_common";
export { select_by_th_label, select_all_by_th_label } from "./zentao";
