// compile-excel 的 circle 扩展（circle 1.0 起，TypeScript 版）：把 cex_* 工具注册进 circle，
// 执行时调发行根的 bin/cex_tool。circle 0.5.0 及更早（Python 版）读同目录的 extension.py，
// 两份做同一件事：工具说明与参数 schema 来自 cex_client/tool_specs.json，逻辑只有 cex_client 一份。
// 参数经 stdin 传（`cex_tool <名> -`）：整批用例这类大参数放进命令行会撞上长度上限。
// cex_tool 退出码：0 成功（含 pending）；1 工具返回 ok:false；2 用法错误。非 0 时抛 ToolError。
import { spawn } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

// 单次调用上限：登录/扫码等待最长 300 秒，一次上机可以更久，按最长的给
export const TIMEOUT_MS = 45 * 60 * 1000;
// 超时或取消时先 SIGTERM，过这么久还没退再 SIGKILL
const KILL_GRACE_MS = 5000;

/** 发行根：本文件在 <根>/adapters/circle/ 下；CEX_HOME 可覆盖。 */
export function distRoot() {
  const override = process.env.CEX_HOME;
  if (override && existsSync(join(override, 'bin', 'cex_tool'))) return resolve(override);
  return resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
}

export function loadSpecs(root) {
  return JSON.parse(readFileSync(join(root, 'cex_client', 'tool_specs.json'), 'utf8')).tools;
}

function runCexTool(python, cexTool, name, input, signal, timeout) {
  return new Promise((done) => {
    const child = spawn(python, [cexTool, name, '-'], { stdio: ['pipe', 'pipe', 'pipe'] });
    const stdout = [];
    const stderr = [];
    let killed = false;
    let timedOut = false;
    let settled = false;
    let hardKill;
    const stop = () => {
      if (killed || child.exitCode !== null) return;
      killed = true;
      child.kill('SIGTERM');
      hardKill = setTimeout(() => child.kill('SIGKILL'), KILL_GRACE_MS);
    };
    const timer = setTimeout(() => {
      timedOut = true;
      stop();
    }, timeout);
    const onAbort = () => stop();
    signal?.addEventListener('abort', onAbort, { once: true });
    const finish = (result) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (hardKill) clearTimeout(hardKill);
      signal?.removeEventListener('abort', onAbort);
      done(result);
    };
    child.stdout.on('data', (chunk) => stdout.push(chunk));
    child.stderr.on('data', (chunk) => stderr.push(chunk));
    // 解释器不在（CEX_PYTHON 指错）、没有执行权限之类：照样报成这次调用失败
    child.on('error', (error) => finish({ startError: error.message }));
    child.on('close', (code) =>
      finish({
        stdout: Buffer.concat(stdout).toString('utf8'),
        stderr: Buffer.concat(stderr).toString('utf8'),
        code: code ?? -1,
        timedOut,
      }),
    );
    // 子进程提前退出时写 stdin 会 EPIPE：吞掉，结果照 close 事件报
    child.stdin.on('error', () => undefined);
    child.stdin.end(input, 'utf8');
    if (signal?.aborted) stop();
  });
}

export function makeExecutor(root, name, ToolError) {
  const python = process.env.CEX_PYTHON || 'python3';
  const cexTool = join(root, 'bin', 'cex_tool');
  return async (args, context) => {
    const result = await runCexTool(
      python,
      cexTool,
      name,
      JSON.stringify(args ?? {}),
      context?.signal,
      TIMEOUT_MS,
    );
    if (result.startError !== undefined)
      throw new ToolError(`${name} could not start ${JSON.stringify(python)}: ${result.startError}`);
    if (result.timedOut) throw new ToolError(`${name} timed out after ${TIMEOUT_MS / 1000}s`);
    context?.signal?.throwIfAborted();
    let payload;
    try {
      payload = JSON.parse(result.stdout);
    } catch {
      const tail = (result.stderr || result.stdout).slice(-800);
      throw new ToolError(`${name} returned no JSON (exit ${result.code}): ${tail}`);
    }
    if (result.code !== 0) throw new ToolError(JSON.stringify(payload, null, 1));
    return payload;
  };
}

export function register(api) {
  const root = distRoot();
  for (const spec of loadSpecs(root))
    api.registerTool(
      spec.name,
      spec.description,
      spec.input_schema,
      makeExecutor(root, spec.name, api.ToolError),
      { readOnly: Boolean(spec.read_only) },
    );
}
