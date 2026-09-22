#!/usr/bin/env python3
"""docs_query：检索服务器端手册片段（工作流 B）。

用法：python docs_query.py --q "check_point found_times" [--limit 3]
需先 login；token 过期自动 refresh。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ist_client  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="compile-excel 文档检索")
    parser.add_argument("--q", required=True, help="检索关键词")
    parser.add_argument("--limit", type=int, default=3, help="返回条数上限（1-10）")
    args = parser.parse_args()

    try:
        result = ist_client.docs_query(args.q, args.limit)
    except (ist_client.ClientError, ConnectionError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1

    result["ok"] = True
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
