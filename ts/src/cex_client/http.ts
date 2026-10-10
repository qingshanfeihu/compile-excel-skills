import http from "node:http";
import https from "node:https";
import { ClientError, ServerUnreachable } from "./errors.js";

export interface HttpRequestOptions {
  method?: string;
  headers?: Record<string, string>;
  body?: string | Buffer;
  timeoutMs?: number;
  maxBytes?: number;
  maxRedirects?: number;
  ca?: string;
  rejectUnauthorized?: boolean;
}

export interface HttpResponse {
  status: number;
  headers: Record<string, string>;
  body: Buffer;
}

const DEFAULT_TIMEOUT_MS = 15_000;
const DEFAULT_MAX_BYTES = 64 * 1024;

export function httpRequest(url: string, options: HttpRequestOptions = {}): Promise<HttpResponse> {
  return new Promise((resolve, reject) => {
    let target: URL;
    try {
      target = new URL(url);
    } catch {
      reject(new ClientError(`invalid URL: ${url}`));
      return;
    }
    const method = options.method ?? "GET";
    const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
    const maxBytes = options.maxBytes ?? DEFAULT_MAX_BYTES;
    const maxRedirects = options.maxRedirects ?? 5;
    const ca = options.ca;

    const doRequest = (currentUrl: URL, redirectsLeft: number) => {
      const isHttps = currentUrl.protocol === "https:";
      const transport = isHttps ? https : http;
      const requestOptions: https.RequestOptions | http.RequestOptions = {
        method,
        headers: { ...(options.headers ?? {}) },
        timeout: timeoutMs,
        rejectUnauthorized: options.rejectUnauthorized ?? (ca !== undefined),
        ca,
      };
      if (options.body !== undefined) {
        const len = typeof options.body === "string" ? Buffer.byteLength(options.body) : options.body.length;
        requestOptions.headers = { ...requestOptions.headers, "content-length": String(len) };
      }
      const req = transport.request(currentUrl, requestOptions, (res) => {
        const status = res.statusCode ?? 0;
        const headers: Record<string, string> = {};
        for (const [k, v] of Object.entries(res.headers)) {
          if (v !== undefined) headers[k.toLowerCase()] = Array.isArray(v) ? v.join("; ") : v;
        }
        if (status >= 300 && status < 400 && headers.location && redirectsLeft > 0) {
          let next: URL;
          try {
            next = new URL(headers.location, currentUrl);
          } catch {
            reject(new ClientError(`invalid redirect location from ${currentUrl}`));
            return;
          }
          doRequest(next, redirectsLeft - 1);
          return;
        }
        const chunks: Buffer[] = [];
        let total = 0;
        res.on("data", (chunk: Buffer) => {
          total += chunk.length;
          if (total > maxBytes) {
            req.destroy(new ClientError(`response exceeds ${maxBytes} bytes`));
            return;
          }
          chunks.push(chunk);
        });
        res.on("end", () => {
          resolve({ status, headers, body: Buffer.concat(chunks) });
        });
        res.on("error", (err) => reject(err));
      });
      req.on("timeout", () => {
        req.destroy(new ServerUnreachable(`request to ${currentUrl} timed out after ${timeoutMs}ms`));
      });
      req.on("error", (err) => {
        if (err instanceof ClientError) {
          reject(err);
        } else {
          reject(new ServerUnreachable(String(err)));
        }
      });
      if (options.body !== undefined) {
        req.write(options.body);
      }
      req.end();
    };

    doRequest(target, maxRedirects);
  });
}

export function httpRequestNoRedirect(url: string, options: HttpRequestOptions = {}): Promise<HttpResponse> {
  return httpRequest(url, { ...options, maxRedirects: 0 });
}
