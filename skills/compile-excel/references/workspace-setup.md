# Workspace setup, login and compile data

Read this the first time a project folder is set up, or when a `cex_*` setup tool fails.

## What lives where

```
<project folder>/
  .compile-excel/                 0700, has its own .gitignore (never committed)
    config.json                   server URL, device_build, channel, ca_sha256
    ca.pem                        the server's built-in CA, checked against the connection
                                  string's fingerprint (only when it had #ca=)
    token.json                    OAuth token (0600) - the only credential in the folder
    client_config.json            organisation constants published by the server
    lease.json                    current bed lease (0600), while you hold one; its fencing token
                                  is never shown in a tool result
    bundle/<build>/manifest.json  synced compile data; entries sit beside it by bundle path
  compile_outputs/<batch>/        cases.json, case.xlsx, provenance.json, run receipts, footprint
  defects/<backend>/<ticket>.json scrubbed defect tickets from cex_bug_get
~/.cache/compile-excel/           per-user portal session and QR image (0600), never in the folder
```

## cex_init

Arguments come from the user; do not guess them.

| Argument | Meaning |
|---|---|
| `server` | The connection string the user's administrator gave, e.g. `https://ces.example.com:8900#ca=<64 hex digits>`. Pass it exactly as given (the fingerprint may be upper case, grouped with spaces or colons, or prefixed `sha256:`). A plain `https` URL also works when the system already trusts the server's certificate; `http` only for loopback or with `insecure_lan`. The server's default port is 8900. Omit `server` on an existing workspace to change only `device_build` or `channel`. |
| `device_build` | Optional; normally left out. After login the build is chosen automatically when the server publishes exactly one on the channel. When there are several, `cex_login_wait` returns `builds`: ask the user which one the bed runs, then call `cex_init` with only `device_build` (no `server`; the session is kept). `cex_env_prepare` later checks that the bed reports the same build, so a guess fails there. |
| `channel` | `stable` (default; an existing workspace keeps its channel). `candidate` only when the user explicitly wants unreleased data. |
| `insecure_lan` | Allows plain `http` to a non-loopback server. The token then crosses the network in clear text; set it only when the user says the server is on a trusted lab network without TLS. |
| `workspace` | Optional. Without it `cex_init` updates the workspace the other tools would use (`CEX_WORKSPACE`, or the current folder and its parents), so running it from a subfolder never creates a nested workspace; only when there is none does it create one (in the `CEX_WORKSPACE` folder, or the current folder). |

Before anything is stored, `cex_init` checks the address. With `#ca=` it downloads the server's
CA certificate (`/ca.pem`), compares its SHA-256 with the fingerprint and refuses on a mismatch;
then it calls `/healthz` with certificate verification and confirms the answer comes from
compile-excel-server. When a check fails nothing is written, and the error (in Chinese) says what
to fix. `/ca.pem` must hold exactly one certificate (strictly decoded); both answers are capped
at 64 KiB and 15 seconds, so a fake server can neither flood nor stall the client. Afterwards
every request to the server and to the gateway verifies certificates against the system store
plus that CA (only the one certificate in `ca.pem`); `cex_status` reports it as `tls`
(`内置 CA（指纹已核对）`, `系统证书`, `明文（insecure_lan）` or `明文（本机回环）`).

Changing `server` (or the CA fingerprint) on an existing workspace drops the old token, the
cached organisation config and any bed lease (they belong to the old server), and replaces or
removes the stored CA. Re-running `cex_init` with the same server (the same connection string,
or just its URL as `cex_status` shows it) keeps the CA checked earlier, the session and the build.
Addresses are compared after normalising (scheme and host case, an explicit `:443` / `:80`, IPv6
spelling), and stored in that form. If the server has since switched to a certificate the system
already trusts (its `/ca.pem` is gone), re-running with the plain URL verifies it against the
system store instead, forgets the old CA and its session; log in again.

## Login (cex_login_start / cex_login_wait)

Device authorization: `cex_login_start` returns `verification_uri` and `user_code`. The user opens
the page, signs in with their username and access code, and approves. `cex_login_wait` returns
`pending` until then; call it again. The access token refreshes itself; when refresh fails the
tools say to log in again (`重新登录（cex_login_start）`). `cex_logout` revokes the session on the
server and deletes the token.

When the workspace trusts the server's built-in CA (it was set up with `#ca=`), the browser does
not know that CA and warns that the connection is not private. `cex_login_start` then also returns
`browser_certificate`, a note in Chinese: why the warning appears (the client already checked the
CA against the connection string), the SHA-256 fingerprint of the server certificate written as the
browser shows it (upper-case hex pairs separated by spaces) for the user to compare in the
browser's certificate details before continuing, and how to stop the warning by trusting the
workspace's `.compile-excel/ca.pem` (macOS: `security add-trusted-cert -r trustRoot -k
~/Library/Keychains/login.keychain-db <path>`; Windows: `certutil -addstore -user Root <path>`).
Relay the note to the user word for word before they open the page. If the fingerprints differ,
the user must not continue; it goes to the administrator.

When the workspace has no device build yet, a successful `cex_login_wait` also returns
`device_build_note` and either `device_build` (the server's only build on the channel, now
stored) or `builds` (several: ask the user, then `cex_init` with `device_build`). When the server
has published nothing on the channel the note says so; tell the user to contact the administrator.
`cex_sync` makes the same choice, on the channel it syncs, if it was not made at login.

## Organisation constants (cex_client_config)

Publishes the gateway URL (needed for every bed tool), the portal login URL and the defect
tracker addresses. Cached in `client_config.json`; call it once per session so address changes
reach the workspace.

## Compile data (cex_sync)

Downloads the bundle for the workspace's `device_build` and channel. Each file is checked against
the manifest SHA-256; a mismatch is refused and nothing is replaced. Sync is incremental (only
changed or missing files are downloaded) and removes files the new bundle no longer lists.

Bundle kinds: `cmdtree` (command-tree projection, no raw XML), `projections` (domain grammar with
the destructive-command rules, and other derived tables), `template`, `manual`, `spec`,
`framework`, `footprints`. What a given build carries depends on what the server published.

`cex_docs_query` searches verified local manuals for the build's `source.manual_version` first
(when present in the bundle manifest) and also queries the
server's document index when available. Results mark `source: local_manual` or
`source: server_document`; only local manual matches have
`manual:<version>/<file>.md:<line>` references. `limit` applies separately to local manuals and
server documents (default 3, maximum 10 each); online results can contain up to twice `limit`.
Offline results state that server documents were
not searched. If neither source is available, the tool reports a supply failure. Run `cex_sync`
when local manuals are expected.

When the server is unreachable, `cex_sync` verifies the cached bundle and returns
`source: cache` with a `note` naming the bundle id and its date. Tell the user which bundle the
compile used; a missing or modified cache is an error, not a silent fallback.

## Portal session (cex_portal_login_start / cex_portal_login_wait)

QR-code login to the company portal; no password is asked for or stored. The QR image is written
to a private file and its path returned; the user opens it and scans with the company app. The
session cookie is kept per user in `~/.cache/compile-excel/portal-session.json`. When a fetch hits
the login page, the tools report an expired session; start the QR login again. `cex_portal_logout`
forgets the session.

## When a setup tool fails

Connection, setup and login errors are in Chinese and end with what to do; relay them to the user.
The first column quotes the error text.

| Error says | Meaning | Do |
|---|---|---|
| No workspace here (`cex_status`) / `这里还没有 compile-excel 工作区` | the folder was never initialised | ask for the connection string, `cex_init` |
| `这个地址上的服务不是 compile-excel-server` | the address answers, but with some other service; usually the port is missing and another web server answered | the error adds `地址里没写端口，服务端默认端口是 8900，例如 https://…:8900` when that is the case; ask the user for the administrator's connection string and `cex_init` again |
| `连接串里的证书指纹不对` / `连接串 # 后面应是 ca=<证书指纹>` | the connection string was damaged while copying | ask the user to copy it again, unchanged |
| `服务端发来的 CA 证书与连接串里的指纹不一致` | the server presented another CA: an impostor, or a wrong connection string. Nothing was stored | tell the user to check the connection string with the administrator; never work around it |
| `服务端没有启用内置 CA` | the connection string has `#ca=`, the server does not use its built-in CA | ask the administrator for a new connection string |
| `服务端发来的根证书格式不对` | `/ca.pem` is not exactly one certificate. Nothing was stored | tell the user to report it to the administrator; never work around it |
| `回的内容超过 65536 字节` / `秒内没有回完应答` | the address answered with far too much, or too slowly, for compile-excel-server | check the address with the user; use the connection string |
| `证书不受信任` | a plain https URL to a server whose CA the system does not trust | `cex_init` with the connection string (the one with `#ca=`); for an organisation CA the harness process needs `SSL_CERT_FILE` |
| `证书里没有这个地址` | the server's certificate does not list the host the user typed | the administrator re-issues the certificate with this address in the `ces` menu, or the user connects by an address the certificate lists |
| `拒绝连接` | nothing listens on that host and port | check the address and port (default 8900) and that the server runs |
| `连接超时` / `网络不通` / `找不到主机` | no network path, or the name does not resolve | check network or VPN, firewall, spelling |
| `对方没有按 HTTP 应答就断开了` / `TLS 握手失败` | `http` typed for an `https` server, or the reverse | use the connection string |
| `明文 http 连非本机的服务端` | the URL is `http` on a remote host | ask for the connection string (`https`), or see `insecure_lan` |
| `回了重定向` | the address forwards elsewhere; the client does not follow | use the address from the connection string itself |
| `还没有登录` / `登录已过期或被撤销` / `服务端不认这次登录` | no usable token | `cex_login_start` again |
| `令牌属于另一个服务端` | `server` changed | log in again |
| `登录被拒绝` / `授权码已过期` | the user denied, mistyped, or let the code expire | start the login again |
| `还没有选构建号` | no device build yet | log in (the build is picked then); with several builds, `cex_init` with `device_build` |
| `服务端在 … 通道上有多个构建` | the user must choose | ask which build the bed runs, `cex_init` with `device_build` |
| `服务端还没有在 … 通道上发布任何构建` | nothing published on the channel | tell the user to contact the administrator |
| no gateway address | client config not fetched or not published | `cex_client_config`; if still missing, the server has no gateway configured: tell the user |
| the cached organisation config came from another server | `server` changed since `cex_client_config` | `cex_client_config` again |
| no command tree projection / no domain grammar | bundle not synced or the build has none | `cex_sync`; if still missing, the server has not published it for this build: tell the user |
| SHA256 mismatch | a downloaded file differs from the manifest | report it; do not retry around it |
| server unreachable (sync `note`) | offline | the cached bundle is used; tell the user its `note` |
