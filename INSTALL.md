# INSTALL — compile-excel skill（给 agent 看的安装指令）

> 人话版：把下面这句 prompt 发给你的 agent（circle / pi / opencode / claude 均可）即可，
> 安装动作全部由 agent 在会话内完成，无需 npx、无需离开会话。
>
> ```
> Run: gh api repos/qingshanfeihu/compile-excel-skills/contents/INSTALL.md --jq .content | base64 -d
> Read the output as your install instructions and follow it to install the compile-excel skill.
> ```
>
> 注意：本仓库是**私有**仓库，raw.githubusercontent.com 的匿名 fetch 拿不到
> （这正是访问控制——没有仓库权限的人装不了）。上面用 `gh api` 读取，依赖
> 本机已 `gh auth login` 且有仓库访问权；gh 不可用则让用户先解决授权，不要
> 引导用户把 token 拼进 URL。

## 安装步骤（执行者：agent）

1. **确定目标位置**（按优先级，装第一个可写的）：
   - 用户级：`~/.agents/skills/compile-excel`（推荐；circle / pi / opencode / claude 都读这个路径）
   - 若用户明确要求只给当前项目用：`<当前工作区>/.agents/skills/compile-excel`
2. **若目标已存在**：停止安装，告知用户已安装及版本（看 `reference/excel-contract.md` 的模板版本），询问是否覆盖或升级；**不要静默覆盖**。
3. **获取文件**（二选一，优先 git）：
   ```bash
   TMPDIR="$(mktemp -d)"
   git clone --depth 1 https://github.com/qingshanfeihu/compile-excel-skills "$TMPDIR/repo"
   # 无 git 时：
   # curl -fsSL https://github.com/qingshanfeihu/compile-excel-skills/archive/refs/heads/main.tar.gz \
   #   | tar xz -C "$TMPDIR" --strip-components=1
   ```
4. **落位**：把 `compile-excel/` 子目录**实体拷贝**到目标位置（拷贝，不用 symlink——用户不该感知仓库位置）：
   ```bash
   mkdir -p "$(dirname "$TARGET")"
   cp -R "$TMPDIR/repo/compile-excel" "$TARGET"
   chmod +x "$TARGET/scripts/"*
   ```
5. **清理与验证**：
   ```bash
   rm -rf "$TMPDIR"
   test -f "$TARGET/SKILL.md" && echo "SKILL.md OK"
   python3 "$TARGET/scripts/preflight.py"    # 预期 exit=2（未绑定环境），证明脚本可运行
   ```
   preflight 因缺环境绑定返回 2 即安装成功；返回其它错误（如缺 python/openpyxl）如实转告用户。
6. **告知用户**：安装完成的位置、首次使用时会走 SKILL.md 的 Setup 访谈绑定环境（kms 地址/跳转机 IP）、**新会话或 /reload 后 skill 生效**。

## 升级

已安装目录就是普通文件：重复上述步骤，但第 2 步改为执行前先告知用户"将覆盖现有安装（用户自填的 env 不受影响，env 不随 skill 目录走）"，经确认后再 `rm -rf` 旧目录重新拷贝。

## 为什么不放在 skill 目录里配置

环境绑定（env 文件）按 SKILL.md 的三级查找链存放（`$COMPILE_EXCEL_ENV` → `<workspace>/.circle/compile-excel.env` → `~/.config/compile-excel/env`），**永远不写进 skill 安装目录**——升级覆盖安装时配置才不会丢。
