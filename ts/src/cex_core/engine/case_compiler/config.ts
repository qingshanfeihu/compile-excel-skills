import fs from "node:fs";
import path from "node:path";
import { _cex_data_path, _cex_set_caller } from "../_root";

_cex_set_caller("cex_core.engine.case_compiler.config");

const _ROOT = _cex_data_path("");
const _CONFIG_PATH = path.join(_ROOT, "runtime", "compiler_config.json");

function _loadFileConfig(): Record<string, any> {
  try {
    if (fs.existsSync(_CONFIG_PATH) && fs.statSync(_CONFIG_PATH).isFile()) {
      return JSON.parse(fs.readFileSync(_CONFIG_PATH, "utf8"));
    }
  } catch (exc) {
    console.warn(`配置文件读取/解析失败: ${_CONFIG_PATH}`, exc);
  }
  return {};
}

function _pick(envKey: string, fileCfg: Record<string, any>, fileKey: string, def: any): any {
  const v = process.env[envKey];
  if (v !== undefined && String(v).trim() !== "") {
    return v;
  }
  if (fileKey in fileCfg && fileCfg[fileKey] !== null && fileCfg[fileKey] !== undefined && fileCfg[fileKey] !== "") {
    return fileCfg[fileKey];
  }
  return def;
}

function _pickPort(envKey: string, fileCfg: Record<string, any>, fileKey: string, def: number): number {
  const envRaw = process.env[envKey];
  const fromEnv = envRaw !== undefined && String(envRaw).trim() !== "";
  const source = fromEnv ? envKey : `配置文件 ${fileKey}`;
  const raw = _pick(envKey, fileCfg, fileKey, def);
  let port: number;
  try {
    port = parseInt(String(raw).trim(), 10);
    if (Number.isNaN(port)) throw new Error("nan");
  } catch {
    console.warn(`${source} 不是整数端口，按 ${def} 处理`);
    return def;
  }
  if (!(port > 0 && port < 65536)) {
    console.warn(`${source} 的端口 ${port} 不在 1–65535，按 ${def} 处理`);
    return def;
  }
  return port;
}

export class JumphostConfig {
  host = "";
  user = "";
  port = 22;
  apv_src = "/home/test/apv_src";
  server_path = "/home/test/mcp_server/server.py";
  py38 = "/home/test/apv_src/.python3.8/bin/python";
  password_env = "IST_JUMPHOST_PASS";

  get server_cmd(): string {
    return `cd ${this.apv_src} && ${this.py38} ${this.server_path}`;
  }
}

export class XlsxLayout {
  header_row = 28;
  data_start = 29;
  header_anchor = "自动化ID";
  n_cols = 9;
}

export class CompilerConfig {
  build = "SAMPLE_BUILD_LOCAL";
  target_version = "10.5.0.568";
  staging_module = "sdns";
  mysql_host = "";
  mysql_db = "smoke_test";
  mysql_user = "root";
  mysql_password_env = "IST_MYSQL_PASS";
  jumphost: JumphostConfig = new JumphostConfig();
  xlsx: XlsxLayout = new XlsxLayout();
  default_init_lines: string[] = [];

  static load(): CompilerConfig {
    const fc = _loadFileConfig();
    const jhFc = fc.jumphost || {};
    const xlFc = fc.xlsx || {};
    const jhDefaults = new JumphostConfig();
    const xlDefaults = new XlsxLayout();
    const jh = new JumphostConfig();
    jh.host = _pick("IST_JUMPHOST_HOST", jhFc, "host", jhDefaults.host);
    jh.user = _pick("IST_JUMPHOST_USER", jhFc, "user", jhDefaults.user);
    jh.port = _pickPort("IST_JUMPHOST_PORT", jhFc, "port", jhDefaults.port);
    jh.apv_src = _pick("IST_APV_SRC", jhFc, "apv_src", jhDefaults.apv_src);
    jh.server_path = _pick("IST_MCP_SERVER_PATH", jhFc, "server_path", jhDefaults.server_path);
    jh.py38 = _pick("IST_JUMPHOST_PY38", jhFc, "py38", jhDefaults.py38);
    const xl = new XlsxLayout();
    xl.header_row = parseInt(String(_pick("IST_XLSX_HEADER_ROW", xlFc, "header_row", xlDefaults.header_row)), 10);
    xl.data_start = parseInt(String(_pick("IST_XLSX_DATA_START", xlFc, "data_start", xlDefaults.data_start)), 10);
    xl.header_anchor = _pick("IST_XLSX_HEADER_ANCHOR", xlFc, "header_anchor", xlDefaults.header_anchor);
    let init = fc.default_init;
    if (!Array.isArray(init) || !init.length) {
      init = null;
    }
    const cfg = new CompilerConfig();
    const defaults = new CompilerConfig();
    cfg.build = _pick("IST_DEVICE_BUILD", fc, "build", defaults.build);
    cfg.target_version = _pick("IST_TARGET_VERSION", fc, "target_version", defaults.target_version);
    cfg.staging_module = _pick("IST_STAGING_MODULE", fc, "staging_module", defaults.staging_module);
    cfg.mysql_host = _pick("IST_MYSQL_HOST", fc, "mysql_host", defaults.mysql_host);
    cfg.mysql_db = _pick("IST_MYSQL_DB", fc, "mysql_db", defaults.mysql_db);
    cfg.mysql_user = _pick("IST_MYSQL_USER", fc, "mysql_user", defaults.mysql_user);
    cfg.jumphost = jh;
    cfg.xlsx = xl;
    cfg.default_init_lines = init || [...defaults.default_init_lines];
    return cfg;
  }

  default_init_g(): string {
    return this.default_init_lines.map((line) => "    " + line).join("\n");
  }

  to_dict(): Record<string, any> {
    return {
      build: this.build,
      target_version: this.target_version,
      staging_module: this.staging_module,
      mysql_host: this.mysql_host,
      mysql_db: this.mysql_db,
      mysql_user: this.mysql_user,
      mysql_password_env: this.mysql_password_env,
      jumphost: {
        host: this.jumphost.host,
        user: this.jumphost.user,
        port: this.jumphost.port,
        apv_src: this.jumphost.apv_src,
        server_path: this.jumphost.server_path,
        py38: this.jumphost.py38,
        password_env: this.jumphost.password_env,
      },
      xlsx: {
        header_row: this.xlsx.header_row,
        data_start: this.xlsx.data_start,
        header_anchor: this.xlsx.header_anchor,
        n_cols: this.xlsx.n_cols,
      },
      default_init_lines: [...this.default_init_lines],
    };
  }
}

let _CACHED: CompilerConfig | null = null;

export function get_config(reload = false): CompilerConfig {
  if (_CACHED === null || reload) {
    _CACHED = CompilerConfig.load();
  }
  return _CACHED;
}

export class Environment {
  id: string;
  jumphost: string;
  ssh_user = "";
  ssh_port = 22;
  pass_env = "IST_JUMPHOST_PASS";
  apv_src = "/home/test/apv_src";
  server_path = "/home/test/mcp_server/server.py";
  py38 = "/home/test/apv_src/.python3.8/bin/python";
  mcp_url = "";
  topology = "network_topology.json";

  constructor(id: string, jumphost: string) {
    this.id = id;
    this.jumphost = jumphost;
  }

  get server_cmd(): string {
    return `cd ${this.apv_src} && ${this.py38} ${this.server_path}`;
  }
}

function _poolEnabled(): boolean {
  return ["1", "true", "on", "yes"].includes((process.env.IST_ENV_POOL_ENABLED || "0").trim().toLowerCase());
}

export function load_environments(): Environment[] {
  const cfg = get_config();
  const jh = cfg.jumphost;

  const _mk = (hostRaw: string): Environment => {
    const host = hostRaw.trim();
    const env = new Environment(`env-${host.split(".").pop()}`, host);
    env.ssh_user = jh.user;
    env.ssh_port = jh.port;
    env.pass_env = jh.password_env;
    env.apv_src = jh.apv_src;
    env.server_path = jh.server_path;
    env.py38 = jh.py38;
    env.mcp_url = `http://${host}:8000/mcp`;
    return env;
  };
  if (!_poolEnabled()) {
    return [_mk(jh.host)];
  }
  const fc = _loadFileConfig();
  const raw = fc.environments;
  if (Array.isArray(raw) && raw.length) {
    const out: Environment[] = [];
    for (const item of raw) {
      if (typeof item !== "object" || item === null || !item.jumphost) {
        continue;
      }
      const host = String(item.jumphost).trim();
      const env = new Environment(String(item.id || `env-${host.split(".").pop()}`), host);
      env.ssh_user = String(item.ssh_user || jh.user);
      env.ssh_port = parseInt(String(item.ssh_port || jh.port), 10);
      env.pass_env = String(item.pass_env || jh.password_env);
      env.apv_src = String(item.apv_src || jh.apv_src);
      env.server_path = String(item.server_path || jh.server_path);
      env.py38 = String(item.py38 || jh.py38);
      env.mcp_url = String(item.mcp_url || `http://${host}:8000/mcp`);
      env.topology = String(item.topology || "network_topology.json");
      out.push(env);
    }
    if (out.length) {
      return out;
    }
  }
  const envHosts = (process.env.IST_ENV_POOL_HOSTS || "").trim();
  const hosts = envHosts.split(",").map((h) => h.trim()).filter((h) => h);
  const seen = new Set<string>();
  const deduped = hosts.filter((h) => {
    if (seen.has(h)) return false;
    seen.add(h);
    return true;
  });
  return deduped.map(_mk);
}

export function detect_xlsx_layout(grid: any[][], cfg?: CompilerConfig | null): XlsxLayout {
  const config = cfg || get_config();
  const anchor = config.xlsx.header_anchor;
  for (let idx = 0; idx < grid.length; idx++) {
    const row = grid[idx];
    const a = row && row.length ? row[0] : null;
    if (a !== null && a !== undefined && String(a).trim() === anchor) {
      const header1based = idx + 1;
      const layout = new XlsxLayout();
      layout.header_row = header1based;
      layout.data_start = header1based + 1;
      layout.header_anchor = anchor;
      layout.n_cols = config.xlsx.n_cols;
      return layout;
    }
  }
  return config.xlsx;
}
