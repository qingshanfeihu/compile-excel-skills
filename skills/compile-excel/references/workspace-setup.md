# Workspace setup, login and compile data

Read this the first time a project folder is set up, or when a `cex_*` setup tool fails.

## What lives where

```
<project folder>/
  .compile-excel/                 0700, has its own .gitignore (never committed)
    config.json                   server URL, device_build, channel
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
| `server` | The distribution server URL the user's admin gave them. `https` is required unless the host is loopback. |
| `device_build` | The build of the bed the cases will run on. `cex_env_prepare` later checks that the bed reports the same build, so a guess fails there. |
| `channel` | `stable` (default). `candidate` only when the user explicitly wants unreleased data. |
| `insecure_lan` | Allows plain `http` to a non-loopback server. The token then crosses the network in clear text; set it only when the user says the server is on a trusted lab network without TLS. |

Changing `server` on an existing workspace drops the old token (it belongs to the old server).

## Login (cex_login_start / cex_login_wait)

Device authorization: `cex_login_start` returns `verification_uri` and `user_code`. The user opens
the page, signs in with their username and access code, and approves. `cex_login_wait` returns
`pending` until then; call it again. The access token refreshes itself; when refresh fails the
tools say "log in again". `cex_logout` revokes the session on the server and deletes the token.

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

| Error says | Meaning | Do |
|---|---|---|
| no workspace here | the folder was never initialised | ask for server URL and device build, `cex_init` |
| plain http to a non-loopback server | URL is http on a remote host | ask the user for the https URL (or see `insecure_lan`) |
| not logged in / session expired / rejected the session | no usable token | `cex_login_start` again |
| login failed: access_denied / expired_token | the user denied or the code expired | start the login again |
| no gateway address | client config not fetched or not published | `cex_client_config`; if still missing, the server has no gateway configured: tell the user |
| the cached organisation config came from another server | `server` changed since `cex_client_config` | `cex_client_config` again |
| no command tree projection / no domain grammar | bundle not synced or the build has none | `cex_sync`; if still missing, the server has not published it for this build: tell the user |
| SHA256 mismatch | a downloaded file differs from the manifest | report it; do not retry around it |
| server unreachable (sync) | offline | the cached bundle is used; tell the user its `note` |
| the token belongs to another server | `server` changed | log in again |
