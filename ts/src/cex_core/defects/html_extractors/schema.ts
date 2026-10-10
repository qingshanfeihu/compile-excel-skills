export interface Attachment {
  url: string;
  filename: string;
}

export interface DefectTicketData {
  ticket_id: string;
  invalid_reason: string;
  title: string;
  module: string;
  product: string;
  severity: string;
  priority: string;
  status: string;
  resolution: string;
  description: string;
  steps_to_reproduce: string;
  fix_summary: string;
  reported_by: string;
  reported_at: string;
  resolved_by: string;
  resolved_at: string;
  affected_versions: string[];
  fixed_versions: string[];
  fixed_commit: string;
  related_feature_ids: string[];
  related_case_ids: string[];
  related_story_ids: string[];
  related_task_ids: string[];
  related_bug_ids: string[];
  activated_count: number;
  comments_count: number;
  attachments: Attachment[];
  backend: string;
  doc_type: string;
  source_html_path: string;
  html_sha256: string;
  captured_at: string;
}

export class DefectTicket {
  ticket_id: string;
  invalid_reason = "";
  title = "";
  module = "";
  product = "";
  severity = "low";
  priority = "";
  status = "open";
  resolution = "";
  description = "";
  steps_to_reproduce = "";
  fix_summary = "";
  reported_by = "";
  reported_at = "";
  resolved_by = "";
  resolved_at = "";
  affected_versions: string[] = [];
  fixed_versions: string[] = [];
  fixed_commit = "";
  related_feature_ids: string[] = [];
  related_case_ids: string[] = [];
  related_story_ids: string[] = [];
  related_task_ids: string[] = [];
  related_bug_ids: string[] = [];
  activated_count = 0;
  comments_count = 0;
  attachments: Attachment[] = [];
  backend = "";
  doc_type = "bug";
  source_html_path = "";
  html_sha256 = "";
  captured_at = "";

  constructor(init: Partial<DefectTicketData> & { ticket_id: string }) {
    this.ticket_id = init.ticket_id;
    for (const [key, value] of Object.entries(init)) {
      (this as any)[key] = value;
    }
  }

  is_valid_detail(): boolean {
    if (this.invalid_reason) {
      return false;
    }
    const tid = (this.ticket_id || "").trim().toUpperCase();
    if (!tid || tid === "UNKNOWN") {
      return false;
    }
    if (!(this.title || "").trim() && !(this.description || "").trim()) {
      return false;
    }
    return true;
  }

  identity_metadata_complete(): boolean {
    return Boolean((this.product || "").trim()) && Boolean((this.status || "").trim());
  }

  to_index_dict(): Record<string, any> {
    const pcParts = [
      `[${this.ticket_id}][${this.module}][Sev=${this.severity}]` +
        `${this.priority ? "[Pri=" + this.priority + "]" : ""}` +
        ` ${this.title}`,
    ];
    if (this.product && this.product !== this.module) {
      pcParts.push(`产品: ${this.product}`);
    }
    if (this.description) {
      pcParts.push(this.description);
    }
    if (this.steps_to_reproduce) {
      pcParts.push("复现:\n" + this.steps_to_reproduce);
    }
    if (this.fix_summary) {
      pcParts.push("修复: " + this.fix_summary);
    }
    if (this.resolution) {
      pcParts.push(`解决方案类型: ${this.resolution}`);
    }
    const timelineParts: string[] = [];
    if (this.reported_by || this.reported_at) {
      timelineParts.push(`由 ${this.reported_by} 提交于 ${this.reported_at}`.trim());
    }
    if (this.resolved_by || this.resolved_at) {
      timelineParts.push(`由 ${this.resolved_by} 解决于 ${this.resolved_at}`.trim());
    }
    if (timelineParts.length) {
      pcParts.push(timelineParts.filter((p) => p).join(" / "));
    }
    const relationParts: string[] = [];
    if (this.related_case_ids.length) {
      relationParts.push(`相关用例: ${this.related_case_ids.join(", ")}`);
    }
    if (this.related_story_ids.length) {
      relationParts.push(`相关需求: ${this.related_story_ids.join(", ")}`);
    }
    if (this.related_task_ids.length) {
      relationParts.push(`相关任务: ${this.related_task_ids.join(", ")}`);
    }
    if (this.related_bug_ids.length) {
      relationParts.push(`相关 Bug: ${this.related_bug_ids.join(", ")}`);
    }
    if (relationParts.length) {
      pcParts.push(relationParts.join("\n"));
    }
    const pageContent = pcParts.filter((p) => p).join("\n\n");

    return {
      ticket_id: this.ticket_id,
      page_content: pageContent,
      title: this.title,
      description: this.description,
      steps_to_reproduce: this.steps_to_reproduce,
      fix_summary: this.fix_summary,
      metadata: {
        doc_type: this.doc_type,
        module: this.module,
        product: this.product,
        severity: this.severity,
        priority: this.priority,
        status: this.status,
        resolution: this.resolution,
        reported_by: this.reported_by,
        reported_at: this.reported_at,
        resolved_by: this.resolved_by,
        resolved_at: this.resolved_at,
        affected_versions: this.affected_versions,
        fixed_versions: this.fixed_versions,
        fixed_commit: this.fixed_commit,
        related_feature_ids: this.related_feature_ids,
        related_case_ids: this.related_case_ids,
        related_story_ids: this.related_story_ids,
        related_task_ids: this.related_task_ids,
        related_bug_ids: this.related_bug_ids,
        activated_count: this.activated_count,
        comments_count: this.comments_count,
        backend: this.backend,
        source_html_path: this.source_html_path,
        html_sha256: this.html_sha256,
        captured_at: this.captured_at,
      },
    };
  }

  to_dict(): DefectTicketData {
    return {
      ticket_id: this.ticket_id,
      invalid_reason: this.invalid_reason,
      title: this.title,
      module: this.module,
      product: this.product,
      severity: this.severity,
      priority: this.priority,
      status: this.status,
      resolution: this.resolution,
      description: this.description,
      steps_to_reproduce: this.steps_to_reproduce,
      fix_summary: this.fix_summary,
      reported_by: this.reported_by,
      reported_at: this.reported_at,
      resolved_by: this.resolved_by,
      resolved_at: this.resolved_at,
      affected_versions: [...this.affected_versions],
      fixed_versions: [...this.fixed_versions],
      fixed_commit: this.fixed_commit,
      related_feature_ids: [...this.related_feature_ids],
      related_case_ids: [...this.related_case_ids],
      related_story_ids: [...this.related_story_ids],
      related_task_ids: [...this.related_task_ids],
      related_bug_ids: [...this.related_bug_ids],
      activated_count: this.activated_count,
      comments_count: this.comments_count,
      attachments: this.attachments.map((a) => ({ ...a })),
      backend: this.backend,
      doc_type: this.doc_type,
      source_html_path: this.source_html_path,
      html_sha256: this.html_sha256,
      captured_at: this.captured_at,
    };
  }
}
