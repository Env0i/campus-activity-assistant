# 手机远程访问：离线验证与真机验收状态（2026-10-30 / 2026-10-31）

本文件只记时间、通道、状态与是否需要重新配对，不记账号、密码、验证码、
cookie、token、完整请求头或带查询参数的地址。

## 一、离线技术验证（已执行）

执行环境：Windows，仓库 HEAD `3cab0d6`，Python 3.12，Node 无外部依赖。

| 时间 | 命令 | 结果 |
|---|---|---|
| 2026-10-31 | `python -X utf8 -m unittest local.tests.test_tunnel_manager -v` | Ran 35 tests, OK |
| 2026-10-31 | `python -X utf8 -m unittest local.tests.test_credential_store local.tests.test_phone_session_store -v` | Ran 27 tests, OK |
| 2026-10-31 | `python -X utf8 -m unittest local.tests.test_phone_service local.tests.test_phone_http -v` | Ran 61 tests, OK |
| 2026-10-31 | `python -X utf8 -m unittest local.tests.test_tunnel_manager local.tests.test_application_services -v` | Ran 49 tests, OK |
| 2026-10-31 | `python -X utf8 -m unittest local.tests.test_phone_ui -v` | Ran 31 tests, OK |
| 2026-10-31 | `python -X utf8 -m unittest local.tests.test_phone_session_store local.tests.test_phone_service local.tests.test_phone_http local.tests.test_tunnel_manager local.tests.test_phone_ui` | Ran 138 tests, OK |
| 2026-10-31 | `python -X utf8 -m compileall local server` | exit 0 |
| 2026-10-31 | `node --check local/ui/app.js` / `local/ui/m/app.js` / `local/ui/views/phone.js` | exit 0 |
| 2026-10-31 | `git diff --check` | exit 0（仅 `docs/OPERATIONS.md`、`local/requirements.txt` 两条入场即存的换行警告） |

覆盖到的行为（离线、替身对象，非真实网络）：

- 探测契约：`tailscale_missing` / `tailscale_not_logged_in` / `probe_failed` /
  `connected` 四态互不冒充，`available: true` 只出现在 `connected`。
- 设备信任：只存 SHA-256；一年未用失效；手动关闭撤销；正常退出保留；
  伪造 token 拒绝；Cloudflare 通道永不进入恢复分支。
- 通道偏好：记住选择；选 Tailscale 才尝试启动时自动恢复，探测失败不监听端口。
- 帮助 UI：两个通道各自成句、MagicDNS 主地址 + `100.x` 备用地址、
  复制降级、切换通道记偏好、关闭改为阻断式确认行（取消不调停止接口）。

## 二、Tailscale 链路真机验证（本机 tailnet，2026-10-31）

环境事实（只读采集，不含凭据）：

- Tailscale 已安装并登录，守护进程与托盘程序都在运行；`BackendState` = `Running`。
- **安装包不写 PATH**：`shutil.which("tailscale")` 为空，可执行文件在
  `%ProgramFiles%\Tailscale	ailscale.exe`。首轮探测因此误报
  `tailscale_missing`，见下面的缺陷 D2。
- 节点 `Self.DNSName` 带尾点（`<node>.<tailnet>.ts.net.`），`TailscaleIPs` 含
  `100.100.121.82` 与一个 IPv6；`MagicDNSSuffix` 为 `<tailnet>.ts.net`。

验证方式：用真实 `Api` 开手机访问，真绑 `100.100.121.82:8765`，再用标准库
HTTP 客户端经 `http://<node>.<tailnet>.ts.net:8765` 与 `http://100.100.121.82:8765`
发请求。**不是手机浏览器**，见第四节边界。

| 检查 | 结果 |
|---|---|
| `tailscale_endpoint()` 探测 | PASS `state=connected`，`bind_host=100.100.121.82`，`public_host` 为 MagicDNS 名 |
| 开启手机访问 | PASS `address=http://<node>.<tailnet>.ts.net:8765`，`persistent_device: true` |
| 配对码 / 二维码 | PASS 6 位、二维码 682 字节 |
| 未配对读状态 | PASS 401 `need_pair` |
| 配对 | PASS 200，`Set-Cookie` 三条：`campus_phone_sid`、`campus_phone_csrf`、`campus_phone_device` |
| 配对后读状态 | PASS 200，活动列表可读 |
| `100.x` 备用地址读写 | PASS 200（首轮 403，见缺陷 D1） |
| 退出后重新开启 | PASS 地址不变（MagicDNS 固定） |
| 仅凭设备 cookie 恢复 | PASS 200，并回写新的 sid/csrf/device |
| 手动关闭后设备 cookie | PASS 401，撤销生效 |
| Cloudflare 通道 | 不可用，`resolve_cloudflared()` 为空 |

### 缺陷 D1：备用地址被自己拒掉（已修）

- 现象：帮助页展示「备用地址 `http://100.x:8765/`」，但用它访问返回
  `403 {"ok": false, "error": "bad_host"}`。
- 原因：`PhoneHttpServer` 的 Host/Origin 校验只认 `public_host`（MagicDNS 名），
  绑定地址不在白名单里。
- 修复：`local/domain/phone_rules.py` 增加 `hosts_allowed()` / `origins_allowed()`
  接受一组字面地址；`local/infrastructure/phone_http.py` 的 `_allowed_hosts()`
  按 scheme 分档——**http 直连认「MagicDNS 名 + 绑定地址」，https 隧道只认公网域名**，
  保证切到隧道后旧的本机 Host 立即失效。
- 锁定测试：`local/tests/test_phone_http.py::BackupHostTests` 三例
  （绑定地址能过、备用 origin 能配对、白名单外主机名仍拒绝）。

### 缺陷 D2：CLI 不在 PATH（已修）

- 现象：用户装好并登录 Tailscale 后，本程序仍报 `tailscale_missing`。
- 原因：Windows 安装包不把 `tailscale.exe` 写进 PATH。
- 修复：`local/infrastructure/tunnel_manager.py` 增加 `resolve_tailscale()`，
  先查 PATH，再查 `%ProgramFiles%`、`%ProgramFiles(x86)%`、`%LOCALAPPDATA%` 下的
  `Tailscale	ailscale.exe`；`tailscale_endpoint()` 改用它。
- 锁定测试：`local/tests/test_tunnel_manager.py::ResolveTailscaleTests` 三例。

## 三、Cloudflare 临时通道验收（本机链路已跑通）

- 二进制：`cloudflared 2026.10.7 (built 2026-10-30T09:43 UTC)`，放在
  `local/bin/cloudflared.exe`（55,390,512 字节，
  sha256 `2493dbc168923bb3e59e5e7716f71deced92992eea9acd6e9d74f84ac7751343`），
  由 `resolve_cloudflared()` 的第 2 个查找点命中；`local/bin/` 已加进 `.gitignore`，
  可执行文件不入库。后续「打包 / 让用户自己安装」的方式交 Codex 定稿。
- 验收脚本（临时目录，不入库）：起真实 `Api` → `start_phone_access("cloudflare")`
  → 等边缘路由就绪 → 经公网 https 域名做断言。**16 项全部 PASS**：

| 检查 | 结果 |
| --- | --- |
| `cloudflared` 已定位 | PASS（`local\bin\cloudflared.exe`） |
| 开启通道返回 `https://<随机>.trycloudflare.com` | PASS |
| 配对码为 6 位 | PASS |
| 公网首页可访问（含「手机」文案） | PASS（200，3800 字节） |
| 未配对 `GET /api/state` | PASS（401 `need_pair`） |
| `POST /pair`（Origin 为公网域名） | PASS（Set-Cookie：`campus_phone_sid` + `campus_phone_csrf`） |
| **Cloudflare 不签发设备信任** | PASS（无 `campus_phone_device`） |
| 带会话读状态 | PASS（200，1126 字节，含 activities） |
| 伪造 Origin（`https://evil.example`） | PASS（403） |
| 通道状态投影为 `running` | PASS |
| 关闭后地址清空 / 隧道进程停止 | PASS |
| 再次开启得到**不同**域名 | PASS |
- 域名在证据里一律写成 `https://<随机>.trycloudflare.com`，不记具体值（一次性域名，
  记下来也打不开）。
- 环境说明（复现时要照做）：本机系统 DNS 解析不了 `*.trycloudflare.com`（解析超时），
  且 Python 的 HTTPS 出站不可用（直连超时、经本机代理 403），所以验收用 `curl`
  （先走 `127.0.0.1:7897` 代理、失败再直连）探测；**这不影响产品**——电脑只做源站，
  由 cloudflared 向外建连，域名由手机侧解析。
- 手机端（用户真机，2026-10-31 10:00）：切到 Cloudflare → 开启 → 扫码 → 输配对码 → 进入列表；
  同一隧道存活期间用**微信扫码再次进入不需要配对码**。也就是说会话 cookie 在浏览器里留住了，
  只有「重新开隧道 / 重启程序换域名」才需要重新配对，与临时地址的预期一致。

## 四、验收边界

- 第二节是**本机链路 + HTTP 客户端**，不是手机浏览器：没有验证 iOS/Android
  的 cookie 策略、后台休眠后的恢复、VPN 断开时「先打开 Tailscale」的实际观感。
- 第三节同样只是「公网域名可达 + 协议行为正确」，**手机经 https 打开、配对、
  地址漂移后要求重新扫码**这三条仍需人工在手机上确认。
- 物理手机端到端（扫码 + 输入配对码 + 重启后免配对 + 关闭后立即失效）仍需人工验收。
- 未验证学校链路：配对、恢复、重登挑战都只在本机替身接口上跑过。
- 本文件不构成「手机端已通过」的结论。
