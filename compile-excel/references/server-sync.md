# 分发服务器对接（可选）

本地编译不依赖服务器；需要同步工件/检索手册时才走本节。

## 环境变量

| 变量 | 缺省 | 说明 |
|---|---|---|
| `COMPILE_EXCEL_SERVER` | `http://127.0.0.1:8900` | 服务器地址 |
| `COMPILE_EXCEL_CONFIG_DIR` | `~/.config/compile-excel` | token 目录（透传给子进程时保持一致） |
| `COMPILE_EXCEL_CACHE_DIR` | `~/.cache/compile-excel` | 工件缓存 |
| `IST_ENGINE_ROOT` | 自动探测同级 | InfoTest 引擎根（verify Layer 2 用；**记得透传给 execute 子进程**） |

## 三条命令

```bash
python3 scripts/login.py       # 设备授权流一次：浏览器点【授权】；token 落 600
python3 scripts/fetch.py       # manifest→下载→逐件 SHA256 校验；不符即拒；
                               # 断网回退缓存并明示版本（缓存缺失则报错）
python3 scripts/docs_query.py --q "check_point found_times" --limit 3
```

- token 过期自动用 refresh_token 换新（401 内部重试一次）；刷新失败报
  `请重新 login`，此时重跑 `login.py` 再授权一次即可。
- 缓存布局：`~/.cache/compile-excel/<device_build>/<工件>` + `manifest.json`。

## 服务器侧（部署/运维）

compile-excel-server 独立项目（GitHub: qingshanfeihu/compile-excel-server）：
一键安装、`ces setup` 配置向导、`ces` 管理菜单。skill 侧无需关心其部署。
