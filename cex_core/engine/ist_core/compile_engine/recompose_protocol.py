# 生成：tools/extract_engine.py ← InfoTest main/ist_core/compile_engine/recompose_protocol.py（sha256 440287fdef464a5e）。不在这里手改。
from __future__ import annotations
import json
from typing import Any, Literal, Self
from pydantic import BaseModel, ConfigDict, Field, model_validator
from cex_core.engine.common.nullable_scalar import restore_endpoint_encodings
SCHEMA = 'ist.mindmap-recompose-result'
_MAX_BYTES = 64 * 1024

class MindmapRecomposeBucketCounts(BaseModel):
    """Closed machine-readable bucket counts for one recompose attempt."""
    model_config = ConfigDict(extra='forbid', strict=True)
    exp_recipe: int = Field(ge=0, description='Cases with a complete expectation recipe.')
    step_recipe: int = Field(ge=0, description='Cases with a step-level recipe.')
    true_gap: int = Field(ge=0, description='Cases with an unresolved source gap.')

class MindmapRecomposeSummary(BaseModel):
    """Closed user-facing and machine-readable recompose summary."""
    model_config = ConfigDict(extra='forbid', strict=True)
    case_count: int = Field(ge=0, description='Total number of identity-bound cases.')
    bucket_counts: MindmapRecomposeBucketCounts = Field(description='Exact closed bucket counts for the identity-bound cases.')
    message_zh: str = Field(min_length=1, max_length=16384, description='Scrubbed Chinese user-facing summary.')

    @model_validator(mode='after')
    def validate_bucket_total(self) -> Self:
        counted = self.bucket_counts.exp_recipe + self.bucket_counts.step_recipe + self.bucket_counts.true_gap
        if counted != self.case_count:
            raise ValueError('bucket counts must sum to case_count')
        return self

class MindmapRecomposeResult(BaseModel):
    """Final response model passed to ``create_agent(response_format=...)``."""
    model_config = ConfigDict(extra='forbid', strict=True, populate_by_name=False)
    schema_: Literal['ist.mindmap-recompose-result'] = Field(alias='schema', serialization_alias='schema', description='Versioned mindmap recompose result schema.')
    status: Literal['produced', 'failed'] = Field(description='Closed terminal status for the recompose attempt — exactly produced or failed. A source gap is a true_gap bucket / scenario2 record inside the machine mindmap, never an envelope status.')
    artifact: str | None = Field(description='Written machine_mindmap.json path for produced only; otherwise null.')
    summary: MindmapRecomposeSummary | None = Field(description='Machine-readable counts plus the Chinese user-facing summary; null on failure.')
    error_code: str | None = Field(description='A stable non-empty code for failed only; otherwise null.')
    reason_zh: str | None = Field(description='A scrubbed Chinese failure reason for failed only; otherwise null.')

    @model_validator(mode='before')
    @classmethod
    def restore_nullish_scalars(cls, data: Any) -> Any:
        schema = cls.model_json_schema()
        return restore_endpoint_encodings(data, schema)

    @model_validator(mode='after')
    def validate_terminal_shape(self) -> Self:
        if self.status == 'produced':
            if not isinstance(self.artifact, str) or not self.artifact.strip():
                raise ValueError('produced result requires an artifact path')
            if self.summary is None or self.error_code is not None or self.reason_zh is not None:
                raise ValueError('produced result fields are inconsistent')
        elif self.artifact is not None or self.summary is not None or (not isinstance(self.error_code, str)) or (not self.error_code.strip()) or (not isinstance(self.reason_zh, str)) or (not self.reason_zh.strip()):
            raise ValueError('failed result fields are inconsistent')
        if isinstance(self.artifact, str):
            self.artifact = self.artifact.strip()
        return self

def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate JSON key: {key}')
        result[key] = value
    return result

def _reject_constant(value: str) -> None:
    raise ValueError(f'non-finite JSON constant: {value}')

def parse_mindmap_recompose_result(raw: str) -> dict[str, Any]:
    if not isinstance(raw, str):
        raise ValueError('mindmap recompose result must be text')
    if not raw.strip() or len(raw.encode('utf-8')) > _MAX_BYTES:
        raise ValueError('mindmap recompose result is empty or exceeds its byte budget')
    try:
        payload = json.loads(raw, object_pairs_hook=_reject_duplicate_keys, parse_constant=_reject_constant)
        result = MindmapRecomposeResult.model_validate(payload, strict=True)
    except (TypeError, ValueError, RecursionError) as exc:
        raise ValueError('invalid mindmap recompose structured response') from exc
    return result.model_dump(mode='json', by_alias=True)

def render_mindmap_recompose_result(payload: dict[str, Any]) -> str:
    result = MindmapRecomposeResult.model_validate(payload, strict=True)
    return json.dumps(result.model_dump(mode='json', by_alias=True), ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)

def invalid_mindmap_recompose_result(failure_note: str='') -> str:
    note = str(failure_note or '').strip()[:200]
    return render_mindmap_recompose_result({'schema': SCHEMA, 'status': 'failed', 'artifact': None, 'summary': None, 'error_code': 'invalid_structured_response', 'reason_zh': '重组结果未通过 LangChain 结构化返回校验' + (f'；{note}' if note else '')})
__all__ = ['MindmapRecomposeBucketCounts', 'MindmapRecomposeResult', 'MindmapRecomposeSummary', 'SCHEMA', 'invalid_mindmap_recompose_result', 'parse_mindmap_recompose_result', 'render_mindmap_recompose_result']
