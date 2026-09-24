#!/usr/bin/env bash
# bind_env: 非交互写入 compile-excel 环境绑定文件（Setup 向导调用，不做终端交互）
#
# 用法：bind_env.sh --target <路径> [--force] KEY=VALUE [KEY=VALUE ...]
#   --target  目标文件（如 ~/.config/compile-excel/env 或 <workspace>/.circle/compile-excel.env）
#   --force   目标已存在时覆盖（默认拒绝，需用户确认后由 agent 显式传入）
#
# 安全约定：目录 700 / 文件 600；原子写盘（tmp + mv）；键名限大写字母/数字/下划线；
# 机密项（含 KEY/TOKEN/SECRET/PASSWORD 的键）拒绝从命令行接收——引导用户人工填写。

set -euo pipefail

TARGET=""
FORCE=0
PAIRS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) TARGET="${2:?--target 缺参数}"; shift 2 ;;
    --force) FORCE=1; shift ;;
    *=*) PAIRS+=("$1"); shift ;;
    *) echo "未知参数: $1" >&2; exit 64 ;;
  esac
done

[[ -n "$TARGET" ]] || { echo "必须指定 --target" >&2; exit 64; }
[[ ${#PAIRS[@]} -gt 0 ]] || { echo "至少需要一个 KEY=VALUE" >&2; exit 64; }

if [[ -f "$TARGET" && "$FORCE" -ne 1 ]]; then
  echo "目标已存在: $TARGET（重复运行请先征得用户确认并加 --force）" >&2
  exit 73
fi

for pair in "${PAIRS[@]}"; do
  key="${pair%%=*}"
  if [[ ! "$key" =~ ^[A-Z][A-Z0-9_]*$ ]]; then
    echo "非法键名: $key（仅限大写字母/数字/下划线）" >&2; exit 65
  fi
  if [[ "$key" =~ (KEY|TOKEN|SECRET|PASSWORD) ]]; then
    echo "机密键 $key 拒绝经命令行传输，请用户按 .env.example 人工填写" >&2; exit 65
  fi
done

TARGET_DIR="$(dirname "$TARGET")"
mkdir -p "$TARGET_DIR"
[[ "$TARGET_DIR" != "." ]] && chmod 700 "$TARGET_DIR"

TMP="$(mktemp "${TARGET}.tmp.XXXXXX")"

# 写入新文件：更新传入的键，保留未提及的键（bash 3.2 兼容）
{
  echo "# compile-excel 环境绑定（由 bind_env.sh 写入；机密项请人工追加）"
  
  # 先输出新增/更新的键值对
  for pair in "${PAIRS[@]}"; do
    echo "$pair"
  done
  
  # 如果目标文件存在且使用 --force，追加未被更新的原有键
  if [[ -f "$TARGET" && "$FORCE" -eq 1 ]]; then
    while IFS= read -r line; do
      # 跳过注释和空行
      [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
      # 提取键名
      key="${line%%=*}"
      [[ -z "$key" ]] && continue
      # 检查这个键是否在新传入的 PAIRS 中
      found=0
      for pair in "${PAIRS[@]}"; do
        if [[ "${pair%%=*}" == "$key" ]]; then
          found=1
          break
        fi
      done
      # 未被更新的键保留
      [[ "$found" -eq 0 ]] && echo "$line"
    done < "$TARGET"
  fi
} > "$TMP"
chmod 600 "$TMP"
mv "$TMP" "$TARGET"

echo "已写入 $TARGET"
