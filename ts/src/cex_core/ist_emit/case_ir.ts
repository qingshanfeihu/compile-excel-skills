export interface Row {
  test_object: string;
  method: string;
  data: string;
  save_as?: string | null;
  input_var?: string | null;
  provenance?: string | null;
}

export interface Step {
  stmt_type: number;
  description: string;
  rows?: Row[];
}

export interface CaseIR {
  autoid: string;
  priority?: string;
  title?: string;
  steps?: Step[];
  source_module?: string;
  source_text?: string;
  expected?: string[];
  confidence?: number;
  notes?: string[];
  is_passthrough?: boolean;
}

export interface FileIR {
  feature: string;
  author?: string;
  init_rows?: Row[];
  cases?: CaseIR[];
  module?: string;
  rejected?: Record<string, unknown>[];
  questions?: Record<string, unknown>[];
}

export function make_Row(init: Partial<Row> = {}): Row {
  return {
    test_object: init.test_object ?? "",
    method: init.method ?? "",
    data: init.data ?? "",
    save_as: init.save_as ?? null,
    input_var: init.input_var ?? null,
    provenance: init.provenance ?? null,
  };
}

export function make_Step(init: Partial<Step> = {}): Step {
  return {
    stmt_type: init.stmt_type ?? 0,
    description: init.description ?? "",
    rows: init.rows ?? [],
  };
}

export function make_CaseIR(init: Partial<CaseIR> = {}): CaseIR {
  return {
    autoid: init.autoid ?? "",
    priority: init.priority ?? "P1",
    title: init.title ?? "",
    steps: init.steps ?? [],
    source_module: init.source_module ?? "",
    source_text: init.source_text ?? "",
    expected: init.expected ?? [],
    confidence: init.confidence ?? 0.0,
    notes: init.notes ?? [],
    is_passthrough: init.is_passthrough ?? false,
  };
}

export function make_FileIR(init: Partial<FileIR> = {}): FileIR {
  return {
    feature: init.feature ?? "",
    author: init.author ?? "IST-Core",
    init_rows: init.init_rows ?? [],
    cases: init.cases ?? [],
    module: init.module ?? "",
    rejected: init.rejected ?? [],
    questions: init.questions ?? [],
  };
}

export function is_check_point(row: Row): boolean {
  return row.test_object === "check_point";
}

export function check_point_count(caseIr: CaseIR): number {
  let n = 0;
  for (const st of caseIr.steps ?? []) {
    for (const r of st.rows ?? []) {
      if (is_check_point(r)) n += 1;
    }
  }
  return n;
}
