import fs from "node:fs";
import path from "node:path";

const _ROOT = path.resolve(__dirname, "..", "..", "..");
const _CONFIG_PATH =
  (process.env.COMPILE_EXCEL_COMPILER_CONFIG ?? "").trim() !== ""
    ? (process.env.COMPILE_EXCEL_COMPILER_CONFIG as string)
    : path.join(_ROOT, "runtime", "compiler_config.json");

function _load_file_config(): Record<string, unknown> {
  try {
    if (fs.statSync(_CONFIG_PATH).isFile()) {
      return JSON.parse(fs.readFileSync(_CONFIG_PATH, "utf-8"));
    }
  } catch (exc) {
    console.warn(`配置文件读取/解析失败: ${_CONFIG_PATH}`, exc);
  }
  return {};
}

function _pick(envKey: string, fileCfg: Record<string, unknown>, fileKey: string, defaultValue: unknown): unknown {
  const v = process.env[envKey];
  if (v !== undefined && String(v).trim() !== "") {
    return v;
  }
  if (fileKey in fileCfg && fileCfg[fileKey] !== null && fileCfg[fileKey] !== undefined && fileCfg[fileKey] !== "") {
    return fileCfg[fileKey];
  }
  return defaultValue;
}

function _pick_port(envKey: string, fileCfg: Record<string, unknown>, fileKey: string, defaultValue: number): number {
  const envRaw = process.env[envKey];
  const fromEnv = envRaw !== undefined && String(envRaw).trim() !== "";
  const source = fromEnv ? envKey : `配置文件 ${fileKey}`;
  const raw = _pick(envKey, fileCfg, fileKey, defaultValue);
  const port = Number.parseInt(String(raw).trim(), 10);
  if (Number.isNaN(port)) {
    console.warn(`${source} 不是整数端口，按 ${defaultValue} 处理`);
    return defaultValue;
  }
  if (!(port > 0 && port < 65536)) {
    console.warn(`${source} 的端口 ${port} 不在 1–65535，按 ${defaultValue} 处理`);
    return defaultValue;
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

  constructor(init?: Partial<XlsxLayout>) {
    if (init) Object.assign(this, init);
  }
}

export class CompilerConfig {
  build = "SAMPLE_BUILD_LOCAL";
  target_version = "10.5.0.585";
  staging_module = "sdns";
  mysql_host = "";
  mysql_db = "smoke_test";
  mysql_user = "root";
  mysql_password_env = "IST_MYSQL_PASS";
  jumphost: JumphostConfig = new JumphostConfig();
  xlsx: XlsxLayout = new XlsxLayout();
  default_init_lines: string[] = [];

  static load(): CompilerConfig {
    const fc = _load_file_config();
    const jhFc = (fc["jumphost"] as Record<string, unknown> | undefined) ?? {};
    const xlFc = (fc["xlsx"] as Record<string, unknown> | undefined) ?? {};

    const jh = new JumphostConfig();
    jh.host = _pick("IST_JUMPHOST_HOST", jhFc, "host", "") as string;
    jh.user = _pick("IST_JUMPHOST_USER", jhFc, "user", "") as string;
    jh.port = _pick_port("IST_JUMPHOST_PORT", jhFc, "port", 22);
    jh.apv_src = _pick("IST_APV_SRC", jhFc, "apv_src", "/home/test/apv_src") as string;
    jh.server_path = _pick("IST_MCP_SERVER_PATH", jhFc, "server_path", "/home/test/mcp_server/server.py") as string;
    jh.py38 = _pick("IST_JUMPHOST_PY38", jhFc, "py38", "/home/test/apv_src/.python3.8/bin/python") as string;

    const xl = new XlsxLayout({
      header_row: Number.parseInt(String(_pick("IST_XLSX_HEADER_ROW", xlFc, "header_row", 28)), 10),
      data_start: Number.parseInt(String(_pick("IST_XLSX_DATA_START", xlFc, "data_start", 29)), 10),
      header_anchor: _pick("IST_XLSX_HEADER_ANCHOR", xlFc, "header_anchor", "自动化ID") as string,
    });

    let init = fc["default_init"];
    if (!Array.isArray(init) || init.length === 0) {
      init = null;
    }
    const cfg = new CompilerConfig();
    cfg.build = _pick("IST_DEVICE_BUILD", fc, "build", "SAMPLE_BUILD_LOCAL") as string;
    cfg.target_version = _pick("IST_TARGET_VERSION", fc, "target_version", "10.5.0.585") as string;
    cfg.staging_module = _pick("IST_STAGING_MODULE", fc, "staging_module", "sdns") as string;
    cfg.mysql_host = _pick("IST_MYSQL_HOST", fc, "mysql_host", "") as string;
    cfg.mysql_db = _pick("IST_MYSQL_DB", fc, "mysql_db", "smoke_test") as string;
    cfg.mysql_user = _pick("IST_MYSQL_USER", fc, "mysql_user", "root") as string;
    cfg.jumphost = jh;
    cfg.xlsx = xl;
    cfg.default_init_lines = (init as string[] | null) ?? [];
    return cfg;
  }

  default_init_g(): string {
    return this.default_init_lines.map((line) => "    " + line).join("\n");
  }

  to_dict(): Record<string, unknown> {
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

function _pool_enabled(): boolean {
  return ["1", "true", "on", "yes"].includes(
    (process.env.IST_ENV_POOL_ENABLED ?? "0").trim().toLowerCase(),
  );
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

  if (!_pool_enabled()) {
    return [_mk(jh.host)];
  }

  const fc = _load_file_config();
  const raw = fc["environments"];
  if (Array.isArray(raw) && raw.length > 0) {
    const out: Environment[] = [];
    for (const item of raw) {
      if (typeof item !== "object" || item === null || !(item as Record<string, unknown>)["jumphost"]) {
        continue;
      }
      const rec = item as Record<string, unknown>;
      const host = String(rec["jumphost"]).trim();
      const env = new Environment(
        String(rec["id"] ?? `env-${host.split(".").pop()}`),
        host,
      );
      env.ssh_user = String(rec["ssh_user"] ?? jh.user);
      env.ssh_port = Number.parseInt(String(rec["ssh_port"] ?? jh.port), 10);
      env.pass_env = String(rec["pass_env"] ?? jh.password_env);
      env.apv_src = String(rec["apv_src"] ?? jh.apv_src);
      env.server_path = String(rec["server_path"] ?? jh.server_path);
      env.py38 = String(rec["py38"] ?? jh.py38);
      env.mcp_url = String(rec["mcp_url"] ?? `http://${host}:8000/mcp`);
      env.topology = String(rec["topology"] ?? "network_topology.json");
      out.push(env);
    }
    if (out.length > 0) {
      return out;
    }
  }

  const envHosts = (process.env.IST_ENV_POOL_HOSTS ?? "").trim();
  const seen = new Set<string>();
  const hosts = envHosts
    .split(",")
    .map((h) => h.trim())
    .filter((h) => h && !seen.has(h) && (seen.add(h), true));
  return hosts.map(_mk);
}

export function detect_xlsx_layout(grid: unknown[][], cfg?: CompilerConfig): XlsxLayout {
  const conf = cfg ?? get_config();
  const anchor = conf.xlsx.header_anchor;
  for (let idx = 0; idx < grid.length; idx++) {
    const row = grid[idx];
    const a = row && row.length > 0 ? row[0] : null;
    if (a !== null && a !== undefined && String(a).trim() === anchor) {
      const header1based = idx + 1;
      return new XlsxLayout({
        header_row: header1based,
        data_start: header1based + 1,
        header_anchor: anchor,
        n_cols: conf.xlsx.n_cols,
      });
    }
  }
  return conf.xlsx;
}
