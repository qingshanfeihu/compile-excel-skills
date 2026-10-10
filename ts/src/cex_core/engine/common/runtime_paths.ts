import os from "node:os";
import path from "node:path";
import { _cex_data_path, _cex_set_caller } from "../_root";

_cex_set_caller("cex_core.engine.common.runtime_paths");
const _REPO_ROOT = _cex_data_path("");

export function runtime_path(...parts: string[]): string {
  if (process.env.PYTEST_CURRENT_TEST) {
    return path.join(os.tmpdir(), `ist_pytest_runtime.${process.pid}`, ...parts);
  }
  return path.join(_REPO_ROOT, "runtime", ...parts);
}
