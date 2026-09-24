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

1. **确定目标位置**（按当前 harness 选；各 harness 扫描的目录不同）：
   - Claude Code 或 circle：`~/.claude/skills/compile-excel`（推荐。Claude Code 只扫
     `~/.claude/skills` 与项目 `.claude/skills`，不读 `~/.agents/skills`；circle 两处都读）
   - pi：`~/.pi/agent/skills/compile-excel`（circle 也读这个位置）
   - 只读 `.agents/skills` 的 harness（Codex、opencode 等）：`~/.agents/skills/compile-excel`
   - 若用户明确要求只给当前项目用：`<当前工作区>/.claude/skills/compile-excel`
     （pi 用 `<当前工作区>/.pi/skills/compile-excel`）
2. **若目标已存在**：停止安装，告知用户已安装及版本（看 `references/excel-contract.md` 的模板版本），询问是否覆盖或升级；**不要静默覆盖**。
3. **获取文件**（二选一，优先 git）：
   ```bash
   TMPDIR="$(mktemp -d)"
   git clone --depth 1 https://github.com/qingshanfeihu/compile-excel-skills "$TMPDIR/repo"
   # 无 git 时：
   # curl -fsSL https://github.com/qingshanfeihu/compile-excel-skills/archive/refs/heads/main.tar.gz \
   #   | tar xz -C "$TMPDIR" --strip-components=1
   ```
4. **落位**：skill 的脚本要用到仓库里的 `cex_core/`、`cex_client/`，所以分两处放：
   发行根整份放到 `~/.local/share/compile-excel/current`，skill 目录**实体拷贝**到目标位置，
   再在 skill 目录里写一行 `.cex_home` 指回发行根（拷贝，不用 symlink——用户不该感知仓库位置）：
   ```bash
   DIST="$HOME/.local/share/compile-excel/current"
   mkdir -p "$(dirname "$DIST")" "$(dirname "$TARGET")"
   rm -rf "$DIST.new" && cp -R "$TMPDIR/repo" "$DIST.new" && rm -rf "$DIST.new/.git" "$DIST.new/tests"
   [ -d "$DIST" ] && mv "$DIST" "$DIST.old"; mv "$DIST.new" "$DIST"; rm -rf "$DIST.old"
   cp -R "$DIST/skills/compile-excel" "$TARGET"
   printf '%s\n' "$DIST" > "$TARGET/.cex_home"
   chmod +x "$TARGET/scripts/"* "$DIST/bin/"*
   python3 -m pip install --user -r "$DIST/requirements.txt"   # openpyxl / beautifulsoup4 / PyYAML
   ```
5. **清理与验证**：
   ```bash
   rm -rf "$TMPDIR"
   test -f "$TARGET/SKILL.md" && echo "SKILL.md OK"
   python3 "$TARGET/scripts/_cex_path.py"                      # 打印发行根，证明 skill 找得到 cex_core
   python3 "$DIST/bin/cex_tool" list > /dev/null && echo "cex_tool OK"
   ```
6. **告知用户**：安装位置；**新会话或 /reload 后 skill 生效**；首次在项目文件夹里使用时，agent 会问
   服务端地址和被测床的 device build，再引导浏览器授权登录（`cex_init` → `cex_login_start`）。
   安装阶段不需要、也不要向用户要任何口令。

## 升级

已安装目录就是普通文件：重复上述步骤，但第 2 步改为执行前先告知用户"将覆盖现有安装"，经确认后再
删除旧目录重新拷贝。项目文件夹里的 `.compile-excel/`（令牌、配置、已同步的数据包）不受影响。

## 为什么不在 skill 目录里放配置

配置和令牌跟着**项目文件夹**走（`<文件夹>/.compile-excel/`），门户会话在用户级
`~/.cache/compile-excel/`，都不写进 skill 安装目录——升级覆盖安装时才不会丢，也不会把令牌带进 skill 分发。
