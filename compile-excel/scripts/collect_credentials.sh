#!/usr/bin/env bash
# collect_credentials: 交互式收集跳转机/APV 凭据（read -s 不回显），直写 600 env 文件。
#
# 用途：无 secret-UI 的 harness（pi/opencode/老版 circle）里的凭据收集通道。
# circle 具备 question(secret) 能力时优先走那个；本脚本保证任何 harness 都有兜底。
# 机密值全程不进对话、不出 stdout、不落日志。
#
# 用法：collect_credentials.sh --target <env文件> [--force]
#   --target  目标 env 文件（如 ~/.config/compile-excel/env）
#   --force   目标已存在时覆盖（默认拒绝，需用户确认后显式传入）

set -euo pipefail

TARGET=""
FORCE=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) TARGET="${2:?--target 缺参数}"; shift 2 ;;
    --force) FORCE=1; shift ;;
    *) echo "未知参数: $1" >&2; exit 64 ;;
  esac
done

[[ -n "$TARGET" ]] || { echo "必须指定 --target" >&2; exit 64; }
if [[ -f "$TARGET" && "$FORCE" -ne 1 ]]; then
  echo "目标已存在: ${TARGET}（先征得用户确认并加 --force）" >&2; exit 73
fi

TARGET_DIR="$(dirname "$TARGET")"
if [[ ! -d "$TARGET_DIR" ]]; then
  mkdir -p "$TARGET_DIR"
  chmod 700 "$TARGET_DIR"
fi

TMP="$(mktemp "${TARGET}.tmp.XXXXXX")"
chmod 600 "$TMP"
trap 'rm -f "$TMP"' EXIT

collect() {  # $1=提示语 $2=键名 $3=是否掩码(1/0) $4=是否可空(1/0)
  local prompt="$1" key="$2" masked="$3" optional="$4" value=""
  while :; do
    if [[ "$masked" == "1" ]]; then
      read -r -s -p "$prompt: " value; echo
    else
      read -r -p "$prompt: " value
    fi
    if [[ -n "$value" || "$optional" == "1" ]]; then
      printf '%s=%s\n' "$key" "$value" >> "$TMP"
      echo "  已收集 $key"
      return 0
    fi
    echo "  $key 不能为空，请重输。"
  done
}

{
  echo "# compile-excel 凭据绑定（collect_credentials.sh 写入；勿提交、勿外传）"
} > "$TMP"

echo "请在终端输入以下凭据（密码类不回显，内容不会进入对话）："
collect "跳转机用户名" "JUMPHOST_USER" 0 0
collect "跳转机密码"   "JUMPHOST_PASS" 1 0
collect "APV 用户名"  "APV_USER"      0 0
collect "APV 密码"    "APV_PASSWORD"  1 0
collect "APV enable 密码（无则回车跳过）" "APV_ENABLE_PASSWORD" 1 1

if [[ -f "$TARGET" ]]; then
  KEPT="$(mktemp)"
  while IFS= read -r line || [[ -n "$line" ]]; do
    key="${line%%=*}"
    if [[ "$line" == \#* || "$line" != *=* ]] || ! grep -q "^${key}=" "$TMP"; then
      printf '%s\n' "$line" >> "$KEPT"
    fi
  done < "$TARGET"
  cat "$TMP" >> "$KEPT"
  mv "$KEPT" "$TMP"
fi
mv "$TMP" "$TARGET"
trap - EXIT
chmod 600 "$TARGET"
echo "已写入 ${TARGET}（权限 600）"
