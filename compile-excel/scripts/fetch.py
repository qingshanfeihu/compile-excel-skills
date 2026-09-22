#!/usr/bin/env python3
"""fetch：拉 manifest → 下载工件到缓存 → 逐件 SHA256 校验（工作流 B）。

用法：python fetch.py [--only NAME ...] [--device-build BUILD]
- 校验不符即拒（temp 不落地，缓存不被污染）；
- 服务器不可达时回退缓存并**明示**缓存版本（禁止静默）；缓存缺失/损坏则报错；
- access token 过期自动用 refresh_token 换新（输出 refreshed=true）。

缓存布局：~/.cache/compile-excel/<device_build>/<name> + manifest.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ist_client  # noqa: E402


def _fetch_from_server(device_build: str, only: list[str]) -> dict:
    manifest = ist_client.fetch_manifest(device_build)
    build = manifest.get("device_build") or device_build
    dest_dir = ist_client.CACHE_DIR / build
    entries = [a for a in manifest["artifacts"] if not only or a["name"] in only]
    missing = set(only) - {a["name"] for a in entries}
    if missing:
        raise ist_client.ClientError(f"manifest 中无这些工件: {sorted(missing)}")
    # manifest 先落缓存（回退依据）
    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    artifacts_out = []
    for entry in entries:
        path = ist_client.download_artifact_verified(
            entry["name"], entry["sha256"], dest_dir)
        artifacts_out.append({
            "name": entry["name"], "version": entry["version"],
            "sha256": entry["sha256"], "path": str(path), "status": "downloaded",
        })
    return {
        "ok": True, "source": "server", "device_build": build,
        "server": ist_client.server_url(), "artifacts": artifacts_out,
    }


def _fallback_to_cache(device_build: str, only: list[str], reason: str) -> dict:
    manifest = ist_client.cached_manifest(device_build)
    if manifest is None:
        raise ist_client.ClientError(f"服务器不可达且无缓存可回退（{reason}）")
    build = manifest.get("device_build") or device_build
    entries = [a for a in manifest.get("artifacts", []) if not only or a["name"] in only]
    artifacts_out = []
    for entry in entries:
        path = ist_client.verify_cached_artifact(entry, build)
        artifacts_out.append({
            "name": entry["name"], "version": entry["version"],
            "sha256": entry["sha256"], "path": str(path), "status": "cache-hit",
        })
    return {
        "ok": True, "source": "cache", "device_build": build,
        "note": (f"服务器不可达（{reason}），回退缓存版本："
                 f"manifest 生成于 {manifest.get('generated_at', '未知时间')}，"
                 f"工件版本 {sorted({a['version'] for a in entries})}——"
                 "非服务器当前版本，禁止静默当作最新"),
        "artifacts": artifacts_out,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="compile-excel 工件拉取")
    parser.add_argument("--only", action="append", default=[],
                        help="只拉指定工件（可重复）；缺省拉全部")
    parser.add_argument("--device-build", default="")
    args = parser.parse_args()

    try:
        try:
            result = _fetch_from_server(args.device_build, args.only)
        except ConnectionError as exc:
            result = _fallback_to_cache(args.device_build, args.only, str(exc))
        # 401 自动刷新在 authed_request 内完成；这里补充报告
        token = ist_client.load_token()
        if token:
            result["token_expires_at"] = token.get("expires_at")
    except ist_client.ClientError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
