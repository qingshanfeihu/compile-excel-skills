const _LEGACY_SUFFIX_RE = /^(.+)\.v\d+$/;

function _repr(value: unknown): string {
  if (typeof value === "string") {
    return `'${value.replace(/\\/g, "\\\\").replace(/'/g, "\\'")}'`;
  }
  return String(value);
}

export function canonical_schema(name: unknown): string {
  if (typeof name !== "string" || !name) {
    return String(name ?? "");
  }
  const match = _LEGACY_SUFFIX_RE.exec(name.trim());
  if (match) {
    return match[1];
  }
  return name.trim();
}

export function accepts_schema(actual: unknown, expected: unknown): boolean {
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

export function reject_unless_schema(
  payload: Record<string, unknown>,
  expected: string,
  field = "schema",
): void {
  const actual = payload[field];
  if (!accepts_schema(actual, expected)) {
    throw new Error(
      `unsupported schema: expected ${_repr(write_schema(expected))}, got ${_repr(actual)}`,
    );
  }
}
