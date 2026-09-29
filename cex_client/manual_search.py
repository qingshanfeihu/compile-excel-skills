"""Search the current workspace's verified, synced product manuals."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import bundle
from .errors import ClientError
from .workspace import Workspace

_ASCII_LOWER = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")
_CONTEXT_LINES = 2
_SNIPPET_CHARS = 600


def _fold(text: str) -> str:
    """Fold ASCII without changing Chinese or other manual text."""
    return text.translate(_ASCII_LOWER)


def _clip(line: str, terms: list[str]) -> str:
    if len(line) <= _SNIPPET_CHARS:
        return line
    folded = _fold(line)
    first = min((pos for term in terms if (pos := folded.find(term)) >= 0), default=0)
    start = max(0, first - 100)
    end = min(len(line), start + _SNIPPET_CHARS)
    return ("…" if start else "") + line[start:end] + ("…" if end < len(line) else "")


def _search_file(path: Path, terms: list[str]) -> tuple[list[str], list[tuple[tuple[int, ...], int]]]:
    lines = path.read_text(encoding="utf-8").splitlines()
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
        # All terms on one line outrank scattered terms; nearby context outranks
        # an isolated partial hit. Stable path/line ordering breaks equal scores.
        score = (int(line_hits == len(terms)), int(window_hits == len(terms)),
                 line_hits, occurrences)
        found.append((score, index))
    return lines, found


def query(ws: Workspace, text: str, limit: int) -> dict[str, Any]:
    terms = list(dict.fromkeys(_fold(part) for part in text.split()))
    if not terms:
        raise ClientError("q is required")
    build = ws.device_build
    with bundle.locked(ws, build, shared=True):
        manifest = bundle.cached_manifest(ws, build)
        if manifest is None:
            return {"ok": False, "build": build, "error": "no synced bundle for this build",
                    "next": "Call cex_sync to download the compile data bundle first."}
        if manifest.get("build") != build:
            raise ClientError(f"cached bundle build does not match {build}; call cex_sync")
        try:
            bundle.verify_cache(ws, build)
        except ClientError as exc:
            return {"ok": False, "build": build, "bundle_id": manifest.get("bundle_id"),
                    "error": f"{exc}; call cex_sync", "next": "Call cex_sync and retry."}
        matches: list[tuple[tuple[int, ...], str, int]] = []
        sources: dict[str, list[str]] = {}
        searched = 0
        for entry in manifest["entries"]:
            rel = str(entry["path"])
            if not (rel.startswith("manual/") and rel.endswith(".md")):
                continue
            manual_rel = rel[len("manual/"):]
            if not manual_rel:
                continue
            # verify_cache checked every manifest path and SHA under this shared
            # lock; avoid hashing each manual a second time before reading it.
            lines, found = _search_file(ws.bundle_dir(build) / rel, terms)
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
                        "ref": f"manual:{rel}:{line_number}", "all_terms": bool(score[1])})
    return {"ok": True, "query": text, "build": build,
            "bundle_id": manifest.get("bundle_id"), "bundle": str(ws.bundle_dir(build)),
            "manuals_searched": searched, "results": results}
