# 宿主机执行勾选表（S2）

按 `RUNBOOK.md` 逐项执行后填写本表。每项要么有结果文件，要么写明「未测」及原因。不要粘贴账号、隧道地址、tailnet 名、100.x 地址或地址栏截图。

## 环境

- 执行日期：2026-11-12
- Windows 版本：Windows 11（10.0.26300），PowerShell 5.1.26100.9711
- Python / pywebview / PyInstaller（PyInstaller 写清是用的已有版本还是本次装的）：Python 3.12.9 / pywebview 6.2.1 / PyInstaller 6.22.3（用发版构建环境已有版本，未新装）
- WebView2 运行时：157.0.4341.46
- 是否装了 Inno Setup：（本手册不运行安装器，此项可不填）

## H1 真实产品加载方式（只用 `--demo`，按进程树取证）

先关掉正在用的产品，再逐个启动下表两个形态，每个形态启动两次。

| 形态 | file_version | 监听端口（两次） | `index.html` 状态码 | head 首行 | 停止后端口是否为空 | 结果文件 |
|---|---|---|---|---|---|---|
| 已装 1.2.2 安装版 | 空（EXE 无版本资源，以 `versions\1.2.2` 目录为准） | 32214 / 6840 | 200 | `<!doctype html>` | 是（两次均为空） | `host-product-installed-1.2.2-run1.json`、`-run2.json` |
| 已发布 1.2.2 独立 EXE | 空（同已装版，无版本资源；sha256 与发布 manifest 一致） | 21155 / 40881 | 200 | `<!doctype html>` | 是（两次均为空） | `host-product-standalone-1.2.2-run1.json`、`-run2.json` |

两次启动的端口是否每次不同：是（已装版 32214 → 6840；独立 EXE 21155 → 40881），两种形态都从 `127.0.0.1:<随机端口>` 取到 `index.html`。

结论（两种形态是否都经 `127.0.0.1:<随机端口>` 供页）：成立。已装版与已发布独立 EXE 在 `--demo` 下均经随机回环端口供页，两次启动端口不同，停止后端口释放；窗口均显示「演示模式 内存样例」。

## H2 file-url-noallow 对照（E1，onefile）

| 项 | 结果 | 结果文件 |
|---|---|---|
| file-url-noallow × 纯英文目录 | `allow_file_urls=false`、`is_pywebview_default=false`、`snapshot.ready=false`、`snapshot.caps={}`（对照组，模块未运行） | `host-onefile-plain-file-url-noallow.json` |
| file-url-noallow × 含空格目录 | 同上：`false` / `false` / `ready=false` / `caps={}` | `host-onefile-space-file-url-noallow.json` |
| file-url-noallow × 中文含空格目录 | 同上：`false` / `false` / `ready=false` / `caps={}` | `host-onefile-cjk-file-url-noallow.json` |

每个文件要核对的字段：`allow_file_urls`（应为 false）、`allow_file_urls_is_pywebview_default`（应为 false）、`snapshot.ready`、`snapshot.caps`。

## H6 打包样机

| 项 | 结果 | 结果文件 |
|---|---|---|
| onefile × 纯英文目录 | 7/7 场景写出；`product` 的 `ready=true`、`caps.all_caps_ok=true`、`h11` 的 `fallback.shown=true` | `host-onefile-plain-*.json` |
| onefile × 含空格目录 | 7/7 场景写出，结果同纯英文目录 | `host-onefile-space-*.json` |
| onefile × 中文含空格目录 | 7/7 场景写出；`ready=true`、`caps` 有值 | `host-onefile-cjk-*.json` |
| onefile 连跑 5 次 | 5/5 写出，`ready=true` 5/5 | `host-onefile-plain-run01..05.json` |
| onedir × 三种目录 | 三目录各 7/7 场景写出，`product` 均 `ready=true`、`caps.all_caps_ok=true` | `host-onedir-*.json` |

三种目录里是否有任一场景 `ready=false`，或结果文件缺失：无缺失；`ready=false` 只出现在 `h11`（预期兜底）与 `h9-*`/`file-url-noallow`（非 product 场景），`product` 场景三目录全部 `ready=true`。

## H7 版本与源码

| 项 | 结果文件 | 备注 |
|---|---|---|
| 组件版本 | `host-versions.json` | 7 个字段齐全，无「未安装」 |
| WebView2 运行时 | `host-webview2-version.txt` | 157.0.4341.46 |
| pywebview 三处源码 | `host-pywebview-source.txt` | `is_local_url`、`has_local_urls` + `http.start_global_server`、`ALLOW_FILE_URLS` 三段齐全 |

## H8 / H9 / H10 手机真机

每台设备、每个浏览器、每个通道一行。「结果」写「通过」「有失败」「未测」。

| 设备 / 系统 | 浏览器 | Tailscale | Cloudflare | 备注（失败的页面、UA 摘要） |
|---|---|---|---|---|
| iPhone 15（iOS 18.7，Safari 27.0.1） | 系统浏览器 | 通过（32 条上报，0 失败） | 通过（48 条上报，0 失败） | `h3` 出现预期 `ReferenceError: Cannot access 'a' before initialization`；`h9` 四形态各 3 次、`esm_count=40`；`h11` 兜底 Tailscale 5/5、Cloudflare 3/3；`h2` 在 Cloudflare 4 次（`ready=true`，1613–2794ms），在 Tailscale 仅 1 次 |

未测说明：本轮只测系统浏览器（Safari），两条通道均已完成。

补充说明：

- 没测的平台写「未测：没有设备」或「未测：不用该浏览器」，不算失败。
- H9 的耗时看各 `phone-*-*.json` 里的 `payload.done_ms`（同一导航内的时间基准）。
- 每种通道结束后确认服务日志末行 `端口已释放=True`。

## H11 失败时用户看到什么

| 环境 | 兜底提示是否出现 | 出现时间（约） | 结果文件 |
|---|---|---|---|
| 桌面（样机打包） | 是 | 约 5 秒（`fallback.shown=true`） | `host-*-h11.json` |
| 手机（Tailscale） | 是 | 约 5 秒（5/5 上报 `fallback.shown=true`） | `phone-tailscale-*.json` |
| 手机（Cloudflare） | 是 | 约 5 秒（3/3 上报 `fallback.shown=true`） | `phone-cloudflare-*.json` |

## 收尾

- `git status --short` 是否只动了 allowed_paths：是。新增 `design/evidence/2026-11-12/esm-verify/` 与既有的 `design/evidence/2026-11-12/refactor-audit/`；`M design/proposals/engineering-refactor.md` 为开工前已存在的改动，非本次产生。
- `redact.py --check` 是否全部 PASS：是，`results/` 下 167 个文件全部 PASS。
- `__pycache__` 是否为空：是，无输出。
- 未完成 / 异常项及原因：`h2` 在 Tailscale 通道只跑了 1 次（规范 3 次；同一页面在 Cloudflare 通道已 4 次通过）。其余项目完成。手册 3.4/3.5/3.6/3.7 与 2.2 的命令在 PowerShell 5.1 下有缺陷，见「备注」。

## 备注（原样贴报错，不改写）

- 3.4 / 3.5 / 3.6 / 3.7：按手册原样用 `& <exe> ...` 执行时，PowerShell 5.1 不会等待 GUI 子进程，21 次启动瞬间返回，结果文件 0 个。改用 `Start-Process -Wait` 顺序执行后全部写出；探针脚本未改。
- 2.2 的 `Invoke-DemoProbe` 中 `$r = Invoke-WebRequest` 会覆盖结果目录变量 `$R`（PowerShell 变量名不区分大小写），首次执行写盘报 `Join-Path : 找不到驱动器`。把响应变量改名为 `$resp` 后正常，结果字段未改。
- 已装 `campus-activity-watch.exe` 无版本资源，`FileVersion` / `ProductVersion` 均为空；H1-A 的版本以安装目录 `versions\1.2.2` 为准，未改写结果。
- 手机段：Tailscale 通道启动后约 15 分钟到时自动退出，32 条上报全部无 `ok=false`（`h9` 25 条、`h11` 5 条、`h3` 1 条、`h2` 1 条）；Cloudflare 通道启动后约 15 分钟到时自动退出（末行 `端口已释放=True`），48 条上报全部无 `ok=false`（`h9` 40 条、`h2` 4 条、`h11` 3 条、`h3` 1 条）。两条通道都用组件包自带的 `cloudflared` / Tailscale，服务地址只出现在运行时输出，未写入任何结果文件（日志已脱敏）。
- 窗口被其他窗口遮挡，截屏改用 `PrintWindow(PW_RENDERFULLCONTENT)` 直接抓窗口内容；两次启动均显示「演示模式 内存样例」，无登录要求，H1-A 取证有效。
