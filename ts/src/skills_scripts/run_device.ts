#!/usr/bin/env node
import path from "node:path";
import * as device from "../cex_client/device";
import * as gateway from "../cex_client/gateway";
import * as workspace from "../cex_client/workspace";
import { ClientError } from "../cex_client/errors";

const EXIT_PASS = 0, EXIT_FAIL = 1, EXIT_REFUSED = 2, EXIT_TIMEOUT = 3, EXIT_FETCH_FAILED = 4, EXIT_LOST = 5;

function emit(payload: any): void {
  console.log(JSON.stringify(payload));
}

function sleep(s: number): Promise<void> {
  return new Promise((r) => setTimeout(r, Math.max(0, s * 1000)));
}

export async function main(argv: string[]): Promise<number> {
  let xlsxArg = "";
  let module_ = "";
  let maxS = 2400;
  let pollS = 10;
  let heartbeatS = 300;
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--xlsx") xlsxArg = argv[++i] || "";
    else if (a === "--module") module_ = argv[++i] || "";
    else if (a === "--max-s") maxS = Number(argv[++i]);
    else if (a === "--poll-s") pollS = Number(argv[++i]);
    else if (a === "--heartbeat-s") heartbeatS = Number(argv[++i]);
  }
  if (!xlsxArg) {
    emit({ ok: false, stage: "usage", error: "usage: run_device --xlsx <case.xlsx> [--module N] [--max-s S] [--poll-s S] [--heartbeat-s S]" });
    return EXIT_REFUSED;
  }
  const xlsx = path.resolve(xlsxArg);

  let submitted: any;
  let ws: workspace.Workspace;
  try {
    ws = workspace.requireWorkspace(path.dirname(xlsx));
    submitted = await device.submit(ws, xlsx, module_ || undefined);
  } catch (exc: any) {
    if (exc instanceof ClientError) {
      emit({ ok: false, stage: "submit", error: String(exc.message || exc) });
      return EXIT_REFUSED;
    }
    throw exc;
  }
  if (!submitted.ok || !submitted.task_id) {
    const extra: any = { ok: false, stage: "submit" };
    for (const k of ["error", "problems"]) if (submitted[k]) extra[k] = submitted[k];
    emit(extra);
    return EXIT_REFUSED;
  }
  const taskId = String(submitted.task_id);
  console.error(`run_device: submitted task_id=${taskId} (if this script stops, continue with cex_case_status / cex_case_results for this task_id; do not resubmit)`);

  const deadline = Date.now() + Math.max(maxS, 0) * 1000;
  let lastBeat = Date.now();
  let finished = false;
  try {
    while (Date.now() < deadline) {
      const state = (await device.status(ws, taskId)).state;
      if (state === "lost") {
        emit({ ok: false, stage: "wait", task_id: taskId, state: "lost", error: device.RUNNER_LOST });
        return EXIT_LOST;
      }
      if (state === "done") {
        finished = true;
        break;
      }
      if (Date.now() - lastBeat > heartbeatS * 1000) {
        await gateway.lease(ws, "heartbeat");
        lastBeat = Date.now();
      }
      await sleep(pollS);
    }
  } catch (exc: any) {
    if (exc instanceof ClientError) {
      emit({ ok: false, stage: "status", task_id: taskId, error: String(exc.message || exc) });
      return EXIT_FETCH_FAILED;
    }
    throw exc;
  }
  if (!finished) {
    emit({ ok: false, stage: "wait", task_id: taskId,
      error: `the run did not finish within ${Math.floor(maxS)}s and is still going; poll cex_case_status with this task_id, then cex_case_results` });
    return EXIT_TIMEOUT;
  }

  let out: any;
  try {
    out = await device.results(ws, taskId);
  } catch (exc: any) {
    if (exc instanceof ClientError) {
      emit({ ok: false, stage: "results", task_id: taskId, error: String(exc.message || exc) });
      return EXIT_FETCH_FAILED;
    }
    throw exc;
  }
  if (!out.ok || !out.totals) {
    const extra: any = { ok: false, stage: "results", task_id: taskId };
    for (const k of ["error", "problems", "channel"]) if (out[k]) extra[k] = out[k];
    emit(extra);
    return EXIT_FETCH_FAILED;
  }
  const t = out.totals;
  const ok = t.fail === 0 && (t.broken ?? 0) === 0 && t.not_run === 0 && t.cases > 0;
  emit({ ok, totals: t, task_id: taskId, rc: out.rc, result_channel: out.channel, receipt: out.receipt });
  return ok ? EXIT_PASS : EXIT_FAIL;
}

if (require.main === module) {
  main(process.argv.slice(2)).then((code) => process.exit(code));
}

