# 手机远程访问：通道分层与固定入口（讨论材料，供 Codex 定稿）

> 本文是 `/discuss` 流水线①段的产出，是②段「出 plan.yaml + executor brief」的输入。
> 代码取证基于 HEAD `3cab0d6dfeb2dccbcd5d7ff86d23b49958b368f5`，路径均为仓库相对路径。
> 本轮讨论所属计划的上一轮执行结果：`.claude/results/20261030-phone-ui-failure-repair-result.yaml`（execution completed / verification passed / acceptance pending_user_review）。

## 目标

让「手机控制」在用户离开电脑后仍然可用：**配对一次之后，程序重启、电脑重启、手机切换网络都不需要回到电脑旁重新扫码。**

## 已拍板（含理由）

1. **三层分离**：功能层（`phone_control` / `relogin_ocr` 组件包）／通道层（Tailscale、Cloudflare，外部程序）／会话层（6 位配对码 + CSRF cookie）。
   理由：Tailscale 不是我们的功能，后端本来就是这个形状（`channels` 与 `features` 平级返回）；上一轮修掉的 bug 正是层间串台（OCR 状态影响了手机面板的 `detail.hidden`）。
2. **默认通道 = Tailscale**。
   理由：它是当前唯一「已实现 + 能提供固定入口」的通道（IP 在 `100.64.0.0/10` 内稳定、MagicDNS 名稳定、端口固定 8765）；Cloudflare quick tunnel 每次换随机域名，导致「人在外面无法自助恢复」。讨论中曾一度主张 Cloudflare 优先，被真实断线场景推翻，已修正。
3. **Cloudflare quick tunnel 保留为临时降级通道**，UI 必须写明「重启后要重新扫码」。
   理由：无需账号、可立即用，作为过渡与降级有价值；但不能让用户误以为是稳定方案。
4. **不打包、不代发 Tailscale 安装包。**
   理由：BSD-3 允许再分发，但它是常驻系统服务 + 独立更新通道 + 需管理员权限 + 版本冲突风险，我们会变成 VPN 客户端分发方，收益不抵风险。
5. **不自行下载执行任何安装程序**；未来若做自动下载，必须 pin 版本 + 内嵌 sha256 + 用户显式确认。
6. **必须提供应用内最小教程**（四步 + 一行自诊断 + 可复制的固定地址）。
   理由：这是必需的前置条件，藏进折叠区会让用户出门后才发现失效；首次向导不能「默认隐藏」。
7. **「我已装好，重新检测」必须真实调用探测**，不要求用户重启程序。
   理由：`tailscale_endpoint()` 已能区分「没装 / 装了没登录」，装完立刻可判。
8. **关闭手机访问时明确告知**「手机将失去访问，需要重新扫码」。
   理由：当前是无声失效，用户事后才发现。
9. **命名隧道、自建固定域名中继首版不做。**
   理由：前者需 Cloudflare 账号 + 自备域名；后者需自营边缘服务并承担转发责任。
10. **与此前 Codex 方案保持一致**：Tailscale 为默认通道，Quick Tunnel 为第二通道。

## 未决项

以下 9 条**没有定**，Codex 遇到请逐条问用户，不要自行填默认值。

1. 首次向导的形态：内联面板／模态对话框／分步向导 —— **未定**（UI 设计）。
2. 「记住通道选择」的落点：现有 prefs 机制加键 vs 新文件 —— **未定**（需先核对该项目 prefs 结构）。
3. 「临时地址」方案在 UI 中的位置：与 Tailscale 并列第三选项 vs 收进「高级」折叠区 —— **未定**。
4. 地址展示：只给 MagicDNS 名，还是同时给 `100.x` 原始 IP —— **未定**（代码当前 `public_host` 优先 MagicDNS）。
5. 教程是否配截图／录屏 —— **未定**。
6. 是否为 cloudflared 增加看门狗（崩溃自动重启、旧地址宽限 60 秒）—— **未定**，影响「临时通道」体验。
7. 「加进手机书签」是否做成按钮，还是仅文案 —— **未定**。
8. 关闭手机访问时的提示：阻断式确认 vs 非阻断文案 —— **未定**。
9. 是否为 `phone_access_state` 新增字段（如 `channels[*].guide_url`）—— **未定**；一旦新增，改动就越过「纯 UI」边界，需要同步改后端与测试。

## 代码取证

以下全部在 HEAD `3cab0d6dfeb2dccbcd5d7ff86d23b49958b368f5` 上核对过。`local/ui/` 与 `local/tests/test_phone_ui.py` 在上一轮已改，行号以当前工作区为准，**建议按函数名定位**。

| 位置 | 事实 |
|---|---|
| `local/app.py:786-812` | `advanced_features_state()`：`features` 与 `channels` 平级；`channels.tailscale = tailscale_endpoint()`；`channels.cloudflare.error = "cloudflared_missing"`，text「可用时由 Cloudflare 临时地址提供远程访问。」 |
| `local/app.py:822-841` | `install_advanced_feature()`：frozen 时 `create_file_dialog(OPEN, 组件包 *.zip)`，用户取消返回 `{ok:True, canceled:True}` |
| `local/app.py:1849-1868` | `phone_access_state()`：返回 `feature/running/channel/address/qr/pair_code/supported/advanced` |
| `local/app.py:1874-1912` | `_start_phone_access()`：`feature_ready(PHONE_CONTROL)` 检查（`feature_required`「请先在帮助里的高级功能安装手机控制。」）→ `bad_channel` → `tailscale_endpoint()` 可用性检查（带 error + text）→ Cloudflare 启动 |
| `local/infrastructure/tunnel_manager.py:53-77` | `tailscale_endpoint()`，文档串「只读探测；不自动安装、不改防火墙、不启动守护进程」；error ∈ `tailscale_missing` / `tailscale_not_logged_in` / `tailscale_probe_failed` / 可用；可用时给 `bind_host` / `addresses` / `magicdns` / `public_host`（`public_host = magic or addresses[0]`） |
| `local/infrastructure/tunnel_manager.py:80-94` | `resolve_cloudflared()`：组件包 → `bin/cloudflared.exe` → `shutil.which` |
| `local/infrastructure/tunnel_manager.py:108-154` | `CloudflareTunnel.start()` 执行 `[exe, "tunnel", "--url", local_url]` —— **仅快速隧道**，无 `--token`、无 config；从 stdout 用 `URL_RE` 抓 URL |
| `local/infrastructure/tunnel_manager.py:156-172` | `CloudflareTunnel.stop()` terminate→kill 并清空 `public_url` |
| `local/domain/phone_rules.py:21` | `HTTP_PORT = 8765`（端口固定） |
| `local/domain/phone_rules.py:77` | `literal_origin(host, port=HTTP_PORT)` |
| `local/application/phone_service.py:59` / `:90` / `:145` | `address()` / `start(host, port=HTTP_PORT, ...)` / `set_public_url()` |
| `local/ui/views/phone.js` 的 `paint()` | 只用 `channels` 填 `#phone-channel` 的选中值，**从未渲染 `state.advanced.channels[*].text`** —— 这是本方案的核心缺口 |
| `local/ui/index.html:226-258` | 帮助弹窗「跨设备访问与高级功能」段；`:243` 上一轮新增 `id="ocr-feature-status"` |
| `local/tests/test_phone_ui.py` | `PHONE_JS_HARNESS`：`sandbox.$` 做 `#` 归一化、`document` 含 `cookie` 属性；上一轮后 24/24 通过 |
| `local/ui/m/app.js` | `readCookie()`、`poll()` 的 CSRF 兜底与 `pair/app` 切换、`ingest()` 的 `state.login_relay` 快照、`endReloginControls()`、`refreshRelogin()` —— 上一轮已实现 |

## 补充取证（联网核准，2026-10-30）

| 项 | 结论 | 来源 |
|---|---|---|
| Cloudflare quick tunnel 限制 | 官方明确：**no uptime guarantee**；每个隧道最多 **200 个 in-flight 请求**，超出返回 `429`；**不支持 SSE**；**hostname 每次创建都变**；支持 `--allowed-mail` 限制访问 | [Quick Tunnels · Cloudflare Docs](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/) |
| Tailscale 免费额度 | 官方明确：Personal 计划**个人免费永久**、**设备数不限**（Unlimited user devices）、**最多 6 个用户**、非商业用途；用 Gmail／GitHub 等公开域名注册会自动进入 Personal | [Pricing](https://tailscale.com/pricing)、[Free pricing plans](https://tailscale.com/docs/account/manage-plans/free-plans-discounts) |
| 「已安装未登录」判定 | **未定稿**：`tailscale status --json` 的 `BackendState` 可区分状态，但官方 CLI 文档页未逐条列出取值 → 落地时必须实测（见未验证假设 8） | [Tailscale CLI](https://tailscale.com/docs/reference/tailscale-cli) |

对材料的影响：

- 已知坑 #10 由「记忆取证」升级为「官方文档核实」，可以直接写进文案：并发 200／`429`／不支持 SSE／无 uptime 保证。
- 教程文案可以放心写「个人版设备数不限（最多 6 个用户）」，不必含糊。
- 「重新检测」的判定条件还不能定稿，Codex 需先做一次真机取证。

## 硬约束

- 只服务本人账号；不新增局域网入口；远程通道只允许 Tailscale 与 Cloudflare。
- 配对码不进 URL、不落日志、不推送手机；不复述账号密码验证码。
- 不改学校登录协议、数据模型、登录态机制。
- 不引入新依赖；不修改 `local/data`、`server/data`、`.venv`、`node_modules`、`server/`。
- 新增文档不写本机绝对路径与临时目录路径；证据放 `design/evidence/<YYYY-MM-DD>/`。
- 任何代码改动**必须先出新计划**（上一计划 `20261030-phone-ui-failure-repair` 已执行完毕、guard 已释放为 `active: false`）；`git commit` 需用户授权。

## 验收判据

1. `python -X utf8 -m unittest local.tests.test_phone_ui -v` ≥ 24 tests 全绿，且新增断言覆盖通道状态渲染（例如断言 `#channel-tailscale-status` 的 textContent）。
2. `node --check local/ui/app.js`、`node --check local/ui/m/app.js` 均 exit 0。
3. 改动文件严格 UTF-8 解码通过（`[Text.UTF8Encoding]::new($false,$true)`）+ 乱码黑名单 0 命中。
4. **真机证据（缺一不可）**：
   a. Tailscale：配对一次 → 重启程序 → 手机从书签打开，不出现配对页；
   b. 重启电脑后同上；
   c. 手机 Wi-Fi ↔ 移动数据切换后仍可操作，不重新配对；
   d. 关闭手机访问后，手机下一次轮询回到配对页；
   e. Cloudflare 临时通道：重启后地址变化，UI 出现「需重新扫码」提示。
5. `docs/PHONE_ACCESS.md` 与帮助页文案同源（同一套四步），不含未落地的下载指引。

## 已知坑

1. 手机刷新后写操作 401 —— 地址 origin 变了，或 CSRF 未从 `document.cookie` 恢复（上一轮已修：`readCookie` + `poll()` 兜底）。
2. 直接快照被忽略 —— `ingest()` 不处理 `payload.state.login_relay`（上一轮已修）。
3. 帮助页两功能状态串台 —— `paint()` 只用单一 ready 控制 `detail.hidden`（上一轮已修：逐行 `featureCopy`）。
4. 取消导入后弹失败提示 —— `install()` 未判 `canceled` 就 `helpStatus`（上一轮已修）。
5. 保存凭据异常外逃 —— `saveCredentials()` 无 catch（上一轮已修，且不显示异常原文）。
6. `$ is not defined` —— 测试 harness 只在 files 分支注入 `$`（上一轮已修为全局）。
7. 同一元素被判成两个 —— harness 的 `el2` 以选择器字符串为键缓存，`"#id"` 与 `"id"` 不归一（上一轮已在 `sandbox.$` 归一化）。
8. **quick tunnel 地址每次变** —— `stop()` 清空 `public_url`，`start()` 用 `--url` 无可复用凭证 → cookie 的 origin 失效 → 免配对失效。
9. **隧道崩溃无人重启** —— `CloudflareTunnel` 无看门狗；进程死了 URL 立即不可用。
10. **quick tunnel 的能力上限（官方已核实）** —— 无 uptime 保证、每隧道最多 200 in-flight 请求（超出 `429`）、不支持 SSE。因此长轮询可行、SSE 不可行；不要把大文件或长连接设计进这条通道。

## 未验证假设

1. **两条通道在本机均未实测**：2026-10-30 只读探测显示 `tailscale` CLI 不存在（`tailscale_missing`）、`resolve_cloudflared()` 返回空（`cloudflared_missing`）、`local/data` 下也没有已保存凭据。
2. 「固定入口」成立的前提是 MagicDNS 名可解析、且手机端 Tailscale 处于连接状态 —— **推断**。
3. iOS／Android 后台挂起后需手动打开 Tailscale app —— **推断**，本轮未实测。
4. `phone_service.address()` 是否已用 `public_host` 拼出完整 URL —— 部分取证（`start(host, ...)` 与 `set_public_url()` 存在，拼接路径未逐行确认）。
5. `local/` 是否具备「向本人飞书发消息」的能力 —— 仅字符串命中（`local/README.md`、`config.example.json`、`grab.py`、`ui/index.html`），**能力未核实**。
6. cookie 在 MagicDNS 名与 `100.x` 两种 host 下是否都成立 —— 未实测（换 host 即换 origin，需确认用户只用一个地址）。
7. `CloudflareTunnel.start()` 的 20 秒等待 URL 超时在慢网络下是否够 —— 未实测。
8. **`tailscale status --json` 的 `BackendState` 取值枚举未核实** —— 官方 CLI 文档页未列出；Codex 需在本机实测「已安装未登录／已连接／已断开」三种状态的原始 JSON，把字段名与取值钉死再写判定逻辑。

---

**交给 Codex 的开场句**

> 请先核对本材料「代码取证」表里的路径与行号是否与当前 HEAD（3cab0d6dfeb2dccbcd5d7ff86d23b49958b368f5）一致，如有偏移先更正再动手；按「已拍板」出 plan.yaml 与 executor brief；「未决项」9 条逐条问我，不要自行填默认值；动手前先完成「未验证假设 8」的真机取证。出完 plan 先停下等我确认，不要直接执行。
