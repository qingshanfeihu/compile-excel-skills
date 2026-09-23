# 环境绑定（首次使用 Setup）

## 绑定文件查找顺序

1. `$COMPILE_EXCEL_ENV` 显式路径
2. `<工作区>/.circle/compile-excel.env`（项目级）
3. `~/.config/compile-excel/env`（用户级）

三级都未命中 → 走下面的访谈；命中任意一级 → 直接 preflight。

## 访谈流程（一次问一项，给默认值）

1. KMS 服务地址（host:port）
2. 跳转机 IP（及可选用户名/端口）
3. 写入非机密项：
   ```bash
   scripts/bind_env.sh --target <目标路径> KMS_ADDR=host:port JUMPHOST_IP=ip JUMPHOST_PORT=22
   ```
   目标已存在需用户确认后加 `--force`。
4. 收跳转机/APV 凭据（见下）
5. `scripts/preflight.py` 探活，**先报告再征得确认**，然后才进入编译

## 凭据通道

密码类值不进对话、不进日志；两条通道按 harness 能力选：

- **circle（有 secret UI）**：question 工具机密提问（`secret: true` + `key` +
  `target_file`）——掩码输入、harness 直写 env 文件、对话只见"已收集"
- **其他 harness / 兜底**：
  ```bash
  printf 问题答案由用户在终端输入 | scripts/collect_credentials.sh --target ~/.config/compile-excel/env
  ```
  `read -s` 不回显，直写 600 文件；目标已存在拒绝覆盖（`--force` 显式覆盖）

凭据文件（600）与项目级 env 分开存放；skill 目录内**禁止**放任何 env/凭据
（升级覆盖即丢）。

## env 文件字段

| 键 | 必填 | 说明 |
|---|---|---|
| `KMS_ADDR` | 是 | host:port，preflight TCP 探活 |
| `JUMPHOST_IP` | 是 | 跳转机 |
| `JUMPHOST_PORT` | 否 | 缺省 22 |
| `JUMPHOST_USER/JUMPHOST_PASS` | 部署期 | 凭据通道写入用户级 env |
| `APV_USER/APV_PASSWORD/APV_ENABLE_PASSWORD` | 部署期 | 同上 |
