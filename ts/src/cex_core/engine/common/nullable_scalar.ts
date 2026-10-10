const NULLISH_TOKENS = new Set(["", "none", "null", "nil", "n/a", "undefined", "/dev/null"]);
const _SCALAR_TYPES = new Set(["string", "integer", "number", "boolean"]);

export function nullable_scalar_type(prop: any): string | null {
  if (typeof prop !== "object" || prop === null || Array.isArray(prop)) {
    return null;
  }
  const branches = prop.anyOf;
  if (!Array.isArray(branches) || branches.length !== 2) {
    return null;
  }
  if (!branches.every((b) => typeof b === "object" && b !== null && !Array.isArray(b))) {
    return null;
  }
  if (branches.filter((b) => b.type === "null").length !== 1) {
    return null;
  }
  const other = branches.find((b) => b.type !== "null");
  if (Object.keys(other).filter((k) => k !== "type").length > 0) {
    return null;
  }
  const kind = other.type;
  return _SCALAR_TYPES.has(kind) ? kind : null;
}

export function strip_nullable_scalars(schema: any): number {
  if (typeof schema !== "object" || schema === null || Array.isArray(schema)) {
    return 0;
  }
  let changed = 0;
  for (const container of ["properties", "$defs"]) {
    const node = schema[container];
    if (typeof node !== "object" || node === null || Array.isArray(node)) {
      continue;
    }
    for (const key of Object.keys(node)) {
      const prop = node[key];
      const kind = nullable_scalar_type(prop);
      if (kind !== null) {
        const rest: any = {};
        for (const k of Object.keys(prop)) {
          if (k !== "anyOf") rest[k] = prop[k];
        }
        node[key] = { type: kind, ...rest };
        changed += 1;
        continue;
      }
      changed += strip_nullable_scalars(prop);
    }
  }
  const items = schema.items;
  if (typeof items === "object" && items !== null && !Array.isArray(items)) {
    changed += strip_nullable_scalars(items);
  }
  return changed;
}

export function nullable_scalar_keys(json_schema: any): Set<string> {
  if (typeof json_schema !== "object" || json_schema === null || Array.isArray(json_schema)) {
    return new Set();
  }
  const props = json_schema.properties;
  if (typeof props !== "object" || props === null || Array.isArray(props)) {
    return new Set();
  }
  const out = new Set<string>();
  for (const key of Object.keys(props)) {
    if (nullable_scalar_type(props[key]) !== null) {
      out.add(key);
    }
  }
  return out;
}

export function is_nullish(value: any): boolean {
  return typeof value === "string" && NULLISH_TOKENS.has(value.trim().toLowerCase());
}

export function restore_nullish(data: any, json_schema: any): any {
  if (typeof data !== "object" || data === null || Array.isArray(data)) {
    return data;
  }
  const keys = nullable_scalar_keys(json_schema);
  if (keys.size === 0) {
    return data;
  }
  const hits = Array.from(keys).filter((k) => k in data && is_nullish(data[k]));
  if (hits.length === 0) {
    return data;
  }
  const out: any = { ...data };
  for (const key of hits) {
    out[key] = null;
  }
  return out;
}

function _objectLike(prop: any): boolean {
  if (typeof prop !== "object" || prop === null || Array.isArray(prop)) {
    return false;
  }
  if ("$ref" in prop || prop.type === "object") {
    return true;
  }
  const branches = prop.anyOf;
  if (Array.isArray(branches)) {
    return branches.some(
      (branch) =>
        typeof branch === "object" && branch !== null && !Array.isArray(branch) && branch.type !== "null" && _objectLike(branch)
    );
  }
  return false;
}

export function json_object_keys(json_schema: any): Set<string> {
  const props = (json_schema || {}).properties;
  if (typeof props !== "object" || props === null || Array.isArray(props)) {
    return new Set();
  }
  const out = new Set<string>();
  for (const key of Object.keys(props)) {
    if (_objectLike(props[key])) out.add(key);
  }
  return out;
}

export function restore_json_objects(data: any, json_schema: any): any {
  if (typeof data !== "object" || data === null || Array.isArray(data)) {
    return data;
  }
  const keys = json_object_keys(json_schema);
  if (keys.size === 0) {
    return data;
  }
  let out: any = null;
  for (const key of keys) {
    const value = data[key];
    if (typeof value !== "string") continue;
    const text = value.trim();
    if (!(text.startsWith("{") && text.endsWith("}"))) continue;
    let parsed: any;
    try {
      parsed = JSON.parse(text);
    } catch {
      continue;
    }
    if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) continue;
    if (out === null) out = { ...data };
    out[key] = parsed;
  }
  return out !== null ? out : data;
}

function _arrayLike(prop: any): boolean {
  if (typeof prop !== "object" || prop === null || Array.isArray(prop)) {
    return false;
  }
  if (prop.type === "array") {
    return true;
  }
  const branches = prop.anyOf;
  if (Array.isArray(branches)) {
    return branches.some(
      (branch) =>
        typeof branch === "object" && branch !== null && !Array.isArray(branch) && branch.type !== "null" && _arrayLike(branch)
    );
  }
  return false;
}

export function json_array_keys(json_schema: any): Set<string> {
  const props = (json_schema || {}).properties;
  if (typeof props !== "object" || props === null || Array.isArray(props)) {
    return new Set();
  }
  const out = new Set<string>();
  for (const key of Object.keys(props)) {
    if (_arrayLike(props[key])) out.add(key);
  }
  return out;
}

export function restore_json_arrays(data: any, json_schema: any): any {
  if (typeof data !== "object" || data === null || Array.isArray(data)) {
    return data;
  }
  const keys = json_array_keys(json_schema);
  if (keys.size === 0) {
    return data;
  }
  let out: any = null;
  for (const key of keys) {
    const value = data[key];
    if (typeof value !== "string") continue;
    const text = value.trim();
    if (!(text.startsWith("[") && text.endsWith("]"))) continue;
    let parsed: any;
    try {
      parsed = JSON.parse(text);
    } catch {
      continue;
    }
    if (!Array.isArray(parsed)) continue;
    if (out === null) out = { ...data };
    out[key] = parsed;
  }
  return out !== null ? out : data;
}

export function restore_endpoint_encodings(data: any, json_schema: any): any {
  return restore_json_arrays(restore_json_objects(restore_nullish(data, json_schema), json_schema), json_schema);
}
