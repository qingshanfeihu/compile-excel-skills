# 生成：tools/extract_engine.py ← InfoTest main/common/nullable_scalar.py（sha256 250d3b696ab79d56）。不在这里手改。
from __future__ import annotations
from typing import Any
NULLISH_TOKENS = frozenset({'', 'none', 'null', 'nil', 'n/a', 'undefined', '/dev/null'})
_SCALAR_TYPES = frozenset({'string', 'integer', 'number', 'boolean'})

def nullable_scalar_type(prop: Any) -> str | None:
    if not isinstance(prop, dict):
        return None
    branches = prop.get('anyOf')
    if not isinstance(branches, list) or len(branches) != 2:
        return None
    if not all((isinstance(b, dict) for b in branches)):
        return None
    if sum((1 for b in branches if b.get('type') == 'null')) != 1:
        return None
    other = next((b for b in branches if b.get('type') != 'null'))
    if set(other) - {'type'}:
        return None
    kind = other.get('type')
    return kind if kind in _SCALAR_TYPES else None

def strip_nullable_scalars(schema: Any) -> int:
    if not isinstance(schema, dict):
        return 0
    changed = 0
    for container in ('properties', '$defs'):
        node = schema.get(container)
        if not isinstance(node, dict):
            continue
        for key, prop in node.items():
            kind = nullable_scalar_type(prop)
            if kind is not None:
                rest = {k: v for k, v in prop.items() if k != 'anyOf'}
                node[key] = {'type': kind, **rest}
                changed += 1
                continue
            changed += strip_nullable_scalars(prop)
    items = schema.get('items')
    if isinstance(items, dict):
        changed += strip_nullable_scalars(items)
    return changed

def nullable_scalar_keys(json_schema: Any) -> frozenset[str]:
    if not isinstance(json_schema, dict):
        return frozenset()
    props = json_schema.get('properties')
    if not isinstance(props, dict):
        return frozenset()
    return frozenset((key for key, prop in props.items() if nullable_scalar_type(prop) is not None))

def is_nullish(value: Any) -> bool:
    return isinstance(value, str) and value.strip().lower() in NULLISH_TOKENS

def restore_nullish(data: Any, json_schema: Any) -> Any:
    if not isinstance(data, dict):
        return data
    keys = nullable_scalar_keys(json_schema)
    if not keys:
        return data
    hits = [k for k in keys if k in data and is_nullish(data[k])]
    if not hits:
        return data
    out = dict(data)
    for key in hits:
        out[key] = None
    return out

def _object_like(prop: Any) -> bool:
    if not isinstance(prop, dict):
        return False
    if '$ref' in prop or prop.get('type') == 'object':
        return True
    branches = prop.get('anyOf')
    if isinstance(branches, list):
        return any((_object_like(branch) for branch in branches if isinstance(branch, dict) and branch.get('type') != 'null'))
    return False

def json_object_keys(json_schema: Any) -> frozenset[str]:
    props = (json_schema or {}).get('properties')
    if not isinstance(props, dict):
        return frozenset()
    return frozenset((key for key, prop in props.items() if _object_like(prop)))

def restore_json_objects(data: Any, json_schema: Any) -> Any:
    import json as _json
    if not isinstance(data, dict):
        return data
    keys = json_object_keys(json_schema)
    if not keys:
        return data
    out: dict[str, Any] | None = None
    for key in keys:
        value = data.get(key)
        if not isinstance(value, str):
            continue
        text = value.strip()
        if not (text.startswith('{') and text.endswith('}')):
            continue
        try:
            parsed = _json.loads(text)
        except (ValueError, TypeError, RecursionError):
            continue
        if not isinstance(parsed, dict):
            continue
        if out is None:
            out = dict(data)
        out[key] = parsed
    return out if out is not None else data

def _array_like(prop: Any) -> bool:
    if not isinstance(prop, dict):
        return False
    if prop.get('type') == 'array':
        return True
    branches = prop.get('anyOf')
    if isinstance(branches, list):
        return any((_array_like(branch) for branch in branches if isinstance(branch, dict) and branch.get('type') != 'null'))
    return False

def json_array_keys(json_schema: Any) -> frozenset[str]:
    props = (json_schema or {}).get('properties')
    if not isinstance(props, dict):
        return frozenset()
    return frozenset((key for key, prop in props.items() if _array_like(prop)))

def restore_json_arrays(data: Any, json_schema: Any) -> Any:
    import json as _json
    if not isinstance(data, dict):
        return data
    keys = json_array_keys(json_schema)
    if not keys:
        return data
    out: dict[str, Any] | None = None
    for key in keys:
        value = data.get(key)
        if not isinstance(value, str):
            continue
        text = value.strip()
        if not (text.startswith('[') and text.endswith(']')):
            continue
        try:
            parsed = _json.loads(text)
        except (ValueError, TypeError, RecursionError):
            continue
        if not isinstance(parsed, list):
            continue
        if out is None:
            out = dict(data)
        out[key] = parsed
    return out if out is not None else data

def restore_endpoint_encodings(data: Any, json_schema: Any) -> Any:
    return restore_json_arrays(restore_json_objects(restore_nullish(data, json_schema), json_schema), json_schema)
