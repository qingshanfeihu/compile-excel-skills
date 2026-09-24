"""找到 compile-excel 的发行根（含 cex_core/ 与 cex_client/）并加进 sys.path。

skill 目录可能被整份拷贝进 harness 的 skills 目录，离开了仓库。按下面的顺序找发行根：
1. 环境变量 CEX_HOME；
2. skill 目录下的 `.cex_home` 文件（安装器写入，一行绝对路径）；
3. 从本文件真实路径往上找（开发检出、Claude Code 插件根）；
4. `~/.local/share/compile-excel/current`（安装器的默认落位）。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_SKILL_DIR = Path(__file__).resolve().parents[1]


def _is_home(path: Path) -> bool:
    return (path / "cex_core" / "__init__.py").is_file()


def cex_home() -> Path | None:
    candidates: list[Path] = []
    if os.environ.get("CEX_HOME"):
        candidates.append(Path(os.environ["CEX_HOME"]).expanduser())
    marker = _SKILL_DIR / ".cex_home"
    if marker.is_file():
        text = marker.read_text(encoding="utf-8").strip()
        if text:
            candidates.append(Path(text).expanduser())
    candidates.extend(Path(__file__).resolve().parents)
    candidates.append(Path.home() / ".local" / "share" / "compile-excel" / "current")
    for candidate in candidates:
        if _is_home(candidate):
            return candidate.resolve()
    return None


def ensure() -> Path:
    home = cex_home()
    if home is None:
        raise SystemExit(
            "找不到 compile-excel 发行根（cex_core/）。重新运行安装器，"
            "或把 CEX_HOME 设为 compile-excel-skills 仓的检出目录。")
    if str(home) not in sys.path:
        sys.path.insert(0, str(home))
    return home


HOME = ensure()
