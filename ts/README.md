# compile-excel TypeScript 版（Windows 兼容）

这是 compile-excel 发行根的 TypeScript 重写版，替代原 Python 实现，目标：
- Windows / macOS / Linux 全平台可运行（原 Python 版依赖 fcntl 文件锁、chmod 权限位、/bin/sh 等 POSIX 特性，Windows 上无法运行）
- 不依赖 Python；只要 Node.js ≥ 20 和 `npm install` 一次即可

## 布局

- `src/platform/index.ts` — Windows 兼容层：跨平台文件锁（O_EXCL 锁文件，替代 fcntl.flock）、权限收紧（Windows 上为无操作）、原子写、数据目录（`%LOCALAPPDATA%\compile-excel`，替代 `~/.local/share`）
- `src/cex_client/` — 客户端：工作区、网关连接、OAuth 设备流登录、床租约、上机提交/回执
- `src/cex_core/` — 引擎：`engine/`（case_compiler / ist_core / kms / sync / scripts）、`ist_emit/`（xlsx 发射器）、`defects/`（工单解析）
- `src/skills_scripts/` — skill 命令行脚本（compile_excel / verify_batch / run_device / rework_gate / backfill / cmdtree_check）
- `src/bin/cex_tool.ts` — `cex_tool list | <name> - | <name> '<json>'`
- `src/bin/cex_mcp_proxy.ts` — stdio MCP 服务（Claude Code / Codex 等）
- `src/install.ts` — 安装器：`node dist/install.js --harness circle|claude|pi|all [--upgrade] [--install-deps] [--dry-run]`
- `adapters/` — harness 适配（circle extension.mjs、cex_mcp 启动 shim）
- `skills/` — 模型说明（SKILL.md 等；命令入口是 `node "$CEX_HOME/dist/..."`，`scripts/_cex_path.js` 解析发行根）

## 构建与测试

```
npm install
npm run build
npm test
```

`npm run build` 产出 `dist/` 并把 `tool_specs.json`、xlsx 模板、YAML 选择器等资源拷到 dist。
`npm test` 编译后跑 `node --test`（编译往返、数据验证保持、平台锁、配置静默、版本一致、安装清单）。

## 冒烟验证

```
node dist/bin/cex_tool.js list
node dist/bin/cex_tool.js cex_status
node dist/skills_scripts/compile_excel.js --cases cases.json --out compile_outputs
node dist/skills_scripts/verify_batch.js --xlsx compile_outputs/<batch>/case.xlsx
node dist/bin/cex_mcp_proxy.js   # stdio JSON-RPC
node dist/install.js --harness circle --dry-run
```

## 已知差异

- `cex_core/engine/scripts/gen_capability_atlas.ts` 里的 `_parse_cert_methods`/`_execute_actions` 目前是对 apv_lang 既有导出的薄封装，不复现 Python 版用 ast 扫描框架源码的过程（该 ast 分析依赖私有框架源码，不在本发行根内；线上路径走已生成的 projections，不影响编译/上机流程）。
- `cex_core/engine/case_compiler/provenance_ir.ts` 的 config-binding 逻辑指纹用文本静态分析替代 Python ast.dump 序列化，指纹值与 Python 版不同（接受/拒绝判定不变）。
- `engine/ist_core/tools/ask_user/index.ts` 用模块状态替代 Python 的 contextvars/threading；`json_repair` 未装，解析走 try/catch 兜底。
