# INSTALL — compile-excel（给 agent 看的安装指令）

> 人话版：把下面这句 prompt 发给你的 agent（Claude Code / pi / circle 均可），安装动作由 agent 在会话内完成。
>
> ```
> Run: gh api repos/qingshanfeihu/compile-excel-skills/contents/INSTALL.md --jq .content | base64 -d
> Read the output as your install instructions and follow it to install compile-excel.
> ```
>
> 本仓库是**私有**仓库：依赖本机 `gh auth login` 且账号有仓库访问权（这也构成访问控制）。
> gh 不可用时让用户先解决授权，不要引导用户把 token 拼进 URL。

## Steps (for the agent)

1. **Pick the harness.** Install for the harness you are running in (`claude` for Claude Code, `pi`,
   or `circle`). If the user wants several, pass `--harness` once per harness or `--harness all`.

2. **Fetch the files** into a temporary directory:

   ```bash
   TMPDIR="$(mktemp -d)"
   gh repo clone qingshanfeihu/compile-excel-skills "$TMPDIR/repo" -- --depth 1
   ```

3. **Run the installer** with the system `python3`:

   ```bash
   python3 "$TMPDIR/repo/install.py" --harness <claude|pi|circle>
   ```

   It prints a JSON report. What it does: copies the distribution to
   `~/.local/share/compile-excel/current`, then
   - claude: registers that directory as a plugin marketplace and installs the `compile-excel`
     plugin (skill + `cex_*` tools over MCP) with the `claude` CLI;
   - pi: `pi install <that directory>` (skill + extension);
   - circle: copies the skill to `~/.circle/skills/compile-excel` and writes the extension entry to
     `~/.circle/extensions/compile-excel/extension.py`.

   Read the report:
   - exit 3 (`installed_version` in the report): compile-excel is already installed. Tell the user
     the installed version, ask whether to replace it, and only then re-run with `--upgrade`.
     The user's project folders (`.compile-excel/`) are not touched by an upgrade.
   - `dependencies.missing` not empty: the Python packages the tools need are absent. Tell the user
     which ones and run the command in `dependencies.next` only after they agree. If `pip` refuses
     because the Python is externally managed, suggest a virtualenv and setting `CEX_PYTHON` to its
     `python`; do not force the install.
   - a harness with `ok: false`: relay its `error` (e.g. the harness CLI is not on PATH).
   - `--dry-run` prints the plan without changing anything, if the user wants to see it first.

4. **Clean up**: `rm -rf "$TMPDIR"`.

5. **Tell the user**: where it was installed, which harnesses were set up, that a **new session**
   (or `/reload-plugins` in Claude Code, `/reload` in pi) picks it up, and that on first use in a
   project folder the skill asks for the server URL and the device build, then signs in through the
   browser. Installing never needs a password; do not ask for one.

## Native alternatives

- Claude Code: `/plugin marketplace add qingshanfeihu/compile-excel-skills`, then
  `/plugin install compile-excel@compile-excel` (needs git access to the private repo).
- pi: `pi install git:github.com/qingshanfeihu/compile-excel-skills`.

Both still need the Python packages from `requirements.txt` for the `python3` the tools run with.

## Why configuration is not in the install directory

Tokens and settings follow the **project folder** (`<folder>/.compile-excel/`); the portal session
lives in `~/.cache/compile-excel/`. Nothing is written into the install directory at runtime, so
upgrades never lose configuration and the distribution never carries a token.
