// compile-excel circle extension (TypeScript distribution): registers cex_* tools into circle,
// executes them via `node <dist>/dist/bin/cex_tool.js`. Tool specs come from
// cex_client/tool_specs.json; args go over stdin (`cex_tool <name> -`).
// Exit codes: 0 ok (incl. pending); 1 tool returned ok:false; 2 usage error. Non-zero throws ToolError.
import { spawn } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

export const TIMEOUT_MS = 45 * 60 * 1000;
const KILL_GRACE_MS = 5000;

export function distRoot() {
  const override = process.env.CEX_HOME;
  if (override && existsSync(join(override, 'dist', 'bin', 'cex_tool.js'))) return resolve(override);
  return resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
}

export function loadSpecs(root) {
  return JSON.parse(readFileSync(join(root, 'dist', 'cex_client', 'tool_specs.json'), 'utf8')).tools;
}

function runCexTool(node, cexTool, name, input, signal, timeout) {
  return new Promise((done) => {
    const child = spawn(node, [cexTool, name, '-'], { stdio: ['pipe', 'pipe', 'pipe'] });
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
    child.on('error', (error) => finish({ startError: error.message }));
    child.on('close', (code) =>
      finish({
        stdout: Buffer.concat(stdout).toString('utf8'),
        stderr: Buffer.concat(stderr).toString('utf8'),
        code: code ?? -1,
        timedOut,
      }),
    );
    child.stdin.on('error', () => undefined);
    child.stdin.end(input, 'utf8');
    if (signal?.aborted) stop();
  });
}

export function makeExecutor(root, name, ToolError) {
  const node = process.env.CEX_NODE || process.execPath;
  const cexTool = join(root, 'dist', 'bin', 'cex_tool.js');
  return async (args, context) => {
    const result = await runCexTool(
      node,
      cexTool,
      name,
      JSON.stringify(args ?? {}),
      context?.signal,
      TIMEOUT_MS,
    );
    if (result.startError !== undefined)
      throw new ToolError(`${name} could not start ${JSON.stringify(node)}: ${result.startError}`);
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
