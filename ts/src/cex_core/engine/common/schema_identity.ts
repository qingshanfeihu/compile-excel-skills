const _LEGACY_SUFFIX_RE = /^(.+)\.v\d+$/;

export function canonical_schema(name: any): string {
  if (typeof name !== "string" || !name) {
    return String(name ?? "");
  }
  const match = _LEGACY_SUFFIX_RE.exec(name.trim());
  if (match) {
    return match[1];
  }
  return name.trim();
}

export function accepts_schema(actual: any, expected: any): boolean {
  if (typeof actual !== "string" || !actual.trim()) {
    return false;
  }
  if (typeof expected !== "string" || !expected.trim()) {
    return false;
  }
  return canonical_schema(actual) === canonical_schema(expected);
}

export function write_schema(expected: string): string {
  return canonical_schema(expected);
}

function _pyRepr(value: any): string {
  return JSON.stringify(String(value));
}

export function reject_unless_schema(payload: Record<string, any>, expected: string, field = "schema"): void {
  const actual = payload[field];
  if (!accepts_schema(actual, expected)) {
    throw new Error(`unsupported schema: expected ${_pyRepr(write_schema(expected))}, got ${_pyRepr(actual)}`);
  }
}
