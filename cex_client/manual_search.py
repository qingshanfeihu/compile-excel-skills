"""Search the current workspace's verified, synced product manuals."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from . import bundle
from .errors import ClientError
from .workspace import NO_DEVICE_BUILD, Workspace, safe_component

_TERM_RE = re.compile(r"[A-Za-z0-9_]+|[一-鿿]")
_MAX_QUERY_CHARS = 512
_MAX_QUERY_TERMS = 32
_CONTEXT_LINES = 2
_SNIPPET_CHARS = 600


def _fold(text: str) -> str:
    return text.lower()


def _terms(text: str) -> list[str]:
    """Use the server's word and Han-character boundaries for manual queries."""
    return list(dict.fromkeys(_TERM_RE.findall(_fold(text[:_MAX_QUERY_CHARS]))))[:_MAX_QUERY_TERMS]


def _clip(line: str, terms: list[str]) -> str:
    if len(line) <= _SNIPPET_CHARS:
        return line
    folded = _fold(line)
    first = min((pos for term in terms if (pos := folded.find(term)) >= 0), default=0)
    start = max(0, first - 100)
    end = min(len(line), start + _SNIPPET_CHARS)
    return ("…" if start else "") + line[start:end] + ("…" if end < len(line) else "")


def _search_file(path: Path, terms: list[str]) -> tuple[list[str], list[tuple[tuple[int, ...], int]]]:
    # Preserve CR and Unicode separators inside physical lines. Manual locators
    # count LF bytes, so splitlines() would mint incorrect line numbers.
    lines = path.read_bytes().decode("utf-8").split("\n")
    folded = [_fold(line) for line in lines]
    hits = [tuple(term in line for term in terms) for line in folded]
    found: list[tuple[tuple[int, ...], int]] = []
    for index, flags in enumerate(hits):
        line_hits = sum(flags)
        if not line_hits:
            continue
        lo, hi = max(0, index - _CONTEXT_LINES), min(len(lines), index + _CONTEXT_LINES + 1)
        window_hits = sum(any(row[term_index] for row in hits[lo:hi])
                          for term_index in range(len(terms)))
        occurrences = sum(folded[index].count(term) for term in terms)
        # Rank by distinct query-term coverage on the cited line, then its
        # nearby context. Repetitions only break ties in coverage.
        score = (line_hits, window_hits, occurrences)
        found.append((score, index))
    return lines, found


def query(ws: Workspace, text: str, limit: int) -> dict[str, Any]:
    terms = _terms(text)
    if not terms:
        raise ClientError("q is required")
    build = ws.selected_build
    if not build:
        # 还没选构建号：本地手册没得查（与"没有同步数据"同一分支），服务端文档照查
        return {"ok": False, "build": None, "error": NO_DEVICE_BUILD,
                "next": "Log in (cex_login_start / cex_login_wait picks the device build) or set "
                        "it with cex_init device_build, then call cex_sync."}
    with bundle.locked(ws, build, shared=True):
        manifest = bundle.cached_manifest(ws, build)
        if manifest is None:
            return {"ok": False, "build": build, "error": "no synced bundle for this build",
                    "next": "Call cex_sync to download the compile data bundle first."}
        try:
            entries = bundle._check_manifest(manifest, build)
        except ClientError as exc:
            return {"ok": False, "build": build, "bundle_id": manifest.get("bundle_id"),
                    "error": f"{exc}; call cex_sync", "next": "Call cex_sync and retry."}
        source = manifest.get("source")
        bound_version = source.get("manual_version") if isinstance(source, dict) else None
        manual_root = (f"manual/{safe_component(bound_version, 'manual_version')}/"
                       if bound_version is not None else "manual/")
        matches: list[tuple[tuple[int, ...], str, int]] = []
        sources: dict[str, list[str]] = {}
        skipped: list[dict[str, str]] = []
        searched = 0
        for entry in entries:
            rel = str(entry["path"])
            if not (rel.startswith(manual_root) and rel.endswith(".md")):
                continue
            manual_rel = rel[len("manual/"):]
            if not manual_rel:
                continue
            try:
                path = bundle.verified_file(ws, entry, build)
            except ClientError as exc:
                return {"ok": False, "build": build, "bundle_id": manifest.get("bundle_id"),
                        "error": str(exc), "next": "Call cex_sync and retry."}
            try:
                lines, found = _search_file(path, terms)
            except (UnicodeDecodeError, OSError) as exc:
                skipped.append({"path": manual_rel,
                                "reason": "invalid UTF-8" if isinstance(exc, UnicodeDecodeError)
                                else "could not read"})
                continue
            sources[manual_rel] = lines
            matches.extend((score, manual_rel, index) for score, index in found)
            searched += 1
    matches.sort(key=lambda item: (tuple(-part for part in item[0]), item[1], item[2]))
    results = []
    for score, rel, index in matches[:limit]:
        lines = sources[rel]
        lo, hi = max(0, index - _CONTEXT_LINES), min(len(lines), index + _CONTEXT_LINES + 1)
        snippet = "\n".join(f"{row + 1}: {_clip(lines[row], terms)}" for row in range(lo, hi))
        line_number = index + 1
        results.append({"path": rel, "line": line_number, "snippet": snippet,
                        "ref": f"manual:{rel}:{line_number}", "all_terms": score[1] == len(terms)})
    return {"ok": True, "query": text, "build": build,
            "bundle_id": manifest.get("bundle_id"), "bundle": str(ws.bundle_dir(build)),
            "manuals_searched": searched, "manuals_skipped": skipped, "results": results}
